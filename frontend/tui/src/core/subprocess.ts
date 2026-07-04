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

    this.process = spawn(
      "sh",
      ["-c", `cd '${backendPath}' && uv run python -m saddlery.cli.main --json-input`],
      {
        env,
        stdio: ["pipe", "pipe", "pipe"],
      }
    );

    if (!this.process.stdout || !this.process.stdin) {
      throw new Error("Failed to spawn core process");
    }

    // Read events from core stdout
    const readline = createInterface({
      input: this.process.stdout,
      crlfDelay: Infinity,
    });

    readline.on("line", (eventLine: string) => {
      try {
        const event = JSON.parse(eventLine) as CoreEvent;
        this.handleEvent(event);
      } catch {
        // Ignore parse errors (e.g., stderr output)
      }
    });

    // Capture stderr logs from subprocess
    if (this.process.stderr) {
      const stderrReadline = createInterface({
        input: this.process.stderr,
        crlfDelay: Infinity,
      });

      stderrReadline.on("line", (line: string) => {
        appendFileSync("core.log", `${line}\n`);
      });
    }

    // Handle process errors
    this.process.on("error", (err) => {
      this.emit("error", new Error(`Core process error: ${err.message}`));
    });

    this.process.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        this.emit("error", new Error(`Core process exited with code ${code}`));
      }
      this.emit("closed", code);
    });

    // Extract session ID from first event
    await new Promise<void>((resolve, reject) => {
      let timeoutId: NodeJS.Timeout | null = null;

      const cleanup = () => {
        if (timeoutId) clearTimeout(timeoutId);
        this.removeListener("event", onEvent);
        this.removeListener("error", onError);
      };

      const onEvent = (event: CoreEvent) => {
        if (event.event === "session_started" && event.session_id) {
          this.sessionId = event.session_id as string;
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

    // Handle session_started (structured log event)
    if (event.event === "session_started") {
      // Don't extract here; let caller listen for "event"
      return;
    }

    // Parse AG-UI event_emitted events
    if (event.event === "event_emitted" && event.event_type) {
      const eventType = event.event_type as string;

      if (eventType === "run_started") {
        this.emit("run_start");
      } else if (eventType === "assistant_message_delta") {
        const eventData = event.event_data as Record<string, unknown>;
        const text = eventData?.text as string | undefined;
        if (text) {
          this.emit("assistant_delta", text);
        }
      } else if (eventType === "run_finished") {
        this.emit("run_finish");
      } else if (eventType === "error") {
        const eventData = event.event_data as Record<string, unknown>;
        const message = eventData?.message as string | undefined;
        if (message) {
          this.emit("error", new Error(message));
        }
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

    this.process.stdin.write(JSON.stringify(msg) + "\n");
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
