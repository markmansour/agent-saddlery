import React from "react";
import { Text, Box } from "ink";

interface Message {
  id: string;
  role: "user" | "assistant" | "tool" | "error";
  content: string;
  toolName?: string;
  isError?: boolean;
}

interface MessageHistoryProps {
  messages: Message[];
}

const MessageHistory = ({ messages }: MessageHistoryProps) => {
  if (messages.length === 0) {
    return <Text dimColor>[No messages yet. Start typing to begin.]</Text>;
  }

  return (
    <Box flexDirection="column">
      {messages.map((msg) => (
        <Box key={msg.id} marginBottom={1}>
          <Box marginRight={2} width={10}>
            <Text
              bold
              color={
                msg.role === "error"
                  ? "red"
                  : msg.role === "tool"
                  ? msg.isError
                    ? "red"
                    : "yellow"
                  : undefined
              }
            >
              {msg.role === "user"
                ? "You"
                : msg.role === "tool"
                ? "Tool"
                : msg.role === "error"
                ? "Error"
                : "Assistant"}
              :
            </Text>
          </Box>
          <Text color={msg.role === "error" ? "red" : undefined}>{msg.content}</Text>
        </Box>
      ))}
    </Box>
  );
};

export default MessageHistory;
