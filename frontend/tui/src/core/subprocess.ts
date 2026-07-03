import { spawn, ChildProcess } from "child_process";
import { EventEmitter } from "events";
import { createInterface } from "readline";

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
    // Spawn Python core with --json-input flag and JSON logging
    const pythonPath = "uv";
    const args = [
      "run",
      "python",
      "-m",
      "saddlery.cli.main",
      "--json-input",
    ];
    const env = {
      ...process.env,
      SADDLERY_LOG_FORMAT: "json",
    };

    this.process = spawn(pythonPath, args, {
      cwd: "../../backend", // Path to backend directory
      env,
      stdio: ["pipe", "pipe", "pipe"],
    });

    if (!this.process.stdout || !this.process.stdin || !this.process.stderr) {
      throw new Error("Failed to spawn core process");
    }

    // Read events from core stdout
    const readline = createInterface({
      input: this.process.stdout,
      crlfDelay: Infinity,
    });

    readline.on("line", (line) => {
      try {
        const event = JSON.parse(line) as CoreEvent;
        this.handleEvent(event);
      } catch (e) {
        // Ignore parse errors (e.g., stderr output)
      }
    });

    // Read stderr for debugging (not emitted, just logged)
    const stderrReadline = createInterface({
      input: this.process.stderr,
      crlfDelay: Infinity,
    });

    stderrReadline.on("line", (line) => {
      // Ignore stderr for now; could log to file or emit separate event
    });

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
      const onEvent = (event: CoreEvent) => {
        if (event.event === "session_started" && event.session_id) {
          this.sessionId = event.session_id as string;
          this.removeListener("event", onEvent);
          this.removeListener("error", onError);
          resolve();
        }
      };

      const onError = (err: Error) => {
        this.removeListener("event", onEvent);
        this.removeListener("error", onError);
        reject(err);
      };

      this.on("event", onEvent);
      this.on("error", onError);

      // Timeout if session doesn't start
      const timeoutId = setTimeout(() => {
        this.removeListener("event", onEvent);
        this.removeListener("error", onError);
        reject(new Error("Core process did not start within 5 seconds"));
      }, 5000);

      // Cancel timeout if we resolve/reject
      this.once("event", () => clearTimeout(timeoutId));
      this.once("error", () => clearTimeout(timeoutId));
    });
  }

  private handleEvent(event: CoreEvent): void {
    // Emit raw event
    this.emit("event", event);

    // Parse specific event types
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
