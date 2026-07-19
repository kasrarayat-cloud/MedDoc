import { createHash } from "node:crypto";

import { canonicalSha256 } from "../template-twin/canonical";
import {
  OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION,
  POST_LIBREOFFICE_ARTIFACTS,
  POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS,
  POST_LIBREOFFICE_EXPECTED_TARGET_OBSERVATIONS,
  POST_LIBREOFFICE_OBSERVATION_PROVENANCE,
  POST_LIBREOFFICE_OBSERVATION_PROVENANCE_SHA256,
  POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
  POST_LIBREOFFICE_REVIEWED_FINDINGS,
  POST_LIBREOFFICE_SCHEMA_CONTRACT_VERSION,
  POST_LIBREOFFICE_TARGETS,
  reviewedFindingsForArtifact,
  reviewedLibreOfficeSignatureKey,
  type ReviewedLibreOfficePhysicalFinding,
} from "./office-libreoffice-reviewed-registry";

export const POST_LIBREOFFICE_VALIDATOR_NAME =
  "DocumentFormat.OpenXml.OpenXmlValidator" as const;
export const POST_LIBREOFFICE_VALIDATOR_SDK_VERSION = "3.5.1.0" as const;
export const POST_LIBREOFFICE_VALIDATOR_PACKAGE_VERSION =
  "3.5.1+Branch.main.Sha.3139fdfd27414548a41555f7848d5728f6e71a42.3139fdfd27414548a41555f7848d5728f6e71a42" as const;
export const POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256 =
  "0c936ff95c6562bfeac91a8e57ad2484457a823739c8aa2f4a0d9703f5a8386a" as const;
export const POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256 =
  "b30baf3df3d42ca524b684a8caaa89e08c3bc95836faee44cf476cc1e405d28f" as const;

const SHA256 = /^[a-f0-9]{64}$/u;
const SOURCE_COMMIT = /^[a-f0-9]{40}$/u;

interface RawOpenXmlError {
  readonly id?: unknown;
  readonly type?: unknown;
  readonly description?: unknown;
  readonly part?: unknown;
  readonly path?: unknown;
}

interface RawOpenXmlResult {
  readonly file?: unknown;
  readonly sha256?: unknown;
  readonly sizeBytes?: unknown;
  readonly opened?: unknown;
  readonly valid?: unknown;
  readonly errorCount?: unknown;
  readonly errors?: unknown;
}

interface RawOpenXmlReport {
  readonly tool?: unknown;
  readonly sdkVersion?: unknown;
  readonly packageVersion?: unknown;
  readonly validatorExecutableSha256?: unknown;
  readonly targetFileFormat?: unknown;
  readonly sourceCommit?: unknown;
  readonly generatedAt?: unknown;
  readonly results?: unknown;
}

export interface PostLibreOfficeRawReportInput {
  readonly relativePath: string;
  readonly bytes: Uint8Array;
}

export interface PostLibreOfficeSavedArtifactInput {
  readonly caseId: string;
  readonly filename: string;
  readonly sha256: string;
  readonly sizeBytes: number;
}

export interface BuildPostLibreOfficeEvidenceInput {
  readonly sourceCommit: string;
  readonly generatedAtIso: string;
  readonly validatorExecutableSha256: string;
  readonly windowsValidatorExecutableSha256: string;
  readonly libreOfficeResults: {
    readonly relativePath: "libreoffice-results.json";
    readonly bytes: Uint8Array;
  };
  readonly rawReports: readonly PostLibreOfficeRawReportInput[];
  readonly savedArtifacts: readonly PostLibreOfficeSavedArtifactInput[];
}

export interface PostLibreOfficeEvidenceManifest {
  readonly contractVersion: typeof POST_LIBREOFFICE_SCHEMA_CONTRACT_VERSION;
  readonly sourceCommit: string;
  readonly generatedAtIso: string;
  readonly syntheticOnly: true;
  readonly evidenceClass: "QA_ONLY_OFFICE_COMPATIBILITY_EVIDENCE";
  readonly schemaStatus: "external_tool_pending_word";
  readonly schemaValid: false;
  readonly signingEligible: false;
  readonly reimportEligible: false;
  readonly productionStateTransitionEligible: false;
  readonly compatibilityEngineeringStatus: "PENDING_INDEPENDENT_EXACT_HEAD_REVIEW";
  readonly compatibilityEngineeringEligible: false;
  readonly syntheticReviewerPackageGenerationEligible: true;
  readonly desktopWordApprovalRequired: true;
  readonly validator: {
    readonly name: typeof POST_LIBREOFFICE_VALIDATOR_NAME;
    readonly sdkVersion: typeof POST_LIBREOFFICE_VALIDATOR_SDK_VERSION;
    readonly packageVersion: typeof POST_LIBREOFFICE_VALIDATOR_PACKAGE_VERSION;
    readonly executedLinuxExecutableSha256: string;
    readonly packagedWindowsExecutableSha256: string;
    readonly networkMode: "none";
    readonly targets: typeof POST_LIBREOFFICE_TARGETS;
  };
  readonly reviewProvenance: {
    readonly registryVersion: typeof OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION;
    readonly observationRegistrySha256: string;
    readonly observationProvenanceSha256: string;
    readonly observedSourceCommit: string;
    readonly approvalEffect: "none";
    readonly independentReviewStatus: "PENDING";
    readonly acceptedIndependentReviewRecordSha256: null;
  };
  readonly reviewAdvancement: {
    readonly contractVersion: "template-twin-independent-review-binding/1.0.0";
    readonly bindingMode: "separate_additive_review_record";
    readonly implementationAuthorMayApprove: false;
    readonly acceptedRecordMustBind: readonly [
      "reviewedSourceCommit",
      "observationRegistrySha256",
      "canonicalEvidenceSha256",
      "rawReportSha256s",
      "verdict",
      "reviewerIdentityAndRole",
    ];
    readonly freshIndependentExactHeadReviewAfterBindingRequired: true;
  };
  readonly libreOfficeEvidence: {
    readonly relativePath: "libreoffice-results.json";
    readonly sha256: string;
    readonly sizeBytes: number;
    readonly image: string;
    readonly overallStatus: "passed";
    readonly microsoftWordStatus: "PENDING";
  };
  readonly totals: {
    readonly savedArtifacts: 5;
    readonly physicalFindings: 32;
    readonly targetObservations: 64;
    readonly unclassifiedFindings: 0;
    readonly blockingUnknownFindings: 0;
  };
  readonly classificationSummary: Readonly<
    Record<
      | "FONT_CHARACTER_SET_EXTENSION"
      | "LOGICAL_ALIGNMENT_ENUM"
      | "TABLE_ROW_ON_OFF_LEXICAL_VALUE"
      | "LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW",
      number
    >
  >;
  readonly rawReports: readonly {
    readonly targetFileFormat: (typeof POST_LIBREOFFICE_TARGETS)[number];
    readonly relativePath: string;
    readonly sha256: string;
    readonly sizeBytes: number;
    readonly resultCount: 5;
    readonly errorCount: 32;
  }[];
  readonly savedArtifacts: readonly {
    readonly caseId: string;
    readonly filename: string;
    readonly sha256: string;
    readonly sizeBytes: number;
    readonly physicalFindingCount: number;
    readonly observedTargets: typeof POST_LIBREOFFICE_TARGETS;
  }[];
  readonly findings: readonly {
    readonly findingId: string;
    readonly caseId: string;
    readonly artifactFilename: string;
    readonly familyCode: ReviewedLibreOfficePhysicalFinding["familyCode"];
    readonly validatorErrorId: "Sch_AttributeValueDataTypeDetailed";
    readonly errorType: "Schema";
    readonly description: string;
    readonly descriptionSha256: string;
    readonly classificationRationale: string;
    readonly classificationRationaleSha256: string;
    readonly partName: string;
    readonly path: string;
    readonly pathSha256: string;
    readonly elementQName: string;
    readonly attributeQName: string;
    readonly observedValue: string;
    readonly disposition: "external_tool_pending_word";
    readonly schemaValid: false;
    readonly signingEligible: false;
    readonly reimportEligible: false;
    readonly targetObservations: readonly {
      readonly targetFileFormat: (typeof POST_LIBREOFFICE_TARGETS)[number];
      readonly rawReportSha256: string;
    }[];
  }[];
  readonly artifactSetSha256: string;
  readonly findingSetSha256: string;
  readonly evidenceSha256: string;
}

function invariant(condition: unknown, code: string): asserts condition {
  if (!condition) throw new Error(code);
}

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function parseJson(bytes: Uint8Array, code: string): unknown {
  try {
    return JSON.parse(Buffer.from(bytes).toString("utf8"));
  } catch (error) {
    throw new Error(code, { cause: error });
  }
}

function safeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}

function exactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const observed = Object.keys(value).sort();
  return (
    observed.length === expected.length &&
    observed.every((key, index) => key === [...expected].sort()[index])
  );
}

function rawSignatureKey(error: RawOpenXmlError): string {
  return reviewedLibreOfficeSignatureKey({
    validatorErrorId: String(error.id),
    errorType: String(error.type),
    description: String(error.description),
    partName: String(error.part),
    path: String(error.path),
  });
}

function validateError(
  error: unknown,
  expectedByKey: Map<string, ReviewedLibreOfficePhysicalFinding>,
): ReviewedLibreOfficePhysicalFinding {
  invariant(
    error !== null && typeof error === "object" && !Array.isArray(error),
    "POST_LIBREOFFICE_DIAGNOSTIC_INVALID",
  );
  const record = error as RawOpenXmlError & Record<string, unknown>;
  invariant(
    exactKeys(record, ["description", "id", "part", "path", "type"]),
    "POST_LIBREOFFICE_DIAGNOSTIC_UNKNOWN_FIELD",
  );
  invariant(
    [
      record.id,
      record.type,
      record.description,
      record.part,
      record.path,
    ].every((value) => typeof value === "string" && value.length > 0),
    "POST_LIBREOFFICE_DIAGNOSTIC_INVALID",
  );
  const key = rawSignatureKey(record);
  const expected = expectedByKey.get(key);
  invariant(expected, "POST_LIBREOFFICE_DIAGNOSTIC_UNREVIEWED");
  expectedByKey.delete(key);
  return expected;
}

function validateResult(
  result: unknown,
  expectedArtifact: (typeof POST_LIBREOFFICE_ARTIFACTS)[number],
  observedArtifact: PostLibreOfficeSavedArtifactInput,
): readonly ReviewedLibreOfficePhysicalFinding[] {
  invariant(
    result !== null && typeof result === "object" && !Array.isArray(result),
    "POST_LIBREOFFICE_RESULT_INVALID",
  );
  const record = result as RawOpenXmlResult & Record<string, unknown>;
  invariant(
    exactKeys(record, [
      "errorCount",
      "errors",
      "file",
      "opened",
      "sha256",
      "sizeBytes",
      "valid",
    ]),
    "POST_LIBREOFFICE_RESULT_UNKNOWN_FIELD",
  );
  invariant(
    record.file === expectedArtifact.filename,
    "POST_LIBREOFFICE_ARTIFACT_FILENAME_DRIFT",
  );
  invariant(
    record.sha256 === observedArtifact.sha256 &&
      record.sizeBytes === observedArtifact.sizeBytes,
    "POST_LIBREOFFICE_ARTIFACT_IDENTITY_DRIFT",
  );
  invariant(
    record.opened === true && record.valid === false,
    "POST_LIBREOFFICE_SCHEMA_STATE_DRIFT",
  );
  invariant(
    safeInteger(record.errorCount) && Array.isArray(record.errors),
    "POST_LIBREOFFICE_DIAGNOSTIC_COUNT_INVALID",
  );
  const expectedFindings = reviewedFindingsForArtifact(
    expectedArtifact.filename,
  );
  invariant(
    record.errorCount === expectedFindings.length &&
      record.errors.length === expectedFindings.length,
    "POST_LIBREOFFICE_DIAGNOSTIC_COUNT_DRIFT",
  );
  const expectedByKey = new Map(
    expectedFindings.map((finding) => [
      reviewedLibreOfficeSignatureKey(finding),
      finding,
    ]),
  );
  const observed = record.errors.map((error) =>
    validateError(error, expectedByKey),
  );
  invariant(expectedByKey.size === 0, "POST_LIBREOFFICE_DIAGNOSTIC_MISSING");
  return observed;
}

function classificationSummary(): PostLibreOfficeEvidenceManifest["classificationSummary"] {
  const counts = {
    FONT_CHARACTER_SET_EXTENSION: 0,
    LOGICAL_ALIGNMENT_ENUM: 0,
    TABLE_ROW_ON_OFF_LEXICAL_VALUE: 0,
    LIBREOFFICE_DOCGRID_CHARSPACE_UINT32_OVERFLOW: 0,
  };
  for (const finding of POST_LIBREOFFICE_REVIEWED_FINDINGS) {
    counts[finding.familyCode] += 1;
  }
  return Object.freeze(counts);
}

export function buildPostLibreOfficeEvidenceManifest(
  input: BuildPostLibreOfficeEvidenceInput,
): PostLibreOfficeEvidenceManifest {
  invariant(
    SOURCE_COMMIT.test(input.sourceCommit),
    "POST_LIBREOFFICE_SOURCE_COMMIT_INVALID",
  );
  invariant(
    typeof input.generatedAtIso === "string" &&
      !Number.isNaN(Date.parse(input.generatedAtIso)),
    "POST_LIBREOFFICE_GENERATED_AT_INVALID",
  );
  invariant(
    input.validatorExecutableSha256 ===
      POST_LIBREOFFICE_VALIDATOR_EXECUTABLE_SHA256 &&
      input.windowsValidatorExecutableSha256 ===
        POST_LIBREOFFICE_WINDOWS_VALIDATOR_EXECUTABLE_SHA256,
    "POST_LIBREOFFICE_VALIDATOR_IDENTITY_DRIFT",
  );

  invariant(
    input.savedArtifacts.length === POST_LIBREOFFICE_ARTIFACTS.length,
    "POST_LIBREOFFICE_ARTIFACT_COUNT_DRIFT",
  );
  const savedByCase = new Map(
    input.savedArtifacts.map((artifact) => [artifact.caseId, artifact]),
  );
  invariant(
    savedByCase.size === input.savedArtifacts.length,
    "POST_LIBREOFFICE_ARTIFACT_DUPLICATE",
  );
  for (const expected of POST_LIBREOFFICE_ARTIFACTS) {
    const observed = savedByCase.get(expected.caseId);
    invariant(observed, "POST_LIBREOFFICE_ARTIFACT_MISSING");
    invariant(
      observed.filename === expected.filename &&
        SHA256.test(observed.sha256) &&
        !/^0{64}$/u.test(observed.sha256) &&
        Number.isSafeInteger(observed.sizeBytes) &&
        observed.sizeBytes > 0,
      "POST_LIBREOFFICE_ARTIFACT_IDENTITY_DRIFT",
    );
  }
  invariant(
    [...savedByCase.keys()].every((caseId) =>
      POST_LIBREOFFICE_ARTIFACTS.some((expected) => expected.caseId === caseId),
    ),
    "POST_LIBREOFFICE_ARTIFACT_UNKNOWN",
  );

  invariant(
    input.libreOfficeResults.relativePath === "libreoffice-results.json",
    "POST_LIBREOFFICE_LIBREOFFICE_PATH_DRIFT",
  );
  const parsedLibreOffice = parseJson(
    input.libreOfficeResults.bytes,
    "POST_LIBREOFFICE_LIBREOFFICE_JSON_INVALID",
  ) as {
    contractVersion?: unknown;
    sourceCommit?: unknown;
    generatedAtIso?: unknown;
    syntheticOnly?: unknown;
    image?: unknown;
    results?: unknown;
    overallStatus?: unknown;
    microsoftWordStatus?: unknown;
  };
  invariant(
    parsedLibreOffice !== null &&
      typeof parsedLibreOffice === "object" &&
      parsedLibreOffice.contractVersion ===
        "template-twin-human-gate-libreoffice-evidence/1.0.0" &&
      parsedLibreOffice.sourceCommit === input.sourceCommit &&
      parsedLibreOffice.generatedAtIso === input.generatedAtIso &&
      parsedLibreOffice.syntheticOnly === true &&
      parsedLibreOffice.image ===
        "lscr.io/linuxserver/libreoffice@sha256:92b7de866a39764dc51040918885cb9178f1ec3ff11d8336621ddf2239dfcfe4" &&
      parsedLibreOffice.overallStatus === "passed" &&
      parsedLibreOffice.microsoftWordStatus === "PENDING" &&
      Array.isArray(parsedLibreOffice.results) &&
      parsedLibreOffice.results.length === POST_LIBREOFFICE_ARTIFACTS.length,
    "POST_LIBREOFFICE_LIBREOFFICE_PROVENANCE_DRIFT",
  );
  const libreOfficeByCase = new Map(
    (
      parsedLibreOffice.results as Array<{
        id?: unknown;
        sourceCommit?: unknown;
        libreOfficeSaved?: { sha256?: unknown; sizeBytes?: unknown };
        semanticSurvival?: unknown;
        staticComparison?: { aggregateVisibleContentMatches?: unknown };
        security?: { status?: unknown };
        visual?: { status?: unknown };
      }>
    ).map((result) => [String(result.id), result]),
  );
  invariant(
    libreOfficeByCase.size === POST_LIBREOFFICE_ARTIFACTS.length,
    "POST_LIBREOFFICE_LIBREOFFICE_RESULT_SET_DRIFT",
  );
  for (const expected of POST_LIBREOFFICE_ARTIFACTS) {
    const observedArtifact = savedByCase.get(expected.caseId)!;
    const result = libreOfficeByCase.get(expected.caseId);
    invariant(
      result &&
        result.sourceCommit === input.sourceCommit &&
        result.libreOfficeSaved?.sha256 === observedArtifact.sha256 &&
        result.libreOfficeSaved.sizeBytes === observedArtifact.sizeBytes &&
        result.semanticSurvival === true &&
        result.staticComparison?.aggregateVisibleContentMatches === true &&
        result.security?.status === "passed" &&
        result.visual?.status === "passed",
      "POST_LIBREOFFICE_LIBREOFFICE_RESULT_DRIFT",
    );
  }
  invariant(
    [...libreOfficeByCase.keys()].every((caseId) =>
      POST_LIBREOFFICE_ARTIFACTS.some((artifact) => artifact.caseId === caseId),
    ),
    "POST_LIBREOFFICE_LIBREOFFICE_RESULT_SET_DRIFT",
  );

  invariant(
    input.rawReports.length === POST_LIBREOFFICE_TARGETS.length,
    "POST_LIBREOFFICE_REPORT_COUNT_DRIFT",
  );
  const reportEvidence = new Map<
    (typeof POST_LIBREOFFICE_TARGETS)[number],
    {
      readonly targetFileFormat: (typeof POST_LIBREOFFICE_TARGETS)[number];
      readonly relativePath: string;
      readonly sha256: string;
      readonly sizeBytes: number;
      readonly resultCount: 5;
      readonly errorCount: 32;
    }
  >();
  const observationKeysByTarget = new Map<string, string[]>();
  for (const rawReport of input.rawReports) {
    invariant(
      /^post-libreoffice-(?:Office2013|Microsoft365)\.json$/u.test(
        rawReport.relativePath,
      ),
      "POST_LIBREOFFICE_REPORT_PATH_DRIFT",
    );
    const parsed = parseJson(
      rawReport.bytes,
      "POST_LIBREOFFICE_REPORT_JSON_INVALID",
    );
    invariant(
      parsed !== null && typeof parsed === "object" && !Array.isArray(parsed),
      "POST_LIBREOFFICE_REPORT_INVALID",
    );
    const report = parsed as RawOpenXmlReport & Record<string, unknown>;
    invariant(
      exactKeys(report, [
        "generatedAt",
        "packageVersion",
        "results",
        "sdkVersion",
        "sourceCommit",
        "targetFileFormat",
        "tool",
        "validatorExecutableSha256",
      ]),
      "POST_LIBREOFFICE_REPORT_UNKNOWN_FIELD",
    );
    invariant(
      POST_LIBREOFFICE_TARGETS.includes(
        report.targetFileFormat as (typeof POST_LIBREOFFICE_TARGETS)[number],
      ),
      "POST_LIBREOFFICE_TARGET_UNKNOWN",
    );
    const target =
      report.targetFileFormat as (typeof POST_LIBREOFFICE_TARGETS)[number];
    invariant(
      rawReport.relativePath === `post-libreoffice-${target}.json`,
      "POST_LIBREOFFICE_REPORT_PATH_DRIFT",
    );
    invariant(!reportEvidence.has(target), "POST_LIBREOFFICE_TARGET_DUPLICATE");
    invariant(
      report.tool === POST_LIBREOFFICE_VALIDATOR_NAME &&
        report.sdkVersion === POST_LIBREOFFICE_VALIDATOR_SDK_VERSION &&
        report.packageVersion === POST_LIBREOFFICE_VALIDATOR_PACKAGE_VERSION &&
        report.validatorExecutableSha256 === input.validatorExecutableSha256,
      "POST_LIBREOFFICE_VALIDATOR_IDENTITY_DRIFT",
    );
    invariant(
      report.sourceCommit === input.sourceCommit &&
        report.generatedAt === input.generatedAtIso,
      "POST_LIBREOFFICE_REPORT_PROVENANCE_DRIFT",
    );
    invariant(
      Array.isArray(report.results) &&
        report.results.length === POST_LIBREOFFICE_ARTIFACTS.length,
      "POST_LIBREOFFICE_RESULT_COUNT_DRIFT",
    );
    const resultByFile = new Map(
      (report.results as RawOpenXmlResult[]).map((result) => [
        String(result.file),
        result,
      ]),
    );
    invariant(
      resultByFile.size === report.results.length,
      "POST_LIBREOFFICE_ARTIFACT_DUPLICATE",
    );
    const observationKeys: string[] = [];
    for (const expectedArtifact of POST_LIBREOFFICE_ARTIFACTS) {
      const result = resultByFile.get(expectedArtifact.filename);
      invariant(result, "POST_LIBREOFFICE_ARTIFACT_MISSING");
      const findings = validateResult(
        result,
        expectedArtifact,
        savedByCase.get(expectedArtifact.caseId)!,
      );
      observationKeys.push(
        ...findings.map((finding) =>
          canonicalSha256({
            artifactFilename: expectedArtifact.filename,
            signature: reviewedLibreOfficeSignatureKey(finding),
          }),
        ),
      );
    }
    invariant(
      [...resultByFile.keys()].every((filename) =>
        POST_LIBREOFFICE_ARTIFACTS.some(
          (artifact) => artifact.filename === filename,
        ),
      ),
      "POST_LIBREOFFICE_ARTIFACT_UNKNOWN",
    );
    invariant(
      observationKeys.length === POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS,
      "POST_LIBREOFFICE_DIAGNOSTIC_COUNT_DRIFT",
    );
    observationKeysByTarget.set(target, observationKeys.sort());
    reportEvidence.set(target, {
      targetFileFormat: target,
      relativePath: rawReport.relativePath,
      sha256: sha256(rawReport.bytes),
      sizeBytes: rawReport.bytes.byteLength,
      resultCount: 5,
      errorCount: 32,
    });
  }
  invariant(
    POST_LIBREOFFICE_TARGETS.every((target) => reportEvidence.has(target)),
    "POST_LIBREOFFICE_TARGET_MISSING",
  );
  const office2013Keys = observationKeysByTarget.get("Office2013");
  const microsoft365Keys = observationKeysByTarget.get("Microsoft365");
  invariant(
    office2013Keys &&
      microsoft365Keys &&
      JSON.stringify(office2013Keys) === JSON.stringify(microsoft365Keys),
    "POST_LIBREOFFICE_TARGET_OBSERVATION_DRIFT",
  );

  const rawReports = Object.freeze(
    POST_LIBREOFFICE_TARGETS.map((target) => reportEvidence.get(target)!),
  );
  const savedArtifacts = Object.freeze(
    POST_LIBREOFFICE_ARTIFACTS.map((artifact) =>
      Object.freeze({
        ...savedByCase.get(artifact.caseId)!,
        physicalFindingCount: reviewedFindingsForArtifact(artifact.filename)
          .length,
        observedTargets: POST_LIBREOFFICE_TARGETS,
      }),
    ),
  );
  const findings = Object.freeze(
    POST_LIBREOFFICE_REVIEWED_FINDINGS.map((finding) =>
      Object.freeze({
        ...finding,
        disposition: "external_tool_pending_word" as const,
        schemaValid: false as const,
        signingEligible: false as const,
        reimportEligible: false as const,
        targetObservations: Object.freeze(
          POST_LIBREOFFICE_TARGETS.map((target) =>
            Object.freeze({
              targetFileFormat: target,
              rawReportSha256: reportEvidence.get(target)!.sha256,
            }),
          ),
        ),
      }),
    ),
  );
  const unsigned = {
    contractVersion: POST_LIBREOFFICE_SCHEMA_CONTRACT_VERSION,
    sourceCommit: input.sourceCommit,
    generatedAtIso: input.generatedAtIso,
    syntheticOnly: true as const,
    evidenceClass: "QA_ONLY_OFFICE_COMPATIBILITY_EVIDENCE" as const,
    schemaStatus: "external_tool_pending_word" as const,
    schemaValid: false as const,
    signingEligible: false as const,
    reimportEligible: false as const,
    productionStateTransitionEligible: false as const,
    compatibilityEngineeringStatus:
      POST_LIBREOFFICE_OBSERVATION_PROVENANCE.compatibilityEngineeringStatus,
    compatibilityEngineeringEligible:
      POST_LIBREOFFICE_OBSERVATION_PROVENANCE.compatibilityEngineeringEligible,
    syntheticReviewerPackageGenerationEligible:
      POST_LIBREOFFICE_OBSERVATION_PROVENANCE.syntheticReviewerPackageGenerationEligible,
    desktopWordApprovalRequired: true as const,
    validator: Object.freeze({
      name: POST_LIBREOFFICE_VALIDATOR_NAME,
      sdkVersion: POST_LIBREOFFICE_VALIDATOR_SDK_VERSION,
      packageVersion: POST_LIBREOFFICE_VALIDATOR_PACKAGE_VERSION,
      executedLinuxExecutableSha256: input.validatorExecutableSha256,
      packagedWindowsExecutableSha256: input.windowsValidatorExecutableSha256,
      networkMode: "none" as const,
      targets: POST_LIBREOFFICE_TARGETS,
    }),
    reviewProvenance: Object.freeze({
      registryVersion: OFFICE_SCHEMA_REVIEW_REGISTRY_VERSION,
      observationRegistrySha256: POST_LIBREOFFICE_OBSERVATION_REGISTRY_SHA256,
      observationProvenanceSha256:
        POST_LIBREOFFICE_OBSERVATION_PROVENANCE_SHA256,
      observedSourceCommit:
        POST_LIBREOFFICE_OBSERVATION_PROVENANCE.observedSourceCommit,
      approvalEffect: POST_LIBREOFFICE_OBSERVATION_PROVENANCE.approvalEffect,
      independentReviewStatus:
        POST_LIBREOFFICE_OBSERVATION_PROVENANCE.independentReviewStatus,
      acceptedIndependentReviewRecordSha256:
        POST_LIBREOFFICE_OBSERVATION_PROVENANCE.acceptedIndependentReviewRecordSha256,
    }),
    reviewAdvancement: Object.freeze({
      contractVersion:
        "template-twin-independent-review-binding/1.0.0" as const,
      bindingMode: "separate_additive_review_record" as const,
      implementationAuthorMayApprove: false as const,
      acceptedRecordMustBind: Object.freeze([
        "reviewedSourceCommit",
        "observationRegistrySha256",
        "canonicalEvidenceSha256",
        "rawReportSha256s",
        "verdict",
        "reviewerIdentityAndRole",
      ] as const),
      freshIndependentExactHeadReviewAfterBindingRequired: true as const,
    }),
    libreOfficeEvidence: Object.freeze({
      relativePath: "libreoffice-results.json" as const,
      sha256: sha256(input.libreOfficeResults.bytes),
      sizeBytes: input.libreOfficeResults.bytes.byteLength,
      image:
        "lscr.io/linuxserver/libreoffice@sha256:92b7de866a39764dc51040918885cb9178f1ec3ff11d8336621ddf2239dfcfe4",
      overallStatus: "passed" as const,
      microsoftWordStatus: "PENDING" as const,
    }),
    totals: Object.freeze({
      savedArtifacts: 5 as const,
      physicalFindings: 32 as const,
      targetObservations: 64 as const,
      unclassifiedFindings: 0 as const,
      blockingUnknownFindings: 0 as const,
    }),
    classificationSummary: classificationSummary(),
    rawReports,
    savedArtifacts,
    findings,
    artifactSetSha256: canonicalSha256(savedArtifacts),
    findingSetSha256: canonicalSha256(findings),
  };
  invariant(
    findings.length === POST_LIBREOFFICE_EXPECTED_PHYSICAL_FINDINGS &&
      findings.reduce(
        (count, finding) => count + finding.targetObservations.length,
        0,
      ) === POST_LIBREOFFICE_EXPECTED_TARGET_OBSERVATIONS,
    "POST_LIBREOFFICE_MANIFEST_COUNT_DRIFT",
  );
  return Object.freeze({
    ...unsigned,
    evidenceSha256: canonicalSha256(unsigned),
  });
}

export function assertPostLibreOfficeEvidenceManifest(
  observed: unknown,
  expected: PostLibreOfficeEvidenceManifest,
): asserts observed is PostLibreOfficeEvidenceManifest {
  invariant(
    observed !== null &&
      typeof observed === "object" &&
      !Array.isArray(observed),
    "POST_LIBREOFFICE_CANONICAL_MANIFEST_INVALID",
  );
  invariant(
    canonicalSha256(observed) === canonicalSha256(expected),
    "POST_LIBREOFFICE_CANONICAL_MANIFEST_DRIFT",
  );
  invariant(
    (observed as { evidenceSha256?: unknown }).evidenceSha256 ===
      expected.evidenceSha256 && SHA256.test(expected.evidenceSha256),
    "POST_LIBREOFFICE_CANONICAL_MANIFEST_HASH_DRIFT",
  );
}
