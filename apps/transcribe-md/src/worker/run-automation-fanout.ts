import {
  markVisitAutomationLayerRunning,
  recordVisitAutomationLayerFailure,
  recordVisitAutomationLayerSuccess,
  type VisitAutomationAttempt,
} from "@/worker/automation-manifest";
import type { VisitAutomationLayerId } from "@/worker/automation-policy";

export type AutomationFanoutLayerStatus =
  | { status: "ok"; metadata?: unknown }
  | { status: "skipped" }
  | { status: "failed"; reason: string };

export interface AutomationFanoutTask {
  key: VisitAutomationLayerId;
  enabled: boolean;
  resumedOutput?: unknown;
  run: () => Promise<unknown>;
  validate?: (output: unknown) => void;
  metadata?: (output: unknown) => unknown;
}

export class AutomationFanoutPersistenceError extends Error {
  readonly code = "AUTOMATION_FANOUT_PERSISTENCE_FAILED" as const;

  constructor(readonly failedLayerIds: readonly VisitAutomationLayerId[]) {
    super("One or more automation layer outcomes could not be persisted.");
    this.name = "AutomationFanoutPersistenceError";
  }
}

/**
 * Controlled automation: every configured layer produces a durable terminal
 * row. L7 task functions currently own their visit-output commit after the
 * provider returns, so they execute in deterministic layer order rather than
 * racing six SERIALIZABLE transactions over the same practice/user/visit.
 * Provider work still runs once outside the retryable manifest transaction;
 * only idempotent database commits retry. Every configured failure is
 * inspected and persisted before finalization.
 */
export async function runAutomationFanout(input: {
  attempt: VisitAutomationAttempt;
  visitId: string;
  userId: string;
  practiceId: string;
  tasks: AutomationFanoutTask[];
}): Promise<Record<string, AutomationFanoutLayerStatus>> {
  const outcomes: Record<string, AutomationFanoutLayerStatus> = {};
  const enabled = input.tasks.filter((task) => task.enabled);
  for (const task of input.tasks) {
    if (!task.enabled) outcomes[task.key] = { status: "skipped" };
  }

  const persistenceFailures: VisitAutomationLayerId[] = [];
  for (const task of enabled) {
    try {
      const running = await markVisitAutomationLayerRunning({
        attempt: input.attempt,
        visitId: input.visitId,
        userId: input.userId,
        practiceId: input.practiceId,
        layerId: task.key,
      });
      if (running.alreadySucceeded) {
        outcomes[task.key] = { status: "ok" };
        continue;
      }
      if (task.resumedOutput !== undefined) {
        try {
          task.validate?.(task.resumedOutput);
          await recordVisitAutomationLayerSuccess({
            attempt: input.attempt,
            visitId: input.visitId,
            userId: input.userId,
            practiceId: input.practiceId,
            layerId: task.key,
            output: task.resumedOutput,
          });
          outcomes[task.key] = { status: "ok" };
          continue;
        } catch (error) {
          await recordVisitAutomationLayerFailure({
            attempt: input.attempt,
            visitId: input.visitId,
            userId: input.userId,
            practiceId: input.practiceId,
            layerId: task.key,
            error,
          });
          outcomes[task.key] = { status: "failed", reason: "layer_failed" };
          continue;
        }
      }

      let output: unknown;
      try {
        output = await task.run();
        task.validate?.(output);
      } catch (error) {
        await recordVisitAutomationLayerFailure({
          attempt: input.attempt,
          visitId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          layerId: task.key,
          error,
        });
        outcomes[task.key] = { status: "failed", reason: "layer_failed" };
        continue;
      }
      await recordVisitAutomationLayerSuccess({
        attempt: input.attempt,
        visitId: input.visitId,
        userId: input.userId,
        practiceId: input.practiceId,
        layerId: task.key,
        output,
      });
      const metadata = task.metadata?.(output);
      outcomes[task.key] =
        metadata === undefined ? { status: "ok" } : { status: "ok", metadata };
    } catch {
      persistenceFailures.push(task.key);
      outcomes[task.key] = {
        status: "failed",
        reason: "outcome_persistence_failed",
      };
    }
  }
  if (persistenceFailures.length > 0) {
    throw new AutomationFanoutPersistenceError(persistenceFailures);
  }
  return outcomes;
}
