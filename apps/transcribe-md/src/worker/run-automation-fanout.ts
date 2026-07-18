import {
  markVisitAutomationLayerRunning,
  recordVisitAutomationLayerFailure,
  recordVisitAutomationLayerSuccess,
  type VisitAutomationAttempt,
} from "@/worker/automation-manifest";
import type { VisitAutomationLayerId } from "@/worker/automation-policy";
import {
  runDurableVisitAutomationProvider,
  type VisitAutomationProviderDescriptor,
} from "@/worker/provider-execution";

export type AutomationFanoutLayerStatus =
  | { status: "ok"; metadata?: unknown }
  | { status: "skipped" }
  | { status: "failed"; reason: string };

export interface AutomationFanoutTask {
  key: VisitAutomationLayerId;
  enabled: boolean;
  provider: VisitAutomationProviderDescriptor;
  run: (providerIdempotencyKey: string) => Promise<unknown>;
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
 * Controlled automation: every configured layer produces durable terminal
 * evidence. L7 tasks execute in deterministic order rather than racing six
 * SERIALIZABLE transactions over the same practice/user/visit. Their database
 * effects are captured while provider work runs once outside retryable
 * transactions, then projected atomically with layer state and audit outbox.
 * Only idempotent database commits retry; every failure is inspected and
 * persisted before finalization.
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
      let execution: Awaited<
        ReturnType<typeof runDurableVisitAutomationProvider>
      >;
      try {
        execution = await runDurableVisitAutomationProvider({
          attempt: input.attempt,
          visitId: input.visitId,
          userId: input.userId,
          practiceId: input.practiceId,
          layerId: task.key,
          descriptor: task.provider,
          invoke: task.run,
          validate: task.validate,
        });
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
        output: execution.output,
        providerExecutionId: execution.executionId,
        effects: execution.effects,
      });
      const metadata = task.metadata?.(execution.output);
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
