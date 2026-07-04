import React from "react";
import { Text, Box } from "ink";
import TextInput from "ink-text-input";

interface InputBoxProps {
  onSubmit: (content: string) => void;
  disabled?: boolean;
}

const InputBox = ({ onSubmit, disabled = false }: InputBoxProps) => {
  const [input, setInput] = React.useState("");

  const handleSubmit = (value: string) => {
    if (value.trim()) {
      onSubmit(value);
      setInput("");
    }
  };

  return (
    <Box borderTop borderStyle="round" paddingY={0}>
      <Box marginRight={1}>
        <Text>{disabled ? "..." : ">"}</Text>
      </Box>
      {disabled ? (
        <Text>[waiting for response...]</Text>
      ) : (
        <TextInput value={input} onChange={setInput} onSubmit={handleSubmit} />
      )}
    </Box>
  );
};

export default InputBox;
