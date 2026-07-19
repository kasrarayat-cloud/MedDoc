import { describe, expect, it } from "vitest";

import {
  buildTemplateTwinCohortPlan,
  evaluateTemplateTwinMetricSnapshot,
  parseTemplateTwinGuardrailPolicy,
  templateTwinApprovalConfirmation,
  templateTwinGuardrailPolicySha256,
  templateTwinReleaseIdentitySha256,
  TEMPLATE_TWIN_GUARDRAIL_SCHEMA_VERSION,
  TEMPLATE_TWIN_METRIC_DEFINITIONS,
  TEMPLATE_TWIN_RELEASE_STAGES,
  type TemplateTwinGuardrailPolicy,
  type TemplateTwinMetricKey,
} from "../release-control-contracts";

const sha = (character: string) => character.repeat(64);
const commit = (character: string) => character.repeat(40);
const image = (character: string) => `sha256:${character.repeat(64)}`;

function policy(): TemplateTwinGuardrailPolicy {
  const metrics = Object.fromEntries(
    Object.entries(TEMPLATE_TWIN_METRIC_DEFINITIONS).map(
      ([key, definition]) => [
        key,
        {
          direction: definition.direction,
          threshold: definition.direction === "MAX" ? 0.1 : 0.9,
          critical: [
            "unsafe_bypass_attempt_count",
            "provider_ambiguous_outcome_count",
            "critical_field_accuracy",
            "hallucination_rate",
            "evidence_anchor_validity",
            "exact_dropdown_accuracy",
            "negation_accuracy",
            "laterality_accuracy",
            "table_placement_accuracy",
          ].includes(key),
        },
      ],
    ),
  ) as unknown as TemplateTwinGuardrailPolicy["metrics"];
  return {
    schemaVersion: TEMPLATE_TWIN_GUARDRAIL_SCHEMA_VERSION,
    maxObservationAgeSeconds: 600,
    minimumBakeSecondsByStage: {
      CANARY: 60,
      PERCENT_10: 60,
      PERCENT_25: 60,
      PERCENT_50: 60,
      PERCENT_100: 60,
    },
    minimumSampleCountByStage: {
      CANARY: 5,
      PERCENT_10: 5,
      PERCENT_25: 5,
      PERCENT_50: 5,
      PERCENT_100: 5,
    },
    metrics,
  };
}

function passingMetrics(
  guardrails: TemplateTwinGuardrailPolicy,
): Record<TemplateTwinMetricKey, number> {
  return Object.fromEntries(
    Object.entries(guardrails.metrics).map(([key, rule]) => [
      key,
      rule.direction === "MAX" ? 0 : 1,
    ]),
  ) as Record<TemplateTwinMetricKey, number>;
}

describe("Template Twin production release identity", () => {
  it("binds commits, all three images, every evidence class, policy, and manifest", () => {
    const input = {
      sourceCommitSha: commit("a"),
      baseCommitSha: commit("b"),
      appImageDigest: image("c"),
      workerImageDigest: image("d"),
      migratorImageDigest: image("e"),
      testCensusEvidenceSha256: sha("1"),
      independentReviewEvidenceSha256: sha("2"),
      securityEvidenceSha256: sha("3"),
      migrationRestoreEvidenceSha256: sha("4"),
      officeWordEvidenceSha256: sha("5"),
      guardrailPolicySha256: sha("6"),
      authorizedPracticeManifestSha256: sha("7"),
    };
    const identity = templateTwinReleaseIdentitySha256(input);
    expect(identity).toMatch(/^[0-9a-f]{64}$/u);
    expect(
      templateTwinReleaseIdentitySha256({
        ...input,
        workerImageDigest: image("f"),
      }),
    ).not.toBe(identity);
    expect(() =>
      templateTwinReleaseIdentitySha256({
        ...input,
        sourceCommitSha: "main",
      }),
    ).toThrow(/exact lowercase 40-character SHAs/u);
  });

  it("uses exact typed human confirmation bound to discipline and identity", () => {
    expect(
      templateTwinApprovalConfirmation({
        decision: "APPROVE",
        discipline: "CLINICAL_SAFETY",
        releaseIdentitySha256: sha("a"),
      }),
    ).toBe("APPROVE CLINICAL_SAFETY aaaaaaaaaaaa");
  });
});

describe("Template Twin authorized practice cohorts", () => {
  it("keeps explicit canaries first, reports practice-granularity overshoot, and includes all at 100%", () => {
    const plan = buildTemplateTwinCohortPlan({
      sourceCommitSha: commit("a"),
      practices: [
        {
          practiceId: "practice-a",
          practiceSlug: "practice-a",
          physicianCount: 2,
        },
        {
          practiceId: "practice-b",
          practiceSlug: "practice-b",
          physicianCount: 6,
        },
        {
          practiceId: "practice-c",
          practiceSlug: "practice-c",
          physicianCount: 2,
        },
      ],
      canaryPracticeIds: ["practice-a"],
    });
    expect(plan.practices[0]).toMatchObject({
      practiceId: "practice-a",
      cohortRank: 1,
      isCanary: true,
      activationStage: "CANARY",
    });
    expect(plan.checkpoints).toHaveLength(5);
    expect(plan.checkpoints[1]).toMatchObject({
      stage: "PERCENT_10",
      targetPhysicianCount: 1,
      assignedPhysicianCount: 2,
    });
    expect(plan.checkpoints.at(-1)).toMatchObject({
      stage: "PERCENT_100",
      targetPhysicianCount: 10,
      assignedPhysicianCount: 10,
    });
    expect(plan.practices.every(({ activationStage }) => activationStage)).toBe(
      true,
    );
    expect(plan.authorizedPracticeManifestSha256).toMatch(/^[0-9a-f]{64}$/u);
  });

  it("is deterministic across input order but changes when the frozen count changes", () => {
    const practices = [
      {
        practiceId: "practice-a",
        practiceSlug: "practice-a",
        physicianCount: 2,
      },
      {
        practiceId: "practice-b",
        practiceSlug: "practice-b",
        physicianCount: 3,
      },
    ];
    const first = buildTemplateTwinCohortPlan({
      sourceCommitSha: commit("b"),
      practices,
      canaryPracticeIds: ["practice-a"],
    });
    const reordered = buildTemplateTwinCohortPlan({
      sourceCommitSha: commit("b"),
      practices: [...practices].reverse(),
      canaryPracticeIds: ["practice-a"],
    });
    expect(reordered).toEqual(first);
    const changed = buildTemplateTwinCohortPlan({
      sourceCommitSha: commit("b"),
      practices: [{ ...practices[0]!, physicianCount: 4 }, practices[1]!],
      canaryPracticeIds: ["practice-a"],
    });
    expect(changed.authorizedPracticeManifestSha256).not.toBe(
      first.authorizedPracticeManifestSha256,
    );
  });
});

describe("Template Twin PHI-free guardrails", () => {
  it("requires the exact metric policy and critical safety floors", () => {
    const valid = policy();
    expect(parseTemplateTwinGuardrailPolicy(valid)).toEqual(valid);
    expect(templateTwinGuardrailPolicySha256(valid)).toMatch(/^[0-9a-f]{64}$/u);
    expect(() =>
      parseTemplateTwinGuardrailPolicy({
        ...valid,
        patient_metric: { direction: "MAX", threshold: 1, critical: false },
      }),
    ).toThrow(/shape or version/u);
    expect(() =>
      parseTemplateTwinGuardrailPolicy({
        ...valid,
        metrics: {
          ...valid.metrics,
          hallucination_rate: {
            ...valid.metrics.hallucination_rate,
            critical: false,
          },
        },
      }),
    ).toThrow(/hallucination_rate/u);
  });

  it("passes only a fresh, complete, baked, sufficiently sampled snapshot", () => {
    const guardrails = policy();
    const started = new Date("2026-07-19T12:00:01.000Z");
    const ended = new Date("2026-07-19T12:01:01.000Z");
    const result = evaluateTemplateTwinMetricSnapshot({
      releaseIdentitySha256: sha("a"),
      policy: guardrails,
      policySha256: templateTwinGuardrailPolicySha256(guardrails),
      stage: "CANARY",
      checkpointActivatedAt: new Date("2026-07-19T12:00:00.000Z"),
      sampleCount: 5,
      observationStartedAt: started,
      observationEndedAt: ended,
      metrics: passingMetrics(guardrails),
      now: new Date("2026-07-19T12:01:02.000Z"),
    });
    expect(result).toMatchObject({
      evaluation: "PASS",
      missingMetrics: [],
      breachedMetrics: [],
      blockingReasons: [],
    });
  });

  it("blocks absent metrics and automatically classifies a critical threshold breach", () => {
    const guardrails = policy();
    const shared = {
      releaseIdentitySha256: sha("b"),
      policy: guardrails,
      policySha256: templateTwinGuardrailPolicySha256(guardrails),
      stage: "CANARY" as const,
      checkpointActivatedAt: new Date("2026-07-19T12:00:00.000Z"),
      sampleCount: 5,
      observationStartedAt: new Date("2026-07-19T12:00:01.000Z"),
      observationEndedAt: new Date("2026-07-19T12:01:01.000Z"),
      now: new Date("2026-07-19T12:01:02.000Z"),
    };
    expect(
      evaluateTemplateTwinMetricSnapshot({ ...shared, metrics: {} }),
    ).toMatchObject({
      evaluation: "BLOCK",
      blockingReasons: expect.arrayContaining(["REQUIRED_METRICS_MISSING"]),
    });
    expect(
      evaluateTemplateTwinMetricSnapshot({
        ...shared,
        metrics: {
          ...passingMetrics(guardrails),
          hallucination_rate: 0.2,
        },
      }),
    ).toMatchObject({
      evaluation: "CRITICAL_REVOKE",
      breachedMetrics: ["hallucination_rate"],
    });
  });

  it("rejects unknown keys and all non-numeric values before persistence", () => {
    const guardrails = policy();
    const base = {
      releaseIdentitySha256: sha("c"),
      policy: guardrails,
      policySha256: templateTwinGuardrailPolicySha256(guardrails),
      stage: TEMPLATE_TWIN_RELEASE_STAGES[0].stage,
      checkpointActivatedAt: new Date("2026-07-19T12:00:00.000Z"),
      sampleCount: 5,
      observationStartedAt: new Date("2026-07-19T12:00:01.000Z"),
      observationEndedAt: new Date("2026-07-19T12:01:01.000Z"),
      now: new Date("2026-07-19T12:01:02.000Z"),
    };
    expect(() =>
      evaluateTemplateTwinMetricSnapshot({
        ...base,
        metrics: { patient_id: 123 },
      }),
    ).toThrow(/versioned aggregate key set/u);
    expect(() =>
      evaluateTemplateTwinMetricSnapshot({
        ...base,
        metrics: { error_rate: "patient-like narrative" },
      }),
    ).toThrow(/finite, bounded aggregate numbers/u);
  });
});
