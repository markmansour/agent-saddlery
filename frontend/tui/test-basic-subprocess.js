import { spawn } from "child_process";
import { createInterface } from "readline";

console.log("Testing basic core subprocess (no --json-input)...\n");

const proc = spawn("uv", ["run", "python", "-m", "saddlery.cli.main"], {
  cwd: process.cwd().replace(/\/frontend\/tui.*/, "/backend"),
  env: {
    ...process.env,
    SADDLERY_LOG_FORMAT: "json",
    PYTHONUNBUFFERED: "1",
  },
  stdio: ["pipe", "pipe", "pipe"],
});

const readline = createInterface({
  input: proc.stdout,
  crlfDelay: Infinity,
});

let lines = 0;

readline.on("line", (line) => {
  lines++;
  console.log(line);
  if (lines >= 3) {
    proc.kill();
    process.exit(0);
  }
});

setTimeout(() => {
  console.error("Timeout - no output");
  proc.kill();
  process.exit(1);
}, 5000);
