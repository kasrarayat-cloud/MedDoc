import { describe, expect, it } from "vitest";

import {
  cancelPreparedTemplateTwinRollback,
  prepareTemplateTwinRollback,
  revokeTemplateTwinRollout,
  type TemplateTwinRollbackDependencies,
  type TemplateTwinRollbackInventory,
} from "../rollback-control";

const OPERATION_ID = "4d5cb6df-91bb-4b1e-8d2a-3ecbbf421cea";
const OTHER_OPERATION_ID = "7533cd57-8df0-4b13-96bb-a5ea7f414a09";
const actor = {
  userId: "synthetic-super-admin",
  userEmail: "rollback-operator@synthetic.test",
  practiceId: "synthetic-operator-practice",
};

function emptyInventory(
  overrides: Partial<TemplateTwinRollbackInventory> = {},
): TemplateTwinRollbackInventory {
  return {
    activeTemplateVersions: 2,
    enabledPractices: 2,
    resolvingFills: 0,
    reviewPendingFills: 0,
    signedFillManifests: 3,
    nonterminalSyntheticRuns: 0,
    processingSyntheticRuns: 0,
    nonterminalSyntheticAdmissions: 0,
    runningAutomationManifests: 0,
    providerExecutionsReserved: 0,
    providerExecutionsInFlight: 0,
    providerExecutionsUnknown: 0,
    pendingAuditOutboxEvents: 0,
    objectMaintenanceBacklog: 0,
    ...overrides,
  };
}

class FakeRollbackStore {
  now = new Date("2026-07-19T08:45:00.000Z");
  control = {
    enabled: true,
    generation: BigInt(7),
    rollbackFenceState: "OPEN",
    rollbackFenceGeneration: BigInt(1),
    rollbackOperationId: null as string | null,
    rollbackPreparedAt: null as Date | null,
    rollbackRevokedAt: null as Date | null,
  };
  inventory = emptyInventory();
  operations = new Map<
    string,
    {
      id: string;
      state: string;
      reasonCode: string;
      changeId: string;
      preparedAt: Date;
      revokedAt: Date | null;
      cancelledAt: Date | null;
    }
  >();
  templates = [
    {
      id: "template-a",
      version: 1,
      compiledVersionId: "compiled-a",
      practiceId: "practice-a",
    },
    {
      id: "template-b",
      version: 3,
      compiledVersionId: "compiled-b",
      practiceId: "practice-b",
    },
  ];
  practices = [
    { id: "practice-a", templateTwinRolloutGeneration: BigInt(4) },
    { id: "practice-b", templateTwinRolloutGeneration: BigInt(9) },
  ];
  audits: Array<{ eventKey: string; action: string; targetType?: string }> = [];

  private tx = {
    lockControl: async () => ({ ...this.control }),
    lockSuperAdminActor: async () => actor,
    findOperation: async (id: string) => this.operations.get(id) ?? null,
    readInventory: async () => ({ ...this.inventory }),
    createOperation: async (input: {
      operationId: string;
      reasonCode: string;
      changeId: string;
    }) => {
      const operation = {
        id: input.operationId,
        state: "PREPARED",
        reasonCode: input.reasonCode,
        changeId: input.changeId,
        preparedAt: this.now,
        revokedAt: null,
        cancelledAt: null,
      };
      this.operations.set(input.operationId, operation);
      return operation;
    },
    prepareFence: async (operationId: string) => {
      this.control = {
        ...this.control,
        rollbackFenceState: "PREPARED",
        rollbackFenceGeneration:
          this.control.rollbackFenceGeneration + BigInt(1),
        rollbackOperationId: operationId,
        rollbackPreparedAt: this.now,
      };
      return { ...this.control };
    },
    cancelFence: async () => {
      this.control = {
        ...this.control,
        rollbackFenceState: "OPEN",
        rollbackFenceGeneration:
          this.control.rollbackFenceGeneration + BigInt(1),
        rollbackOperationId: null,
        rollbackPreparedAt: null,
        rollbackRevokedAt: null,
      };
      return { ...this.control };
    },
    cancelOperation: async (operationId: string) => {
      const current = this.operations.get(operationId)!;
      const operation = {
        ...current,
        state: "CANCELLED",
        cancelledAt: this.now,
      };
      this.operations.set(operationId, operation);
      return operation;
    },
    listActiveTemplates: async () => [...this.templates],
    deactivateActiveTemplates: async (ids: readonly string[]) => {
      const changed = this.templates.filter(({ id }) =>
        ids.includes(id),
      ).length;
      this.templates = this.templates.filter(({ id }) => !ids.includes(id));
      this.inventory = {
        ...this.inventory,
        activeTemplateVersions: this.inventory.activeTemplateVersions - changed,
      };
      return changed;
    },
    listEnabledPractices: async () => [...this.practices],
    disablePractices: async (ids: readonly string[]) => {
      const changed = this.practices.filter(({ id }) =>
        ids.includes(id),
      ).length;
      this.practices = this.practices.filter(({ id }) => !ids.includes(id));
      this.inventory = {
        ...this.inventory,
        enabledPractices: this.inventory.enabledPractices - changed,
      };
      return changed;
    },
    revokeGlobal: async () => {
      this.control = {
        ...this.control,
        enabled: false,
        generation: this.control.generation + BigInt(1),
        rollbackFenceState: "REVOKED",
        rollbackFenceGeneration:
          this.control.rollbackFenceGeneration + BigInt(1),
        rollbackRevokedAt: this.now,
      };
      return { ...this.control };
    },
    revokeOperation: async (input: { operationId: string }) => {
      const current = this.operations.get(input.operationId)!;
      const operation = {
        ...current,
        state: "REVOKED",
        revokedAt: this.now,
      };
      this.operations.set(input.operationId, operation);
      return operation;
    },
    enqueueAudit: async (input: {
      eventKey: string;
      action: string;
      targetType?: string | null;
    }) => {
      this.audits.push({
        eventKey: input.eventKey,
        action: input.action,
        targetType: input.targetType ?? undefined,
      });
      this.inventory = {
        ...this.inventory,
        pendingAuditOutboxEvents: this.inventory.pendingAuditOutboxEvents + 1,
      };
    },
  };

  dependencies(): TemplateTwinRollbackDependencies {
    return {
      transaction: async (callback) => callback(this.tx as never),
      inspect: async () => {
        throw new Error("inspect is not used by mutation tests");
      },
    };
  }
}

async function prepare(store: FakeRollbackStore, operationId = OPERATION_ID) {
  return prepareTemplateTwinRollback({
    operationId,
    reasonCode: "RELEASE_CRITERION_FAILED",
    changeId: "chg-template-twin-rollback-001",
    actor,
    dependencies: store.dependencies(),
  });
}

describe("Template Twin rollback fence operation", () => {
  it("prepares once, blocks new work through durable state, and retries idempotently", async () => {
    const store = new FakeRollbackStore();

    const first = await prepare(store);
    const repeated = await prepare(store);

    expect(first.idempotent).toBe(false);
    expect(first.status).toMatchObject({
      fenceState: "PREPARED",
      fenceGeneration: "2",
      globalRolloutEnabled: true,
      readyToRevoke: true,
    });
    expect(repeated.idempotent).toBe(true);
    expect(repeated.status.fenceGeneration).toBe("2");
    expect(store.audits.map(({ action }) => action)).toEqual([
      "TEMPLATE_TWIN_ROLLBACK_PREPARED",
    ]);
  });

  it("does not let a second operation steal an engaged fence", async () => {
    const store = new FakeRollbackStore();
    await prepare(store);

    await expect(prepare(store, OTHER_OPERATION_ID)).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_ROLLBACK_OPERATION_CONFLICT",
    });
    expect(store.control.rollbackOperationId).toBe(OPERATION_ID);
  });

  it("rejects reuse of an operation id with different immutable request identity", async () => {
    const store = new FakeRollbackStore();
    await prepare(store);

    await expect(
      prepareTemplateTwinRollback({
        operationId: OPERATION_ID,
        reasonCode: "A_DIFFERENT_REASON",
        changeId: "chg-template-twin-rollback-002",
        actor,
        dependencies: store.dependencies(),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_ROLLBACK_OPERATION_CONFLICT",
    });
    expect(store.audits).toHaveLength(1);
  });

  it("reports and blocks unresolved provider or processing work before revoke", async () => {
    const store = new FakeRollbackStore();
    store.inventory = emptyInventory({
      processingSyntheticRuns: 1,
      providerExecutionsUnknown: 1,
    });
    await prepare(store);

    await expect(
      revokeTemplateTwinRollout({
        operationId: OPERATION_ID,
        actor,
        dependencies: store.dependencies(),
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_ROLLBACK_IN_FLIGHT_WORK",
      status: {
        blockingInFlight: [
          "PROCESSING_SYNTHETIC_RUNS",
          "UNKNOWN_PROVIDER_OUTCOMES",
        ],
      },
    });
    expect(store.control.rollbackFenceState).toBe("PREPARED");
    expect(store.templates).toHaveLength(2);
    expect(store.practices).toHaveLength(2);
  });

  it("atomically deactivates Twins, disables rollout, preserves signed evidence, and retries idempotently", async () => {
    const store = new FakeRollbackStore();
    await prepare(store);

    const first = await revokeTemplateTwinRollout({
      operationId: OPERATION_ID,
      actor,
      dependencies: store.dependencies(),
    });
    const auditCount = store.audits.length;

    expect(first.idempotent).toBe(false);
    expect(first.status).toMatchObject({
      fenceState: "REVOKED",
      globalRolloutEnabled: false,
      globalRolloutGeneration: "8",
      rollbackComplete: false,
      inventory: {
        activeTemplateVersions: 0,
        enabledPractices: 0,
        signedFillManifests: 3,
        pendingAuditOutboxEvents: auditCount,
      },
    });
    expect(first.operation.state).toBe("REVOKED");
    store.inventory = {
      ...store.inventory,
      pendingAuditOutboxEvents: 0,
    };
    const repeated = await revokeTemplateTwinRollout({
      operationId: OPERATION_ID,
      actor,
      dependencies: store.dependencies(),
    });
    expect(repeated.idempotent).toBe(true);
    expect(repeated.status.rollbackComplete).toBe(true);
    expect(store.audits).toHaveLength(auditCount);
    expect(
      store.audits.filter(
        ({ action }) => action === "TEMPLATE_TWIN_DEACTIVATED",
      ),
    ).toHaveLength(4);
    expect(store.audits.at(-1)?.action).toBe("TEMPLATE_TWIN_ROLLOUT_REVOKED");
  });

  it("keeps completion false until both audit and object maintenance backlogs clear", async () => {
    const store = new FakeRollbackStore();
    store.inventory = emptyInventory({ objectMaintenanceBacklog: 1 });
    await prepare(store);
    const revoked = await revokeTemplateTwinRollout({
      operationId: OPERATION_ID,
      actor,
      dependencies: store.dependencies(),
    });
    expect(revoked.status.rollbackComplete).toBe(false);

    store.inventory = {
      ...store.inventory,
      pendingAuditOutboxEvents: 0,
    };
    const auditClear = await revokeTemplateTwinRollout({
      operationId: OPERATION_ID,
      actor,
      dependencies: store.dependencies(),
    });
    expect(auditClear.status.rollbackComplete).toBe(false);

    store.inventory = {
      ...store.inventory,
      objectMaintenanceBacklog: 0,
    };
    const reconciled = await revokeTemplateTwinRollout({
      operationId: OPERATION_ID,
      actor,
      dependencies: store.dependencies(),
    });
    expect(reconciled.status.rollbackComplete).toBe(true);
  });

  it("cancels only a prepared fence without changing global or practice rollout", async () => {
    const store = new FakeRollbackStore();
    await prepare(store);

    const first = await cancelPreparedTemplateTwinRollback({
      operationId: OPERATION_ID,
      actor,
      dependencies: store.dependencies(),
    });
    const repeated = await cancelPreparedTemplateTwinRollback({
      operationId: OPERATION_ID,
      actor,
      dependencies: store.dependencies(),
    });

    expect(first).toMatchObject({
      idempotent: false,
      operation: { state: "CANCELLED" },
      status: {
        fenceState: "OPEN",
        globalRolloutEnabled: true,
        globalRolloutGeneration: "7",
      },
    });
    expect(repeated.idempotent).toBe(true);
    expect(store.templates).toHaveLength(2);
    expect(store.practices).toHaveLength(2);
  });
});
