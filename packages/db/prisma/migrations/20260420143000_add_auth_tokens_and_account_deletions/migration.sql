-- T-M16.2: HIPAA trio — forgot-password / delete-account / export-data
-- (and email-verification gate as part of the same feature set).
--   1) AuthTokenPurpose enum + auth_tokens table
--   2) account_deletions audit table
--   3) Backfill existing users' emailVerified to createdAt so the
--      email-verification gate (when enabled) doesn't retroactively
--      lock out users who signed up before it existed.

-- ------------------------------------------------------------------
-- 1. auth_tokens
-- ------------------------------------------------------------------
CREATE TYPE "AuthTokenPurpose" AS ENUM (
    'PASSWORD_RESET',
    'EMAIL_VERIFICATION',
    'EMAIL_CHANGE'
);

CREATE TABLE "auth_tokens" (
    "id"        TEXT NOT NULL,
    "userId"    TEXT NOT NULL,
    "purpose"   "AuthTokenPurpose" NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "usedAt"    TIMESTAMP(3),
    "metadata"  JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "auth_tokens_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "auth_tokens_tokenHash_key"
  ON "auth_tokens"("tokenHash");

CREATE INDEX "auth_tokens_userId_purpose_idx"
  ON "auth_tokens"("userId", "purpose");

CREATE INDEX "auth_tokens_expiresAt_idx"
  ON "auth_tokens"("expiresAt");

ALTER TABLE "auth_tokens"
  ADD CONSTRAINT "auth_tokens_userId_fkey"
  FOREIGN KEY ("userId") REFERENCES "users"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;

-- ------------------------------------------------------------------
-- 2. account_deletions
-- ------------------------------------------------------------------
CREATE TABLE "account_deletions" (
    "id"         TEXT NOT NULL,
    "userId"     TEXT NOT NULL,
    "email"      TEXT NOT NULL,
    "specialty"  TEXT,
    "visitCount" INTEGER NOT NULL,
    "deletedAt"  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "purgeAt"    TIMESTAMP(3) NOT NULL,

    CONSTRAINT "account_deletions_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "account_deletions_purgeAt_idx"
  ON "account_deletions"("purgeAt");

-- ------------------------------------------------------------------
-- 3. Backfill existing users' emailVerified to createdAt.
-- Treats every pre-T-M16.2 account as "verified" so enabling the
-- verification gate (with RESEND_API_KEY + RESEND_FROM_VERIFIED)
-- doesn't retroactively lock them out.
-- ------------------------------------------------------------------
UPDATE "users"
SET "emailVerified" = "createdAt"
WHERE "emailVerified" IS NULL;
