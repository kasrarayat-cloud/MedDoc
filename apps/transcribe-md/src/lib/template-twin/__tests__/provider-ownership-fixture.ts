import { canonicalSha256 } from "../canonical";
import { createHash } from "node:crypto";
import { templateTwinVisitProviderSubjectSha256 } from "../live-provider-ownership";

const RELEASE_ID = "11111111-1111-4111-8111-111111111111";
const SOURCE_PLAN = [
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

export function sourceProviderOwnershipFixture(input: {
  practiceId: string;
  actorUserId: string;
  sourceArtifactId: string;
  sourceSha256: string;
  compiledVersionId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  sourceLineageId: string;
  sourceLineageVersion: number;
}) {
  const executionPlan = SOURCE_PLAN;
  const evidence = {
    contractVersion: "template-twin-provider-ownership-receipt-v2",
    scope: "SOURCE_INTAKE",
    practiceId: input.practiceId,
    actorUserId: input.actorUserId,
    subjectId: input.sourceArtifactId,
    subjectSha256: input.sourceSha256,
    visitId: null,
    sourceArtifactId: input.sourceArtifactId,
    compiledVersionId: input.compiledVersionId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: input.noteTemplateVersion,
    visitInputMode: null,
    logicalAttempt: 1,
    sourceLineageId: input.sourceLineageId,
    sourceLineageVersion: input.sourceLineageVersion,
    sourceSha256: input.sourceSha256,
    providerMode: "LIVE",
    pinnedGlobalRolloutGeneration: "1",
    pinnedPracticeRolloutGeneration: "1",
    releaseId: RELEASE_ID,
    releaseIdentitySha256: "1".repeat(64),
    runtimeManifestSha256: "2".repeat(64),
    runtimeInstanceId: "provider-fixture-runtime",
    runtimeIdentitySha256: "3".repeat(64),
    syntheticAdmissionId: null,
    executionPlanSha256: canonicalSha256({
      contractVersion: "template-twin-provider-execution-plan-v1",
      scope: "SOURCE_INTAKE",
      entries: executionPlan,
    }),
    executionPlan,
    executions: [
      {
        executionId: "provider-fixture-source-phi",
        operation: "SOURCE_PHI_SCAN",
        operationInstance: "primary",
        resultSha256: "4".repeat(64),
      },
      {
        executionId: "provider-fixture-source-mapping",
        operation: "SOURCE_SEMANTIC_MAPPING",
        operationInstance: "primary",
        resultSha256: "5".repeat(64),
      },
    ],
  } as const;
  return { evidence, sha256: canonicalSha256(evidence) };
}

export function visitProviderOwnershipFixture(input: {
  practiceId: string;
  actorUserId: string;
  visitId: string;
  visitInputMode: "audio_upload" | "voice_dictation" | "text_notes";
  sourceArtifactId: string;
  sourceSha256: string;
  compiledVersionId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  sourceLineageId: string;
  sourceLineageVersion: number;
  logicalAttempt: number;
}) {
  const inputModeEntries =
    input.visitInputMode === "audio_upload"
      ? [
          ["L1_TRANSCRIBE", "EXECUTED", null],
          ["L1B_TRANSCRIBE", "NOT_APPLICABLE", "INPUT_MODE_CONVERSATION"],
          ["L2_SPEAKER_ROLES", "EXECUTED", null],
        ]
      : input.visitInputMode === "voice_dictation"
        ? [
            ["L1_TRANSCRIBE", "NOT_APPLICABLE", "INPUT_MODE_DICTATION"],
            ["L1B_TRANSCRIBE", "EXECUTED", null],
            ["L2_SPEAKER_ROLES", "NOT_APPLICABLE", "INPUT_MODE_DICTATION"],
          ]
        : [
            ["L1_TRANSCRIBE", "NOT_APPLICABLE", "INPUT_MODE_TEXT"],
            ["L1B_TRANSCRIBE", "NOT_APPLICABLE", "INPUT_MODE_TEXT"],
            ["L2_SPEAKER_ROLES", "NOT_APPLICABLE", "INPUT_MODE_TEXT"],
          ];
  const emptySpecInstance = `spec-set-${createHash("sha256")
    .update("", "utf8")
    .digest("hex")
    .slice(0, 48)}`;
  const executionPlan = [
    {
      operation: "CUSTOM_CONCEPT_EXTRACTION",
      operationInstance: emptySpecInstance,
      disposition: "NOT_APPLICABLE",
      reasonCode: "NO_CERTIFIED_CUSTOM_SPECIFICATIONS",
    },
    ...inputModeEntries.map(([operation, disposition, reasonCode]) => ({
      operation,
      operationInstance: "primary",
      disposition,
      reasonCode,
    })),
    {
      operation: "L3_EXTRACT_ENTITIES",
      operationInstance: "primary",
      disposition: "EXECUTED",
      reasonCode: null,
    },
    {
      operation: "L4_GENERATE_SOAP",
      operationInstance: "primary",
      disposition: "EXECUTED",
      reasonCode: null,
    },
    ...[1, 2, 3].map((pass) => ({
      operation: "L4_ANCHOR_VERIFY",
      operationInstance: `ensemble-pass-${pass}`,
      disposition: "NOT_APPLICABLE",
      reasonCode: "EVIDENCE_ANCHORS_DISABLED",
    })),
    {
      operation: "L5_SELF_CRITIQUE",
      operationInstance: "primary",
      disposition: "EXECUTED",
      reasonCode: null,
    },
    {
      operation: "L6_POLISH",
      operationInstance: "primary",
      disposition: "NOT_APPLICABLE",
      reasonCode: "NO_FIXABLE_CRITIQUE_WORK",
    },
    {
      operation: "L6_FIDELITY_VERIFY",
      operationInstance: "primary",
      disposition: "NOT_APPLICABLE",
      reasonCode: "POLISH_NOT_EXECUTED",
    },
  ].sort((left, right) =>
    `${left.operation}:${left.operationInstance}`.localeCompare(
      `${right.operation}:${right.operationInstance}`,
    ),
  );
  const subjectSha256 = templateTwinVisitProviderSubjectSha256(input);
  const executions = executionPlan
    .filter((entry) => entry.disposition === "EXECUTED")
    .map((entry, index) => ({
      executionId: `provider-fixture-visit-${index + 1}`,
      operation: entry.operation,
      operationInstance: entry.operationInstance,
      resultSha256: String(index + 6).repeat(64).slice(0, 64),
    }));
  const evidence = {
    contractVersion: "template-twin-provider-ownership-receipt-v2",
    scope: "VISIT_PIPELINE",
    practiceId: input.practiceId,
    actorUserId: input.actorUserId,
    subjectId: input.visitId,
    subjectSha256,
    visitId: input.visitId,
    sourceArtifactId: input.sourceArtifactId,
    compiledVersionId: input.compiledVersionId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: input.noteTemplateVersion,
    visitInputMode: input.visitInputMode,
    logicalAttempt: input.logicalAttempt,
    sourceLineageId: input.sourceLineageId,
    sourceLineageVersion: input.sourceLineageVersion,
    sourceSha256: input.sourceSha256,
    providerMode: "LIVE",
    pinnedGlobalRolloutGeneration: "1",
    pinnedPracticeRolloutGeneration: "1",
    releaseId: RELEASE_ID,
    releaseIdentitySha256: "1".repeat(64),
    runtimeManifestSha256: "2".repeat(64),
    runtimeInstanceId: "provider-fixture-runtime",
    runtimeIdentitySha256: "3".repeat(64),
    syntheticAdmissionId: null,
    executionPlanSha256: canonicalSha256({
      contractVersion: "template-twin-provider-execution-plan-v1",
      scope: "VISIT_PIPELINE",
      entries: executionPlan,
    }),
    executionPlan,
    executions,
  };
  return { evidence, sha256: canonicalSha256(evidence) };
}
