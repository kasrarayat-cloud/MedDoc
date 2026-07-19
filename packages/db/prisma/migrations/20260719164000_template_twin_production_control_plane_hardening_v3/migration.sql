-- Template Twin production control-plane hardening v3.
--
-- Additive correction after exact-head review of v2. Keep the release-control
-- lock order, close caller-temporary-schema resolution in every privileged
-- function, make SUPER_ADMIN entitlement loss an atomic authority revocation,
-- and remove unnecessary runtime reads of raw control-plane evidence.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

SELECT pg_advisory_xact_lock(73119, 20260719);
SELECT "id" FROM "template_twin_rollout_controls"
WHERE "id" = 'global' FOR UPDATE;

DO $$
BEGIN
  IF (
    SELECT COUNT(*) FROM pg_roles
    WHERE rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher'
    )
      AND rolcanlogin = FALSE AND rolsuper = FALSE
      AND rolcreatedb = FALSE AND rolcreaterole = FALSE
      AND rolinherit = FALSE AND rolreplication = FALSE
      AND rolbypassrls = FALSE
  ) <> 4 THEN
    RAISE EXCEPTION 'Template Twin v3 requires the reviewed database role boundary';
  END IF;
END;
$$;

-- PostgreSQL implicitly searches a caller's temporary schema before a
-- function's configured path unless pg_temp is listed explicitly. Put it
-- last so caller-owned temporary relations can never shadow public evidence.
ALTER FUNCTION public.template_twin_assert_release_audit_delivery()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_assert_release_control_coupling()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_assert_rollback_fence_coupling()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_check_release_audit_delivery()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_check_rollback_audit_log_delivery()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_check_rollback_outbox_delivery()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_current_runtime_release()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_guard_checkpoint_pass()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_guard_release_approval_insert()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_guard_release_candidate_history()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_guard_release_checkpoint_history()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_issue_metric_receipt(
  TEXT, TEXT, UUID, UUID, TEXT, BIGINT, BIGINT, INTEGER,
  BIGINT, BIGINT, JSONB, BIGINT, CHAR(64)
) SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_issue_release_action_receipt(
  TEXT, TEXT, UUID, UUID, TEXT, TEXT, TEXT, TEXT
) SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_issue_release_capability(
  UUID, CHAR(64), UUID, BIGINT, BIGINT
) SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_mark_release_coupling_dirty()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_register_runtime_attestation(
  TEXT, TEXT, UUID, CHAR(64), TEXT, TEXT, CHAR(40), TEXT,
  BIGINT, BIGINT, CHAR(64)
) SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_release_approvals_are_current(
  UUID, CHAR(64)
) SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_release_runtime_ready(UUID, CHAR(64))
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_revoke_authority_on_user_lifecycle()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_revoke_release_authority(
  UUID, TEXT, TEXT, TEXT, TEXT
) SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_validate_release_freeze_manifest()
  SET search_path TO pg_catalog, public, pg_temp;
ALTER FUNCTION public.template_twin_verify_release_actor(TEXT, TEXT)
  SET search_path TO pg_catalog, public, pg_temp;

-- The same shadowing rule applies to invoker trigger functions: a caller can
-- otherwise make an unqualified evidence-table read resolve to its own temp
-- relation before a guard executes. Harden the complete installed Template
-- Twin function surface, including the accepted intake/lineage/rollback stack.
DO $safe_function_paths$
DECLARE
  target RECORD;
BEGIN
  FOR target IN
    SELECT namespace.nspname, procedure.proname,
      pg_get_function_identity_arguments(procedure.oid) AS identity_arguments
    FROM pg_proc procedure
    JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
    WHERE namespace.nspname = 'public'
      AND procedure.proname LIKE 'template_twin_%'
      AND procedure.prokind = 'f'
    ORDER BY procedure.oid
  LOOP
    EXECUTE format(
      'ALTER FUNCTION %I.%I(%s) SET search_path TO pg_catalog, public, pg_temp',
      target.nspname, target.proname, target.identity_arguments
    );
  END LOOP;
END;
$safe_function_paths$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_proc procedure
    JOIN pg_namespace namespace ON namespace.oid = procedure.pronamespace
    WHERE namespace.nspname = 'public'
      AND procedure.proname LIKE 'template_twin_%'
      AND procedure.prokind = 'f'
      AND NOT (
        COALESCE(procedure.proconfig, ARRAY[]::TEXT[])
          @> ARRAY['search_path=pg_catalog, public, pg_temp']::TEXT[]
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin privileged function search paths are incomplete';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION public.template_twin_revoke_authority_on_user_lifecycle()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  assignment RECORD;
  lifecycle_change_id TEXT;
BEGIN
  IF (
    NEW."isActive" = FALSE OR NEW."deactivatedAt" IS NOT NULL
    OR NEW."suspendedAt" IS NOT NULL OR NEW."softDeletedAt" IS NOT NULL
    OR NEW."mfaEnabled" = FALSE OR NEW."mfaVerifiedAt" IS NULL
    OR NOT ('SUPER_ADMIN'::public."Product" = ANY(NEW."products"))
    OR NEW."forceLogoutAt" IS DISTINCT FROM OLD."forceLogoutAt"
  ) THEN
    lifecycle_change_id := 'USER_LIFECYCLE_' || upper(substr(md5(
      txid_current()::TEXT || ':' || OLD."id"
    ), 1, 24));
    FOR assignment IN
      SELECT authority."id"
      FROM public."template_twin_release_authorities" authority
      WHERE authority."userId" = OLD."id"
        AND authority."revokedAt" IS NULL
      ORDER BY authority."id"
    LOOP
      PERFORM public.template_twin_revoke_release_authority(
        assignment."id", NULL, NULL, lifecycle_change_id,
        'AUTHORITY_USER_LIFECYCLE'
      );
    END LOOP;
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.template_twin_revoke_authority_on_user_lifecycle()
  FROM PUBLIC;

DROP TRIGGER template_twin_user_lifecycle_authority_revoke ON "users";
DROP TRIGGER aaa_template_twin_user_lifecycle_statement_lock ON "users";
CREATE TRIGGER aaa_template_twin_user_lifecycle_statement_lock
BEFORE UPDATE OF "isActive", "deactivatedAt", "suspendedAt", "softDeletedAt",
  "mfaEnabled", "mfaVerifiedAt", "products", "forceLogoutAt" ON "users"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_practice_release_statement();
CREATE TRIGGER template_twin_user_lifecycle_authority_revoke
BEFORE UPDATE OF "isActive", "deactivatedAt", "suspendedAt", "softDeletedAt",
  "mfaEnabled", "mfaVerifiedAt", "products", "forceLogoutAt" ON "users"
FOR EACH ROW EXECUTE FUNCTION template_twin_revoke_authority_on_user_lifecycle();

-- The dedicated HTTP control process must validate the signed-cookie claim
-- without receiving the ordinary runtime role or any ability to enumerate,
-- mint, update, or delete sessions. Return only the exact matching live row.
CREATE OR REPLACE FUNCTION public.template_twin_verify_release_admin_session(
  actor_user_id TEXT,
  actor_session_token TEXT
)
RETURNS TABLE (
  "userId" TEXT,
  "email" TEXT,
  "practiceId" TEXT,
  "role" TEXT,
  "sessionCreatedAt" TIMESTAMPTZ,
  "sessionExpiresAt" TIMESTAMPTZ,
  "mfaVerifiedAt" TIMESTAMPTZ,
  "sessionSha256" TEXT
)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  SELECT account."id", account."email", account."practiceId",
    account."role"::TEXT, session."createdAt", session."expiresAt",
    account."mfaVerifiedAt",
    encode(digest(convert_to(session."sessionToken", 'UTF8'), 'sha256'), 'hex')
  FROM public."users" account
  JOIN public."user_sessions" session ON session."userId" = account."id"
  WHERE actor_user_id IS NOT NULL
    AND actor_session_token IS NOT NULL
    AND length(actor_session_token) BETWEEN 16 AND 512
    AND account."id" = actor_user_id
    AND session."sessionToken" = actor_session_token
    AND account."isActive" = TRUE
    AND account."deactivatedAt" IS NULL
    AND account."suspendedAt" IS NULL
    AND account."softDeletedAt" IS NULL
    AND account."mfaEnabled" = TRUE
    AND account."mfaVerifiedAt" IS NOT NULL
    AND 'SUPER_ADMIN'::public."Product" = ANY(account."products")
    AND session."createdAt" <= clock_timestamp()
    AND session."createdAt" > clock_timestamp() - INTERVAL '12 hours'
    AND session."expiresAt" > clock_timestamp()
    AND (
      account."forceLogoutAt" IS NULL
      OR session."createdAt" > account."forceLogoutAt"
    )
  FOR SHARE OF account, session;
$$;
REVOKE ALL ON FUNCTION public.template_twin_verify_release_admin_session(
  TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.template_twin_verify_release_admin_session(
  TEXT, TEXT
) TO quillmd_release_control;

-- Revoking a runtime verification key changes live readiness just as surely
-- as changing a runtime requirement. It must therefore participate in the
-- same deferred coupling scan. A key cannot be revoked while exposure stays
-- enabled; release revocation/disable and key revocation must be ordered or
-- performed atomically.
DROP TRIGGER IF EXISTS template_twin_release_coupling_dirty
  ON "template_twin_release_attestation_keys";
CREATE TRIGGER template_twin_release_coupling_dirty
AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE
  ON "template_twin_release_attestation_keys"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_mark_release_coupling_dirty();

DROP TRIGGER IF EXISTS template_twin_release_attestation_key_coupling_guard
  ON "template_twin_release_attestation_keys";
CREATE CONSTRAINT TRIGGER template_twin_release_attestation_key_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_release_attestation_keys"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();

-- The runtime consumes only the narrow SECURITY DEFINER release view and
-- registration function. Raw human, metric, and capability evidence remains
-- private to release control.
REVOKE SELECT ON
  "template_twin_release_candidates",
  "template_twin_release_authorities",
  "template_twin_release_practices",
  "template_twin_release_approval_decisions",
  "template_twin_release_checkpoints",
  "template_twin_release_metric_snapshots",
  "template_twin_release_capabilities",
  "template_twin_release_metric_receipts",
  "template_twin_release_action_receipts",
  "template_twin_release_coupling_receipts",
  "template_twin_release_runtime_requirements",
  "template_twin_release_runtime_attestations",
  "template_twin_release_attestation_keys"
FROM quillmd_runtime;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM
  quillmd_runtime, quillmd_release_control, quillmd_release_security,
  quillmd_audit_dispatcher;

COMMIT;
