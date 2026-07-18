import { describe, expect, it, vi } from "vitest";

import { lockTemplateTwinStagingQaAdmissionThenRun } from "../staging-qa-visit-guard";

const RUN = {
  id: "run-synthetic-1",
  admissionId: "admission-synthetic-1",
  visitId: "visit-synthetic-1",
  practiceId: "practice-synthetic-1",
  doctorId: "doctor-synthetic-1",
  noteTemplateId: "template-synthetic-1",
  noteTemplateVersion: 1,
  requestSha256: "a".repeat(64),
  payloadSha256: "b".repeat(64),
  mode: "typed",
  status: "PROCESSING",
  fixtureVersion: "synthetic-fixture-v1",
  attempt: 1,
  enqueuedAt: new Date(),
  workerClaimId: "worker-claim-synthetic-1",
  workerClaimedAt: new Date(),
  workerHeartbeatAt: new Date(),
  workerLeaseExpiresAt: new Date(Date.now() + 60_000),
  workerDeliveryCount: 1,
  workerRetryReadyAt: null,
  pinnedGlobalRolloutGeneration: BigInt(2),
  pinnedPracticeRolloutGeneration: BigInt(3),
};

describe("shared staging admission/run lock order", () => {
  it.each(["kill-switch-enabled", "kill-switch-disabled"])(
    "locks admission before run for normal and reconciliation use (%s)",
    async () => {
      const statements: string[] = [];
      const tx = {
        $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
          const sql = query.strings?.join("?") ?? "";
          statements.push(sql.replace(/\s+/gu, " ").trim());
          if (!sql.includes("FOR UPDATE")) {
            return [{ admissionId: RUN.admissionId }];
          }
          if (sql.includes("template_twin_synthetic_qa_admissions")) {
            return [{ id: RUN.admissionId }];
          }
          return [RUN];
        }),
      };

      await expect(
        lockTemplateTwinStagingQaAdmissionThenRun({
          tx: tx as never,
          runId: RUN.id,
          expectedAdmissionId: RUN.admissionId,
        }),
      ).resolves.toMatchObject({ admissionId: RUN.admissionId, run: RUN });

      const admissionLock = statements.findIndex(
        (sql) =>
          sql.includes("template_twin_synthetic_qa_admissions") &&
          sql.includes("FOR UPDATE"),
      );
      const runLock = statements.findIndex(
        (sql) =>
          sql.includes("template_twin_synthetic_qa_runs") &&
          sql.includes("FOR UPDATE"),
      );
      expect(admissionLock).toBeGreaterThanOrEqual(0);
      expect(runLock).toBeGreaterThan(admissionLock);
    },
  );

  it.each(["kill-switch-enabled", "kill-switch-disabled"])(
    "serializes a normal guard and crash reconciliation without reversing locks (%s)",
    async () => {
      function deferred() {
        let release!: () => void;
        const promise = new Promise<void>((resolve) => {
          release = resolve;
        });
        return { promise, release };
      }

      const normalRunAttempted = deferred();
      const allowNormalRun = deferred();
      const reconciliationAdmissionAttempted = deferred();
      const normalTransactionReleased = deferred();
      const trace: string[] = [];

      const normalTx = {
        $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
          const sql = query.strings?.join("?") ?? "";
          if (!sql.includes("FOR UPDATE"))
            return [{ admissionId: RUN.admissionId }];
          if (sql.includes("template_twin_synthetic_qa_admissions")) {
            trace.push("normal:admission");
            return [{ id: RUN.admissionId }];
          }
          trace.push("normal:run-waiting");
          normalRunAttempted.release();
          await allowNormalRun.promise;
          trace.push("normal:run");
          return [RUN];
        }),
      };
      const reconciliationTx = {
        $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
          const sql = query.strings?.join("?") ?? "";
          if (!sql.includes("FOR UPDATE"))
            return [{ admissionId: RUN.admissionId }];
          if (sql.includes("template_twin_synthetic_qa_admissions")) {
            trace.push("reconciliation:admission-waiting");
            reconciliationAdmissionAttempted.release();
            await normalTransactionReleased.promise;
            trace.push("reconciliation:admission");
            return [{ id: RUN.admissionId }];
          }
          trace.push("reconciliation:run");
          return [RUN];
        }),
      };

      const normal = lockTemplateTwinStagingQaAdmissionThenRun({
        tx: normalTx as never,
        runId: RUN.id,
      });
      await normalRunAttempted.promise;
      const reconciliation = lockTemplateTwinStagingQaAdmissionThenRun({
        tx: reconciliationTx as never,
        runId: RUN.id,
      });
      await reconciliationAdmissionAttempted.promise;

      expect(trace).not.toContain("reconciliation:run");
      allowNormalRun.release();
      await normal;
      normalTransactionReleased.release();
      await reconciliation;

      expect(trace).toEqual([
        "normal:admission",
        "normal:run-waiting",
        "reconciliation:admission-waiting",
        "normal:run",
        "reconciliation:admission",
        "reconciliation:run",
      ]);
    },
  );
});
