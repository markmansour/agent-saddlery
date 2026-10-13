import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { CoreSubprocess, buildCoreEnv } from "../core/subprocess";

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

  it("should have a sendPermissionDecision method", () => {
    expect(typeof core.sendPermissionDecision).toBe("function");
  });

  it("emits permission_request when a permission_request event arrives", () => {
    const handler = vi.fn();
    core.on("permission_request", handler);

    (core as unknown as { handleEvent: (e: unknown) => void }).handleEvent({
      event_type: "permission_request",
      event_data: {
        tool_call_id: "call-1",
        tool_name: "write_file",
        arguments: { path: "out.txt" },
        capability: "write",
        resource: ["out.txt"],
        tainted: true,
      },
    });

    expect(handler).toHaveBeenCalledWith({
      toolCallId: "call-1",
      toolName: "write_file",
      arguments: { path: "out.txt" },
      capability: "write",
      resource: ["out.txt"],
      tainted: true,
    });
  });

  it("sendPermissionDecision writes a permission_decision JSON line to stdin", () => {
    const writeSpy = vi.fn();
    (core as unknown as { process: { stdin: { write: typeof writeSpy }; kill: () => void } }).process = {
      stdin: { write: writeSpy },
      kill: vi.fn(),
    };

    core.sendPermissionDecision("call-1", "allow");

    expect(writeSpy).toHaveBeenCalledWith(
      JSON.stringify({
        type: "permission_decision",
        tool_call_id: "call-1",
        decision: "allow",
      }) + "\n"
    );
  });

  it("sendPermissionDecision throws if core process is not running", () => {
    expect(() => core.sendPermissionDecision("call-1", "deny")).toThrow(
      "Core process not running"
    );
  });

  // Integration test: requires Python backend
  // it("should start core subprocess and emit session_started", async () => {
  //   await core.start();
  //   expect(core.getSessionId()).not.toBe("");
  // });
});

describe("buildCoreEnv", () => {
  it("roots the core's file tools at the launch directory", () => {
    const env = buildCoreEnv({ PATH: "/bin" }, "/work/project");
    expect(env.SADDLERY_ROOT).toBe("/work/project");
    expect(env.PYTHONUNBUFFERED).toBe("1");
    expect(env.PATH).toBe("/bin");
  });

  it("lets an explicit SADDLERY_ROOT win over the launch directory", () => {
    const env = buildCoreEnv({ SADDLERY_ROOT: "/elsewhere" }, "/work/project");
    expect(env.SADDLERY_ROOT).toBe("/elsewhere");
  });
});
