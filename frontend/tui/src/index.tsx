import React from "react";
import { render } from "ink";
import ChatApp from "./components/ChatApp.js";

const App = () => {
  return <ChatApp />;
};

// Pass stdin/stdout explicitly for TTY support
render(<App />, {
  stdin: process.stdin,
  stdout: process.stdout,
});
