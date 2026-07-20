-- Durable anonymous auth-email delivery. Requests take the same database path
-- for known and unknown addresses, store no raw email or bearer token, and are
-- resolved by a least-privilege dispatcher through SECURITY DEFINER functions.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'EMAIL_VERIFIED';

CREATE TYPE "AuthEmailPurpose" AS ENUM (
  'PASSWORD_RESET',
  'EMAIL_VERIFICATION',
  'EMAIL_CHANGE',
  'ACCOUNT_EXISTS'
);

CREATE TYPE "AuthEmailOutboxStatus" AS ENUM (
  'PENDING',
  'CLAIMED',
  'DELIVERED',
  'AMBIGUOUS',
  'NOOP',
  'FAILED'
);

CREATE TABLE "auth_email_outbox" (
  "id" UUID NOT NULL DEFAULT gen_random_uuid(),
  "candidateUserId" TEXT,
  "emailSha256" CHAR(64) NOT NULL,
  "sourceEmailSha256" CHAR(64),
  "recipientEmail" TEXT,
  "authorityPracticeId" TEXT,
  "authoritySessionSha256" CHAR(64),
  "authoritySessionCreatedAt" TIMESTAMPTZ(6),
  "authoritySessionExpiresAt" TIMESTAMPTZ(6),
  "purpose" "AuthEmailPurpose" NOT NULL,
  "status" "AuthEmailOutboxStatus" NOT NULL DEFAULT 'PENDING',
  "attemptCount" INTEGER NOT NULL DEFAULT 0,
  "availableAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "requestExpiresAt" TIMESTAMPTZ(6) NOT NULL,
  "claimedAt" TIMESTAMPTZ(6),
  "leaseExpiresAt" TIMESTAMPTZ(6),
  "claimToken" UUID,
  "tokenId" TEXT,
  "providerReceiptSha256" CHAR(64),
  "lastErrorCode" TEXT,
  "finishedAt" TIMESTAMPTZ(6),
  "purgeAfter" TIMESTAMPTZ(6) NOT NULL
    DEFAULT CURRENT_TIMESTAMP + INTERVAL '7 days',
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "auth_email_outbox_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "auth_email_outbox_email_hash" CHECK (
    "emailSha256" ~ '^[0-9a-f]{64}$'
    AND (
      "sourceEmailSha256" IS NULL
      OR "sourceEmailSha256" ~ '^[0-9a-f]{64}$'
    )
    AND (
      "authoritySessionSha256" IS NULL
      OR "authoritySessionSha256" ~ '^[0-9a-f]{64}$'
    )
    AND (
      "providerReceiptSha256" IS NULL
      OR "providerReceiptSha256" ~ '^[0-9a-f]{64}$'
    )
  ),
  CONSTRAINT "auth_email_outbox_recipient_shape" CHECK (
    ("purpose" = 'EMAIL_CHANGE' AND "sourceEmailSha256" IS NOT NULL
      AND "authorityPracticeId" IS NOT NULL
      AND "authoritySessionSha256" IS NOT NULL
      AND "authoritySessionCreatedAt" IS NOT NULL
      AND "authoritySessionExpiresAt" IS NOT NULL
      AND "authoritySessionExpiresAt" > "authoritySessionCreatedAt"
      AND (
        ("status" IN ('PENDING', 'CLAIMED') AND "recipientEmail" IS NOT NULL)
        OR
        ("status" IN ('DELIVERED', 'AMBIGUOUS', 'NOOP', 'FAILED')
          AND "recipientEmail" IS NULL)
      ))
    OR
    ("purpose" <> 'EMAIL_CHANGE' AND "recipientEmail" IS NULL
      AND "sourceEmailSha256" IS NULL
      AND "authorityPracticeId" IS NULL
      AND "authoritySessionSha256" IS NULL
      AND "authoritySessionCreatedAt" IS NULL
      AND "authoritySessionExpiresAt" IS NULL)
  ),
  CONSTRAINT "auth_email_outbox_attempt_count" CHECK (
    "attemptCount" BETWEEN 0 AND 3
  ),
  CONSTRAINT "auth_email_outbox_request_lifetime" CHECK (
    "requestExpiresAt" > "createdAt"
  ),
  CONSTRAINT "auth_email_outbox_lease_shape" CHECK (
    ("status" = 'CLAIMED' AND "claimedAt" IS NOT NULL
      AND "leaseExpiresAt" IS NOT NULL AND "claimToken" IS NOT NULL
      AND "leaseExpiresAt" > "claimedAt")
    OR
    ("status" <> 'CLAIMED' AND "claimedAt" IS NULL
      AND "leaseExpiresAt" IS NULL AND "claimToken" IS NULL)
  ),
  CONSTRAINT "auth_email_outbox_terminal_shape" CHECK (
    ("status" = 'DELIVERED' AND "finishedAt" IS NOT NULL
      AND "providerReceiptSha256" IS NOT NULL)
    OR
    ("status" IN ('AMBIGUOUS', 'NOOP', 'FAILED')
      AND "finishedAt" IS NOT NULL
      AND "providerReceiptSha256" IS NULL)
    OR
    ("status" IN ('PENDING', 'CLAIMED') AND "finishedAt" IS NULL
      AND "providerReceiptSha256" IS NULL)
  )
);

ALTER TABLE "auth_email_outbox"
  ADD CONSTRAINT "auth_email_outbox_candidate_user_fkey"
  FOREIGN KEY ("candidateUserId") REFERENCES "users"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "auth_email_outbox"
  ADD CONSTRAINT "auth_email_outbox_token_fkey"
  FOREIGN KEY ("tokenId") REFERENCES "auth_tokens"("id")
  ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX "auth_email_outbox_status_available_idx"
  ON "auth_email_outbox" ("status", "availableAt");
CREATE INDEX "auth_email_outbox_lease_expiry_idx"
  ON "auth_email_outbox" ("leaseExpiresAt");
CREATE INDEX "auth_email_outbox_request_expiry_idx"
  ON "auth_email_outbox" ("requestExpiresAt");
CREATE INDEX "auth_email_outbox_recipient_budget_idx"
  ON "auth_email_outbox" ("emailSha256", "purpose", "createdAt" DESC);
CREATE INDEX "auth_email_outbox_change_authority_idx"
  ON "auth_email_outbox" (
    "candidateUserId", "purpose", "authoritySessionSha256"
  );
CREATE INDEX "auth_email_outbox_purge_after_idx"
  ON "auth_email_outbox" ("purgeAfter");

DO $roles$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'quillmd_auth_email_dispatcher'
  ) THEN
    CREATE ROLE quillmd_auth_email_dispatcher
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT
      NOREPLICATION NOBYPASSRLS;
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname = 'quillmd_auth_email_dispatcher'
      AND (
        rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit
        OR rolreplication OR rolbypassrls
      )
  ) THEN
    RAISE EXCEPTION 'Refusing non-exact auth email dispatcher role';
  END IF;
END
$roles$;

CREATE OR REPLACE FUNCTION public.auth_email_enqueue(
  request_email TEXT,
  request_purpose "AuthEmailPurpose"
)
RETURNS UUID
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  request_id UUID;
  email_hash CHAR(64);
  request_now TIMESTAMPTZ(6);
  latest_request_id UUID;
  latest_request_status "AuthEmailOutboxStatus";
  latest_request_expires_at TIMESTAMPTZ(6);
  latest_request_created_at TIMESTAMPTZ(6);
  hourly_request_count INTEGER;
  daily_request_count INTEGER;
BEGIN
  IF request_email IS NULL
    OR length(request_email) NOT BETWEEN 3 AND 254
    OR request_email <> lower(btrim(request_email))
    OR request_purpose = 'EMAIL_CHANGE'
  THEN
    RAISE EXCEPTION 'Auth email request is not normalized';
  END IF;
  email_hash := encode(
    digest(convert_to(request_email, 'UTF8'), 'sha256'),
    'hex'
  );
  -- Serialize only identical anonymous request keys. This lock contains no
  -- account-existence signal and is never combined with a user/token lock.
  -- It makes supersession plus insertion one linearizable operation without
  -- reintroducing request-visible account resolution.
  PERFORM pg_advisory_xact_lock(
    hashtextextended(email_hash || ':' || request_purpose::TEXT, 0)
  );
  request_now := clock_timestamp();

  -- Coalesce an already-active request and every request made inside the
  -- fixed 60-second recipient cooldown. The decision depends only on the
  -- recipient hash, purpose, and outbox history, so known and unknown
  -- addresses take the same path. In particular, a request arriving while a
  -- provider attempt is CLAIMED cannot mint a replacement bearer or cause a
  -- duplicate provider submission.
  SELECT outbox."id", outbox."status", outbox."requestExpiresAt",
    outbox."createdAt"
  INTO latest_request_id, latest_request_status,
    latest_request_expires_at, latest_request_created_at
  FROM public."auth_email_outbox" outbox
  WHERE outbox."emailSha256" = email_hash
    AND outbox."purpose" = request_purpose
  ORDER BY outbox."createdAt" DESC, outbox."id" DESC
  LIMIT 1;
  IF FOUND AND (
    (
      latest_request_status IN ('PENDING', 'CLAIMED')
      AND latest_request_expires_at > request_now
    )
    OR latest_request_created_at > request_now - INTERVAL '60 seconds'
  ) THEN
    RETURN latest_request_id;
  END IF;

  -- Bound distributed-source abuse independently of ingress IP. These
  -- recipient-hash budgets are intentionally identical for eligible and
  -- ineligible accounts. Returning the most recent opaque request id keeps
  -- the public response generic while preventing email amplification and
  -- repeated invalidation of a previously delivered recovery bearer.
  SELECT
    count(*) FILTER (
      WHERE outbox."createdAt" > request_now - INTERVAL '1 hour'
    )::INTEGER,
    count(*) FILTER (
      WHERE outbox."createdAt" > request_now - INTERVAL '24 hours'
    )::INTEGER
  INTO hourly_request_count, daily_request_count
  FROM public."auth_email_outbox" outbox
  WHERE outbox."emailSha256" = email_hash
    AND outbox."purpose" = request_purpose
    AND outbox."createdAt" > request_now - INTERVAL '24 hours';
  IF hourly_request_count >= 5 OR daily_request_count >= 10 THEN
    RETURN latest_request_id;
  END IF;

  -- Ingress is deliberately account-oblivious. Known and unknown addresses
  -- execute the same hash-only outbox operations and never wait on a user or
  -- token lock. The isolated dispatcher resolves current account authority,
  -- retires superseded bearers, and binds candidateUserId during prepare.
  UPDATE public."auth_email_outbox"
  SET "status" = 'FAILED', "finishedAt" = clock_timestamp(),
      "claimedAt" = NULL, "leaseExpiresAt" = NULL, "claimToken" = NULL,
      "recipientEmail" = CASE WHEN "purpose" = 'EMAIL_CHANGE'
        THEN NULL ELSE "recipientEmail" END,
      "lastErrorCode" = 'SUPERSEDED', "updatedAt" = clock_timestamp()
  WHERE "emailSha256" = email_hash
    AND "purpose" = request_purpose
    AND "status" = 'PENDING';

  INSERT INTO public."auth_email_outbox" (
    "candidateUserId", "emailSha256", "purpose", "requestExpiresAt"
  ) VALUES (
    NULL, email_hash, request_purpose,
    request_now + CASE request_purpose
      WHEN 'EMAIL_VERIFICATION' THEN INTERVAL '24 hours'
      ELSE INTERVAL '1 hour'
    END
  ) RETURNING "id" INTO request_id;
  RETURN request_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_enqueue_change(
  request_user_id TEXT,
  expected_current_email TEXT,
  requested_new_email TEXT,
  expected_practice_id TEXT,
  expected_session_token TEXT,
  expected_password_hash TEXT
)
RETURNS UUID
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  request_id UUID;
  authority_session_created_at TIMESTAMPTZ(6);
  authority_session_expires_at TIMESTAMPTZ(6);
BEGIN
  IF request_user_id IS NULL
    OR expected_current_email IS NULL
    OR requested_new_email IS NULL
    OR expected_current_email <> lower(btrim(expected_current_email))
    OR requested_new_email <> lower(btrim(requested_new_email))
    OR length(requested_new_email) NOT BETWEEN 3 AND 254
    OR expected_current_email = requested_new_email
    OR expected_practice_id IS NULL
    OR expected_session_token IS NULL
    OR expected_password_hash IS NULL
  THEN
    RAISE EXCEPTION 'Auth email change request is invalid';
  END IF;
  PERFORM 1
  FROM public."practices" practice
  WHERE practice."id" = expected_practice_id
    AND practice."isActive" = TRUE
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Auth email change authority changed';
  END IF;

  PERFORM 1
  FROM public."users" account
  WHERE account."id" = request_user_id
    AND account."email" = expected_current_email
    AND account."practiceId" = expected_practice_id
    AND account."passwordHash" = expected_password_hash
    AND account."role" = 'DOCTOR'
    AND account."products" @> ARRAY['TRANSCRIBE_MD']::"Product"[]
    AND account."isActive" = TRUE
    AND account."deactivatedAt" IS NULL
    AND account."suspendedAt" IS NULL
    AND account."softDeletedAt" IS NULL
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Auth email change authority changed';
  END IF;

  SELECT session."createdAt", session."expiresAt"
  INTO authority_session_created_at, authority_session_expires_at
  FROM public."user_sessions" session
  JOIN public."users" account ON account."id" = session."userId"
  WHERE session."userId" = request_user_id
    AND session."sessionToken" = expected_session_token
    AND session."createdAt" <= clock_timestamp()
    AND session."expiresAt" > clock_timestamp()
    AND (
      account."forceLogoutAt" IS NULL
      OR account."forceLogoutAt" < session."createdAt"
    )
  FOR UPDATE OF session;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Auth email change authority changed';
  END IF;

  UPDATE public."auth_tokens"
  SET "usedAt" = clock_timestamp()
  WHERE "userId" = request_user_id
    AND "purpose" = 'EMAIL_CHANGE'
    AND "usedAt" IS NULL;
  UPDATE public."auth_email_outbox"
  SET "status" = 'FAILED', "finishedAt" = clock_timestamp(),
      "claimedAt" = NULL, "leaseExpiresAt" = NULL, "claimToken" = NULL,
      "recipientEmail" = NULL, "lastErrorCode" = 'SUPERSEDED',
      "updatedAt" = clock_timestamp()
  WHERE "candidateUserId" = request_user_id
    AND "purpose" = 'EMAIL_CHANGE'
    AND "status" = 'PENDING';

  INSERT INTO public."auth_email_outbox" (
    "candidateUserId", "emailSha256", "sourceEmailSha256",
    "recipientEmail", "authorityPracticeId", "authoritySessionSha256",
    "authoritySessionCreatedAt", "authoritySessionExpiresAt",
    "purpose", "requestExpiresAt"
  ) VALUES (
    request_user_id,
    encode(digest(convert_to(requested_new_email, 'UTF8'), 'sha256'), 'hex'),
    encode(digest(convert_to(expected_current_email, 'UTF8'), 'sha256'), 'hex'),
    requested_new_email, expected_practice_id,
    encode(
      digest(convert_to(expected_session_token, 'UTF8'), 'sha256'),
      'hex'
    ),
    authority_session_created_at, authority_session_expires_at,
    'EMAIL_CHANGE',
    clock_timestamp() + INTERVAL '24 hours'
  ) RETURNING "id" INTO request_id;
  RETURN request_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_claim(claim_limit INTEGER)
RETURNS TABLE ("id" UUID, "claimToken" UUID)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
  IF claim_limit IS NULL OR claim_limit NOT BETWEEN 1 AND 100 THEN
    RAISE EXCEPTION 'Auth email claim limit is invalid';
  END IF;
  -- Once prepare has run, a crashed worker may already have handed the
  -- message to the provider. Treat an expired prepared lease as ambiguous,
  -- retire its bearer, and never auto-redeliver it.
  UPDATE public."auth_tokens" token
  SET "usedAt" = clock_timestamp()
  FROM public."auth_email_outbox" outbox
  WHERE outbox."status" = 'CLAIMED'
    AND outbox."leaseExpiresAt" <= clock_timestamp()
    AND outbox."attemptCount" > 0
    AND outbox."tokenId" = token."id"
    AND token."usedAt" IS NULL;

  UPDATE public."auth_email_outbox"
  SET "status" = 'AMBIGUOUS', "finishedAt" = clock_timestamp(),
      "claimedAt" = NULL, "leaseExpiresAt" = NULL, "claimToken" = NULL,
      "recipientEmail" = CASE WHEN "purpose" = 'EMAIL_CHANGE'
        THEN NULL ELSE "recipientEmail" END,
      "lastErrorCode" = 'LEASE_OUTCOME_AMBIGUOUS',
      "purgeAfter" = clock_timestamp() + INTERVAL '30 days',
      "updatedAt" = clock_timestamp()
  WHERE "status" = 'CLAIMED'
    AND "leaseExpiresAt" <= clock_timestamp()
    AND "attemptCount" > 0;

  -- Expired requests are never allowed to mint a fresh bearer after an
  -- outage. Retire any prepared token and minimize a pending destination.
  UPDATE public."auth_tokens" token
  SET "usedAt" = clock_timestamp()
  FROM public."auth_email_outbox" outbox
  WHERE outbox."status" IN ('PENDING', 'CLAIMED')
    AND outbox."requestExpiresAt" <= clock_timestamp()
    AND outbox."tokenId" = token."id"
    AND token."usedAt" IS NULL;

  UPDATE public."auth_email_outbox"
  SET "status" = 'FAILED', "finishedAt" = clock_timestamp(),
      "claimedAt" = NULL, "leaseExpiresAt" = NULL, "claimToken" = NULL,
      "recipientEmail" = CASE WHEN "purpose" = 'EMAIL_CHANGE'
        THEN NULL ELSE "recipientEmail" END,
      "lastErrorCode" = 'REQUEST_EXPIRED', "updatedAt" = clock_timestamp()
  WHERE "status" IN ('PENDING', 'CLAIMED')
    AND "requestExpiresAt" <= clock_timestamp();

  RETURN QUERY
  WITH candidates AS (
    SELECT outbox."id"
    FROM public."auth_email_outbox" outbox
    WHERE outbox."attemptCount" < 3
      AND outbox."requestExpiresAt" > clock_timestamp()
      AND (
        (outbox."status" = 'PENDING' AND outbox."availableAt" <= clock_timestamp())
        OR
        (outbox."status" = 'CLAIMED'
          AND outbox."leaseExpiresAt" <= clock_timestamp())
      )
    ORDER BY outbox."availableAt", outbox."createdAt", outbox."id"
    FOR UPDATE SKIP LOCKED
    LIMIT claim_limit
  )
  UPDATE public."auth_email_outbox" outbox
  SET "status" = 'CLAIMED',
      "claimedAt" = clock_timestamp(),
      "leaseExpiresAt" = clock_timestamp() + INTERVAL '2 minutes',
      "claimToken" = gen_random_uuid(),
      "lastErrorCode" = NULL,
      "updatedAt" = clock_timestamp()
  FROM candidates
  WHERE outbox."id" = candidates."id"
  RETURNING outbox."id", outbox."claimToken";
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_prepare_delivery(
  request_id UUID,
  expected_claim_token UUID,
  next_token_id TEXT,
  next_token_hash TEXT
)
RETURNS TABLE (
  "userId" TEXT,
  "email" TEXT,
  "name" TEXT,
  "tokenId" TEXT,
  "purpose" "AuthEmailPurpose"
)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  request_row RECORD;
  stored_candidate_hint TEXT;
  candidate_id_hint TEXT;
  email_hash_hint CHAR(64);
  authority_practice_hint TEXT;
  authority_session_hash_hint CHAR(64);
  authority_session_created_hint TIMESTAMPTZ(6);
  authority_session_expires_hint TIMESTAMPTZ(6);
  purpose_hint "AuthEmailPurpose";
  token_id_hint TEXT;
  change_authority_current BOOLEAN := TRUE;
  account_id TEXT;
  account_email TEXT;
  account_name TEXT;
  token_expiry TIMESTAMPTZ(6);
BEGIN
  -- Preserve the program-wide account lock order: user before outbox. The
  -- first read is only a routing hint; every value is re-read and validated
  -- after the canonical locks are held.
  SELECT outbox."candidateUserId", outbox."emailSha256",
    outbox."authorityPracticeId",
    outbox."authoritySessionSha256", outbox."authoritySessionCreatedAt",
    outbox."authoritySessionExpiresAt", outbox."purpose", outbox."tokenId"
  INTO stored_candidate_hint, email_hash_hint, authority_practice_hint,
    authority_session_hash_hint, authority_session_created_hint,
    authority_session_expires_hint, purpose_hint, token_id_hint
  FROM public."auth_email_outbox" outbox
  WHERE outbox."id" = request_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Auth email claim is not current';
  END IF;
  candidate_id_hint := stored_candidate_hint;
  IF candidate_id_hint IS NULL AND purpose_hint <> 'EMAIL_CHANGE' THEN
    -- This non-locking hash lookup is outside the request path. The current
    -- account is locked and the hash is revalidated below before any bearer
    -- can be minted or any destination can leave the database boundary.
    SELECT account."id" INTO candidate_id_hint
    FROM public."users" account
    WHERE encode(
      digest(convert_to(account."email", 'UTF8'), 'sha256'),
      'hex'
    ) = email_hash_hint
    ORDER BY account."id"
    LIMIT 1;
  END IF;
  IF authority_practice_hint IS NOT NULL THEN
    PERFORM 1
    FROM public."practices" practice
    WHERE practice."id" = authority_practice_hint
      AND practice."isActive" = TRUE
    FOR UPDATE;
    IF NOT FOUND THEN
      change_authority_current := FALSE;
    END IF;
  END IF;
  IF candidate_id_hint IS NOT NULL THEN
    PERFORM 1
    FROM public."users" account
    WHERE account."id" = candidate_id_hint
    FOR UPDATE;
  END IF;
  IF authority_session_hash_hint IS NOT NULL THEN
    PERFORM 1
    FROM public."user_sessions" session
    JOIN public."users" account ON account."id" = session."userId"
    WHERE session."userId" = candidate_id_hint
      AND encode(
        digest(convert_to(session."sessionToken", 'UTF8'), 'sha256'),
        'hex'
      ) = authority_session_hash_hint
      AND session."createdAt" = authority_session_created_hint
      AND session."expiresAt" = authority_session_expires_hint
      AND session."createdAt" <= clock_timestamp()
      AND session."expiresAt" > clock_timestamp()
      AND (
        account."forceLogoutAt" IS NULL
        OR account."forceLogoutAt" < session."createdAt"
      )
    FOR UPDATE OF session;
    IF NOT FOUND THEN
      change_authority_current := FALSE;
    END IF;
  END IF;

  -- All auth-email functions lock bearer rows before the outbox row. Parent
  -- authority locks (practice/user/session) are acquired first where present.
  -- This order prevents provider completion from deadlocking revocation.
  IF candidate_id_hint IS NOT NULL AND purpose_hint <> 'ACCOUNT_EXISTS' THEN
    PERFORM 1
    FROM public."auth_tokens" token
    WHERE token."userId" = candidate_id_hint
      AND token."purpose" = purpose_hint::TEXT::"AuthTokenPurpose"
      AND token."usedAt" IS NULL
    ORDER BY token."id"
    FOR UPDATE;
  END IF;
  IF token_id_hint IS NOT NULL THEN
    PERFORM 1
    FROM public."auth_tokens" token
    WHERE token."id" = token_id_hint
    FOR UPDATE;
  END IF;

  SELECT outbox.* INTO request_row
  FROM public."auth_email_outbox" outbox
  WHERE outbox."id" = request_id
  FOR UPDATE;
  IF NOT FOUND
    OR request_row."status" <> 'CLAIMED'
    OR request_row."claimToken" IS DISTINCT FROM expected_claim_token
    OR request_row."leaseExpiresAt" <= clock_timestamp()
    OR request_row."requestExpiresAt" <= clock_timestamp()
    OR request_row."attemptCount" <> 0
    OR request_row."candidateUserId" IS DISTINCT FROM stored_candidate_hint
    OR request_row."emailSha256" IS DISTINCT FROM email_hash_hint
    OR request_row."purpose" IS DISTINCT FROM purpose_hint
    OR request_row."authorityPracticeId"
      IS DISTINCT FROM authority_practice_hint
    OR request_row."authoritySessionSha256"
      IS DISTINCT FROM authority_session_hash_hint
    OR request_row."authoritySessionCreatedAt"
      IS DISTINCT FROM authority_session_created_hint
    OR request_row."authoritySessionExpiresAt"
      IS DISTINCT FROM authority_session_expires_hint
  THEN
    RAISE EXCEPTION 'Auth email claim is not current';
  END IF;

  IF request_row."purpose" <> 'ACCOUNT_EXISTS' AND (
    next_token_id IS NULL OR length(next_token_id) NOT BETWEEN 16 AND 128
    OR next_token_hash IS NULL OR next_token_hash !~ '^[0-9a-f]{64}$'
  ) THEN
    RAISE EXCEPTION 'Auth email token material is invalid';
  END IF;

  IF candidate_id_hint IS NOT NULL THEN
    SELECT account."id", account."email", account."name"
    INTO account_id, account_email, account_name
    FROM public."users" account
    WHERE account."id" = candidate_id_hint
      AND account."isActive" = TRUE
      AND account."deactivatedAt" IS NULL
      AND account."suspendedAt" IS NULL
      AND account."softDeletedAt" IS NULL
      AND encode(
        digest(convert_to(account."email", 'UTF8'), 'sha256'),
        'hex'
      ) = CASE
        WHEN request_row."purpose" = 'EMAIL_CHANGE'
          THEN request_row."sourceEmailSha256"
        ELSE request_row."emailSha256"
      END
      AND (
        request_row."purpose" <> 'EMAIL_VERIFICATION'
        OR account."emailVerified" IS NULL
      )
      AND (
        request_row."purpose" <> 'EMAIL_CHANGE'
        OR (
          change_authority_current
          AND account."practiceId" = request_row."authorityPracticeId"
          AND account."role" = 'DOCTOR'
          AND account."products" @> ARRAY['TRANSCRIBE_MD']::"Product"[]
          AND NOT EXISTS (
            SELECT 1 FROM public."users" conflict
            WHERE conflict."email" = request_row."recipientEmail"
              AND conflict."id" <> account."id"
          )
        )
      )
    FOR UPDATE;
  END IF;

  IF account_id IS NULL THEN
    UPDATE public."auth_tokens" token
    SET "usedAt" = clock_timestamp()
    WHERE token."id" = request_row."tokenId"
      AND token."usedAt" IS NULL;
    UPDATE public."auth_email_outbox" outbox
    SET "status" = 'NOOP', "finishedAt" = clock_timestamp(),
        "claimedAt" = NULL, "leaseExpiresAt" = NULL, "claimToken" = NULL,
        "recipientEmail" = CASE WHEN outbox."purpose" = 'EMAIL_CHANGE'
          THEN NULL ELSE outbox."recipientEmail" END,
        "lastErrorCode" = 'INELIGIBLE_NOOP',
        "purgeAfter" = clock_timestamp() + INTERVAL '1 day',
        "updatedAt" = clock_timestamp()
    WHERE outbox."id" = request_id;
    RETURN;
  END IF;

  IF request_row."purpose" <> 'ACCOUNT_EXISTS' THEN
    UPDATE public."auth_tokens" token
    SET "usedAt" = clock_timestamp()
    WHERE token."userId" = account_id
      AND token."purpose" = request_row."purpose"::TEXT::"AuthTokenPurpose"
      AND token."usedAt" IS NULL;

    token_expiry := LEAST(
      request_row."requestExpiresAt",
      CASE request_row."purpose"
        WHEN 'PASSWORD_RESET' THEN clock_timestamp() + INTERVAL '1 hour'
        WHEN 'EMAIL_CHANGE' THEN request_row."authoritySessionExpiresAt"
        ELSE clock_timestamp() + INTERVAL '24 hours'
      END
    );
    INSERT INTO public."auth_tokens" (
      "id", "userId", "purpose", "tokenHash", "expiresAt", "metadata"
    ) VALUES (
      next_token_id,
      account_id,
      request_row."purpose"::TEXT::"AuthTokenPurpose",
      next_token_hash,
      token_expiry,
      CASE request_row."purpose"
        WHEN 'EMAIL_CHANGE' THEN jsonb_build_object(
          'newEmail', request_row."recipientEmail",
          'oldEmail', account_email
        )
        ELSE jsonb_build_object('email', account_email)
      END
    );
  END IF;

  UPDATE public."auth_email_outbox" outbox
  SET "candidateUserId" = account_id,
      "attemptCount" = outbox."attemptCount" + 1,
      "tokenId" = CASE
        WHEN request_row."purpose" = 'ACCOUNT_EXISTS' THEN NULL
        ELSE next_token_id
      END,
      "updatedAt" = clock_timestamp()
  WHERE outbox."id" = request_id;

  RETURN QUERY SELECT account_id,
    CASE WHEN request_row."purpose" = 'EMAIL_CHANGE'
      THEN request_row."recipientEmail" ELSE account_email END,
    account_name,
    CASE WHEN request_row."purpose" = 'ACCOUNT_EXISTS'
      THEN NULL::TEXT ELSE next_token_id END,
    request_row."purpose";
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_finish_delivery(
  request_id UUID,
  expected_claim_token UUID,
  expected_token_id TEXT,
  delivered BOOLEAN,
  fixed_error_code TEXT DEFAULT NULL,
  provider_receipt_sha256 TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  request_row RECORD;
BEGIN
  IF delivered IS NULL THEN
    RAISE EXCEPTION 'Auth email completion outcome is invalid';
  END IF;
  IF delivered = FALSE AND (
    fixed_error_code IS NULL OR fixed_error_code !~ '^[A-Z0-9_]{1,64}$'
    OR provider_receipt_sha256 IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Auth email failure code is invalid';
  END IF;
  IF delivered = TRUE AND (
    provider_receipt_sha256 IS NULL
    OR provider_receipt_sha256 !~ '^[0-9a-f]{64}$'
    OR fixed_error_code IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Auth email provider receipt is required';
  END IF;

  -- Every path that can touch both records takes the token lock first.
  -- A missing token is still revalidated against the locked outbox below.
  IF expected_token_id IS NOT NULL THEN
    PERFORM 1
    FROM public."auth_tokens" token
    WHERE token."id" = expected_token_id
    FOR UPDATE;
  END IF;

  SELECT * INTO request_row
  FROM public."auth_email_outbox"
  WHERE "id" = request_id
  FOR UPDATE;

  -- Completion retries are idempotent only when every immutable completion
  -- attribute matches. A newer claim or token can never be completed by an
  -- older worker.
  IF FOUND AND delivered = TRUE
    AND request_row."status" = 'DELIVERED'
    AND request_row."tokenId" IS NOT DISTINCT FROM expected_token_id
    AND request_row."providerReceiptSha256" = provider_receipt_sha256
  THEN
    RETURN;
  END IF;
  IF FOUND AND delivered = FALSE
    AND request_row."status" = 'AMBIGUOUS'
    AND request_row."tokenId" IS NOT DISTINCT FROM expected_token_id
    AND request_row."lastErrorCode" = fixed_error_code
  THEN
    RETURN;
  END IF;

  IF NOT FOUND OR request_row."status" <> 'CLAIMED'
    OR request_row."claimToken" IS DISTINCT FROM expected_claim_token
    OR request_row."leaseExpiresAt" <= clock_timestamp()
    OR request_row."tokenId" IS DISTINCT FROM expected_token_id
  THEN
    RAISE EXCEPTION 'Auth email completion is not current';
  END IF;

  IF delivered THEN
    UPDATE public."auth_email_outbox"
    SET "status" = 'DELIVERED', "finishedAt" = clock_timestamp(),
        "claimedAt" = NULL, "leaseExpiresAt" = NULL, "claimToken" = NULL,
        "recipientEmail" = CASE WHEN "purpose" = 'EMAIL_CHANGE'
          THEN NULL ELSE "recipientEmail" END,
        "lastErrorCode" = NULL,
        "providerReceiptSha256" = provider_receipt_sha256,
        "updatedAt" = clock_timestamp()
    WHERE "id" = request_id;
    RETURN;
  END IF;

  UPDATE public."auth_tokens"
  SET "usedAt" = clock_timestamp()
  WHERE "id" = expected_token_id AND "usedAt" IS NULL;

  UPDATE public."auth_email_outbox"
  SET "status" = 'AMBIGUOUS',
      "claimedAt" = NULL,
      "leaseExpiresAt" = NULL,
      "claimToken" = NULL,
      "recipientEmail" = CASE WHEN "purpose" = 'EMAIL_CHANGE'
        THEN NULL ELSE "recipientEmail" END,
      "finishedAt" = clock_timestamp(),
      "lastErrorCode" = fixed_error_code,
      "purgeAfter" = clock_timestamp() + INTERVAL '30 days',
      "updatedAt" = clock_timestamp()
  WHERE "id" = request_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_purge(purge_limit INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  outbox_purged INTEGER;
  token_purged INTEGER;
BEGIN
  IF purge_limit IS NULL OR purge_limit NOT BETWEEN 1 AND 1000 THEN
    RAISE EXCEPTION 'Auth email purge limit is invalid';
  END IF;
  -- Token deletion can update an outbox foreign key through ON DELETE SET
  -- NULL, so purge tokens first to retain the global token-before-outbox
  -- lock order.
  WITH candidates AS (
    SELECT token."id"
    FROM public."auth_tokens" token
    WHERE (
        token."usedAt" < clock_timestamp() - INTERVAL '7 days'
        OR
        (token."usedAt" IS NULL
          AND token."expiresAt" < clock_timestamp() - INTERVAL '7 days')
      )
    ORDER BY COALESCE(token."usedAt", token."expiresAt"), token."id"
    FOR UPDATE SKIP LOCKED
    LIMIT purge_limit
  )
  DELETE FROM public."auth_tokens" token
  USING candidates
  WHERE token."id" = candidates."id";
  GET DIAGNOSTICS token_purged = ROW_COUNT;

  WITH candidates AS (
    SELECT outbox."id"
    FROM public."auth_email_outbox" outbox
    WHERE outbox."status" IN ('DELIVERED', 'AMBIGUOUS', 'NOOP', 'FAILED')
      AND outbox."purgeAfter" <= clock_timestamp()
    ORDER BY outbox."purgeAfter", outbox."id"
    FOR UPDATE SKIP LOCKED
    LIMIT purge_limit
  )
  DELETE FROM public."auth_email_outbox" outbox
  USING candidates
  WHERE outbox."id" = candidates."id";
  GET DIAGNOSTICS outbox_purged = ROW_COUNT;
  RETURN outbox_purged + token_purged;
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_cancel_on_user_security_change()
RETURNS TRIGGER
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  lifecycle_ineligible BOOLEAN;
  password_changed BOOLEAN;
  email_changed BOOLEAN;
  verification_completed BOOLEAN;
  email_change_authority_changed BOOLEAN;
BEGIN
  lifecycle_ineligible := NEW."isActive" = FALSE
    OR NEW."deactivatedAt" IS NOT NULL
    OR NEW."suspendedAt" IS NOT NULL
    OR NEW."softDeletedAt" IS NOT NULL;
  password_changed := NEW."passwordHash" IS DISTINCT FROM OLD."passwordHash";
  email_changed := NEW."email" IS DISTINCT FROM OLD."email";
  verification_completed := OLD."emailVerified" IS NULL
    AND NEW."emailVerified" IS NOT NULL;
  email_change_authority_changed :=
    NEW."practiceId" IS DISTINCT FROM OLD."practiceId"
    OR NEW."role" IS DISTINCT FROM OLD."role"
    OR NEW."products" IS DISTINCT FROM OLD."products"
    OR NEW."forceLogoutAt" IS DISTINCT FROM OLD."forceLogoutAt"
    OR NEW."mfaEnabled" IS DISTINCT FROM OLD."mfaEnabled"
    OR NEW."mfaSecret" IS DISTINCT FROM OLD."mfaSecret"
    OR NEW."mfaVerifiedAt" IS DISTINCT FROM OLD."mfaVerifiedAt"
    OR NEW."mfaBackupCodes" IS DISTINCT FROM OLD."mfaBackupCodes";

  IF lifecycle_ineligible OR password_changed OR email_changed
    OR verification_completed OR email_change_authority_changed
  THEN
    UPDATE public."auth_tokens" token
    SET "usedAt" = clock_timestamp()
    WHERE token."userId" = NEW."id"
      AND token."usedAt" IS NULL
      AND (
        lifecycle_ineligible
        OR email_changed
        OR (password_changed AND token."purpose" IN (
          'PASSWORD_RESET', 'EMAIL_CHANGE'
        ))
        OR (verification_completed
          AND token."purpose" = 'EMAIL_VERIFICATION')
        OR (email_change_authority_changed
          AND token."purpose" = 'EMAIL_CHANGE')
      );

    UPDATE public."auth_email_outbox" outbox
    SET "status" = 'FAILED', "finishedAt" = clock_timestamp(),
        "claimedAt" = NULL, "leaseExpiresAt" = NULL,
        "claimToken" = NULL,
        "recipientEmail" = CASE WHEN outbox."purpose" = 'EMAIL_CHANGE'
          THEN NULL ELSE outbox."recipientEmail" END,
        "lastErrorCode" = 'ACCOUNT_SECURITY_STATE_CHANGED',
        "updatedAt" = clock_timestamp()
    WHERE outbox."candidateUserId" = NEW."id"
      AND outbox."status" IN ('PENDING', 'CLAIMED')
      AND (
        lifecycle_ineligible
        OR email_changed
        OR (password_changed AND outbox."purpose" IN (
          'PASSWORD_RESET', 'EMAIL_CHANGE'
        ))
        OR (verification_completed
          AND outbox."purpose" = 'EMAIL_VERIFICATION')
        OR (email_change_authority_changed
          AND outbox."purpose" = 'EMAIL_CHANGE')
      );
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_cancel_on_session_change()
RETURNS TRIGGER
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  prior_session_hash CHAR(64);
BEGIN
  prior_session_hash := encode(
    digest(convert_to(OLD."sessionToken", 'UTF8'), 'sha256'),
    'hex'
  );
  UPDATE public."auth_tokens" token
  SET "usedAt" = clock_timestamp()
  FROM public."auth_email_outbox" outbox
  WHERE outbox."candidateUserId" = OLD."userId"
    AND outbox."purpose" = 'EMAIL_CHANGE'
    AND outbox."authoritySessionSha256" = prior_session_hash
    AND outbox."tokenId" = token."id"
    AND token."usedAt" IS NULL;

  UPDATE public."auth_email_outbox" outbox
  SET "status" = 'FAILED', "finishedAt" = clock_timestamp(),
      "claimedAt" = NULL, "leaseExpiresAt" = NULL,
      "claimToken" = NULL, "recipientEmail" = NULL,
      "lastErrorCode" = 'SESSION_AUTHORITY_CHANGED',
      "updatedAt" = clock_timestamp()
  WHERE outbox."candidateUserId" = OLD."userId"
    AND outbox."purpose" = 'EMAIL_CHANGE'
    AND outbox."authoritySessionSha256" = prior_session_hash
    AND outbox."status" IN ('PENDING', 'CLAIMED');
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_cancel_on_practice_change()
RETURNS TRIGGER
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
  IF NEW."isActive" IS DISTINCT FROM OLD."isActive" THEN
    UPDATE public."auth_tokens" token
    SET "usedAt" = clock_timestamp()
    FROM public."auth_email_outbox" outbox
    WHERE outbox."authorityPracticeId" = NEW."id"
      AND outbox."purpose" = 'EMAIL_CHANGE'
      AND outbox."tokenId" = token."id"
      AND token."usedAt" IS NULL;

    UPDATE public."auth_email_outbox" outbox
    SET "status" = 'FAILED', "finishedAt" = clock_timestamp(),
        "claimedAt" = NULL, "leaseExpiresAt" = NULL,
        "claimToken" = NULL, "recipientEmail" = NULL,
        "lastErrorCode" = 'PRACTICE_AUTHORITY_CHANGED',
        "updatedAt" = clock_timestamp()
    WHERE outbox."authorityPracticeId" = NEW."id"
      AND outbox."purpose" = 'EMAIL_CHANGE'
      AND outbox."status" IN ('PENDING', 'CLAIMED');
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.auth_email_health()
RETURNS TABLE (
  "pending" BIGINT,
  "claimed" BIGINT,
  "ambiguous" BIGINT,
  "oldestPendingSeconds" BIGINT
)
LANGUAGE SQL STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  SELECT
    count(*) FILTER (WHERE "status" = 'PENDING') AS "pending",
    count(*) FILTER (WHERE "status" = 'CLAIMED') AS "claimed",
    count(*) FILTER (WHERE "status" = 'AMBIGUOUS') AS "ambiguous",
    COALESCE(
      extract(epoch FROM (
        statement_timestamp() - min("createdAt")
          FILTER (WHERE "status" = 'PENDING')
      ))::BIGINT,
      0
    ) AS "oldestPendingSeconds"
  FROM public."auth_email_outbox";
$$;

CREATE TRIGGER auth_email_cancel_on_user_security_change
AFTER UPDATE OF "passwordHash", "email", "emailVerified", "isActive",
  "deactivatedAt", "suspendedAt", "softDeletedAt", "practiceId", "role",
  "products", "forceLogoutAt", "mfaEnabled", "mfaSecret", "mfaVerifiedAt",
  "mfaBackupCodes"
ON public."users"
FOR EACH ROW
EXECUTE FUNCTION public.auth_email_cancel_on_user_security_change();

CREATE TRIGGER auth_email_cancel_on_session_delete
AFTER DELETE
ON public."user_sessions"
FOR EACH ROW
EXECUTE FUNCTION public.auth_email_cancel_on_session_change();

CREATE TRIGGER auth_email_cancel_on_session_update
AFTER UPDATE OF "sessionToken", "userId", "createdAt", "expiresAt"
ON public."user_sessions"
FOR EACH ROW
EXECUTE FUNCTION public.auth_email_cancel_on_session_change();

CREATE TRIGGER auth_email_cancel_on_practice_change
AFTER UPDATE OF "isActive"
ON public."practices"
FOR EACH ROW
EXECUTE FUNCTION public.auth_email_cancel_on_practice_change();

REVOKE ALL ON TABLE "auth_email_outbox" FROM PUBLIC;
REVOKE ALL ON TABLE "auth_email_outbox" FROM quillmd_runtime;
REVOKE ALL ON TABLE "auth_email_outbox" FROM quillmd_auth_email_dispatcher;

REVOKE ALL ON FUNCTION public.auth_email_enqueue(
  TEXT, "AuthEmailPurpose"
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_enqueue_change(
  TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_claim(INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_prepare_delivery(
  UUID, UUID, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_finish_delivery(
  UUID, UUID, TEXT, BOOLEAN, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_purge(INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_health() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_cancel_on_user_security_change()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_cancel_on_session_change()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION public.auth_email_cancel_on_practice_change()
  FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO quillmd_runtime,
  quillmd_auth_email_dispatcher;
GRANT USAGE ON TYPE "AuthEmailPurpose", "AuthEmailOutboxStatus"
  TO quillmd_runtime, quillmd_auth_email_dispatcher;
GRANT EXECUTE ON FUNCTION public.auth_email_enqueue(
  TEXT, "AuthEmailPurpose"
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION public.auth_email_enqueue_change(
  TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION public.auth_email_claim(INTEGER),
  public.auth_email_prepare_delivery(UUID, UUID, TEXT, TEXT),
  public.auth_email_finish_delivery(UUID, UUID, TEXT, BOOLEAN, TEXT, TEXT),
  public.auth_email_purge(INTEGER),
  public.auth_email_health()
  TO quillmd_auth_email_dispatcher;

COMMIT;
