import { describe, it, expect } from "vitest";
import { formatPermissionPrompt } from "../components/permissionPrompt";

const base = {
  toolCallId: "c1",
  toolName: "write_file",
  arguments: {},
  capability: "write",
  resource: ["docs", "a.md"],
  tainted: false,
};

describe("formatPermissionPrompt", () => {
  it("joins path resources with slashes", () => {
    expect(formatPermissionPrompt(base)).toBe("Allow write_file: docs/a.md? [y/n]");
  });

  it("joins exec resources with spaces", () => {
    expect(
      formatPermissionPrompt({
        ...base,
        toolName: "shell",
        capability: "exec",
        resource: ["git", "push", "origin", "main"],
      })
    ).toBe("Allow shell: git push origin main? [y/n]");
  });

  it("flags requests that follow untrusted content", () => {
    expect(formatPermissionPrompt({ ...base, tainted: true })).toBe(
      "Allow write_file: docs/a.md? (follows untrusted content) [y/n]"
    );
  });

  it("falls back to the tool name when the resource is empty", () => {
    expect(formatPermissionPrompt({ ...base, resource: [] })).toBe("Allow write_file? [y/n]");
  });
});
