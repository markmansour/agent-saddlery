import { describe, it, expect } from "vitest";
import { CoreSubprocess, describeCoreExit } from "../core/subprocess";
import { notConnectedMessage } from "../components/notConnected";

describe("describeCoreExit", () => {
  it("reports only the code when there are no stderr lines", () => {
    expect(describeCoreExit(2, [])).toBe("Core exited with code 2");
  });
  it("appends a single line", () => {
    expect(describeCoreExit(2, ["bad config"])).toBe("Core exited with code 2: bad config");
  });
  it("joins several lines with ' | '", () => {
    expect(describeCoreExit(1, ["a", "b", "c"])).toBe("Core exited with code 1: a | b | c");
  });
  it("caps the reason at 300 characters with an ellipsis", () => {
    const msg = describeCoreExit(2, ["x".repeat(500)]);
    const reason = msg.slice("Core exited with code 2: ".length);
    expect(reason.length).toBe(301);
    expect(reason.endsWith("…")).toBe(true);
  });
  it("does not add an ellipsis when the reason fits", () => {
    expect(describeCoreExit(2, ["x".repeat(300)])).not.toContain("…");
  });
  it("handles a null exit code", () => {
    expect(describeCoreExit(null, ["boom"])).toBe("Core exited with code null: boom");
  });
});

describe("CoreSubprocess startup failure", () => {
  it("rejects start() with the exit code and the core's stderr reason", async () => {
    const core = new CoreSubprocess({
      command: `node -e "console.error('permissions config error: bad'); process.exit(2)"`,
    });
    const began = Date.now();
    let message = "";
    try {
      await core.start();
    } catch (e) {
      message = (e as Error).message;
    }
    expect(message).toContain("exited with code 2");
    expect(message).toContain("permissions config error: bad");
    expect(Date.now() - began).toBeLessThan(4000);
  });

  it("leaves JSON log lines out of the message", async () => {
    const core = new CoreSubprocess({
      command: `node -e "console.error('{\\"level\\":\\"info\\"}'); console.error(''); console.error('real reason'); process.exit(3)"`,
    });
    let message = "";
    try {
      await core.start();
    } catch (e) {
      message = (e as Error).message;
    }
    expect(message).toContain("real reason");
    expect(message).not.toContain("level");
  });
});

describe("notConnectedMessage", () => {
  it("includes the reason", () => {
    expect(notConnectedMessage("Core exited with code 2: bad")).toBe(
      "Not connected: Core exited with code 2: bad",
    );
  });
  it("falls back when no reason is known", () => {
    expect(notConnectedMessage()).toBe("Not connected: core did not start");
    expect(notConnectedMessage("")).toBe("Not connected: core did not start");
  });
});
