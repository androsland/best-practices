export function recordFirstValue(workspaceId: string) {
  analytics.track("project_created", { workspaceId, activation_event: true });
}

declare const analytics: { track(name: string, value: object): void };
