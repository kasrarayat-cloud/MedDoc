import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  isTemplateTwinSyntheticQaPatient,
  ordinaryClinicalVisitWhere,
  TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID,
} from "@/lib/template-twin/synthetic-qa-patient";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";

const APP_ROOT = resolve(__dirname, "..", "..");

function source(relativePath: string): string {
  return readFileSync(resolve(APP_ROOT, relativePath), "utf8");
}

function sourceBetween(
  contents: string,
  startMarker: string,
  endMarker: string,
): string {
  const start = contents.indexOf(startMarker);
  const end = contents.indexOf(endMarker, start + startMarker.length);
  if (start < 0 || end < 0) {
    throw new Error(
      `Could not find static-contract boundaries ${startMarker}..${endMarker}`,
    );
  }
  return contents.slice(start, end);
}

function countOccurrences(contents: string, token: string): number {
  return contents.split(token).length - 1;
}

function namedImport(contents: string, moduleName: string): string {
  const doubleQuoted = `from "${moduleName}";`;
  const singleQuoted = `from '${moduleName}';`;
  const doubleEnd = contents.indexOf(doubleQuoted);
  const singleEnd = contents.indexOf(singleQuoted);
  const end = doubleEnd >= 0 ? doubleEnd : singleEnd;
  const marker = doubleEnd >= 0 ? doubleQuoted : singleQuoted;
  const start = contents.lastIndexOf("import ", end);
  if (start < 0 || end < 0) {
    throw new Error(`Could not find import from ${moduleName}`);
  }
  return contents.slice(start, end + marker.length);
}

function expectNamedObjectCall(contents: string, functionName: string): void {
  const invocation = new RegExp(
    `\\b${functionName}(?:\\s*<[\\s\\S]*?>)?\\s*\\(\\s*\\{`,
  );
  expect(contents).toMatch(invocation);
}

const ORDINARY_VISIT_READ_SURFACES = [
  {
    path: "src/actions/command-palette.ts",
    authorities: ["readTemplateTwinVisibleVisitPage"],
  },
  {
    path: "src/actions/visits.ts",
    authorities: [
      "aggregateTemplateTwinVisibleVisits",
      "readTemplateTwinVisibleVisitPage",
    ],
  },
  {
    path: "src/actions/patients.ts",
    authorities: [
      "countTemplateTwinVisibleVisitsByPatient",
      "readLatestTemplateTwinVisibleVisitByPatient",
    ],
  },
  {
    path: "src/app/dashboard/page.tsx",
    authorities: [
      "aggregateTemplateTwinVisibleVisits",
      "countTemplateTwinVisibleVisitsByPatient",
      "readLatestTemplateTwinVisibleVisitByPatient",
      "readTemplateTwinVisibleVisitPage",
    ],
  },
  {
    path: "src/components/dashboard/dashboard-c3.tsx",
    authorities: [
      "aggregateTemplateTwinVisibleVisits",
      "readTemplateTwinVisibleVisitPage",
    ],
  },
  {
    path: "src/app/visits/page.tsx",
    authorities: [
      "aggregateTemplateTwinVisibleVisits",
      "readTemplateTwinVisibleVisitPage",
    ],
  },
  {
    path: "src/app/visits/new/page.tsx",
    authorities: ["readTemplateTwinVisibleVisitPage"],
  },
  {
    path: "src/app/patients/page.tsx",
    authorities: [
      "countTemplateTwinVisibleVisitsByPatient",
      "readLatestTemplateTwinVisibleVisitByPatient",
    ],
  },
  {
    path: "src/app/patients/[id]/page.tsx",
    authorities: [
      "aggregateTemplateTwinVisibleVisits",
      "readTemplateTwinVisibleVisitPage",
      "templateTwinVisitReadVisibilitySql",
    ],
  },
  {
    path: "src/app/api/patients/[id]/route.ts",
    authorities: ["aggregateTemplateTwinVisibleVisits"],
  },
  {
    path: "src/app/api/patients/[id]/export/route.ts",
    authorities: ["listTemplateTwinVisibleVisitIdentities"],
  },
  {
    path: "src/app/api/settings/export-data/route.ts",
    authorities: ["listTemplateTwinVisibleVisitIdentities"],
  },
] as const;

const RAW_SQL_VISIBILITY_SURFACES = [
  {
    path: "src/lib/patients-query.ts",
    bindings: [
      { name: "visibleV", assignments: 1, interpolations: 3 },
      { name: "visibleV2", assignments: 1, interpolations: 3 },
    ],
  },
  {
    path: "src/app/api/patients/route.ts",
    bindings: [{ name: "visitVisibility", assignments: 1, interpolations: 2 }],
  },
  {
    path: "src/app/api/patients/search/route.ts",
    bindings: [{ name: "visitVisibility", assignments: 1, interpolations: 1 }],
  },
  {
    path: "src/app/patients/[id]/page.tsx",
    bindings: [{ name: "visibility", assignments: 2, interpolations: 2 }],
  },
] as const;

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

  it("keeps the generic durable exclusion fail-closed across every Twin marker", () => {
    expect(TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE).toEqual({
      AND: [
        {
          OR: [
            { noteTemplateId: null },
            {
              noteTemplate: {
                is: {
                  templateKind: { not: "template_twin_docx" },
                  templateTwinCompiledVersion: { is: null },
                },
              },
            },
          ],
        },
        { templateTwinFill: { is: null } },
        { templateTwinSyntheticQaRun: { is: null } },
        { templateTwinSyntheticQaAdmission: { is: null } },
        { templateTwinProviderExecutions: { none: {} } },
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

  it.each([
    "src/app/api/patients/route.ts",
    "src/app/api/patients/search/route.ts",
    "src/app/api/patients/fuzzy-match/route.ts",
    "src/lib/patients-query.ts",
  ])("excludes the reserved row from SQL roster surface %s", (path) => {
    const contents = source(path);
    expect(contents).toContain("currentClinicalPatientReadAuthoritySql");
    const authority = source("src/lib/clinical-patient-authority.ts");
    expect(authority).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID",
    );
    expect(authority).toMatch(/externalId[^\n]+IS DISTINCT FROM/);
  });

  it.each([
    "src/actions/patients.ts",
    "src/app/patients/page.tsx",
    "src/app/dashboard/page.tsx",
  ])("excludes the reserved row from Prisma roster surface %s", (path) => {
    const contents = source(path);
    expect(contents).toContain("currentClinicalPatientCollectionWhere");
    const authority = source("src/lib/clinical-patient-authority.ts");
    expect(authority).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID",
    );
    expect(authority).toMatch(/externalId:\s*null/);
    expect(authority).toMatch(/externalId:\s*\{[\s\S]*?not:/);
  });

  it.each(ORDINARY_VISIT_READ_SURFACES)(
    "invokes its exact approved fail-closed visit authority in $path",
    ({ path, authorities }) => {
      const contents = source(path);
      const authorityImport = namedImport(
        contents,
        "@/lib/template-twin/read-authority",
      );
      for (const authority of authorities) {
        expect(authorityImport).toMatch(new RegExp(`\\b${authority}\\b`));
        expectNamedObjectCall(contents, authority);
      }
    },
  );

  it("keeps the query-native authority's durable and reserved-patient exclusions in one SQL predicate", () => {
    const contents = source("src/lib/template-twin/read-authority.ts");
    const helper = sourceBetween(
      contents,
      "export function templateTwinVisitReadVisibilitySql",
      "export interface TemplateTwinVisibleVisitIdentity",
    );

    expect(helper).toContain(
      'FROM "template_twin_fill_manifests" provenance_fill',
    );
    expect(helper).toContain(
      'FROM "template_twin_synthetic_qa_runs" provenance_run',
    );
    expect(helper).toContain(
      'FROM "template_twin_synthetic_qa_admissions" provenance_admission',
    );
    expect(helper).toContain(
      'FROM "template_twin_provider_executions" provenance_execution',
    );
    expect(helper).toContain(
      "ordinary_patient.\"externalId\" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'",
    );
    expect(helper).toContain(
      "current_patient.\"externalId\" IS DISTINCT FROM 'SYNTHETIC-QA-ONLY'",
    );
  });

  it.each(RAW_SQL_VISIBILITY_SURFACES)(
    "interpolates the query-native visibility predicate into every visit-bearing SQL query in $path",
    ({ path, bindings }) => {
      const contents = source(path);
      expect(
        namedImport(contents, "@/lib/template-twin/read-authority"),
      ).toMatch(/\btemplateTwinVisitReadVisibilitySql\b/);

      for (const binding of bindings) {
        const assignments = contents.match(
          new RegExp(
            `const\\s+${binding.name}\\s*=\\s*templateTwinVisitReadVisibilitySql\\s*\\(\\s*\\{`,
            "g",
          ),
        );
        expect(assignments).toHaveLength(binding.assignments);
        expect(countOccurrences(contents, `\${${binding.name}}`)).toBe(
          binding.interpolations,
        );
      }
    },
  );

  it("keeps the settings export's ordinary edit rows behind the durable same-statement exclusion", () => {
    const contents = source("src/app/api/settings/export-data/route.ts");
    expect(contents).toMatch(
      /import \{ TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE \} from ["']@\/lib\/template-twin\/durable-visit-exclusion["'];/,
    );
    expect(contents).toMatch(
      /visit:\s*\{\s*is:\s*TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE\s*\}/,
    );
  });

  it("excludes the reserved patient in the export lookup and repeats that lookup before streaming PHI", () => {
    const contents = source("src/app/api/patients/[id]/export/route.ts");
    const patientLookup = sourceBetween(
      contents,
      "async function loadCurrentPatientExportRecord",
      "export const GET",
    );

    expect(
      countOccurrences(patientLookup, "transcribeMdPatient.findFirst"),
    ).toBe(1);
    expect(patientLookup).toContain("currentClinicalPatientWhere({");
    expect(patientLookup).toContain("actor,");
    expect(patientLookup).toContain("patientId,");
    expect(patientLookup).toContain("includeDeleted: true");
    expect(patientLookup).toContain("select: PATIENT_EXPORT_SELECT");

    const initialLookup = contents.indexOf(
      "const patient = await loadCurrentPatientExportRecord",
    );
    const visitCensus = contents.indexOf(
      "const visits = await listTemplateTwinVisibleVisitIdentities",
    );
    const currentLookup = contents.indexOf(
      "const currentPatient = await loadCurrentPatientExportRecord",
      visitCensus,
    );
    const firstPhiAppend = contents.indexOf("archive.append(", currentLookup);

    expect(initialLookup).toBeGreaterThan(-1);
    expect(initialLookup).toBeLessThan(visitCensus);
    expect(currentLookup).toBeGreaterThan(visitCensus);
    expect(firstPhiAppend).toBeGreaterThan(currentLookup);
    expect(contents.slice(currentLookup, firstPhiAppend)).toContain(
      "currentIdentity.practiceId",
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
    "src/app/patients/[id]/page.tsx",
    "src/app/visits/new/page.tsx",
    "src/actions/visits.ts",
    "src/app/api/visits/[id]/route.ts",
  ])("treats the reserved patient as unavailable in %s", (path) => {
    expect(source(path)).toMatch(
      /isTemplateTwinSyntheticQaPatient|currentClinicalPatientWhere|lockCurrentClinicalPatient/,
    );
  });

  it("keeps the reserved identity centralized in staging creation", () => {
    const contents = source("src/lib/template-twin/staging-qa-service.ts");
    expect(contents).toContain(
      "TEMPLATE_TWIN_SYNTHETIC_QA_PATIENT_EXTERNAL_ID",
    );
    expect(contents).not.toMatch(/externalId:\s*["']SYNTHETIC-QA-ONLY["']/);
  });
});
