import React, { useState, useEffect, useRef } from "react";
import { Box } from "ink";
import MessageHistory from "./MessageHistory.js";
import InputBox from "./InputBox.js";
import StatusLine from "./StatusLine.js";
import { CoreSubprocess } from "../core/subprocess.js";

interface Message {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  toolName?: string;
  isError?: boolean;
}

const ChatApp = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState("Initializing...");
  const [sessionId, setSessionId] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const coreRef = useRef<CoreSubprocess | null>(null);
  const pendingMessageIdRef = useRef<string | null>(null);

  // Initialize core subprocess
  useEffect(() => {
    const initCore = async () => {
      try {
        const core = new CoreSubprocess();
        setStatus("Starting core...");

        await core.start();
        coreRef.current = core;
        setSessionId(core.getSessionId());
        setStatus("Ready");

        // Handle events from core
        core.on("run_start", () => {
          setStatus("Processing...");
          setIsRunning(true);
        });

        core.on("assistant_delta", (text: string) => {
          // Update the pending assistant message with the delta
          const msgId = pendingMessageIdRef.current;
          if (msgId) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === msgId ? { ...msg, content: msg.content + text } : msg
              )
            );
          }
        });

        core.on("tool_call", (call: { id: string; name: string; arguments: Record<string, unknown> }) => {
          const toolMsg: Message = {
            id: `tool-${call.id}`,
            role: "tool",
            content: `→ ${call.name}(${JSON.stringify(call.arguments)})`,
            toolName: call.name,
          };
          setMessages((prev) => [...prev, toolMsg]);
        });

        core.on("tool_result", (result: { id: string; content: string; isError: boolean }) => {
          const resultMsg: Message = {
            id: `tool-result-${result.id}`,
            role: "tool",
            content: result.isError ? `✗ ${result.content}` : `← ${result.content.slice(0, 200)}`,
            isError: result.isError,
          };
          setMessages((prev) => [...prev, resultMsg]);
        });

        core.on("run_finish", () => {
          // Clear the pending message ID
          pendingMessageIdRef.current = null;
          setStatus("Ready");
          setIsRunning(false);
        });

        core.on("error", (err: Error) => {
          const msg = err.message || "Unknown error";
          setStatus(`Error: ${msg.slice(0, 40)}`);
          setIsRunning(false);
        });

        core.on("closed", () => {
          setStatus("Core closed");
        });
      } catch (err) {
        const msg = (err as Error).message || "Unknown error";
        setStatus(`Core error: ${msg.slice(0, 30)}`);
      }
    };

    initCore();

    // Cleanup
    return () => {
      if (coreRef.current) {
        coreRef.current.stop();
      }
    };
  }, []);

  const handleUserMessage = (content: string) => {
    if (isRunning || !coreRef.current) return;

    // Add user message to history
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    };
    setMessages((prev) => [...prev, userMsg]);

    // Create placeholder for assistant message
    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMsg: Message = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
    };
    setMessages((prev) => [...prev, assistantMsg]);

    // Track which message we're filling in
    pendingMessageIdRef.current = assistantMsgId;

    // Send to core
    try {
      coreRef.current.sendUserMessage(content);
    } catch (err) {
      setStatus(`Failed to send message: ${(err as Error).message}`);
      setIsRunning(false);
    }
  };

  return (
    <Box flexDirection="column">
      <Box flexDirection="column" marginBottom={1}>
        <MessageHistory messages={messages} />
      </Box>
      <InputBox onSubmit={handleUserMessage} disabled={isRunning} />
      <StatusLine sessionId={sessionId} status={status} />
    </Box>
  );
};

export default ChatApp;
