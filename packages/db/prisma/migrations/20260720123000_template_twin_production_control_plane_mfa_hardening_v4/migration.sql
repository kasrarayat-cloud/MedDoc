-- Template Twin production control-plane MFA hardening v4.
--
-- Additive correction after the complete-MFA boundary was made canonical in
-- the application. Release authority now requires all four durable database
-- facts: enabled MFA, a non-null/non-blank secret, a non-future verification
-- timestamp, and Product.SUPER_ADMIN. Existing evidence remains immutable;
-- stale live authority is revoked through the audited v2 revocation path.
-- Non-blank checks remove the explicit ECMAScript String.trim whitespace set
-- so database admission is identical to the canonical application predicate.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

-- Preserve the production control-plane lock order while replacing the actor
-- predicates and reconciling authority that predates the complete-MFA rule.
SELECT pg_advisory_xact_lock(73119, 20260719);
SELECT "id" FROM "template_twin_rollout_controls"
WHERE "id" = 'global' FOR UPDATE;

-- Re-establish the complete cluster-role precondition at this data-bearing
-- migration boundary. Exact direct login membership is not enough: if a
-- trusted NOLOGIN group is itself a member of another role, its dispatcher or
-- control login inherits that nested authority. The only permitted edges that
-- touch a trusted login or boundary are the three expected login -> boundary
-- memberships, without ADMIN OPTION. No other role may be a member of a
-- trusted LOGIN role because that would confer the dispatcher's authority.
-- The separately provisioned release-security login is an exact optional
-- lifecycle state: it may be absent, or it must have its sole exact edge.
-- PostgreSQL 16 records direct ownership, ACL, default-ACL, policy, and other
-- role-to-object dependencies in pg_shdepend. Role and database settings live
-- separately in pg_db_role_setting/rolconfig. A trusted LOGIN must have none;
-- permissions belong only on its reviewed NOLOGIN boundary.
CREATE OR REPLACE FUNCTION pg_temp.quillmd_login_has_direct_authority(
  principal_oid OID
)
RETURNS BOOLEAN LANGUAGE sql STABLE
SET search_path = pg_catalog
AS $direct_authority$
  SELECT EXISTS (
    SELECT 1 FROM pg_catalog.pg_shdepend dependency
    WHERE dependency.refclassid =
        'pg_catalog.pg_authid'::pg_catalog.regclass
      AND dependency.refobjid = principal_oid
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_db_role_setting setting
    WHERE setting.setrole = principal_oid
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles role
    WHERE role.oid = principal_oid AND role.rolconfig IS NOT NULL
  );
$direct_authority$;

DO $$
BEGIN
  IF (
    SELECT COUNT(*) FROM pg_catalog.pg_roles
    WHERE rolname IN (
      'quillmd_runtime', 'quillmd_release_control',
      'quillmd_release_security', 'quillmd_audit_dispatcher'
    )
      AND rolcanlogin = FALSE AND rolsuper = FALSE
      AND rolcreatedb = FALSE AND rolcreaterole = FALSE
      AND rolinherit = FALSE AND rolreplication = FALSE
      AND rolbypassrls = FALSE AND rolconnlimit = -1
      AND rolvaliduntil IS NULL AND rolconfig IS NULL
  ) <> 4 OR (
    SELECT COUNT(*) FROM pg_catalog.pg_roles
    WHERE rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_audit_dispatcher'
    )
      AND rolcanlogin = TRUE AND rolsuper = FALSE
      AND rolcreatedb = FALSE AND rolcreaterole = FALSE
      AND rolinherit = TRUE AND rolreplication = FALSE
      AND rolbypassrls = FALSE AND rolconnlimit = -1
      AND rolvaliduntil IS NULL
  ) <> 3 OR (
    SELECT COUNT(*) FROM pg_catalog.pg_roles
    WHERE rolname = 'meddoc_release_security'
      AND rolcanlogin = TRUE AND rolsuper = FALSE
      AND rolcreatedb = FALSE AND rolcreaterole = FALSE
      AND rolinherit = TRUE AND rolreplication = FALSE
      AND rolbypassrls = FALSE AND rolconnlimit = -1
      AND rolvaliduntil IS NULL
  ) <> (
    SELECT COUNT(*) FROM pg_catalog.pg_roles
    WHERE rolname = 'meddoc_release_security'
  ) OR EXISTS (
    SELECT 1
    FROM (
      VALUES
        ('meddoc_runtime', 'quillmd_runtime'),
        ('meddoc_release_control', 'quillmd_release_control'),
        ('meddoc_audit_dispatcher', 'quillmd_audit_dispatcher')
    ) AS expected(member_name, boundary_name)
    LEFT JOIN pg_catalog.pg_roles member_role
      ON member_role.rolname = expected.member_name
    LEFT JOIN pg_catalog.pg_roles boundary_role
      ON boundary_role.rolname = expected.boundary_name
    WHERE (
      SELECT COUNT(*)
      FROM pg_catalog.pg_auth_members membership
      JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = membership.grantor
      WHERE membership.member = member_role.oid
        AND membership.roleid = boundary_role.oid
        AND membership.admin_option = FALSE
        AND membership.inherit_option = TRUE
        AND membership.set_option = FALSE
        AND grantor.rolsuper = TRUE
    ) <> 1
  ) OR (
    EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname = 'meddoc_release_security'
    ) AND (
      SELECT COUNT(*)
      FROM pg_catalog.pg_auth_members membership
      JOIN pg_catalog.pg_roles member_role
        ON member_role.oid = membership.member
      JOIN pg_catalog.pg_roles granted_role
        ON granted_role.oid = membership.roleid
      JOIN pg_catalog.pg_roles grantor
        ON grantor.oid = membership.grantor
      WHERE member_role.rolname = 'meddoc_release_security'
        AND granted_role.rolname = 'quillmd_release_security'
        AND membership.admin_option = FALSE
        AND membership.inherit_option = TRUE
        AND membership.set_option = FALSE
        AND grantor.rolsuper = TRUE
    ) <> 1
  ) OR EXISTS (
    SELECT 1
    FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role
      ON member_role.oid = membership.member
    JOIN pg_catalog.pg_roles granted_role
      ON granted_role.oid = membership.roleid
    JOIN pg_catalog.pg_roles grantor
      ON grantor.oid = membership.grantor
    WHERE (
      member_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher', 'quillmd_runtime',
        'quillmd_release_control', 'quillmd_release_security',
        'quillmd_audit_dispatcher'
      ) OR granted_role.rolname IN (
        'meddoc_runtime', 'meddoc_release_control',
        'meddoc_release_security', 'meddoc_audit_dispatcher',
        'quillmd_runtime', 'quillmd_release_control',
        'quillmd_release_security', 'quillmd_audit_dispatcher'
      )
    ) AND (
      membership.admin_option = TRUE
      OR membership.inherit_option = FALSE
      OR membership.set_option = TRUE
      OR grantor.rolsuper = FALSE OR NOT (
        (member_role.rolname = 'meddoc_runtime'
          AND granted_role.rolname = 'quillmd_runtime')
        OR (member_role.rolname = 'meddoc_release_control'
          AND granted_role.rolname = 'quillmd_release_control')
        OR (member_role.rolname = 'meddoc_audit_dispatcher'
          AND granted_role.rolname = 'quillmd_audit_dispatcher')
        OR (member_role.rolname = 'meddoc_release_security'
          AND granted_role.rolname = 'quillmd_release_security')
      )
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles login_role
    WHERE login_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control',
      'meddoc_release_security', 'meddoc_audit_dispatcher'
    ) AND pg_temp.quillmd_login_has_direct_authority(login_role.oid)
  ) THEN
    RAISE EXCEPTION 'Template Twin MFA hardening requires the reviewed database role boundary';
  END IF;
END;
$$;

-- The release-control role cannot read session tokens or the MFA secret. This
-- verifier returns only the exact live actor identity and a token fingerprint.
CREATE OR REPLACE FUNCTION public.template_twin_verify_release_actor(
  actor_user_id TEXT,
  actor_session_token TEXT
)
RETURNS TABLE (
  "userId" TEXT,
  "email" TEXT,
  "practiceId" TEXT,
  "sessionSha256" TEXT
)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  SELECT account."id", account."email", account."practiceId",
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
    AND account."mfaSecret" IS NOT NULL
    AND regexp_replace(
      account."mfaSecret",
      U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
      '',
      'g'
    ) <> ''
    AND account."mfaVerifiedAt" IS NOT NULL
    AND account."mfaVerifiedAt" <= CURRENT_TIMESTAMP
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
REVOKE ALL ON FUNCTION public.template_twin_verify_release_actor(TEXT, TEXT)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.template_twin_verify_release_actor(TEXT, TEXT)
  TO quillmd_release_control;

CREATE OR REPLACE FUNCTION public.template_twin_release_approvals_are_current(
  candidate_id UUID,
  candidate_identity CHAR(64)
)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
  WITH latest AS (
    SELECT DISTINCT ON (decision."discipline")
      decision."discipline", decision."decision",
      decision."authorityAssignmentId", decision."actorId",
      decision."actorSessionSha256", decision."actionReceiptNonce",
      decision."decidedAt"
    FROM public."template_twin_release_approval_decisions" decision
    WHERE decision."releaseId" = candidate_id
      AND decision."releaseIdentitySha256" = candidate_identity
    ORDER BY decision."discipline", decision."decidedAt" DESC,
      decision."id" DESC
  )
  SELECT COUNT(*) = 4
    AND COUNT(DISTINCT latest."actorId") = 4
    AND BOOL_AND(
      latest."decision" = 'APPROVE'
      AND EXISTS (
        SELECT 1 FROM public."template_twin_release_authorities" authority
        JOIN public."users" account ON account."id" = authority."userId"
        WHERE authority."id" = latest."authorityAssignmentId"
          AND authority."userId" = latest."actorId"
          AND authority."discipline" = latest."discipline"
          AND authority."effectiveAt" <= latest."decidedAt"
          AND authority."revokedAt" IS NULL
          AND account."isActive" = TRUE
          AND account."deactivatedAt" IS NULL
          AND account."suspendedAt" IS NULL
          AND account."softDeletedAt" IS NULL
          AND account."mfaEnabled" = TRUE
          AND account."mfaSecret" IS NOT NULL
          AND regexp_replace(
            account."mfaSecret",
            U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
            '',
            'g'
          ) <> ''
          AND account."mfaVerifiedAt" IS NOT NULL
          AND account."mfaVerifiedAt" <= CURRENT_TIMESTAMP
          AND 'SUPER_ADMIN'::public."Product" = ANY(account."products")
          AND EXISTS (
            SELECT 1 FROM public."template_twin_release_action_receipts" receipt
            WHERE receipt."nonce" = latest."actionReceiptNonce"
              AND receipt."releaseId" = candidate_id
              AND receipt."checkpointId" IS NULL
              AND receipt."action" = 'APPROVAL'
              AND receipt."discipline" = latest."discipline"
              AND receipt."decision" = latest."decision"
              AND receipt."actorId" = latest."actorId"
              AND receipt."actorSessionSha256" = latest."actorSessionSha256"
              AND receipt."issuedAt" = latest."decidedAt"
          )
      )
    )
  FROM latest;
$$;
REVOKE ALL ON FUNCTION public.template_twin_release_approvals_are_current(
  UUID, CHAR(64)
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.template_twin_release_approvals_are_current(
  UUID, CHAR(64)
) TO quillmd_release_control;

CREATE OR REPLACE FUNCTION public.template_twin_guard_release_approval_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  release_creator TEXT;
  release_finalizer TEXT;
  release_identity CHAR(64);
  release_state TEXT;
  receipt RECORD;
BEGIN
  SELECT "createdById", "frozenById", "releaseIdentitySha256", "status"
    INTO release_creator, release_finalizer, release_identity, release_state
  FROM public."template_twin_release_candidates"
  WHERE "id" = NEW."releaseId";
  IF NOT FOUND OR release_state NOT IN (
    'FROZEN', 'APPROVED', 'ROLLING_OUT', 'STABLE_100'
  ) THEN
    RAISE EXCEPTION 'Template Twin release is not open for a human decision';
  END IF;
  IF NEW."releaseIdentitySha256" <> release_identity
    OR NEW."confirmation" <> NEW."decision" || ' ' || NEW."discipline" ||
      ' ' || left(release_identity, 12)
  THEN
    RAISE EXCEPTION 'Template Twin approval identity or exact confirmation is invalid';
  END IF;
  IF NEW."actorId" = release_creator OR NEW."actorId" = release_finalizer THEN
    RAISE EXCEPTION 'Template Twin release creator/finalizer cannot approve the release';
  END IF;
  IF release_state IN ('ROLLING_OUT', 'STABLE_100')
    AND NEW."decision" = 'APPROVE'
  THEN
    RAISE EXCEPTION 'Template Twin approvals cannot be refreshed after rollout begins';
  END IF;
  SELECT action_receipt.* INTO receipt
  FROM public."template_twin_release_action_receipts" action_receipt
  WHERE action_receipt."nonce" = NEW."actionReceiptNonce"
    AND action_receipt."transactionId" = txid_current()
    AND action_receipt."backendPid" = pg_backend_pid()
    AND action_receipt."releaseId" = NEW."releaseId"
    AND action_receipt."checkpointId" IS NULL
    AND action_receipt."action" = 'APPROVAL'
    AND action_receipt."discipline" = NEW."discipline"
    AND action_receipt."decision" = NEW."decision"
    AND action_receipt."actorId" = NEW."actorId"
    AND action_receipt."actorSessionSha256" = NEW."actorSessionSha256"
    AND action_receipt."confirmationSha256" = encode(
      digest(NEW."confirmation", 'sha256'), 'hex'
    )
    AND action_receipt."expiresAt" > clock_timestamp();
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin approval action receipt is missing or invalid';
  END IF;
  NEW."decidedAt" := receipt."issuedAt";
  IF NOT EXISTS (
    SELECT 1 FROM public."template_twin_release_authorities" authority
    JOIN public."users" account ON account."id" = authority."userId"
    WHERE authority."id" = NEW."authorityAssignmentId"
      AND authority."userId" = NEW."actorId"
      AND authority."discipline" = NEW."discipline"
      AND authority."effectiveAt" <= NEW."decidedAt"
      AND authority."revokedAt" IS NULL
      AND account."isActive" = TRUE
      AND account."deactivatedAt" IS NULL
      AND account."suspendedAt" IS NULL
      AND account."softDeletedAt" IS NULL
      AND account."mfaEnabled" = TRUE
      AND account."mfaSecret" IS NOT NULL
      AND regexp_replace(
        account."mfaSecret",
        U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
        '',
        'g'
      ) <> ''
      AND account."mfaVerifiedAt" IS NOT NULL
      AND account."mfaVerifiedAt" <= CURRENT_TIMESTAMP
      AND 'SUPER_ADMIN'::public."Product" = ANY(account."products")
  ) THEN
    RAISE EXCEPTION 'Template Twin live human authority is missing or revoked';
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.template_twin_guard_release_approval_insert()
  FROM PUBLIC;

-- ACTIVE -> PASSED remains a database safety boundary. Preserve the v2/v3
-- receipt, monitoring, exposure, census, audit, and lock contracts while
-- applying the same complete-MFA predicate to the final checkpoint actor.
CREATE OR REPLACE FUNCTION public.template_twin_guard_checkpoint_pass()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  metric RECORD;
  release RECORD;
  expected_physician_count INTEGER;
BEGIN
  IF OLD."status" <> 'ACTIVE' OR NEW."status" <> 'PASSED' THEN
    RETURN NEW;
  END IF;
  SELECT candidate.* INTO release
  FROM public."template_twin_release_candidates" candidate
  WHERE candidate."id" = NEW."releaseId" FOR SHARE;
  IF NOT FOUND OR release."status" <> 'ROLLING_OUT'
    OR NEW."passedAt" < OLD."earliestPassAt"
    OR NEW."passedAt" > clock_timestamp() + INTERVAL '5 seconds'
    OR clock_timestamp() < OLD."earliestPassAt"
    OR NOT public.template_twin_release_approvals_are_current(
      release."id", release."releaseIdentitySha256"
    )
  THEN
    RAISE EXCEPTION 'Template Twin checkpoint cannot pass before its live release and bake gates';
  END IF;

  SELECT snapshot.* INTO metric
  FROM public."template_twin_release_metric_snapshots" snapshot
  WHERE snapshot."checkpointId" = NEW."id"
  ORDER BY snapshot."createdAt" DESC, snapshot."id" DESC
  LIMIT 1 FOR SHARE;
  IF NOT FOUND OR metric."evaluation" <> 'PASS'
    OR metric."schemaVersion" <> 'template-twin-guardrails-v1'
    OR cardinality(metric."missingMetrics") <> 0
    OR cardinality(metric."breachedMetrics") <> 0
    OR cardinality(metric."blockingReasons") <> 0
    OR metric."observationStartedAt" < OLD."activatedAt"
    OR metric."observationEndedAt" < OLD."earliestPassAt"
    OR metric."observationEndedAt" > NEW."passedAt"
    OR metric."createdAt" > NEW."passedAt"
    OR metric."releaseGeneration" <> release."generation"
    OR NOT EXISTS (
      SELECT 1
      FROM public."template_twin_rollout_controls" control
      WHERE control."id" = 'global' AND control."enabled" = TRUE
        AND control."generation" = metric."globalGeneration"
    )
    OR NEW."passedAt" - metric."observationEndedAt" >
      make_interval(
        secs => (release."guardrailPolicy"->>'maxObservationAgeSeconds')::INTEGER
      )
    OR NOT EXISTS (
      SELECT 1
      FROM public."template_twin_release_metric_receipts" receipt
      JOIN public."template_twin_release_attestation_keys" key
        ON key."keyId" = receipt."attestationKeyId"
       AND key."purpose" = 'METRICS'
       AND key."effectiveAt" <= NEW."passedAt"
       AND key."expiresAt" > NEW."passedAt"
       AND key."revokedAt" IS NULL
      WHERE receipt."releaseId" = metric."releaseId"
        AND receipt."checkpointId" = metric."checkpointId"
        AND receipt."releaseGeneration" = metric."releaseGeneration"
        AND receipt."globalGeneration" = metric."globalGeneration"
        AND receipt."releaseIdentitySha256" = metric."releaseIdentitySha256"
        AND receipt."policySha256" = metric."policySha256"
        AND receipt."schemaVersion" = metric."schemaVersion"
        AND receipt."sampleCount" = metric."sampleCount"
        AND receipt."observationStartedAt" = metric."observationStartedAt"
        AND receipt."observationEndedAt" = metric."observationEndedAt"
        AND receipt."metrics" = metric."metrics"
        AND receipt."canonicalSha256" = metric."canonicalSha256"
        AND receipt."evaluation" = metric."evaluation"
        AND receipt."missingMetrics" = metric."missingMetrics"
        AND receipt."breachedMetrics" = metric."breachedMetrics"
        AND receipt."blockingReasons" = metric."blockingReasons"
        AND receipt."principalUserId" = metric."recordedById"
        AND receipt."attestationKeyId" = metric."attestationKeyId"
        AND receipt."attestationNonceSha256" = metric."attestationNonceSha256"
        AND receipt."attestationSignatureSha256" =
          metric."attestationSignatureSha256"
    )
  THEN
    RAISE EXCEPTION 'Template Twin checkpoint pass requires a fresh exact signed monitoring receipt';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM public."template_twin_release_practices" manifest
    JOIN public."practices" practice ON practice."id" = manifest."practiceId"
    WHERE manifest."releaseId" = NEW."releaseId"
      AND manifest."activationStageOrdinal" <= NEW."ordinal"
      AND (practice."isActive" = FALSE OR practice."templateTwinEnabled" = FALSE)
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint pass requires exact in-scope practice exposure';
  END IF;
  SELECT COUNT(*)::INTEGER INTO expected_physician_count
  FROM public."users" clinician
  WHERE clinician."practiceId" IN (
      SELECT manifest."practiceId"
      FROM public."template_twin_release_practices" manifest
      WHERE manifest."releaseId" = NEW."releaseId"
        AND manifest."activationStageOrdinal" <= NEW."ordinal"
    )
    AND clinician."role" = 'DOCTOR'::public."UserRole"
    AND 'TRANSCRIBE_MD'::public."Product" = ANY(clinician."products")
    AND clinician."isActive" = TRUE
    AND clinician."deactivatedAt" IS NULL
    AND clinician."suspendedAt" IS NULL
    AND clinician."softDeletedAt" IS NULL;
  IF NEW."passedPhysicianCount" <> expected_physician_count
    OR NOT EXISTS (
      SELECT 1 FROM public."users" actor
      WHERE actor."id" = NEW."passedById"
        AND actor."isActive" = TRUE
        AND actor."deactivatedAt" IS NULL
        AND actor."suspendedAt" IS NULL
        AND actor."softDeletedAt" IS NULL
        AND actor."mfaEnabled" = TRUE
        AND actor."mfaSecret" IS NOT NULL
        AND regexp_replace(
          actor."mfaSecret",
          U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
          '',
          'g'
        ) <> ''
        AND actor."mfaVerifiedAt" IS NOT NULL
        AND actor."mfaVerifiedAt" <= CURRENT_TIMESTAMP
        AND 'SUPER_ADMIN'::public."Product" = ANY(actor."products")
        AND EXISTS (
          SELECT 1 FROM public."user_sessions" session
          WHERE session."userId" = actor."id"
            AND session."createdAt" <= clock_timestamp()
            AND session."createdAt" > clock_timestamp() - INTERVAL '12 hours'
            AND session."expiresAt" > clock_timestamp()
            AND (
              actor."forceLogoutAt" IS NULL
              OR session."createdAt" > actor."forceLogoutAt"
            )
        )
    )
    OR NOT EXISTS (
      SELECT 1 FROM public."template_twin_audit_outbox" outbox
      WHERE outbox."eventKey" = NEW."passOutboxEventKey"
        AND outbox."action"::TEXT = 'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_PASSED'
        AND outbox."targetType" = 'TemplateTwinReleaseCheckpoint'
        AND outbox."targetId" = NEW."id"::TEXT
        AND outbox."actorId" = NEW."passedById"
        AND outbox."metadata"->>'releaseId' = NEW."releaseId"::TEXT
        AND outbox."metadata"->>'releaseIdentitySha256' =
          NEW."releaseIdentitySha256"
        AND outbox."metadata"->>'stage' = NEW."stage"
        AND outbox."metadata"->>'metricSnapshotSha256' = metric."canonicalSha256"
        AND outbox."metadata"->>'passedPhysicianCount' =
          expected_physician_count::TEXT
    )
  THEN
    RAISE EXCEPTION 'Template Twin checkpoint pass actor, census, or audit evidence is invalid';
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.template_twin_guard_checkpoint_pass()
  FROM PUBLIC;

-- The isolated admin HTTP process receives only this bounded projection. The
-- MFA secret participates in the predicate but is never projected.
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
    AND account."mfaSecret" IS NOT NULL
    AND regexp_replace(
      account."mfaSecret",
      U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
      '',
      'g'
    ) <> ''
    AND account."mfaVerifiedAt" IS NOT NULL
    AND account."mfaVerifiedAt" <= CURRENT_TIMESTAMP
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

-- Any lifecycle invalidation or MFA evidence change revokes authority. This
-- includes secret removal, blanking, and rotation even when the replacement
-- secret is otherwise well formed. Authority must be explicitly reassigned
-- after the new factor has been reviewed.
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
    OR NEW."mfaEnabled" IS DISTINCT FROM TRUE
    OR NEW."mfaSecret" IS NULL
    OR NOT (
      regexp_replace(
        NEW."mfaSecret",
        U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
        '',
        'g'
      ) <> ''
    )
    OR NEW."mfaVerifiedAt" IS NULL
    OR NEW."mfaVerifiedAt" > CURRENT_TIMESTAMP
    OR NEW."mfaEnabled" IS DISTINCT FROM OLD."mfaEnabled"
    OR NEW."mfaSecret" IS DISTINCT FROM OLD."mfaSecret"
    OR NEW."mfaVerifiedAt" IS DISTINCT FROM OLD."mfaVerifiedAt"
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

DROP TRIGGER IF EXISTS template_twin_user_lifecycle_authority_revoke
  ON public."users";
DROP TRIGGER IF EXISTS aaa_template_twin_user_lifecycle_statement_lock
  ON public."users";
CREATE TRIGGER aaa_template_twin_user_lifecycle_statement_lock
BEFORE UPDATE OF "isActive", "deactivatedAt", "suspendedAt", "softDeletedAt",
  "mfaEnabled", "mfaSecret", "mfaVerifiedAt", "products", "forceLogoutAt"
  ON public."users"
FOR EACH STATEMENT EXECUTE FUNCTION public.template_twin_lock_practice_release_statement();
CREATE TRIGGER template_twin_user_lifecycle_authority_revoke
BEFORE UPDATE OF "isActive", "deactivatedAt", "suspendedAt", "softDeletedAt",
  "mfaEnabled", "mfaSecret", "mfaVerifiedAt", "products", "forceLogoutAt"
  ON public."users"
FOR EACH ROW EXECUTE FUNCTION public.template_twin_revoke_authority_on_user_lifecycle();

-- Migrations v5 and provider ownership were ordered after v3's exhaustive
-- caller-temporary-schema hardening. Reapply that census at the latest edge so
-- no subsequently installed Template Twin function can resolve pg_temp ahead
-- of trusted catalog/public objects.
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

-- Reconcile pre-v4 active authority through the existing audited revocation
-- procedure. This may atomically revoke a live release and disable global and
-- practice exposure. Approval/history rows are never rewritten or deleted.
DO $reconcile_incomplete_mfa$
DECLARE
  assignment RECORD;
BEGIN
  FOR assignment IN
    SELECT authority."id"
    FROM public."template_twin_release_authorities" authority
    JOIN public."users" account ON account."id" = authority."userId"
    WHERE authority."revokedAt" IS NULL
      AND (
        account."mfaEnabled" IS DISTINCT FROM TRUE
        OR account."mfaSecret" IS NULL
        OR NOT (
          regexp_replace(
            account."mfaSecret",
            U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
            '',
            'g'
          ) <> ''
        )
        OR account."mfaVerifiedAt" IS NULL
        OR account."mfaVerifiedAt" > CURRENT_TIMESTAMP
      )
    ORDER BY authority."id"
    FOR UPDATE OF authority
  LOOP
    PERFORM public.template_twin_revoke_release_authority(
      assignment."id", NULL, NULL,
      'MFA_V4_INSTALL_' || upper(replace(assignment."id"::TEXT, '-', '')),
      'AUTHORITY_MFA_INCOMPLETE_INSTALL'
    );
  END LOOP;
END;
$reconcile_incomplete_mfa$;

-- Force the existing deferred audit/coupling contracts before installation
-- can succeed, then prove no current authority or live approval remains stale.
SET CONSTRAINTS ALL IMMEDIATE;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public."template_twin_release_authorities" authority
    JOIN public."users" account ON account."id" = authority."userId"
    WHERE authority."revokedAt" IS NULL
      AND (
        account."mfaEnabled" IS DISTINCT FROM TRUE
        OR account."mfaSecret" IS NULL
        OR NOT (
          regexp_replace(
            account."mfaSecret",
            U&'[\0009-\000D\0020\00A0\1680\2000-\200A\2028\2029\202F\205F\3000\FEFF]',
            '',
            'g'
          ) <> ''
        )
        OR account."mfaVerifiedAt" IS NULL
        OR account."mfaVerifiedAt" > CURRENT_TIMESTAMP
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin MFA hardening left incomplete live authority';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public."template_twin_release_candidates" candidate
    WHERE candidate."status" IN ('APPROVED', 'ROLLING_OUT', 'STABLE_100')
      AND NOT public.template_twin_release_approvals_are_current(
        candidate."id", candidate."releaseIdentitySha256"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin MFA hardening left stale live approvals';
  END IF;
END;
$$;

COMMIT;
