import { describe, expect, it } from "vitest";

import {
  POST_LIBREOFFICE_ARTIFACTS,
  POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS,
  POST_LIBREOFFICE_EXPECTED_TARGET_OBSERVATIONS,
  POST_LIBREOFFICE_REVIEWED_FINDINGS,
  POST_LIBREOFFICE_TARGETS,
  reviewedFindingsForArtifact,
} from "../office-libreoffice-reviewed-registry";
import {
  assertPostLibreOfficeEvidenceManifest,
  buildPostLibreOfficeEvidenceManifest,
  POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256,
  POST_LIBREOFFICE_VALIDATOR_NAME,
  POST_LIBREOFFICE_VALIDATOR_PACKAGE_VERSION,
  POST_LIBREOFFICE_VALIDATOR_SDK_VERSION,
  POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256,
  type BuildPostLibreOfficeEvidenceInput,
} from "../office-post-libreoffice-evidence";

const SOURCE_COMMIT = "a".repeat(40);
const GENERATED_AT = "2026-07-19T18:36:44+00:00";

function libreOfficeResults() {
  return {
    contractVersion: "template-twin-human-gate-libreoffice-evidence/1.0.0",
    sourceCommit: SOURCE_COMMIT,
    generatedAtIso: GENERATED_AT,
    syntheticOnly: true,
    image:
      "lscr.io/linuxserver/libreoffice@sha256:92b7de866a39764dc51040918885cb9178f1ec3ff11d8336621ddf2239dfcfe4",
    results: POST_LIBREOFFICE_ARTIFACTS.map((artifact) => ({
      id: artifact.caseId,
      sourceCommit: SOURCE_COMMIT,
      libreOfficeSaved: {
        sha256: artifact.sha256,
        sizeBytes: artifact.sizeBytes,
      },
      semanticSurvival: true,
      staticComparison: { aggregateVisibleContentMatches: true },
      security: { status: "passed" },
      visual: { status: "passed" },
    })),
    overallStatus: "passed",
    microsoftWordStatus: "PENDING",
  };
}

function report(target: (typeof POST_LIBREOFFICE_TARGETS)[number]) {
  return {
    tool: POST_LIBREOFFICE_VALIDATOR_NAME,
    sdkVersion: POST_LIBREOFFICE_VALIDATOR_SDK_VERSION,
    packageVersion: POST_LIBREOFFICE_VALIDATOR_PACKAGE_VERSION,
    validatorExecutableSha256: POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256,
    targetFileFormat: target,
    sourceCommit: SOURCE_COMMIT,
    generatedAt: GENERATED_AT,
    results: POST_LIBREOFFICE_ARTIFACTS.map((artifact) => {
      const findings = reviewedFindingsForArtifact(artifact.filename);
      return {
        file: artifact.filename,
        sha256: artifact.sha256,
        sizeBytes: artifact.sizeBytes,
        opened: true,
        valid: false,
        errorCount: findings.length,
        errors: findings.map((finding) => ({
          id: finding.validatorErrorId,
          type: finding.errorType,
          description: finding.description,
          part: finding.partName,
          path: finding.path,
        })),
      };
    }),
  };
}

function input(): BuildPostLibreOfficeEvidenceInput {
  return {
    sourceCommit: SOURCE_COMMIT,
    generatedAtIso: GENERATED_AT,
    validatorExecutableSha256: POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256,
    windowsValidatorExecutableSha256:
      POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256,
    libreOfficeResults: {
      relativePath: "libreoffice-results.json",
      bytes: Buffer.from(JSON.stringify(libreOfficeResults()), "utf8"),
    },
    rawReports: POST_LIBREOFFICE_TARGETS.map((target) => ({
      relativePath: `post-libreoffice-${target}.json`,
      bytes: Buffer.from(JSON.stringify(report(target)), "utf8"),
    })),
    savedArtifacts: POST_LIBREOFFICE_ARTIFACTS,
  };
}

function mutateReport(
  current: BuildPostLibreOfficeEvidenceInput,
  target: (typeof POST_LIBREOFFICE_TARGETS)[number],
  mutate: (value: ReturnType<typeof report>) => void,
): BuildPostLibreOfficeEvidenceInput {
  return {
    ...current,
    rawReports: current.rawReports.map((raw) => {
      if (raw.relativePath !== `post-libreoffice-${target}.json`) return raw;
      const value = JSON.parse(
        Buffer.from(raw.bytes).toString("utf8"),
      ) as ReturnType<typeof report>;
      mutate(value);
      return { ...raw, bytes: Buffer.from(JSON.stringify(value), "utf8") };
    }),
  };
}

describe("post-LibreOffice Open XML evidence", () => {
  it("binds the exact five artifacts, 32 physical findings, and 64 target observations without granting authority", () => {
    const manifest = buildPostLibreOfficeEvidenceManifest(input());

    expect(POST_LIBREOFFICE_REVIEWED_FINDINGS).toHaveLength(
      POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS,
    );
    expect(manifest).toMatchObject({
      syntheticOnly: true,
      schemaStatus: "external_tool_pending_word",
      schemaValid: false,
      signingEligible: false,
      reimportEligible: false,
      productionStateTransitionEligible: false,
      compatibilityEngineeringStatus: "PENDING_INDEPENDENT_EXACT_HEAD_REVIEW",
      compatibilityEngineeringEligible: false,
      syntheticReviewerPackageGenerationEligible: true,
      desktopWordApprovalRequired: true,
      reviewProvenance: {
        approvalEffect: "none",
        independentReviewStatus: "PENDING",
        acceptedIndependentReviewRecordSha256: null,
      },
      reviewAdvancement: {
        bindingMode: "separate_additive_review_record",
        implementationAuthorMayApprove: false,
        freshIndependentExactHeadReviewAfterBindingRequired: true,
      },
      totals: {
        savedArtifacts: 5,
        physicalFindings: POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS,
        targetObservations: POST_LIBREOFFICE_EXPECTED_TARGET_OBSERVATIONS,
        unclassifiedFindings: 0,
        blockingUnknownFindings: 0,
      },
      classificationSummary: {
        FONT_CHARACTER_SET_EXTENSION: 25,
        LOGICAL_ALIGNMENT_ENUM: 2,
        TABLE_ROW_ON_OFF_LEXICAL_VALUE: 1,
        LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW: 4,
      },
    });
    expect(manifest.savedArtifacts).toHaveLength(5);
    expect(manifest.findings).toHaveLength(32);
    expect(
      manifest.findings.flatMap((finding) => finding.targetObservations),
    ).toHaveLength(64);
    expect(manifest.evidenceSha256).toMatch(/^[a-f0-9]{64}$/u);
    expect(buildPostLibreOfficeEvidenceManifest(input())).toEqual(manifest);
  });

  it("rejects missing, duplicate, and unknown artifacts", () => {
    const current = input();
    expect(() =>
      buildPostLibreOfficeEvidenceManifest({
        ...current,
        savedArtifacts: current.savedArtifacts.slice(1),
      }),
    ).toThrow("POST_LIBREOFFICE_ARTIFACT_COUNT_DRIFT");
    expect(() =>
      buildPostLibreOfficeEvidenceManifest({
        ...current,
        savedArtifacts: [
          ...current.savedArtifacts.slice(0, -1),
          current.savedArtifacts[0]!,
        ],
      }),
    ).toThrow("POST_LIBREOFFICE_ARTIFACT_DUPLICATE");

    const unknown = mutateReport(current, "Office2013", (value) => {
      (value.results[0]! as { file: string }).file =
        "unknown.libreoffice-saved.docx";
    });
    expect(() => buildPostLibreOfficeEvidenceManifest(unknown)).toThrow(
      "POST_LIBREOFFICE_ARTIFACT_MISSING",
    );
  });

  it("rejects artifact hash and size drift in either the observed files or validator report", () => {
    const current = input();
    expect(() =>
      buildPostLibreOfficeEvidenceManifest({
        ...current,
        savedArtifacts: current.savedArtifacts.map((artifact, index) =>
          index === 0 ? { ...artifact, sha256: "f".repeat(64) } : artifact,
        ),
      }),
    ).toThrow("POST_LIBREOFFICE_LIBREOFFICE_RESULT_DRIFT");

    const changedReport = mutateReport(current, "Microsoft365", (value) => {
      value.results[0]!.sizeBytes += 1;
    });
    expect(() => buildPostLibreOfficeEvidenceManifest(changedReport)).toThrow(
      "POST_LIBREOFFICE_ARTIFACT_IDENTITY_DRIFT",
    );
  });

  it("binds a fresh run's nondeterministic ZIP hash only when actual bytes, LibreOffice evidence, and both reports agree", () => {
    const current = input();
    const freshSha256 = "d".repeat(64);
    const freshSizeBytes = current.savedArtifacts[0]!.sizeBytes + 17;
    const libreOffice = JSON.parse(
      Buffer.from(current.libreOfficeResults.bytes).toString("utf8"),
    ) as ReturnType<typeof libreOfficeResults>;
    libreOffice.results[0]!.libreOfficeSaved = {
      sha256: freshSha256,
      sizeBytes: freshSizeBytes,
    } as (typeof libreOffice.results)[number]["libreOfficeSaved"];
    const freshInput: BuildPostLibreOfficeEvidenceInput = {
      ...current,
      libreOfficeResults: {
        ...current.libreOfficeResults,
        bytes: Buffer.from(JSON.stringify(libreOffice), "utf8"),
      },
      savedArtifacts: current.savedArtifacts.map((artifact, index) =>
        index === 0
          ? { ...artifact, sha256: freshSha256, sizeBytes: freshSizeBytes }
          : artifact,
      ),
      rawReports: current.rawReports.map((raw) => {
        const value = JSON.parse(
          Buffer.from(raw.bytes).toString("utf8"),
        ) as ReturnType<typeof report>;
        (value.results[0]! as { sha256: string }).sha256 = freshSha256;
        (value.results[0]! as { sizeBytes: number }).sizeBytes = freshSizeBytes;
        return { ...raw, bytes: Buffer.from(JSON.stringify(value), "utf8") };
      }),
    };

    const manifest = buildPostLibreOfficeEvidenceManifest(freshInput);
    expect(manifest.savedArtifacts[0]).toMatchObject({
      sha256: freshSha256,
      sizeBytes: freshSizeBytes,
    });
    expect(manifest.libreOfficeEvidence.sha256).toMatch(/^[a-f0-9]{64}$/u);
  });

  it.each([
    ["unknown error", "id", "Sch_Unknown"],
    ["description drift", "description", "Synthetic changed description."],
    ["path drift", "path", "/w:document[1]/w:body[2]"],
    ["part drift", "part", "/word/header1.xml"],
  ] as const)("rejects %s", (_label, key, value) => {
    const changed = mutateReport(input(), "Office2013", (reportValue) => {
      Object.assign(reportValue.results[0]!.errors[0]!, { [key]: value });
    });
    expect(() => buildPostLibreOfficeEvidenceManifest(changed)).toThrow(
      "POST_LIBREOFFICE_DIAGNOSTIC_UNREVIEWED",
    );
  });

  it("rejects missing/count drift and unknown report or diagnostic fields", () => {
    const current = input();
    expect(() =>
      buildPostLibreOfficeEvidenceManifest({
        ...current,
        rawReports: current.rawReports.slice(1),
      }),
    ).toThrow("POST_LIBREOFFICE_REPORT_COUNT_DRIFT");

    const missing = mutateReport(input(), "Office2013", (value) => {
      value.results[0]!.errors.pop();
    });
    expect(() => buildPostLibreOfficeEvidenceManifest(missing)).toThrow(
      "POST_LIBREOFFICE_DIAGNOSTIC_COUNT_DRIFT",
    );

    const unknownDiagnosticField = mutateReport(
      input(),
      "Office2013",
      (value) => {
        Object.assign(value.results[0]!.errors[0]!, { syntheticExtra: true });
      },
    );
    expect(() =>
      buildPostLibreOfficeEvidenceManifest(unknownDiagnosticField),
    ).toThrow("POST_LIBREOFFICE_DIAGNOSTIC_UNKNOWN_FIELD");

    const unknownReportField = mutateReport(input(), "Office2013", (value) => {
      Object.assign(value, { syntheticExtra: true });
    });
    expect(() =>
      buildPostLibreOfficeEvidenceManifest(unknownReportField),
    ).toThrow("POST_LIBREOFFICE_REPORT_UNKNOWN_FIELD");

    const unknownResultField = mutateReport(input(), "Office2013", (value) => {
      Object.assign(value.results[0]!, { syntheticExtra: true });
    });
    expect(() =>
      buildPostLibreOfficeEvidenceManifest(unknownResultField),
    ).toThrow("POST_LIBREOFFICE_RESULT_UNKNOWN_FIELD");
  });

  it("rejects source, target, path, and executable provenance drift", () => {
    const current = input();
    expect(() =>
      buildPostLibreOfficeEvidenceManifest({
        ...current,
        sourceCommit: "b".repeat(40),
      }),
    ).toThrow("POST_LIBREOFFICE_LIBREOFFICE_PROVENANCE_DRIFT");
    expect(() =>
      buildPostLibreOfficeEvidenceManifest({
        ...current,
        validatorExecutableSha256: "f".repeat(64),
      }),
    ).toThrow("POST_LIBREOFFICE_VALIDATOR_IDENTITY_DRIFT");
    expect(() =>
      buildPostLibreOfficeEvidenceManifest({
        ...current,
        rawReports: current.rawReports.map((raw, index) =>
          index === 0 ? { ...raw, relativePath: "renamed.json" } : raw,
        ),
      }),
    ).toThrow("POST_LIBREOFFICE_REPORT_PATH_DRIFT");

    const changedTarget = mutateReport(current, "Office2013", (value) => {
      value.targetFileFormat = "Microsoft365";
    });
    expect(() => buildPostLibreOfficeEvidenceManifest(changedTarget)).toThrow(
      "POST_LIBREOFFICE_REPORT_PATH_DRIFT",
    );
  });

  it("canonicalizes raw diagnostic order and rejects a tampered canonical manifest", () => {
    const changed = mutateReport(input(), "Microsoft365", (value) => {
      const first = value.results[0]!.errors[0]!;
      const second = value.results[0]!.errors[1]!;
      value.results[0]!.errors[0] = second;
      value.results[0]!.errors[1] = first;
    });
    // Ordering is not evidence drift; the closed multiset is canonicalized.
    const manifest = buildPostLibreOfficeEvidenceManifest(changed);
    expect(manifest.totals.targetObservations).toBe(64);

    expect(() =>
      assertPostLibreOfficeEvidenceManifest(
        { ...manifest, schemaValid: true },
        manifest,
      ),
    ).toThrow("POST_LIBREOFFICE_CANONICAL_MANIFEST_DRIFT");
  });
});
