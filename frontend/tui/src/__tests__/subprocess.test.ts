import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { CoreSubprocess } from "../core/subprocess";

describe("CoreSubprocess", () => {
  let core: CoreSubprocess;

  beforeEach(() => {
    core = new CoreSubprocess();
  });

  afterEach(() => {
    if (core) {
      core.stop();
    }
  });

  it("should instantiate without errors", () => {
    expect(core).toBeDefined();
    expect(core.getSessionId()).toBe("");
  });

  it("should have a stop method", () => {
    expect(typeof core.stop).toBe("function");
  });

  it("should have a sendUserMessage method", () => {
    expect(typeof core.sendUserMessage).toBe("function");
  });

  it("should have a getSessionId method", () => {
    expect(typeof core.getSessionId).toBe("function");
  });

  // Integration test: requires Python backend
  // it("should start core subprocess and emit session_started", async () => {
  //   await core.start();
  //   expect(core.getSessionId()).not.toBe("");
  // });
});
