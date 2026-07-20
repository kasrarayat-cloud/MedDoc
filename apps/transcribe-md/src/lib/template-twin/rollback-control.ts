import { Prisma, type AuditAction } from "@prisma/client";
import prisma from "@meddoc/db";

import {
  enqueueTemplateTwinAudit,
  type EnqueueTemplateTwinAuditInput,
} from "./audit-outbox";
import {
  TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID,
  TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_KEY,
  TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_NAMESPACE,
  TEMPLATE_TWIN_ROLLBACK_FENCE_OPEN,
} from "./rollout";

export const TEMPLATE_TWIN_ROLLBACK_FENCE_PREPARED = "PREPARED" as const;
export const TEMPLATE_TWIN_ROLLBACK_FENCE_REVOKED = "REVOKED" as const;

export type TemplateTwinRollbackFenceState =
  | typeof TEMPLATE_TWIN_ROLLBACK_FENCE_OPEN
  | typeof TEMPLATE_TWIN_ROLLBACK_FENCE_PREPARED
  | typeof TEMPLATE_TWIN_ROLLBACK_FENCE_REVOKED;

export type TemplateTwinRollbackOperationState =
  | "PREPARED"
  | "REVOKED"
  | "CANCELLED";

export interface TemplateTwinRollbackActor {
  readonly userId: string;
  readonly userEmail: string | null;
  readonly practiceId: string;
  readonly sessionId: string;
}

export interface TemplateTwinRollbackInventory {
  readonly activeTemplateVersions: number;
  readonly enabledPractices: number;
  readonly resolvingFills: number;
  readonly reviewPendingFills: number;
  readonly pinnedTemplateTwinVisitsWithoutFill: number;
  readonly signedFillManifests: number;
  readonly nonterminalSyntheticRuns: number;
  readonly processingSyntheticRuns: number;
  readonly nonterminalSyntheticAdmissions: number;
  readonly runningAutomationManifests: number;
  readonly providerExecutionsReserved: number;
  readonly providerExecutionsInFlight: number;
  readonly providerExecutionsUnknown: number;
  readonly pendingAuditOutboxEvents: number;
  readonly missingRollbackAuditReceipts: number;
  readonly objectMaintenanceBacklog: number;
}

export interface TemplateTwinRollbackOperationSummary {
  readonly id: string;
  readonly state: TemplateTwinRollbackOperationState;
  readonly reasonCode: string;
  readonly changeId: string;
  readonly preparedAt: string;
  readonly revokedAt: string | null;
  readonly cancelledAt: string | null;
}

export interface TemplateTwinRollbackStatus {
  readonly fenceState: TemplateTwinRollbackFenceState;
  readonly fenceGeneration: string;
  readonly globalRolloutEnabled: boolean;
  readonly globalRolloutGeneration: string;
  readonly preparedAt: string | null;
  readonly revokedAt: string | null;
  readonly activeOperation: TemplateTwinRollbackOperationSummary | null;
  readonly inventory: TemplateTwinRollbackInventory;
  readonly blockingInFlight: readonly string[];
  readonly readyToRevoke: boolean;
  readonly rollbackComplete: boolean;
}

export interface TemplateTwinRollbackMutationResult {
  readonly idempotent: boolean;
  readonly operation: TemplateTwinRollbackOperationSummary;
  readonly status: TemplateTwinRollbackStatus;
}

export type TemplateTwinRollbackControlErrorCode =
  | "TEMPLATE_TWIN_ROLLBACK_INVALID_REQUEST"
  | "TEMPLATE_TWIN_ROLLBACK_OPERATOR_UNAUTHORIZED"
  | "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE"
  | "TEMPLATE_TWIN_ROLLBACK_OPERATION_CONFLICT"
  | "TEMPLATE_TWIN_ROLLBACK_INVALID_STATE"
  | "TEMPLATE_TWIN_ROLLBACK_IN_FLIGHT_WORK"
  | "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT";

export class TemplateTwinRollbackControlError extends Error {
  constructor(
    readonly code: TemplateTwinRollbackControlErrorCode,
    message: string,
    readonly status: TemplateTwinRollbackStatus | null = null,
  ) {
    super(message);
    this.name = "TemplateTwinRollbackControlError";
  }
}

interface RollbackControlRow {
  readonly enabled: boolean;
  readonly generation: bigint | number | string;
  readonly rollbackFenceState: string;
  readonly rollbackFenceGeneration: bigint | number | string;
  readonly rollbackOperationId: string | null;
  readonly rollbackPreparedAt: Date | null;
  readonly rollbackRevokedAt: Date | null;
}

interface RollbackOperationRow {
  readonly id: string;
  readonly state: string;
  readonly reasonCode: string;
  readonly changeId: string;
  readonly preparedAt: Date;
  readonly revokedAt: Date | null;
  readonly cancelledAt: Date | null;
}

interface InventoryRow {
  readonly activeTemplateVersions: bigint | number | string;
  readonly enabledPractices: bigint | number | string;
  readonly resolvingFills: bigint | number | string;
  readonly reviewPendingFills: bigint | number | string;
  readonly pinnedTemplateTwinVisitsWithoutFill: bigint | number | string;
  readonly signedFillManifests: bigint | number | string;
  readonly nonterminalSyntheticRuns: bigint | number | string;
  readonly processingSyntheticRuns: bigint | number | string;
  readonly nonterminalSyntheticAdmissions: bigint | number | string;
  readonly runningAutomationManifests: bigint | number | string;
  readonly providerExecutionsReserved: bigint | number | string;
  readonly providerExecutionsInFlight: bigint | number | string;
  readonly providerExecutionsUnknown: bigint | number | string;
  readonly pendingAuditOutboxEvents: bigint | number | string;
  readonly missingRollbackAuditReceipts: bigint | number | string;
  readonly objectMaintenanceBacklog: bigint | number | string;
}

interface ActiveTemplateRow {
  readonly id: string;
  readonly version: number;
  readonly compiledVersionId: string;
  readonly practiceId: string;
}

interface EnabledPracticeRow {
  readonly id: string;
  readonly templateTwinRolloutGeneration: bigint | number | string;
}

interface RollbackTransaction {
  lockControl(): Promise<RollbackControlRow>;
  lockSuperAdminActor(
    actor: TemplateTwinRollbackActor,
  ): Promise<TemplateTwinRollbackActor>;
  findOperation(id: string): Promise<RollbackOperationRow | null>;
  readInventory(): Promise<TemplateTwinRollbackInventory>;
  createOperation(input: {
    operationId: string;
    reasonCode: string;
    changeId: string;
    actor: TemplateTwinRollbackActor;
    snapshot: TemplateTwinRollbackStatus;
  }): Promise<RollbackOperationRow>;
  prepareFence(operationId: string): Promise<RollbackControlRow>;
  cancelFence(operationId: string): Promise<RollbackControlRow>;
  cancelOperation(operationId: string): Promise<RollbackOperationRow>;
  listActiveTemplates(): Promise<readonly ActiveTemplateRow[]>;
  deactivateActiveTemplates(ids: readonly string[]): Promise<number>;
  listEnabledPractices(): Promise<readonly EnabledPracticeRow[]>;
  disablePractices(ids: readonly string[]): Promise<number>;
  revokeGlobal(operationId: string): Promise<RollbackControlRow>;
  revokeOperation(input: {
    operationId: string;
    snapshot: TemplateTwinRollbackStatus;
  }): Promise<RollbackOperationRow>;
  enqueueAudit(input: EnqueueTemplateTwinAuditInput): Promise<void>;
}

export interface TemplateTwinRollbackDependencies {
  transaction<T>(callback: (tx: RollbackTransaction) => Promise<T>): Promise<T>;
  inspect(): Promise<TemplateTwinRollbackStatus>;
}

function exactCount(value: bigint | number | string): number {
  const parsed = typeof value === "bigint" ? Number(value) : Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE",
      "Template Twin rollback inventory could not be represented safely.",
    );
  }
  return parsed;
}

function generation(value: bigint | number | string): string {
  return (typeof value === "bigint" ? value : BigInt(value)).toString();
}

function assertOperationId(operationId: string): void {
  if (
    !/^[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/iu.test(
      operationId,
    )
  ) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_INVALID_REQUEST",
      "Template Twin rollback operation identifier is invalid.",
    );
  }
}

function assertPrepareIdentity(reasonCode: string, changeId: string): void {
  if (
    !/^[A-Z][A-Z0-9_]{2,79}$/u.test(reasonCode) ||
    !/^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$/u.test(changeId)
  ) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_INVALID_REQUEST",
      "Template Twin rollback reason or change identifier is invalid.",
    );
  }
}

function operationSummary(
  row: RollbackOperationRow,
): TemplateTwinRollbackOperationSummary {
  if (!["PREPARED", "REVOKED", "CANCELLED"].includes(row.state)) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE",
      "Template Twin rollback operation state is invalid.",
    );
  }
  return {
    id: row.id,
    state: row.state as TemplateTwinRollbackOperationState,
    reasonCode: row.reasonCode,
    changeId: row.changeId,
    preparedAt: row.preparedAt.toISOString(),
    revokedAt: row.revokedAt?.toISOString() ?? null,
    cancelledAt: row.cancelledAt?.toISOString() ?? null,
  };
}

function blockingInFlight(
  inventory: TemplateTwinRollbackInventory,
): readonly string[] {
  const blocked: string[] = [];
  if (inventory.resolvingFills > 0) blocked.push("RESOLVING_FILLS");
  if (inventory.reviewPendingFills > 0) {
    blocked.push("REVIEW_PENDING_FILLS");
  }
  if (inventory.pinnedTemplateTwinVisitsWithoutFill > 0) {
    blocked.push("PINNED_TEMPLATE_TWIN_VISITS_WITHOUT_FILL");
  }
  if (inventory.processingSyntheticRuns > 0) {
    blocked.push("PROCESSING_SYNTHETIC_RUNS");
  }
  if (inventory.nonterminalSyntheticRuns > 0) {
    blocked.push("NONTERMINAL_SYNTHETIC_RUNS");
  }
  if (inventory.nonterminalSyntheticAdmissions > 0) {
    blocked.push("NONTERMINAL_SYNTHETIC_ADMISSIONS");
  }
  if (inventory.runningAutomationManifests > 0) {
    blocked.push("RUNNING_AUTOMATION_MANIFESTS");
  }
  if (inventory.providerExecutionsReserved > 0) {
    blocked.push("RESERVED_PROVIDER_EXECUTIONS");
  }
  if (inventory.providerExecutionsInFlight > 0) {
    blocked.push("IN_FLIGHT_PROVIDER_EXECUTIONS");
  }
  if (inventory.providerExecutionsUnknown > 0) {
    blocked.push("UNKNOWN_PROVIDER_OUTCOMES");
  }
  return blocked;
}

function fenceState(value: string): TemplateTwinRollbackFenceState {
  if (
    value !== TEMPLATE_TWIN_ROLLBACK_FENCE_OPEN &&
    value !== TEMPLATE_TWIN_ROLLBACK_FENCE_PREPARED &&
    value !== TEMPLATE_TWIN_ROLLBACK_FENCE_REVOKED
  ) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE",
      "Template Twin rollback fence state is invalid.",
    );
  }
  return value;
}

async function statusFrom(
  tx: Pick<RollbackTransaction, "findOperation" | "readInventory">,
  control: RollbackControlRow,
): Promise<TemplateTwinRollbackStatus> {
  const inventory = await tx.readInventory();
  const operation = control.rollbackOperationId
    ? await tx.findOperation(control.rollbackOperationId)
    : null;
  if (control.rollbackOperationId && !operation) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE",
      "Template Twin rollback operation linkage is unavailable.",
    );
  }
  const state = fenceState(control.rollbackFenceState);
  const blockers = blockingInFlight(inventory);
  const revokedPostconditions =
    state === TEMPLATE_TWIN_ROLLBACK_FENCE_REVOKED &&
    !control.enabled &&
    inventory.activeTemplateVersions === 0 &&
    inventory.enabledPractices === 0;
  return {
    fenceState: state,
    fenceGeneration: generation(control.rollbackFenceGeneration),
    globalRolloutEnabled: control.enabled,
    globalRolloutGeneration: generation(control.generation),
    preparedAt: control.rollbackPreparedAt?.toISOString() ?? null,
    revokedAt: control.rollbackRevokedAt?.toISOString() ?? null,
    activeOperation: operation ? operationSummary(operation) : null,
    inventory,
    blockingInFlight: blockers,
    readyToRevoke:
      state === TEMPLATE_TWIN_ROLLBACK_FENCE_PREPARED && blockers.length === 0,
    rollbackComplete:
      revokedPostconditions &&
      blockers.length === 0 &&
      inventory.nonterminalSyntheticRuns === 0 &&
      inventory.nonterminalSyntheticAdmissions === 0 &&
      inventory.reviewPendingFills === 0 &&
      inventory.pinnedTemplateTwinVisitsWithoutFill === 0 &&
      inventory.pendingAuditOutboxEvents === 0 &&
      inventory.missingRollbackAuditReceipts === 0 &&
      inventory.objectMaintenanceBacklog === 0,
  };
}

function inventoryMetadata(
  inventory: TemplateTwinRollbackInventory,
): Record<string, number> {
  return { ...inventory };
}

function actorAudit(input: {
  actor: TemplateTwinRollbackActor;
  eventKey: string;
  action: AuditAction;
  operationId: string;
  metadata: Record<
    string,
    string | number | boolean | null | Record<string, number>
  >;
}): EnqueueTemplateTwinAuditInput {
  return {
    eventKey: input.eventKey,
    practiceId: input.actor.practiceId,
    actorId: input.actor.userId,
    actorEmailSnapshot: input.actor.userEmail,
    action: input.action,
    targetType: "TemplateTwinRollbackOperation",
    targetId: input.operationId,
    metadata: input.metadata,
  };
}

export async function inspectTemplateTwinRollback(
  dependencies: TemplateTwinRollbackDependencies = defaultDependencies,
): Promise<TemplateTwinRollbackStatus> {
  return dependencies.inspect();
}

export async function prepareTemplateTwinRollback(input: {
  operationId: string;
  reasonCode: string;
  changeId: string;
  actor: TemplateTwinRollbackActor;
  dependencies?: TemplateTwinRollbackDependencies;
}): Promise<TemplateTwinRollbackMutationResult> {
  assertOperationId(input.operationId);
  assertPrepareIdentity(input.reasonCode, input.changeId);
  const dependencies = input.dependencies ?? defaultDependencies;
  return dependencies.transaction(async (tx) => {
    const control = await tx.lockControl();
    const verifiedActor = await tx.lockSuperAdminActor(input.actor);
    const existing = await tx.findOperation(input.operationId);
    if (existing) {
      if (
        existing.reasonCode === input.reasonCode &&
        existing.changeId === input.changeId &&
        (existing.state === "PREPARED" || existing.state === "REVOKED") &&
        control.rollbackOperationId === input.operationId &&
        control.rollbackFenceState === existing.state
      ) {
        return {
          idempotent: true,
          operation: operationSummary(existing),
          status: await statusFrom(tx, control),
        };
      }
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_OPERATION_CONFLICT",
        "That rollback operation identifier has already been used for a different request or state.",
      );
    }
    if (control.rollbackFenceState !== TEMPLATE_TWIN_ROLLBACK_FENCE_OPEN) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_OPERATION_CONFLICT",
        "Another Template Twin rollback operation already owns the fence.",
        await statusFrom(tx, control),
      );
    }

    const before = await statusFrom(tx, control);
    const operation = await tx.createOperation({
      operationId: input.operationId,
      reasonCode: input.reasonCode,
      changeId: input.changeId,
      actor: verifiedActor,
      snapshot: before,
    });
    const prepared = await tx.prepareFence(input.operationId);
    const status = await statusFrom(tx, prepared);
    await tx.enqueueAudit(
      actorAudit({
        actor: verifiedActor,
        eventKey: `template-twin:rollback:${input.operationId}:prepared`,
        action: "TEMPLATE_TWIN_ROLLBACK_PREPARED",
        operationId: input.operationId,
        metadata: {
          stage: "prepared",
          reasonCode: input.reasonCode,
          changeId: input.changeId,
          fenceGeneration: status.fenceGeneration,
          inventory: inventoryMetadata(status.inventory),
        },
      }),
    );
    const auditedStatus = await statusFrom(tx, prepared);
    return {
      idempotent: false,
      operation: operationSummary(operation),
      status: auditedStatus,
    };
  });
}

export async function cancelPreparedTemplateTwinRollback(input: {
  operationId: string;
  actor: TemplateTwinRollbackActor;
  dependencies?: TemplateTwinRollbackDependencies;
}): Promise<TemplateTwinRollbackMutationResult> {
  assertOperationId(input.operationId);
  const dependencies = input.dependencies ?? defaultDependencies;
  return dependencies.transaction(async (tx) => {
    const control = await tx.lockControl();
    const verifiedActor = await tx.lockSuperAdminActor(input.actor);
    const operation = await tx.findOperation(input.operationId);
    if (!operation) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_INVALID_STATE",
        "The requested rollback operation does not exist.",
      );
    }
    if (
      operation.state === "CANCELLED" &&
      control.rollbackFenceState === TEMPLATE_TWIN_ROLLBACK_FENCE_OPEN
    ) {
      return {
        idempotent: true,
        operation: operationSummary(operation),
        status: await statusFrom(tx, control),
      };
    }
    if (
      operation.state !== "PREPARED" ||
      control.rollbackFenceState !== TEMPLATE_TWIN_ROLLBACK_FENCE_PREPARED ||
      control.rollbackOperationId !== input.operationId
    ) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_INVALID_STATE",
        "Only the currently prepared, not-yet-revoked rollback fence can be cancelled.",
        await statusFrom(tx, control),
      );
    }

    const opened = await tx.cancelFence(input.operationId);
    const cancelled = await tx.cancelOperation(input.operationId);
    const status = await statusFrom(tx, opened);
    await tx.enqueueAudit(
      actorAudit({
        actor: verifiedActor,
        eventKey: `template-twin:rollback:${input.operationId}:cancelled`,
        action: "TEMPLATE_TWIN_ROLLBACK_CANCELLED",
        operationId: input.operationId,
        metadata: {
          stage: "cancelled",
          changeId: operation.changeId,
          reasonCode: operation.reasonCode,
          fenceGeneration: status.fenceGeneration,
          rolloutStateChanged: false,
        },
      }),
    );
    const auditedStatus = await statusFrom(tx, opened);
    return {
      idempotent: false,
      operation: operationSummary(cancelled),
      status: auditedStatus,
    };
  });
}

export async function revokeTemplateTwinRollout(input: {
  operationId: string;
  actor: TemplateTwinRollbackActor;
  dependencies?: TemplateTwinRollbackDependencies;
}): Promise<TemplateTwinRollbackMutationResult> {
  assertOperationId(input.operationId);
  const dependencies = input.dependencies ?? defaultDependencies;
  return dependencies.transaction(async (tx) => {
    const control = await tx.lockControl();
    const verifiedActor = await tx.lockSuperAdminActor(input.actor);
    const operation = await tx.findOperation(input.operationId);
    if (!operation) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_INVALID_STATE",
        "Prepare the rollback fence before revoking rollout.",
      );
    }
    if (
      operation.state === "REVOKED" &&
      control.rollbackFenceState === TEMPLATE_TWIN_ROLLBACK_FENCE_REVOKED &&
      control.rollbackOperationId === input.operationId
    ) {
      return {
        idempotent: true,
        operation: operationSummary(operation),
        status: await statusFrom(tx, control),
      };
    }
    if (
      operation.state !== "PREPARED" ||
      control.rollbackFenceState !== TEMPLATE_TWIN_ROLLBACK_FENCE_PREPARED ||
      control.rollbackOperationId !== input.operationId
    ) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_INVALID_STATE",
        "The current prepared rollback operation does not match this request.",
        await statusFrom(tx, control),
      );
    }

    const before = await statusFrom(tx, control);
    if (before.blockingInFlight.length > 0) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_IN_FLIGHT_WORK",
        "Template Twin has in-flight work that must be drained or classified before rollout revocation.",
        before,
      );
    }

    // Lock order extends the existing rollout protocol: global singleton,
    // practices in stable id order, then Template Twin versions in stable id
    // order. Do not parallelize or reverse these reads.
    const enabledPractices = await tx.listEnabledPractices();
    const activeTemplates = await tx.listActiveTemplates();
    if (activeTemplates.length !== before.inventory.activeTemplateVersions) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
        "The active Template Twin inventory is incomplete.",
        before,
      );
    }
    if (enabledPractices.length !== before.inventory.enabledPractices) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
        "The enabled-practice inventory changed during rollback preparation.",
        before,
      );
    }

    const deactivated = await tx.deactivateActiveTemplates(
      activeTemplates.map(({ id }) => id),
    );
    const disabled = await tx.disablePractices(
      enabledPractices.map(({ id }) => id),
    );
    if (
      deactivated !== activeTemplates.length ||
      disabled !== enabledPractices.length
    ) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
        "Template Twin rollback lost a concurrent state transition.",
        before,
      );
    }

    for (const template of activeTemplates) {
      await tx.enqueueAudit({
        eventKey: `template-twin:rollback:${input.operationId}:template:${template.id}`,
        practiceId: template.practiceId,
        actorId: verifiedActor.userId,
        actorEmailSnapshot: verifiedActor.userEmail,
        action: "TEMPLATE_TWIN_DEACTIVATED",
        targetType: "NoteTemplate",
        targetId: template.id,
        metadata: {
          reasonCode: "OPERATIONAL_ROLLBACK",
          rollbackOperationId: input.operationId,
          templateVersion: template.version,
          compiledVersionId: template.compiledVersionId,
        },
      });
    }
    for (const practice of enabledPractices) {
      const previousGeneration = generation(
        practice.templateTwinRolloutGeneration,
      );
      await tx.enqueueAudit({
        eventKey: `template-twin:rollback:${input.operationId}:practice:${practice.id}`,
        practiceId: practice.id,
        actorId: verifiedActor.userId,
        actorEmailSnapshot: verifiedActor.userEmail,
        action: "TEMPLATE_TWIN_DEACTIVATED",
        targetType: "Practice",
        targetId: practice.id,
        metadata: {
          scope: "practice",
          reasonCode: "OPERATIONAL_ROLLBACK",
          rollbackOperationId: input.operationId,
          previousGeneration,
          generation: (BigInt(previousGeneration) + BigInt(1)).toString(),
        },
      });
    }

    const revokedControl = await tx.revokeGlobal(input.operationId);
    const afterControlChange = await statusFrom(tx, revokedControl);
    if (
      afterControlChange.inventory.activeTemplateVersions !== 0 ||
      afterControlChange.inventory.enabledPractices !== 0 ||
      afterControlChange.globalRolloutEnabled ||
      afterControlChange.inventory.signedFillManifests !==
        before.inventory.signedFillManifests
    ) {
      throw new TemplateTwinRollbackControlError(
        "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
        "Template Twin rollback postconditions were not preserved.",
        afterControlChange,
      );
    }
    const revokedOperation = await tx.revokeOperation({
      operationId: input.operationId,
      snapshot: afterControlChange,
    });
    const after = await statusFrom(tx, revokedControl);
    await tx.enqueueAudit(
      actorAudit({
        actor: verifiedActor,
        eventKey: `template-twin:rollback:${input.operationId}:revoked`,
        action: "TEMPLATE_TWIN_ROLLOUT_REVOKED",
        operationId: input.operationId,
        metadata: {
          stage: "revoked",
          reasonCode: operation.reasonCode,
          changeId: operation.changeId,
          previousGlobalGeneration: generation(control.generation),
          globalGeneration: after.globalRolloutGeneration,
          fenceGeneration: after.fenceGeneration,
          deactivatedTemplateVersions: deactivated,
          disabledPractices: disabled,
          signedArtifactsPreserved: after.inventory.signedFillManifests,
          inventory: inventoryMetadata(after.inventory),
        },
      }),
    );
    const auditedStatus = await statusFrom(tx, revokedControl);
    return {
      idempotent: false,
      operation: operationSummary(revokedOperation),
      status: auditedStatus,
    };
  });
}

interface PrismaRollbackClient {
  $queryRaw<T>(query: Prisma.Sql): Promise<T>;
  $executeRaw(query: Prisma.Sql): Promise<number>;
  templateTwinAuditOutbox: Prisma.TransactionClient["templateTwinAuditOutbox"];
}

async function readControl(
  client: PrismaRollbackClient,
  lock: boolean,
): Promise<RollbackControlRow> {
  const rows = await client.$queryRaw<RollbackControlRow[]>(
    lock
      ? Prisma.sql`
          SELECT
            "enabled", "generation", "rollbackFenceState",
            "rollbackFenceGeneration", "rollbackOperationId",
            "rollbackPreparedAt", "rollbackRevokedAt"
          FROM "template_twin_rollout_controls"
          WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
          FOR UPDATE
        `
      : Prisma.sql`
          SELECT
            "enabled", "generation", "rollbackFenceState",
            "rollbackFenceGeneration", "rollbackOperationId",
            "rollbackPreparedAt", "rollbackRevokedAt"
          FROM "template_twin_rollout_controls"
          WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
        `,
  );
  const row = rows[0];
  if (!row) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE",
      "Template Twin rollback controls are unavailable.",
    );
  }
  return row;
}

async function findOperation(
  client: PrismaRollbackClient,
  id: string,
): Promise<RollbackOperationRow | null> {
  const rows = await client.$queryRaw<RollbackOperationRow[]>(Prisma.sql`
    SELECT
      "id"::text, "state", "reasonCode", "changeId", "preparedAt",
      "revokedAt", "cancelledAt"
    FROM "template_twin_rollback_operations"
    WHERE "id" = ${id}::uuid
  `);
  return rows[0] ?? null;
}

async function readInventory(
  client: PrismaRollbackClient,
): Promise<TemplateTwinRollbackInventory> {
  const rows = await client.$queryRaw<InventoryRow[]>(Prisma.sql`
    SELECT
      (SELECT COUNT(*)::bigint
       FROM "note_templates"
       WHERE "templateKind" = 'template_twin_docx' AND "status" = 'active')
        AS "activeTemplateVersions",
      (SELECT COUNT(*)::bigint
       FROM "practices" WHERE "templateTwinEnabled" = true)
        AS "enabledPractices",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_fill_manifests" WHERE "status" = 'RESOLVING')
        AS "resolvingFills",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_fill_manifests"
       WHERE "status" IN ('NEEDS_REVIEW', 'VERIFIED'))
        AS "reviewPendingFills",
      (SELECT COUNT(*)::bigint
       FROM "transcribe_visits" visit
       JOIN "note_templates" template
         ON template."id" = visit."noteTemplateId"
       LEFT JOIN "template_twin_fill_manifests" fill
         ON fill."visitId" = visit."id"
       WHERE template."templateKind" = 'template_twin_docx'
         AND visit."status" NOT IN ('FAILED', 'SIGNED')
         AND fill."id" IS NULL)
        AS "pinnedTemplateTwinVisitsWithoutFill",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_fill_manifests" WHERE "status" = 'SIGNED')
        AS "signedFillManifests",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_synthetic_qa_runs"
       WHERE "status" NOT IN ('COMPLETED', 'PROCESSING_FAILED'))
        AS "nonterminalSyntheticRuns",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_synthetic_qa_runs" WHERE "status" = 'PROCESSING')
        AS "processingSyntheticRuns",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_synthetic_qa_admissions"
       WHERE "phase" NOT IN ('SIGNED', 'FAILED', 'REVOKED'))
        AS "nonterminalSyntheticAdmissions",
      (SELECT COUNT(*)::bigint
       FROM "visit_automation_manifests" manifest
       WHERE manifest."status" IN ('PENDING', 'RUNNING')
         AND (
           manifest."stagingAdmissionId" IS NOT NULL
           OR manifest."stagingRunId" IS NOT NULL
           OR EXISTS (
             SELECT 1 FROM "template_twin_fill_manifests" fill
             WHERE fill."visitId" = manifest."visitId"
           )
           OR EXISTS (
             SELECT 1
             FROM "transcribe_visits" visit
             JOIN "note_templates" template
               ON template."id" = visit."noteTemplateId"
             WHERE visit."id" = manifest."visitId"
               AND template."templateKind" = 'template_twin_docx'
           )
         )) AS "runningAutomationManifests",
      (SELECT COUNT(*)::bigint
       FROM "visit_automation_provider_executions" execution
       WHERE execution."status" = 'RESERVED'
         AND (
           execution."stagingAdmissionId" IS NOT NULL
           OR execution."stagingRunId" IS NOT NULL
           OR EXISTS (
             SELECT 1 FROM "template_twin_fill_manifests" fill
             WHERE fill."visitId" = execution."visitId"
           )
           OR EXISTS (
             SELECT 1
             FROM "transcribe_visits" visit
             JOIN "note_templates" template
               ON template."id" = visit."noteTemplateId"
             WHERE visit."id" = execution."visitId"
               AND template."templateKind" = 'template_twin_docx'
           )
         )) AS "providerExecutionsReserved",
      (SELECT COUNT(*)::bigint
       FROM "visit_automation_provider_executions" execution
       WHERE execution."status" = 'IN_FLIGHT'
         AND (
           execution."stagingAdmissionId" IS NOT NULL
           OR execution."stagingRunId" IS NOT NULL
           OR EXISTS (
             SELECT 1 FROM "template_twin_fill_manifests" fill
             WHERE fill."visitId" = execution."visitId"
           )
           OR EXISTS (
             SELECT 1
             FROM "transcribe_visits" visit
             JOIN "note_templates" template
               ON template."id" = visit."noteTemplateId"
             WHERE visit."id" = execution."visitId"
               AND template."templateKind" = 'template_twin_docx'
           )
         )) AS "providerExecutionsInFlight",
      (SELECT COUNT(*)::bigint
       FROM "visit_automation_provider_executions" execution
       WHERE execution."status" = 'UNKNOWN_OUTCOME'
         AND (
           execution."stagingAdmissionId" IS NOT NULL
           OR execution."stagingRunId" IS NOT NULL
           OR EXISTS (
             SELECT 1 FROM "template_twin_fill_manifests" fill
             WHERE fill."visitId" = execution."visitId"
           )
           OR EXISTS (
             SELECT 1
             FROM "transcribe_visits" visit
             JOIN "note_templates" template
               ON template."id" = visit."noteTemplateId"
             WHERE visit."id" = execution."visitId"
               AND template."templateKind" = 'template_twin_docx'
           )
         )) AS "providerExecutionsUnknown",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_audit_outbox"
       WHERE "status" <> 'DELIVERED')
        AS "pendingAuditOutboxEvents",
      (SELECT COUNT(*)::bigint
       FROM (
         SELECT
           operation."id", operation."actorPracticeId",
           operation."requestedById", operation."actorEmailSnapshot",
           'prepared'::text AS "stage",
           'TEMPLATE_TWIN_ROLLBACK_PREPARED'::"AuditAction" AS "action"
         FROM "template_twin_rollback_operations" operation
         UNION ALL
         SELECT
           operation."id", operation."actorPracticeId",
           operation."requestedById", operation."actorEmailSnapshot",
           CASE operation."state"
             WHEN 'CANCELLED' THEN 'cancelled'
             WHEN 'REVOKED' THEN 'revoked'
           END,
           CASE operation."state"
             WHEN 'CANCELLED' THEN
               'TEMPLATE_TWIN_ROLLBACK_CANCELLED'::"AuditAction"
             WHEN 'REVOKED' THEN
               'TEMPLATE_TWIN_ROLLOUT_REVOKED'::"AuditAction"
           END
         FROM "template_twin_rollback_operations" operation
         WHERE operation."state" IN ('CANCELLED', 'REVOKED')
       ) expected
       WHERE NOT EXISTS (
         SELECT 1
         FROM "template_twin_audit_outbox" outbox
         JOIN "audit_logs" audit
           ON audit."templateTwinOutboxEventKey" = outbox."eventKey"
         WHERE outbox."eventKey" =
             'template-twin:rollback:' || expected."id"::text || ':' ||
             expected."stage"
           AND outbox."status" = 'DELIVERED'
           AND outbox."deliveredAt" IS NOT NULL
           AND outbox."action" = expected."action"
           AND outbox."targetType" = 'TemplateTwinRollbackOperation'
           AND outbox."targetId" = expected."id"::text
           AND outbox."practiceId" = expected."actorPracticeId"
           AND outbox."actorId" = expected."requestedById"
           AND outbox."actorEmailSnapshot" IS NOT DISTINCT FROM
             expected."actorEmailSnapshot"
           AND audit."action" = outbox."action"
           AND audit."targetType" = outbox."targetType"
           AND audit."targetId" = outbox."targetId"
           AND audit."practiceId" = outbox."practiceId"
           AND audit."userId" IS NOT DISTINCT FROM outbox."actorId"
           AND audit."userEmailSnapshot" IS NOT DISTINCT FROM
             outbox."actorEmailSnapshot"
           AND audit."success" = true
           AND audit."errorCode" IS NULL
       )) AS "missingRollbackAuditReceipts",
      (SELECT COUNT(*)::bigint
       FROM "template_twin_object_ledgers"
       WHERE "state" IN ('INTENT', 'WRITTEN_UNCLAIMED', 'PURGE_PENDING', 'FAILED'))
        AS "objectMaintenanceBacklog"
  `);
  const row = rows[0];
  if (!row) {
    throw new TemplateTwinRollbackControlError(
      "TEMPLATE_TWIN_ROLLBACK_CONTROL_UNAVAILABLE",
      "Template Twin rollback inventory is unavailable.",
    );
  }
  return {
    activeTemplateVersions: exactCount(row.activeTemplateVersions),
    enabledPractices: exactCount(row.enabledPractices),
    resolvingFills: exactCount(row.resolvingFills),
    reviewPendingFills: exactCount(row.reviewPendingFills),
    pinnedTemplateTwinVisitsWithoutFill: exactCount(
      row.pinnedTemplateTwinVisitsWithoutFill,
    ),
    signedFillManifests: exactCount(row.signedFillManifests),
    nonterminalSyntheticRuns: exactCount(row.nonterminalSyntheticRuns),
    processingSyntheticRuns: exactCount(row.processingSyntheticRuns),
    nonterminalSyntheticAdmissions: exactCount(
      row.nonterminalSyntheticAdmissions,
    ),
    runningAutomationManifests: exactCount(row.runningAutomationManifests),
    providerExecutionsReserved: exactCount(row.providerExecutionsReserved),
    providerExecutionsInFlight: exactCount(row.providerExecutionsInFlight),
    providerExecutionsUnknown: exactCount(row.providerExecutionsUnknown),
    pendingAuditOutboxEvents: exactCount(row.pendingAuditOutboxEvents),
    missingRollbackAuditReceipts: exactCount(row.missingRollbackAuditReceipts),
    objectMaintenanceBacklog: exactCount(row.objectMaintenanceBacklog),
  };
}

function snapshotJson(status: TemplateTwinRollbackStatus): string {
  return JSON.stringify(status);
}

function prismaTransaction(client: PrismaRollbackClient): RollbackTransaction {
  return {
    async lockControl() {
      await client.$executeRaw(Prisma.sql`
        SELECT template_twin_acquire_rollback_linearization_lock()
      `);
      return readControl(client, true);
    },
    async lockSuperAdminActor(actor) {
      const rows = await client.$queryRaw<TemplateTwinRollbackActor[]>(
        Prisma.sql`
          SELECT
            account."id" AS "userId", account."email" AS "userEmail",
            account."practiceId", session."sessionToken" AS "sessionId"
          FROM "practices" practice
          JOIN "users" account ON account."practiceId" = practice."id"
          JOIN "user_sessions" session ON session."userId" = account."id"
          WHERE account."id" = ${actor.userId}
            AND account."email" IS NOT DISTINCT FROM ${actor.userEmail}
            AND account."practiceId" = ${actor.practiceId}
            AND session."sessionToken" = ${actor.sessionId}
            AND practice."isActive" = true
            AND account."isActive" = true
            AND account."deactivatedAt" IS NULL
            AND account."suspendedAt" IS NULL
            AND account."softDeletedAt" IS NULL
            AND account."mfaEnabled" = true
            AND account."mfaSecret" IS NOT NULL
            AND regexp_replace(
              account."mfaSecret",
              U&'[\\0009-\\000D\\0020\\00A0\\1680\\2000-\\200A\\2028\\2029\\202F\\205F\\3000\\FEFF]',
              '',
              'g'
            ) <> ''
            AND account."mfaVerifiedAt" IS NOT NULL
            AND account."mfaVerifiedAt" <= CURRENT_TIMESTAMP
            AND 'SUPER_ADMIN'::"Product" = ANY(account."products")
            AND session."createdAt" <= clock_timestamp()
            AND session."createdAt" > clock_timestamp() - INTERVAL '12 hours'
            AND session."expiresAt" > clock_timestamp()
            AND (
              account."forceLogoutAt" IS NULL
              OR session."createdAt" > account."forceLogoutAt"
            )
          FOR SHARE OF practice, account, session
        `,
      );
      if (!rows[0]) {
        throw new TemplateTwinRollbackControlError(
          "TEMPLATE_TWIN_ROLLBACK_OPERATOR_UNAUTHORIZED",
          "A current SUPER_ADMIN identity is required for Template Twin rollback.",
        );
      }
      return rows[0];
    },
    findOperation: (id) => findOperation(client, id),
    readInventory: () => readInventory(client),
    async createOperation(input) {
      const rows = await client.$queryRaw<RollbackOperationRow[]>(Prisma.sql`
        INSERT INTO "template_twin_rollback_operations" (
          "id", "state", "reasonCode", "changeId", "requestedById",
          "actorPracticeId", "actorEmailSnapshot", "preparedSnapshot",
          "preparedAt", "createdAt", "updatedAt"
        ) VALUES (
          ${input.operationId}::uuid, 'PREPARED', ${input.reasonCode},
          ${input.changeId}, ${input.actor.userId}, ${input.actor.practiceId},
          ${input.actor.userEmail}, ${snapshotJson(input.snapshot)}::jsonb,
          CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        RETURNING
          "id"::text, "state", "reasonCode", "changeId", "preparedAt",
          "revokedAt", "cancelledAt"
      `);
      return rows[0]!;
    },
    async prepareFence(operationId) {
      const rows = await client.$queryRaw<RollbackControlRow[]>(Prisma.sql`
        UPDATE "template_twin_rollout_controls"
        SET "rollbackFenceState" = 'PREPARED',
            "rollbackFenceGeneration" = "rollbackFenceGeneration" + 1,
            "rollbackOperationId" = ${operationId}::uuid,
            "rollbackPreparedAt" = CURRENT_TIMESTAMP,
            "rollbackRevokedAt" = NULL,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
          AND "rollbackFenceState" = 'OPEN'
        RETURNING
          "enabled", "generation", "rollbackFenceState",
          "rollbackFenceGeneration", "rollbackOperationId"::text,
          "rollbackPreparedAt", "rollbackRevokedAt"
      `);
      if (!rows[0]) {
        throw new TemplateTwinRollbackControlError(
          "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
          "Template Twin rollback fence could not be prepared.",
        );
      }
      return rows[0];
    },
    async cancelFence(operationId) {
      const rows = await client.$queryRaw<RollbackControlRow[]>(Prisma.sql`
        UPDATE "template_twin_rollout_controls"
        SET "rollbackFenceState" = 'OPEN',
            "rollbackFenceGeneration" = "rollbackFenceGeneration" + 1,
            "rollbackOperationId" = NULL,
            "rollbackPreparedAt" = NULL,
            "rollbackRevokedAt" = NULL,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
          AND "rollbackFenceState" = 'PREPARED'
          AND "rollbackOperationId" = ${operationId}::uuid
        RETURNING
          "enabled", "generation", "rollbackFenceState",
          "rollbackFenceGeneration", "rollbackOperationId"::text,
          "rollbackPreparedAt", "rollbackRevokedAt"
      `);
      if (!rows[0]) {
        throw new TemplateTwinRollbackControlError(
          "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
          "Template Twin rollback fence could not be cancelled.",
        );
      }
      return rows[0];
    },
    async cancelOperation(operationId) {
      const rows = await client.$queryRaw<RollbackOperationRow[]>(Prisma.sql`
        UPDATE "template_twin_rollback_operations"
        SET "state" = 'CANCELLED',
            "cancelledAt" = CURRENT_TIMESTAMP,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${operationId}::uuid AND "state" = 'PREPARED'
        RETURNING
          "id"::text, "state", "reasonCode", "changeId", "preparedAt",
          "revokedAt", "cancelledAt"
      `);
      if (!rows[0]) {
        throw new TemplateTwinRollbackControlError(
          "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
          "Template Twin rollback operation could not be cancelled.",
        );
      }
      return rows[0];
    },
    listActiveTemplates: () =>
      client.$queryRaw<ActiveTemplateRow[]>(Prisma.sql`
        SELECT
          template."id", template."version",
          compiled."id" AS "compiledVersionId",
          source."practiceId"
        FROM "note_templates" template
        JOIN "template_twin_compiled_versions" compiled
          ON compiled."noteTemplateId" = template."id"
        JOIN "template_twin_source_artifacts" source
          ON source."id" = compiled."sourceArtifactId"
        WHERE template."templateKind" = 'template_twin_docx'
          AND template."status" = 'active'
        ORDER BY template."id"
        FOR UPDATE OF template
      `),
    async deactivateActiveTemplates(ids) {
      if (ids.length === 0) return 0;
      return client.$executeRaw(Prisma.sql`
        UPDATE "note_templates"
        SET "status" = 'inactive', "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" IN (${Prisma.join(ids)})
          AND "templateKind" = 'template_twin_docx'
          AND "status" = 'active'
      `);
    },
    listEnabledPractices: () =>
      client.$queryRaw<EnabledPracticeRow[]>(Prisma.sql`
        SELECT "id", "templateTwinRolloutGeneration"
        FROM "practices"
        WHERE "templateTwinEnabled" = true
        ORDER BY "id"
        FOR UPDATE
      `),
    async disablePractices(ids) {
      if (ids.length === 0) return 0;
      return client.$executeRaw(Prisma.sql`
        UPDATE "practices"
        SET "templateTwinEnabled" = false,
            "templateTwinRolloutGeneration" =
              "templateTwinRolloutGeneration" + 1,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" IN (${Prisma.join(ids)})
          AND "templateTwinEnabled" = true
      `);
    },
    async revokeGlobal(operationId) {
      const rows = await client.$queryRaw<RollbackControlRow[]>(Prisma.sql`
        UPDATE "template_twin_rollout_controls"
        SET "enabled" = false,
            "generation" = "generation" + 1,
            "rollbackFenceState" = 'REVOKED',
            "rollbackFenceGeneration" = "rollbackFenceGeneration" + 1,
            "rollbackRevokedAt" = CURRENT_TIMESTAMP,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID}
          AND "rollbackFenceState" = 'PREPARED'
          AND "rollbackOperationId" = ${operationId}::uuid
        RETURNING
          "enabled", "generation", "rollbackFenceState",
          "rollbackFenceGeneration", "rollbackOperationId"::text,
          "rollbackPreparedAt", "rollbackRevokedAt"
      `);
      if (!rows[0]) {
        throw new TemplateTwinRollbackControlError(
          "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
          "Template Twin global rollout could not be revoked.",
        );
      }
      return rows[0];
    },
    async revokeOperation(input) {
      const rows = await client.$queryRaw<RollbackOperationRow[]>(Prisma.sql`
        UPDATE "template_twin_rollback_operations"
        SET "state" = 'REVOKED',
            "revokedAt" = CURRENT_TIMESTAMP,
            "revokedSnapshot" = ${snapshotJson(input.snapshot)}::jsonb,
            "updatedAt" = CURRENT_TIMESTAMP
        WHERE "id" = ${input.operationId}::uuid AND "state" = 'PREPARED'
        RETURNING
          "id"::text, "state", "reasonCode", "changeId", "preparedAt",
          "revokedAt", "cancelledAt"
      `);
      if (!rows[0]) {
        throw new TemplateTwinRollbackControlError(
          "TEMPLATE_TWIN_ROLLBACK_PERSISTENCE_CONFLICT",
          "Template Twin rollback operation could not be finalized.",
        );
      }
      return rows[0];
    },
    enqueueAudit: (input) => enqueueTemplateTwinAudit(client, input),
  };
}

const defaultDependencies: TemplateTwinRollbackDependencies = {
  transaction: (callback) =>
    prisma.$transaction(
      async (tx: Prisma.TransactionClient) => {
        // The release service uses advisory -> global -> practice. Acquire the
        // same advisory lock before rollback's global row lock so rollback and
        // enablement cannot deadlock with an inverted lock order.
        await tx.$executeRaw(Prisma.sql`
          SELECT pg_advisory_xact_lock(
            ${TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_NAMESPACE},
            ${TEMPLATE_TWIN_RELEASE_CONTROL_LOCK_KEY}
          )
        `);
        return callback(prismaTransaction(tx as PrismaRollbackClient));
      },
      { isolationLevel: "Serializable" },
    ),
  inspect: async () => {
    return prisma.$transaction(
      async (client: Prisma.TransactionClient) => {
        const rollbackClient = client as unknown as PrismaRollbackClient;
        const tx = prismaTransaction(rollbackClient);
        const control = await readControl(rollbackClient, false);
        return statusFrom(tx, control);
      },
      { isolationLevel: "RepeatableRead" },
    );
  },
};
