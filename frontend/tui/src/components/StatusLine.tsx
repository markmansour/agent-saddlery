import React from "react";
import { Text, Box } from "ink";

interface StatusLineProps {
  sessionId?: string;
  status: string;
}

const StatusLine = ({ sessionId, status }: StatusLineProps) => {
  return (
    <Box borderTop borderStyle="round" paddingY={0}>
      <Text dimColor>
        {sessionId ? `[${sessionId.slice(0, 8)}]` : "[offline]"} {status}
      </Text>
    </Box>
  );
};

export default StatusLine;
