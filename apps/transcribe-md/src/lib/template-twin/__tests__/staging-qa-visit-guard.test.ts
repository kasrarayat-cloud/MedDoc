import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  assertTemplateTwinStagingQaVisitGuard,
  lockAndAssertTemplateTwinStagingQaAttempt,
  lockAndAssertTemplateTwinStagingQaOperation,
  templateTwinStagingQaDestinationsAreAllowed,
  TemplateTwinStagingQaVisitGuardError,
  type TemplateTwinStagingQaRunGuardRow,
} from "../staging-qa-visit-guard";
import { TemplateTwinStagingQaDisabledError } from "../staging-qa-gate";

const SAFE_ENV = {
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  MOCK_AI_CALLS: "true",
  MOCK_TEMPLATE_TWIN_E2E: "true",
  DATABASE_URL: "postgresql://synthetic:synthetic@localhost/template_twin_test",
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
} as const;

function run(
  overrides: Partial<TemplateTwinStagingQaRunGuardRow> = {},
): TemplateTwinStagingQaRunGuardRow {
  return {
    id: "run-synthetic-1",
    practiceId: "practice-synthetic-1",
    doctorId: "doctor-synthetic-1",
    fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
    attempt: 2,
    pinnedGlobalRolloutGeneration: BigInt(7),
    pinnedPracticeRolloutGeneration: BigInt(11),
    ...overrides,
  };
}

const token = {
  practiceId: "practice-synthetic-1",
  globalGeneration: BigInt(7),
  practiceGeneration: BigInt(11),
};

beforeEach(() => {
  vi.unstubAllEnvs();
  for (const [key, value] of Object.entries(SAFE_ENV)) vi.stubEnv(key, value);
});

describe("synthetic QA visit admission", () => {
  it("preserves normal visit behavior without consulting the staging process gate", () => {
    vi.stubEnv("TEMPLATE_TWIN_STAGING_QA_ENABLED", "false");
    expect(
      assertTemplateTwinStagingQaVisitGuard({
        run: null,
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: token,
      }),
    ).toEqual({ applies: false });
  });

  it("fails closed when a marked visit is accessed with the process gate off", () => {
    vi.stubEnv("TEMPLATE_TWIN_STAGING_QA_ENABLED", "false");
    expect(() =>
      assertTemplateTwinStagingQaVisitGuard({
        run: run(),
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: token,
      }),
    ).toThrow(TemplateTwinStagingQaDisabledError);
  });

  it.each([
    ["doctor", { userId: "doctor-other", practiceId: "practice-synthetic-1" }],
    [
      "practice",
      { userId: "doctor-synthetic-1", practiceId: "practice-other" },
    ],
  ] as const)(
    "returns a non-revealing ownership failure for another %s",
    (_label, actor) => {
      expect(() =>
        assertTemplateTwinStagingQaVisitGuard({
          run: run(),
          actor,
          currentRolloutToken: { ...token, practiceId: actor.practiceId },
        }),
      ).toThrowError(
        expect.objectContaining({ code: "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND" }),
      );
    },
  );

  it("rejects an old generation after disable and re-enable", () => {
    expect(() =>
      assertTemplateTwinStagingQaVisitGuard({
        run: run(),
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: {
          ...token,
          globalGeneration: BigInt(9),
          practiceGeneration: BigInt(13),
        },
      }),
    ).toThrowError(
      expect.objectContaining({
        code: "TEMPLATE_TWIN_STAGING_QA_ROLLOUT_STALE",
      }),
    );
  });

  it("permits no delivery or one Original Template DOCX and rejects every external/generic destination", () => {
    expect(templateTwinStagingQaDestinationsAreAllowed(run(), [])).toBe(true);
    expect(
      templateTwinStagingQaDestinationsAreAllowed(run(), [
        "docx_original_template",
      ]),
    ).toBe(true);
    for (const destination of [
      "email",
      "pdf",
      "docx",
      "clipboard_epic",
      "clipboard_generic",
    ]) {
      expect(
        templateTwinStagingQaDestinationsAreAllowed(run(), [destination]),
      ).toBe(false);
    }
    expect(
      templateTwinStagingQaDestinationsAreAllowed(run(), [
        "docx_original_template",
        "docx_original_template",
      ]),
    ).toBe(false);
  });

  it("locks and rejects a stale worker attempt before the output claim", async () => {
    const queryRaw = vi
      .fn()
      .mockResolvedValueOnce([
        {
          ...run(),
          visitId: "visit-synthetic-1",
          requestSha256: "a".repeat(64),
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          status: "ENQUEUED",
          attempt: 2,
          enqueuedAt: new Date("2026-07-17T00:00:00Z"),
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          role: "DOCTOR",
          isActive: true,
        },
      ]);
    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: { $queryRaw: queryRaw },
        currentRolloutToken: token,
        claim: {
          runId: "run-synthetic-1",
          visitId: "visit-synthetic-1",
          practiceId: "practice-synthetic-1",
          doctorId: "doctor-synthetic-1",
          fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
          requestSha256: "a".repeat(64),
          attempt: 1,
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          pinnedGlobalGeneration: BigInt(7),
          pinnedPracticeGeneration: BigInt(11),
        },
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
    });
    expect(queryRaw).toHaveBeenCalledTimes(1);
  });

  it("accepts the exact durable run and attempt under the current epoch", async () => {
    const queryRaw = vi
      .fn()
      .mockResolvedValueOnce([
        {
          ...run(),
          visitId: "visit-synthetic-1",
          requestSha256: "a".repeat(64),
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          status: "ENQUEUED",
          attempt: 2,
          enqueuedAt: new Date("2026-07-17T00:00:00Z"),
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          role: "DOCTOR",
          isActive: true,
        },
      ]);
    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: { $queryRaw: queryRaw },
        currentRolloutToken: token,
        claim: {
          runId: "run-synthetic-1",
          visitId: "visit-synthetic-1",
          practiceId: "practice-synthetic-1",
          doctorId: "doctor-synthetic-1",
          fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
          requestSha256: "a".repeat(64),
          attempt: 2,
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          pinnedGlobalGeneration: BigInt(7),
          pinnedPracticeGeneration: BigInt(11),
        },
      }),
    ).resolves.toBeUndefined();
  });

  it("rejects a terminal claim whose worker lease expired at database time", async () => {
    const databaseNow = new Date("2026-07-17T00:00:20.000Z");
    const queryRaw = vi
      .fn()
      .mockResolvedValueOnce([
        {
          ...run(),
          visitId: "visit-synthetic-1",
          requestSha256: "a".repeat(64),
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          workerClaimedAt: new Date("2026-07-17T00:00:00.000Z"),
          workerHeartbeatAt: new Date("2026-07-17T00:00:05.000Z"),
          workerLeaseExpiresAt: databaseNow,
          status: "PROCESSING",
          enqueuedAt: new Date("2026-07-17T00:00:00.000Z"),
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          role: "DOCTOR",
          isActive: true,
        },
      ])
      .mockResolvedValueOnce([{ databaseNow }]);

    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: { $queryRaw: queryRaw },
        currentRolloutToken: token,
        claim: {
          runId: "run-synthetic-1",
          visitId: "visit-synthetic-1",
          practiceId: "practice-synthetic-1",
          doctorId: "doctor-synthetic-1",
          fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
          requestSha256: "a".repeat(64),
          attempt: 2,
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          pinnedGlobalGeneration: BigInt(7),
          pinnedPracticeGeneration: BigInt(11),
        },
        allowedStatuses: ["PROCESSING"],
        requireLiveWorkerLease: true,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
    });
  });

  it("accepts a terminal claim only while its database-time lease is live", async () => {
    const queryRaw = vi
      .fn()
      .mockResolvedValueOnce([
        {
          ...run(),
          visitId: "visit-synthetic-1",
          requestSha256: "a".repeat(64),
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          workerClaimedAt: new Date("2026-07-17T00:00:00.000Z"),
          workerHeartbeatAt: new Date("2026-07-17T00:00:05.000Z"),
          workerLeaseExpiresAt: new Date("2026-07-17T00:00:25.000Z"),
          status: "PROCESSING",
          enqueuedAt: new Date("2026-07-17T00:00:00.000Z"),
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          role: "DOCTOR",
          isActive: true,
        },
      ])
      .mockResolvedValueOnce([
        { databaseNow: new Date("2026-07-17T00:00:20.000Z") },
      ]);

    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: { $queryRaw: queryRaw },
        currentRolloutToken: token,
        claim: {
          runId: "run-synthetic-1",
          visitId: "visit-synthetic-1",
          practiceId: "practice-synthetic-1",
          doctorId: "doctor-synthetic-1",
          fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
          requestSha256: "a".repeat(64),
          attempt: 2,
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          pinnedGlobalGeneration: BigInt(7),
          pinnedPracticeGeneration: BigInt(11),
        },
        allowedStatuses: ["PROCESSING"],
        requireLiveWorkerLease: true,
      }),
    ).resolves.toBeUndefined();
  });

  it("uses post-lock wall time when lock contention crosses lease expiry", async () => {
    let releaseRunLock!: () => void;
    const runLock = new Promise<void>((resolve) => {
      releaseRunLock = resolve;
    });
    let runQueryEntered!: () => void;
    const entered = new Promise<void>((resolve) => {
      runQueryEntered = resolve;
    });
    const queryRaw = vi
      .fn()
      .mockImplementationOnce(async () => {
        runQueryEntered();
        await runLock;
        return [
          {
            ...run(),
            visitId: "visit-synthetic-1",
            requestSha256: "a".repeat(64),
            workerClaimId: "11111111-1111-4111-8111-111111111111",
            workerClaimedAt: new Date("2026-07-17T00:00:00.000Z"),
            workerHeartbeatAt: new Date("2026-07-17T00:00:05.000Z"),
            workerLeaseExpiresAt: new Date("2026-07-17T00:00:20.000Z"),
            status: "PROCESSING",
            enqueuedAt: new Date("2026-07-17T00:00:00.000Z"),
          },
        ];
      })
      .mockResolvedValueOnce([
        {
          id: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          role: "DOCTOR",
          isActive: true,
        },
      ])
      .mockResolvedValueOnce([
        { databaseNow: new Date("2026-07-17T00:00:21.000Z") },
      ]);

    const claim = lockAndAssertTemplateTwinStagingQaAttempt({
      tx: { $queryRaw: queryRaw },
      currentRolloutToken: token,
      claim: {
        runId: "run-synthetic-1",
        visitId: "visit-synthetic-1",
        practiceId: "practice-synthetic-1",
        doctorId: "doctor-synthetic-1",
        fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
        requestSha256: "a".repeat(64),
        attempt: 2,
        workerClaimId: "11111111-1111-4111-8111-111111111111",
        pinnedGlobalGeneration: BigInt(7),
        pinnedPracticeGeneration: BigInt(11),
      },
      allowedStatuses: ["PROCESSING"],
      requireLiveWorkerLease: true,
    });
    await entered;
    releaseRunLock();

    await expect(claim).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
    });
    expect(queryRaw).toHaveBeenCalledTimes(3);
  });

  it("rejects the old worker after the same attempt is lease-reclaimed", async () => {
    const queryRaw = vi
      .fn()
      .mockResolvedValueOnce([
        {
          ...run(),
          visitId: "visit-synthetic-1",
          requestSha256: "a".repeat(64),
          workerClaimId: "22222222-2222-4222-8222-222222222222",
          status: "PROCESSING",
          attempt: 2,
          enqueuedAt: new Date("2026-07-17T00:00:00Z"),
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          role: "DOCTOR",
          isActive: true,
        },
      ]);
    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: { $queryRaw: queryRaw },
        currentRolloutToken: token,
        claim: {
          runId: "run-synthetic-1",
          visitId: "visit-synthetic-1",
          practiceId: "practice-synthetic-1",
          doctorId: "doctor-synthetic-1",
          fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
          requestSha256: "a".repeat(64),
          attempt: 2,
          workerClaimId: "11111111-1111-4111-8111-111111111111",
          pinnedGlobalGeneration: BigInt(7),
          pinnedPracticeGeneration: BigInt(11),
        },
        allowedStatuses: ["PROCESSING"],
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
    });
    expect(queryRaw).toHaveBeenCalledTimes(2);
  });

  it("rejects signing, correction, or download claims from a prior attempt", async () => {
    const queryRaw = vi.fn().mockResolvedValue([
      {
        ...run({ attempt: 4 }),
        visitId: "visit-synthetic-1",
        requestSha256: "a".repeat(64),
        status: "ENQUEUED",
        enqueuedAt: new Date("2026-07-17T00:00:00Z"),
      },
    ]);
    await expect(
      lockAndAssertTemplateTwinStagingQaOperation({
        tx: { $queryRaw: queryRaw },
        runId: "run-synthetic-1",
        expectedAttempt: 3,
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: token,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
    });
  });
});

describe("synthetic QA guard error contract", () => {
  it("keeps stable physician-facing codes", () => {
    expect(
      new TemplateTwinStagingQaVisitGuardError(
        "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
        "Synthetic retry required.",
      ),
    ).toMatchObject({
      name: "TemplateTwinStagingQaVisitGuardError",
      code: "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
    });
  });
});
