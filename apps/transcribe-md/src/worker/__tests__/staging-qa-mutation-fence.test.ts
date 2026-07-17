import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
  TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  runWithTemplateTwinSyntheticQaProviderContext,
  type SyntheticQaProviderEnvironment,
} from "@meddoc/ai";
import { TranscribeVisitStatus } from "@prisma/client";

import { TemplateTwinStagingQaVisitGuardError } from "../../lib/template-twin/staging-qa-visit-guard";

const mocks = vi.hoisted(() => ({
  transaction: vi.fn(),
  rootUpdate: vi.fn(),
  lockRollout: vi.fn(),
  lockAttempt: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: {
    $transaction: mocks.transaction,
    transcribeVisit: { update: mocks.rootUpdate },
  },
}));
vi.mock("@/lib/template-twin/rollout", () => ({
  lockTemplateTwinRolloutForFinalClaim: mocks.lockRollout,
}));
vi.mock("@/lib/template-twin/staging-qa-visit-guard", async (original) => ({
  ...(await original<
    typeof import("../../lib/template-twin/staging-qa-visit-guard")
  >()),
  lockAndAssertTemplateTwinStagingQaAttempt: mocks.lockAttempt,
}));

import {
  TemplateTwinSyntheticQaMutationFenceError,
  updateTemplateTwinSyntheticQaClaimBoundVisit,
} from "../staging-qa-mutation-fence";

const SAFE_ENV: SyntheticQaProviderEnvironment = {
  TEMPLATE_TWIN_STAGING_QA_ENABLED: "true",
  TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "test",
  TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION: "isolated-disposable-qa-v1",
  TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
  DATABASE_URL: "postgresql:///meddoc_qa_test",
  REDIS_URL: "redis://redis:6379/15",
  MINIO_ENDPOINT: "minio:9000",
  MINIO_USE_SSL: "false",
  TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
  TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
  MOCK_AI_CALLS: "true",
  MOCK_TEMPLATE_TWIN_E2E: "true",
};

function context(workerClaimId: string) {
  return {
    mode: TEMPLATE_TWIN_SYNTHETIC_QA_MODE,
    fixtureVersion: TEMPLATE_TWIN_SYNTHETIC_QA_FIXTURE_VERSION,
    runId: "run-synthetic-1",
    visitId: "visit-synthetic-1",
    practiceId: "practice-synthetic-1",
    requestSha256: "a".repeat(64),
    attempt: 1,
    workerClaimId,
    pinnedGlobalGeneration: BigInt(11),
    pinnedPracticeGeneration: BigInt(19),
    evidenceText: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  } as const;
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset();
});

describe("synthetic QA intermediate-write claim fence", () => {
  it("preserves the ordinary worker's direct mutation path", async () => {
    mocks.rootUpdate.mockResolvedValue({});

    await updateTemplateTwinSyntheticQaClaimBoundVisit({
      visitId: "visit-ordinary-1",
      userId: "doctor-ordinary-1",
      practiceId: "practice-ordinary-1",
      data: { status: TranscribeVisitStatus.DRAFTING },
    });

    expect(mocks.transaction).not.toHaveBeenCalled();
    expect(mocks.rootUpdate).toHaveBeenCalledWith({
      where: { id: "visit-ordinary-1" },
      data: { status: TranscribeVisitStatus.DRAFTING },
    });
  });

  it("lets replacement B complete and prevents stale A from regressing status or derived fields", async () => {
    const claimA = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
    const claimB = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
    let currentClaim = claimA;
    const visitState: {
      status: TranscribeVisitStatus;
      soapDraft: string | null;
    } = {
      status: TranscribeVisitStatus.DRAFTING,
      soapDraft: "synthetic draft from A before lease expiry",
    };
    const order: string[] = [];
    const tx = {
      $queryRaw: vi.fn(async () => {
        order.push("visit");
        return [
          {
            id: "visit-synthetic-1",
            userId: "doctor-synthetic-1",
            status: visitState.status,
            deletedAt: null,
            archivedAt: null,
          },
        ];
      }),
      transcribeVisit: {
        update: vi.fn(async (input: { data: typeof visitState }) => {
          order.push("mutation");
          Object.assign(visitState, input.data);
          return {};
        }),
      },
    };
    mocks.transaction.mockImplementation(
      async (callback: (client: typeof tx) => Promise<unknown>) => callback(tx),
    );
    mocks.lockRollout.mockImplementation(async () => {
      order.push("rollout");
      return {
        allowed: true,
        token: {
          practiceId: "practice-synthetic-1",
          globalGeneration: BigInt(11),
          practiceGeneration: BigInt(19),
        },
      };
    });
    mocks.lockAttempt.mockImplementation(
      async (input: {
        claim: { workerClaimId: string };
        requireLiveWorkerLease: boolean;
      }) => {
        order.push("claim");
        expect(input.requireLiveWorkerLease).toBe(true);
        if (input.claim.workerClaimId !== currentClaim) {
          throw new TemplateTwinStagingQaVisitGuardError(
            "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
            "Synthetic worker claim was replaced.",
          );
        }
      },
    );

    const aFinishedProviderWork = deferred();
    const releaseAWrite = deferred();
    const staleA = runWithTemplateTwinSyntheticQaProviderContext(
      context(claimA),
      async () => {
        aFinishedProviderWork.resolve();
        await releaseAWrite.promise;
        await updateTemplateTwinSyntheticQaClaimBoundVisit({
          visitId: "visit-synthetic-1",
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          data: {
            status: TranscribeVisitStatus.CRITIQUING,
            soapDraft: "stale A overwrite after B completed",
          },
        });
      },
      SAFE_ENV,
    );

    await aFinishedProviderWork.promise;
    currentClaim = claimB;
    await runWithTemplateTwinSyntheticQaProviderContext(
      context(claimB),
      () =>
        updateTemplateTwinSyntheticQaClaimBoundVisit({
          visitId: "visit-synthetic-1",
          userId: "doctor-synthetic-1",
          practiceId: "practice-synthetic-1",
          data: {
            status: TranscribeVisitStatus.READY,
            soapDraft: "verified synthetic output from B",
          },
        }),
      SAFE_ENV,
    );
    releaseAWrite.resolve();

    await expect(staleA).rejects.toBeInstanceOf(
      TemplateTwinSyntheticQaMutationFenceError,
    );
    expect(visitState).toEqual({
      status: TranscribeVisitStatus.READY,
      soapDraft: "verified synthetic output from B",
    });
    expect(tx.transcribeVisit.update).toHaveBeenCalledTimes(1);
    expect(order.slice(0, 4)).toEqual([
      "rollout",
      "claim",
      "visit",
      "mutation",
    ]);
  });
});
