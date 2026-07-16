#!/usr/bin/env tsx

// Actual-PostgreSQL rollout proof for an already-migrated disposable QA
// database. This imports the production rollout lock/mutation, audit-outbox,
// and object-ledger helpers. It then uses independent connections and
// database-observed blocking to prove a stale final claim cannot mutate the
// clinical fill or claim its object. No production target is accepted.

import { performance } from "node:perf_hooks";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";

import { enqueueTemplateTwinAudit } from "../../../apps/transcribe-md/src/lib/template-twin/audit-outbox";
import {
  applyTemplateTwinGlobalRolloutMutation,
  applyTemplateTwinPracticeRolloutMutation,
  lockTemplateTwinRolloutForFinalClaim,
  type TemplateTwinRolloutToken,
} from "../../../apps/transcribe-md/src/lib/template-twin/rollout";
import { claimTemplateTwinObject } from "../../../apps/transcribe-md/src/lib/template-twin/storage/object-ledger";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_ROLLOUT_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
assertNonProdDatabase(databaseUrl);
if (!databaseUrl) throw new Error("Disposable rollout test URL is required.");
const verifiedDatabaseUrl = databaseUrl;
process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";

const suffix = `${process.pid}-${Date.now()}`;
const practiceId = `synthetic-rollout-pg-${suffix}`;
const actorId = `synthetic-rollout-actor-${suffix}`;
const actorEmail = `rollout-${suffix}@synthetic.test`;
const patientId = `synthetic-rollout-patient-${suffix}`;
const visitId = `synthetic-rollout-visit-${suffix}`;
const noteTemplateId = `synthetic-rollout-template-${suffix}`;
const sourceArtifactId = `synthetic-rollout-source-${suffix}`;
const compiledVersionId = `synthetic-rollout-compiled-${suffix}`;
const fillId = `synthetic-rollout-fill-${suffix}`;
const outputArtifactId = `synthetic-rollout-artifact-${suffix}`;
const objectKey =
  `practices/${practiceId}/template-twin/outputs/${visitId}/` +
  `${"a".repeat(64)}/${outputArtifactId}/${"a".repeat(64)}.docx`;
const globalId = "global";
const syntheticSha = "a".repeat(64);

function client(applicationName: string): PrismaClient {
  const url = new URL(verifiedDatabaseUrl);
  url.searchParams.set("application_name", applicationName);
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString: url.toString() }),
  });
}

function latch<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const finalClient = client("template-twin-rollout-pg-final");
const mutationClient = client("template-twin-rollout-pg-mutation");
const observer = client("template-twin-rollout-pg-observer");

const actor = {
  userId: actorId,
  userEmail: actorEmail,
  practiceId,
};

interface StateSnapshot {
  fillStatus: string;
  fillOutputObjectKey: string | null;
  ledgerState: string;
  ledgerClaimType: string | null;
  ledgerClaimId: string | null;
}

interface RevocationProof {
  scope: "practice" | "global";
  blockingObserved: boolean;
  blockingPidCount: number;
  blockedLockMs: number;
  pinnedGlobalGeneration: string;
  pinnedPracticeGeneration: string;
  rejectionCode: string;
  clinicalStateUnchanged: boolean;
  objectRemainedReconcilable: boolean;
  blockerAuditCommitted: boolean;
}

async function waitUntilBlocked(pid: number): Promise<number[]> {
  for (let attempt = 0; attempt < 5_000; attempt += 1) {
    const rows = await observer.$queryRawUnsafe<Array<{ blockers: number[] }>>(
      "SELECT pg_blocking_pids($1) AS blockers",
      pid,
    );
    const blockers = rows[0]?.blockers ?? [];
    if (blockers.length > 0) return blockers;
  }
  throw new Error(
    "PostgreSQL never reported the final-claim transaction as blocked.",
  );
}

async function readState(): Promise<StateSnapshot> {
  const [fill, ledger] = await Promise.all([
    observer.templateTwinFillManifest.findUniqueOrThrow({
      where: { id: fillId },
      select: { status: true, outputObjectKey: true },
    }),
    observer.templateTwinObjectLedger.findUniqueOrThrow({
      where: { objectKey },
      select: { state: true, claimType: true, claimId: true },
    }),
  ]);
  return {
    fillStatus: fill.status,
    fillOutputObjectKey: fill.outputObjectKey,
    ledgerState: ledger.state,
    ledgerClaimType: ledger.claimType,
    ledgerClaimId: ledger.claimId,
  };
}

async function resetClaimState(token: TemplateTwinRolloutToken): Promise<void> {
  await observer.$transaction(async (tx) => {
    await tx.templateTwinFillManifest.update({
      where: { id: fillId },
      data: {
        status: "NEEDS_REVIEW",
        outputObjectKey: null,
        outputVersionId: null,
        outputEtag: null,
        outputSha256: null,
        outputMimeType: null,
        outputSizeBytes: null,
        staticContentSha256: null,
        roundTripVerified: false,
        pinnedGlobalRolloutGeneration: token.globalGeneration,
        pinnedPracticeRolloutGeneration: token.practiceGeneration,
        signedGlobalRolloutGeneration: null,
        signedPracticeRolloutGeneration: null,
      },
    });
    await tx.templateTwinObjectLedger.update({
      where: { objectKey },
      data: {
        state: "WRITTEN_UNCLAIMED",
        claimType: null,
        claimId: null,
        lastErrorCode: null,
      },
    });
  });
}

async function enableBothScopes(): Promise<TemplateTwinRolloutToken> {
  await observer.$transaction((tx) =>
    applyTemplateTwinGlobalRolloutMutation({ tx, enabled: true, actor }),
  );
  await observer.$transaction((tx) =>
    applyTemplateTwinPracticeRolloutMutation({
      tx,
      practiceId,
      enabled: true,
      actor,
    }),
  );
  const pinned = await observer.$transaction((tx) =>
    lockTemplateTwinRolloutForFinalClaim({ tx, practiceId }),
  );
  if (!pinned.allowed) {
    throw new Error(`Rollout admission failed: ${pinned.code}`);
  }
  return pinned.token;
}

async function runFinalOutputClaim(input: {
  tx: Prisma.TransactionClient;
  token: TemplateTwinRolloutToken;
  eventKey: string;
}): Promise<{ allowed: boolean; code?: string }> {
  const decision = await lockTemplateTwinRolloutForFinalClaim({
    tx: input.tx,
    practiceId,
    pinnedToken: input.token,
  });
  if (!decision.allowed) {
    await enqueueTemplateTwinAudit(input.tx, {
      eventKey: input.eventKey,
      practiceId,
      actorId,
      actorEmailSnapshot: actorEmail,
      action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
      targetType: "TemplateTwinFillManifest",
      targetId: fillId,
      metadata: {
        reasonCode: decision.code,
        operation: "postgres_final_output_claim_probe",
      },
    });
    return { allowed: false, code: decision.code };
  }

  const updated = await input.tx.templateTwinFillManifest.updateMany({
    where: {
      id: fillId,
      practiceId,
      status: "NEEDS_REVIEW",
      pinnedGlobalRolloutGeneration: input.token.globalGeneration,
      pinnedPracticeRolloutGeneration: input.token.practiceGeneration,
    },
    data: {
      status: "VERIFIED",
      outputObjectKey: objectKey,
      outputVersionId: "synthetic-output-version",
      outputEtag: "synthetic-output-etag",
      outputSha256: syntheticSha,
      outputMimeType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      outputSizeBytes: 4096,
      staticContentSha256: syntheticSha,
      roundTripVerified: true,
    },
  });
  if (updated.count !== 1) {
    throw new Error("Synthetic clinical final state lost its predicate.");
  }
  await claimTemplateTwinObject(input.tx, {
    objectKey,
    practiceId,
    claimType: "fill_manifest",
    claimId: fillId,
  });
  await enqueueTemplateTwinAudit(input.tx, {
    eventKey: input.eventKey,
    practiceId,
    actorId,
    actorEmailSnapshot: actorEmail,
    action: "TEMPLATE_TWIN_RENDER_VERIFIED",
    targetType: "TemplateTwinFillManifest",
    targetId: fillId,
    metadata: { operation: "postgres_final_output_claim_probe" },
  });
  return { allowed: true };
}

async function proveRevocation(
  scope: "practice" | "global",
): Promise<RevocationProof> {
  const token = await enableBothScopes();
  await resetClaimState(token);
  const before = await readState();
  const mutationReady = latch<void>();
  const releaseMutation = latch<void>();

  const mutation = mutationClient.$transaction(async (tx) => {
    if (scope === "global") {
      await applyTemplateTwinGlobalRolloutMutation({
        tx,
        enabled: false,
        actor,
      });
    } else {
      await applyTemplateTwinPracticeRolloutMutation({
        tx,
        practiceId,
        enabled: false,
        actor,
      });
    }
    mutationReady.resolve();
    await releaseMutation.promise;
  });
  await mutationReady.promise;

  const finalPid = latch<number>();
  let lockStartedAt = 0;
  const blockerEventKey = `template-twin:pg-proof:${scope}:blocked:${suffix}`;
  const finalClaim = finalClient.$transaction(async (tx) => {
    const pidRows = await tx.$queryRaw<Array<{ pid: number }>>(
      Prisma.sql`SELECT pg_backend_pid() AS pid`,
    );
    finalPid.resolve(pidRows[0]!.pid);
    lockStartedAt = performance.now();
    return runFinalOutputClaim({ tx, token, eventKey: blockerEventKey });
  });
  const blockers = await waitUntilBlocked(await finalPid.promise);
  releaseMutation.resolve();
  await mutation;
  const result = await finalClaim;
  const blockedLockMs = performance.now() - lockStartedAt;
  const after = await readState();
  const blockerAudit = await observer.templateTwinAuditOutbox.count({
    where: { eventKey: blockerEventKey, status: "PENDING" },
  });

  if (result.allowed || !result.code) {
    throw new Error(`${scope} revocation allowed a stale final claim.`);
  }
  const clinicalStateUnchanged =
    before.fillStatus === after.fillStatus &&
    before.fillOutputObjectKey === after.fillOutputObjectKey;
  const objectRemainedReconcilable =
    after.ledgerState === "WRITTEN_UNCLAIMED" &&
    after.ledgerClaimType === null &&
    after.ledgerClaimId === null;
  if (
    !clinicalStateUnchanged ||
    !objectRemainedReconcilable ||
    blockerAudit !== 1
  ) {
    throw new Error(
      `${scope} revocation did not fail closed across fill, ledger, and audit.`,
    );
  }
  return {
    scope,
    blockingObserved: blockers.length > 0,
    blockingPidCount: blockers.length,
    blockedLockMs,
    pinnedGlobalGeneration: token.globalGeneration.toString(),
    pinnedPracticeGeneration: token.practiceGeneration.toString(),
    rejectionCode: result.code,
    clinicalStateUnchanged,
    objectRemainedReconcilable,
    blockerAuditCommitted: blockerAudit === 1,
  };
}

async function proveOutboxFailureRollback(): Promise<boolean> {
  const token = await enableBothScopes();
  await resetClaimState(token);

  // Prove this exact fill tuple and ledger claim can commit before changing
  // only the audit event key to a deliberate unique-key collision.
  const controlEventKey = `template-twin:pg-proof:valid-claim:${suffix}`;
  const control = await finalClient.$transaction((tx) =>
    runFinalOutputClaim({ tx, token, eventKey: controlEventKey }),
  );
  const controlState = await readState();
  if (
    !control.allowed ||
    controlState.fillStatus !== "VERIFIED" ||
    controlState.fillOutputObjectKey !== objectKey ||
    controlState.ledgerState !== "CLAIMED" ||
    controlState.ledgerClaimType !== "fill_manifest" ||
    controlState.ledgerClaimId !== fillId
  ) {
    throw new Error("The valid final-claim control did not commit.");
  }
  await resetClaimState(token);
  const before = await readState();
  const collisionKey = `template-twin:pg-proof:outbox-collision:${suffix}`;
  await observer.templateTwinAuditOutbox.create({
    data: {
      eventKey: collisionKey,
      practiceId,
      actorId,
      actorEmailSnapshot: actorEmail,
      action: "TEMPLATE_TWIN_SAFETY_GATE_BLOCKED",
      targetType: "TemplateTwinFillManifest",
      targetId: fillId,
      metadata: { operation: "postgres_outbox_rollback_sentinel" },
      status: "PENDING",
      attemptCount: 0,
    },
  });

  let failureCode: string | null = null;
  let failureWasAuditOutboxUniqueCollision = false;
  try {
    await finalClient.$transaction((tx) =>
      runFinalOutputClaim({ tx, token, eventKey: collisionKey }),
    );
  } catch (error) {
    const candidate = error as {
      code?: unknown;
      message?: unknown;
      meta?: unknown;
    };
    failureCode = typeof candidate.code === "string" ? candidate.code : null;
    const diagnostic = `${String(candidate.message ?? "")} ${JSON.stringify(candidate.meta ?? null)}`;
    failureWasAuditOutboxUniqueCollision =
      failureCode === "P2002" &&
      /TemplateTwinAuditOutbox|template_twin_audit_outbox|eventKey/i.test(
        diagnostic,
      );
  }
  const after = await readState();
  const eventCount = await observer.templateTwinAuditOutbox.count({
    where: { eventKey: collisionKey },
  });
  const rolledBack =
    failureWasAuditOutboxUniqueCollision &&
    eventCount === 1 &&
    JSON.stringify(after) === JSON.stringify(before);
  if (!rolledBack) {
    throw new Error(
      `Expected audit-outbox P2002 did not roll back fill/object claim (code=${failureCode ?? "none"}).`,
    );
  }
  return true;
}

async function createSyntheticFixture(): Promise<void> {
  await observer.practice.create({
    data: {
      id: practiceId,
      name: "Synthetic rollout transaction practice",
      slug: practiceId,
      templateTwinEnabled: false,
    },
  });
  await observer.user.create({
    data: {
      id: actorId,
      email: actorEmail,
      passwordHash: "synthetic-not-a-login-credential",
      role: "DOCTOR",
      practiceId,
    },
  });
  await observer.transcribeMdPatient.create({
    data: {
      id: patientId,
      practiceId,
      name: "Synthetic Patient",
    },
  });
  await observer.noteTemplate.create({
    data: {
      id: noteTemplateId,
      doctorId: actorId,
      name: "Synthetic rollout proof template",
      sections: [],
      version: 1,
      versionDescription: "Synthetic transaction proof",
      status: "draft",
      lineageId: noteTemplateId,
      templateKind: "template_twin_docx",
    },
  });
  await observer.templateTwinSourceArtifact.create({
    data: {
      id: sourceArtifactId,
      practiceId,
      createdById: actorId,
      lineageId: noteTemplateId,
      lineageVersion: 1,
      sha256: syntheticSha,
      mimeType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      sizeBytes: 4096,
      validationStatus: "quarantined",
      rejectionCodes: ["SYNTHETIC_PG_TRANSACTION_FIXTURE"],
    },
  });
  await observer.templateTwinCompiledVersion.create({
    data: {
      id: compiledVersionId,
      sourceArtifactId,
      noteTemplateId,
      compilerVersion: "synthetic-compiler-v1",
      irSchemaVersion: 1,
      compiledDocumentIr: { synthetic: true },
      unsupportedElements: [],
      structureSha256: syntheticSha,
      staticContentSha256: syntheticSha,
      certificationStatus: "NEEDS_CONFIRMATION",
    },
  });
  await observer.transcribeVisit.create({
    data: {
      id: visitId,
      userId: actorId,
      patientId,
      specialty: "synthetic",
      inputMode: "text_notes",
      status: "READY",
      soapFinal: "Synthetic SOAP content only.",
      noteTemplateId,
      noteTemplateVersion: 1,
    },
  });
  await observer.templateTwinFillManifest.create({
    data: {
      id: fillId,
      practiceId,
      visitId,
      compiledVersionId,
      noteTemplateId,
      noteTemplateVersion: 1,
      compilerVersion: "synthetic-compiler-v1",
      resolverVersion: "synthetic-resolver-v1",
      rendererVersion: "synthetic-renderer-v1",
      status: "NEEDS_REVIEW",
      fillManifest: { synthetic: true },
      manifestSha256: syntheticSha,
      factSetSha256: syntheticSha,
      soapVersion: 1,
      soapSha256: syntheticSha,
      validationResult: { synthetic: true },
    },
  });
  await observer.templateTwinObjectLedger.create({
    data: {
      practiceId,
      objectKey,
      objectVersionId: "synthetic-output-version",
      objectEtag: "synthetic-output-etag",
      sha256: syntheticSha,
      sizeBytes: 4096,
      kind: "output",
      state: "WRITTEN_UNCLAIMED",
      retentionUntil: new Date("2099-01-01T00:00:00.000Z"),
    },
  });
}

async function main(): Promise<void> {
  const lineage = await observer.$queryRawUnsafe<Array<{ phase: string }>>(
    `SELECT phase
     FROM template_twin_lineage_migration_progress
     WHERE "operationKey" = 'note_templates_lineage_v1'`,
  );
  if (lineage[0]?.phase !== "CONTRACTED") {
    throw new Error(
      "Disposable QA lineage must be CONTRACTED before rollout proof.",
    );
  }
  await createSyntheticFixture();
  const practice = await proveRevocation("practice");
  const global = await proveRevocation("global");
  const outboxFailureRolledBack = await proveOutboxFailureRollback();

  process.stdout.write(
    `${JSON.stringify({
      profile: "template-twin-rollout-postgres-v2",
      synthetic: true,
      databaseGuard: "passed",
      productionProtocolHelpersExercised: [
        "applyTemplateTwinGlobalRolloutMutation",
        "applyTemplateTwinPracticeRolloutMutation",
        "lockTemplateTwinRolloutForFinalClaim",
        "claimTemplateTwinObject",
        "enqueueTemplateTwinAudit",
      ],
      practice,
      global,
      outboxFailureRolledBack,
      fixtureLifecycle:
        "retained only in the disposable database because source artifacts are immutable",
    })}\n`,
  );
}

void main()
  .catch((error: unknown) => {
    process.stderr.write(
      `${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`,
    );
    process.exitCode = 1;
  })
  .finally(async () => {
    await Promise.all([
      finalClient.$disconnect(),
      mutationClient.$disconnect(),
      observer.$disconnect(),
    ]);
  });
