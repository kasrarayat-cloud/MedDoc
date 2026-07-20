import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ findUser: vi.fn() }));

vi.mock("@meddoc/db", () => ({
  default: { user: { findUnique: mocks.findUser } },
}));

import { loadCurrentVisitExportActor } from "../visit-export-authority";

const currentActor = {
  id: "doctor-1",
  practiceId: "practice-1",
  role: "DOCTOR",
  isActive: true,
  deactivatedAt: null,
  suspendedAt: null,
  softDeletedAt: null,
  products: ["TRANSCRIBE_MD"],
  practice: { isActive: true },
};

beforeEach(() => {
  vi.clearAllMocks();
  mocks.findUser.mockResolvedValue(currentActor);
});

describe("current visit-export actor", () => {
  it("returns only the current physician and practice identifiers", async () => {
    await expect(loadCurrentVisitExportActor("doctor-1")).resolves.toEqual({
      id: "doctor-1",
      practiceId: "practice-1",
    });
    expect(mocks.findUser).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: "doctor-1" } }),
    );
  });

  it.each([
    ["missing", null],
    ["wrong role", { ...currentActor, role: "ADMIN" }],
    ["inactive", { ...currentActor, isActive: false }],
    ["deactivated", { ...currentActor, deactivatedAt: new Date() }],
    ["suspended", { ...currentActor, suspendedAt: new Date() }],
    ["soft deleted", { ...currentActor, softDeletedAt: new Date() }],
    ["product removed", { ...currentActor, products: [] }],
    ["practice inactive", { ...currentActor, practice: { isActive: false } }],
  ])("fails closed for a %s actor", async (_label, actor) => {
    mocks.findUser.mockResolvedValue(actor);
    await expect(loadCurrentVisitExportActor("doctor-1")).resolves.toBeNull();
  });
});
