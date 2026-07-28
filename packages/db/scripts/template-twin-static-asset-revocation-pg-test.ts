#!/usr/bin/env tsx

// Actual-PostgreSQL proof that a Template Twin source/certification claim and
// a practice static-asset revocation have one database-linearized order. The
// harness imports the production lock/revalidation and revocation helpers,
// uses database-observed lock blocking instead of timing sleeps, and refuses
// any database that is not positively identified as disposable QA/test.

import { createHash } from "node:crypto";
import { deflateSync } from "node:zlib";

import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@prisma/client";

import {
  approveTemplateTwinStaticAsset,
  inspectTemplateTwinStaticAssetForReview,
  lockAndAssertTemplateTwinStaticAssetBindingsCurrent,
  revokeTemplateTwinStaticAsset,
  TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
  type TemplateTwinStaticAssetApprovalBinding,
  type TemplateTwinStaticAssetClaimDb,
  type TemplateTwinStaticAssetDb,
  type TemplateTwinStaticAssetActor,
} from "../../../apps/transcribe-md/src/lib/template-twin/static-assets";
import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl =
  process.env.TEMPLATE_TWIN_STATIC_ASSET_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
assertNonProdDatabase(databaseUrl);
if (!databaseUrl) {
  throw new Error("A disposable static-asset test database URL is required.");
}
const verifiedDatabaseUrl = databaseUrl;

const suffix = `${process.pid}-${Date.now()}`;
const practiceId = `synthetic-static-asset-practice-${suffix}`;
const adminId = `synthetic-static-asset-admin-${suffix}`;
const adminEmail = `static-asset-${suffix}@synthetic.test`;
const revokerApplicationName = `tt-static-asset-revoker-${suffix}`;
let assetId = "";
let digest = "";
let inspectionDigest = "";
let privacyDigest = "";
process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
let globalRolloutGeneration = BigInt(1);
let practiceRolloutGeneration = BigInt(1);

interface RawSqlDb {
  $executeRawUnsafe(query: string, ...values: unknown[]): Promise<number>;
}

function client(applicationName: string): PrismaClient {
  const url = new URL(verifiedDatabaseUrl);
  url.searchParams.set("application_name", applicationName);
  return new PrismaClient({
    adapter: new PrismaPg({
      connectionString: url.toString(),
      max: 1,
      connectionTimeoutMillis: 10_000,
    }),
  });
}

function latch(): { promise: Promise<void>; release: () => void } {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

const claimant = client(`tt-static-asset-claimant-${suffix}`);
const revoker = client(revokerApplicationName);
const observer = client(`tt-static-asset-observer-${suffix}`);

let binding: TemplateTwinStaticAssetApprovalBinding;

function staticAssetActor(): TemplateTwinStaticAssetActor {
  return {
    userId: adminId,
    userEmail: adminEmail,
    practiceId,
    role: "ADMIN",
    rolloutToken: {
      practiceId,
      globalGeneration: globalRolloutGeneration,
      practiceGeneration: practiceRolloutGeneration,
    },
  };
}

const syntheticOcr = {
  async scan() {
    return {
      local: true as const,
      complete: true as const,
      engineVersion: "synthetic-local-ocr/1.0",
      text: "Synthetic Clinic",
    };
  },
};

const syntheticPrivacyClient = {
  async complete() {
    return { phiFields: [], anyUncertain: false };
  },
};

async function waitUntilRevocationBlocked(): Promise<{
  pid: number;
  waitEvent: string;
}> {
  for (let attempt = 0; attempt < 5_000; attempt += 1) {
    const rows = await observer.$queryRawUnsafe<
      Array<{ pid: number; waitEvent: string | null }>
    >(
      `SELECT pid, wait_event AS "waitEvent"
       FROM pg_stat_activity
       WHERE application_name = $1
         AND wait_event_type = 'Lock'`,
      revokerApplicationName,
    );
    const row = rows[0];
    if (row?.waitEvent) return { pid: row.pid, waitEvent: row.waitEvent };
    await new Promise<void>((resolve) => setImmediate(resolve));
  }
  throw new Error(
    "PostgreSQL never reported static-asset revocation waiting on the final-claim lock.",
  );
}

async function createSyntheticFixture(): Promise<void> {
  const lineage = await observer.$queryRawUnsafe<Array<{ phase: string }>>(
    `SELECT "phase"
     FROM "template_twin_lineage_migration_progress"
     WHERE "operationKey" = 'note_templates_lineage_v1'`,
  );
  if (lineage[0]?.phase !== "CONTRACTED") {
    throw new Error(
      "Disposable QA lineage must be CONTRACTED before static-asset proof.",
    );
  }
  await observer.practice.create({
    data: {
      id: practiceId,
      name: "Synthetic static asset concurrency practice",
      slug: practiceId,
    },
  });
  await observer.user.create({
    data: {
      id: adminId,
      email: adminEmail,
      passwordHash: "synthetic-not-a-login-credential",
      role: "ADMIN",
      practiceId,
    },
  });
  const [globalRollout, practiceRollout] = await observer.$transaction([
    observer.templateTwinRolloutControl.update({
      where: { id: "global" },
      data: { enabled: true, generation: { increment: 1 } },
      select: { generation: true },
    }),
    observer.practice.update({
      where: { id: practiceId },
      data: {
        templateTwinEnabled: true,
        templateTwinRolloutGeneration: { increment: 1 },
      },
      select: { templateTwinRolloutGeneration: true },
    }),
  ]);
  globalRolloutGeneration = globalRollout.generation;
  practiceRolloutGeneration =
    practiceRollout.templateTwinRolloutGeneration;
  const bytes = syntheticPng();
  const review = await inspectTemplateTwinStaticAssetForReview({
    bytes,
    claimedMimeType: "image/png",
    actor: staticAssetActor(),
    ocr: syntheticOcr,
    client: syntheticPrivacyClient,
    db: observer as unknown as TemplateTwinStaticAssetDb,
  });
  const reviewReceiptId = review.previewReviewReceipt.split(".")[0]!;
  const beforeApproval =
    await observer.templateTwinStaticAssetReviewReceipt.findUniqueOrThrow({
      where: { id: reviewReceiptId },
      select: { consumedAt: true },
    });
  if (beforeApproval.consumedAt !== null) {
    throw new Error("Production inspection persisted a pre-consumed receipt.");
  }
  binding = await approveTemplateTwinStaticAsset({
    bytes,
    claimedMimeType: "image/png",
    actor: staticAssetActor(),
    ocr: syntheticOcr,
    client: syntheticPrivacyClient,
    previewReviewReceipt: review.previewReviewReceipt,
    expectedSha256: review.evidence.sha256,
    attestedReusableBlankAsset: true,
    reason: "Synthetic reusable blank image approval.",
    db: observer as unknown as TemplateTwinStaticAssetDb,
  });
  assetId = binding.assetId;
  digest = binding.sha256;
  inspectionDigest = binding.inspectionEvidenceSha256;
  privacyDigest = binding.privacyEvidenceSha256;
  const afterApproval =
    await observer.templateTwinStaticAssetReviewReceipt.findUniqueOrThrow({
      where: { id: reviewReceiptId },
      select: { consumedAt: true, expiresAt: true },
    });
  if (
    afterApproval.consumedAt === null ||
    afterApproval.consumedAt > afterApproval.expiresAt
  ) {
    throw new Error("Production approval did not consume a valid receipt.");
  }

  const repeatReview = await inspectTemplateTwinStaticAssetForReview({
    bytes,
    claimedMimeType: "image/png",
    actor: staticAssetActor(),
    ocr: syntheticOcr,
    client: syntheticPrivacyClient,
    db: observer as unknown as TemplateTwinStaticAssetDb,
  });
  const repeatReceiptId = repeatReview.previewReviewReceipt.split(".")[0]!;
  binding = await approveTemplateTwinStaticAsset({
    bytes,
    claimedMimeType: "image/png",
    actor: staticAssetActor(),
    ocr: syntheticOcr,
    client: syntheticPrivacyClient,
    previewReviewReceipt: repeatReview.previewReviewReceipt,
    expectedSha256: repeatReview.evidence.sha256,
    attestedReusableBlankAsset: true,
    reason: "Synthetic repeat approval records a fresh decision.",
    db: observer as unknown as TemplateTwinStaticAssetDb,
  });
  const repeatReceipt =
    await observer.templateTwinStaticAssetReviewReceipt.findUniqueOrThrow({
      where: { id: repeatReceiptId },
      select: { consumedAt: true, expiresAt: true },
    });
  if (
    binding.decisionVersion !== 2 ||
    repeatReceipt.consumedAt === null ||
    repeatReceipt.consumedAt > repeatReceipt.expiresAt
  ) {
    throw new Error(
      "A repeat production approval did not append a decision and consume its fresh receipt.",
    );
  }
}

function syntheticPng(): Uint8Array {
  const width = 2;
  const height = 2;
  const ihdr = new Uint8Array(13);
  writeU32(ihdr, 0, width);
  writeU32(ihdr, 4, height);
  ihdr.set([8, 6, 0, 0, 0], 8);
  const scanlines = new Uint8Array((width * 4 + 1) * height);
  for (let row = 0; row < height; row += 1) {
    scanlines[row * (width * 4 + 1)] = 0;
    scanlines.fill(
      0x7f,
      row * (width * 4 + 1) + 1,
      (row + 1) * (width * 4 + 1),
    );
  }
  return concat(
    Uint8Array.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    pngChunk("IHDR", ihdr),
    pngChunk("IDAT", deflateSync(scanlines)),
    pngChunk("IEND", new Uint8Array()),
  );
}

function pngChunk(type: string, data: Uint8Array): Uint8Array {
  const typeBytes = new TextEncoder().encode(type);
  const output = new Uint8Array(12 + data.byteLength);
  writeU32(output, 0, data.byteLength);
  output.set(typeBytes, 4);
  output.set(data, 8);
  writeU32(output, 8 + data.byteLength, crc32(concat(typeBytes, data)));
  return output;
}

function concat(...values: Uint8Array[]): Uint8Array {
  const output = new Uint8Array(
    values.reduce((total, value) => total + value.byteLength, 0),
  );
  let offset = 0;
  for (const value of values) {
    output.set(value, offset);
    offset += value.byteLength;
  }
  return output;
}

function writeU32(bytes: Uint8Array, offset: number, value: number): void {
  bytes[offset] = (value >>> 24) & 0xff;
  bytes[offset + 1] = (value >>> 16) & 0xff;
  bytes[offset + 2] = (value >>> 8) & 0xff;
  bytes[offset + 3] = value & 0xff;
}

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

async function expectDatabaseRejection(
  label: string,
  expectedCode: RegExp,
  operation: () => Promise<unknown>,
): Promise<string> {
  try {
    await operation();
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error);
    if (expectedCode.test(text)) return label;
    throw new Error(`${label} failed with the wrong database error: ${text}`);
  }
  throw new Error(`${label} unexpectedly passed.`);
}

async function insertRawReceipt(input: {
  id: string;
  inspectionEvidenceSha256?: string;
  scannerVersion?: string;
  ocrEngineVersion?: string;
  privacyEvidenceSha256?: string;
  globalGeneration?: bigint;
  practiceGeneration?: bigint;
  expiresSql?: string;
  consumedSql?: string;
}, db: RawSqlDb = observer as unknown as RawSqlDb): Promise<void> {
  const expiresSql = input.expiresSql ?? "CURRENT_TIMESTAMP + INTERVAL '10 minutes'";
  const consumedSql = input.consumedSql ?? "NULL";
  await db.$executeRawUnsafe(
    `INSERT INTO "template_twin_static_asset_review_receipts" (
       "id", "practiceId", "reviewedById", "tokenSha256", "assetSha256",
       "inspectionEvidenceSha256", "scannerVersion", "ocrEngineVersion",
       "privacyEvidenceSha256", "globalRolloutGeneration",
       "practiceRolloutGeneration", "expiresAt", "consumedAt"
     ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,${expiresSql},${consumedSql})`,
    input.id,
    practiceId,
    adminId,
    createHash("sha256").update(input.id).digest("hex"),
    digest,
    input.inspectionEvidenceSha256 ?? inspectionDigest,
    input.scannerVersion ?? TEMPLATE_TWIN_STATIC_ASSET_SCANNER,
    input.ocrEngineVersion ?? "synthetic-local-ocr/1.0",
    input.privacyEvidenceSha256 ?? privacyDigest,
    input.globalGeneration ?? globalRolloutGeneration,
    input.practiceGeneration ?? practiceRolloutGeneration,
  );
}

async function consumeRawReceipt(
  id: string,
  db: RawSqlDb = observer as unknown as RawSqlDb,
): Promise<void> {
  const count = await db.$executeRawUnsafe(
    `UPDATE "template_twin_static_asset_review_receipts"
     SET "consumedAt" = CURRENT_TIMESTAMP WHERE "id" = $1`,
    id,
  );
  if (count !== 1) throw new Error(`Receipt ${id} was not consumed once.`);
}

function rawApprovalIdentity(label: string): {
  decisionId: string;
  auditEventKey: string;
} {
  const decisionId = `synthetic-adversarial-decision-${label}-${suffix}`;
  return {
    decisionId,
    auditEventKey: `template-twin:static-asset-approved:${decisionId}`,
  };
}

async function insertRawApprovalAudit(
  label: string,
  options: {
    action?: string;
    practiceId?: string;
    actorId?: string;
    targetId?: string;
    metadataDecisionId?: string;
  } = {},
  db: RawSqlDb = observer as unknown as RawSqlDb,
): Promise<void> {
  const identity = rawApprovalIdentity(label);
  await db.$executeRawUnsafe(
    `INSERT INTO "template_twin_audit_outbox" (
       "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
       "action", "targetId", "targetType", "metadata", "status", "attemptCount",
       "updatedAt"
     ) VALUES ($1,$2,$3,$4,$5,$6::"AuditAction",$7,'TemplateTwinStaticAsset',$8::jsonb,'PENDING',0,CURRENT_TIMESTAMP)`,
    `synthetic-adversarial-audit-${label}-${suffix}`,
    options.practiceId ?? practiceId,
    options.actorId ?? adminId,
    adminEmail,
    identity.auditEventKey,
    options.action ?? "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
    options.targetId ?? assetId,
    JSON.stringify({
      decisionId: options.metadataDecisionId ?? identity.decisionId,
      synthetic: true,
    }),
  );
}

async function attemptRawApproval(
  receiptId: string,
  label: string,
  db: RawSqlDb = observer as unknown as RawSqlDb,
): Promise<string> {
  const identity = rawApprovalIdentity(label);
  await db.$executeRawUnsafe(
    `INSERT INTO "template_twin_static_asset_decisions" (
       "id", "assetId", "version", "decision", "reason",
       "attestedReusableBlankAsset", "inspectionEvidenceSha256",
       "reviewReceiptId", "auditEventKey", "decidedById"
     ) VALUES ($1,$2,$3,'APPROVED',$4,true,$5,$6,$7,$8)`,
    identity.decisionId,
    assetId,
    binding.decisionVersion + 1,
    "Synthetic direct database approval proof.",
    inspectionDigest,
    receiptId,
    identity.auditEventKey,
    adminId,
  );
  return identity.decisionId;
}

async function runReceiptAdversarialProofs(): Promise<string[]> {
  const rejected: string[] = [];
  const preConsumedId = `synthetic-preconsumed-${suffix}`;
  rejected.push(
    await expectDatabaseRejection(
      "pre-consumed receipt insert",
      /TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID/,
      () =>
        insertRawReceipt({
          id: preConsumedId,
          consumedSql: "CURRENT_TIMESTAMP",
        }),
    ),
  );
  rejected.push(
    await expectDatabaseRejection(
      "expired receipt insert",
      /TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID/,
      () =>
        insertRawReceipt({
          id: `synthetic-expired-${suffix}`,
          expiresSql: "CURRENT_TIMESTAMP - INTERVAL '1 second'",
        }),
    ),
  );
  rejected.push(
    await expectDatabaseRejection(
      "stale global rollout generation receipt",
      /TT_STATIC_ASSET_ROLLOUT_STALE/,
      () =>
        insertRawReceipt({
          id: `synthetic-generation-${suffix}`,
          globalGeneration: globalRolloutGeneration + BigInt(1),
        }),
    ),
  );
  rejected.push(
    await expectDatabaseRejection(
      "stale practice rollout generation receipt",
      /TT_STATIC_ASSET_ROLLOUT_STALE/,
      () =>
        insertRawReceipt({
          id: `synthetic-practice-generation-${suffix}`,
          practiceGeneration: practiceRolloutGeneration + BigInt(1),
        }),
    ),
  );

  const replayId = `synthetic-replay-${suffix}`;
  await insertRawReceipt({ id: replayId });
  await consumeRawReceipt(replayId);
  rejected.push(
    await expectDatabaseRejection(
      "second receipt consumption",
      /TEMPLATE_TWIN_STATIC_ASSET_REVIEW_RECEIPT_IMMUTABLE/,
      () => consumeRawReceipt(replayId),
    ),
  );

  const missingOutboxReceiptId = `synthetic-missing-outbox-${suffix}`;
  await insertRawReceipt({ id: missingOutboxReceiptId });
  await consumeRawReceipt(missingOutboxReceiptId);
  rejected.push(
    await expectDatabaseRejection(
      "decision without audit outbox",
      /TT_STATIC_ASSET_AUDIT_OUTBOX_INVALID/,
      () =>
        attemptRawApproval(
          missingOutboxReceiptId,
          "missing-outbox",
        ),
    ),
  );

  rejected.push(
    await expectDatabaseRejection(
      "decision with mismatched audit outbox",
      /TT_STATIC_ASSET_AUDIT_OUTBOX_INVALID/,
      () =>
        observer.$transaction(async (tx) => {
          const db = tx as unknown as RawSqlDb;
          const id = `synthetic-mismatched-outbox-${suffix}`;
          await insertRawReceipt({ id }, db);
          await consumeRawReceipt(id, db);
          await insertRawApprovalAudit(
            "mismatched-outbox",
            { action: "TEMPLATE_TWIN_STATIC_ASSET_REJECTED" },
            db,
          );
          await attemptRawApproval(id, "mismatched-outbox", db);
        }),
    ),
  );

  const mismatches = [
    {
      label: "wrong inspection evidence",
      receipt: { inspectionEvidenceSha256: "1".repeat(64) },
    },
    {
      label: "wrong scanner version",
      receipt: { scannerVersion: "synthetic-wrong-scanner/1.0" },
    },
    {
      label: "wrong OCR version",
      receipt: { ocrEngineVersion: "synthetic-wrong-ocr/1.0" },
    },
    {
      label: "wrong privacy evidence",
      receipt: { privacyEvidenceSha256: "2".repeat(64) },
    },
  ] as const;
  for (const [index, mismatch] of mismatches.entries()) {
    rejected.push(
      await expectDatabaseRejection(
        mismatch.label,
        /TT_STATIC_ASSET_PREVIEW_RECEIPT_INVALID/,
        () =>
          observer.$transaction(async (tx) => {
            const db = tx as unknown as RawSqlDb;
            const id = `synthetic-mismatch-${index}-${suffix}`;
            const label = `receipt-mismatch-${index}`;
            await insertRawReceipt({ id, ...mismatch.receipt }, db);
            await consumeRawReceipt(id, db);
            await insertRawApprovalAudit(label, {}, db);
            await attemptRawApproval(id, label, db);
          }),
      ),
    );
  }
  return rejected;
}

async function proveSelfConsistentDirectSqlApproval(): Promise<string> {
  const label = "self-consistent";
  const receiptId = `synthetic-self-consistent-${suffix}`;
  await insertRawReceipt({ id: receiptId });
  await consumeRawReceipt(receiptId);
  await insertRawApprovalAudit(label);
  const decisionId = await attemptRawApproval(receiptId, label);
  const [proof] = await observer.$queryRawUnsafe<
    Array<{
      decisionId: string;
      auditEventKey: string;
      action: string;
      status: string;
    }>
  >(
    `SELECT decision."id" AS "decisionId",
            decision."auditEventKey" AS "auditEventKey",
            outbox."action"::text AS "action",
            outbox."status"::text AS "status"
     FROM "template_twin_static_asset_decisions" decision
     JOIN "template_twin_audit_outbox" outbox
       ON outbox."eventKey" = decision."auditEventKey"
     WHERE decision."id" = $1`,
    decisionId,
  );
  if (
    proof?.decisionId !== decisionId ||
    proof.auditEventKey !== rawApprovalIdentity(label).auditEventKey ||
    proof.action !== "TEMPLATE_TWIN_STATIC_ASSET_APPROVED" ||
    proof.status !== "PENDING"
  ) {
    throw new Error(
      "A self-consistent direct database decision did not retain its durable audit identity.",
    );
  }
  binding = {
    ...binding,
    decisionId,
    decisionVersion: binding.decisionVersion + 1,
  };
  return decisionId;
}

async function main(): Promise<void> {
  await createSyntheticFixture();
  const directSqlReceiptRejections = await runReceiptAdversarialProofs();
  const directSqlAuditedDecisionId =
    await proveSelfConsistentDirectSqlApproval();

  const claimHasLocked = latch();
  const releaseClaim = latch();
  const commitOrder: string[] = [];

  const claim = claimant
    .$transaction(
      async (tx) => {
        await lockAndAssertTemplateTwinStaticAssetBindingsCurrent({
          practiceId,
          bindings: [binding],
          db: tx as unknown as TemplateTwinStaticAssetClaimDb,
        });
        claimHasLocked.release();
        await releaseClaim.promise;
      },
      { isolationLevel: "Serializable" },
    )
    .then(() => {
      commitOrder.push("claim");
    });

  await claimHasLocked.promise;
  const revocation = revokeTemplateTwinStaticAsset({
    practiceId,
    sha256: digest,
    actor: {
      userId: adminId,
      userEmail: adminEmail,
      practiceId,
      role: "ADMIN",
      rolloutToken: {
        practiceId,
        globalGeneration: globalRolloutGeneration,
        practiceGeneration: practiceRolloutGeneration,
      },
    },
    reason: "Synthetic concurrent revocation proof.",
    db: revoker as unknown as TemplateTwinStaticAssetDb,
  }).then(() => {
    commitOrder.push("revocation");
  });

  const blocked = await waitUntilRevocationBlocked();
  releaseClaim.release();
  await Promise.all([claim, revocation]);

  if (commitOrder.join(",") !== "claim,revocation") {
    throw new Error(
      `Unexpected static-asset linearization order: ${commitOrder.join(",")}`,
    );
  }

  let staleClaimCode: string | null = null;
  try {
    await claimant.$transaction(
      (tx) =>
        lockAndAssertTemplateTwinStaticAssetBindingsCurrent({
          practiceId,
          bindings: [binding],
          db: tx as unknown as TemplateTwinStaticAssetClaimDb,
        }),
      { isolationLevel: "Serializable" },
    );
  } catch (error) {
    staleClaimCode =
      typeof error === "object" && error !== null && "code" in error
        ? String((error as { code: unknown }).code)
        : null;
  }
  if (staleClaimCode !== "TT_STATIC_ASSET_NOT_APPROVED") {
    throw new Error(
      `A post-revocation claim did not fail closed (code=${staleClaimCode ?? "none"}).`,
    );
  }

  const [asset, approvalAuditCount, revocationAuditCount] = await Promise.all([
    observer.templateTwinStaticAsset.findUniqueOrThrow({
      where: { id: assetId },
      select: { currentStatus: true, currentDecisionVersion: true },
    }),
    observer.templateTwinAuditOutbox.count({
      where: {
        action: "TEMPLATE_TWIN_STATIC_ASSET_APPROVED",
        targetId: assetId,
        status: "PENDING",
      },
    }),
    observer.templateTwinAuditOutbox.count({
      where: {
        action: "TEMPLATE_TWIN_STATIC_ASSET_REVOKED",
        targetId: assetId,
        status: "PENDING",
      },
    }),
  ]);
  if (
    asset.currentStatus !== "REVOKED" ||
    asset.currentDecisionVersion !== 4 ||
    approvalAuditCount !== 3 ||
    revocationAuditCount !== 1
  ) {
    throw new Error("Revocation state and durable audit evidence diverged.");
  }

  process.stdout.write(
    `${JSON.stringify({
      profile: "template-twin-static-asset-receipt-and-revocation-postgres-v2",
      synthetic: true,
      databaseGuard: "passed",
      productionHelpersExercised: [
        "lockAndAssertTemplateTwinStaticAssetBindingsCurrent",
        "inspectTemplateTwinStaticAssetForReview",
        "approveTemplateTwinStaticAsset",
        "revokeTemplateTwinStaticAsset",
      ],
      productionLikeReceiptFlow: true,
      directSqlReceiptRejections,
      durableApprovalAudit: approvalAuditCount === 3,
      repeatApprovalDecisionRecorded: true,
      directSqlDecisionAuditBound: directSqlAuditedDecisionId.length > 0,
      previewAuthenticityBoundary:
        "application bearer-secret verification plus least-privilege database writers; a privileged direct database writer can synthesize self-consistent receipt evidence but cannot create an unaudited decision",
      databaseObservedBlocking: true,
      blockedWaitEvent: blocked.waitEvent,
      linearizationOrder: commitOrder,
      postRevocationClaimCode: staleClaimCode,
      finalStatus: asset.currentStatus,
      decisionVersion: asset.currentDecisionVersion,
      durableRevocationAudit: revocationAuditCount === 1,
      fixtureLifecycle:
        "retained only in the disposable database because asset evidence is immutable",
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
      claimant.$disconnect(),
      revoker.$disconnect(),
      observer.$disconnect(),
    ]);
  });
