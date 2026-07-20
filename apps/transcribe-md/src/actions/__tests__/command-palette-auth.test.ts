import { readFileSync } from "node:fs";
import path from "node:path";

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getSession: vi.fn(),
  readVisibleVisits: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({ default: { synthetic: "db" } }));
vi.mock("@/lib/auth", () => ({ getSession: mocks.getSession }));
vi.mock("@/lib/template-twin/read-authority", () => ({
  readTemplateTwinVisibleVisitPage: mocks.readVisibleVisits,
}));

import { getRecentVisits } from "../command-palette";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("command-palette physician authorization", () => {
  it("mounts clinician globals only in the exact physician process", () => {
    const layout = readFileSync(
      path.resolve(__dirname, "../../app/layout.tsx"),
      "utf8",
    );
    expect(layout).toContain("isTranscribeMdPhysicianAppService()");
    expect(layout).toMatch(
      /physicianSurface\s*\?\s*\([\s\S]*?<CommandPalette[\s\S]*?<GlobalShortcuts/u,
    );
  });

  it("returns no clinical projection when the shared physician session boundary denies", async () => {
    mocks.getSession.mockResolvedValue(null);

    await expect(getRecentVisits()).resolves.toEqual([]);
    expect(mocks.readVisibleVisits).not.toHaveBeenCalled();
  });

  it("returns the bounded projection for an admitted physician session", async () => {
    mocks.getSession.mockResolvedValue({
      user: {
        id: "doctor-synthetic",
        email: "doctor-synthetic@example.test",
        fullName: "Synthetic Doctor",
        role: "DOCTOR",
        practiceId: "practice-synthetic",
      },
    });
    mocks.readVisibleVisits.mockResolvedValue([
      {
        id: "visit-synthetic",
        patientName: "Synthetic Patient",
        specialty: "Family Medicine",
        createdAt: new Date("2026-07-20T09:00:00.000Z"),
      },
    ]);

    await expect(getRecentVisits()).resolves.toEqual([
      {
        id: "visit-synthetic",
        patientName: "Synthetic Patient",
        specialty: "Family Medicine",
        createdAt: "2026-07-20T09:00:00.000Z",
      },
    ]);
    expect(mocks.readVisibleVisits).toHaveBeenCalledWith(
      expect.objectContaining({ actorUserId: "doctor-synthetic" }),
    );
  });
});
