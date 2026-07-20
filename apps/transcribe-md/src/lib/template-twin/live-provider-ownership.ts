import { canonicalSha256 } from "./canonical";

const SHA256 = /^[a-f0-9]{64}$/u;
const GENERATION = /^(?:0|[1-9][0-9]*)$/u;
const OPERATION_INSTANCE = /^[a-z0-9][a-z0-9._:-]{0,119}$/u;
const MAX_RECEIPT_BYTES = 131_072;
const EXPECTED_SOURCE_PLAN = [
  {
    operation: "SOURCE_PHI_SCAN",
    operationInstance: "primary",
    disposition: "EXECUTED",
    reasonCode: null,
  },
  {
    operation: "SOURCE_SEMANTIC_MAPPING",
    operationInstance: "primary",
    disposition: "EXECUTED",
    reasonCode: null,
  },
] as const;
const RECEIPT_KEYS = [
  "contractVersion",
  "scope",
  "practiceId",
  "actorUserId",
  "subjectId",
  "subjectSha256",
  "visitId",
  "sourceArtifactId",
  "compiledVersionId",
  "noteTemplateId",
  "noteTemplateVersion",
  "visitInputMode",
  "logicalAttempt",
  "sourceLineageId",
  "sourceLineageVersion",
  "sourceSha256",
  "providerMode",
  "pinnedGlobalRolloutGeneration",
  "pinnedPracticeRolloutGeneration",
  "releaseId",
  "releaseIdentitySha256",
  "runtimeManifestSha256",
  "runtimeInstanceId",
  "runtimeIdentitySha256",
  "syntheticAdmissionId",
  "executionPlanSha256",
  "executionPlan",
  "executions",
] as const;
const PLAN_KEYS = [
  "operation",
  "operationInstance",
  "disposition",
  "reasonCode",
] as const;
const EXECUTION_KEYS = [
  "executionId",
  "operation",
  "operationInstance",
  "resultSha256",
] as const;

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function hasExactKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === expected[index])
  );
}

interface ExactProviderReceiptAuthority {
  readonly pinnedGlobalRolloutGeneration: string;
  readonly pinnedPracticeRolloutGeneration: string;
  readonly releaseId: string | null;
  readonly releaseIdentitySha256: string | null;
  readonly runtimeManifestSha256: string | null;
  readonly runtimeInstanceId: string | null;
  readonly runtimeIdentitySha256: string;
  readonly syntheticAdmissionId: string | null;
}

function receiptIsExact(input: {
  readonly evidence: unknown;
  readonly evidenceSha256: string | null | undefined;
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly sourceArtifactId: string;
  readonly sourceSha256: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly providerMode: "LIVE" | "SYNTHETIC_QA";
  readonly syntheticAdmissionId: string | null;
}): ExactProviderReceiptAuthority | null {
  const evidence = record(input.evidence);
  let encodedSize = Number.POSITIVE_INFINITY;
  try {
    encodedSize = Buffer.byteLength(JSON.stringify(evidence), "utf8");
  } catch {
    return null;
  }
  if (
    !evidence ||
    encodedSize > MAX_RECEIPT_BYTES ||
    !hasExactKeys(evidence, RECEIPT_KEYS) ||
    !input.evidenceSha256 ||
    !SHA256.test(input.evidenceSha256) ||
    canonicalSha256(evidence) !== input.evidenceSha256 ||
    evidence.contractVersion !== "template-twin-provider-ownership-receipt-v2" ||
    evidence.scope !== "SOURCE_INTAKE" ||
    evidence.practiceId !== input.practiceId ||
    evidence.actorUserId !== input.actorUserId ||
    evidence.providerMode !== input.providerMode ||
    evidence.syntheticAdmissionId !== input.syntheticAdmissionId ||
    evidence.subjectId !== input.sourceArtifactId ||
    evidence.subjectSha256 !== input.sourceSha256 ||
    evidence.visitId !== null ||
    evidence.visitInputMode !== null ||
    evidence.sourceArtifactId !== input.sourceArtifactId ||
    evidence.compiledVersionId !== input.compiledVersionId ||
    evidence.noteTemplateId !== input.noteTemplateId ||
    evidence.noteTemplateVersion !== input.noteTemplateVersion ||
    evidence.logicalAttempt !== 1 ||
    evidence.sourceLineageId !== input.sourceLineageId ||
    evidence.sourceLineageVersion !== input.sourceLineageVersion ||
    evidence.sourceSha256 !== input.sourceSha256 ||
    typeof evidence.pinnedGlobalRolloutGeneration !== "string" ||
    !GENERATION.test(evidence.pinnedGlobalRolloutGeneration) ||
    typeof evidence.pinnedPracticeRolloutGeneration !== "string" ||
    !GENERATION.test(evidence.pinnedPracticeRolloutGeneration) ||
    typeof evidence.runtimeIdentitySha256 !== "string" ||
    !SHA256.test(evidence.runtimeIdentitySha256) ||
    typeof evidence.executionPlanSha256 !== "string" ||
    !SHA256.test(evidence.executionPlanSha256) ||
    !Array.isArray(evidence.executionPlan) ||
    !Array.isArray(evidence.executions)
  ) {
    return null;
  }
  if (
    input.providerMode === "LIVE" &&
    (typeof evidence.releaseId !== "string" ||
      evidence.releaseId.length === 0 ||
      typeof evidence.releaseIdentitySha256 !== "string" ||
      !SHA256.test(evidence.releaseIdentitySha256) ||
      typeof evidence.runtimeManifestSha256 !== "string" ||
      !SHA256.test(evidence.runtimeManifestSha256) ||
      typeof evidence.runtimeInstanceId !== "string" ||
      evidence.runtimeInstanceId.length === 0)
  ) {
    return null;
  }
  const plan = evidence.executionPlan.map(record);
  if (
    plan.length !== EXPECTED_SOURCE_PLAN.length ||
    plan.some(
      (entry, index) =>
        !entry ||
        !hasExactKeys(entry, PLAN_KEYS) ||
        entry.operation !== EXPECTED_SOURCE_PLAN[index].operation ||
        entry.operationInstance !==
          EXPECTED_SOURCE_PLAN[index].operationInstance ||
        !OPERATION_INSTANCE.test(entry.operationInstance as string) ||
        entry.disposition !== EXPECTED_SOURCE_PLAN[index].disposition ||
        entry.reasonCode !== null,
    ) ||
    canonicalSha256({
      contractVersion: "template-twin-provider-execution-plan-v1",
      scope: "SOURCE_INTAKE",
      entries: evidence.executionPlan,
    }) !== evidence.executionPlanSha256
  ) {
    return null;
  }
  const executions = evidence.executions.map(record);
  const executionIds = executions.map((execution) => execution?.executionId);
  if (
    executions.length !== EXPECTED_SOURCE_PLAN.length ||
    executions.some(
      (execution, index) =>
        !execution ||
        !hasExactKeys(execution, EXECUTION_KEYS) ||
        typeof execution.executionId !== "string" ||
        execution.executionId.length === 0 ||
        execution.operation !== EXPECTED_SOURCE_PLAN[index].operation ||
        execution.operationInstance !==
          EXPECTED_SOURCE_PLAN[index].operationInstance ||
        typeof execution.resultSha256 !== "string" ||
        !SHA256.test(execution.resultSha256),
    ) ||
    new Set(executionIds).size !== executionIds.length
  ) {
    return null;
  }
  return {
    pinnedGlobalRolloutGeneration:
      evidence.pinnedGlobalRolloutGeneration as string,
    pinnedPracticeRolloutGeneration:
      evidence.pinnedPracticeRolloutGeneration as string,
    releaseId:
      typeof evidence.releaseId === "string" ? evidence.releaseId : null,
    releaseIdentitySha256:
      typeof evidence.releaseIdentitySha256 === "string"
        ? evidence.releaseIdentitySha256
        : null,
    runtimeManifestSha256:
      typeof evidence.runtimeManifestSha256 === "string"
        ? evidence.runtimeManifestSha256
        : null,
    runtimeInstanceId:
      typeof evidence.runtimeInstanceId === "string"
        ? evidence.runtimeInstanceId
        : null,
    runtimeIdentitySha256: evidence.runtimeIdentitySha256 as string,
    syntheticAdmissionId: input.syntheticAdmissionId,
  };
}

export interface TemplateTwinProviderCompilationIdentity {
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly compiledVersionId: string;
  readonly sourceArtifactId: string;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly sourceProviderOwnershipEvidence: unknown;
  readonly sourceProviderOwnershipSha256: string | null | undefined;
  readonly compiledProviderOwnershipEvidence: unknown;
  readonly compiledProviderOwnershipSha256: string | null | undefined;
}

function exactCompilationAuthority(input: {
  readonly identity: TemplateTwinProviderCompilationIdentity;
  readonly providerMode: "LIVE" | "SYNTHETIC_QA";
  readonly syntheticAdmissionId: string | null;
}): boolean {
  const exact = {
    practiceId: input.identity.practiceId,
    actorUserId: input.identity.actorUserId,
    sourceArtifactId: input.identity.sourceArtifactId,
    sourceSha256: input.identity.sourceSha256,
    compiledVersionId: input.identity.compiledVersionId,
    noteTemplateId: input.identity.noteTemplateId,
    noteTemplateVersion: input.identity.noteTemplateVersion,
    sourceLineageId: input.identity.sourceLineageId,
    sourceLineageVersion: input.identity.sourceLineageVersion,
    providerMode: input.providerMode,
    syntheticAdmissionId: input.syntheticAdmissionId,
  } as const;
  const source = receiptIsExact({
    ...exact,
    evidence: input.identity.sourceProviderOwnershipEvidence,
    evidenceSha256: input.identity.sourceProviderOwnershipSha256,
  });
  const compiled = receiptIsExact({
    ...exact,
    evidence: input.identity.compiledProviderOwnershipEvidence,
    evidenceSha256: input.identity.compiledProviderOwnershipSha256,
  });
  return Boolean(
    source &&
      compiled &&
      canonicalSha256(source) === canonicalSha256(compiled),
  );
}

export function isTemplateTwinLiveProviderCompilationOwned(
  input: TemplateTwinProviderCompilationIdentity,
): boolean {
  return exactCompilationAuthority({
    identity: input,
    providerMode: "LIVE",
    syntheticAdmissionId: null,
  });
}

export function isTemplateTwinStagingProviderCompilationOwned(
  input: TemplateTwinProviderCompilationIdentity & {
    readonly expectedSyntheticAdmissionId: string;
  },
): boolean {
  const sourceEvidence = record(input.sourceProviderOwnershipEvidence);
  const compiledEvidence = record(input.compiledProviderOwnershipEvidence);
  const admissionId = sourceEvidence?.syntheticAdmissionId;
  if (
    sourceEvidence?.providerMode !== "SYNTHETIC_QA" ||
    compiledEvidence?.providerMode !== "SYNTHETIC_QA" ||
    typeof admissionId !== "string" ||
    admissionId.length === 0 ||
    admissionId !== input.expectedSyntheticAdmissionId ||
    compiledEvidence.syntheticAdmissionId !== admissionId
  ) {
    return false;
  }
  return exactCompilationAuthority({
    identity: input,
    providerMode: "SYNTHETIC_QA",
    syntheticAdmissionId: admissionId,
  });
}

export function templateTwinVisitProviderSubjectSha256(input: {
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly visitId: string;
  readonly visitInputMode: string;
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly logicalAttempt: number;
}): string {
  return canonicalSha256({
    contractVersion: "template-twin-visit-provider-subject-v1",
    practiceId: input.practiceId,
    actorUserId: input.actorUserId,
    visitId: input.visitId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: input.noteTemplateVersion,
    compiledVersionId: input.compiledVersionId,
    sourceArtifactId: input.sourceArtifactId,
    sourceLineageId: input.sourceLineageId,
    sourceLineageVersion: input.sourceLineageVersion,
    sourceSha256: input.sourceSha256,
    logicalAttempt: input.logicalAttempt,
    inputMode: input.visitInputMode,
  });
}

export function isTemplateTwinVisitProviderReceiptOwned(input: {
  readonly evidence: unknown;
  readonly evidenceSha256: string | null | undefined;
  readonly practiceId: string;
  readonly actorUserId: string;
  readonly visitId: string;
  readonly visitInputMode: "audio_upload" | "voice_dictation" | "text_notes";
  readonly sourceArtifactId: string;
  readonly compiledVersionId: string;
  readonly noteTemplateId: string;
  readonly noteTemplateVersion: number;
  readonly sourceLineageId: string;
  readonly sourceLineageVersion: number;
  readonly sourceSha256: string;
  readonly logicalAttempt: number;
  readonly providerMode: "LIVE" | "SYNTHETIC_QA";
  readonly syntheticAdmissionId: string | null;
  readonly pinnedGlobalRolloutGeneration: bigint | string;
  readonly pinnedPracticeRolloutGeneration: bigint | string;
}): boolean {
  const evidence = record(input.evidence);
  let encodedSize = Number.POSITIVE_INFINITY;
  try {
    encodedSize = Buffer.byteLength(JSON.stringify(evidence), "utf8");
  } catch {
    return false;
  }
  const subjectSha256 = templateTwinVisitProviderSubjectSha256(input);
  if (
    !evidence ||
    encodedSize > MAX_RECEIPT_BYTES ||
    !hasExactKeys(evidence, RECEIPT_KEYS) ||
    !input.evidenceSha256 ||
    !SHA256.test(input.evidenceSha256) ||
    canonicalSha256(evidence) !== input.evidenceSha256 ||
    evidence.contractVersion !== "template-twin-provider-ownership-receipt-v2" ||
    evidence.scope !== "VISIT_PIPELINE" ||
    evidence.practiceId !== input.practiceId ||
    evidence.actorUserId !== input.actorUserId ||
    evidence.subjectId !== input.visitId ||
    evidence.subjectSha256 !== subjectSha256 ||
    evidence.visitId !== input.visitId ||
    evidence.visitInputMode !== input.visitInputMode ||
    evidence.sourceArtifactId !== input.sourceArtifactId ||
    evidence.compiledVersionId !== input.compiledVersionId ||
    evidence.noteTemplateId !== input.noteTemplateId ||
    evidence.noteTemplateVersion !== input.noteTemplateVersion ||
    evidence.logicalAttempt !== input.logicalAttempt ||
    evidence.sourceLineageId !== input.sourceLineageId ||
    evidence.sourceLineageVersion !== input.sourceLineageVersion ||
    evidence.sourceSha256 !== input.sourceSha256 ||
    evidence.providerMode !== input.providerMode ||
    evidence.syntheticAdmissionId !== input.syntheticAdmissionId ||
    evidence.pinnedGlobalRolloutGeneration !==
      String(input.pinnedGlobalRolloutGeneration) ||
    evidence.pinnedPracticeRolloutGeneration !==
      String(input.pinnedPracticeRolloutGeneration) ||
    typeof evidence.runtimeIdentitySha256 !== "string" ||
    !SHA256.test(evidence.runtimeIdentitySha256) ||
    typeof evidence.executionPlanSha256 !== "string" ||
    !SHA256.test(evidence.executionPlanSha256) ||
    !Array.isArray(evidence.executionPlan) ||
    evidence.executionPlan.length !== 12 ||
    !Array.isArray(evidence.executions) ||
    evidence.executions.length < 3 ||
    evidence.executions.length > 12
  ) {
    return false;
  }
  if (
    input.providerMode === "LIVE" &&
    (input.syntheticAdmissionId !== null ||
      typeof evidence.releaseId !== "string" ||
      evidence.releaseId.length === 0 ||
      typeof evidence.releaseIdentitySha256 !== "string" ||
      !SHA256.test(evidence.releaseIdentitySha256) ||
      typeof evidence.runtimeManifestSha256 !== "string" ||
      !SHA256.test(evidence.runtimeManifestSha256) ||
      typeof evidence.runtimeInstanceId !== "string" ||
      evidence.runtimeInstanceId.length === 0)
  ) {
    return false;
  }
  if (
    input.providerMode === "SYNTHETIC_QA" &&
    (!input.syntheticAdmissionId || input.syntheticAdmissionId.length === 0)
  ) {
    return false;
  }

  const plan = evidence.executionPlan.map(record);
  if (
    plan.some(
      (entry) =>
        !entry ||
        !hasExactKeys(entry, PLAN_KEYS) ||
        typeof entry.operation !== "string" ||
        typeof entry.operationInstance !== "string" ||
        !OPERATION_INSTANCE.test(entry.operationInstance) ||
        !["EXECUTED", "NOT_APPLICABLE"].includes(
          entry.disposition as string,
        ) ||
        (entry.disposition === "EXECUTED" && entry.reasonCode !== null) ||
        (entry.disposition === "NOT_APPLICABLE" &&
          (typeof entry.reasonCode !== "string" ||
            !/^[A-Z0-9_]{3,80}$/u.test(entry.reasonCode))),
    )
  ) {
    return false;
  }
  const planKeys = plan.map(
    (entry) => `${entry!.operation}:${entry!.operationInstance}`,
  );
  if (
    new Set(planKeys).size !== planKeys.length ||
    canonicalSha256({
      contractVersion: "template-twin-provider-execution-plan-v1",
      scope: "VISIT_PIPELINE",
      entries: evidence.executionPlan,
    }) !== evidence.executionPlanSha256
  ) {
    return false;
  }
  const byKey = new Map(
    plan.map((entry) => [
      `${entry!.operation}:${entry!.operationInstance}`,
      entry!,
    ]),
  );
  const requirePlan = (
    operation: string,
    operationInstance: string,
    disposition: "EXECUTED" | "NOT_APPLICABLE",
    reasonCode: string | null,
  ): boolean => {
    const entry = byKey.get(`${operation}:${operationInstance}`);
    return (
      entry?.disposition === disposition && entry.reasonCode === reasonCode
    );
  };
  const inputPlanValid =
    input.visitInputMode === "audio_upload"
      ? requirePlan("L1_TRANSCRIBE", "primary", "EXECUTED", null) &&
        requirePlan(
          "L1B_TRANSCRIBE",
          "primary",
          "NOT_APPLICABLE",
          "INPUT_MODE_CONVERSATION",
        ) &&
        requirePlan("L2_SPEAKER_ROLES", "primary", "EXECUTED", null)
      : input.visitInputMode === "voice_dictation"
        ? requirePlan(
            "L1_TRANSCRIBE",
            "primary",
            "NOT_APPLICABLE",
            "INPUT_MODE_DICTATION",
          ) &&
          requirePlan("L1B_TRANSCRIBE", "primary", "EXECUTED", null) &&
          requirePlan(
            "L2_SPEAKER_ROLES",
            "primary",
            "NOT_APPLICABLE",
            "INPUT_MODE_DICTATION",
          )
        : requirePlan(
            "L1_TRANSCRIBE",
            "primary",
            "NOT_APPLICABLE",
            "INPUT_MODE_TEXT",
          ) &&
          requirePlan(
            "L1B_TRANSCRIBE",
            "primary",
            "NOT_APPLICABLE",
            "INPUT_MODE_TEXT",
          ) &&
          requirePlan(
            "L2_SPEAKER_ROLES",
            "primary",
            "NOT_APPLICABLE",
            "INPUT_MODE_TEXT",
          );
  if (
    !inputPlanValid ||
    !requirePlan("L3_EXTRACT_ENTITIES", "primary", "EXECUTED", null) ||
    !requirePlan("L4_GENERATE_SOAP", "primary", "EXECUTED", null) ||
    !requirePlan("L5_SELF_CRITIQUE", "primary", "EXECUTED", null)
  ) {
    return false;
  }
  const anchors = [1, 2, 3].map((pass) =>
    byKey.get(`L4_ANCHOR_VERIFY:ensemble-pass-${pass}`),
  );
  if (
    anchors.some((entry) => !entry) ||
    anchors.some(
      (entry) =>
        entry!.disposition !== anchors[0]!.disposition ||
        entry!.reasonCode !== anchors[0]!.reasonCode,
    ) ||
    (anchors[0]!.disposition === "NOT_APPLICABLE" &&
      ![
        "EVIDENCE_ANCHORS_DISABLED",
        "NO_ANCHORED_CLAIMS",
        "DETERMINISTIC_ANCHOR_MOCK",
      ].includes(anchors[0]!.reasonCode as string))
  ) {
    return false;
  }
  const customEntries = plan.filter(
    (entry) => entry!.operation === "CUSTOM_CONCEPT_EXTRACTION",
  );
  if (
    customEntries.length !== 1 ||
    !/^spec-set-[0-9a-f]{48}$/u.test(
      customEntries[0]!.operationInstance as string,
    ) ||
    !(
      (customEntries[0]!.disposition === "EXECUTED" &&
        customEntries[0]!.reasonCode === null) ||
      (customEntries[0]!.disposition === "NOT_APPLICABLE" &&
        customEntries[0]!.reasonCode ===
          "NO_CERTIFIED_CUSTOM_SPECIFICATIONS")
    )
  ) {
    return false;
  }
  const polishExecuted = requirePlan(
    "L6_POLISH",
    "primary",
    "EXECUTED",
    null,
  );
  if (
    !(
      (polishExecuted &&
        (requirePlan(
          "L6_FIDELITY_VERIFY",
          "primary",
          "EXECUTED",
          null,
        ) ||
          requirePlan(
            "L6_FIDELITY_VERIFY",
            "primary",
            "NOT_APPLICABLE",
            "EMPTY_POLISH_OUTPUT",
          ))) ||
      (requirePlan(
        "L6_POLISH",
        "primary",
        "NOT_APPLICABLE",
        "NO_FIXABLE_CRITIQUE_WORK",
      ) &&
        requirePlan(
          "L6_FIDELITY_VERIFY",
          "primary",
          "NOT_APPLICABLE",
          "POLISH_NOT_EXECUTED",
        ))
    )
  ) {
    return false;
  }

  const executions = evidence.executions.map(record);
  const executionIds = executions.map((execution) => execution?.executionId);
  const executionKeys = executions.map(
    (execution) => `${execution?.operation}:${execution?.operationInstance}`,
  );
  if (
    executions.some(
      (execution) =>
        !execution ||
        !hasExactKeys(execution, EXECUTION_KEYS) ||
        typeof execution.executionId !== "string" ||
        execution.executionId.length === 0 ||
        typeof execution.resultSha256 !== "string" ||
        !SHA256.test(execution.resultSha256) ||
        byKey.get(
          `${execution.operation as string}:${execution.operationInstance as string}`,
        )?.disposition !== "EXECUTED",
    ) ||
    new Set(executionIds).size !== executionIds.length ||
    new Set(executionKeys).size !== executionKeys.length ||
    plan.some(
      (entry) =>
        (entry!.disposition === "EXECUTED") !==
        executionKeys.includes(
          `${entry!.operation as string}:${entry!.operationInstance as string}`,
        ),
    )
  ) {
    return false;
  }
  return true;
}
