import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  db: vi.fn(),
  ocr: vi.fn(),
  runtime: vi.fn(),
  service: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $queryRaw: mocks.db,
  },
}));
vi.mock("@/lib/template-twin/static-asset-ocr", () => ({
  configuredTemplateTwinLocalOcr: mocks.ocr,
}));
vi.mock("@/lib/template-twin/runtime-attestation", () => ({
  refreshTemplateTwinRuntimeAttestation: mocks.runtime,
}));
vi.mock("@/lib/template-twin/admin-app-service", () => ({
  isTemplateTwinAdminAppService: mocks.service,
}));

import { GET } from "./route";

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubEnv("ANTHROPIC_API_KEY", "synthetic-configured-key");
  mocks.service.mockReturnValue(true);
  mocks.db.mockResolvedValue([{ one: 1 }]);
  mocks.ocr.mockResolvedValue({
    ready: true,
    code: "TT_STATIC_ASSET_LOCAL_OCR_READY",
    message: "Synthetic OCR ready.",
    engineVersion: "tesseract/5.5.1",
  });
  mocks.runtime.mockResolvedValue("NOT_CONFIGURED");
});

describe("isolated Template Twin admin app health", () => {
  it("is unavailable from every other same-image process", async () => {
    mocks.service.mockReturnValue(false);
    const response = await GET();
    expect(response.status).toBe(404);
    expect(mocks.db).not.toHaveBeenCalled();
  });

  it("reports only boolean/configuration state and never provider material", async () => {
    const response = await GET();
    const body = await response.json();
    expect(response.status).toBe(200);
    expect(body).toEqual({
      status: "healthy",
      service: "template-twin-admin-app",
      checks: {
        database: true,
        localOcr: true,
        providerConfigured: true,
        runtimeIdentity: "NOT_CONFIGURED",
      },
    });
    expect(JSON.stringify(body)).not.toContain("synthetic-configured-key");
  });

  it.each([
    ["database", () => mocks.db.mockRejectedValue(new Error("synthetic"))],
    ["OCR", () => mocks.ocr.mockResolvedValue({ ready: false })],
    ["runtime", () => mocks.runtime.mockRejectedValue(new Error("synthetic"))],
    ["provider", () => vi.stubEnv("ANTHROPIC_API_KEY", "")],
  ])(
    "fails health when %s readiness is unavailable",
    async (_label, breakIt) => {
      breakIt();
      const response = await GET();
      expect(response.status).toBe(503);
      expect(await response.json()).toMatchObject({ status: "unhealthy" });
    },
  );
});
