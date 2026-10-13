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

  describe("escapes control and format characters", () => {
    const cases: Array<[string, string, string]> = [
      ["ESC", "\u001b", "\\u{1b}"],
      ["NUL", "\u0000", "\\u{0}"],
      ["backspace", "\u0008", "\\u{8}"],
      ["right-to-left override", "\u202e", "\\u{202e}"],
      ["zero-width space", "\u200b", "\\u{200b}"],
    ];

    it.each(cases)("renders %s in a resource token as a visible escape", (_, raw, shown) => {
      const out = formatPermissionPrompt({ ...base, resource: ["docs", `a${raw}.md`] });
      expect(out).toBe(`Allow write_file: docs/a${shown}.md? [y/n]`);
      expect(out.includes(raw)).toBe(false);
    });

    it.each(cases)("renders %s in the tool name as a visible escape", (_, raw, shown) => {
      const out = formatPermissionPrompt({ ...base, toolName: `write${raw}_file` });
      expect(out).toBe(`Allow write${shown}_file: docs/a.md? [y/n]`);
      expect(out.includes(raw)).toBe(false);
    });

    it("hides a spoofed CSI sequence", () => {
      const out = formatPermissionPrompt({
        ...base,
        toolName: "shell",
        capability: "exec",
        resource: ["rm", "-rf", "/\u001b[2K\u001b[1Gls"],
      });
      expect(out).toBe("Allow shell: rm -rf /\\u{1b}[2K\\u{1b}[1Gls? [y/n]");
      expect(out.includes("\u001b")).toBe(false);
    });
  });

  it("quotes exec tokens that contain whitespace", () => {
    expect(
      formatPermissionPrompt({
        ...base,
        toolName: "shell",
        capability: "exec",
        resource: ["git", "commit", "-m", "fix it"],
      })
    ).toBe('Allow shell: git commit -m "fix it"? [y/n]');
  });

  it("does not quote path tokens that contain whitespace", () => {
    expect(formatPermissionPrompt({ ...base, resource: ["my docs", "a.md"] })).toBe(
      "Allow write_file: my docs/a.md? [y/n]"
    );
  });
});
