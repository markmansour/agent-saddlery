/** Reply shown when the user types while no core is connected. */
export function notConnectedMessage(reason?: string): string {
  return `Not connected: ${reason || "core did not start"}`;
}
