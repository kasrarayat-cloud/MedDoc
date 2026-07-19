import { readFile } from "node:fs/promises";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  POST_LIBREOFFICE_ARTIFACTS,
  POST_LIBREOFFICE_OBSERVATION_PROVENANCE_SHA256,
  POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
  POST_LIBREOFFICE_REVIEWED_FINDINGS,
} from "../office-libreoffice-reviewed-registry";

const matrixPath = path.resolve(
  process.cwd(),
  "../../docs/qa/template-twin-office-schema-error-matrix.json",
);

interface SchemaMatrix {
  matrixContract: string;
  observationSourceCommit: string;
  observationRegistrySha256: string;
  observationProvenanceSha256: string;
  reviewProvenance: {
    approvalEffect: string;
    independentReviewStatus: string;
    acceptedIndependentReviewRecordSha256: string | null;
    compatibilityEngineeringStatus: string;
    compatibilityEngineeringEligible: boolean;
    syntheticReviewerPackageGenerationEligible: boolean;
  };
  stageSummary: Array<{
    stage: string;
    documents?: number;
    errors?: number;
    physicalFindings?: number;
    targetObservations?: number;
    result: string;
  }>;
  classificationSummary: Record<string, number>;
  artifacts: Array<{
    caseId: string;
    filename: string;
    sha256: string;
    sizeBytes: number;
  }>;
  policy: string;
  errors: Array<{
    findingId: string;
    caseId: string;
    artifactFilename: string;
    officeTargets: string[];
    familyCode: string;
    validatorErrorId: string;
    errorType: string;
    description: string;
    descriptionSha256: string;
    classificationRationale: string;
    classificationRationaleSha256: string;
    partName: string;
    path: string;
    pathSha256: string;
    elementQName: string;
    attributeQName: string;
    observedValue: string;
    disposition: string;
    schemaValid: boolean;
    signingEligible: boolean;
    reimportEligible: boolean;
  }>;
}

async function loadMatrix(): Promise<SchemaMatrix> {
  return JSON.parse(await readFile(matrixPath, "utf8")) as SchemaMatrix;
}

describe("Template Twin Office schema-stage evidence", () => {
  it("records the exact current source/renderer zero-error boundary", async () => {
    const matrix = await loadMatrix();

    expect(matrix.matrixContract).toBe(
      "template-twin-office-schema-stage-matrix/2.0.0",
    );
    expect(matrix.observationSourceCommit).toBe(
      "f16e7b48944d48d24fa768efefbc6a26159e1f09",
    );
    expect(matrix.observationRegistrySha256).toBe(
      POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
    );
    expect(matrix.observationProvenanceSha256).toBe(
      POST_LIBREOFFICE_OBSERVATION_PROVENANCE_SHA256,
    );
    expect(matrix.stageSummary).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          stage: "synthetic_source_before_rendering",
          documents: 7,
          errors: 0,
          result: "PASS",
        }),
        expect.objectContaining({
          stage: "quillmd_rendered_before_libreoffice",
          documents: 5,
          errors: 0,
          result: "PASS",
        }),
      ]),
    );
  });

  it("binds all five exact LibreOffice-saved artifacts and 32/64 closed findings", async () => {
    const matrix = await loadMatrix();
    const officeStage = matrix.stageSummary.find(
      (stage) => stage.stage === "libreoffice_saved",
    );

    expect(officeStage).toMatchObject({
      documents: 5,
      physicalFindings: 32,
      targetObservations: 64,
      result: "EXTERNAL_TOOL_PENDING_WORD_NOT_SCHEMA_VALID",
    });
    expect(matrix.classificationSummary).toEqual({
      FONT_CHARACTER_SET_EXTENSION: 25,
      LOGICAL_ALIGNMENT_ENUM: 2,
      TABLE_ROW_ON_OFF_LEXICAL_VALUE: 1,
      LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW: 4,
    });
    expect(matrix.artifacts).toHaveLength(5);
    expect(matrix.artifacts).toEqual(POST_LIBREOFFICE_ARTIFACTS);
    expect(
      new Set(matrix.artifacts.map((artifact) => artifact.caseId)).size,
    ).toBe(5);
    for (const artifact of matrix.artifacts) {
      expect(artifact.filename).toBe(
        `${artifact.caseId}.libreoffice-saved.docx`,
      );
      expect(artifact.sha256).toMatch(/^[a-f0-9]{64}$/u);
      expect(artifact.sizeBytes).toBeGreaterThan(0);
    }
    expect(matrix.errors).toHaveLength(32);
    expect(new Set(matrix.errors.map((error) => error.findingId)).size).toBe(
      32,
    );
    expect(matrix.errors).toEqual(
      POST_LIBREOFFICE_REVIEWED_FINDINGS.map((finding) => ({
        findingId: finding.findingId,
        caseId: finding.caseId,
        artifactFilename: finding.artifactFilename,
        officeTargets: ["Office2013", "Microsoft365"],
        familyCode: finding.familyCode,
        validatorErrorId: finding.validatorErrorId,
        errorType: finding.errorType,
        description: finding.description,
        descriptionSha256: finding.descriptionSha256,
        classificationRationale: finding.classificationRationale,
        classificationRationaleSha256: finding.classificationRationaleSha256,
        partName: finding.partName,
        path: finding.path,
        pathSha256: finding.pathSha256,
        elementQName: finding.elementQName,
        attributeQName: finding.attributeQName,
        observedValue: finding.observedValue,
        disposition: "external_tool_pending_word",
        schemaValid: false,
        signingEligible: false,
        reimportEligible: false,
      })),
    );

    for (const error of matrix.errors) {
      expect(error.officeTargets).toEqual(["Office2013", "Microsoft365"]);
      expect(error.artifactFilename).toBe(
        `${error.caseId}.libreoffice-saved.docx`,
      );
      expect(error.validatorErrorId).toBe("Sch_AttributeValueDataTypeDetailed");
      expect(error.errorType).toBe("Schema");
      expect(error.description).not.toHaveLength(0);
      expect(error.descriptionSha256).toMatch(/^[a-f0-9]{64}$/u);
      expect(error.classificationRationaleSha256).toMatch(/^[a-f0-9]{64}$/u);
      expect(error.partName).toMatch(/^\/word\//u);
      expect(error.path).toMatch(/^\/w:/u);
      expect(error.pathSha256).toMatch(/^[a-f0-9]{64}$/u);
      expect(error.elementQName).toMatch(/^w:/u);
      expect(error.attributeQName).toMatch(/^w:/u);
      expect(error.observedValue).not.toHaveLength(0);
      expect(error.disposition).toBe("external_tool_pending_word");
      expect(error.schemaValid).toBe(false);
      expect(error.signingEligible).toBe(false);
      expect(error.reimportEligible).toBe(false);
    }
  });

  it("records no approval and forbids treating external findings as schema-valid or authoritative", async () => {
    const matrix = await loadMatrix();

    expect(matrix.reviewProvenance).toEqual({
      approvalEffect: "none",
      independentReviewStatus: "PENDING",
      acceptedIndependentReviewRecordSha256: null,
      compatibilityEngineeringStatus: "PENDING_INDEPENDENT_EXACT_HEAD_REVIEW",
      compatibilityEngineeringEligible: false,
      syntheticReviewerPackageGenerationEligible: true,
    });
    expect(matrix.policy).toContain(
      "Sources and immutable pre-delivery renderer outputs require zero errors.",
    );
    expect(matrix.policy).toContain(
      "independent exact-head review remains PENDING",
    );
    expect(matrix.policy).toContain(
      "never schema-valid, compatibility-engineering-accepted",
    );
    expect(matrix.policy).toContain(
      "only non-authorizing synthetic reviewer-package generation is eligible",
    );
  });
});
