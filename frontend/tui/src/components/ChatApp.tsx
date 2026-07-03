import React, { useState } from "react";
import { Text, Box } from "ink";
import MessageHistory from "./MessageHistory";
import InputBox from "./InputBox";
import StatusLine from "./StatusLine";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const ChatApp = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState("Initializing...");
  const [sessionId, setSessionId] = useState<string>("");

  const handleUserMessage = (content: string) => {
    // Add user message to history
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    };
    setMessages((prev) => [...prev, userMsg]);

    // TODO: Send to core and wait for response
    setStatus("Processing...");
  };

  return (
    <Box flexDirection="column" width={80} height={24}>
      <Box flexDirection="column" flex={1} borderStyle="round">
        <MessageHistory messages={messages} />
      </Box>
      <InputBox onSubmit={handleUserMessage} />
      <StatusLine sessionId={sessionId} status={status} />
    </Box>
  );
};

export default ChatApp;
