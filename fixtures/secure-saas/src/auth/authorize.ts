export function authorizeWorkspace(userId: string, workspaceId: string) {
  return policy.canAccess({ userId, workspaceId });
}

declare const policy: { canAccess(input: object): boolean };
