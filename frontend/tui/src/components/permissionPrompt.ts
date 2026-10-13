export interface PermissionRequestInfo {
  toolCallId: string;
  toolName: string;
  arguments: Record<string, unknown>;
  capability: string;
  resource: string[];
  tainted: boolean;
}

/** The prompt shows the backend's `resource`, never one rebuilt from raw arguments. */
export function formatPermissionPrompt(info: PermissionRequestInfo): string {
  const separator = info.capability === "exec" ? " " : "/";
  const target = info.resource.join(separator);
  const subject = target ? `${info.toolName}: ${target}` : info.toolName;
  const taint = info.tainted ? " (follows untrusted content)" : "";
  return `Allow ${subject}?${taint} [y/n]`;
}
