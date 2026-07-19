import { canonicalSha256 } from "./canonical";

export const TEMPLATE_TWIN_RELEASE_IDENTITY_VERSION =
  "template-twin-production-release-v2" as const;
export const TEMPLATE_TWIN_GUARDRAIL_SCHEMA_VERSION =
  "template-twin-guardrails-v1" as const;
export const TEMPLATE_TWIN_RUNTIME_ATTESTATION_VERSION =
  "template-twin-runtime-attestation-v1" as const;
export const TEMPLATE_TWIN_METRIC_ATTESTATION_VERSION =
  "template-twin-metric-attestation-v1" as const;

export const TEMPLATE_TWIN_RUNTIME_COMPONENTS = ["APP", "WORKER"] as const;
export type TemplateTwinRuntimeComponent =
  (typeof TEMPLATE_TWIN_RUNTIME_COMPONENTS)[number];

export const TEMPLATE_TWIN_RELEASE_DISCIPLINES = [
  "DESKTOP_WORD",
  "CLINICAL_SAFETY",
  "PRIVACY_LEGAL",
  "OPERATIONS",
] as const;

export type TemplateTwinReleaseDiscipline =
  (typeof TEMPLATE_TWIN_RELEASE_DISCIPLINES)[number];

export const TEMPLATE_TWIN_RELEASE_STAGES = [
  { stage: "CANARY", ordinal: 1, targetPercent: 0 },
  { stage: "PERCENT_10", ordinal: 2, targetPercent: 10 },
  { stage: "PERCENT_25", ordinal: 3, targetPercent: 25 },
  { stage: "PERCENT_50", ordinal: 4, targetPercent: 50 },
  { stage: "PERCENT_100", ordinal: 5, targetPercent: 100 },
] as const;

export type TemplateTwinReleaseStage =
  (typeof TEMPLATE_TWIN_RELEASE_STAGES)[number]["stage"];

export type TemplateTwinReleaseStatus =
  | "DRAFT"
  | "FROZEN"
  | "APPROVED"
  | "ROLLING_OUT"
  | "STABLE_100"
  | "REJECTED"
  | "REVOKED";

export type TemplateTwinCheckpointStatus =
  | "PENDING"
  | "ACTIVE"
  | "PASSED"
  | "FAILED"
  | "REVOKED";

export type TemplateTwinApprovalDecision = "APPROVE" | "REJECT" | "REVOKE";

const SHA256 = /^[0-9a-f]{64}$/u;
const COMMIT_SHA = /^[0-9a-f]{40}$/u;
const IMAGE_DIGEST = /^sha256:[0-9a-f]{64}$/u;

function ordinalCompare(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

export interface TemplateTwinReleaseIdentityEvidence {
  readonly sourceCommitSha: string;
  readonly baseCommitSha: string;
  readonly appImageDigest: string;
  readonly workerImageDigest: string;
  readonly migratorImageDigest: string;
  readonly testCensusEvidenceSha256: string;
  readonly independentReviewEvidenceSha256: string;
  readonly securityEvidenceSha256: string;
  readonly migrationRestoreEvidenceSha256: string;
  readonly officeWordEvidenceSha256: string;
}

export interface TemplateTwinReleaseIdentityInput extends TemplateTwinReleaseIdentityEvidence {
  readonly guardrailPolicySha256: string;
  readonly authorizedPracticeManifestSha256: string;
  readonly runtimeManifestSha256: string;
}

export function assertTemplateTwinReleaseIdentityInput(
  input: TemplateTwinReleaseIdentityInput,
): void {
  if (
    !COMMIT_SHA.test(input.sourceCommitSha) ||
    !COMMIT_SHA.test(input.baseCommitSha)
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_IDENTITY_INVALID",
      "Release source and base commits must be exact lowercase 40-character SHAs.",
    );
  }
  if (
    !IMAGE_DIGEST.test(input.appImageDigest) ||
    !IMAGE_DIGEST.test(input.workerImageDigest) ||
    !IMAGE_DIGEST.test(input.migratorImageDigest)
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_IDENTITY_INVALID",
      "Release images must use exact lowercase sha256 digests.",
    );
  }
  for (const digest of [
    input.testCensusEvidenceSha256,
    input.independentReviewEvidenceSha256,
    input.securityEvidenceSha256,
    input.migrationRestoreEvidenceSha256,
    input.officeWordEvidenceSha256,
    input.guardrailPolicySha256,
    input.authorizedPracticeManifestSha256,
    input.runtimeManifestSha256,
  ]) {
    if (!SHA256.test(digest)) {
      throw new TemplateTwinReleaseContractError(
        "TEMPLATE_TWIN_RELEASE_IDENTITY_INVALID",
        "Every release evidence reference must be an exact lowercase SHA-256 digest.",
      );
    }
  }
}

export function templateTwinReleaseIdentitySha256(
  input: TemplateTwinReleaseIdentityInput,
): string {
  assertTemplateTwinReleaseIdentityInput(input);
  return canonicalSha256({
    version: TEMPLATE_TWIN_RELEASE_IDENTITY_VERSION,
    sourceCommitSha: input.sourceCommitSha,
    baseCommitSha: input.baseCommitSha,
    images: {
      application: input.appImageDigest,
      worker: input.workerImageDigest,
      migrator: input.migratorImageDigest,
    },
    evidence: {
      testCensus: input.testCensusEvidenceSha256,
      independentExactHeadReview: input.independentReviewEvidenceSha256,
      securityAndSecretScan: input.securityEvidenceSha256,
      migrationAndRestoreRehearsal: input.migrationRestoreEvidenceSha256,
      desktopMicrosoftWord: input.officeWordEvidenceSha256,
    },
    guardrailPolicySha256: input.guardrailPolicySha256,
    authorizedPracticeManifestSha256: input.authorizedPracticeManifestSha256,
    runtimeManifestSha256: input.runtimeManifestSha256,
  });
}

export interface TemplateTwinRuntimeRequirementInput {
  readonly instanceId: string;
  readonly component: TemplateTwinRuntimeComponent;
  readonly imageDigest: string;
}

export interface TemplateTwinRuntimeManifest {
  readonly instances: readonly TemplateTwinRuntimeRequirementInput[];
  readonly runtimeManifestSha256: string;
}

export function buildTemplateTwinRuntimeManifest(input: {
  readonly sourceCommitSha: string;
  readonly appImageDigest: string;
  readonly workerImageDigest: string;
  readonly instances: readonly TemplateTwinRuntimeRequirementInput[];
}): TemplateTwinRuntimeManifest {
  if (
    !COMMIT_SHA.test(input.sourceCommitSha) ||
    !IMAGE_DIGEST.test(input.appImageDigest) ||
    !IMAGE_DIGEST.test(input.workerImageDigest) ||
    input.instances.length < 2 ||
    input.instances.length > 256
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RUNTIME_MANIFEST_INVALID",
      "The runtime manifest requires bounded APP and WORKER instances pinned to exact image digests.",
    );
  }

  const instanceIds = new Set<string>();
  const instances = input.instances
    .map((instance) => {
      const expectedDigest =
        instance.component === "APP"
          ? input.appImageDigest
          : instance.component === "WORKER"
            ? input.workerImageDigest
            : null;
      if (
        !expectedDigest ||
        instance.imageDigest !== expectedDigest ||
        !/^[a-z0-9][a-z0-9._-]{1,127}$/u.test(instance.instanceId) ||
        instanceIds.has(instance.instanceId)
      ) {
        throw new TemplateTwinReleaseContractError(
          "TEMPLATE_TWIN_RUNTIME_MANIFEST_INVALID",
          "Runtime instance identifiers must be unique and every instance must use its release-pinned component digest.",
        );
      }
      instanceIds.add(instance.instanceId);
      return {
        instanceId: instance.instanceId,
        component: instance.component,
        imageDigest: instance.imageDigest,
      };
    })
    .sort(
      (left, right) =>
        ordinalCompare(left.component, right.component) ||
        ordinalCompare(left.instanceId, right.instanceId),
    );

  if (
    !instances.some(({ component }) => component === "APP") ||
    !instances.some(({ component }) => component === "WORKER")
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RUNTIME_MANIFEST_INVALID",
      "The runtime manifest must include at least one application and one worker replica.",
    );
  }

  return {
    instances,
    runtimeManifestSha256: canonicalSha256({
      version: "template-twin-runtime-manifest-v1",
      sourceCommitSha: input.sourceCommitSha,
      instances,
    }),
  };
}

export const TEMPLATE_TWIN_METRIC_DEFINITIONS = {
  failed_upload_rate: { direction: "MAX", min: 0, max: 1 },
  malware_inspection_failure_rate: { direction: "MAX", min: 0, max: 1 },
  render_verification_failure_rate: { direction: "MAX", min: 0, max: 1 },
  sign_download_block_rate: { direction: "MAX", min: 0, max: 1 },
  unsafe_bypass_attempt_count: { direction: "MAX", min: 0, max: 1_000_000 },
  audit_outbox_delivery_failure_rate: { direction: "MAX", min: 0, max: 1 },
  audit_outbox_max_lag_seconds: { direction: "MAX", min: 0, max: 86_400 },
  object_storage_failure_rate: { direction: "MAX", min: 0, max: 1 },
  queue_failure_rate: { direction: "MAX", min: 0, max: 1 },
  provider_failure_rate: { direction: "MAX", min: 0, max: 1 },
  provider_ambiguous_outcome_count: {
    direction: "MAX",
    min: 0,
    max: 1_000_000,
  },
  p95_latency_ms: { direction: "MAX", min: 0, max: 3_600_000 },
  p99_latency_ms: { direction: "MAX", min: 0, max: 3_600_000 },
  error_rate: { direction: "MAX", min: 0, max: 1 },
  critical_field_accuracy: { direction: "MIN", min: 0, max: 1 },
  unsupported_field_recall: { direction: "MIN", min: 0, max: 1 },
  hallucination_rate: { direction: "MAX", min: 0, max: 1 },
  evidence_anchor_validity: { direction: "MIN", min: 0, max: 1 },
  exact_dropdown_accuracy: { direction: "MIN", min: 0, max: 1 },
  negation_accuracy: { direction: "MIN", min: 0, max: 1 },
  laterality_accuracy: { direction: "MIN", min: 0, max: 1 },
  table_placement_accuracy: { direction: "MIN", min: 0, max: 1 },
} as const;

export type TemplateTwinMetricKey =
  keyof typeof TEMPLATE_TWIN_METRIC_DEFINITIONS;

const REQUIRED_CRITICAL_METRICS = new Set<TemplateTwinMetricKey>([
  "unsafe_bypass_attempt_count",
  "provider_ambiguous_outcome_count",
  "critical_field_accuracy",
  "hallucination_rate",
  "evidence_anchor_validity",
  "exact_dropdown_accuracy",
  "negation_accuracy",
  "laterality_accuracy",
  "table_placement_accuracy",
]);

export interface TemplateTwinMetricRule {
  readonly direction: "MIN" | "MAX";
  readonly threshold: number;
  readonly critical: boolean;
}

export interface TemplateTwinGuardrailPolicy {
  readonly schemaVersion: typeof TEMPLATE_TWIN_GUARDRAIL_SCHEMA_VERSION;
  readonly maxObservationAgeSeconds: number;
  readonly minimumBakeSecondsByStage: Readonly<
    Record<TemplateTwinReleaseStage, number>
  >;
  readonly minimumSampleCountByStage: Readonly<
    Record<TemplateTwinReleaseStage, number>
  >;
  readonly metrics: Readonly<
    Record<TemplateTwinMetricKey, TemplateTwinMetricRule>
  >;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function safeInteger(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return (
    typeof value === "number" &&
    Number.isSafeInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function exactObjectKeys(
  input: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(input).sort();
  return (
    actual.length === expected.length &&
    actual.every((key, index) => key === [...expected].sort()[index])
  );
}

export function parseTemplateTwinGuardrailPolicy(
  value: unknown,
): TemplateTwinGuardrailPolicy {
  if (
    !isPlainRecord(value) ||
    !exactObjectKeys(value, [
      "schemaVersion",
      "maxObservationAgeSeconds",
      "minimumBakeSecondsByStage",
      "minimumSampleCountByStage",
      "metrics",
    ]) ||
    value.schemaVersion !== TEMPLATE_TWIN_GUARDRAIL_SCHEMA_VERSION ||
    !safeInteger(value.maxObservationAgeSeconds, 60, 86_400) ||
    !isPlainRecord(value.minimumBakeSecondsByStage) ||
    !isPlainRecord(value.minimumSampleCountByStage) ||
    !isPlainRecord(value.metrics)
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_GUARDRAIL_POLICY_INVALID",
      "Guardrail policy shape or version is unsupported.",
    );
  }

  const stageNames = TEMPLATE_TWIN_RELEASE_STAGES.map(({ stage }) => stage);
  if (
    !exactObjectKeys(value.minimumBakeSecondsByStage, stageNames) ||
    !exactObjectKeys(value.minimumSampleCountByStage, stageNames)
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_GUARDRAIL_POLICY_INVALID",
      "Guardrail policy must define every fixed rollout checkpoint.",
    );
  }
  for (const stage of stageNames) {
    if (
      !safeInteger(value.minimumBakeSecondsByStage[stage], 1, 2_592_000) ||
      !safeInteger(value.minimumSampleCountByStage[stage], 1, 10_000_000)
    ) {
      throw new TemplateTwinReleaseContractError(
        "TEMPLATE_TWIN_GUARDRAIL_POLICY_INVALID",
        "Checkpoint bake time and sample floor must be positive bounded integers.",
      );
    }
  }

  const metricKeys = Object.keys(
    TEMPLATE_TWIN_METRIC_DEFINITIONS,
  ) as TemplateTwinMetricKey[];
  if (!exactObjectKeys(value.metrics, metricKeys)) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_GUARDRAIL_POLICY_INVALID",
      "Guardrail policy must use the exact aggregate metric key set.",
    );
  }
  for (const key of metricKeys) {
    const rawRule = value.metrics[key];
    const definition = TEMPLATE_TWIN_METRIC_DEFINITIONS[key];
    if (
      !isPlainRecord(rawRule) ||
      !exactObjectKeys(rawRule, ["direction", "threshold", "critical"]) ||
      rawRule.direction !== definition.direction ||
      typeof rawRule.threshold !== "number" ||
      !Number.isFinite(rawRule.threshold) ||
      rawRule.threshold < definition.min ||
      rawRule.threshold > definition.max ||
      !Number.isSafeInteger(rawRule.threshold * 1_000_000) ||
      typeof rawRule.critical !== "boolean" ||
      (REQUIRED_CRITICAL_METRICS.has(key) && !rawRule.critical)
    ) {
      throw new TemplateTwinReleaseContractError(
        "TEMPLATE_TWIN_GUARDRAIL_POLICY_INVALID",
        `Guardrail rule ${key} has an invalid direction, threshold, or criticality.`,
      );
    }
  }

  return value as unknown as TemplateTwinGuardrailPolicy;
}

export function templateTwinGuardrailPolicySha256(value: unknown): string {
  return canonicalSha256(parseTemplateTwinGuardrailPolicy(value));
}

export interface TemplateTwinPracticeSnapshot {
  readonly practiceId: string;
  readonly practiceSlug: string;
  readonly physicianCount: number;
}

export interface TemplateTwinAssignedPractice extends TemplateTwinPracticeSnapshot {
  readonly cohortRank: number;
  readonly cohortHashSha256: string;
  readonly isCanary: boolean;
  readonly activationStage: TemplateTwinReleaseStage;
  readonly activationStageOrdinal: number;
}

export interface TemplateTwinCheckpointPlan {
  readonly stage: TemplateTwinReleaseStage;
  readonly ordinal: number;
  readonly targetPercent: number;
  readonly targetPhysicianCount: number;
  readonly assignedPhysicianCount: number;
}

export interface TemplateTwinCohortPlan {
  readonly practices: readonly TemplateTwinAssignedPractice[];
  readonly checkpoints: readonly TemplateTwinCheckpointPlan[];
  readonly authorizedPracticeManifestSha256: string;
}

function targetCount(total: number, percent: number): number {
  return percent === 100 ? total : Math.ceil((total * percent) / 100);
}

export function buildTemplateTwinCohortPlan(input: {
  readonly sourceCommitSha: string;
  readonly practices: readonly TemplateTwinPracticeSnapshot[];
  readonly canaryPracticeIds: readonly string[];
}): TemplateTwinCohortPlan {
  if (!COMMIT_SHA.test(input.sourceCommitSha)) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_MANIFEST_INVALID",
      "A stable cohort requires the exact release source commit.",
    );
  }
  if (input.practices.length === 0 || input.practices.length > 10_000) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_MANIFEST_INVALID",
      "The authorized manifest must contain between one and 10,000 practices.",
    );
  }

  const practiceIds = new Set<string>();
  for (const practice of input.practices) {
    if (
      !practice.practiceId ||
      !/^[a-z0-9][a-z0-9_-]{1,127}$/iu.test(practice.practiceId) ||
      !/^[a-z0-9][a-z0-9-]{0,158}[a-z0-9]$/u.test(practice.practiceSlug) ||
      !safeInteger(practice.physicianCount, 0, 10_000_000) ||
      practiceIds.has(practice.practiceId)
    ) {
      throw new TemplateTwinReleaseContractError(
        "TEMPLATE_TWIN_RELEASE_MANIFEST_INVALID",
        "Authorized practice identifiers, slugs, and physician counts must be unique and bounded.",
      );
    }
    practiceIds.add(practice.practiceId);
  }

  const canaryIds = new Set(input.canaryPracticeIds);
  if (
    canaryIds.size === 0 ||
    canaryIds.size !== input.canaryPracticeIds.length ||
    [...canaryIds].some((practiceId) => !practiceIds.has(practiceId))
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_MANIFEST_INVALID",
      "Canary practices must be a non-empty unique subset of the authorized manifest.",
    );
  }

  const ranked = input.practices
    .map((practice) => ({
      ...practice,
      isCanary: canaryIds.has(practice.practiceId),
      cohortHashSha256: canonicalSha256({
        version: "template-twin-cohort-rank-v1",
        sourceCommitSha: input.sourceCommitSha,
        practiceId: practice.practiceId,
      }),
    }))
    .sort((left, right) => {
      if (left.isCanary !== right.isCanary) return left.isCanary ? -1 : 1;
      return (
        ordinalCompare(left.cohortHashSha256, right.cohortHashSha256) ||
        ordinalCompare(left.practiceId, right.practiceId)
      );
    });

  const totalPhysicians = ranked.reduce(
    (sum, practice) => sum + practice.physicianCount,
    0,
  );
  const canaryPhysicians = ranked
    .filter(({ isCanary }) => isCanary)
    .reduce((sum, practice) => sum + practice.physicianCount, 0);
  if (canaryPhysicians === 0) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_MANIFEST_INVALID",
      "The canary cohort must include at least one authorized physician.",
    );
  }

  let assignedPhysicians = canaryPhysicians;
  let cursor = ranked.findIndex(({ isCanary }) => !isCanary);
  if (cursor < 0) cursor = ranked.length;
  const stageByPractice = new Map<string, TemplateTwinReleaseStage>();
  for (const practice of ranked.filter(({ isCanary }) => isCanary)) {
    stageByPractice.set(practice.practiceId, "CANARY");
  }

  const checkpointPlans: TemplateTwinCheckpointPlan[] = [];
  for (const checkpoint of TEMPLATE_TWIN_RELEASE_STAGES) {
    const target =
      checkpoint.stage === "CANARY"
        ? canaryPhysicians
        : targetCount(totalPhysicians, checkpoint.targetPercent);
    if (checkpoint.stage !== "CANARY") {
      while (cursor < ranked.length && assignedPhysicians < target) {
        const practice = ranked[cursor]!;
        stageByPractice.set(practice.practiceId, checkpoint.stage);
        assignedPhysicians += practice.physicianCount;
        cursor += 1;
      }
      if (checkpoint.stage === "PERCENT_100") {
        while (cursor < ranked.length) {
          const practice = ranked[cursor]!;
          stageByPractice.set(practice.practiceId, checkpoint.stage);
          assignedPhysicians += practice.physicianCount;
          cursor += 1;
        }
      }
    }
    checkpointPlans.push({
      ...checkpoint,
      targetPhysicianCount: target,
      assignedPhysicianCount: assignedPhysicians,
    });
  }

  const stageOrdinal = new Map(
    TEMPLATE_TWIN_RELEASE_STAGES.map(({ stage, ordinal }) => [stage, ordinal]),
  );
  const practices: TemplateTwinAssignedPractice[] = ranked.map(
    (practice, index) => {
      const activationStage = stageByPractice.get(practice.practiceId);
      if (!activationStage) {
        throw new TemplateTwinReleaseContractError(
          "TEMPLATE_TWIN_RELEASE_MANIFEST_INVALID",
          "Every authorized practice must be assigned by the 100% checkpoint.",
        );
      }
      return {
        practiceId: practice.practiceId,
        practiceSlug: practice.practiceSlug,
        physicianCount: practice.physicianCount,
        cohortRank: index + 1,
        cohortHashSha256: practice.cohortHashSha256,
        isCanary: practice.isCanary,
        activationStage,
        activationStageOrdinal: stageOrdinal.get(activationStage)!,
      };
    },
  );

  const manifestPayload = {
    version: "template-twin-authorized-practice-manifest-v1",
    sourceCommitSha: input.sourceCommitSha,
    practices: practices.map((practice) => ({
      practiceId: practice.practiceId,
      practiceSlugSnapshot: practice.practiceSlug,
      physicianCountSnapshot: practice.physicianCount,
      cohortRank: practice.cohortRank,
      cohortHashSha256: practice.cohortHashSha256,
      isCanary: practice.isCanary,
      activationStage: practice.activationStage,
      activationStageOrdinal: practice.activationStageOrdinal,
    })),
  };
  return {
    practices,
    checkpoints: checkpointPlans,
    authorizedPracticeManifestSha256: canonicalSha256(manifestPayload),
  };
}

export interface TemplateTwinMetricEvaluation {
  readonly evaluation: "PASS" | "BLOCK" | "CRITICAL_REVOKE";
  readonly metrics: Readonly<Partial<Record<TemplateTwinMetricKey, number>>>;
  readonly missingMetrics: readonly TemplateTwinMetricKey[];
  readonly breachedMetrics: readonly TemplateTwinMetricKey[];
  readonly blockingReasons: readonly string[];
  readonly canonicalSha256: string;
}

export function evaluateTemplateTwinMetricSnapshot(input: {
  readonly releaseIdentitySha256: string;
  readonly policy: TemplateTwinGuardrailPolicy;
  readonly policySha256: string;
  readonly stage: TemplateTwinReleaseStage;
  readonly checkpointActivatedAt: Date;
  readonly sampleCount: number;
  readonly observationStartedAt: Date;
  readonly observationEndedAt: Date;
  readonly metrics: unknown;
  readonly now?: Date;
}): TemplateTwinMetricEvaluation {
  if (
    !SHA256.test(input.releaseIdentitySha256) ||
    !SHA256.test(input.policySha256) ||
    templateTwinGuardrailPolicySha256(input.policy) !== input.policySha256 ||
    !safeInteger(input.sampleCount, 0, 1_000_000_000) ||
    !isPlainRecord(input.metrics)
  ) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_METRIC_SNAPSHOT_INVALID",
      "Metric snapshot identity, count, or aggregate map is invalid.",
    );
  }
  const now = input.now ?? new Date();
  for (const date of [
    input.checkpointActivatedAt,
    input.observationStartedAt,
    input.observationEndedAt,
    now,
  ]) {
    if (!Number.isFinite(date.getTime())) {
      throw new TemplateTwinReleaseContractError(
        "TEMPLATE_TWIN_METRIC_SNAPSHOT_INVALID",
        "Metric snapshot timestamps are invalid.",
      );
    }
  }

  const metricKeys = Object.keys(
    TEMPLATE_TWIN_METRIC_DEFINITIONS,
  ) as TemplateTwinMetricKey[];
  const unknownKeys = Object.keys(input.metrics).filter(
    (key) => !metricKeys.includes(key as TemplateTwinMetricKey),
  );
  if (unknownKeys.length > 0) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_METRIC_SNAPSHOT_PHI_RISK",
      "Metric snapshots accept only the versioned aggregate key set.",
    );
  }

  const metrics: Partial<Record<TemplateTwinMetricKey, number>> = {};
  for (const [key, rawValue] of Object.entries(input.metrics)) {
    const typedKey = key as TemplateTwinMetricKey;
    const definition = TEMPLATE_TWIN_METRIC_DEFINITIONS[typedKey];
    if (
      typeof rawValue !== "number" ||
      !Number.isFinite(rawValue) ||
      rawValue < definition.min ||
      rawValue > definition.max
    ) {
      throw new TemplateTwinReleaseContractError(
        "TEMPLATE_TWIN_METRIC_SNAPSHOT_PHI_RISK",
        "Metric values must be finite, bounded aggregate numbers; free text is forbidden.",
      );
    }
    metrics[typedKey] = rawValue;
  }

  const missingMetrics = metricKeys.filter((key) => metrics[key] === undefined);
  const breachedMetrics = metricKeys.filter((key) => {
    const value = metrics[key];
    if (value === undefined) return false;
    const rule = input.policy.metrics[key];
    return rule.direction === "MAX"
      ? value > rule.threshold
      : value < rule.threshold;
  });
  const criticalBreach = breachedMetrics.some(
    (key) => input.policy.metrics[key].critical,
  );
  const blockingReasons: string[] = [];
  const intervalMs =
    input.observationEndedAt.getTime() - input.observationStartedAt.getTime();
  if (intervalMs <= 0) blockingReasons.push("OBSERVATION_INTERVAL_INVALID");
  if (input.observationStartedAt < input.checkpointActivatedAt) {
    blockingReasons.push("OBSERVATION_PRECEDES_CHECKPOINT");
  }
  if (input.observationEndedAt > now) {
    blockingReasons.push("OBSERVATION_ENDS_IN_FUTURE");
  }
  if (
    now.getTime() - input.observationEndedAt.getTime() >
    input.policy.maxObservationAgeSeconds * 1000
  ) {
    blockingReasons.push("OBSERVATION_STALE");
  }
  if (intervalMs < input.policy.minimumBakeSecondsByStage[input.stage] * 1000) {
    blockingReasons.push("BAKE_INTERVAL_INSUFFICIENT");
  }
  if (input.sampleCount < input.policy.minimumSampleCountByStage[input.stage]) {
    blockingReasons.push("SAMPLE_COUNT_INSUFFICIENT");
  }
  if (missingMetrics.length > 0)
    blockingReasons.push("REQUIRED_METRICS_MISSING");
  if (breachedMetrics.length > 0) blockingReasons.push("THRESHOLD_BREACH");

  const evaluation = criticalBreach
    ? "CRITICAL_REVOKE"
    : blockingReasons.length > 0
      ? "BLOCK"
      : "PASS";
  const snapshotPayload = {
    version: "template-twin-metric-snapshot-v1",
    releaseIdentitySha256: input.releaseIdentitySha256,
    policySha256: input.policySha256,
    schemaVersion: input.policy.schemaVersion,
    stage: input.stage,
    sampleCount: input.sampleCount,
    observationStartedAt: input.observationStartedAt.toISOString(),
    observationEndedAt: input.observationEndedAt.toISOString(),
    metrics,
    evaluation,
    missingMetrics,
    breachedMetrics,
    blockingReasons,
  };
  return {
    evaluation,
    metrics,
    missingMetrics,
    breachedMetrics,
    blockingReasons,
    canonicalSha256: canonicalSha256(snapshotPayload),
  };
}

export function templateTwinApprovalConfirmation(input: {
  readonly decision: TemplateTwinApprovalDecision;
  readonly discipline: TemplateTwinReleaseDiscipline;
  readonly releaseIdentitySha256: string;
}): string {
  if (!SHA256.test(input.releaseIdentitySha256)) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_IDENTITY_INVALID",
      "Release identity is invalid.",
    );
  }
  return `${input.decision} ${input.discipline} ${input.releaseIdentitySha256.slice(0, 12)}`;
}

export function templateTwinCheckpointConfirmation(input: {
  readonly verb: "ACTIVATE" | "PASS";
  readonly stage: TemplateTwinReleaseStage;
  readonly releaseIdentitySha256: string;
}): string {
  if (!SHA256.test(input.releaseIdentitySha256)) {
    throw new TemplateTwinReleaseContractError(
      "TEMPLATE_TWIN_RELEASE_IDENTITY_INVALID",
      "Release identity is invalid.",
    );
  }
  return `${input.verb} ${input.stage} ${input.releaseIdentitySha256.slice(0, 12)}`;
}

export class TemplateTwinReleaseContractError extends Error {
  constructor(
    readonly code:
      | "TEMPLATE_TWIN_RELEASE_IDENTITY_INVALID"
      | "TEMPLATE_TWIN_RELEASE_MANIFEST_INVALID"
      | "TEMPLATE_TWIN_RUNTIME_MANIFEST_INVALID"
      | "TEMPLATE_TWIN_GUARDRAIL_POLICY_INVALID"
      | "TEMPLATE_TWIN_METRIC_SNAPSHOT_INVALID"
      | "TEMPLATE_TWIN_METRIC_SNAPSHOT_PHI_RISK",
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinReleaseContractError";
  }
}
