-- Linearize bearer-token issuance by account and purpose. Historical
-- duplicates are failed closed by retaining only the newest unused row; all
-- older links become consumed before the partial uniqueness invariant lands.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

WITH ranked AS (
  SELECT "id",
    row_number() OVER (
      PARTITION BY "userId", "purpose"
      ORDER BY "createdAt" DESC, "id" DESC
    ) AS ordinal
  FROM "auth_tokens"
  WHERE "usedAt" IS NULL
)
UPDATE "auth_tokens" token
SET "usedAt" = CURRENT_TIMESTAMP
FROM ranked
WHERE token."id" = ranked."id"
  AND ranked.ordinal > 1;

CREATE UNIQUE INDEX "auth_tokens_one_unused_per_user_purpose"
ON "auth_tokens" ("userId", "purpose")
WHERE "usedAt" IS NULL;

COMMIT;
