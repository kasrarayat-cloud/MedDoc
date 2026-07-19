// @vitest-environment node

import { beforeAll, describe, expect, it, vi } from "vitest";

// The unit contract is pure. Keep the durable workspace reader mocked so this
// focused suite never requires a generated Prisma client or a database.
vi.mock("../workspace-read", () => ({
  readTemplateTwinWorkspace: vi.fn(),
}));
vi.mock("@meddoc/db", () => ({ default: {}, prisma: {} }));

import type { TemplateTwinWorkspace } from "../client-types";
import { unresolvedFieldIntent } from "../field-intent";
import { DOCX_TEMPLATE_COMPILER } from "../artifact-compiler";
import { fallbackSemanticMappings } from "../semantic-mapping";
import {
  buildTemplateTwinStagingQaDocx,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from "../staging-qa-fixtures";
import {
  TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT,
  TEMPLATE_TWIN_STAGING_QA_REVIEWED_MAPPING_CONTRACT_VERSION,
} from "../staging-qa-reviewed-mapping-contract";
import {
  buildTemplateTwinStagingQaReviewedMappingDraft,
  loadTemplateTwinStagingQaReviewedMappingDraft,
  TemplateTwinStagingQaReviewedMappingsError,
} from "../staging-qa-reviewed-mappings";

let reviewedWorkspace: TemplateTwinWorkspace;

beforeAll(async () => {
  const ir = DOCX_TEMPLATE_COMPILER.compile(
    await buildTemplateTwinStagingQaDocx(),
  );
  const mappings = fallbackSemanticMappings(ir);
  reviewedWorkspace = {
    template: {
      id: "template-synthetic-reviewed-1",
      lineageId: "lineage-synthetic-reviewed-1",
      version: 1,
      name: "Template Twin Synthetic QA Fixture",
      encounterType: "Synthetic follow-up encounter",
      status: "draft",
      certificationStatus: "needs_confirmation",
    },
    source: {
      sha256: ir.source.sha256,
      sizeBytes: ir.source.sizeBytes,
      mimeType: ir.source.mimeType,
      compiledAtIso: "2026-07-19T00:00:00.000Z",
      compilerVersion: ir.compilerVersion,
    },
    stagingQaFixtureSource: true,
    stats: ir.stats,
    fields: ir.fields.map((field, index) => ({
      definitionId: `definition-synthetic-${index + 1}`,
      field,
      mapping: mappings[index]!,
      intent: unresolvedFieldIntent(),
      customConceptScaffold: null,
    })),
    unsupported: ir.unsupported,
    mappingsSha256: "a".repeat(64),
    fieldIntentsSha256: "b".repeat(64),
    admissionChecks: [],
    latestSyntheticTest: null,
    canEdit: true,
  };
});

function cloneWorkspace(): TemplateTwinWorkspace {
  return structuredClone(reviewedWorkspace);
}

function expectReviewedError(
  operation: () => unknown,
  code: TemplateTwinStagingQaReviewedMappingsError["code"],
): void {
  try {
    operation();
    throw new Error("Expected the reviewed mapping contract to fail closed.");
  } catch (error) {
    expect(error).toBeInstanceOf(
      TemplateTwinStagingQaReviewedMappingsError,
    );
    expect(
      (error as TemplateTwinStagingQaReviewedMappingsError).code,
    ).toBe(code);
  }
}

describe("reviewed synthetic fixture mapping contract", () => {
  it("loads all eight reviewed mappings without persisting or activating", () => {
    const workspace = cloneWorkspace();
    const before = structuredClone(workspace);
    const result = buildTemplateTwinStagingQaReviewedMappingDraft(workspace);

    expect(workspace).toEqual(before);
    expect(result).toMatchObject({
      contractVersion:
        TEMPLATE_TWIN_STAGING_QA_REVIEWED_MAPPING_CONTRACT_VERSION,
      fixture: {
        sha256: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
        sizeBytes: TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
      },
      template: { id: workspace.template.id, version: 1 },
      expectedMappingsSha256: "a".repeat(64),
      expectedFieldIntentsSha256: "b".repeat(64),
      physicianReviewSummary: {
        fieldCount: 8,
        explicitConfirmationRequired: true,
        activationPerformed: false,
        settings: {
          approvedSynonyms: "none",
          practiceDefaults: "none",
          blankPolicy: "blank",
          missingClinicalDetail: "requires_input",
          requiredBeforeSigning: true,
        },
      },
    });
    expect(result.mappings).toHaveLength(8);
    expect(result.mappings.map((mapping) => mapping.clinicalConcept)).toEqual(
      TEMPLATE_TWIN_STAGING_QA_REVIEWED_FIELD_CONTRACT.map(
        (field) => field.clinicalConcept,
      ),
    );
    expect(
      result.mappings.every(
        (mapping) =>
          mapping.status === "certified" &&
          mapping.temporality === "any" &&
          mapping.laterality === "not_applicable" &&
          mapping.unitPolicy === "not_applicable" &&
          mapping.required &&
          mapping.blankPolicy === "blank" &&
          mapping.unknownPolicy === "requires_input" &&
          mapping.approvedSynonyms.length === 0 &&
          mapping.practiceDefault === null,
      ),
    ).toBe(true);
    expect(result.fieldIntents).toEqual([
      {
        fieldId: "ttf_471aee4f349042e2d7e10237",
        intentKind: "supported_concept",
        supportedConcept: "hpi.context",
      },
    ]);
    expect(result.physicianReviewSummary.fields).toHaveLength(8);
  });

  it.each([
    ["source digest", (workspace: TemplateTwinWorkspace) => {
      workspace.source.sha256 = "c".repeat(64);
    }, "UNAVAILABLE"],
    ["source byte count", (workspace: TemplateTwinWorkspace) => {
      workspace.source.sizeBytes += 1;
    }, "UNAVAILABLE"],
    ["staging provenance", (workspace: TemplateTwinWorkspace) => {
      workspace.stagingQaFixtureSource = false;
    }, "UNAVAILABLE"],
    ["field inventory", (workspace: TemplateTwinWorkspace) => {
      workspace.fields.pop();
      workspace.stats.totalFields -= 1;
    }, "CONTRACT_MISMATCH"],
    ["field label", (workspace: TemplateTwinWorkspace) => {
      workspace.fields[0]!.field.originalLabel = "Lookalike chief concern";
    }, "CONTRACT_MISMATCH"],
    ["binding identity", (workspace: TemplateTwinWorkspace) => {
      workspace.fields[0]!.field.rendererBinding.sourceBindingIdentitySha256 =
        "d".repeat(64);
    }, "CONTRACT_MISMATCH"],
    ["field kind", (workspace: TemplateTwinWorkspace) => {
      workspace.fields[0]!.field.kind = "date";
    }, "CONTRACT_MISMATCH"],
    ["structure setting", (workspace: TemplateTwinWorkspace) => {
      workspace.stats.tables = 2;
    }, "CONTRACT_MISMATCH"],
  ] as const)("fails closed when the %s drifts", (_label, mutate, code) => {
    const workspace = cloneWorkspace();
    mutate(workspace);
    expectReviewedError(
      () => buildTemplateTwinStagingQaReviewedMappingDraft(workspace),
      code,
    );
  });

  it("does not load into a certified or otherwise immutable version", () => {
    const workspace = cloneWorkspace();
    workspace.canEdit = false;
    workspace.template.status = "active";
    workspace.template.certificationStatus = "certified";
    expectReviewedError(
      () => buildTemplateTwinStagingQaReviewedMappingDraft(workspace),
      "NOT_EDITABLE",
    );
  });

  it("keeps the durable read tenant- and doctor-scoped", async () => {
    const readWorkspace = vi.fn().mockResolvedValue(cloneWorkspace());
    const reviewed = await loadTemplateTwinStagingQaReviewedMappingDraft({
      noteTemplateId: "template-synthetic-reviewed-1",
      doctorId: "doctor-synthetic-reviewed-1",
      practiceId: "practice-synthetic-reviewed-1",
      dependencies: { readWorkspace },
    });

    expect(readWorkspace).toHaveBeenCalledWith({
      noteTemplateId: "template-synthetic-reviewed-1",
      doctorId: "doctor-synthetic-reviewed-1",
      practiceId: "practice-synthetic-reviewed-1",
    });
    expect(reviewed.template.id).toBe("template-synthetic-reviewed-1");
  });

  it("fails closed when the scoped durable read resolves no owned version", async () => {
    const readWorkspace = vi.fn().mockResolvedValue(null);
    await expect(
      loadTemplateTwinStagingQaReviewedMappingDraft({
        noteTemplateId: "template-arbitrary-1",
        doctorId: "doctor-synthetic-reviewed-1",
        practiceId: "practice-synthetic-reviewed-1",
        dependencies: { readWorkspace },
      }),
    ).rejects.toMatchObject({ code: "UNAVAILABLE" });
  });
});
