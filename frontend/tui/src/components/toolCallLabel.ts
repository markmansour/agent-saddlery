function cut(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…(+${text.length - max} more chars)` : text;
}

/** One-line tool-call label; values whose text exceeds maxValueChars are truncated. */
export function formatToolCall(
  name: string,
  args: Record<string, unknown>,
  maxValueChars = 80,
): string {
  const json = JSON.stringify(args, function (this: unknown, key: string, value: unknown) {
    if (key === "") return value;
    if (typeof value === "string") return cut(value, maxValueChars);
    if (value !== null && typeof value === "object") {
      const text = JSON.stringify(value);
      return text !== undefined && text.length > maxValueChars ? cut(text, maxValueChars) : value;
    }
    return value;
  });
  return `→ ${name}(${json})`;
}
