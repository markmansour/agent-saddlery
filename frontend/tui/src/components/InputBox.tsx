import React, { useState, useEffect } from "react";
import { Text, Box } from "ink";
import keypress from "keypress";

interface InputBoxProps {
  onSubmit: (content: string) => void;
  disabled?: boolean;
}

const InputBox = ({ onSubmit, disabled = false }: InputBoxProps) => {
  const [input, setInput] = useState("");

  useEffect(() => {
    if (disabled) return;

    const stdin = process.stdin as NodeJS.ReadStream;

    // Make stdin emit keypress events
    keypress(stdin);

    const handleKeypress = (ch: string, key: Record<string, unknown>) => {
      if (key.name === "return") {
        // Submit on Enter
        if (input.trim()) {
          onSubmit(input);
          setInput("");
        }
      } else if (key.name === "backspace") {
        // Delete character
        setInput((prev) => prev.slice(0, -1));
      } else if (key.name === "escape") {
        // Clear on Escape
        setInput("");
      } else if (key.ctrl && key.name === "c") {
        // Exit on Ctrl-C
        process.exit(0);
      } else if (ch && ch.length === 1 && ch.charCodeAt(0) >= 32) {
        // Add printable character
        setInput((prev) => prev + ch);
      }
    };

    stdin.on("keypress", handleKeypress);

    return () => {
      stdin.removeListener("keypress", handleKeypress);
    };
  }, [input, disabled, onSubmit]);

  const displayInput = input || (disabled ? "[waiting...]" : "");

  return (
    <Box borderTop borderStyle="round" paddingY={1}>
      <Box marginRight={1}>
        <Text>{disabled ? "..." : ">"}</Text>
      </Box>
      <Text>{displayInput}</Text>
    </Box>
  );
};

export default InputBox;
