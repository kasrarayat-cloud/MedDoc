import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function source(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

function occurrences(value: string, needle: string): number {
  return value.split(needle).length - 1;
}

describe("current clinical-patient read census", () => {
  it.each([
    "src/app/api/patients/route.ts",
    "src/app/api/patients/search/route.ts",
    "src/app/api/patients/fuzzy-match/route.ts",
  ])("binds %s raw roster PHI to the current exact actor", (path) => {
    const contents = source(path);
    expect(contents).toContain("currentClinicalPatientReadAuthoritySql");
    expect(contents).toContain("userId: session.user.id");
    expect(contents).toContain("practiceId: session.user.practiceId");
    expect(contents).toContain("WHERE ${patientAuthority}");
  });

  it("binds every paginated raw roster query to current authority", () => {
    const contents = source("src/lib/patients-query.ts");
    expect(contents).toContain("currentClinicalPatientReadAuthoritySql");
    expect(contents).toContain("actor: { userId: actorUserId, practiceId }");
    expect(occurrences(contents, "WHERE ${patientAuthority}")).toBe(3);
  });

  it("binds both patients-page branches, search action, and dashboard count/list queries", () => {
    const patientsPage = source("src/app/patients/page.tsx");
    const patientActions = source("src/actions/patients.ts");
    const dashboard = source("src/app/dashboard/page.tsx");

    expect(
      occurrences(
        patientsPage,
        "currentClinicalPatientCollectionWhere({ actor })",
      ),
    ).toBe(3);
    expect(patientActions).toContain(
      "...currentClinicalPatientCollectionWhere({ actor })",
    );
    expect(
      occurrences(dashboard, "currentClinicalPatientCollectionWhere({"),
    ).toBe(2);
  });

  it("binds detail, preload, and export projections in their PHI statement", () => {
    const detail = source("src/app/patients/[id]/page.tsx");
    const preload = source("src/app/visits/new/page.tsx");
    const patientExport = source("src/app/api/patients/[id]/export/route.ts");

    expect(detail).toContain("where: currentClinicalPatientWhere({");
    expect(occurrences(detail, "AND ${patientAuthority}")).toBe(2);
    expect(preload).toContain("where: currentClinicalPatientWhere({");
    expect(patientExport).toContain("where: currentClinicalPatientWhere({");
    expect(patientExport).toContain("includeDeleted: true");
  });

  it("keeps patient create and draft-visit reassignment inside locking transactions", () => {
    const patientsApi = source("src/app/api/patients/route.ts");
    const visitApi = source("src/app/api/visits/[id]/route.ts");

    expect(patientsApi).toContain("lockAndAssertCurrentClinicalPatientActor");
    expect(patientsApi).toMatch(
      /prisma\.\$transaction\([\s\S]*?lockAndAssertCurrentClinicalPatientActor[\s\S]*?tx\.transcribeMdPatient\.create/,
    );
    expect(visitApi).toContain("lockCurrentClinicalPatientAfterActor");
    expect(visitApi).not.toContain(
      "prisma.transcribeMdPatient.findUnique({\n        where: { id: parsed.data.patientId }",
    );
  });
});
