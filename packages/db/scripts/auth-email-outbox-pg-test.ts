#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the durable auth-email outbox authority boundary.
// Synthetic identifiers only; the target must be a disposable, migrated DB.
// No provider client is imported or called: delivery outcomes are fixed fixtures.

import assert from "node:assert/strict";
import { createHash } from "node:crypto";

import { Client, type QueryResultRow } from "pg";

import { assertNonProdDatabase } from "../src/db-guard";

const databaseUrl = process.env.AUTH_EMAIL_OUTBOX_TEST_DATABASE_URL;
if (!databaseUrl) {
  throw new Error(
    "AUTH_EMAIL_OUTBOX_TEST_DATABASE_URL is required; ambient DATABASE_URL is never accepted.",
  );
}
const guardedTarget = assertNonProdDatabase(databaseUrl);

const runtimeRole = "quillmd_runtime" as const;
const dispatcherRole = "quillmd_auth_email_dispatcher" as const;
type TestRole = typeof runtimeRole | typeof dispatcherRole;

const practiceId = "synthetic-auth-email-outbox-practice";
const practiceSlug = "synthetic-auth-email-outbox-practice";
const passwordHash = "synthetic-password-hash-not-a-credential";
const sessionToken = "synthetic-auth-email-current-session-token";
const noopSessionToken = "synthetic-auth-email-noop-session-token";

const fixtures = {
  privacy: {
    id: "synthetic-auth-email-privacy-user",
    email: "auth-email-privacy@synthetic.invalid",
  },
  reset: {
    id: "synthetic-auth-email-reset-user",
    email: "auth-email-reset@synthetic.invalid",
  },
  verification: {
    id: "synthetic-auth-email-verification-user",
    email: "auth-email-verification@synthetic.invalid",
  },
  change: {
    id: "synthetic-auth-email-change-user",
    email: "auth-email-change-old@synthetic.invalid",
  },
  accountExists: {
    id: "synthetic-auth-email-account-exists-user",
    email: "auth-email-account-exists@synthetic.invalid",
  },
  staleWorker: {
    id: "synthetic-auth-email-stale-worker-user",
    email: "auth-email-stale-worker@synthetic.invalid",
  },
  noop: {
    id: "synthetic-auth-email-noop-user",
    email: "auth-email-noop-old@synthetic.invalid",
  },
  noopConflict: {
    id: "synthetic-auth-email-noop-conflict-user",
    email: "auth-email-noop-new@synthetic.invalid",
  },
  crashedLease: {
    id: "synthetic-auth-email-crashed-lease-user",
    email: "auth-email-crashed-lease@synthetic.invalid",
  },
  supersededClaim: {
    id: "synthetic-auth-email-superseded-claim-user",
    email: "auth-email-superseded-claim@synthetic.invalid",
  },
  recipientBudget: {
    id: "synthetic-auth-email-recipient-budget-user",
    email: "auth-email-recipient-budget@synthetic.invalid",
  },
  triggerPassword: {
    id: "synthetic-auth-email-trigger-password-user",
    email: "auth-email-trigger-password@synthetic.invalid",
  },
  triggerEmail: {
    id: "synthetic-auth-email-trigger-email-user",
    email: "auth-email-trigger-email@synthetic.invalid",
  },
  triggerLifecycle: {
    id: "synthetic-auth-email-trigger-lifecycle-user",
    email: "auth-email-trigger-lifecycle@synthetic.invalid",
  },
  purge: {
    id: "synthetic-auth-email-purge-user",
    email: "auth-email-purge@synthetic.invalid",
  },
  authoritySessionDelete: {
    id: "synthetic-auth-email-authority-session-delete-user",
    email: "auth-email-authority-session-delete@synthetic.invalid",
  },
  authoritySessionUpdate: {
    id: "synthetic-auth-email-authority-session-update-user",
    email: "auth-email-authority-session-update@synthetic.invalid",
  },
  authorityForceLogout: {
    id: "synthetic-auth-email-authority-force-logout-user",
    email: "auth-email-authority-force-logout@synthetic.invalid",
  },
  authorityMutations: {
    id: "synthetic-auth-email-authority-mutations-user",
    email: "auth-email-authority-mutations@synthetic.invalid",
  },
  authorityPractice: {
    id: "synthetic-auth-email-authority-practice-user",
    email: "auth-email-authority-practice@synthetic.invalid",
  },
  redeemReset: {
    id: "synthetic-auth-email-redeem-reset-user",
    email: "auth-email-redeem-reset@synthetic.invalid",
  },
  redeemVerification: {
    id: "synthetic-auth-email-redeem-verification-user",
    email: "auth-email-redeem-verification@synthetic.invalid",
  },
  redeemChange: {
    id: "synthetic-auth-email-redeem-change-user",
    email: "auth-email-redeem-change-old@synthetic.invalid",
  },
  redeemChangeConflict: {
    id: "synthetic-auth-email-redeem-change-conflict-user",
    email: "auth-email-redeem-change-conflict-old@synthetic.invalid",
  },
  redeemChangeConflictOwner: {
    id: "synthetic-auth-email-redeem-change-conflict-owner",
    email: "auth-email-redeem-change-conflict-owner@synthetic.invalid",
  },
  raceExpiredFinishFirst: {
    id: "synthetic-auth-email-race-expired-finish-first-user",
    email: "auth-email-race-expired-finish-first@synthetic.invalid",
  },
  raceExpiredClaimFirst: {
    id: "synthetic-auth-email-race-expired-claim-first-user",
    email: "auth-email-race-expired-claim-first@synthetic.invalid",
  },
  raceSessionFinishFirst: {
    id: "synthetic-auth-email-race-session-finish-first-user",
    email: "auth-email-race-session-finish-first@synthetic.invalid",
  },
  raceSessionDeleteFirst: {
    id: "synthetic-auth-email-race-session-delete-first-user",
    email: "auth-email-race-session-delete-first@synthetic.invalid",
  },
} as const;

const unknownEmail = "auth-email-unknown@synthetic.invalid";
const changeCapabilityEmailOne =
  "auth-email-change-capability-one@synthetic.invalid";
const changeCapabilityEmailTwo =
  "auth-email-change-capability-two@synthetic.invalid";
const changePurposeEmail = "auth-email-change-purpose@synthetic.invalid";
const triggerEmailReplacement =
  "auth-email-trigger-email-replaced@synthetic.invalid";
const authorityTargets = {
  sessionDelete: "auth-email-session-delete-new@synthetic.invalid",
  sessionUpdate: "auth-email-session-update-new@synthetic.invalid",
  forceLogout: "auth-email-force-logout-new@synthetic.invalid",
  role: "auth-email-role-change-new@synthetic.invalid",
  product: "auth-email-product-change-new@synthetic.invalid",
  mfaEnabled: "auth-email-mfa-enabled-new@synthetic.invalid",
  mfaSecret: "auth-email-mfa-secret-new@synthetic.invalid",
  mfaVerifiedAt: "auth-email-mfa-verified-new@synthetic.invalid",
  mfaBackupCodes: "auth-email-mfa-backup-new@synthetic.invalid",
  practice: "auth-email-practice-inactive-new@synthetic.invalid",
  redeemChange: "auth-email-redeem-change-new@synthetic.invalid",
  redeemChangeConflict:
    "auth-email-redeem-change-conflict-new@synthetic.invalid",
  raceSessionFinishFirst:
    "auth-email-race-session-finish-first-new@synthetic.invalid",
  raceSessionDeleteFirst:
    "auth-email-race-session-delete-first-new@synthetic.invalid",
} as const;
const concurrentEmails = Array.from(
  { length: 24 },
  (_, index) =>
    `auth-email-concurrent-${index.toString().padStart(2, "0")}@synthetic.invalid`,
);
const concurrentSameEmail =
  "auth-email-concurrent-same-address@synthetic.invalid";

const userFixtures = Object.values(fixtures);
const initiallySeededUserFixtures = userFixtures.filter(
  (fixture) => fixture.id !== fixtures.noopConflict.id,
);
const fixtureUserIds = userFixtures.map((fixture) => fixture.id);
const allFixtureEmails = [
  ...userFixtures.map((fixture) => fixture.email),
  unknownEmail,
  changeCapabilityEmailOne,
  changeCapabilityEmailTwo,
  changePurposeEmail,
  triggerEmailReplacement,
  ...Object.values(authorityTargets),
  ...concurrentEmails,
  concurrentSameEmail,
];

function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

const fixtureEmailHashes = [...new Set(allFixtureEmails.map(sha256))];
const rawTokenFixtures: string[] = [];

interface ClaimRow extends QueryResultRow {
  id: string;
  claimToken: string;
}

interface PreparedRow extends QueryResultRow {
  userId: string;
  email: string;
  name: string | null;
  tokenId: string | null;
  purpose:
    | "PASSWORD_RESET"
    | "EMAIL_VERIFICATION"
    | "EMAIL_CHANGE"
    | "ACCOUNT_EXISTS";
}

interface OutboxState extends QueryResultRow {
  id: string;
  candidateUserId: string | null;
  emailSha256: string;
  sourceEmailSha256: string | null;
  recipientEmail: string | null;
  authorityPracticeId: string | null;
  authoritySessionSha256: string | null;
  authoritySessionCreatedAt: Date | null;
  authoritySessionExpiresAt: Date | null;
  purpose: string;
  status: string;
  attemptCount: number;
  claimToken: string | null;
  tokenId: string | null;
  providerReceiptSha256: string | null;
  lastErrorCode: string | null;
}

interface TokenState extends QueryResultRow {
  id: string;
  userId: string;
  purpose: string;
  tokenHash: string;
  expiresAt: Date;
  usedAt: Date | null;
  metadata: Record<string, unknown> | null;
}

const admin = new Client({ connectionString: databaseUrl });

function fixtureSessionToken(userId: string): string {
  if (userId === fixtures.change.id) return sessionToken;
  if (userId === fixtures.noop.id) return noopSessionToken;
  return `synthetic-auth-email-session-${userId}`;
}

async function roleQuery<Row extends QueryResultRow = QueryResultRow>(
  role: TestRole,
  text: string,
  values: readonly unknown[] = [],
): Promise<Row[]> {
  const client = new Client({ connectionString: databaseUrl });
  try {
    await client.connect();
    await client.query("BEGIN");
    await client.query(`SET LOCAL ROLE "${role}"`);
    const result = await client.query<Row>(text, [...values]);
    await client.query("COMMIT");
    return result.rows;
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  } finally {
    await client.end();
  }
}

async function openBoundedTransaction(
  applicationName: string,
  role?: TestRole,
): Promise<Client> {
  const client = new Client({ connectionString: databaseUrl });
  await client.connect();
  await client.query("BEGIN");
  await client.query(
    `SELECT set_config('application_name', $1, TRUE),
            set_config('lock_timeout', '3s', TRUE),
            set_config('statement_timeout', '8s', TRUE)`,
    [applicationName],
  );
  if (role) await client.query(`SET LOCAL ROLE "${role}"`);
  return client;
}

async function boundedTransaction<T>(
  applicationName: string,
  operation: (client: Client) => Promise<T>,
): Promise<T> {
  const client = await openBoundedTransaction(applicationName);
  try {
    const result = await operation(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  } finally {
    await client.end();
  }
}

interface SettledDatabaseOperation {
  ok: boolean;
  error?: Error & { code?: string };
}

async function settleDatabaseOperation(
  client: Client,
  operation: Promise<unknown>,
): Promise<SettledDatabaseOperation> {
  try {
    await operation;
    await client.query("COMMIT");
    return { ok: true };
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    return {
      ok: false,
      error:
        error instanceof Error
          ? (error as Error & { code?: string })
          : new Error("unknown database race failure"),
    };
  } finally {
    await client.end();
  }
}

async function waitForLockWaiters(
  applicationNames: readonly string[],
  expected: number,
): Promise<void> {
  const deadline = Date.now() + 2_000;
  while (Date.now() < deadline) {
    const result = await admin.query<{ count: number }>(
      `SELECT count(*)::int AS count
         FROM pg_catalog.pg_stat_activity
        WHERE application_name = ANY($1::text[])
          AND wait_event_type = 'Lock'`,
      [[...applicationNames]],
    );
    if ((result.rows[0]?.count ?? 0) >= expected) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error(
    `bounded race barrier did not observe ${expected} lock waiters`,
  );
}

function assertNoConcurrencyTimeoutOrDeadlock(
  result: SettledDatabaseOperation,
): void {
  if (result.ok) return;
  assert.notEqual(result.error?.code, "40P01", "race must not deadlock");
  assert.notEqual(
    result.error?.code,
    "55P03",
    "race must not hit lock timeout",
  );
  assert.notEqual(
    result.error?.code,
    "57014",
    "race must not hit statement timeout",
  );
}

async function expectRoleError(
  role: TestRole,
  text: string,
  values: readonly unknown[],
  expectedMessage: RegExp,
): Promise<void> {
  let failure: unknown;
  try {
    await roleQuery(role, text, values);
  } catch (error) {
    failure = error;
  }
  assert.ok(failure instanceof Error, "the guarded call must fail closed");
  assert.match(failure.message, expectedMessage);
}

async function expectDirectTableDenied(role: TestRole): Promise<void> {
  let failure: unknown;
  try {
    await roleQuery(role, 'SELECT * FROM public."auth_email_outbox" LIMIT 1');
  } catch (error) {
    failure = error;
  }
  assert.ok(failure instanceof Error, `${role} must not read the outbox table`);
  assert.equal(
    (failure as Error & { code?: string }).code,
    "42501",
    `${role} direct-table access must fail with insufficient privilege`,
  );
}

async function enqueue(
  email: string,
  purpose: "PASSWORD_RESET" | "EMAIL_VERIFICATION" | "ACCOUNT_EXISTS",
): Promise<string> {
  const rows = await roleQuery<{ id: string }>(
    runtimeRole,
    'SELECT public.auth_email_enqueue($1, $2::"AuthEmailPurpose") AS id',
    [email, purpose],
  );
  assert.equal(rows.length, 1);
  assert.match(rows[0]!.id, /^[0-9a-f-]{36}$/u);
  return rows[0]!.id;
}

async function enqueueChange(
  userId: string,
  currentEmail: string,
  newEmail: string,
  expectedPracticeId = practiceId,
  expectedSessionToken = sessionToken,
  expectedPasswordHash = passwordHash,
): Promise<string> {
  const rows = await roleQuery<{ id: string }>(
    runtimeRole,
    `SELECT public.auth_email_enqueue_change(
       $1, $2, $3, $4, $5, $6
     ) AS id`,
    [
      userId,
      currentEmail,
      newEmail,
      expectedPracticeId,
      expectedSessionToken,
      expectedPasswordHash,
    ],
  );
  assert.equal(rows.length, 1);
  return rows[0]!.id;
}

async function claim(limit = 1): Promise<ClaimRow[]> {
  return roleQuery<ClaimRow>(
    dispatcherRole,
    "SELECT * FROM public.auth_email_claim($1)",
    [limit],
  );
}

async function claimExact(expectedId: string): Promise<ClaimRow> {
  const rows = await claim(1);
  assert.equal(rows.length, 1, `request ${expectedId} must be claimable`);
  assert.equal(rows[0]!.id, expectedId);
  assert.match(rows[0]!.claimToken, /^[0-9a-f-]{36}$/u);
  return rows[0]!;
}

function tokenMaterial(label: string): {
  id: string;
  raw: string;
  hash: string;
} {
  const id = `synthetic-auth-email-token-${label}`;
  const raw = `synthetic-auth-email-raw-bearer-${label}-never-delivered`;
  rawTokenFixtures.push(raw);
  return { id, raw, hash: sha256(raw) };
}

async function prepare(
  claimed: ClaimRow,
  material: { id: string; hash: string } | null,
): Promise<PreparedRow[]> {
  return roleQuery<PreparedRow>(
    dispatcherRole,
    `SELECT * FROM public.auth_email_prepare_delivery(
       $1::uuid, $2::uuid, $3, $4
     )`,
    [
      claimed.id,
      claimed.claimToken,
      material?.id ?? null,
      material?.hash ?? null,
    ],
  );
}

async function finish(
  claimed: ClaimRow,
  tokenId: string | null,
  delivered: boolean,
  errorCode: string | null,
  providerReceipt: string | null,
): Promise<void> {
  await roleQuery(
    dispatcherRole,
    `SELECT public.auth_email_finish_delivery(
       $1::uuid, $2::uuid, $3, $4, $5, $6
     )`,
    [
      claimed.id,
      claimed.claimToken,
      tokenId,
      delivered,
      errorCode,
      providerReceipt,
    ],
  );
}

async function outboxState(id: string): Promise<OutboxState> {
  const result = await admin.query<OutboxState>(
    `SELECT "id", "candidateUserId", "emailSha256", "sourceEmailSha256",
            "recipientEmail", "authorityPracticeId",
            "authoritySessionSha256", "authoritySessionCreatedAt",
            "authoritySessionExpiresAt", "purpose", "status",
            "attemptCount", "claimToken", "tokenId",
            "providerReceiptSha256", "lastErrorCode"
       FROM public."auth_email_outbox"
      WHERE "id" = $1::uuid`,
    [id],
  );
  assert.equal(result.rows.length, 1, `outbox row ${id} must exist`);
  return result.rows[0]!;
}

async function tokenState(id: string): Promise<TokenState> {
  const result = await admin.query<TokenState>(
    `SELECT "id", "userId", "purpose", "tokenHash", "expiresAt",
            "usedAt", "metadata"
       FROM public."auth_tokens"
      WHERE "id" = $1`,
    [id],
  );
  assert.equal(result.rows.length, 1, `token ${id} must exist`);
  return result.rows[0]!;
}

async function cleanup(): Promise<void> {
  await admin.query(
    `DELETE FROM public."auth_email_outbox"
      WHERE "candidateUserId" = ANY($1::text[])
         OR "emailSha256" = ANY($2::text[])
         OR "sourceEmailSha256" = ANY($2::text[])`,
    [fixtureUserIds, fixtureEmailHashes],
  );
  await admin.query(
    'DELETE FROM public."auth_tokens" WHERE "userId" = ANY($1::text[])',
    [fixtureUserIds],
  );
  await admin.query(
    'DELETE FROM public."user_sessions" WHERE "userId" = ANY($1::text[])',
    [fixtureUserIds],
  );
  await admin.query('DELETE FROM public."users" WHERE "id" = ANY($1::text[])', [
    fixtureUserIds,
  ]);
  await admin.query('DELETE FROM public."practices" WHERE "id" = $1', [
    practiceId,
  ]);
}

async function assertInstalledContract(): Promise<void> {
  const target = await admin.query<{ database: string }>(
    "SELECT current_database() AS database",
  );
  assert.equal(target.rows[0]?.database.toLowerCase(), guardedTarget.database);

  const installed = await admin.query<{
    outbox: string | null;
    recipientBudgetIndex: string | null;
    enqueue: string | null;
    claim: string | null;
    prepare: string | null;
    finish: string | null;
    purge: string | null;
  }>(`SELECT
      to_regclass('public.auth_email_outbox')::text AS outbox,
      to_regclass('public.auth_email_outbox_recipient_budget_idx')::text AS "recipientBudgetIndex",
      to_regprocedure('public.auth_email_enqueue(text,"AuthEmailPurpose")')::text AS enqueue,
      to_regprocedure('public.auth_email_claim(integer)')::text AS claim,
      to_regprocedure('public.auth_email_prepare_delivery(uuid,uuid,text,text)')::text AS prepare,
      to_regprocedure('public.auth_email_finish_delivery(uuid,uuid,text,boolean,text,text)')::text AS finish,
      to_regprocedure('public.auth_email_purge(integer)')::text AS purge`);
  const row = installed.rows[0];
  assert.ok(row?.outbox, "the v6 outbox table must already be migrated");
  assert.ok(
    row?.recipientBudgetIndex,
    "the recipient hash/purpose/time budget index must be installed",
  );
  for (const key of [
    "enqueue",
    "claim",
    "prepare",
    "finish",
    "purge",
  ] as const) {
    assert.ok(row[key], `the v6 ${key} function must already be migrated`);
  }
}

async function seedFixtures(): Promise<void> {
  await admin.query(
    `INSERT INTO public."practices" (
       "id", "name", "slug", "isActive", "createdAt", "updatedAt"
     ) VALUES ($1, 'Synthetic Auth Email Practice', $2, TRUE,
       clock_timestamp(), clock_timestamp())`,
    [practiceId, practiceSlug],
  );
  for (const fixture of initiallySeededUserFixtures) {
    await admin.query(
      `INSERT INTO public."users" (
         "id", "email", "name", "passwordHash", "role", "products",
         "practiceId", "isActive", "createdAt", "updatedAt"
       ) VALUES (
         $1, $2, 'Synthetic Auth Email Doctor', $3, 'DOCTOR',
         ARRAY['TRANSCRIBE_MD']::"Product"[], $4, TRUE,
         clock_timestamp(), clock_timestamp()
       )`,
      [fixture.id, fixture.email, passwordHash, practiceId],
    );
  }
  for (const fixture of initiallySeededUserFixtures) {
    await admin.query(
      `INSERT INTO public."user_sessions" (
         "id", "userId", "sessionToken", "createdAt", "lastActiveAt",
         "expiresAt"
       ) VALUES (
         $1, $2, $3, clock_timestamp(), clock_timestamp(),
         clock_timestamp() + INTERVAL '1 hour'
       )`,
      [
        `synthetic-auth-email-session-row-${fixture.id}`,
        fixture.id,
        fixtureSessionToken(fixture.id),
      ],
    );
  }
}

async function proveAclBoundary(): Promise<void> {
  const signatures = [
    'public.auth_email_enqueue(text,"AuthEmailPurpose")',
    "public.auth_email_enqueue_change(text,text,text,text,text,text)",
    "public.auth_email_claim(integer)",
    "public.auth_email_prepare_delivery(uuid,uuid,text,text)",
    "public.auth_email_finish_delivery(uuid,uuid,text,boolean,text,text)",
    "public.auth_email_purge(integer)",
    "public.auth_email_health()",
    "public.auth_email_cancel_on_user_security_change()",
    "public.auth_email_cancel_on_session_change()",
    "public.auth_email_cancel_on_practice_change()",
  ];
  const runtimeAllowed = new Set(signatures.slice(0, 2));
  const dispatcherAllowed = new Set(signatures.slice(2, 7));
  for (const signature of signatures) {
    for (const [role, allowed] of [
      [runtimeRole, runtimeAllowed.has(signature)],
      [dispatcherRole, dispatcherAllowed.has(signature)],
    ] as const) {
      const result = await admin.query<{
        oid: string | null;
        allowed: boolean;
      }>(
        `SELECT to_regprocedure($2)::text AS oid,
                has_function_privilege($1, to_regprocedure($2), 'EXECUTE') AS allowed`,
        [role, signature],
      );
      assert.ok(result.rows[0]?.oid, `${signature} must exist`);
      assert.equal(
        result.rows[0]?.allowed,
        allowed,
        `${role} EXECUTE capability must be exact for ${signature}`,
      );
    }
  }

  const publicExecute = await admin.query<{ signature: string }>(
    `SELECT p.oid::regprocedure::text AS signature
       FROM pg_catalog.pg_proc p
       JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
       CROSS JOIN LATERAL pg_catalog.aclexplode(
         COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
       ) acl
      WHERE n.nspname = 'public'
        AND p.proname LIKE 'auth_email_%'
        AND acl.grantee = 0
        AND acl.privilege_type = 'EXECUTE'`,
  );
  assert.deepEqual(
    publicExecute.rows,
    [],
    "PUBLIC must have no auth_email_* execution capability",
  );

  const tablePrivileges = await admin.query<{
    runtime: boolean;
    dispatcher: boolean;
  }>(`SELECT
      has_table_privilege('quillmd_runtime', 'public.auth_email_outbox',
        'SELECT,INSERT,UPDATE,DELETE') AS runtime,
      has_table_privilege('quillmd_auth_email_dispatcher',
        'public.auth_email_outbox', 'SELECT,INSERT,UPDATE,DELETE') AS dispatcher`);
  assert.equal(tablePrivileges.rows[0]?.runtime, false);
  assert.equal(tablePrivileges.rows[0]?.dispatcher, false);
  await expectDirectTableDenied(runtimeRole);
  await expectDirectTableDenied(dispatcherRole);
}

async function proveAnonymousStorage(): Promise<void> {
  const knownId = await enqueue(fixtures.privacy.email, "ACCOUNT_EXISTS");
  const unknownId = await enqueue(unknownEmail, "ACCOUNT_EXISTS");
  const known = await outboxState(knownId);
  const unknown = await outboxState(unknownId);
  assert.equal(known.candidateUserId, null);
  assert.equal(unknown.candidateUserId, null);
  assert.equal(known.emailSha256.trim(), sha256(fixtures.privacy.email));
  assert.equal(unknown.emailSha256.trim(), sha256(unknownEmail));
  assert.equal(known.recipientEmail, null);
  assert.equal(unknown.recipientEmail, null);

  const serialized = await admin.query<{ body: string }>(
    `SELECT row_to_json(outbox)::text AS body
       FROM public."auth_email_outbox" outbox
      WHERE "id" = ANY($1::uuid[])
      ORDER BY "id"`,
    [[knownId, unknownId]],
  );
  for (const row of serialized.rows) {
    assert.ok(!row.body.includes(fixtures.privacy.email));
    assert.ok(!row.body.includes(unknownEmail));
  }

  const knownClaim = await claimExact(knownId);
  const knownPrepared = await prepare(knownClaim, null);
  assert.equal(knownPrepared[0]?.userId, fixtures.privacy.id);
  assert.equal(
    (await outboxState(knownId)).candidateUserId,
    fixtures.privacy.id,
  );
  await finish(
    knownClaim,
    null,
    true,
    null,
    sha256("synthetic-anonymous-known-provider-receipt"),
  );

  const unknownClaim = await claimExact(unknownId);
  assert.deepEqual(await prepare(unknownClaim, null), []);
  const unknownPrepared = await outboxState(unknownId);
  assert.equal(unknownPrepared.status, "NOOP");
  assert.equal(unknownPrepared.candidateUserId, null);

  await admin.query(
    'DELETE FROM public."auth_email_outbox" WHERE "id" = ANY($1::uuid[])',
    [[knownId, unknownId]],
  );
}

async function proveAnonymousIngressLockIndependence(): Promise<void> {
  const blocker = await openBoundedTransaction(
    "auth-email-ingress-held-user-lock",
  );
  await blocker.query(
    'SELECT "id" FROM public."users" WHERE "id" = $1 FOR UPDATE',
    [fixtures.privacy.id],
  );

  const timedEnqueue = async (email: string, applicationName: string) => {
    const client = await openBoundedTransaction(applicationName, runtimeRole);
    await client.query(
      `SELECT set_config('lock_timeout', '250ms', TRUE),
              set_config('statement_timeout', '750ms', TRUE)`,
    );
    const startedAt = performance.now();
    try {
      const result = await client.query<{ id: string }>(
        "SELECT public.auth_email_enqueue($1, 'ACCOUNT_EXISTS'::\"AuthEmailPurpose\") AS id",
        [email],
      );
      await client.query("COMMIT");
      return {
        id: result.rows[0]!.id,
        elapsedMs: performance.now() - startedAt,
      };
    } catch (error) {
      await client.query("ROLLBACK").catch(() => undefined);
      throw error;
    } finally {
      await client.end();
    }
  };

  let known: { id: string; elapsedMs: number } | null = null;
  let unknown: { id: string; elapsedMs: number } | null = null;
  try {
    known = await timedEnqueue(
      fixtures.privacy.email,
      "auth-email-ingress-known",
    );
    unknown = await timedEnqueue(unknownEmail, "auth-email-ingress-unknown");
    assert.ok(
      known.elapsedMs < 750,
      "known-address ingress must not wait on the held user lock",
    );
    assert.ok(
      unknown.elapsedMs < 750,
      "unknown-address ingress must stay within the same bounded path",
    );
    assert.ok(
      Math.abs(known.elapsedMs - unknown.elapsedMs) < 500,
      "known and unknown hash-only ingress timings must remain bounded",
    );
  } finally {
    await blocker.query("ROLLBACK").catch(() => undefined);
    await blocker.end();
    const ids = [known?.id, unknown?.id].filter(
      (value): value is string => typeof value === "string",
    );
    if (ids.length > 0) {
      await admin.query(
        'DELETE FROM public."auth_email_outbox" WHERE "id" = ANY($1::uuid[])',
        [ids],
      );
    }
  }
}

async function proveEmailChangeCapability(): Promise<void> {
  const before = await admin.query<{ count: string }>(
    `SELECT count(*)::text AS count FROM public."auth_email_outbox"
      WHERE "candidateUserId" = $1 AND "purpose" = 'EMAIL_CHANGE'`,
    [fixtures.change.id],
  );
  assert.equal(before.rows[0]?.count, "0");

  const callSql = `SELECT public.auth_email_enqueue_change(
    $1, $2, $3, $4, $5, $6
  )`;
  const base = [
    fixtures.change.id,
    fixtures.change.email,
    changeCapabilityEmailOne,
    practiceId,
    sessionToken,
    passwordHash,
  ] as const;
  await expectRoleError(
    runtimeRole,
    callSql,
    [...base.slice(0, 4), "synthetic-stale-session", base[5]],
    /Auth email change authority changed/u,
  );
  await expectRoleError(
    runtimeRole,
    callSql,
    [...base.slice(0, 3), "synthetic-wrong-practice", ...base.slice(4)],
    /Auth email change authority changed/u,
  );
  await expectRoleError(
    runtimeRole,
    callSql,
    [...base.slice(0, 5), "synthetic-wrong-password-hash"],
    /Auth email change authority changed/u,
  );
  await admin.query(
    'UPDATE public."users" SET "suspendedAt" = clock_timestamp() WHERE "id" = $1',
    [fixtures.change.id],
  );
  await expectRoleError(
    runtimeRole,
    callSql,
    base,
    /Auth email change authority changed/u,
  );
  await admin.query(
    'UPDATE public."users" SET "suspendedAt" = NULL WHERE "id" = $1',
    [fixtures.change.id],
  );
  const afterRejected = await admin.query<{ count: string }>(
    `SELECT count(*)::text AS count FROM public."auth_email_outbox"
      WHERE "candidateUserId" = $1 AND "purpose" = 'EMAIL_CHANGE'`,
    [fixtures.change.id],
  );
  assert.equal(afterRejected.rows[0]?.count, "0");

  const firstId = await enqueueChange(
    fixtures.change.id,
    fixtures.change.email,
    changeCapabilityEmailOne,
  );
  const secondId = await enqueueChange(
    fixtures.change.id,
    fixtures.change.email,
    changeCapabilityEmailTwo,
  );
  const first = await outboxState(firstId);
  const second = await outboxState(secondId);
  assert.equal(first.status, "FAILED");
  assert.equal(first.lastErrorCode, "SUPERSEDED");
  assert.equal(first.recipientEmail, null);
  assert.equal(second.status, "PENDING");
  assert.equal(second.recipientEmail, changeCapabilityEmailTwo);
  assert.equal(second.sourceEmailSha256?.trim(), sha256(fixtures.change.email));
  assert.equal(second.emailSha256.trim(), sha256(changeCapabilityEmailTwo));
  await admin.query(
    'DELETE FROM public."auth_email_outbox" WHERE "id" = ANY($1::uuid[])',
    [[firstId, secondId]],
  );
}

async function provePurposePreparation(): Promise<{
  successOutboxId: string;
  successTokenId: string;
}> {
  const resetId = await enqueue(fixtures.reset.email, "PASSWORD_RESET");
  const resetClaim = await claimExact(resetId);
  const resetToken = tokenMaterial("purpose-reset-0001");
  const resetPrepared = await prepare(resetClaim, resetToken);
  assert.deepEqual(
    resetPrepared.map((row) => row.purpose),
    ["PASSWORD_RESET"],
  );
  assert.equal(resetPrepared[0]?.email, fixtures.reset.email);
  assert.equal(resetPrepared[0]?.tokenId, resetToken.id);
  const resetStored = await tokenState(resetToken.id);
  assert.equal(resetStored.purpose, "PASSWORD_RESET");
  assert.equal(resetStored.tokenHash, resetToken.hash);
  assert.deepEqual(resetStored.metadata, { email: fixtures.reset.email });
  const successReceipt = sha256("synthetic-provider-success-receipt-fixed");
  await finish(resetClaim, resetToken.id, true, null, successReceipt);
  const resetFinished = await outboxState(resetId);
  assert.equal(resetFinished.status, "DELIVERED");
  assert.equal(resetFinished.providerReceiptSha256?.trim(), successReceipt);

  const verificationId = await enqueue(
    fixtures.verification.email,
    "EMAIL_VERIFICATION",
  );
  const verificationClaim = await claimExact(verificationId);
  const verificationToken = tokenMaterial("purpose-verification-0001");
  const verificationPrepared = await prepare(
    verificationClaim,
    verificationToken,
  );
  assert.equal(verificationPrepared[0]?.purpose, "EMAIL_VERIFICATION");
  assert.equal(verificationPrepared[0]?.email, fixtures.verification.email);
  assert.deepEqual((await tokenState(verificationToken.id)).metadata, {
    email: fixtures.verification.email,
  });
  await finish(
    verificationClaim,
    verificationToken.id,
    false,
    "AUTH_EMAIL_PROVIDER_AMBIGUOUS",
    null,
  );
  const ambiguous = await outboxState(verificationId);
  assert.equal(ambiguous.status, "AMBIGUOUS");
  assert.equal(ambiguous.lastErrorCode, "AUTH_EMAIL_PROVIDER_AMBIGUOUS");
  assert.ok((await tokenState(verificationToken.id)).usedAt);
  assert.ok(!(await claim(100)).some((row) => row.id === verificationId));

  const changeId = await enqueueChange(
    fixtures.change.id,
    fixtures.change.email,
    changePurposeEmail,
  );
  const changeClaim = await claimExact(changeId);
  const changeToken = tokenMaterial("purpose-change-0001");
  const changePrepared = await prepare(changeClaim, changeToken);
  assert.equal(changePrepared[0]?.purpose, "EMAIL_CHANGE");
  assert.equal(changePrepared[0]?.email, changePurposeEmail);
  const changeStored = await tokenState(changeToken.id);
  const changeOutbox = await outboxState(changeId);
  assert.deepEqual(changeStored.metadata, {
    newEmail: changePurposeEmail,
    oldEmail: fixtures.change.email,
  });
  assert.ok(changeOutbox.authoritySessionExpiresAt);
  assert.equal(
    changeStored.expiresAt.getTime(),
    changeOutbox.authoritySessionExpiresAt.getTime(),
    "EMAIL_CHANGE bearer expiry must be bounded by its exact session",
  );
  await finish(
    changeClaim,
    changeToken.id,
    true,
    null,
    sha256("synthetic-provider-change-receipt-fixed"),
  );
  assert.equal((await outboxState(changeId)).recipientEmail, null);

  const accountExistsId = await enqueue(
    fixtures.accountExists.email,
    "ACCOUNT_EXISTS",
  );
  const accountExistsClaim = await claimExact(accountExistsId);
  const accountExistsPrepared = await prepare(accountExistsClaim, null);
  assert.equal(accountExistsPrepared[0]?.purpose, "ACCOUNT_EXISTS");
  assert.equal(accountExistsPrepared[0]?.email, fixtures.accountExists.email);
  assert.equal(accountExistsPrepared[0]?.tokenId, null);
  await finish(
    accountExistsClaim,
    null,
    true,
    null,
    sha256("synthetic-provider-account-exists-receipt-fixed"),
  );
  assert.equal((await outboxState(accountExistsId)).tokenId, null);

  return { successOutboxId: resetId, successTokenId: resetToken.id };
}

async function proveRecipientCooldownAndClaimCoalescing(): Promise<void> {
  const originalId = await enqueue(
    fixtures.supersededClaim.email,
    "PASSWORD_RESET",
  );
  const originalClaim = await claimExact(originalId);
  const originalToken = tokenMaterial("superseded-claim-original-0001");
  const originalPrepared = await prepare(originalClaim, originalToken);
  assert.equal(originalPrepared[0]?.tokenId, originalToken.id);

  const [coalescedClaimedId] = await Promise.all([
    enqueue(fixtures.supersededClaim.email, "PASSWORD_RESET"),
    finish(
      originalClaim,
      originalToken.id,
      true,
      null,
      sha256("synthetic-superseded-claim-provider-receipt"),
    ),
  ]);

  assert.equal(
    coalescedClaimedId,
    originalId,
    "a distributed-source request must coalesce while provider work is claimed",
  );
  assert.equal((await outboxState(originalId)).status, "DELIVERED");
  assert.equal(
    (await tokenState(originalToken.id)).usedAt,
    null,
    "coalescing must not invalidate the delivered bearer",
  );

  const coalescedDeliveredId = await enqueue(
    fixtures.supersededClaim.email,
    "PASSWORD_RESET",
  );
  assert.equal(
    coalescedDeliveredId,
    originalId,
    "the recipient cooldown must include a previously delivered request",
  );
  assert.equal((await tokenState(originalToken.id)).usedAt, null);

  await admin.query(
    `UPDATE public."auth_email_outbox"
        SET "createdAt" = clock_timestamp() - INTERVAL '61 seconds'
      WHERE "id" = $1::uuid`,
    [originalId],
  );
  const replacementId = await enqueue(
    fixtures.supersededClaim.email,
    "PASSWORD_RESET",
  );
  assert.notEqual(replacementId, originalId);
  const replacementClaim = await claimExact(replacementId);
  const replacementToken = tokenMaterial("superseded-claim-next-0001");
  await prepare(replacementClaim, replacementToken);
  assert.ok(
    (await tokenState(originalToken.id)).usedAt,
    "replacement prepare must retire the earlier delivered bearer",
  );
  await finish(
    replacementClaim,
    replacementToken.id,
    false,
    "AUTH_EMAIL_PROVIDER_AMBIGUOUS",
    null,
  );
  assert.equal((await outboxState(replacementId)).status, "AMBIGUOUS");
  assert.ok((await tokenState(replacementToken.id)).usedAt);
}

async function proveDurableRecipientBudget(): Promise<void> {
  const ids: string[] = [];
  const materials: Array<ReturnType<typeof tokenMaterial>> = [];
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const id = await enqueue(fixtures.recipientBudget.email, "PASSWORD_RESET");
    assert.ok(!ids.includes(id), "each allowed post-cooldown request is new");
    ids.push(id);
    const claimed = await claimExact(id);
    const material = tokenMaterial(
      `recipient-budget-${attempt.toString().padStart(2, "0")}`,
    );
    materials.push(material);
    assert.equal((await prepare(claimed, material)).length, 1);
    await finish(
      claimed,
      material.id,
      true,
      null,
      sha256(`synthetic-recipient-budget-receipt-${attempt}`),
    );
    await admin.query(
      `UPDATE public."auth_email_outbox"
          SET "createdAt" = clock_timestamp() - INTERVAL '61 seconds'
        WHERE "id" = $1::uuid`,
      [id],
    );
  }

  // Keep the synthetic age manipulation deterministic: every row remains
  // inside the hourly window while the last-issued bearer is also the most
  // recent request according to the production ordering key.
  for (const [attempt, id] of ids.entries()) {
    await admin.query(
      `UPDATE public."auth_email_outbox"
          SET "createdAt" = clock_timestamp()
            - INTERVAL '70 seconds'
            + ($2::integer * INTERVAL '1 second')
        WHERE "id" = $1::uuid`,
      [id, attempt],
    );
  }

  const finalMaterial = materials.at(-1)!;
  assert.equal((await tokenState(finalMaterial.id)).usedAt, null);
  const budgetedId = await enqueue(
    fixtures.recipientBudget.email,
    "PASSWORD_RESET",
  );
  assert.equal(
    budgetedId,
    ids.at(-1),
    "the sixth independent ingress request inside one hour must coalesce",
  );
  assert.equal(
    (await tokenState(finalMaterial.id)).usedAt,
    null,
    "budget coalescing must preserve the latest delivered bearer",
  );
  const stored = await admin.query<{ count: string }>(
    `SELECT count(*)::text AS count
       FROM public."auth_email_outbox"
      WHERE "emailSha256" = $1
        AND "purpose" = 'PASSWORD_RESET'`,
    [sha256(fixtures.recipientBudget.email)],
  );
  assert.equal(stored.rows[0]?.count, "5");
}

async function proveSameAddressEnqueueLinearization(): Promise<void> {
  const blocker = await openBoundedTransaction(
    "auth-email-same-address-barrier",
  );
  await blocker.query(
    `SELECT pg_advisory_xact_lock(
       hashtextextended($1 || ':' || 'ACCOUNT_EXISTS', 0)
     )`,
    [sha256(concurrentSameEmail)],
  );

  const clients = await Promise.all([
    openBoundedTransaction("auth-email-same-address-one", runtimeRole),
    openBoundedTransaction("auth-email-same-address-two", runtimeRole),
  ]);
  const run = async (client: Client): Promise<string> => {
    try {
      const result = await client.query<{ id: string }>(
        "SELECT public.auth_email_enqueue($1, 'ACCOUNT_EXISTS'::\"AuthEmailPurpose\") AS id",
        [concurrentSameEmail],
      );
      await client.query("COMMIT");
      return result.rows[0]!.id;
    } catch (error) {
      await client.query("ROLLBACK").catch(() => undefined);
      throw error;
    } finally {
      await client.end();
    }
  };
  const operations = clients.map((client) => run(client));
  try {
    await waitForLockWaiters(
      ["auth-email-same-address-one", "auth-email-same-address-two"],
      2,
    );
  } finally {
    await blocker.query("ROLLBACK").catch(() => undefined);
    await blocker.end();
  }
  const ids = await Promise.all(operations);
  assert.equal(
    new Set(ids).size,
    1,
    "identical concurrent ingress must return one durable request",
  );
  assert.equal((await outboxState(ids[0]!)).status, "PENDING");
  const stored = await admin.query<{ count: string }>(
    `SELECT count(*)::text AS count
       FROM public."auth_email_outbox"
      WHERE "emailSha256" = $1
        AND "purpose" = 'ACCOUNT_EXISTS'`,
    [sha256(concurrentSameEmail)],
  );
  assert.equal(stored.rows[0]?.count, "1");
  await admin.query(
    'DELETE FROM public."auth_email_outbox" WHERE "id" = ANY($1::uuid[])',
    [[...new Set(ids)]],
  );
}

async function proveClaimNonce(): Promise<void> {
  const id = await enqueue(fixtures.staleWorker.email, "PASSWORD_RESET");
  const current = await claimExact(id);
  const material = tokenMaterial("stale-worker-0001");
  const staleNonce = "00000000-0000-4000-8000-000000000001";
  await expectRoleError(
    dispatcherRole,
    `SELECT * FROM public.auth_email_prepare_delivery(
       $1::uuid, $2::uuid, $3, $4
     )`,
    [id, staleNonce, material.id, material.hash],
    /Auth email claim is not current/u,
  );
  const prepared = await prepare(current, material);
  assert.equal(prepared[0]?.tokenId, material.id);
  await expectRoleError(
    dispatcherRole,
    `SELECT public.auth_email_finish_delivery(
       $1::uuid, $2::uuid, $3, TRUE, NULL, $4
     )`,
    [id, staleNonce, material.id, sha256("synthetic-stale-receipt")],
    /Auth email completion is not current/u,
  );
  await finish(
    current,
    material.id,
    true,
    null,
    sha256("synthetic-current-worker-receipt"),
  );
}

async function proveRequestExpiry(): Promise<void> {
  const id = await enqueue(fixtures.privacy.email, "PASSWORD_RESET");
  await admin.query(
    `UPDATE public."auth_email_outbox"
        SET "createdAt" = clock_timestamp() - INTERVAL '2 hours',
            "requestExpiresAt" = clock_timestamp() - INTERVAL '1 hour',
            "updatedAt" = clock_timestamp()
      WHERE "id" = $1::uuid`,
    [id],
  );
  assert.ok(!(await claim(100)).some((row) => row.id === id));
  const expired = await outboxState(id);
  assert.equal(expired.status, "FAILED");
  assert.equal(expired.lastErrorCode, "REQUEST_EXPIRED");
}

async function proveIneligibleNoopRetiresToken(): Promise<void> {
  const id = await enqueueChange(
    fixtures.noop.id,
    fixtures.noop.email,
    fixtures.noopConflict.email,
    practiceId,
    noopSessionToken,
  );
  const firstMaterial = tokenMaterial("noop-original-0001");
  // Model a recovered request that already references a current bearer but
  // has not run the one-shot prepare operation in this lease generation.
  await admin.query(
    `INSERT INTO public."auth_tokens" (
       "id", "userId", "purpose", "tokenHash", "expiresAt", "metadata"
     ) VALUES (
       $1, $2, 'EMAIL_CHANGE', $3, clock_timestamp() + INTERVAL '1 hour',
       jsonb_build_object('oldEmail', $4::text, 'newEmail', $5::text)
     )`,
    [
      firstMaterial.id,
      fixtures.noop.id,
      firstMaterial.hash,
      fixtures.noop.email,
      fixtures.noopConflict.email,
    ],
  );
  await admin.query(
    `UPDATE public."auth_email_outbox" SET "tokenId" = $2
      WHERE "id" = $1::uuid`,
    [id, firstMaterial.id],
  );
  assert.equal((await tokenState(firstMaterial.id)).usedAt, null);
  await admin.query(
    `INSERT INTO public."users" (
       "id", "email", "name", "passwordHash", "role", "products",
       "practiceId", "isActive", "createdAt", "updatedAt"
     ) VALUES (
       $1, $2, 'Synthetic Auth Email Conflict Doctor', $3, 'DOCTOR',
       ARRAY['TRANSCRIBE_MD']::"Product"[], $4, TRUE,
       clock_timestamp(), clock_timestamp()
     )`,
    [
      fixtures.noopConflict.id,
      fixtures.noopConflict.email,
      passwordHash,
      practiceId,
    ],
  );
  const secondClaim = await claimExact(id);
  const unusedReplacement = tokenMaterial("noop-replacement-0001");
  const rows = await prepare(secondClaim, unusedReplacement);
  assert.deepEqual(rows, []);
  const noop = await outboxState(id);
  assert.equal(noop.status, "NOOP");
  assert.equal(noop.lastErrorCode, "INELIGIBLE_NOOP");
  assert.equal(noop.recipientEmail, null);
  assert.ok((await tokenState(firstMaterial.id)).usedAt);
  const replacementCount = await admin.query<{ count: string }>(
    'SELECT count(*)::text AS count FROM public."auth_tokens" WHERE "id" = $1',
    [unusedReplacement.id],
  );
  assert.equal(replacementCount.rows[0]?.count, "0");
}

async function proveCrashedPreparedLeaseIsTerminal(): Promise<void> {
  const id = await enqueue(fixtures.crashedLease.email, "PASSWORD_RESET");
  const firstClaim = await claimExact(id);
  const material = tokenMaterial("crashed-lease-0001");
  assert.equal((await prepare(firstClaim, material)).length, 1);
  await admin.query(
    `UPDATE public."auth_email_outbox"
        SET "claimedAt" = clock_timestamp() - INTERVAL '3 minutes',
            "leaseExpiresAt" = clock_timestamp() - INTERVAL '1 second',
            "updatedAt" = clock_timestamp()
      WHERE "id" = $1::uuid`,
    [id],
  );
  assert.ok(!(await claim(100)).some((row) => row.id === id));
  const terminal = await outboxState(id);
  assert.equal(terminal.status, "AMBIGUOUS");
  assert.equal(terminal.lastErrorCode, "LEASE_OUTCOME_AMBIGUOUS");
  assert.ok((await tokenState(material.id)).usedAt);
}

async function prepareResetForTrigger(
  fixture: { id: string; email: string },
  label: string,
): Promise<{ id: string; tokenId: string }> {
  const id = await enqueue(fixture.email, "PASSWORD_RESET");
  const claimed = await claimExact(id);
  const material = tokenMaterial(label);
  assert.equal((await prepare(claimed, material)).length, 1);
  return { id, tokenId: material.id };
}

async function assertTriggerCancelled(
  id: string,
  tokenId: string,
): Promise<void> {
  const row = await outboxState(id);
  assert.equal(row.status, "FAILED");
  assert.equal(row.lastErrorCode, "ACCOUNT_SECURITY_STATE_CHANGED");
  assert.ok((await tokenState(tokenId)).usedAt);
}

async function proveSecurityTrigger(): Promise<void> {
  const password = await prepareResetForTrigger(
    fixtures.triggerPassword,
    "trigger-password-0001",
  );
  await admin.query(
    `UPDATE public."users"
        SET "passwordHash" = 'synthetic-rotated-password-hash',
            "updatedAt" = clock_timestamp()
      WHERE "id" = $1`,
    [fixtures.triggerPassword.id],
  );
  await assertTriggerCancelled(password.id, password.tokenId);

  const email = await prepareResetForTrigger(
    fixtures.triggerEmail,
    "trigger-email-0001",
  );
  await admin.query(
    `UPDATE public."users"
        SET "email" = $2, "updatedAt" = clock_timestamp()
      WHERE "id" = $1`,
    [fixtures.triggerEmail.id, triggerEmailReplacement],
  );
  await assertTriggerCancelled(email.id, email.tokenId);

  const lifecycle = await prepareResetForTrigger(
    fixtures.triggerLifecycle,
    "trigger-lifecycle-0001",
  );
  await admin.query(
    `UPDATE public."users"
        SET "suspendedAt" = clock_timestamp(), "updatedAt" = clock_timestamp()
      WHERE "id" = $1`,
    [fixtures.triggerLifecycle.id],
  );
  await assertTriggerCancelled(lifecycle.id, lifecycle.tokenId);
}

interface PreparedChangeAuthority {
  id: string;
  claimed: ClaimRow;
  tokenId: string;
}

async function prepareChangeAuthority(
  fixture: { id: string; email: string },
  targetEmail: string,
  label: string,
): Promise<PreparedChangeAuthority> {
  const id = await enqueueChange(
    fixture.id,
    fixture.email,
    targetEmail,
    practiceId,
    fixtureSessionToken(fixture.id),
  );
  const claimed = await claimExact(id);
  const material = tokenMaterial(label);
  const prepared = await prepare(claimed, material);
  assert.equal(prepared.length, 1);
  assert.equal(prepared[0]?.purpose, "EMAIL_CHANGE");
  assert.equal((await tokenState(material.id)).usedAt, null);
  return { id, claimed, tokenId: material.id };
}

async function assertChangeAuthorityCancelled(
  prepared: PreparedChangeAuthority,
  expectedErrorCode:
    | "ACCOUNT_SECURITY_STATE_CHANGED"
    | "SESSION_AUTHORITY_CHANGED"
    | "PRACTICE_AUTHORITY_CHANGED",
): Promise<void> {
  const row = await outboxState(prepared.id);
  assert.equal(row.status, "FAILED");
  assert.equal(row.lastErrorCode, expectedErrorCode);
  assert.equal(row.recipientEmail, null);
  assert.ok((await tokenState(prepared.tokenId)).usedAt);
}

async function proveSessionAuthorityInvalidation(): Promise<void> {
  const deleted = await prepareChangeAuthority(
    fixtures.authoritySessionDelete,
    authorityTargets.sessionDelete,
    "authority-session-delete-0001",
  );
  await admin.query(
    `DELETE FROM public."user_sessions"
      WHERE "userId" = $1 AND "sessionToken" = $2`,
    [
      fixtures.authoritySessionDelete.id,
      fixtureSessionToken(fixtures.authoritySessionDelete.id),
    ],
  );
  await assertChangeAuthorityCancelled(deleted, "SESSION_AUTHORITY_CHANGED");

  const updated = await prepareChangeAuthority(
    fixtures.authoritySessionUpdate,
    authorityTargets.sessionUpdate,
    "authority-session-update-0001",
  );
  const unrelatedToken = "synthetic-auth-email-unrelated-session-token";
  await admin.query(
    `INSERT INTO public."user_sessions" (
       "id", "userId", "sessionToken", "createdAt", "lastActiveAt",
       "expiresAt"
     ) VALUES (
       'synthetic-auth-email-unrelated-session-row', $1, $2,
       clock_timestamp(), clock_timestamp(),
       clock_timestamp() + INTERVAL '1 hour'
     )`,
    [fixtures.authoritySessionUpdate.id, unrelatedToken],
  );
  await admin.query(
    `UPDATE public."user_sessions"
        SET "expiresAt" = "expiresAt" + INTERVAL '1 minute'
      WHERE "sessionToken" = $1`,
    [unrelatedToken],
  );
  assert.equal((await outboxState(updated.id)).status, "CLAIMED");
  assert.equal((await tokenState(updated.tokenId)).usedAt, null);

  await admin.query(
    `UPDATE public."user_sessions"
        SET "expiresAt" = "expiresAt" + INTERVAL '1 minute'
      WHERE "userId" = $1 AND "sessionToken" = $2`,
    [
      fixtures.authoritySessionUpdate.id,
      fixtureSessionToken(fixtures.authoritySessionUpdate.id),
    ],
  );
  await assertChangeAuthorityCancelled(updated, "SESSION_AUTHORITY_CHANGED");
}

async function proveAccountAndPracticeAuthorityInvalidation(): Promise<void> {
  const forceLogout = await prepareChangeAuthority(
    fixtures.authorityForceLogout,
    authorityTargets.forceLogout,
    "authority-force-logout-0001",
  );
  await admin.query(
    `UPDATE public."users"
        SET "forceLogoutAt" = clock_timestamp(),
            "updatedAt" = clock_timestamp()
      WHERE "id" = $1`,
    [fixtures.authorityForceLogout.id],
  );
  await assertChangeAuthorityCancelled(
    forceLogout,
    "ACCOUNT_SECURITY_STATE_CHANGED",
  );

  const userMutations: Array<{
    label: keyof Pick<
      typeof authorityTargets,
      | "role"
      | "product"
      | "mfaEnabled"
      | "mfaSecret"
      | "mfaVerifiedAt"
      | "mfaBackupCodes"
    >;
    mutate: string;
    restore: string;
  }> = [
    {
      label: "role",
      mutate: `SET "role" = 'STAFF', "updatedAt" = clock_timestamp()`,
      restore: `SET "role" = 'DOCTOR', "updatedAt" = clock_timestamp()`,
    },
    {
      label: "product",
      mutate: `SET "products" = ARRAY['MEDDOC_PRO']::"Product"[],
        "updatedAt" = clock_timestamp()`,
      restore: `SET "products" = ARRAY['TRANSCRIBE_MD']::"Product"[],
        "updatedAt" = clock_timestamp()`,
    },
    {
      label: "mfaEnabled",
      mutate: `SET "mfaEnabled" = TRUE, "updatedAt" = clock_timestamp()`,
      restore: `SET "mfaEnabled" = FALSE, "updatedAt" = clock_timestamp()`,
    },
    {
      label: "mfaSecret",
      mutate: `SET "mfaSecret" = 'synthetic-mfa-secret-ciphertext',
        "updatedAt" = clock_timestamp()`,
      restore: `SET "mfaSecret" = NULL, "updatedAt" = clock_timestamp()`,
    },
    {
      label: "mfaVerifiedAt",
      mutate: `SET "mfaVerifiedAt" = clock_timestamp(),
        "updatedAt" = clock_timestamp()`,
      restore: `SET "mfaVerifiedAt" = NULL, "updatedAt" = clock_timestamp()`,
    },
    {
      label: "mfaBackupCodes",
      mutate: `SET "mfaBackupCodes" = ARRAY['synthetic-mfa-backup-hash'],
        "updatedAt" = clock_timestamp()`,
      restore: `SET "mfaBackupCodes" = ARRAY[]::TEXT[],
        "updatedAt" = clock_timestamp()`,
    },
  ];
  for (const mutation of userMutations) {
    const prepared = await prepareChangeAuthority(
      fixtures.authorityMutations,
      authorityTargets[mutation.label],
      `authority-${mutation.label}-0001`,
    );
    await admin.query(
      `UPDATE public."users" ${mutation.mutate} WHERE "id" = $1`,
      [fixtures.authorityMutations.id],
    );
    await assertChangeAuthorityCancelled(
      prepared,
      "ACCOUNT_SECURITY_STATE_CHANGED",
    );
    await admin.query(
      `UPDATE public."users" ${mutation.restore} WHERE "id" = $1`,
      [fixtures.authorityMutations.id],
    );
  }

  const practice = await prepareChangeAuthority(
    fixtures.authorityPractice,
    authorityTargets.practice,
    "authority-practice-inactive-0001",
  );
  await admin.query(
    `UPDATE public."practices"
        SET "isActive" = FALSE, "updatedAt" = clock_timestamp()
      WHERE "id" = $1`,
    [practiceId],
  );
  await assertChangeAuthorityCancelled(practice, "PRACTICE_AUTHORITY_CHANGED");
  await admin.query(
    `UPDATE public."practices"
        SET "isActive" = TRUE, "updatedAt" = clock_timestamp()
      WHERE "id" = $1`,
    [practiceId],
  );
}

type RedeemablePurpose =
  | "PASSWORD_RESET"
  | "EMAIL_VERIFICATION"
  | "EMAIL_CHANGE";

async function mintDeliveredGeneric(
  fixture: { id: string; email: string },
  purpose: "PASSWORD_RESET" | "EMAIL_VERIFICATION",
  label: string,
): Promise<{ outboxId: string; material: ReturnType<typeof tokenMaterial> }> {
  const outboxId = await enqueue(fixture.email, purpose);
  const claimed = await claimExact(outboxId);
  const material = tokenMaterial(label);
  assert.equal((await prepare(claimed, material)).length, 1);
  await finish(
    claimed,
    material.id,
    true,
    null,
    sha256(`synthetic-provider-redeem-${label}-receipt`),
  );
  return { outboxId, material };
}

async function lockAndConsumeForRoute(
  client: Client,
  fixture: { id: string; email: string },
  material: ReturnType<typeof tokenMaterial>,
  purpose: RedeemablePurpose,
  redeemedAt: Date,
  beforeConsume?: (client: Client) => Promise<void>,
): Promise<Record<string, unknown> | null> {
  const user = await client.query<{ id: string; email: string }>(
    `SELECT "id", "email" FROM public."users"
      WHERE "id" = $1 FOR UPDATE`,
    [fixture.id],
  );
  assert.deepEqual(user.rows, [{ id: fixture.id, email: fixture.email }]);
  const token = await client.query<{
    id: string;
    metadata: Record<string, unknown> | null;
  }>(
    `SELECT "id", "metadata" FROM public."auth_tokens"
      WHERE "id" = $1
        AND "userId" = $2
        AND "purpose" = $3::"AuthTokenPurpose"
        AND "tokenHash" = $4
        AND "usedAt" IS NULL
        AND "expiresAt" > $5
      FOR UPDATE`,
    [material.id, fixture.id, purpose, material.hash, redeemedAt],
  );
  assert.equal(token.rows.length, 1, "route bearer must be exactly current");
  const current = await client.query<{ id: string }>(
    `SELECT "id" FROM public."auth_tokens"
      WHERE "userId" = $1
        AND "purpose" = $2::"AuthTokenPurpose"
        AND "usedAt" IS NULL
      ORDER BY "createdAt" DESC, "id" DESC
      LIMIT 2`,
    [fixture.id, purpose],
  );
  assert.deepEqual(current.rows, [{ id: material.id }]);
  await beforeConsume?.(client);
  const consumed = await client.query(
    `UPDATE public."auth_tokens"
        SET "usedAt" = $2
      WHERE "id" = $1 AND "usedAt" IS NULL`,
    [material.id, redeemedAt],
  );
  assert.equal(consumed.rowCount, 1, "consume must precede security mutation");
  return token.rows[0]!.metadata;
}

async function proveRouteOrderedRedemptions(): Promise<void> {
  const reset = await mintDeliveredGeneric(
    fixtures.redeemReset,
    "PASSWORD_RESET",
    "redeem-reset-0001",
  );
  await boundedTransaction("auth-email-redeem-reset", async (client) => {
    const redeemedAt = new Date();
    const metadata = await lockAndConsumeForRoute(
      client,
      fixtures.redeemReset,
      reset.material,
      "PASSWORD_RESET",
      redeemedAt,
    );
    assert.deepEqual(metadata, { email: fixtures.redeemReset.email });
    await client.query(
      `UPDATE public."users"
          SET "passwordHash" = 'synthetic-route-reset-password-hash',
              "failedLoginCount" = 0, "lockedUntil" = NULL,
              "updatedAt" = $2
        WHERE "id" = $1`,
      [fixtures.redeemReset.id, redeemedAt],
    );
    await client.query(
      'DELETE FROM public."user_sessions" WHERE "userId" = $1',
      [fixtures.redeemReset.id],
    );
    await client.query(
      `UPDATE public."auth_tokens" SET "usedAt" = $2
        WHERE "userId" = $1
          AND "purpose" IN ('PASSWORD_RESET', 'EMAIL_CHANGE')
          AND "usedAt" IS NULL`,
      [fixtures.redeemReset.id, redeemedAt],
    );
  });
  assert.ok((await tokenState(reset.material.id)).usedAt);
  const resetUser = await admin.query<{ passwordHash: string }>(
    'SELECT "passwordHash" FROM public."users" WHERE "id" = $1',
    [fixtures.redeemReset.id],
  );
  assert.equal(
    resetUser.rows[0]?.passwordHash,
    "synthetic-route-reset-password-hash",
  );
  assert.equal((await outboxState(reset.outboxId)).status, "DELIVERED");

  const verification = await mintDeliveredGeneric(
    fixtures.redeemVerification,
    "EMAIL_VERIFICATION",
    "redeem-verification-0001",
  );
  await boundedTransaction("auth-email-redeem-verification", async (client) => {
    const redeemedAt = new Date();
    const metadata = await lockAndConsumeForRoute(
      client,
      fixtures.redeemVerification,
      verification.material,
      "EMAIL_VERIFICATION",
      redeemedAt,
    );
    assert.deepEqual(metadata, {
      email: fixtures.redeemVerification.email,
    });
    await client.query(
      `UPDATE public."users"
            SET "emailVerified" = $2, "updatedAt" = $2
          WHERE "id" = $1`,
      [fixtures.redeemVerification.id, redeemedAt],
    );
    await client.query(
      'DELETE FROM public."user_sessions" WHERE "userId" = $1',
      [fixtures.redeemVerification.id],
    );
    await client.query(
      `UPDATE public."auth_tokens" SET "usedAt" = $2
          WHERE "userId" = $1
            AND "purpose" = 'EMAIL_VERIFICATION'
            AND "usedAt" IS NULL`,
      [fixtures.redeemVerification.id, redeemedAt],
    );
  });
  assert.ok((await tokenState(verification.material.id)).usedAt);
  const verifiedUser = await admin.query<{ emailVerified: Date | null }>(
    'SELECT "emailVerified" FROM public."users" WHERE "id" = $1',
    [fixtures.redeemVerification.id],
  );
  assert.ok(verifiedUser.rows[0]?.emailVerified);
  assert.equal((await outboxState(verification.outboxId)).status, "DELIVERED");

  const change = await prepareChangeAuthority(
    fixtures.redeemChange,
    authorityTargets.redeemChange,
    "redeem-change-0001",
  );
  await finish(
    change.claimed,
    change.tokenId,
    true,
    null,
    sha256("synthetic-provider-redeem-change-receipt"),
  );
  const changeMaterial = {
    id: change.tokenId,
    raw: "synthetic-auth-email-raw-bearer-redeem-change-0001-never-delivered",
    hash: sha256(
      "synthetic-auth-email-raw-bearer-redeem-change-0001-never-delivered",
    ),
  };
  await boundedTransaction("auth-email-redeem-change", async (client) => {
    const redeemedAt = new Date();
    const metadata = await lockAndConsumeForRoute(
      client,
      fixtures.redeemChange,
      changeMaterial,
      "EMAIL_CHANGE",
      redeemedAt,
    );
    assert.deepEqual(metadata, {
      newEmail: authorityTargets.redeemChange,
      oldEmail: fixtures.redeemChange.email,
    });
    const conflict = await client.query<{ id: string }>(
      'SELECT "id" FROM public."users" WHERE "email" = $1',
      [authorityTargets.redeemChange],
    );
    assert.deepEqual(conflict.rows, []);
    await client.query(
      `UPDATE public."users"
          SET "email" = $2, "emailVerified" = $3, "updatedAt" = $3
        WHERE "id" = $1`,
      [fixtures.redeemChange.id, authorityTargets.redeemChange, redeemedAt],
    );
    await client.query(
      'DELETE FROM public."user_sessions" WHERE "userId" = $1',
      [fixtures.redeemChange.id],
    );
    await client.query(
      `UPDATE public."auth_tokens" SET "usedAt" = $2
        WHERE "userId" = $1
          AND "purpose" IN (
            'PASSWORD_RESET', 'EMAIL_VERIFICATION', 'EMAIL_CHANGE'
          )
          AND "usedAt" IS NULL`,
      [fixtures.redeemChange.id, redeemedAt],
    );
  });
  assert.ok((await tokenState(change.tokenId)).usedAt);
  const changedUser = await admin.query<{
    email: string;
    emailVerified: Date | null;
  }>('SELECT "email", "emailVerified" FROM public."users" WHERE "id" = $1', [
    fixtures.redeemChange.id,
  ]);
  assert.equal(changedUser.rows[0]?.email, authorityTargets.redeemChange);
  assert.ok(changedUser.rows[0]?.emailVerified);
  assert.equal((await outboxState(change.id)).status, "DELIVERED");

  const conflictLabel = "redeem-change-conflict-0001";
  const conflict = await prepareChangeAuthority(
    fixtures.redeemChangeConflict,
    authorityTargets.redeemChangeConflict,
    conflictLabel,
  );
  await finish(
    conflict.claimed,
    conflict.tokenId,
    true,
    null,
    sha256("synthetic-provider-redeem-change-conflict-receipt"),
  );
  const conflictMaterial = tokenMaterial(conflictLabel);
  let uniqueFailure: unknown;
  try {
    await boundedTransaction(
      "auth-email-redeem-change-unique-race",
      async (client) => {
        const redeemedAt = new Date();
        const metadata = await lockAndConsumeForRoute(
          client,
          fixtures.redeemChangeConflict,
          conflictMaterial,
          "EMAIL_CHANGE",
          redeemedAt,
          async (routeClient) => {
            const beforeRace = await routeClient.query<{ id: string }>(
              'SELECT "id" FROM public."users" WHERE "email" = $1',
              [authorityTargets.redeemChangeConflict],
            );
            assert.deepEqual(beforeRace.rows, []);
            await admin.query(
              `UPDATE public."users"
                  SET "email" = $2, "updatedAt" = clock_timestamp()
                WHERE "id" = $1`,
              [
                fixtures.redeemChangeConflictOwner.id,
                authorityTargets.redeemChangeConflict,
              ],
            );
          },
        );
        assert.deepEqual(metadata, {
          newEmail: authorityTargets.redeemChangeConflict,
          oldEmail: fixtures.redeemChangeConflict.email,
        });
        await client.query(
          `UPDATE public."users"
              SET "email" = $2, "emailVerified" = $3, "updatedAt" = $3
            WHERE "id" = $1`,
          [
            fixtures.redeemChangeConflict.id,
            authorityTargets.redeemChangeConflict,
            redeemedAt,
          ],
        );
      },
    );
  } catch (error) {
    uniqueFailure = error;
  }
  assert.ok(
    uniqueFailure instanceof Error,
    "the cross-user unique-index race must reject the identity mutation",
  );
  assert.equal(
    (uniqueFailure as Error & { code?: string }).code,
    "23505",
    "the database unique index must arbitrate the cross-user race",
  );
  assert.equal(
    (await tokenState(conflict.tokenId)).usedAt,
    null,
    "transaction rollback must restore the consumed bearer",
  );
  const conflictSource = await admin.query<{ email: string }>(
    'SELECT "email" FROM public."users" WHERE "id" = $1',
    [fixtures.redeemChangeConflict.id],
  );
  assert.equal(
    conflictSource.rows[0]?.email,
    fixtures.redeemChangeConflict.email,
    "transaction rollback must preserve the source identity",
  );
  const conflictSessions = await admin.query<{ count: string }>(
    'SELECT count(*)::text AS count FROM public."user_sessions" WHERE "userId" = $1',
    [fixtures.redeemChangeConflict.id],
  );
  assert.equal(
    conflictSessions.rows[0]?.count,
    "1",
    "the failed identity mutation must not revoke sessions",
  );
  assert.equal((await outboxState(conflict.id)).status, "DELIVERED");
}

interface BarrierRaceOperation {
  applicationName: string;
  role?: TestRole;
  text: string;
  values: readonly unknown[];
}

async function runTokenBarrierRace(
  tokenId: string,
  first: BarrierRaceOperation,
  second: BarrierRaceOperation,
): Promise<[SettledDatabaseOperation, SettledDatabaseOperation]> {
  const barrier = new Client({ connectionString: databaseUrl });
  await barrier.connect();
  await barrier.query("BEGIN");
  await barrier.query("SET LOCAL lock_timeout = '3s'");
  await barrier.query(
    'SELECT "id" FROM public."auth_tokens" WHERE "id" = $1 FOR UPDATE',
    [tokenId],
  );

  const firstClient = await openBoundedTransaction(
    first.applicationName,
    first.role,
  );
  const secondClient = await openBoundedTransaction(
    second.applicationName,
    second.role,
  );
  let barrierReleased = false;
  let firstPromise: Promise<SettledDatabaseOperation> | undefined;
  let secondPromise: Promise<SettledDatabaseOperation> | undefined;
  try {
    firstPromise = settleDatabaseOperation(
      firstClient,
      firstClient.query(first.text, [...first.values]),
    );
    await waitForLockWaiters([first.applicationName], 1);
    secondPromise = settleDatabaseOperation(
      secondClient,
      secondClient.query(second.text, [...second.values]),
    );
    await waitForLockWaiters(
      [first.applicationName, second.applicationName],
      2,
    );
    await barrier.query("COMMIT");
    barrierReleased = true;
    return await Promise.all([firstPromise, secondPromise]);
  } finally {
    if (!barrierReleased) {
      await barrier.query("ROLLBACK").catch(() => undefined);
    }
    await barrier.end().catch(() => undefined);
    if (firstPromise) {
      await firstPromise.catch(() => undefined);
    } else {
      await firstClient.query("ROLLBACK").catch(() => undefined);
      await firstClient.end().catch(() => undefined);
    }
    if (secondPromise) {
      await secondPromise.catch(() => undefined);
    } else {
      await secondClient.query("ROLLBACK").catch(() => undefined);
      await secondClient.end().catch(() => undefined);
    }
  }
}

async function prepareExpiredClaimRace(
  fixture: { id: string; email: string },
  label: string,
): Promise<{
  id: string;
  claimed: ClaimRow;
  material: ReturnType<typeof tokenMaterial>;
}> {
  const id = await enqueue(fixture.email, "PASSWORD_RESET");
  const claimed = await claimExact(id);
  const material = tokenMaterial(label);
  assert.equal((await prepare(claimed, material)).length, 1);
  await admin.query(
    `UPDATE public."auth_email_outbox"
        SET "claimedAt" = clock_timestamp() - INTERVAL '3 minutes',
            "leaseExpiresAt" = clock_timestamp() - INTERVAL '1 second',
            "updatedAt" = clock_timestamp()
      WHERE "id" = $1::uuid`,
    [id],
  );
  return { id, claimed, material };
}

function finishRaceOperation(
  applicationName: string,
  claimed: ClaimRow,
  tokenId: string,
): BarrierRaceOperation {
  return {
    applicationName,
    role: dispatcherRole,
    text: `SELECT public.auth_email_finish_delivery(
      $1::uuid, $2::uuid, $3, TRUE, NULL, $4
    )`,
    values: [
      claimed.id,
      claimed.claimToken,
      tokenId,
      sha256(`synthetic-provider-${applicationName}-receipt`),
    ],
  };
}

function claimRaceOperation(applicationName: string): BarrierRaceOperation {
  return {
    applicationName,
    role: dispatcherRole,
    text: "SELECT * FROM public.auth_email_claim(100)",
    values: [],
  };
}

async function proveFinishVsExpiredClaimRace(): Promise<void> {
  for (const testCase of [
    {
      fixture: fixtures.raceExpiredFinishFirst,
      label: "race-expired-finish-first-0001",
      first: "finish" as const,
    },
    {
      fixture: fixtures.raceExpiredClaimFirst,
      label: "race-expired-claim-first-0001",
      first: "claim" as const,
    },
  ]) {
    const prepared = await prepareExpiredClaimRace(
      testCase.fixture,
      testCase.label,
    );
    const finishOperation = finishRaceOperation(
      `auth-email-${testCase.label}-finish`,
      prepared.claimed,
      prepared.material.id,
    );
    const claimOperation = claimRaceOperation(
      `auth-email-${testCase.label}-claim`,
    );
    const [first, second] = await runTokenBarrierRace(
      prepared.material.id,
      testCase.first === "finish" ? finishOperation : claimOperation,
      testCase.first === "finish" ? claimOperation : finishOperation,
    );
    assertNoConcurrencyTimeoutOrDeadlock(first);
    assertNoConcurrencyTimeoutOrDeadlock(second);
    const finishResult = testCase.first === "finish" ? first : second;
    const claimResult = testCase.first === "claim" ? first : second;
    assert.equal(finishResult.ok, false);
    assert.match(
      finishResult.error?.message ?? "",
      /Auth email completion is not current/u,
    );
    assert.equal(claimResult.ok, true);
    const terminal = await outboxState(prepared.id);
    assert.equal(terminal.status, "AMBIGUOUS");
    assert.equal(terminal.lastErrorCode, "LEASE_OUTCOME_AMBIGUOUS");
    assert.ok((await tokenState(prepared.material.id)).usedAt);
  }
}

async function proveFinishVsSessionDeleteRace(): Promise<void> {
  for (const testCase of [
    {
      fixture: fixtures.raceSessionFinishFirst,
      target: authorityTargets.raceSessionFinishFirst,
      label: "race-session-finish-first-0001",
      first: "finish" as const,
    },
    {
      fixture: fixtures.raceSessionDeleteFirst,
      target: authorityTargets.raceSessionDeleteFirst,
      label: "race-session-delete-first-0001",
      first: "delete" as const,
    },
  ]) {
    const prepared = await prepareChangeAuthority(
      testCase.fixture,
      testCase.target,
      testCase.label,
    );
    const finishOperation = finishRaceOperation(
      `auth-email-${testCase.label}-finish`,
      prepared.claimed,
      prepared.tokenId,
    );
    const deleteOperation: BarrierRaceOperation = {
      applicationName: `auth-email-${testCase.label}-delete`,
      text: `DELETE FROM public."user_sessions"
        WHERE "userId" = $1 AND "sessionToken" = $2`,
      values: [testCase.fixture.id, fixtureSessionToken(testCase.fixture.id)],
    };
    const [first, second] = await runTokenBarrierRace(
      prepared.tokenId,
      testCase.first === "finish" ? finishOperation : deleteOperation,
      testCase.first === "finish" ? deleteOperation : finishOperation,
    );
    assertNoConcurrencyTimeoutOrDeadlock(first);
    assertNoConcurrencyTimeoutOrDeadlock(second);
    const finishResult = testCase.first === "finish" ? first : second;
    const deleteResult = testCase.first === "delete" ? first : second;
    assert.equal(deleteResult.ok, true);
    const terminal = await outboxState(prepared.id);
    if (testCase.first === "finish") {
      assert.equal(finishResult.ok, true);
      assert.equal(terminal.status, "DELIVERED");
      assert.equal(terminal.lastErrorCode, null);
    } else {
      assert.equal(finishResult.ok, false);
      assert.match(
        finishResult.error?.message ?? "",
        /Auth email completion is not current/u,
      );
      assert.equal(terminal.status, "FAILED");
      assert.equal(terminal.lastErrorCode, "SESSION_AUTHORITY_CHANGED");
    }
    assert.equal(terminal.recipientEmail, null);
    assert.ok((await tokenState(prepared.tokenId)).usedAt);
    const session = await admin.query<{ count: string }>(
      `SELECT count(*)::text AS count FROM public."user_sessions"
        WHERE "userId" = $1 AND "sessionToken" = $2`,
      [testCase.fixture.id, fixtureSessionToken(testCase.fixture.id)],
    );
    assert.equal(session.rows[0]?.count, "0");
  }
}

async function provePurge(): Promise<void> {
  const id = await enqueue(fixtures.purge.email, "PASSWORD_RESET");
  const claimed = await claimExact(id);
  const material = tokenMaterial("purge-0001");
  assert.equal((await prepare(claimed, material)).length, 1);
  await finish(
    claimed,
    material.id,
    true,
    null,
    sha256("synthetic-provider-purge-receipt"),
  );
  await admin.query(
    `UPDATE public."auth_email_outbox"
        SET "purgeAfter" = clock_timestamp() - INTERVAL '1 second'
      WHERE "id" = $1::uuid`,
    [id],
  );
  await admin.query(
    `UPDATE public."auth_tokens"
        SET "usedAt" = clock_timestamp() - INTERVAL '8 days'
      WHERE "id" = $1`,
    [material.id],
  );
  const unrelatedEligible = await admin.query<{ count: string }>(
    `SELECT count(*)::text AS count
       FROM public."auth_tokens"
      WHERE "userId" <> ALL($1::text[])
        AND (
          "usedAt" < clock_timestamp() - INTERVAL '7 days'
          OR ("usedAt" IS NULL
            AND "expiresAt" < clock_timestamp() - INTERVAL '7 days')
        )`,
    [fixtureUserIds],
  );
  assert.equal(
    unrelatedEligible.rows[0]?.count,
    "0",
    "purge proof refuses to touch unrelated eligible tokens",
  );
  const purged = await roleQuery<{ purged: number }>(
    dispatcherRole,
    "SELECT public.auth_email_purge(1000) AS purged",
  );
  assert.ok((purged[0]?.purged ?? 0) >= 2);
  const remaining = await admin.query<{ outbox: string; token: string }>(
    `SELECT
       (SELECT count(*)::text FROM public."auth_email_outbox" WHERE "id" = $1::uuid) AS outbox,
       (SELECT count(*)::text FROM public."auth_tokens" WHERE "id" = $2) AS token`,
    [id, material.id],
  );
  assert.deepEqual(remaining.rows[0], { outbox: "0", token: "0" });
}

async function proveRawTokenAbsence(): Promise<void> {
  const serialized = await admin.query<{ body: string }>(
    `SELECT row_to_json(token)::text AS body
       FROM public."auth_tokens" token
      WHERE "userId" = ANY($1::text[])
     UNION ALL
     SELECT row_to_json(outbox)::text AS body
       FROM public."auth_email_outbox" outbox
      WHERE "candidateUserId" = ANY($1::text[])
         OR "emailSha256" = ANY($2::text[])`,
    [fixtureUserIds, fixtureEmailHashes],
  );
  for (const raw of rawTokenFixtures) {
    assert.ok(
      serialized.rows.every((row) => !row.body.includes(raw)),
      "raw bearer material must never be persisted",
    );
  }
}

async function proveConcurrentClaimUniqueness(): Promise<void> {
  const ids = await Promise.all(
    concurrentEmails.map((email) => enqueue(email, "ACCOUNT_EXISTS")),
  );
  const batches = await Promise.all(Array.from({ length: 8 }, () => claim(3)));
  const claimed = batches.flat();
  assert.equal(claimed.length, ids.length);
  assert.equal(new Set(claimed.map((row) => row.id)).size, ids.length);
  assert.equal(new Set(claimed.map((row) => row.claimToken)).size, ids.length);
  assert.deepEqual(
    [...new Set(claimed.map((row) => row.id))].sort(),
    [...ids].sort(),
  );
}

async function main(): Promise<void> {
  try {
    await admin.connect();
    await assertInstalledContract();
    await cleanup();
    const unrelatedOutbox = await admin.query<{ count: string }>(
      'SELECT count(*)::text AS count FROM public."auth_email_outbox"',
    );
    assert.equal(
      unrelatedOutbox.rows[0]?.count,
      "0",
      "the disposable auth-email test database must not contain unrelated outbox work",
    );
    await seedFixtures();

    await proveAclBoundary();
    await proveAnonymousStorage();
    await proveAnonymousIngressLockIndependence();
    await proveEmailChangeCapability();
    await provePurposePreparation();
    await proveRecipientCooldownAndClaimCoalescing();
    await proveDurableRecipientBudget();
    await proveSameAddressEnqueueLinearization();
    await proveClaimNonce();
    await proveRequestExpiry();
    await proveIneligibleNoopRetiresToken();
    await proveCrashedPreparedLeaseIsTerminal();
    await proveSecurityTrigger();
    await proveSessionAuthorityInvalidation();
    await proveAccountAndPracticeAuthorityInvalidation();
    await proveRouteOrderedRedemptions();
    await proveFinishVsExpiredClaimRace();
    await proveFinishVsSessionDeleteRace();
    await provePurge();
    await proveRawTokenAbsence();
    await proveConcurrentClaimUniqueness();

    process.stdout.write(
      JSON.stringify({
        verdict: "PASS",
        fixtures: "synthetic-only",
        providerCalls: 0,
        targetDatabase: guardedTarget.database,
        exactRuntimeCapabilities: 2,
        exactDispatcherCapabilities: 5,
        purposesPrepared: 4,
        changeAuthorityInvalidations: 10,
        orderedRedemptions: 4,
        uniqueConflictRollback: true,
        boundedRaceOrderings: 4,
        anonymousIngressLockIndependent: true,
        claimedRequestCoalesced: true,
        deliveredRequestCooldown: true,
        durableRecipientHourlyBudget: 5,
        sameAddressEnqueueLinearized: true,
        concurrentClaimRequests: concurrentEmails.length,
        uniqueConcurrentClaims: concurrentEmails.length,
        rawBearerMaterialPersisted: false,
      }) + "\n",
    );
  } finally {
    try {
      if ((admin as Client & { _connected?: boolean })._connected) {
        await cleanup().catch(() => undefined);
      }
    } finally {
      await admin.end().catch(() => undefined);
    }
  }
}

main().catch((error) => {
  process.stderr.write(
    `${error instanceof Error ? error.message : "Auth-email outbox PostgreSQL proof failed."}\n`,
  );
  process.exitCode = 1;
});
