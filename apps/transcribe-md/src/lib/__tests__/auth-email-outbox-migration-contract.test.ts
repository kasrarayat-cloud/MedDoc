import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");
const migration = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260720170000_auth_email_outbox_and_dispatcher_v6/migration.sql",
  ),
  "utf8",
);
const schema = readFileSync(
  resolve(repositoryRoot, "packages/db/prisma/schema.prisma"),
  "utf8",
);

const PURPOSES = [
  "PASSWORD_RESET",
  "EMAIL_VERIFICATION",
  "EMAIL_CHANGE",
  "ACCOUNT_EXISTS",
] as const;
const STATUSES = [
  "PENDING",
  "CLAIMED",
  "DELIVERED",
  "AMBIGUOUS",
  "NOOP",
  "FAILED",
] as const;

function sqlEnum(name: string): string[] {
  const match = migration.match(
    new RegExp(`CREATE TYPE "${name}" AS ENUM \\(([\\s\\S]*?)\\);`, "u"),
  );
  expect(match, `${name} must be created by auth-email v6`).not.toBeNull();
  return [...match![1]!.matchAll(/'([^']+)'/gu)].map((item) => item[1]!);
}

function prismaBlock(kind: "enum" | "model", name: string): string {
  const match = schema.match(
    new RegExp(`${kind} ${name} \\{([\\s\\S]*?)\\n\\}`, "u"),
  );
  expect(match, `${kind} ${name} must exist in Prisma`).not.toBeNull();
  return match![1]!;
}

function prismaEnum(name: string): string[] {
  return prismaBlock("enum", name)
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => /^[A-Z][A-Z0-9_]*$/u.test(line));
}

function functionDefinition(name: string): string {
  const marker = `CREATE OR REPLACE FUNCTION public.${name}`;
  const start = migration.indexOf(marker);
  expect(start, `${name} must exist`).toBeGreaterThanOrEqual(0);
  const nextFunction = migration.indexOf(
    "CREATE OR REPLACE FUNCTION public.",
    start + marker.length,
  );
  const nextTrigger = migration.indexOf(
    "CREATE TRIGGER ",
    start + marker.length,
  );
  const ends = [nextFunction, nextTrigger].filter((value) => value > start);
  return migration.slice(
    start,
    ends.length > 0 ? Math.min(...ends) : undefined,
  );
}

function canonicalSql(value: string): string {
  return value
    .replace(/\s+/gu, " ")
    .replace(/\s*([(),;])\s*/gu, "$1")
    .trim();
}

describe("auth-email outbox and dispatcher v6 migration contract", () => {
  it("keeps the SQL and Prisma purpose/status enums exact and aligned", () => {
    expect(sqlEnum("AuthEmailPurpose")).toEqual(PURPOSES);
    expect(prismaEnum("AuthEmailPurpose")).toEqual(PURPOSES);
    expect(sqlEnum("AuthEmailOutboxStatus")).toEqual(STATUSES);
    expect(prismaEnum("AuthEmailOutboxStatus")).toEqual(STATUSES);
  });

  it("uses a UUID claim nonce with an exhaustive lease shape and exact APIs", () => {
    const model = prismaBlock("model", "AuthEmailOutbox");
    expect(migration).toContain('"claimToken" UUID,');
    expect(model).toMatch(/claimToken\s+String\?\s+@db\.Uuid/u);
    expect(migration).toMatch(
      /"status" = 'CLAIMED'[\s\S]{0,180}"claimToken" IS NOT NULL[\s\S]{0,220}"status" <> 'CLAIMED'[\s\S]{0,180}"claimToken" IS NULL/u,
    );

    const claim = functionDefinition("auth_email_claim(claim_limit INTEGER)");
    expect(claim).toContain('RETURNS TABLE ("id" UUID, "claimToken" UUID)');
    expect(claim).toContain('"claimToken" = gen_random_uuid()');
    expect(claim).toContain('RETURNING outbox."id", outbox."claimToken"');

    expect(canonicalSql(migration)).toContain(
      canonicalSql(`CREATE OR REPLACE FUNCTION public.auth_email_prepare_delivery(
        request_id UUID,
        expected_claim_token UUID,
        next_token_id TEXT,
        next_token_hash TEXT
      )`),
    );
    expect(canonicalSql(migration)).toContain(
      canonicalSql(`CREATE OR REPLACE FUNCTION public.auth_email_finish_delivery(
        request_id UUID,
        expected_claim_token UUID,
        expected_token_id TEXT,
        delivered BOOLEAN,
        fixed_error_code TEXT DEFAULT NULL,
        provider_receipt_sha256 TEXT DEFAULT NULL
      )`),
    );
    for (const definition of [
      functionDefinition("auth_email_prepare_delivery("),
      functionDefinition("auth_email_finish_delivery("),
    ]) {
      expect(definition).toContain(
        'request_row."claimToken" IS DISTINCT FROM expected_claim_token',
      );
      expect(definition).toContain(
        'request_row."leaseExpiresAt" <= clock_timestamp()',
      );
    }
  });

  it("qualifies columns that collide with table-returning output names", () => {
    const prepare = functionDefinition("auth_email_prepare_delivery(");
    expect(prepare).toContain('UPDATE public."auth_tokens" token');
    expect(prepare).toContain('WHERE token."userId" = account_id');
    expect(prepare).toContain(
      'AND token."purpose" = request_row."purpose"::TEXT::"AuthTokenPurpose"',
    );
    expect(prepare).toContain(
      'UPDATE public."auth_email_outbox" outbox\n  SET "candidateUserId" = account_id,\n      "attemptCount" = outbox."attemptCount" + 1',
    );
    expect(prepare).toContain('WHERE outbox."id" = request_id');
    expect(prepare).not.toMatch(/WHERE\s+"userId"\s*=/u);
  });

  it("keeps anonymous ingress hash-only and resolves account authority in the dispatcher", () => {
    const enqueue = functionDefinition("auth_email_enqueue(");
    expect(enqueue).not.toContain('FROM public."users"');
    expect(enqueue).not.toContain('public."auth_tokens"');
    expect(enqueue).not.toContain("FOR UPDATE");
    expect(enqueue).toContain(
      "NULL, email_hash, request_purpose,\n    request_now + CASE request_purpose",
    );
    expect(enqueue).toContain("pg_advisory_xact_lock(");
    expect(enqueue).toContain(
      "hashtextextended(email_hash || ':' || request_purpose::TEXT, 0)",
    );
    expect(enqueue).toContain(
      "latest_request_status IN ('PENDING', 'CLAIMED')",
    );
    expect(enqueue).toContain(
      "latest_request_created_at > request_now - INTERVAL '60 seconds'",
    );
    expect(enqueue).toContain("hourly_request_count >= 5");
    expect(enqueue).toContain("daily_request_count >= 10");
    expect(enqueue).toContain("RETURN latest_request_id");
    expect(enqueue).toContain("AND \"status\" = 'PENDING'");
    expect(enqueue).not.toContain("AND \"status\" IN ('PENDING', 'CLAIMED')");

    const model = prismaBlock("model", "AuthEmailOutbox");
    expect(migration).toContain(
      'CREATE INDEX "auth_email_outbox_recipient_budget_idx"',
    );
    expect(model).toContain(
      '@@index([emailSha256, purpose, createdAt(sort: Desc)], map: "auth_email_outbox_recipient_budget_idx")',
    );

    const prepare = functionDefinition("auth_email_prepare_delivery(");
    expect(prepare).toContain("candidate_id_hint := stored_candidate_hint");
    expect(prepare).toContain(
      "candidate_id_hint IS NULL AND purpose_hint <> 'EMAIL_CHANGE'",
    );
    expect(prepare).toContain(
      "digest(convert_to(account.\"email\", 'UTF8'), 'sha256')",
    );
    expect(prepare).toContain(
      'request_row."candidateUserId" IS DISTINCT FROM stored_candidate_hint',
    );
    expect(prepare).toContain('SET "candidateUserId" = account_id');
  });

  it("revokes PUBLIC from every definer and grants only bounded role APIs", () => {
    const functionNames = [
      ...migration.matchAll(
        /CREATE OR REPLACE FUNCTION public\.(auth_email_[a-z_]+)\(/gu,
      ),
    ].map((match) => match[1]!);
    const expectedFunctions = [
      "auth_email_enqueue",
      "auth_email_enqueue_change",
      "auth_email_claim",
      "auth_email_prepare_delivery",
      "auth_email_finish_delivery",
      "auth_email_purge",
      "auth_email_cancel_on_user_security_change",
      "auth_email_cancel_on_session_change",
      "auth_email_cancel_on_practice_change",
      "auth_email_health",
    ];
    expect(functionNames).toEqual(expectedFunctions);
    expect(migration.match(/SECURITY DEFINER/gu)).toHaveLength(
      expectedFunctions.length + 1,
    );

    const canonical = canonicalSql(migration);
    for (const signature of [
      'auth_email_enqueue(TEXT,"AuthEmailPurpose")',
      "auth_email_enqueue_change(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT)",
      "auth_email_claim(INTEGER)",
      "auth_email_prepare_delivery(UUID,UUID,TEXT,TEXT)",
      "auth_email_finish_delivery(UUID,UUID,TEXT,BOOLEAN,TEXT,TEXT)",
      "auth_email_purge(INTEGER)",
      "auth_email_cancel_on_user_security_change()",
      "auth_email_cancel_on_session_change()",
      "auth_email_cancel_on_practice_change()",
      "auth_email_health()",
    ]) {
      expect(canonical).toContain(
        `REVOKE ALL ON FUNCTION public.${signature}FROM PUBLIC;`,
      );
    }
    expect(
      migration.match(/REVOKE ALL ON FUNCTION public\.auth_email_/gu),
    ).toHaveLength(expectedFunctions.length);
    for (const role of [
      "PUBLIC",
      "quillmd_runtime",
      "quillmd_auth_email_dispatcher",
    ]) {
      expect(canonical).toContain(
        `REVOKE ALL ON TABLE "auth_email_outbox" FROM ${role};`,
      );
    }

    const executeGrants = [
      ...migration.matchAll(/GRANT EXECUTE ON FUNCTION[\s\S]*?;/gu),
    ].map((match) => canonicalSql(match[0]));
    expect(executeGrants).toEqual([
      'GRANT EXECUTE ON FUNCTION public.auth_email_enqueue(TEXT,"AuthEmailPurpose")TO quillmd_runtime;',
      "GRANT EXECUTE ON FUNCTION public.auth_email_enqueue_change(TEXT,TEXT,TEXT,TEXT,TEXT,TEXT)TO quillmd_runtime;",
      "GRANT EXECUTE ON FUNCTION public.auth_email_claim(INTEGER),public.auth_email_prepare_delivery(UUID,UUID,TEXT,TEXT),public.auth_email_finish_delivery(UUID,UUID,TEXT,BOOLEAN,TEXT,TEXT),public.auth_email_purge(INTEGER),public.auth_email_health()TO quillmd_auth_email_dispatcher;",
    ]);
    expect(canonical).not.toMatch(
      /GRANT (?:SELECT|INSERT|UPDATE|DELETE|ALL) ON TABLE "auth_email_outbox"/u,
    );
  });

  it("expires requests before claim or bearer minting", () => {
    const model = prismaBlock("model", "AuthEmailOutbox");
    expect(migration).toContain(
      'CONSTRAINT "auth_email_outbox_request_lifetime" CHECK (\n    "requestExpiresAt" > "createdAt"',
    );
    expect(model).toMatch(
      /requestExpiresAt\s+DateTime\s+@db\.Timestamptz\(6\)/u,
    );
    expect(model).toContain(
      '@@index([requestExpiresAt], map: "auth_email_outbox_request_expiry_idx")',
    );
    expect(migration).toContain(
      "WHEN 'EMAIL_VERIFICATION' THEN INTERVAL '24 hours'",
    );
    expect(migration).toContain("ELSE INTERVAL '1 hour'");
    expect(migration).toContain("clock_timestamp() + INTERVAL '24 hours'");

    const claim = functionDefinition("auth_email_claim(");
    expect(claim).toContain('outbox."requestExpiresAt" <= clock_timestamp()');
    expect(claim).toContain("\"lastErrorCode\" = 'REQUEST_EXPIRED'");
    expect(claim).toContain('outbox."requestExpiresAt" > clock_timestamp()');
    const prepare = functionDefinition("auth_email_prepare_delivery(");
    expect(prepare).toContain(
      'request_row."requestExpiresAt" <= clock_timestamp()',
    );
    expect(prepare).toContain(
      'token_expiry := LEAST(\n      request_row."requestExpiresAt"',
    );
  });

  it("binds EMAIL_CHANGE to exact current session and account authority", () => {
    const model = prismaBlock("model", "AuthEmailOutbox");
    for (const field of [
      "authorityPracticeId",
      "authoritySessionSha256",
      "authoritySessionCreatedAt",
      "authoritySessionExpiresAt",
    ]) {
      expect(model).toContain(field);
    }
    const enqueue = functionDefinition("auth_email_enqueue_change(");
    expect(enqueue).toContain('practice."isActive" = TRUE');
    expect(enqueue).toContain('account."forceLogoutAt" < session."createdAt"');
    expect(enqueue).toContain('"authoritySessionSha256"');
    expect(enqueue).toContain("digest(convert_to(expected_session_token");

    const prepare = functionDefinition("auth_email_prepare_delivery(");
    expect(prepare).toContain(
      'session."expiresAt" = authority_session_expires_hint',
    );
    expect(prepare).toContain(
      "WHEN 'EMAIL_CHANGE' THEN request_row.\"authoritySessionExpiresAt\"",
    );
    expect(prepare).toContain("account.\"role\" = 'DOCTOR'");
    expect(prepare).toContain(
      'account."products" @> ARRAY[\'TRANSCRIBE_MD\']::"Product"[]',
    );

    const cancelUser = functionDefinition(
      "auth_email_cancel_on_user_security_change()",
    );
    for (const field of [
      "practiceId",
      "role",
      "products",
      "forceLogoutAt",
      "mfaEnabled",
      "mfaSecret",
      "mfaVerifiedAt",
      "mfaBackupCodes",
    ]) {
      expect(cancelUser).toContain(
        `NEW."${field}" IS DISTINCT FROM OLD."${field}"`,
      );
    }

    const cancelSession = functionDefinition(
      "auth_email_cancel_on_session_change()",
    );
    expect(cancelSession).toContain('OLD."sessionToken"');
    expect(cancelSession).toContain(
      "\"lastErrorCode\" = 'SESSION_AUTHORITY_CHANGED'",
    );
    const cancelPractice = functionDefinition(
      "auth_email_cancel_on_practice_change()",
    );
    expect(cancelPractice).toContain(
      'NEW."isActive" IS DISTINCT FROM OLD."isActive"',
    );
    expect(cancelPractice).toContain(
      "\"lastErrorCode\" = 'PRACTICE_AUTHORITY_CHANGED'",
    );
    expect(migration).toContain(
      "CREATE TRIGGER auth_email_cancel_on_session_delete",
    );
    expect(migration).toContain(
      "CREATE TRIGGER auth_email_cancel_on_session_update",
    );
    expect(migration).toContain(
      "CREATE TRIGGER auth_email_cancel_on_practice_change",
    );
  });

  it("makes provider-ambiguous outcomes terminal and retires their bearer", () => {
    expect(migration).toMatch(
      /"status" IN \('AMBIGUOUS', 'NOOP', 'FAILED'\)[\s\S]{0,150}"finishedAt" IS NOT NULL/u,
    );
    const claim = functionDefinition("auth_email_claim(");
    expect(claim).toMatch(
      /UPDATE public\."auth_tokens" token[\s\S]{0,420}outbox\."attemptCount" > 0[\s\S]{0,500}SET "status" = 'AMBIGUOUS'/u,
    );
    expect(claim).toContain("\"lastErrorCode\" = 'LEASE_OUTCOME_AMBIGUOUS'");
    expect(claim).toContain(
      "\"purgeAfter\" = clock_timestamp() + INTERVAL '30 days'",
    );

    const finish = functionDefinition("auth_email_finish_delivery(");
    expect(finish).toContain("provider_receipt_sha256 !~ '^[0-9a-f]{64}$'");
    expect(finish).toMatch(
      /UPDATE public\."auth_tokens"[\s\S]{0,180}"usedAt" IS NULL[\s\S]{0,240}SET "status" = 'AMBIGUOUS'/u,
    );
    expect(finish).not.toMatch(/SET "status" = 'PENDING'/u);
    expect(finish).toContain(
      "\"purgeAfter\" = clock_timestamp() + INTERVAL '30 days'",
    );
  });

  it("cancels pending authority on every relevant account security change", () => {
    const cancel = functionDefinition(
      "auth_email_cancel_on_user_security_change()",
    );
    for (const fragment of [
      'NEW."isActive" = FALSE',
      'NEW."deactivatedAt" IS NOT NULL',
      'NEW."suspendedAt" IS NOT NULL',
      'NEW."softDeletedAt" IS NOT NULL',
      'NEW."passwordHash" IS DISTINCT FROM OLD."passwordHash"',
      'NEW."email" IS DISTINCT FROM OLD."email"',
      'OLD."emailVerified" IS NULL',
      'NEW."emailVerified" IS NOT NULL',
      'SET "usedAt" = clock_timestamp()',
      "\"status\" = 'FAILED'",
      "\"lastErrorCode\" = 'ACCOUNT_SECURITY_STATE_CHANGED'",
      "outbox.\"status\" IN ('PENDING', 'CLAIMED')",
    ]) {
      expect(cancel).toContain(fragment);
    }
    expect(migration).toContain(
      'CREATE TRIGGER auth_email_cancel_on_user_security_change\nAFTER UPDATE OF "passwordHash", "email", "emailVerified", "isActive",\n  "deactivatedAt", "suspendedAt", "softDeletedAt"',
    );
    expect(migration).toContain(
      "EXECUTE FUNCTION public.auth_email_cancel_on_user_security_change();",
    );
  });

  it("bounds retention and exposes purge only to the dispatcher", () => {
    const model = prismaBlock("model", "AuthEmailOutbox");
    expect(model).toMatch(
      /purgeAfter\s+DateTime\s+@default\(dbgenerated\("CURRENT_TIMESTAMP \+ INTERVAL '7 days'"\)\) @db\.Timestamptz\(6\)/u,
    );
    expect(model).toContain(
      '@@index([purgeAfter], map: "auth_email_outbox_purge_after_idx")',
    );
    expect(migration).toContain(
      "\"purgeAfter\" = clock_timestamp() + INTERVAL '1 day'",
    );
    const purge = functionDefinition("auth_email_purge(");
    expect(purge).toContain("purge_limit NOT BETWEEN 1 AND 1000");
    expect(purge).toContain(
      "outbox.\"status\" IN ('DELIVERED', 'AMBIGUOUS', 'NOOP', 'FAILED')",
    );
    expect(purge).toContain('outbox."purgeAfter" <= clock_timestamp()');
    expect(purge.match(/FOR UPDATE SKIP LOCKED/gu)).toHaveLength(2);
    expect(purge).toContain(
      "token.\"usedAt\" < clock_timestamp() - INTERVAL '7 days'",
    );
    expect(purge).toContain(
      "token.\"expiresAt\" < clock_timestamp() - INTERVAL '7 days'",
    );
  });
});
