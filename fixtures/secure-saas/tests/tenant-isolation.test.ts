import { describe, expect, it } from "vitest";
import { authorizeWorkspace } from "../src/auth/authorize";

describe("tenant isolation", () => {
  it("denies a user from another workspace", () => {
    expect(authorizeWorkspace("other-user", "workspace-a")).toBe(false);
  });
});
