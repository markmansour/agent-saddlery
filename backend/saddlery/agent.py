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
from saddlery.permissions.gate import PolicyRequest
from saddlery.permissions.shell import ShellCommand
from saddlery.tools.base import ResourceError
from saddlery.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from saddlery.llm.base import LLMProvider
    from saddlery.permissions.gate import PermissionGate
    from saddlery.session import Session
    from saddlery.tools.base import Tool
    from saddlery.transport.base import EventSink

    Emit = Callable[[Event], Awaitable[None]]

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
                        result_content, is_error = await self._run_tool_call(
                            call, tool, session, emit
                        )
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

    async def _run_tool_call(
        self, call: ToolCallDelta, tool: Tool, session: Session, emit: Emit
    ) -> tuple[str, bool]:
        """Gate (when configured) and execute one tool call. Returns (content, is_error)."""
        gate = self.permission_gate
        if gate is not None:
            try:
                request = PolicyRequest(
                    tool_name=call.name,
                    arguments=call.input,
                    principal=session.principal,
                    capability=tool.capability,
                    resource=tool.resource(call.input),
                    tainted=session.is_tainted(),
                    detail=tool.detail(call.input),
                )
            except ResourceError as exc:
                return f"Invalid arguments: {exc}", True
            decision = await gate.check(request)
            if decision == "ask":
                decision = await self._ask(call, request, session, emit)
                gate.remember(request, decision)
            if decision == "deny":
                return self._denial_message(request), True
            try:
                changed = tool.resource(call.input) != request.resource
            except ResourceError:
                changed = True
            if changed:
                return "Permission denied: the target changed after approval.", True
        outcome = await tool.call(call.input)
        return outcome.content, outcome.is_error

    async def _ask(
        self, call: ToolCallDelta, request: PolicyRequest, session: Session, emit: Emit
    ) -> Literal["allow", "deny"]:
        """Emit a PermissionRequest, suspend until resolve_permission(), emit the decision."""
        sid, principal = session.session_id, session.principal
        await emit(
            PermissionRequest(
                session_id=sid,
                principal=principal,
                tool_call_id=call.id,
                tool_name=call.name,
                arguments=call.input,
                capability=request.capability,
                resource=list(request.resource),
                tainted=request.tainted,
            )
        )
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_decisions[call.id] = future
        try:
            decision = await future
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
        return decision

    @staticmethod
    def _denial_message(request: PolicyRequest) -> str:
        if isinstance(request.detail, ShellCommand) and request.detail.kind == "rejected":
            return "Compound commands are not supported. Run each command separately."
        return "Permission denied"

    async def resolve_permission(
        self, tool_call_id: str, decision: Literal["allow", "deny"]
    ) -> None:
        future = self._pending_decisions.get(tool_call_id)
        if future is not None and not future.done():
            future.set_result(decision)
