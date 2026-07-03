import React from "react";
import { Text, Box } from "ink";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface MessageHistoryProps {
  messages: Message[];
}

const MessageHistory = ({ messages }: MessageHistoryProps) => {
  if (messages.length === 0) {
    return (
      <Text dimColor>
        [No messages yet. Start typing to begin.]
      </Text>
    );
  }

  return (
    <Box flexDirection="column">
      {messages.map((msg) => (
        <Box key={msg.id} marginBottom={1}>
          <Box marginRight={2} width={10}>
            <Text bold>{msg.role === "user" ? "You" : "Assistant"}:</Text>
          </Box>
          <Text>{msg.content}</Text>
        </Box>
      ))}
    </Box>
  );
};

export default MessageHistory;
