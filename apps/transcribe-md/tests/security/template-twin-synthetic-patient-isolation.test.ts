import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  isTemplateTwinSyntheticQaPatient,
  ordinaryClinicalVisitWhere,
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
} from "@/lib/template-twin/synthetic-qa-patient";

const APP_ROOT = resolve(__dirname, "..", "..");

function source(relativePath: string): string {
  return readFileSync(resolve(APP_ROOT, relativePath), "utf8");
}

describe("Template Twin synthetic QA patient isolation", () => {
  it("recognizes only the exact reserved external ID", () => {
    expect(
      isTemplateTwinSyntheticQaPatient({
        externalId: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
      }),
    ).toBe(true);
    expect(isTemplateTwinSyntheticQaPatient({ externalId: null })).toBe(false);
    expect(
      isTemplateTwinSyntheticQaPatient({ externalId: "synthetic-qa-only" }),
    ).toBe(false);
  });

  it("builds a fail-closed ordinary visit predicate from both staging markers", () => {
    expect(
      ordinaryClinicalVisitWhere({
        userId: "doctor-synthetic-test",
        deletedAt: null,
      }),
    ).toEqual({
      AND: [
        { userId: "doctor-synthetic-test", deletedAt: null },
        { templateTwinSyntheticQaRun: { is: null } },
        {
          patient: {
            is: {
              OR: [
                { externalId: null },
                {
                  externalId: {
                    not: TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
                  },
                },
              ],
            },
          },
        },
      ],
    });
  });

  it("keeps the nullable external-id branch explicit", () => {
    const where = ordinaryClinicalVisitWhere({ id: "ordinary-visit" });

    expect(where).toMatchObject({
      AND: expect.arrayContaining([
        {
          patient: {
            is: {
              OR: expect.arrayContaining([{ externalId: null }]),
            },
          },
        },
      ]),
    });
  });

  it.each([
    "src/app/api/patients/route.ts",
    "src/app/api/patients/search/route.ts",
    "src/app/api/patients/fuzzy-match/route.ts",
    "src/lib/patients-query.ts",
  ])("excludes the reserved row from SQL roster surface %s", (path) => {
    const contents = source(path);
    expect(contents).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID",
    );
    expect(contents).toMatch(/externalId[^\n]+IS DISTINCT FROM/);
  });

  it.each([
    "src/actions/patients.ts",
    "src/app/patients/page.tsx",
    "src/app/dashboard/page.tsx",
  ])("excludes the reserved row from Prisma roster surface %s", (path) => {
    const contents = source(path);
    expect(contents).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID",
    );
    expect(contents).toMatch(/externalId:\s*null/);
    expect(contents).toMatch(/externalId:\s*\{[\s\S]*?not:/);
  });

  it.each([
    "src/actions/command-palette.ts",
    "src/actions/visits.ts",
    "src/actions/patients.ts",
    "src/app/dashboard/page.tsx",
    "src/components/dashboard/dashboard-c3.tsx",
    "src/app/visits/page.tsx",
    "src/app/visits/new/page.tsx",
    "src/app/patients/page.tsx",
    "src/app/patients/[id]/page.tsx",
    "src/app/api/patients/[id]/route.ts",
    "src/app/api/patients/[id]/export/route.ts",
    "src/app/api/settings/export-data/route.ts",
  ])("applies both visit-isolation markers to ordinary surface %s", (path) => {
    expect(source(path)).toContain("ordinaryClinicalVisitWhere");
  });

  it.each([
    "src/lib/patients-query.ts",
    "src/app/api/patients/route.ts",
    "src/app/api/patients/search/route.ts",
  ])("excludes staging-run visits from ordinary raw-SQL surface %s", (path) => {
    const contents = source(path);
    expect(contents).toContain("template_twin_synthetic_qa_runs");
    expect(contents).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID",
    );
  });

  it("keeps direct staging reads on their exact guarded admission path", () => {
    const contents = source(
      "src/app/api/note-templates/template-twin/staging-qa/runs/[id]/route.ts",
    );
    expect(contents).not.toContain("ordinaryClinicalVisitWhere");
    expect(contents).toContain("readTemplateTwinStagingQaRun");
  });

  it.each([
    "src/app/api/patients/[id]/route.ts",
    "src/app/api/patients/[id]/export/route.ts",
    "src/app/patients/[id]/page.tsx",
    "src/app/visits/new/page.tsx",
    "src/actions/visits.ts",
    "src/app/api/visits/[id]/route.ts",
  ])("treats the reserved patient as unavailable in %s", (path) => {
    expect(source(path)).toContain("isTemplateTwinSyntheticQaPatient");
  });

  it("keeps the reserved identity centralized in staging creation", () => {
    const contents = source("src/lib/template-twin/staging-qa-service.ts");
    expect(contents).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID",
    );
    expect(contents).not.toMatch(/externalId:\s*["']SYNTHETIC-QA-ONLY["']/);
  });
});
