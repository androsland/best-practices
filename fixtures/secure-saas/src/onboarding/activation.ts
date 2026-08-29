export interface Analytics {
  track(
    name: "project_created",
    value: { workspaceId: string; activation_event: true },
  ): void;
}

export function recordFirstValue(workspaceId: string, analytics: Analytics) {
  analytics.track("project_created", { workspaceId, activation_event: true });
}
