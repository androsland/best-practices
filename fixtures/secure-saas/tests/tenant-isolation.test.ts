import { describe, expect, it } from "vitest";
import { authorizeWorkspace } from "../src/auth/authorize";

describe("tenant isolation", () => {
  it("denies a user from another workspace", () => {
    const policy = {
      canAccess: ({ userId, workspaceId }: { userId: string; workspaceId: string }) =>
        userId === "workspace-a-owner" && workspaceId === "workspace-a",
    };

    expect(authorizeWorkspace("other-user", "workspace-a", policy)).toBe(false);
  });
});
