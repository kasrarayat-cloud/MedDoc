import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  stagingRequested: vi.fn(),
  notFound: vi.fn(),
  requireAdmin: vi.fn(),
  recordAccess: vi.fn(),
  workspace: vi.fn(),
}));

vi.mock("next/navigation", () => ({ notFound: mocks.notFound }));
vi.mock("@/lib/template-twin/static-asset-access-audit", () => ({
  recordTemplateTwinStaticAssetInventoryAccess: mocks.recordAccess,
}));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: mocks.stagingRequested,
}));
vi.mock("@/lib/template-twin/static-asset-admin", () => ({
  requireTemplateTwinStaticAssetAdmin: mocks.requireAdmin,
}));
vi.mock("../static-asset-review-workspace", () => ({
  StaticAssetReviewWorkspace: mocks.workspace,
}));

import TemplateTwinStaticAssetSettingsPage from "../page";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.stagingRequested.mockReturnValue(true);
  mocks.requireAdmin.mockResolvedValue({
    userId: "admin_synthetic",
    userEmail: "admin@synthetic.test",
    practiceId: "practice_synthetic",
    role: "ADMIN",
    rolloutToken: {
      practiceId: "practice_synthetic",
      globalGeneration: BigInt(1),
      practiceGeneration: BigInt(1),
    },
  });
  mocks.recordAccess.mockResolvedValue(undefined);
  mocks.workspace.mockReturnValue(<div>Synthetic static-asset workspace</div>);
  mocks.notFound.mockImplementation(() => {
    throw new Error("NEXT_NOT_FOUND");
  });
});

describe("Template Twin reusable-image settings page", () => {
  it("fails closed before authentication or audit work in synthetic-only mode", async () => {
    await expect(TemplateTwinStaticAssetSettingsPage()).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );

    expect(mocks.requireAdmin).not.toHaveBeenCalled();
    expect(mocks.recordAccess).not.toHaveBeenCalled();
  });

  it("awaits the required access audit before rendering the inventory workspace", async () => {
    mocks.stagingRequested.mockReturnValue(false);

    render(await TemplateTwinStaticAssetSettingsPage());

    expect(mocks.recordAccess).toHaveBeenCalledWith({
      actor: expect.objectContaining({
        userId: "admin_synthetic",
        practiceId: "practice_synthetic",
      }),
      surface: "page",
    });
    expect(
      screen.getByText("Synthetic static-asset workspace"),
    ).toBeInTheDocument();
  });

  it("returns no workspace when required access-audit persistence fails", async () => {
    mocks.stagingRequested.mockReturnValue(false);
    mocks.recordAccess.mockRejectedValue(
      new Error("synthetic audit persistence failure"),
    );
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    await expect(TemplateTwinStaticAssetSettingsPage()).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );

    expect(mocks.recordAccess).toHaveBeenCalledTimes(1);
    expect(mocks.workspace).not.toHaveBeenCalled();
    expect(
      screen.queryByText("Synthetic static-asset workspace"),
    ).not.toBeInTheDocument();
  });
});
