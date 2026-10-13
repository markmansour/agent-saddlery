import { describe, it, expect } from "vitest";
import { formatToolCall } from "../components/toolCallLabel.js";

describe("formatToolCall", () => {
  it("renders short args unchanged", () => {
    expect(formatToolCall("read_file", { path: "README.md" })).toBe(
      '→ read_file({"path":"README.md"})',
    );
  });

  it("truncates long content with an exact suffix", () => {
    const content = "a".repeat(1000);
    const out = formatToolCall("write_file", { content });
    expect(out).toBe(`→ write_file({"content":"${"a".repeat(80)}…(+920 more chars)"})`);
  });

  it("keeps path intact next to truncated content", () => {
    const out = formatToolCall("write_file", { path: "tmp.md", content: "x".repeat(500) });
    expect(out).toContain('"path":"tmp.md"');
    expect(out).toContain("…(+420 more chars)");
  });

  it("does not truncate at exactly maxValueChars but does at +1", () => {
    expect(formatToolCall("t", { v: "a".repeat(80) })).not.toContain("more chars");
    expect(formatToolCall("t", { v: "a".repeat(81) })).toContain("…(+1 more chars)");
  });

  it("honours a custom maxValueChars", () => {
    expect(formatToolCall("t", { v: "abcdef" }, 3)).toBe('→ t({"v":"abc…(+3 more chars)"})');
  });

  it("keeps newlines escaped", () => {
    const out = formatToolCall("t", { v: "line\n".repeat(100) });
    expect(out).not.toContain("\n");
    expect(out).toContain("\\n");
  });

  it("handles empty args", () => {
    expect(formatToolCall("name", {})).toBe("→ name({})");
  });

  it("truncates long non-string values by their JSON text", () => {
    const arr = Array.from({ length: 100 }, (_, i) => i);
    const json = JSON.stringify(arr);
    const out = formatToolCall("t", { arr });
    expect(out).toBe(`→ t(${JSON.stringify({ arr: `${json.slice(0, 80)}…(+${json.length - 80} more chars)` })})`);
  });
});
