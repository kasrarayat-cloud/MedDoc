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
  const base: TemplateTwinStagingQaRunGuardRow = {
    id: "run-synthetic-1",
    admissionId: "admission-synthetic-1",
    visitId: "visit-synthetic-1",
    practiceId: "practice-synthetic-1",
    doctorId: "doctor-synthetic-1",
    noteTemplateId: "template-synthetic-1",
    noteTemplateVersion: 4,
    requestSha256: "a".repeat(64),
    payloadSha256: "b".repeat(64),
    mode: "typed",
    status: "COMPLETED",
    fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
    attempt: 2,
    pinnedGlobalRolloutGeneration: BigInt(7),
    pinnedPracticeRolloutGeneration: BigInt(11),
    admission: {
      id: "admission-synthetic-1",
      practiceId: "practice-synthetic-1",
      actorId: "doctor-synthetic-1",
      parentAdmissionId: "admission-upload-synthetic-1",
      sourceSha256:
        "9c917a831e661d5fdcf92a6e13cbc542adda9fb86a2292cf34689fc333c375d4",
      sourceSizeBytes: 4686,
      fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
      providerMode: "SYNTHETIC_TYPED",
      purpose: "VISIT",
      phase: "REVIEW_READY",
      requestSha256: "a".repeat(64),
      payloadSha256: "b".repeat(64),
      pinnedGlobalRolloutGeneration: BigInt(7),
      pinnedPracticeRolloutGeneration: BigInt(11),
      sourceArtifactId: "source-synthetic-1",
      noteTemplateId: "template-synthetic-1",
      noteTemplateVersion: 4,
      certificationId: "certification-synthetic-1",
      mappingSha256: "c".repeat(64),
      visitId: "visit-synthetic-1",
      attempt: 2,
      expiresAt: new Date("2099-07-17T00:00:00.000Z"),
      failedAt: null,
      revokedAt: null,
      consumedAt: null,
    },
  };
  const merged = { ...base, ...overrides };
  return overrides.admission === undefined
    ? {
        ...merged,
        admission: {
          ...base.admission!,
          requestSha256: merged.requestSha256,
          payloadSha256: merged.payloadSha256,
          noteTemplateId: merged.noteTemplateId,
          noteTemplateVersion: merged.noteTemplateVersion,
          visitId: merged.visitId,
          attempt: merged.attempt,
          pinnedGlobalRolloutGeneration:
            merged.pinnedGlobalRolloutGeneration,
          pinnedPracticeRolloutGeneration:
            merged.pinnedPracticeRolloutGeneration,
        },
      }
    : merged;
}

const token = {
  practiceId: "practice-synthetic-1",
  globalGeneration: BigInt(7),
  practiceGeneration: BigInt(11),
};

function lockedClient(input: {
  lockedRun: TemplateTwinStagingQaRunGuardRow & {
    enqueuedAt: Date | null;
    workerClaimId: string | null;
    workerClaimedAt: Date | null;
    workerHeartbeatAt: Date | null;
    workerLeaseExpiresAt: Date | null;
    workerDeliveryCount: number;
    workerRetryReadyAt: Date | null;
  };
  databaseNow?: Date;
  beforeRunLock?: () => Promise<void>;
}) {
  const admissionPhase =
    input.lockedRun.status === "PROCESSING" ||
    input.lockedRun.status === "RETRY_ENQUEUED"
      ? "PROCESSING"
      : input.lockedRun.status === "ENQUEUED"
        ? "VISIT_LINKED"
        : "REVIEW_READY";
  const admission = {
    ...input.lockedRun.admission!,
    phase: admissionPhase,
    attempt: input.lockedRun.attempt,
  };
  const queryRaw = vi.fn(async (query: { strings?: readonly string[] }) => {
    const sql = query.strings?.join(" ") ?? "";
    if (sql.includes('SELECT "admissionId"')) {
      return [{ admissionId: input.lockedRun.admissionId }];
    }
    if (sql.includes('FROM "template_twin_synthetic_qa_admissions"')) {
      return [admission];
    }
    if (sql.includes('FROM "template_twin_synthetic_qa_runs"')) {
      await input.beforeRunLock?.();
      return [input.lockedRun];
    }
    if (sql.includes('FROM "users"')) {
      return [
        {
          id: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          role: "DOCTOR",
          isActive: true,
        },
      ];
    }
    if (sql.includes("clock_timestamp()")) {
      return [
        {
          databaseNow:
            input.databaseNow ?? new Date("2026-07-17T00:00:20.000Z"),
        },
      ];
    }
    throw new Error(`Unexpected synthetic lock query: ${sql}`);
  });
  return {
    $queryRaw: queryRaw as unknown as <T>(query: unknown) => Promise<T>,
    queryRaw,
  };
}

function lockedRun(
  overrides: Partial<ReturnType<typeof run>> & {
    enqueuedAt?: Date | null;
    workerClaimId?: string | null;
    workerClaimedAt?: Date | null;
    workerHeartbeatAt?: Date | null;
    workerLeaseExpiresAt?: Date | null;
    workerDeliveryCount?: number;
    workerRetryReadyAt?: Date | null;
  } = {},
) {
  return {
    ...run(),
    status: "ENQUEUED",
    enqueuedAt: new Date("2026-07-17T00:00:00.000Z"),
    workerClaimId: "11111111-1111-4111-8111-111111111111",
    workerClaimedAt: null,
    workerHeartbeatAt: null,
    workerLeaseExpiresAt: null,
    workerDeliveryCount: 0,
    workerRetryReadyAt: null,
    ...overrides,
  };
}

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

  it("rejects a missing durable run whenever synthetic QA is requested", () => {
    expect(() =>
      assertTemplateTwinStagingQaVisitGuard({
        run: null,
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: token,
      }),
    ).toThrowError(
      expect.objectContaining({
        code: "TEMPLATE_TWIN_STAGING_QA_NOT_FOUND",
      }),
    );
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

  it("rejects a consumed admission before the SIGNED phase", () => {
    const current = run();
    expect(() =>
      assertTemplateTwinStagingQaVisitGuard({
        run: {
          ...current,
          admission: {
            ...current.admission!,
            consumedAt: new Date("2026-07-17T00:00:00.000Z"),
          },
        },
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: token,
      }),
    ).toThrowError(
      expect.objectContaining({
        code: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
      }),
    );
  });

  it("requires signed download admission to carry its atomic consumption proof", () => {
    const current = run();
    expect(() =>
      assertTemplateTwinStagingQaVisitGuard({
        run: {
          ...current,
          admission: { ...current.admission!, phase: "SIGNED" },
        },
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: token,
        allowedAdmissionPhases: ["SIGNED"],
      }),
    ).toThrowError(
      expect.objectContaining({
        code: "TEMPLATE_TWIN_STAGING_QA_ADMISSION_STALE",
      }),
    );

    expect(
      assertTemplateTwinStagingQaVisitGuard({
        run: {
          ...current,
          admission: {
            ...current.admission!,
            phase: "SIGNED",
            consumedAt: new Date("2026-07-17T00:00:00.000Z"),
          },
        },
        actor: {
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
        },
        currentRolloutToken: token,
        allowedAdmissionPhases: ["SIGNED"],
      }),
    ).toEqual({ applies: true, runId: "run-synthetic-1" });
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
    const client = lockedClient({ lockedRun: lockedRun() });
    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: client,
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
    expect(client.queryRaw).toHaveBeenCalled();
  });

  it("accepts the exact durable run and attempt under the current epoch", async () => {
    const client = lockedClient({ lockedRun: lockedRun() });
    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: client,
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
    const client = lockedClient({
      databaseNow,
      lockedRun: lockedRun({
        status: "PROCESSING",
        workerClaimedAt: new Date("2026-07-17T00:00:00.000Z"),
        workerHeartbeatAt: new Date("2026-07-17T00:00:05.000Z"),
        workerLeaseExpiresAt: databaseNow,
      }),
    });

    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: client,
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
    const client = lockedClient({
      lockedRun: lockedRun({
        status: "PROCESSING",
        workerClaimedAt: new Date("2026-07-17T00:00:00.000Z"),
        workerHeartbeatAt: new Date("2026-07-17T00:00:05.000Z"),
        workerLeaseExpiresAt: new Date("2026-07-17T00:00:25.000Z"),
      }),
    });

    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: client,
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
    const client = lockedClient({
      databaseNow: new Date("2026-07-17T00:00:21.000Z"),
      beforeRunLock: async () => {
        runQueryEntered();
        await runLock;
      },
      lockedRun: lockedRun({
        status: "PROCESSING",
        workerClaimedAt: new Date("2026-07-17T00:00:00.000Z"),
        workerHeartbeatAt: new Date("2026-07-17T00:00:05.000Z"),
        workerLeaseExpiresAt: new Date("2026-07-17T00:00:20.000Z"),
      }),
    });

    const claim = lockAndAssertTemplateTwinStagingQaAttempt({
      tx: client,
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
    expect(client.queryRaw).toHaveBeenCalled();
  });

  it("rejects the old worker after the same attempt is lease-reclaimed", async () => {
    const client = lockedClient({
      lockedRun: lockedRun({
        status: "PROCESSING",
        workerClaimId: "22222222-2222-4222-8222-222222222222",
      }),
    });
    await expect(
      lockAndAssertTemplateTwinStagingQaAttempt({
        tx: client,
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
    expect(client.queryRaw).toHaveBeenCalled();
  });

  it("rejects signing, correction, or download claims from a prior attempt", async () => {
    const client = lockedClient({
      lockedRun: lockedRun({ attempt: 4 }),
    });
    await expect(
      lockAndAssertTemplateTwinStagingQaOperation({
        tx: client,
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
