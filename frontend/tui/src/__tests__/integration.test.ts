/**
 * Integration test: TUI subprocess communication
 *
 * This test verifies:
 * 1. Core subprocess starts and sends session_started event
 * 2. TUI sends user message to core
 * 3. Core streams assistant_message_delta events (tokens)
 * 4. TUI receives and buffers tokens into final message
 *
 * Note: These are unit tests only. Full integration test requires:
 * 1. Python backend available at ../../backend
 * 2. uv command in PATH
 * 3. SADDLERY_LOG_FORMAT=json support
 * See README.md for manual integration test instructions.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { CoreSubprocess } from "../core/subprocess";

describe("CoreSubprocess integration", () => {
  let core: CoreSubprocess;

  beforeEach(() => {
    core = new CoreSubprocess();
  });

  afterEach(() => {
    if (core) {
      core.stop();
    }
  });

  it("should instantiate and have core methods", () => {
    expect(core).toBeDefined();
    expect(typeof core.sendUserMessage).toBe("function");
    expect(typeof core.getSessionId).toBe("function");
    expect(typeof core.stop).toBe("function");
  });

  it("should start with empty session ID", () => {
    expect(core.getSessionId()).toBe("");
  });

  // Manual integration tests (requires Python backend)
  // Uncomment and run with: npm run test
  // Prerequisites: python backend at ../../backend, uv installed
  //
  // it("should start core subprocess and extract session ID", async () => {
  //   await core.start();
  //   const sessionId = core.getSessionId();
  //   expect(sessionId).not.toBe("");
  //   expect(sessionId.length).toBeGreaterThan(0);
  // });
  //
  // it("should send user message and receive streaming response", async () => {
  //   await core.start();
  //   const messages: string[] = [];
  //   core.on("assistant_delta", (text: string) => {
  //     messages.push(text);
  //   });
  //   core.sendUserMessage("hello");
  //   await new Promise((resolve) => {
  //     core.on("run_finish", resolve);
  //   });
  //   expect(messages.length).toBeGreaterThan(0);
  // });
});
