import { Prisma } from "@prisma/client";
import prisma from "@meddoc/db";

import {
  TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE,
  resolveTemplateTwinRuntimeMode,
} from "@/lib/runtime-protocol";
import { enqueueTemplateTwinAudit } from "./audit-outbox";

export const TEMPLATE_TWIN_KILL_SWITCH_ENV =
  "TEMPLATE_TWIN_KILL_SWITCH" as const;
export const TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID = "global" as const;

export type TemplateTwinRolloutCode =
  | "TEMPLATE_TWIN_ROLLBACK_COMPAT_ACTIVE"
  | "TEMPLATE_TWIN_RUNTIME_MODE_INVALID"
  | "TEMPLATE_TWIN_KILL_SWITCH_ACTIVE"
  | "TEMPLATE_TWIN_GLOBAL_DISABLED"
  | "TEMPLATE_TWIN_PRACTICE_DISABLED"
  | "TEMPLATE_TWIN_GLOBAL_GENERATION_STALE"
  | "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE"
  | "TEMPLATE_TWIN_LINEAGE_MIGRATION_INCOMPLETE"
  | "TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE";

export type TemplateTwinRolloutDecision =
  | { allowed: true }
  | {
      allowed: false;
      code: TemplateTwinRolloutCode;
      reason: string;
    };

export interface TemplateTwinRolloutInput {
  practiceEnabled: boolean;
  env?: Readonly<Record<string, string | undefined>>;
}

/** The exact persisted rollout epoch under which clinical work was admitted. */
export interface TemplateTwinRolloutToken {
  practiceId: string;
  globalGeneration: bigint;
  practiceGeneration: bigint;
}

export type LockedTemplateTwinRolloutDecision =
  | { allowed: true; token: TemplateTwinRolloutToken }
  | {
      allowed: false;
      code: TemplateTwinRolloutCode;
      reason: string;
      currentToken: TemplateTwinRolloutToken | null;
    };

export class TemplateTwinRolloutError extends Error {
  constructor(
    readonly code: TemplateTwinRolloutCode,
    message: string,
  ) {
    super(message);
    this.name = "TemplateTwinRolloutError";
  }
}

interface RolloutLockClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
}

interface GlobalRolloutRow {
  enabled: boolean;
  generation: bigint | number | string;
}

interface PracticeRolloutRow {
  templateTwinEnabled: boolean;
  templateTwinRolloutGeneration: bigint | number | string;
}

async function assertTemplateTwinLineageContracted(
  tx: RolloutLockClient,
): Promise<void> {
  const rows = await tx.$queryRaw<Array<{ phase: string }>>(Prisma.sql`
    SELECT "phase"
    FROM "template_twin_lineage_migration_progress"
    WHERE "operationKey" = 'note_templates_lineage_v1'
  `);
  if (rows[0]?.phase !== "CONTRACTED") {
    throw new TemplateTwinRolloutError(
      "TEMPLATE_TWIN_LINEAGE_MIGRATION_INCOMPLETE",
      "Template Twin cannot be enabled until the template-lineage migration is fully contracted.",
    );
  }
}

function generation(value: bigint | number | string): bigint {
  return typeof value === "bigint" ? value : BigInt(value);
}

function blocked(
  code: TemplateTwinRolloutCode,
  reason: string,
  currentToken: TemplateTwinRolloutToken | null = null,
): LockedTemplateTwinRolloutDecision {
  return { allowed: false, code, reason, currentToken };
}

function killSwitchIsExplicitlyOff(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "false";
}

function evaluateRuntimeMode(
  env: Readonly<Record<string, string | undefined>>,
): TemplateTwinRolloutDecision | null {
  try {
    if (
      resolveTemplateTwinRuntimeMode(env) ===
      TEMPLATE_TWIN_ROLLBACK_COMPAT_RUNTIME_MODE
    ) {
      return {
        allowed: false,
        code: "TEMPLATE_TWIN_ROLLBACK_COMPAT_ACTIVE",
        reason:
          "Template Twin is unavailable while rollback compatibility mode is active.",
      };
    }
  } catch {
    return {
      allowed: false,
      code: "TEMPLATE_TWIN_RUNTIME_MODE_INVALID",
      reason: "Template Twin runtime configuration is invalid.",
    };
  }
  return null;
}

function assertRuntimeModeAllowsEnable(
  env: Readonly<Record<string, string | undefined>> = process.env,
): void {
  const decision = evaluateRuntimeMode(env);
  if (decision && !decision.allowed) {
    throw new TemplateTwinRolloutError(decision.code, decision.reason);
  }
}

/**
 * Safe-alpha process boundary. The persisted rollout rows are evaluated by
 * `pinTemplateTwinRollout` and `lockTemplateTwinRolloutForFinalClaim`; this
 * pure helper intentionally remains useful for UI/auth prechecks that do not
 * themselves make a clinical state transition.
 */
export function evaluateTemplateTwinRollout({
  practiceEnabled,
  env = process.env,
}: TemplateTwinRolloutInput): TemplateTwinRolloutDecision {
  const runtimeDecision = evaluateRuntimeMode(env);
  if (runtimeDecision) return runtimeDecision;
  if (!killSwitchIsExplicitlyOff(env[TEMPLATE_TWIN_KILL_SWITCH_ENV])) {
    return {
      allowed: false,
      code: "TEMPLATE_TWIN_KILL_SWITCH_ACTIVE",
      reason: "Template Twin is temporarily unavailable.",
    };
  }
  if (!practiceEnabled) {
    return {
      allowed: false,
      code: "TEMPLATE_TWIN_PRACTICE_DISABLED",
      reason: "Template Twin is not enabled for this practice.",
    };
  }
  return { allowed: true };
}

export function assertTemplateTwinRollout(
  input: TemplateTwinRolloutInput,
): void {
  const decision = evaluateTemplateTwinRollout(input);
  if (!decision.allowed) {
    throw new TemplateTwinRolloutError(decision.code, decision.reason);
  }
}

/**
 * Acquire rollout locks in the one permitted order: global, then practice.
 * Final clinical/output claims hold both locks until their transaction
 * commits. Disable operations take the same locks. Consequently, either a
 * final claim commits before disable obtains its locks, or the claim observes
 * the incremented generation/disabled state and loses closed.
 */
export async function lockTemplateTwinRolloutForFinalClaim(input: {
  tx: RolloutLockClient;
  practiceId: string;
  pinnedToken?: TemplateTwinRolloutToken;
  env?: Readonly<Record<string, string | undefined>>;
}): Promise<LockedTemplateTwinRolloutDecision> {
  const env = input.env ?? process.env;
  const runtimeDecision = evaluateRuntimeMode(env);
  if (runtimeDecision && !runtimeDecision.allowed) {
    return blocked(runtimeDecision.code, runtimeDecision.reason);
  }
  if (!killSwitchIsExplicitlyOff(env[TEMPLATE_TWIN_KILL_SWITCH_ENV])) {
    return blocked(
      "TEMPLATE_TWIN_KILL_SWITCH_ACTIVE",
      "Template Twin was disabled while this work was in progress. Retry after it is re-enabled.",
    );
  }

  // Lock order is load-bearing. Never move the practice query above this one.
  const globalRows = await input.tx.$queryRaw<GlobalRolloutRow[]>(Prisma.sql`
    SELECT "enabled", "generation"
    FROM "template_twin_rollout_controls"
    WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
    FOR UPDATE
  `);
  const global = globalRows[0];
  if (!global) {
    return blocked(
      "TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE",
      "Template Twin rollout controls are unavailable. Try again later.",
    );
  }

  const practiceRows = await input.tx.$queryRaw<
    PracticeRolloutRow[]
  >(Prisma.sql`
    SELECT "templateTwinEnabled", "templateTwinRolloutGeneration"
    FROM "practices"
    WHERE "id" = ${input.practiceId}
    FOR UPDATE
  `);
  const practice = practiceRows[0];
  if (!practice) {
    return blocked(
      "TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE",
      "Template Twin rollout controls are unavailable. Try again later.",
    );
  }

  const currentToken: TemplateTwinRolloutToken = {
    practiceId: input.practiceId,
    globalGeneration: generation(global.generation),
    practiceGeneration: generation(practice.templateTwinRolloutGeneration),
  };
  if (!global.enabled) {
    return blocked(
      "TEMPLATE_TWIN_GLOBAL_DISABLED",
      "Template Twin is temporarily unavailable.",
      currentToken,
    );
  }
  if (!practice.templateTwinEnabled) {
    return blocked(
      "TEMPLATE_TWIN_PRACTICE_DISABLED",
      "Template Twin is not enabled for this practice.",
      currentToken,
    );
  }
  try {
    await assertTemplateTwinLineageContracted(input.tx);
  } catch (error) {
    if (
      error instanceof TemplateTwinRolloutError &&
      error.code === "TEMPLATE_TWIN_LINEAGE_MIGRATION_INCOMPLETE"
    ) {
      return blocked(error.code, error.message, currentToken);
    }
    throw error;
  }
  if (input.pinnedToken) {
    if (
      input.pinnedToken.practiceId !== input.practiceId ||
      input.pinnedToken.globalGeneration !== currentToken.globalGeneration
    ) {
      return blocked(
        "TEMPLATE_TWIN_GLOBAL_GENERATION_STALE",
        "Template Twin rollout changed while this work was in progress. Retry it from the current visit.",
        currentToken,
      );
    }
    if (
      input.pinnedToken.practiceGeneration !== currentToken.practiceGeneration
    ) {
      return blocked(
        "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE",
        "Template Twin was changed for this practice while this work was in progress. Retry it from the current visit.",
        currentToken,
      );
    }
  }
  return { allowed: true, token: currentToken };
}

/** Pin the two persisted generations before any rendering/provider-free work. */
export async function pinTemplateTwinRollout(input: {
  practiceId: string;
  env?: Readonly<Record<string, string | undefined>>;
}): Promise<TemplateTwinRolloutToken> {
  const decision = evaluateTemplateTwinRollout({
    practiceEnabled: true,
    env: input.env,
  });
  if (!decision.allowed) {
    throw new TemplateTwinRolloutError(decision.code, decision.reason);
  }
  const locked = await prisma.$transaction(
    (tx: Prisma.TransactionClient) =>
      lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId: input.practiceId,
        env: input.env,
      }),
    { isolationLevel: "ReadCommitted" },
  );
  if (!locked.allowed) {
    throw new TemplateTwinRolloutError(locked.code, locked.reason);
  }
  return locked.token;
}

export function templateTwinRolloutAuditMetadata(
  pinned: TemplateTwinRolloutToken,
  current: TemplateTwinRolloutToken | null,
): Record<string, string | null> {
  return {
    pinnedGlobalGeneration: pinned.globalGeneration.toString(),
    pinnedPracticeGeneration: pinned.practiceGeneration.toString(),
    currentGlobalGeneration: current?.globalGeneration.toString() ?? null,
    currentPracticeGeneration: current?.practiceGeneration.toString() ?? null,
  };
}

interface RolloutMutationActor {
  userId: string;
  userEmail: string;
  practiceId: string;
}

/**
 * Controlled global operation. The successful transaction commit is the
 * linearization point. The persisted generation increments even for a
 * repeated value, invalidating every token issued before this operation.
 */
export async function setTemplateTwinGlobalRollout(input: {
  enabled: boolean;
  actor: RolloutMutationActor;
}): Promise<bigint> {
  if (input.enabled) assertRuntimeModeAllowsEnable();
  return prisma.$transaction((tx: Prisma.TransactionClient) =>
    applyTemplateTwinGlobalRolloutMutation({ tx, ...input }),
  );
}

/**
 * Transaction-scoped form of the controlled global mutation. Callers that
 * compose a larger operational transaction must not commit other work before
 * this returns. The outer transaction commit remains the linearization point.
 */
export async function applyTemplateTwinGlobalRolloutMutation(input: {
  tx: Prisma.TransactionClient;
  enabled: boolean;
  actor: RolloutMutationActor;
}): Promise<bigint> {
  if (input.enabled) assertRuntimeModeAllowsEnable();
  const tx = input.tx;
  const rows = await tx.$queryRaw<GlobalRolloutRow[]>(Prisma.sql`
    SELECT "enabled", "generation"
    FROM "template_twin_rollout_controls"
    WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
    FOR UPDATE
  `);
  const current = rows[0];
  if (!current) {
    throw new TemplateTwinRolloutError(
      "TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE",
      "Template Twin rollout controls are unavailable.",
    );
  }
  if (input.enabled) {
    await assertTemplateTwinLineageContracted(tx);
  }
  const updated = await tx.$queryRaw<Array<{ generation: bigint }>>(Prisma.sql`
    UPDATE "template_twin_rollout_controls"
    SET "enabled" = ${input.enabled},
        "generation" = "generation" + 1,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
    RETURNING "generation"
  `);
  const nextGeneration = generation(updated[0]!.generation);
  await enqueueTemplateTwinAudit(tx, {
    eventKey: `template-twin:global-rollout:${nextGeneration.toString()}`,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: input.actor.userEmail,
    action: input.enabled
      ? "TEMPLATE_TWIN_ACTIVATED"
      : "TEMPLATE_TWIN_DEACTIVATED",
    targetType: "TemplateTwinRolloutControl",
    targetId: TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID,
    metadata: {
      scope: "global",
      enabled: input.enabled,
      previousGeneration: generation(current.generation).toString(),
      generation: nextGeneration.toString(),
    },
  });
  return nextGeneration;
}

/** Practice operation using the same global-then-practice lock order. */
export async function setTemplateTwinPracticeRollout(input: {
  practiceId: string;
  enabled: boolean;
  actor: RolloutMutationActor;
}): Promise<bigint> {
  if (input.enabled) assertRuntimeModeAllowsEnable();
  return prisma.$transaction((tx: Prisma.TransactionClient) =>
    applyTemplateTwinPracticeRolloutMutation({ tx, ...input }),
  );
}

/** Transaction-scoped practice mutation using global then practice locks. */
export async function applyTemplateTwinPracticeRolloutMutation(input: {
  tx: Prisma.TransactionClient;
  practiceId: string;
  enabled: boolean;
  actor: RolloutMutationActor;
}): Promise<bigint> {
  if (input.enabled) assertRuntimeModeAllowsEnable();
  const tx = input.tx;
  const globalRows = await tx.$queryRaw<GlobalRolloutRow[]>(Prisma.sql`
    SELECT "enabled", "generation"
    FROM "template_twin_rollout_controls"
    WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
    FOR UPDATE
  `);
  if (!globalRows[0]) {
    throw new TemplateTwinRolloutError(
      "TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE",
      "Template Twin rollout controls are unavailable.",
    );
  }
  if (input.enabled) {
    await assertTemplateTwinLineageContracted(tx);
  }
  const practiceRows = await tx.$queryRaw<PracticeRolloutRow[]>(Prisma.sql`
    SELECT "templateTwinEnabled", "templateTwinRolloutGeneration"
    FROM "practices"
    WHERE "id" = ${input.practiceId}
    FOR UPDATE
  `);
  const current = practiceRows[0];
  if (!current) {
    throw new TemplateTwinRolloutError(
      "TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE",
      "Template Twin rollout controls are unavailable.",
    );
  }
  const updated = await tx.$queryRaw<
    Array<{ templateTwinRolloutGeneration: bigint }>
  >(Prisma.sql`
    UPDATE "practices"
    SET "templateTwinEnabled" = ${input.enabled},
        "templateTwinRolloutGeneration" =
          "templateTwinRolloutGeneration" + 1,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "id" = ${input.practiceId}
    RETURNING "templateTwinRolloutGeneration"
  `);
  const nextGeneration = generation(updated[0]!.templateTwinRolloutGeneration);
  await enqueueTemplateTwinAudit(tx, {
    eventKey:
      `template-twin:practice-rollout:${input.practiceId}:` +
      nextGeneration.toString(),
    practiceId: input.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: input.actor.userEmail,
    action: input.enabled
      ? "TEMPLATE_TWIN_ACTIVATED"
      : "TEMPLATE_TWIN_DEACTIVATED",
    targetType: "Practice",
    targetId: input.practiceId,
    metadata: {
      scope: "practice",
      enabled: input.enabled,
      previousGeneration: generation(
        current.templateTwinRolloutGeneration,
      ).toString(),
      generation: nextGeneration.toString(),
    },
  });
  return nextGeneration;
}
