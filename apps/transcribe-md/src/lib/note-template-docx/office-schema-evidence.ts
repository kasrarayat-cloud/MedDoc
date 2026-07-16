import { canonicalSha256 } from "../template-twin/canonical";

export const OFFICE_SCHEMA_QA_CONTRACT_VERSION =
  "template-twin-office-schema-qa/2.0.0" as const;
export const OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION =
  "template-twin-libreoffice-schema-review/1.0.0" as const;
export const OFFICE_QA_EVIDENCE_CLASS =
  "QA_ONLY_OFFICE_COMPATIBILITY_EVIDENCE" as const;

export type OfficeSchemaArtifactStage =
  | "source"
  | "renderer_output"
  | "office_saved";
export type OfficeSchemaDiagnosticSeverity = "warning" | "error";
export type OfficeSchemaDiagnosticDisposition =
  | "blocking"
  | "reviewed_non_blocking"
  /**
   * Known schema-invalid output introduced only by an external Office tool.
   * This can permit continued compatibility engineering, but never marks the
   * file valid, Word-approved, or eligible for signing.
   */
  | "external_tool_pending_word";

export interface OfficeSchemaDiagnosticEvidence {
  readonly diagnosticId: string;
  readonly validatorErrorId: string;
  readonly severity: OfficeSchemaDiagnosticSeverity;
  /** Stable reviewed family; never infer an allow from an unknown diagnostic. */
  readonly familyCode: string | null;
  readonly disposition: OfficeSchemaDiagnosticDisposition | null;
  readonly descriptionSha256: string;
  readonly classificationRationaleSha256: string | null;
  readonly partName: string | null;
  readonly pathSha256: string | null;
  readonly elementQName: string | null;
  readonly attributeQName: string | null;
  readonly observedValue: string | null;
}

export interface OfficeSchemaArtifactEvidence {
  readonly artifactId: string;
  readonly artifactSha256: string;
  readonly opened: boolean;
  readonly reportedDiagnosticCount: number;
  readonly validatorLogSha256: string;
  readonly diagnostics: readonly OfficeSchemaDiagnosticEvidence[];
}

export interface OfficeSchemaStageEvidence {
  readonly stage: OfficeSchemaArtifactStage;
  readonly targetFormat: string;
  readonly validatorName: string;
  readonly validatorVersion: string;
  readonly executionLogSha256: string;
  readonly artifacts: readonly OfficeSchemaArtifactEvidence[];
}

export interface RequiredOfficeSchemaStage {
  readonly stage: OfficeSchemaArtifactStage;
  readonly targetFormat: string;
  readonly artifactIds: readonly string[];
}

export interface EvaluateOfficeSchemaEvidenceInput {
  readonly syntheticOnly: true;
  readonly requiredStages: readonly RequiredOfficeSchemaStage[];
  readonly stages: readonly OfficeSchemaStageEvidence[];
  readonly reviewerProvenance: {
    readonly reviewerId: string;
    readonly reviewerRole: "independent_office_release_auditor";
    readonly reviewedAt: string;
    readonly reviewRecordSha256: string;
    readonly registryVersion: typeof OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION;
  };
}

export type OfficeSchemaQaBlockerCode =
  | "OFFICE_SCHEMA_EVIDENCE_INVALID"
  | "OFFICE_SCHEMA_REQUIRED_STAGE_MISSING"
  | "OFFICE_SCHEMA_REQUIRED_ARTIFACT_MISSING"
  | "OFFICE_SCHEMA_ARTIFACT_OPEN_FAILED"
  | "OFFICE_SCHEMA_DIAGNOSTIC_COUNT_MISMATCH"
  | "OFFICE_SCHEMA_DIAGNOSTIC_UNCLASSIFIED"
  | "OFFICE_SCHEMA_STAGE_SET_INVALID"
  | "OFFICE_SCHEMA_EXTERNAL_CLASSIFICATION_NOT_REVIEWED"
  | "OFFICE_SCHEMA_ERROR_PRESENT"
  | "OFFICE_SCHEMA_BLOCKING_WARNING";

export interface OfficeSchemaMatrixRow {
  readonly matrixId: string;
  readonly stage: OfficeSchemaArtifactStage;
  readonly targetFormat: string;
  readonly artifactId: string;
  readonly artifactSha256: string;
  readonly diagnosticIndex: number;
  readonly diagnosticId: string;
  readonly validatorErrorId: string;
  readonly severity: OfficeSchemaDiagnosticSeverity;
  readonly familyCode: string | null;
  readonly disposition: OfficeSchemaDiagnosticDisposition | null;
  readonly descriptionSha256: string;
  readonly classificationRationaleSha256: string | null;
  readonly partName: string | null;
  readonly pathSha256: string | null;
  readonly elementQName: string | null;
  readonly attributeQName: string | null;
  readonly observedValue: string | null;
  readonly blocksQaGate: boolean;
  readonly requiresDesktopWordResolution: boolean;
}

export interface OfficeSchemaStageQaResult {
  readonly stage: OfficeSchemaArtifactStage;
  readonly targetFormat: string;
  readonly validatorName: string | null;
  readonly validatorVersion: string | null;
  readonly executionLogSha256: string | null;
  readonly requiredArtifactIds: readonly string[];
  readonly observedArtifactIds: readonly string[];
  readonly artifactEvidence: readonly {
    readonly artifactId: string;
    readonly artifactSha256: string;
    readonly validatorLogSha256: string;
    readonly opened: boolean;
  }[];
  readonly openedArtifactCount: number;
  readonly diagnosticCount: number;
  readonly errorCount: number;
  readonly warningCount: number;
  readonly reviewedNonBlockingWarningCount: number;
  readonly externalToolPendingWordErrorCount: number;
  readonly status: "passed" | "failed" | "external_tool_pending_word";
}

/**
 * QA-only schema evidence. This deliberately lacks the production readback-v2
 * shape and can never authorize signing, export, download, or state changes.
 */
export interface OfficeSchemaQaResult {
  readonly evidenceClass: typeof OFFICE_QA_EVIDENCE_CLASS;
  readonly contractVersion: typeof OFFICE_SCHEMA_QA_CONTRACT_VERSION;
  readonly qaOnly: true;
  readonly signingEligible: false;
  readonly productionStateTransitionEligible: false;
  readonly status: "passed" | "failed" | "external_tool_pending_word";
  readonly compatibilityEngineeringEligible: boolean;
  readonly desktopWordApprovalRequired: true;
  readonly blockerCodes: readonly OfficeSchemaQaBlockerCode[];
  readonly stages: readonly OfficeSchemaStageQaResult[];
  readonly matrix: readonly OfficeSchemaMatrixRow[];
  readonly matrixSha256: string;
  readonly reviewerProvenanceSha256: string;
  readonly evidenceSha256: string;
}

const SHA256 = /^[a-f0-9]{64}$/;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,239}$/;
const REQUIRED_STAGE_KEYS = new Set([
  "source\u0000Office2013",
  "source\u0000Microsoft365",
  "renderer_output\u0000Office2013",
  "renderer_output\u0000Microsoft365",
  "office_saved\u0000Office2013",
  "office_saved\u0000Microsoft365",
]);

function stageKey(
  stage: Pick<OfficeSchemaStageEvidence, "stage" | "targetFormat">,
): string {
  return `${stage.stage}\u0000${stage.targetFormat}`;
}

function uniqueSorted<T extends string>(values: readonly T[]): T[] {
  return [...new Set(values)].sort() as T[];
}

function validIdentifier(value: string): boolean {
  return SAFE_ID.test(value);
}

function validEvidenceSha256(value: string): boolean {
  return SHA256.test(value) && !/^0{64}$/.test(value);
}

function validDiagnostic(diagnostic: OfficeSchemaDiagnosticEvidence): boolean {
  return Boolean(
    validIdentifier(diagnostic.diagnosticId) &&
    validIdentifier(diagnostic.validatorErrorId) &&
    validEvidenceSha256(diagnostic.descriptionSha256) &&
    (diagnostic.familyCode === null ||
      validIdentifier(diagnostic.familyCode)) &&
    (diagnostic.classificationRationaleSha256 === null ||
      validEvidenceSha256(diagnostic.classificationRationaleSha256)) &&
    (diagnostic.partName === null ||
      (diagnostic.partName.length > 0 && diagnostic.partName.length <= 240)) &&
    (diagnostic.pathSha256 === null ||
      validEvidenceSha256(diagnostic.pathSha256)) &&
    (diagnostic.elementQName === null ||
      validIdentifier(diagnostic.elementQName)) &&
    (diagnostic.attributeQName === null ||
      validIdentifier(diagnostic.attributeQName)) &&
    (diagnostic.observedValue === null ||
      (diagnostic.observedValue.length > 0 &&
        diagnostic.observedValue.length <= 80)),
  );
}

/**
 * Exact, reviewed LibreOffice-only schema failures. This is intentionally a
 * closed registry, not a caller-extensible allowlist.
 */
function matchesReviewedLibreOfficeRegistry(
  stage: OfficeSchemaStageEvidence,
  diagnostic: OfficeSchemaDiagnosticEvidence,
): boolean {
  if (
    stage.stage !== "office_saved" ||
    stage.validatorName !== "DocumentFormat.OpenXml.OpenXmlValidator" ||
    stage.validatorVersion !== "3.5.1.0" ||
    !["Office2013", "Microsoft365"].includes(stage.targetFormat) ||
    diagnostic.severity !== "error" ||
    diagnostic.disposition !== "external_tool_pending_word" ||
    diagnostic.validatorErrorId !== "Sch_AttributeValueDataTypeDetailed" ||
    !diagnostic.classificationRationaleSha256 ||
    !diagnostic.partName ||
    !diagnostic.elementQName ||
    !diagnostic.attributeQName ||
    !diagnostic.observedValue
  ) {
    return false;
  }
  if (diagnostic.familyCode === "FONT_CHARACTER_SET_EXTENSION") {
    return Boolean(
      diagnostic.partName === "/word/fontTable.xml" &&
      diagnostic.elementQName === "w:charset" &&
      diagnostic.attributeQName === "w:characterSet" &&
      ["utf-8", "windows-1252"].includes(diagnostic.observedValue),
    );
  }
  if (diagnostic.familyCode === "LOGICAL_ALIGNMENT_ENUM") {
    return Boolean(
      ["/word/document.xml", "/word/numbering.xml"].includes(
        diagnostic.partName,
      ) &&
      ["w:jc", "w:lvlJc"].includes(diagnostic.elementQName) &&
      diagnostic.attributeQName === "w:val" &&
      diagnostic.observedValue === "start",
    );
  }
  if (diagnostic.familyCode === "TABLE_ROW_ON_OFF_LEXICAL_VALUE") {
    return Boolean(
      diagnostic.partName === "/word/document.xml" &&
      ["w:cantSplit", "w:tblHeader"].includes(diagnostic.elementQName) &&
      diagnostic.attributeQName === "w:val" &&
      diagnostic.observedValue === "true",
    );
  }
  return false;
}

function matrixRow(
  stage: OfficeSchemaStageEvidence,
  artifact: OfficeSchemaArtifactEvidence,
  diagnostic: OfficeSchemaDiagnosticEvidence,
  diagnosticIndex: number,
): OfficeSchemaMatrixRow {
  const classified = Boolean(
    diagnostic.familyCode &&
    diagnostic.disposition &&
    diagnostic.classificationRationaleSha256,
  );
  const requiresDesktopWordResolution = Boolean(
    classified && matchesReviewedLibreOfficeRegistry(stage, diagnostic),
  );
  const blocksQaGate =
    !classified ||
    (diagnostic.severity === "error" && !requiresDesktopWordResolution) ||
    diagnostic.disposition === "blocking";
  const rowWithoutId = {
    stage: stage.stage,
    targetFormat: stage.targetFormat,
    artifactId: artifact.artifactId,
    artifactSha256: artifact.artifactSha256,
    diagnosticIndex,
    diagnosticId: diagnostic.diagnosticId,
    validatorErrorId: diagnostic.validatorErrorId,
    severity: diagnostic.severity,
    familyCode: diagnostic.familyCode,
    disposition: diagnostic.disposition,
    descriptionSha256: diagnostic.descriptionSha256,
    classificationRationaleSha256: diagnostic.classificationRationaleSha256,
    partName: diagnostic.partName,
    pathSha256: diagnostic.pathSha256,
    elementQName: diagnostic.elementQName,
    attributeQName: diagnostic.attributeQName,
    observedValue: diagnostic.observedValue,
    blocksQaGate,
    requiresDesktopWordResolution,
  } as const;
  return Object.freeze({
    matrixId: `office_schema_${canonicalSha256(rowWithoutId).slice(0, 24)}`,
    ...rowWithoutId,
  });
}

export function evaluateOfficeSchemaEvidence(
  input: EvaluateOfficeSchemaEvidenceInput,
): OfficeSchemaQaResult {
  const blockers: OfficeSchemaQaBlockerCode[] = [];
  const add = (code: OfficeSchemaQaBlockerCode): void => {
    if (!blockers.includes(code)) blockers.push(code);
  };
  if (input.syntheticOnly !== true) add("OFFICE_SCHEMA_EVIDENCE_INVALID");
  const reviewer = input.reviewerProvenance;
  if (
    !reviewer ||
    !validIdentifier(reviewer.reviewerId) ||
    reviewer.reviewerRole !== "independent_office_release_auditor" ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(
      reviewer.reviewedAt,
    ) ||
    !validEvidenceSha256(reviewer.reviewRecordSha256) ||
    reviewer.registryVersion !== OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION
  ) {
    add("OFFICE_SCHEMA_EXTERNAL_CLASSIFICATION_NOT_REVIEWED");
  }
  const requiredStageKeys = new Set(input.requiredStages.map(stageKey));
  const observedStageKeys = new Set(input.stages.map(stageKey));
  if (
    input.requiredStages.length === 0 ||
    input.stages.length === 0 ||
    requiredStageKeys.size !== REQUIRED_STAGE_KEYS.size ||
    observedStageKeys.size !== REQUIRED_STAGE_KEYS.size ||
    [...REQUIRED_STAGE_KEYS].some(
      (key) => !requiredStageKeys.has(key) || !observedStageKeys.has(key),
    )
  ) {
    add("OFFICE_SCHEMA_STAGE_SET_INVALID");
  }

  const requirements = new Map<string, RequiredOfficeSchemaStage>();
  for (const requirement of input.requiredStages) {
    const key = stageKey(requirement);
    if (
      requirements.has(key) ||
      !validIdentifier(requirement.targetFormat) ||
      requirement.artifactIds.length === 0 ||
      uniqueSorted(requirement.artifactIds).length !==
        requirement.artifactIds.length ||
      requirement.artifactIds.some((artifactId) => !validIdentifier(artifactId))
    ) {
      add("OFFICE_SCHEMA_EVIDENCE_INVALID");
      continue;
    }
    requirements.set(key, requirement);
  }

  const observed = new Map<string, OfficeSchemaStageEvidence>();
  for (const stage of input.stages) {
    const key = stageKey(stage);
    if (
      observed.has(key) ||
      !validIdentifier(stage.targetFormat) ||
      !["Office2013", "Microsoft365"].includes(stage.targetFormat) ||
      stage.validatorName !== "DocumentFormat.OpenXml.OpenXmlValidator" ||
      stage.validatorVersion !== "3.5.1.0" ||
      !validEvidenceSha256(stage.executionLogSha256) ||
      stage.artifacts.length === 0
    ) {
      add("OFFICE_SCHEMA_EVIDENCE_INVALID");
      continue;
    }
    observed.set(key, stage);
  }
  if (
    observed.size !== requirements.size ||
    [...observed.keys()].some((key) => !requirements.has(key))
  ) {
    add("OFFICE_SCHEMA_STAGE_SET_INVALID");
  }
  const executionLogHashes = input.stages.map(
    (stage) => stage.executionLogSha256,
  );
  const validatorLogHashes = input.stages.flatMap((stage) =>
    stage.artifacts.map((artifact) => artifact.validatorLogSha256),
  );
  if (
    new Set(executionLogHashes).size !== executionLogHashes.length ||
    new Set(validatorLogHashes).size !== validatorLogHashes.length
  ) {
    add("OFFICE_SCHEMA_EVIDENCE_INVALID");
  }

  const rows: OfficeSchemaMatrixRow[] = [];
  const stageResults: OfficeSchemaStageQaResult[] = [];
  for (const [key, requirement] of requirements) {
    const stage = observed.get(key);
    if (!stage) {
      add("OFFICE_SCHEMA_REQUIRED_STAGE_MISSING");
      stageResults.push(
        Object.freeze({
          stage: requirement.stage,
          targetFormat: requirement.targetFormat,
          validatorName: null,
          validatorVersion: null,
          executionLogSha256: null,
          requiredArtifactIds: uniqueSorted(requirement.artifactIds),
          observedArtifactIds: [],
          artifactEvidence: [],
          openedArtifactCount: 0,
          diagnosticCount: 0,
          errorCount: 0,
          warningCount: 0,
          reviewedNonBlockingWarningCount: 0,
          externalToolPendingWordErrorCount: 0,
          status: "failed" as const,
        }),
      );
      continue;
    }

    const byArtifact = new Map<string, OfficeSchemaArtifactEvidence>();
    for (const artifact of stage.artifacts) {
      if (
        byArtifact.has(artifact.artifactId) ||
        !validIdentifier(artifact.artifactId) ||
        !validEvidenceSha256(artifact.artifactSha256) ||
        !validEvidenceSha256(artifact.validatorLogSha256) ||
        !Number.isSafeInteger(artifact.reportedDiagnosticCount) ||
        artifact.reportedDiagnosticCount < 0
      ) {
        add("OFFICE_SCHEMA_EVIDENCE_INVALID");
        continue;
      }
      byArtifact.set(artifact.artifactId, artifact);
    }

    let stageFailed = false;
    if (
      byArtifact.size !== requirement.artifactIds.length ||
      [...byArtifact.keys()].some(
        (artifactId) => !requirement.artifactIds.includes(artifactId),
      )
    ) {
      add("OFFICE_SCHEMA_EVIDENCE_INVALID");
      stageFailed = true;
    }
    for (const artifactId of requirement.artifactIds) {
      if (!byArtifact.has(artifactId)) {
        add("OFFICE_SCHEMA_REQUIRED_ARTIFACT_MISSING");
        stageFailed = true;
      }
    }
    let openedArtifactCount = 0;
    let errorCount = 0;
    let warningCount = 0;
    let reviewedNonBlockingWarningCount = 0;
    let externalToolPendingWordErrorCount = 0;
    for (const artifact of byArtifact.values()) {
      if (artifact.opened) openedArtifactCount += 1;
      else {
        add("OFFICE_SCHEMA_ARTIFACT_OPEN_FAILED");
        stageFailed = true;
      }
      if (artifact.reportedDiagnosticCount !== artifact.diagnostics.length) {
        add("OFFICE_SCHEMA_DIAGNOSTIC_COUNT_MISMATCH");
        stageFailed = true;
      }
      artifact.diagnostics.forEach((diagnostic, diagnosticIndex) => {
        if (!validDiagnostic(diagnostic)) {
          add("OFFICE_SCHEMA_EVIDENCE_INVALID");
          stageFailed = true;
        }
        const classified = Boolean(
          diagnostic.familyCode &&
          diagnostic.disposition &&
          diagnostic.classificationRationaleSha256,
        );
        if (!classified) {
          add("OFFICE_SCHEMA_DIAGNOSTIC_UNCLASSIFIED");
          stageFailed = true;
        }
        if (diagnostic.severity === "error") {
          errorCount += 1;
          const externalToolPendingWord = Boolean(
            classified && matchesReviewedLibreOfficeRegistry(stage, diagnostic),
          );
          if (externalToolPendingWord) {
            externalToolPendingWordErrorCount += 1;
          } else {
            if (diagnostic.disposition === "external_tool_pending_word") {
              add("OFFICE_SCHEMA_EXTERNAL_CLASSIFICATION_NOT_REVIEWED");
            }
            add("OFFICE_SCHEMA_ERROR_PRESENT");
            stageFailed = true;
          }
        } else {
          warningCount += 1;
          if (
            diagnostic.disposition === "reviewed_non_blocking" &&
            classified
          ) {
            reviewedNonBlockingWarningCount += 1;
          } else {
            add("OFFICE_SCHEMA_BLOCKING_WARNING");
            stageFailed = true;
          }
        }
        rows.push(matrixRow(stage, artifact, diagnostic, diagnosticIndex));
      });
    }
    stageResults.push(
      Object.freeze({
        stage: requirement.stage,
        targetFormat: requirement.targetFormat,
        validatorName: stage.validatorName,
        validatorVersion: stage.validatorVersion,
        executionLogSha256: stage.executionLogSha256,
        requiredArtifactIds: uniqueSorted(requirement.artifactIds),
        observedArtifactIds: uniqueSorted([...byArtifact.keys()]),
        artifactEvidence: Object.freeze(
          [...byArtifact.values()]
            .map((artifact) =>
              Object.freeze({
                artifactId: artifact.artifactId,
                artifactSha256: artifact.artifactSha256,
                validatorLogSha256: artifact.validatorLogSha256,
                opened: artifact.opened,
              }),
            )
            .sort((left, right) =>
              left.artifactId.localeCompare(right.artifactId),
            ),
        ),
        openedArtifactCount,
        diagnosticCount: [...byArtifact.values()].reduce(
          (sum, artifact) => sum + artifact.diagnostics.length,
          0,
        ),
        errorCount,
        warningCount,
        reviewedNonBlockingWarningCount,
        externalToolPendingWordErrorCount,
        status: stageFailed
          ? ("failed" as const)
          : externalToolPendingWordErrorCount > 0
            ? ("external_tool_pending_word" as const)
            : ("passed" as const),
      }),
    );
  }

  rows.sort(
    (left, right) =>
      left.stage.localeCompare(right.stage) ||
      left.targetFormat.localeCompare(right.targetFormat) ||
      left.artifactId.localeCompare(right.artifactId) ||
      left.diagnosticIndex - right.diagnosticIndex,
  );
  stageResults.sort(
    (left, right) =>
      left.stage.localeCompare(right.stage) ||
      left.targetFormat.localeCompare(right.targetFormat),
  );
  const blockerCodes = uniqueSorted(blockers);
  const allRequiredStagesObserved = stageResults.length === requirements.size;
  const compatibilityEngineeringEligible = Boolean(
    blockerCodes.length === 0 &&
    allRequiredStagesObserved &&
    stageResults.every(
      (stage) =>
        stage.status === "passed" ||
        stage.status === "external_tool_pending_word",
    ),
  );
  const status = !compatibilityEngineeringEligible
    ? ("failed" as const)
    : stageResults.some(
          (stage) => stage.status === "external_tool_pending_word",
        )
      ? ("external_tool_pending_word" as const)
      : ("passed" as const);
  const reviewerProvenanceSha256 = canonicalSha256(reviewer ?? null);
  const resultWithoutEvidenceHash = {
    evidenceClass: OFFICE_QA_EVIDENCE_CLASS,
    contractVersion: OFFICE_SCHEMA_QA_CONTRACT_VERSION,
    qaOnly: true as const,
    signingEligible: false as const,
    productionStateTransitionEligible: false as const,
    status,
    compatibilityEngineeringEligible,
    desktopWordApprovalRequired: true as const,
    blockerCodes: Object.freeze(blockerCodes),
    stages: Object.freeze(stageResults),
    matrix: Object.freeze(rows),
    matrixSha256: canonicalSha256(rows),
    reviewerProvenanceSha256,
  };
  return Object.freeze({
    ...resultWithoutEvidenceHash,
    evidenceSha256: canonicalSha256(resultWithoutEvidenceHash),
  });
}
