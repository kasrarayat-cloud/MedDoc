-- Invite-only signup: codes that permit registration, and a waitlist that does not.
--
-- Registration was open (rate-limited 5/hour/IP, nothing else). 195 accounts
-- existed, 172 had never logged in, 43 had verified an email — accruing at
-- 1-3/day, comfortably under the limit. Additive only: no existing row is
-- touched, and every existing account keeps working exactly as before.

CREATE TABLE "invite_codes" (
    "id" TEXT NOT NULL,
    "codeHash" TEXT NOT NULL,
    "label" TEXT,
    "maxUses" INTEGER NOT NULL DEFAULT 1,
    "usedCount" INTEGER NOT NULL DEFAULT 0,
    "expiresAt" TIMESTAMP(3),
    "revokedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "invite_codes_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "invite_codes_codeHash_key" ON "invite_codes"("codeHash");
CREATE INDEX "invite_codes_revokedAt_expiresAt_idx" ON "invite_codes"("revokedAt", "expiresAt");

CREATE TABLE "waitlist_entries" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT,
    "note" TEXT,
    "source" TEXT,
    "invitedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "waitlist_entries_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "waitlist_entries_email_key" ON "waitlist_entries"("email");
CREATE INDEX "waitlist_entries_invitedAt_createdAt_idx" ON "waitlist_entries"("invitedAt", "createdAt");
