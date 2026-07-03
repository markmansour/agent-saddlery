import React, { useState, useEffect, useRef } from "react";
import { Text, Box } from "ink";
import MessageHistory from "./MessageHistory";
import InputBox from "./InputBox";
import StatusLine from "./StatusLine";
import { CoreSubprocess } from "../core/subprocess";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const ChatApp = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState("Initializing...");
  const [sessionId, setSessionId] = useState<string>("");
  const [isRunning, setIsRunning] = useState(false);
  const [assistantBuffer, setAssistantBuffer] = useState("");
  const coreRef = useRef<CoreSubprocess | null>(null);

  // Initialize core subprocess
  useEffect(() => {
    const initCore = async () => {
      try {
        const core = new CoreSubprocess();
        await core.start();
        coreRef.current = core;
        setSessionId(core.getSessionId());
        setStatus("Ready");

        // Handle events from core
        core.on("run_start", () => {
          setAssistantBuffer("");
          setStatus("Processing...");
        });

        core.on("assistant_delta", (text: string) => {
          setAssistantBuffer((prev) => prev + text);
          // Update last message in real-time
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { ...lastMsg, content: prev[prev.length - 1].content + text },
              ];
            }
            return prev;
          });
        });

        core.on("run_finish", () => {
          // Finalize assistant message
          if (assistantBuffer) {
            setMessages((prev) => {
              const lastMsg = prev[prev.length - 1];
              if (lastMsg && lastMsg.role === "assistant") {
                return [
                  ...prev.slice(0, -1),
                  { ...lastMsg, content: assistantBuffer },
                ];
              }
              return [
                ...prev,
                {
                  id: Date.now().toString(),
                  role: "assistant",
                  content: assistantBuffer,
                },
              ];
            });
          }
          setStatus("Ready");
          setIsRunning(false);
          setAssistantBuffer("");
        });

        core.on("error", (err: Error) => {
          setStatus(`Error: ${err.message}`);
          setIsRunning(false);
        });

        core.on("closed", () => {
          setStatus("Core process closed");
        });
      } catch (err) {
        setStatus(`Failed to start core: ${(err as Error).message}`);
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

    // Add placeholder for assistant message
    setMessages((prev) => [
      ...prev,
      {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "",
      },
    ]);

    // Send to core
    setIsRunning(true);
    try {
      coreRef.current.sendUserMessage(content);
    } catch (err) {
      setStatus(`Failed to send message: ${(err as Error).message}`);
      setIsRunning(false);
    }
  };

  return (
    <Box flexDirection="column" width={80} height={24}>
      <Box flexDirection="column" flex={1} borderStyle="round">
        <MessageHistory messages={messages} />
      </Box>
      <InputBox onSubmit={handleUserMessage} disabled={isRunning} />
      <StatusLine sessionId={sessionId} status={status} />
    </Box>
  );
};

export default ChatApp;
