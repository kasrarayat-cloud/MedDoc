import { beforeEach, describe, expect, it, vi } from "vitest";

const db = vi.hoisted(() => ({
  $queryRaw: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({ default: db }));

import { fetchPatientsPage } from "../patients-query";

describe("patient rollup Template Twin read authority", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    db.$queryRaw.mockResolvedValue([]);
  });

  it("computes counts, latest specialty, order, and cursor from a query-native exact boundary", async () => {
    await fetchPatientsPage("practice-session", "doctor-current", null);

    expect(db.$queryRaw).toHaveBeenCalledTimes(1);
    const statement = db.$queryRaw.mock.calls[0]?.[0];
    const sql = statement?.strings?.join(" ") ?? "";
    expect(statement?.values).toContain("practice-session");
    expect(statement?.values).toContain("doctor-current");
    expect(sql).toContain("current_actor.\"role\" = 'DOCTOR'");
    expect(sql).toContain('current_actor."deactivatedAt" IS NULL');
    expect(sql).toContain('current_actor."suspendedAt" IS NULL');
    expect(sql).toContain('current_actor."softDeletedAt" IS NULL');
    expect(sql).toContain("'TRANSCRIBE_MD'");
    expect(sql).toContain('current_patient."practiceId"');
    expect(sql).toContain('current_template."doctorId"');
    expect(sql).toContain(
      'current_template."version" = v."noteTemplateVersion"',
    );
    expect(sql).toContain(
      'current_template."version" = v2."noteTemplateVersion"',
    );
    expect(sql).toContain("execution.\"providerMode\" IS DISTINCT FROM 'LIVE'");
    expect(sql).toContain('execution."syntheticAdmissionId" IS NOT NULL');
    expect(sql).toContain('execution_compiled."noteTemplateId"');
    expect(sql).toContain('execution_source."practiceId"');
    expect(sql).toContain('provenance_execution."visitId"');
  });

  it("keeps deleted and archived rows out of the non-null cursor aggregate", async () => {
    await fetchPatientsPage("practice-session", "doctor-current", {
      lastVisitAt: "2026-07-19T12:00:00.000Z",
      id: "patient-2",
    });

    const statement = db.$queryRaw.mock.calls[0]?.[0];
    const sql = statement?.strings?.join(" ") ?? "";
    expect(sql).toContain('v."deletedAt" IS NULL');
    expect(sql).toContain('v."archivedAt" IS NULL');
  });
});
