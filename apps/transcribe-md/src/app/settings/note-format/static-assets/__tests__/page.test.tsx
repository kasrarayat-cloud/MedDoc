import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  stagingRequested: vi.fn(),
  notFound: vi.fn(),
  requireAdmin: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock("next/navigation", () => ({ notFound: mocks.notFound }));
vi.mock("next/link", () => ({ default: () => null }));
vi.mock("@/components/ui/app-frame", () => ({ AppFrame: () => null }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/template-twin/staging-qa-gate", () => ({
  isTemplateTwinStagingQaRequested: mocks.stagingRequested,
}));
vi.mock("@/lib/template-twin/static-asset-admin", () => ({
  requireTemplateTwinStaticAssetAdmin: mocks.requireAdmin,
}));
vi.mock("../static-asset-review-workspace", () => ({
  StaticAssetReviewWorkspace: () => null,
}));

import TemplateTwinStaticAssetSettingsPage from "../page";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.stagingRequested.mockReturnValue(true);
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
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});
