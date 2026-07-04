import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import { createInterface } from "readline";
import { appendFileSync } from "fs";

export interface CoreEvent {
  event?: string;
  event_type?: string;
  event_data?: Record<string, unknown>;
  level?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export class CoreSubprocess extends EventEmitter {
  private process: ChildProcess | null = null;
  private sessionId: string = "";

  async start(): Promise<void> {
    // Find backend directory: either as sibling (if in frontend/tui) or current dir (if already there)
    let backendPath = process.cwd();
    if (backendPath.includes("/frontend/tui")) {
      backendPath = backendPath.replace(/\/frontend\/tui.*/, "/backend");
    }

    // Spawn Python core with --json-input flag and JSON logging
    // Use sh to cd into backend first (ensures uv finds pyproject.toml)
    const env = {
      ...process.env,
      SADDLERY_LOG_FORMAT: "json",
      PYTHONUNBUFFERED: "1",
    };

    appendFileSync("tui.log", `[subprocess] spawning core at ${backendPath}\n`);
    appendFileSync(
      "tui.log",
      `[subprocess] command: cd '${backendPath}' && uv run python -m saddlery.cli.main --json-input\n`
    );

    this.process = spawn(
      "sh",
      ["-c", `cd '${backendPath}' && uv run python -m saddlery.cli.main --json-input`],
      {
        env,
        stdio: ["pipe", "pipe", "pipe"],
      }
    );

    appendFileSync("tui.log", `[subprocess] spawn returned, checking streams\n`);

    if (!this.process.stdout || !this.process.stdin) {
      appendFileSync("tui.log", `[subprocess] ERROR: no stdout or stdin\n`);
      throw new Error("Failed to spawn core process");
    }

    appendFileSync("tui.log", `[subprocess] streams OK, setting up readline\n`);

    // Read events from core stdout
    const readline = createInterface({
      input: this.process.stdout,
      crlfDelay: Infinity,
    });

    readline.on("line", (eventLine: string) => {
      try {
        const event = JSON.parse(eventLine) as CoreEvent;
        this.handleEvent(event);
      } catch (e) {
        // Log non-JSON lines for debugging
        appendFileSync("tui.log", `[unparseable] ${eventLine.substring(0, 60)}\n`);
      }
    });

    readline.on("close", () => {
      appendFileSync("tui.log", `[readline] closed\n`);
    });

    // Note: stdout.on("data") fires before readline processes lines, so we'll see raw bytes first

    // Capture stderr logs from subprocess
    if (this.process.stderr) {
      const stderrReadline = createInterface({
        input: this.process.stderr,
        crlfDelay: Infinity,
      });

      stderrReadline.on("line", (line: string) => {
        appendFileSync("core.log", `${line}\n`);
        // Don't log stderr to tui.log — it's too verbose. Core logs go to core.log
      });
    }

    // Handle process errors
    this.process.on("error", (err) => {
      appendFileSync("tui.log", `[error] spawn error: ${err.message}\n`);
      this.emit("error", new Error(`Core process error: ${err.message}`));
    });

    this.process.on("exit", (code) => {
      appendFileSync("tui.log", `[exit] process exited with code ${code}\n`);
      if (code !== 0 && code !== null) {
        this.emit("error", new Error(`Core process exited with code ${code}`));
      }
      this.emit("closed", code);
    });

    appendFileSync("tui.log", `[subprocess] process PID: ${this.process.pid}\n`);

    // Extract session ID from first event
    await new Promise<void>((resolve, reject) => {
      let timeoutId: NodeJS.Timeout | null = null;

      const cleanup = () => {
        if (timeoutId) clearTimeout(timeoutId);
        this.removeListener("event", onEvent);
        this.removeListener("error", onError);
      };

      const onEvent = (event: CoreEvent) => {
        const sessionId =
          (event.session_id as string | undefined) ||
          (event.event_data?.session_id as string | undefined);
        if ((event.event_type === "session_started" || event.event === "session_started") && sessionId) {
          this.sessionId = sessionId;
          appendFileSync("tui.log", `[✓] Session started: ${sessionId.substring(0, 8)}\n`);
          cleanup();
          resolve();
        }
      };

      const onError = (err: Error) => {
        cleanup();
        reject(err);
      };

      this.on("event", onEvent);
      this.on("error", onError);

      // Timeout if session doesn't start
      timeoutId = setTimeout(() => {
        cleanup();
        reject(new Error("Core process did not start within 5 seconds"));
      }, 5000);
    });
  }

  private handleEvent(event: CoreEvent): void {
    // Emit raw event
    this.emit("event", event);

    // All AG-UI events have event_type at the top level
    const eventType = event.event_type as string | undefined;
    if (!eventType) {
      // Not an AG-UI event (e.g., a log message), ignore
      return;
    }

    if (eventType === "session_started") {
      // Already handled in start()
      return;
    } else if (eventType === "run_started") {
      appendFileSync("tui.log", `[→] run started\n`);
      this.emit("run_start");
    } else if (eventType === "assistant_message_delta") {
      const eventData = event.event_data as Record<string, unknown>;
      const text = eventData?.text as string | undefined;
      if (text) {
        this.emit("assistant_delta", text);
      }
    } else if (eventType === "assistant_message") {
      appendFileSync("tui.log", `[✓] message complete\n`);
    } else if (eventType === "run_finished") {
      appendFileSync("tui.log", `[✓] run finished\n`);
      this.emit("run_finish");
    } else if (eventType === "error") {
      const eventData = event.event_data as Record<string, unknown>;
      const message = eventData?.message as string | undefined;
      appendFileSync("tui.log", `[✗] error: ${message}\n`);
      if (message) {
        this.emit("error", new Error(message));
      }
    }
  }

  sendUserMessage(content: string): void {
    if (!this.process?.stdin) {
      throw new Error("Core process not running");
    }

    const msg = {
      type: "user_message",
      content,
    };

    const msgStr = JSON.stringify(msg);
    appendFileSync("tui.log", `[send] ${msgStr}\n`);
    this.process.stdin.write(msgStr + "\n");
  }

  getSessionId(): string {
    return this.sessionId;
  }

  stop(): void {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
  }
}
