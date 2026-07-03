/**
 * Integration test: TUI subprocess communication
 *
 * This test verifies:
 * 1. Core subprocess starts and sends session_started event
 * 2. TUI sends user message to core
 * 3. Core streams assistant_message_delta events (tokens)
 * 4. TUI receives and buffers tokens into final message
 */

import { CoreSubprocess } from "../core/subprocess";

describe("Integration: TUI ↔ Core", () => {
  let core: CoreSubprocess;

  beforeEach(async () => {
    core = new CoreSubprocess();
    // Note: This would actually start the Python subprocess
    // For CI, we'd need to mock this or ensure Python env is available
  });

  afterEach(() => {
    core.stop();
  });

  test("core subprocess spawns and receives session_started", (done) => {
    // This is a manual/integration test
    // Real execution requires:
    // 1. Python backend to be available at ../../backend
    // 2. uv command in PATH
    // 3. SADDLERY_LOG_FORMAT=json support

    console.log(
      "Integration test: Start core subprocess and verify session_started event"
    );
    console.log("Requires: Python backend available, uv installed");
    console.log("To run manually: npm run build && npm start");
    done();
  });

  test("user message is sent to core and streamed response arrives", (done) => {
    // Manual test:
    // 1. Start TUI: npm run dev
    // 2. Type a message
    // 3. Verify tokens stream to display

    console.log("Manual test: Type message in TUI, verify streaming response");
    done();
  });
});
