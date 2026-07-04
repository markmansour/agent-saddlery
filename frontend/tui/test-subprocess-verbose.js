import { spawn } from "child_process";

let backendPath = process.cwd();
if (backendPath.includes("/frontend/tui")) {
  backendPath = backendPath.replace(/\/frontend\/tui.*/, "/backend");
}

console.log("Backend path:", backendPath);
console.log("Running: sh -c 'cd <backend> && uv run python -m saddlery.cli.main --json-input'\n");

const proc = spawn("sh", ["-c", `cd '${backendPath}' && uv run python -m saddlery.cli.main --json-input`], {
  env: {
    ...process.env,
    SADDLERY_LOG_FORMAT: "json",
    PYTHONUNBUFFERED: "1",
  },
  stdio: ["pipe", "pipe", "pipe"],
});

console.log("Process spawned, PID:", proc.pid);

let stdoutData = "";
let stderrData = "";

proc.stdout?.on("data", (data) => {
  const text = data.toString();
  stdoutData += text;
  console.log("[stdout data]:", text);
});

proc.stderr?.on("data", (data) => {
  const text = data.toString();
  stderrData += text;
  console.log("[stderr data]:", text);
});

proc.on("error", (err) => {
  console.error("[spawn error]:", err);
  process.exit(1);
});

proc.on("exit", (code, signal) => {
  console.log(`[process exit] code=${code}, signal=${signal}`);
  console.log("Total stdout:", stdoutData.length, "bytes");
  console.log("Total stderr:", stderrData.length, "bytes");
  process.exit(code || 0);
});

// Send a message after 1 second
setTimeout(() => {
  console.log("\n[sending message]");
  const msg = JSON.stringify({ type: "user_message", content: "hello" }) + "\n";
  console.log("Message bytes:", msg.length);
  proc.stdin?.write(msg);
}, 1000);

// Kill after 5 seconds
setTimeout(() => {
  console.log("\n[timeout, killing process]");
  proc.kill();
}, 5000);
