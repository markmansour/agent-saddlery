import { spawn } from "child_process";
import { createInterface } from "readline";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
console.log("TUI ↔ Core Subprocess Communication Test");
console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

if (!process.env.ANTHROPIC_API_KEY) {
  console.log(
    "ℹ️  ANTHROPIC_API_KEY not set\n" +
      "The core will use a mock provider for testing.\n" +
      "Set ANTHROPIC_API_KEY=sk-ant-... to use real Claude.\n"
  );
}

const pythonPath = "uv";
const args = ["run", "python", "-m", "saddlery.cli.main", "--json-input"];

const proc = spawn(pythonPath, args, {
  cwd: process.cwd().replace(/\/frontend\/tui.*/, "/backend"),
  env: {
    ...process.env,
    SADDLERY_LOG_FORMAT: "json",
    PYTHONUNBUFFERED: "1",
  },
  stdio: ["pipe", "pipe", "pipe"],
});

console.log(`\n✓ Spawned core process (PID ${proc.pid})`);
console.log(`  Backend: ${process.cwd().replace(/\/frontend\/tui.*/, "/backend")}`);
console.log(`  Args: ${args.join(" ")}`);

const readline = createInterface({
  input: proc.stdout,
  crlfDelay: Infinity,
});

let lineCount = 0;
let gotSessionStart = false;

readline.on("line", (line) => {
  lineCount++;
  try {
    const obj = JSON.parse(line);
    if (obj.event === "session_started") {
      gotSessionStart = true;
      console.log(`\n✓ Got session_started event`);
      console.log(`  Session ID: ${obj.session_id}`);
    } else if (obj.event_type === "run_started") {
      console.log(`✓ Got run_started`);
    } else if (obj.event_type === "assistant_message_delta") {
      process.stdout.write(obj.event_data?.text || "");
    } else if (obj.event_type === "run_finished") {
      console.log("\n✓ Got run_finished\n");
    } else {
      console.log(`[line ${lineCount}] ${obj.event || obj.event_type || "unknown"}`, obj);
    }
  } catch {
    console.log(`[line ${lineCount}] (non-JSON): ${line}`);
  }
});

proc.stderr?.on("data", (data) => {
  console.error(`\n[stderr] ${data.toString()}`);
});

proc.on("error", (err) => {
  console.error(`\n❌ Process error:`, err);
});

proc.on("exit", (code, signal) => {
  if (code !== 0) {
    console.error(`\n❌ Process exited with code ${code}`);
  }
  process.exit(code || 0);
});

// Send a test message after 1 second
setTimeout(() => {
  if (!gotSessionStart) {
    console.error("\n❌ Did not receive session_started — core may have crashed");
    proc.kill();
    process.exit(1);
  }
  console.log("Sending test message...\n");
  proc.stdin?.write(JSON.stringify({ type: "user_message", content: "What is 2+2?" }) + "\n");
}, 1000);

// Exit after 15 seconds
setTimeout(() => {
  console.log("\n[timeout] Test complete");
  proc.kill();
  process.exit(0);
}, 15000);
