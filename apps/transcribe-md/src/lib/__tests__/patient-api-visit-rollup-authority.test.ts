import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function source(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf8");
}

function occurrences(value: string, needle: string): number {
  return value.split(needle).length - 1;
}

describe("patient API visit-derived metadata authority", () => {
  const list = source("src/app/api/patients/route.ts");
  const search = source("src/app/api/patients/search/route.ts");
  const dashboardQuery = source("src/lib/patients-query.ts");
  const patientDetail = source("src/app/patients/[id]/page.tsx");

  it("applies the exact current-actor visibility SQL to both patient-list JOIN variants", () => {
    expect(list).toContain("templateTwinVisitReadVisibilitySql");
    expect(list).toContain("actorUserId: session.user.id");
    expect(list).toContain('visitAlias: "v"');
    expect(occurrences(list, "AND ${visitVisibility}")).toBe(2);
    expect(list).not.toContain("template_twin_synthetic_qa_runs qa");
  });

  it("applies the same exact visibility SQL to the PHI-minimal POST search rollup", () => {
    expect(search).toContain("templateTwinVisitReadVisibilitySql");
    expect(search).toContain("actorUserId: session.user.id");
    expect(search).toContain('visitAlias: "v"');
    expect(occurrences(search, "AND ${visitVisibility}")).toBe(1);
    expect(search).not.toContain("template_twin_synthetic_qa_runs qa");
  });

  it("finds no remaining raw patient list/detail visit aggregate without exact visibility", () => {
    expect(occurrences(dashboardQuery, "FROM transcribe_visits v2")).toBe(3);
    expect(occurrences(dashboardQuery, "LEFT JOIN transcribe_visits v")).toBe(
      3,
    );
    expect(occurrences(dashboardQuery, "AND ${visibleV2}")).toBe(3);
    expect(occurrences(dashboardQuery, "AND ${visibleV}")).toBe(3);
    expect(occurrences(patientDetail, 'FROM "transcribe_visits" visit')).toBe(
      2,
    );
    expect(occurrences(patientDetail, "AND ${visibility}")).toBe(2);
  });
});
