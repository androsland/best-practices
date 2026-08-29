import { describe, expect, it, vi } from "vitest";
import { recordFirstValue } from "../src/onboarding/activation";

describe("onboarding activation", () => {
  it("records one first-value event for the correct workspace", () => {
    const track = vi.fn();

    recordFirstValue("workspace-a", { track });

    expect(track).toHaveBeenCalledOnce();
    expect(track).toHaveBeenCalledWith("project_created", {
      workspaceId: "workspace-a",
      activation_event: true,
    });
  });
});
