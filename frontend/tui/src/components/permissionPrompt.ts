export interface PermissionRequestInfo {
  toolCallId: string;
  toolName: string;
  arguments: Record<string, unknown>;
  capability: string;
  resource: string[];
  tainted: boolean;
}

/** Control (Cc) and format (Cf: bidi overrides, zero-width) characters can rewrite what the
 * terminal shows, so the prompt renders each one as a visible `\u{…}` escape. */
const INVISIBLE = /[\p{Cc}\p{Cf}]/gu;

function visible(text: string): string {
  return text.replace(INVISIBLE, (ch) => `\\u{${ch.codePointAt(0)!.toString(16)}}`);
}

/** The prompt shows the backend's `resource`, never one rebuilt from raw arguments. */
export function formatPermissionPrompt(info: PermissionRequestInfo): string {
  const exec = info.capability === "exec";
  const tokens = info.resource.map((token) => {
    const shown = visible(token);
    // An argv token with whitespace is one argument; quote it so it cannot pose as several.
    return exec && /\s/u.test(token) ? `"${shown}"` : shown;
  });
  const target = tokens.join(exec ? " " : "/");
  const toolName = visible(info.toolName);
  const subject = target ? `${toolName}: ${target}` : toolName;
  const taint = info.tainted ? " (follows untrusted content)" : "";
  return `Allow ${subject}?${taint} [y/n]`;
}
