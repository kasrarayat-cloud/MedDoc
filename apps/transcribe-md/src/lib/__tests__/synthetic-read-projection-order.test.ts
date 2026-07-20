import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function source(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

function occurrences(value: string, needle: string): number {
  return value.split(needle).length - 1;
}

function projectedVisitWhereClauses(
  code: string,
  marker = "prisma.transcribeVisit.findFirst",
): string[] {
  const clauses: string[] = [];
  let cursor = 0;
  while (cursor < code.length) {
    const call = code.indexOf(marker, cursor);
    if (call < 0) break;
    const where = code.indexOf("where:", call);
    const select = code.indexOf("select:", where);
    if (where < 0 || select < 0) {
      throw new Error(`Could not isolate ${marker} where clause`);
    }
    clauses.push(code.slice(where, select));
    cursor = select + "select:".length;
  }
  return clauses;
}

describe("synthetic generic-read projection ordering", () => {
  const page = source("src/app/visits/[id]/page.tsx");
  const visitRoute = source("src/app/api/visits/[id]/route.ts");
  const getRoute = visitRoute.slice(
    visitRoute.indexOf("export const GET"),
    visitRoute.indexOf("export const PATCH"),
  );
  const status = source("src/app/api/visits/[id]/status/route.ts");
  const record = source("src/app/visits/[id]/record/page.tsx");
  const audio = source("src/app/api/visits/[id]/dictation/audio/route.ts");
  const admission = source("src/lib/template-twin/synthetic-read-admission.ts");
  const delivery = source("src/lib/template-twin/delivery-authorization.ts");
  const visitExport = source("src/lib/visit-export-server.ts");
  const emScore = source("src/app/api/visits/[id]/em-score/route.ts");
  const sign = source("src/app/api/visits/[id]/sign/route.ts");
  const clinicalActor = source("src/lib/clinical-visit-authority.ts");

  it.each([
    ["visit page", page, "const [user, visit, rxOverrides]"],
    ["visit GET", getRoute, "const visit = await prisma.transcribeVisit"],
    ["status GET", status, "const visit = await prisma.transcribeVisit"],
  ])("admits an exact run before %s PHI projection", (_label, code, phi) => {
    const preAdmission = code.indexOf(
      "await requireTemplateTwinSyntheticReadAdmission",
    );
    expect(preAdmission).toBeGreaterThanOrEqual(0);
    expect(preAdmission).toBeLessThan(code.indexOf(phi));
    expect(
      occurrences(code, "requireTemplateTwinSyntheticReadAdmission"),
    ).toBeGreaterThanOrEqual(3);
  });

  it("makes admission-only, pre-cert, and reserved-patient orphans fail before PHI", () => {
    const runCheck = admission.indexOf("!run ||");
    const freshDoctor = admission.indexOf(
      "requireFreshDoctorIdentity(",
      runCheck,
    );
    expect(runCheck).toBeGreaterThanOrEqual(0);
    expect(runCheck).toBeLessThan(freshDoctor);
    expect(admission).toContain(
      "throw new TemplateTwinSyntheticReadAdmissionError()",
    );
    expect(admission).not.toMatch(/soapFinal|transcriptText|audioKey/);
  });

  it("denies synthetic audio before resolving an object key", () => {
    const syntheticDeny = audio.indexOf(
      "if (preReadAuthority.isSyntheticTemplateTwin)",
    );
    const objectProjection = audio.indexOf(
      "const visit = await prisma.transcribeVisit.findFirst",
    );
    expect(syntheticDeny).toBeGreaterThanOrEqual(0);
    expect(syntheticDeny).toBeLessThan(objectProjection);
    expect(audio.indexOf("isOwnedTemplateTwinStagingQaVisit")).toBeLessThan(
      objectProjection,
    );
  });

  it.each([
    ["visit page", page, "prisma.transcribeVisit.findFirst"],
    ["visit GET", getRoute, "prisma.transcribeVisit.findFirst"],
    ["status GET", status, "prisma.transcribeVisit.findFirst"],
    ["record page", record, "prisma.transcribeVisit.findFirst"],
    ["audio object key", audio, "prisma.transcribeVisit.findFirst"],
    ["delivery signing PHI", delivery, "prisma.transcribeVisit.findFirst"],
  ] as const)(
    "binds the durable ordinary exclusion into the %s projection query",
    (_label, code, marker) => {
      const start = code.indexOf(marker);
      expect(start).toBeGreaterThanOrEqual(0);
      expect(code.slice(start, start + 700)).toContain(
        "TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE",
      );
    },
  );

  it("binds ordinary exclusion into export clinical and object-key projections", () => {
    expect(occurrences(visitExport, "prisma.transcribeVisit.findFirst")).toBe(
      2,
    );
    expect(
      occurrences(visitExport, "TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE"),
    ).toBeGreaterThanOrEqual(3);
  });

  it.each([
    ["visit page", page, 1],
    ["record page", record, 1],
    ["visit GET", getRoute, 1],
    ["status GET", status, 1],
    ["audio object key", audio, 1],
    ["delivery signing PHI", delivery, 1],
    ["export clinical and object keys", visitExport, 2],
    [
      "provider-backed E/M clinical inputs",
      emScore,
      1,
      "prisma.transcribeVisit.findUnique",
    ],
  ] as const)(
    "binds current actor lifecycle and tenant in the same %s PHI-bearing projection",
    (_label, code, expectedCalls, marker?: string) => {
      const clauses = projectedVisitWhereClauses(code, marker);
      expect(clauses).toHaveLength(expectedCalls);
      for (const clause of clauses) {
        expect(clause).toContain("currentClinicalVisitActorWhere");
      }
    },
  );

  it("binds current actor authority into the signing PHI read and owner into status refreshes", () => {
    const clauses = projectedVisitWhereClauses(
      sign,
      "prisma.transcribeVisit.findUnique",
    );
    expect(clauses).toHaveLength(3);
    expect(clauses[0]).toContain("currentClinicalVisitActorWhere");
    expect(clauses[1]).toContain("userId");
    expect(clauses[2]).toContain("userId");
  });

  it("binds the warning-id projection through the same current visit authority", () => {
    const overrideRead = page.slice(
      page.indexOf("prisma.rxWarningOverride.findMany"),
      page.indexOf("select: { warningId: true }"),
    );
    expect(overrideRead).toContain("currentClinicalVisitActorWhere");
  });

  it("requires exact lifecycle, entitlement, active practice, and patient tenant", () => {
    for (const predicate of [
      'role: "DOCTOR"',
      "isActive: true",
      "deactivatedAt: null",
      "suspendedAt: null",
      "softDeletedAt: null",
      'has: "TRANSCRIBE_MD"',
      "practice:",
      "users: { some: currentActor }",
    ]) {
      expect(clinicalActor).toContain(predicate);
    }
  });
});
