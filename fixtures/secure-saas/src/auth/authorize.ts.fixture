export interface WorkspacePolicy {
  canAccess(input: { userId: string; workspaceId: string }): boolean;
}

export function authorizeWorkspace(
  userId: string,
  workspaceId: string,
  policy: WorkspacePolicy,
) {
  return policy.canAccess({ userId, workspaceId });
}
