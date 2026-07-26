"""The Agent: an immutable config + the run() loop over the event stream."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from saddlery.events import (
    AssistantMessage,
    AssistantMessageDelta,
    ErrorEvent,
    Event,
    PermissionDecision,
    PermissionRequest,
    RunFinished,
    RunStarted,
    ToolCall,
    ToolResult,
)
from saddlery.llm.base import TextDelta, ToolCallDelta
from saddlery.messages import Message
from saddlery.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from saddlery.llm.base import LLMProvider
    from saddlery.permissions.gate import PermissionGate
    from saddlery.session import Session
    from saddlery.transport.base import EventSink

DEFAULT_MODEL = "claude-haiku-4-5"


@dataclass(frozen=True)
class Agent:
    provider: LLMProvider
    system_prompt: str = "You are a helpful assistant."
    model: str = DEFAULT_MODEL
    tools: ToolRegistry = field(default_factory=lambda: ToolRegistry([]))
    max_tool_iterations: int = 8
    permission_gate: PermissionGate | None = None
    _pending_decisions: dict[str, asyncio.Future] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    async def run(self, session: Session, sink: EventSink) -> None:
        sid = session.session_id
        principal = session.principal

        async def emit(event: Event) -> None:
            session.append(event)
            await sink.emit(event)

        await emit(RunStarted(session_id=sid, principal=principal))
        try:
            for _iteration in range(self.max_tool_iterations):
                # Rebuild messages fresh from the event log fold (single source of truth)
                messages = [
                    Message(role="system", content=self.system_prompt),
                    *session.to_messages(),
                ]
                parts: list[str] = []
                tool_calls: list[ToolCallDelta] = []

                # Stream from provider
                async for delta in self.provider.stream(
                    messages, model=self.model, tools=self.tools.specs()
                ):
                    if isinstance(delta, TextDelta):
                        parts.append(delta.text)
                        await emit(
                            AssistantMessageDelta(
                                session_id=sid, principal=principal, text=delta.text
                            )
                        )
                    elif isinstance(delta, ToolCallDelta):
                        tool_calls.append(delta)

                # Emit any accumulated text as final assistant message
                if parts:
                    await emit(
                        AssistantMessage(
                            session_id=sid,
                            principal=principal,
                            content="".join(parts),
                        )
                    )

                # If no tool calls, we're done
                if not tool_calls:
                    break

                # Execute each tool call
                for call in tool_calls:
                    await emit(
                        ToolCall(
                            session_id=sid,
                            principal=principal,
                            tool_call_id=call.id,
                            tool_name=call.name,
                            arguments=call.input,
                        )
                    )
                    tool = self.tools.get(call.name)
                    if tool is None:
                        result_content, is_error = f"Error: unknown tool '{call.name}'", True
                    else:
                        decision: str = "allow"
                        if self.permission_gate is not None:
                            decision = await self.permission_gate.check(
                                call.name, call.input, principal
                            )
                            if decision == "ask":
                                await emit(
                                    PermissionRequest(
                                        session_id=sid,
                                        principal=principal,
                                        tool_call_id=call.id,
                                        tool_name=call.name,
                                        arguments=call.input,
                                    )
                                )
                                decision_future: asyncio.Future = (
                                    asyncio.get_running_loop().create_future()
                                )
                                self._pending_decisions[call.id] = decision_future
                                try:
                                    decision = await decision_future
                                finally:
                                    del self._pending_decisions[call.id]
                                await emit(
                                    PermissionDecision(
                                        session_id=sid,
                                        principal=principal,
                                        tool_call_id=call.id,
                                        decision=decision,
                                    )
                                )
                                self.permission_gate.remember(call.name, principal, decision)
                        if decision == "deny":
                            result_content, is_error = "Permission denied", True
                        else:
                            outcome = await tool.call(call.input)
                            result_content, is_error = outcome.content, outcome.is_error
                    await emit(
                        ToolResult(
                            session_id=sid,
                            principal=principal,
                            tool_call_id=call.id,
                            content=result_content,
                            is_error=is_error,
                        )
                    )
                # Loop back to step 1: rebuild messages, call provider again
            else:
                # Loop completed max_tool_iterations without breaking
                await emit(
                    ErrorEvent(
                        session_id=sid,
                        principal=principal,
                        message=f"Exceeded max_tool_iterations ({self.max_tool_iterations})",
                    )
                )
        except Exception as exc:  # broad on purpose: failures are recorded as events, not raised
            await emit(
                ErrorEvent(
                    session_id=sid,
                    principal=principal,
                    message=f"{type(exc).__name__}: {exc}",
                )
            )
        finally:
            await emit(RunFinished(session_id=sid, principal=principal))

    async def resolve_permission(
        self, tool_call_id: str, decision: Literal["allow", "deny"]
    ) -> None:
        future = self._pending_decisions.get(tool_call_id)
        if future is not None and not future.done():
            future.set_result(decision)
