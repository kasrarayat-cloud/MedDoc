-- Expand-only transition for one-current auth-token linearization.
--
-- A plain CREATE UNIQUE INDEX on this populated table would hold a write-
-- blocking table lock for the entire build. Prisma migrate deploy therefore
-- installs only a short-lock transition trigger. The separately reviewed
-- auth-token-linearization online operator deterministically retires legacy
-- duplicates in bounded batches, builds the final partial unique index with
-- CREATE UNIQUE INDEX CONCURRENTLY outside a transaction, verifies pg_index,
-- and removes this trigger only after the final invariant is valid.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.auth_tokens_guard_one_unused_transition()
RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
BEGIN
  IF NEW."usedAt" IS NULL THEN
    -- At REPEATABLE READ/SERIALIZABLE, a transaction that began before an
    -- opposing writer committed can retain a stale snapshot after waiting on
    -- the advisory lock. Until the final unique index is valid, fail closed
    -- unless PostgreSQL can take the fresh per-command READ COMMITTED snapshot
    -- used by the post-lock existence check.
    IF current_setting('transaction_isolation') <> 'read committed' THEN
      RAISE EXCEPTION USING
        ERRCODE = '25000',
        MESSAGE = 'Unused authentication-token writes require read committed isolation during online linearization';
    END IF;
    -- Serialize every writer for the exact authority key while the concurrent
    -- index is absent. The fixed salt separates this lock namespace from
    -- application and migration locks elsewhere in the release.
    PERFORM pg_advisory_xact_lock(hashtextextended(
      NEW."userId" || E'\x1f' || NEW."purpose"::TEXT,
      2026072015
    ));
    IF EXISTS (
      SELECT 1
      FROM public."auth_tokens" current_token
      WHERE current_token."userId" = NEW."userId"
        AND current_token."purpose" = NEW."purpose"
        AND current_token."usedAt" IS NULL
        AND current_token."id" IS DISTINCT FROM NEW."id"
    ) THEN
      RAISE EXCEPTION USING
        ERRCODE = '23505',
        CONSTRAINT = 'auth_tokens_one_unused_per_user_purpose',
        MESSAGE = 'Only one unused authentication token is permitted';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.auth_tokens_guard_one_unused_transition()
  FROM PUBLIC;

DROP TRIGGER IF EXISTS aaa_auth_tokens_one_unused_transition
  ON public."auth_tokens";
CREATE TRIGGER aaa_auth_tokens_one_unused_transition
BEFORE INSERT OR UPDATE OF "userId", "purpose", "usedAt"
ON public."auth_tokens"
FOR EACH ROW
EXECUTE FUNCTION public.auth_tokens_guard_one_unused_transition();

COMMIT;
