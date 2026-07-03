import React, { useState } from "react";
import { Text, Box } from "ink";

interface InputBoxProps {
  onSubmit: (content: string) => void;
}

const InputBox = ({ onSubmit }: InputBoxProps) => {
  const [input, setInput] = useState("");

  // TODO: Implement actual input handling with readline
  // For now, this is a placeholder showing the UI structure

  return (
    <Box borderTop borderStyle="round" paddingY={1}>
      <Box marginRight={1}>
        <Text>&gt;</Text>
      </Box>
      <Text>{input || "[input placeholder]"}</Text>
    </Box>
  );
};

export default InputBox;
