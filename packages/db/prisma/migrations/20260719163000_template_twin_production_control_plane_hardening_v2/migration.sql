-- Template Twin production control-plane hardening v2.
--
-- Additive/default-off correction for the independently rejected v1 head.
-- This migration binds the release to a signed multi-replica runtime manifest,
-- enforces four distinct live human authorities, closes practice INSERT and
-- tenant-lifecycle paths, and establishes non-owner runtime/control DB roles.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Linearize the precondition with every rollout mutation before inspecting
-- the singleton and practice rows. The same assertion is repeated at the end.
SELECT pg_advisory_xact_lock(73119, 20260719);
SELECT "id" FROM "template_twin_rollout_controls"
WHERE "id" = 'global' FOR UPDATE;
SELECT "id" FROM "practices"
WHERE "templateTwinEnabled" = TRUE ORDER BY "id" FOR UPDATE;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "template_twin_rollout_controls"
    WHERE "id" = 'global' AND (
      "enabled" = TRUE OR "rollbackFenceState" <> 'OPEN'
      OR "rollbackOperationId" IS NOT NULL
    )
  ) OR EXISTS (
    SELECT 1 FROM "practices" WHERE "templateTwinEnabled" = TRUE
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_candidates"
  ) THEN
    RAISE EXCEPTION 'Template Twin hardening v2 requires an unused, disabled, open-fence control plane';
  END IF;
END;
$$;

-- Cluster roles are deliberately provisioned out of band by infrastructure,
-- not by the Prisma schema owner. Fail closed unless all attributes and the
-- no-cross-membership boundary are already exact.
DO $$
BEGIN
  IF (
    SELECT COUNT(*) FROM pg_roles
    WHERE rolname IN (
      'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
      'quillmd_audit_dispatcher'
    )
      AND rolcanlogin = FALSE
      AND rolsuper = FALSE
      AND rolcreatedb = FALSE
      AND rolcreaterole = FALSE
      AND rolinherit = FALSE
      AND rolbypassrls = FALSE
  ) <> 4 OR EXISTS (
    SELECT 1
    FROM pg_roles left_boundary
    CROSS JOIN pg_roles right_boundary
    WHERE left_boundary.rolname IN (
        'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
        'quillmd_audit_dispatcher'
      )
      AND right_boundary.rolname IN (
        'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
        'quillmd_audit_dispatcher'
      )
      AND left_boundary.oid <> right_boundary.oid
      AND pg_has_role(left_boundary.oid, right_boundary.oid, 'MEMBER')
  ) OR EXISTS (
    WITH RECURSIVE membership(origin, roleid) AS (
      SELECT direct.member, direct.roleid FROM pg_auth_members direct
      UNION
      SELECT membership.origin, inherited.roleid
      FROM membership
      JOIN pg_auth_members inherited ON inherited.member = membership.roleid
    )
    SELECT 1 FROM membership
    JOIN pg_roles login_role ON login_role.oid = membership.origin
    JOIN pg_roles boundary ON boundary.oid = membership.roleid
    WHERE login_role.rolcanlogin = TRUE
      AND boundary.rolname IN (
        'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
        'quillmd_audit_dispatcher'
      )
    GROUP BY login_role.oid HAVING COUNT(DISTINCT boundary.oid) > 1
  ) OR (
    SELECT COUNT(*) FROM pg_roles login_role
    WHERE login_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
      AND login_role.rolcanlogin = TRUE
      AND login_role.rolsuper = FALSE
      AND login_role.rolcreatedb = FALSE
      AND login_role.rolcreaterole = FALSE
      AND login_role.rolinherit = TRUE
      AND login_role.rolreplication = FALSE
      AND login_role.rolbypassrls = FALSE
  ) <> 3 OR NOT pg_has_role(
    'meddoc_runtime', 'quillmd_runtime', 'MEMBER'
  ) OR NOT pg_has_role(
    'meddoc_release_control', 'quillmd_release_control', 'MEMBER'
  ) OR NOT pg_has_role(
    'meddoc_audit_dispatcher', 'quillmd_audit_dispatcher', 'MEMBER'
  ) OR EXISTS (
    SELECT 1 FROM pg_auth_members membership
    JOIN pg_roles member_role ON member_role.oid = membership.member
    JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
    WHERE (
      member_role.rolname = 'meddoc_runtime'
      AND granted_role.rolname <> 'quillmd_runtime'
    ) OR (
      member_role.rolname = 'meddoc_release_control'
      AND granted_role.rolname <> 'quillmd_release_control'
    ) OR (
      member_role.rolname = 'meddoc_audit_dispatcher'
      AND granted_role.rolname <> 'quillmd_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_auth_members membership
    JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
    JOIN pg_roles member_role ON member_role.oid = membership.member
    WHERE granted_role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
      'quillmd_audit_dispatcher'
    ) AND member_role.rolname NOT IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_auth_members membership
    JOIN pg_roles member_role ON member_role.oid = membership.member
    WHERE member_role.rolname IN (
      'quillmd_runtime', 'quillmd_release_control', 'quillmd_release_security',
      'quillmd_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_class object
    JOIN pg_roles owner_role ON owner_role.oid = object.relowner
    WHERE owner_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_namespace object
    JOIN pg_roles owner_role ON owner_role.oid = object.nspowner
    WHERE owner_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_proc object
    JOIN pg_roles owner_role ON owner_role.oid = object.proowner
    WHERE owner_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_database object
    JOIN pg_roles owner_role ON owner_role.oid = object.datdba
    WHERE owner_role.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_class object
    CROSS JOIN LATERAL aclexplode(object.relacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_namespace object
    CROSS JOIN LATERAL aclexplode(object.nspacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_proc object
    CROSS JOIN LATERAL aclexplode(object.proacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) OR EXISTS (
    SELECT 1 FROM pg_database object
    CROSS JOIN LATERAL aclexplode(object.datacl) privilege
    JOIN pg_roles grantee ON grantee.oid = privilege.grantee
    WHERE grantee.rolname IN (
      'meddoc_runtime', 'meddoc_release_control', 'meddoc_audit_dispatcher'
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin database roles or login principals are absent or not least-privilege';
  END IF;
END;
$$;

ALTER TABLE "template_twin_release_candidates"
  ADD COLUMN "runtimeManifestSha256" CHAR(64);
ALTER TABLE "template_twin_release_candidates"
  ALTER COLUMN "runtimeManifestSha256" SET NOT NULL;
ALTER TABLE "template_twin_release_candidates"
  ADD CONSTRAINT "template_twin_release_runtime_manifest_sha" CHECK (
    "runtimeManifestSha256" ~ '^[0-9a-f]{64}$'
  );
ALTER TABLE "template_twin_release_candidates"
  ADD COLUMN "freezeActionReceiptNonce" UUID;
ALTER TABLE "template_twin_release_approval_decisions"
  ADD COLUMN "actionReceiptNonce" UUID;
ALTER TABLE "template_twin_release_approval_decisions"
  ALTER COLUMN "actionReceiptNonce" SET NOT NULL;
ALTER TABLE "template_twin_release_checkpoints"
  ADD COLUMN "activationActionReceiptNonce" UUID,
  ADD COLUMN "passActionReceiptNonce" UUID;

CREATE OR REPLACE FUNCTION template_twin_set_release_candidate_db_time()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW."createdAt" := clock_timestamp();
  NEW."updatedAt" := NEW."createdAt";
  RETURN NEW;
END;
$$;
CREATE TRIGGER aaa_template_twin_release_candidate_db_time
BEFORE INSERT ON "template_twin_release_candidates"
FOR EACH ROW EXECUTE FUNCTION template_twin_set_release_candidate_db_time();

CREATE OR REPLACE FUNCTION template_twin_guard_release_candidate_history()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  receipt RECORD;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin release history cannot be deleted';
  END IF;
  IF ROW(
    NEW."id", NEW."identityVersion", NEW."releaseIdentitySha256",
    NEW."sourceCommitSha", NEW."baseCommitSha", NEW."appImageDigest",
    NEW."workerImageDigest", NEW."migratorImageDigest",
    NEW."testCensusEvidenceSha256", NEW."independentReviewEvidenceSha256",
    NEW."securityEvidenceSha256", NEW."migrationRestoreEvidenceSha256",
    NEW."officeWordEvidenceSha256", NEW."guardrailPolicySha256",
    NEW."authorizedPracticeManifestSha256", NEW."runtimeManifestSha256",
    NEW."guardrailPolicy", NEW."createdById", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."id", OLD."identityVersion", OLD."releaseIdentitySha256",
    OLD."sourceCommitSha", OLD."baseCommitSha", OLD."appImageDigest",
    OLD."workerImageDigest", OLD."migratorImageDigest",
    OLD."testCensusEvidenceSha256", OLD."independentReviewEvidenceSha256",
    OLD."securityEvidenceSha256", OLD."migrationRestoreEvidenceSha256",
    OLD."officeWordEvidenceSha256", OLD."guardrailPolicySha256",
    OLD."authorizedPracticeManifestSha256", OLD."runtimeManifestSha256",
    OLD."guardrailPolicy", OLD."createdById", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'Template Twin release identity is immutable';
  END IF;
  IF NEW."generation" <> OLD."generation" + 1 THEN
    RAISE EXCEPTION 'Template Twin release transition must advance one generation';
  END IF;
  IF NOT (
    (OLD."status" = 'DRAFT' AND NEW."status" = 'FROZEN')
    OR (OLD."status" = 'FROZEN' AND NEW."status" IN ('FROZEN', 'APPROVED', 'REJECTED', 'REVOKED'))
    OR (OLD."status" = 'APPROVED' AND NEW."status" IN ('APPROVED', 'ROLLING_OUT', 'REJECTED', 'REVOKED'))
    OR (OLD."status" = 'ROLLING_OUT' AND NEW."status" IN ('ROLLING_OUT', 'STABLE_100', 'REJECTED', 'REVOKED'))
    OR (OLD."status" = 'STABLE_100' AND NEW."status" IN ('REJECTED', 'REVOKED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin release state transition is invalid';
  END IF;
  IF OLD."status" = 'DRAFT' THEN
    IF NEW."status" <> 'FROZEN' OR NEW."frozenById" IS NULL
      OR NEW."freezeActionReceiptNonce" IS NULL
    THEN
      RAISE EXCEPTION 'Template Twin release freeze evidence is incomplete';
    END IF;
    SELECT action_receipt.* INTO receipt
    FROM public."template_twin_release_action_receipts" action_receipt
    WHERE action_receipt."nonce" = NEW."freezeActionReceiptNonce"
      AND action_receipt."transactionId" = txid_current()
      AND action_receipt."backendPid" = pg_backend_pid()
      AND action_receipt."releaseId" = NEW."id"
      AND action_receipt."checkpointId" IS NULL
      AND action_receipt."action" = 'FREEZE'
      AND action_receipt."actorId" = NEW."frozenById"
      AND action_receipt."expiresAt" > clock_timestamp();
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Template Twin release freeze evidence is incomplete';
    END IF;
    NEW."frozenAt" := receipt."issuedAt";
  ELSIF ROW(
    NEW."frozenById", NEW."frozenAt", NEW."freezeActionReceiptNonce"
  ) IS DISTINCT FROM ROW(
    OLD."frozenById", OLD."frozenAt", OLD."freezeActionReceiptNonce"
  ) THEN
    RAISE EXCEPTION 'Template Twin release finalizer identity is immutable';
  END IF;
  RETURN NEW;
END;
$$;
ALTER TABLE "template_twin_release_candidates"
  DROP CONSTRAINT "template_twin_release_identity_version";
ALTER TABLE "template_twin_release_candidates"
  ADD CONSTRAINT "template_twin_release_identity_version" CHECK (
    "identityVersion" = 'template-twin-production-release-v2'
  );

CREATE TABLE "template_twin_release_runtime_requirements" (
  "id" UUID NOT NULL,
  "releaseId" UUID NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "instanceId" VARCHAR(128) NOT NULL,
  "component" VARCHAR(16) NOT NULL,
  "sourceCommitSha" CHAR(40) NOT NULL,
  "imageDigest" VARCHAR(71) NOT NULL,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_release_runtime_requirements_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_runtime_requirement_instance_key"
    UNIQUE ("releaseId", "instanceId"),
  CONSTRAINT "template_twin_release_runtime_requirement_component" CHECK (
    "component" IN ('APP', 'WORKER')
  ),
  CONSTRAINT "template_twin_release_runtime_requirement_identity" CHECK (
    "releaseIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "sourceCommitSha" ~ '^[0-9a-f]{40}$'
    AND "imageDigest" ~ '^sha256:[0-9a-f]{64}$'
    AND "instanceId" ~ '^[a-z0-9][a-z0-9._-]{1,127}$'
  ),
  CONSTRAINT "template_twin_release_runtime_requirement_release_fkey"
    FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT
);
CREATE INDEX "template_twin_release_runtime_requirement_component_idx"
  ON "template_twin_release_runtime_requirements"("releaseId", "component", "instanceId");

-- Secrets are provisioned only through a migrator-owned operational ceremony.
-- Runtime/control roles have no SELECT or DML privilege on this table.
CREATE TABLE "template_twin_release_attestation_keys" (
  "keyId" VARCHAR(80) NOT NULL,
  "purpose" VARCHAR(16) NOT NULL,
  "secret" BYTEA NOT NULL,
  "principalUserId" TEXT,
  "effectiveAt" TIMESTAMPTZ(6) NOT NULL,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  "revokedAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_release_attestation_keys_pkey" PRIMARY KEY ("keyId"),
  CONSTRAINT "template_twin_release_attestation_key_shape" CHECK (
    "keyId" ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$'
    AND "purpose" IN ('RUNTIME', 'METRICS')
    AND octet_length("secret") >= 32
    AND "expiresAt" > "effectiveAt"
    AND ("revokedAt" IS NULL OR "revokedAt" >= "effectiveAt")
    AND (("purpose" = 'METRICS') = ("principalUserId" IS NOT NULL))
  ),
  CONSTRAINT "template_twin_release_attestation_key_principal_fkey"
    FOREIGN KEY ("principalUserId") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT
);
REVOKE ALL ON "template_twin_release_attestation_keys" FROM PUBLIC;
CREATE OR REPLACE FUNCTION template_twin_guard_attestation_key_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin attestation keys cannot be deleted';
  END IF;
  IF ROW(
    NEW."keyId", NEW."purpose", NEW."secret", NEW."principalUserId",
    NEW."effectiveAt", NEW."expiresAt", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."keyId", OLD."purpose", OLD."secret", OLD."principalUserId",
    OLD."effectiveAt", OLD."expiresAt", OLD."createdAt"
  ) OR OLD."revokedAt" IS NOT NULL OR NEW."revokedAt" IS NULL
    OR NEW."revokedAt" < clock_timestamp() - INTERVAL '5 seconds'
  THEN
    RAISE EXCEPTION 'Template Twin attestation keys permit only a monotonic current revocation';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER template_twin_release_attestation_key_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_attestation_keys"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_attestation_key_history();
CREATE TRIGGER template_twin_release_attestation_key_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_attestation_keys"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_release_truncate();

CREATE TABLE "template_twin_release_runtime_attestations" (
  "id" UUID NOT NULL,
  "releaseId" UUID NOT NULL,
  "requirementId" UUID NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "keyId" VARCHAR(80) NOT NULL,
  "nonceSha256" CHAR(64) NOT NULL,
  "instanceId" VARCHAR(128) NOT NULL,
  "component" VARCHAR(16) NOT NULL,
  "sourceCommitSha" CHAR(40) NOT NULL,
  "imageDigest" VARCHAR(71) NOT NULL,
  "signatureSha256" CHAR(64) NOT NULL,
  "issuedAt" TIMESTAMPTZ(6) NOT NULL,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  "lastSeenAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_release_runtime_attestations_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_release_runtime_attestation_nonce_key" UNIQUE ("nonceSha256"),
  CONSTRAINT "template_twin_release_runtime_attestation_shape" CHECK (
    "releaseIdentitySha256" ~ '^[0-9a-f]{64}$'
    AND "nonceSha256" ~ '^[0-9a-f]{64}$'
    AND "signatureSha256" ~ '^[0-9a-f]{64}$'
    AND "component" IN ('APP', 'WORKER')
    AND "sourceCommitSha" ~ '^[0-9a-f]{40}$'
    AND "imageDigest" ~ '^sha256:[0-9a-f]{64}$'
    AND "expiresAt" > "issuedAt"
  ),
  CONSTRAINT "template_twin_release_runtime_attestation_release_fkey"
    FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT "template_twin_release_runtime_attestation_requirement_fkey"
    FOREIGN KEY ("requirementId") REFERENCES "template_twin_release_runtime_requirements"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT "template_twin_release_runtime_attestation_key_fkey"
    FOREIGN KEY ("keyId") REFERENCES "template_twin_release_attestation_keys"("keyId")
    ON DELETE RESTRICT ON UPDATE RESTRICT
);
CREATE INDEX "template_twin_release_runtime_attestation_readiness_idx"
  ON "template_twin_release_runtime_attestations"("releaseId", "instanceId", "expiresAt");

CREATE OR REPLACE FUNCTION template_twin_reject_runtime_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND ROW(
    NEW."id", NEW."releaseId", NEW."requirementId",
    NEW."releaseIdentitySha256", NEW."keyId", NEW."nonceSha256",
    NEW."instanceId", NEW."component", NEW."sourceCommitSha",
    NEW."imageDigest", NEW."signatureSha256", NEW."issuedAt",
    NEW."expiresAt", NEW."createdAt"
  ) IS NOT DISTINCT FROM ROW(
    OLD."id", OLD."releaseId", OLD."requirementId",
    OLD."releaseIdentitySha256", OLD."keyId", OLD."nonceSha256",
    OLD."instanceId", OLD."component", OLD."sourceCommitSha",
    OLD."imageDigest", OLD."signatureSha256", OLD."issuedAt",
    OLD."expiresAt", OLD."createdAt"
  ) AND NEW."lastSeenAt" >= OLD."lastSeenAt"
    AND NEW."lastSeenAt" <= clock_timestamp() + INTERVAL '5 seconds'
  THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Template Twin runtime requirements and attestations are immutable';
END;
$$;
CREATE TRIGGER template_twin_runtime_requirement_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_runtime_requirements"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_runtime_evidence_mutation();
CREATE TRIGGER template_twin_runtime_attestation_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_runtime_attestations"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_runtime_evidence_mutation();
CREATE TRIGGER template_twin_runtime_requirement_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_runtime_requirements"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_runtime_evidence_mutation();
CREATE TRIGGER template_twin_runtime_attestation_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_runtime_attestations"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_runtime_evidence_mutation();

CREATE OR REPLACE FUNCTION template_twin_register_runtime_attestation(
  attestation_version TEXT,
  attestation_key_id TEXT,
  attestation_nonce UUID,
  candidate_identity CHAR(64),
  runtime_instance_id TEXT,
  runtime_component TEXT,
  runtime_source_commit CHAR(40),
  runtime_image_digest TEXT,
  issued_epoch_seconds BIGINT,
  expires_epoch_seconds BIGINT,
  supplied_signature CHAR(64)
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  signing_secret BYTEA;
  requirement_id UUID;
  candidate_id UUID;
  issued_at TIMESTAMPTZ;
  expires_at TIMESTAMPTZ;
  signing_message TEXT;
  expected_signature TEXT;
  nonce_sha TEXT;
  receipt_id UUID;
BEGIN
  IF attestation_version <> 'template-twin-runtime-attestation-v1'
    OR supplied_signature !~ '^[0-9a-f]{64}$'
  THEN
    RAISE EXCEPTION 'Template Twin runtime attestation shape is invalid';
  END IF;
  issued_at := to_timestamp(issued_epoch_seconds);
  expires_at := to_timestamp(expires_epoch_seconds);
  IF issued_at > clock_timestamp() + INTERVAL '30 seconds'
    OR issued_at < clock_timestamp() - INTERVAL '24 hours'
    OR expires_at <= clock_timestamp() + INTERVAL '30 seconds'
    OR expires_at > issued_at + INTERVAL '30 days'
  THEN
    RAISE EXCEPTION 'Template Twin runtime attestation is stale or outside its bounded lease';
  END IF;

  SELECT key."secret" INTO signing_secret
  FROM public."template_twin_release_attestation_keys" key
  WHERE key."keyId" = attestation_key_id
    AND key."purpose" = 'RUNTIME'
    AND key."effectiveAt" <= clock_timestamp()
    AND key."expiresAt" > clock_timestamp()
    AND key."revokedAt" IS NULL;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin runtime attestation key is unavailable';
  END IF;

  signing_message := concat_ws(E'\n',
    attestation_version, attestation_key_id, attestation_nonce::TEXT,
    btrim(candidate_identity), runtime_instance_id, runtime_component,
    btrim(runtime_source_commit), runtime_image_digest,
    issued_epoch_seconds::TEXT, expires_epoch_seconds::TEXT
  );
  expected_signature := encode(hmac(
    convert_to(signing_message, 'UTF8'), signing_secret, 'sha256'
  ), 'hex');
  IF expected_signature <> supplied_signature THEN
    RAISE EXCEPTION 'Template Twin runtime attestation signature is invalid';
  END IF;

  SELECT candidate."id", req."id" INTO candidate_id, requirement_id
  FROM public."template_twin_release_candidates" candidate
  JOIN public."template_twin_release_runtime_requirements" req
    ON req."releaseId" = candidate."id"
  WHERE candidate."releaseIdentitySha256" = candidate_identity
    AND candidate."status" IN ('DRAFT', 'FROZEN', 'APPROVED', 'ROLLING_OUT', 'STABLE_100')
    AND req."releaseIdentitySha256" = candidate_identity
    AND req."instanceId" = runtime_instance_id
    AND req."component" = runtime_component
    AND req."sourceCommitSha" = runtime_source_commit
    AND req."imageDigest" = runtime_image_digest;
  IF NOT FOUND THEN
    -- A correctly signed deployment envelope can be installed before its
    -- candidate is created and can outlive a revoked candidate. Preserve the
    -- cryptographic validation above, but report this default-off state with
    -- a NULL receipt so kill-switched runtimes keep ordinary visits healthy.
    RETURN NULL;
  END IF;

  nonce_sha := encode(digest(attestation_nonce::TEXT, 'sha256'), 'hex');
  receipt_id := gen_random_uuid();
  INSERT INTO public."template_twin_release_runtime_attestations" (
    "id", "releaseId", "requirementId", "releaseIdentitySha256", "keyId",
    "nonceSha256", "instanceId", "component", "sourceCommitSha",
    "imageDigest", "signatureSha256", "issuedAt", "expiresAt"
  ) VALUES (
    receipt_id, candidate_id, requirement_id, candidate_identity,
    attestation_key_id, nonce_sha, runtime_instance_id, runtime_component,
    runtime_source_commit, runtime_image_digest,
    encode(digest(supplied_signature, 'sha256'), 'hex'), issued_at, expires_at
  ) ON CONFLICT ("nonceSha256") DO UPDATE
    SET "lastSeenAt" = clock_timestamp();
  SELECT attestation."id" INTO receipt_id
  FROM public."template_twin_release_runtime_attestations" attestation
  WHERE attestation."nonceSha256" = nonce_sha
    AND attestation."releaseIdentitySha256" = candidate_identity
    AND attestation."instanceId" = runtime_instance_id
    AND attestation."expiresAt" = expires_at;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin runtime attestation nonce was replayed with another identity';
  END IF;
  RETURN receipt_id;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_release_runtime_ready(
  candidate_id UUID,
  candidate_identity CHAR(64)
)
RETURNS BOOLEAN LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public."template_twin_release_runtime_requirements" requirement
    WHERE requirement."releaseId" = candidate_id
      AND requirement."releaseIdentitySha256" = candidate_identity
      AND requirement."component" = 'APP'
  ) AND EXISTS (
    SELECT 1 FROM public."template_twin_release_runtime_requirements" requirement
    WHERE requirement."releaseId" = candidate_id
      AND requirement."releaseIdentitySha256" = candidate_identity
      AND requirement."component" = 'WORKER'
  ) AND NOT EXISTS (
    SELECT 1 FROM public."template_twin_release_runtime_requirements" requirement
    WHERE requirement."releaseId" = candidate_id
      AND requirement."releaseIdentitySha256" = candidate_identity
      AND NOT EXISTS (
        SELECT 1 FROM public."template_twin_release_runtime_attestations" attestation
        JOIN public."template_twin_release_attestation_keys" key
          ON key."keyId" = attestation."keyId"
         AND key."purpose" = 'RUNTIME'
         AND key."effectiveAt" <= clock_timestamp()
         AND key."expiresAt" > clock_timestamp()
         AND key."revokedAt" IS NULL
        WHERE attestation."requirementId" = requirement."id"
          AND attestation."releaseId" = candidate_id
          AND attestation."releaseIdentitySha256" = candidate_identity
          AND attestation."instanceId" = requirement."instanceId"
          AND attestation."component" = requirement."component"
          AND attestation."sourceCommitSha" = requirement."sourceCommitSha"
          AND attestation."imageDigest" = requirement."imageDigest"
          AND attestation."expiresAt" > clock_timestamp() + INTERVAL '30 seconds'
          AND attestation."lastSeenAt" > clock_timestamp() - INTERVAL '75 seconds'
      )
  );
$$;

CREATE OR REPLACE FUNCTION template_twin_current_runtime_release()
RETURNS TABLE (
  "id" UUID,
  "releaseIdentitySha256" CHAR(64),
  "runtimeManifestSha256" CHAR(64),
  "runtimeReady" BOOLEAN
)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  SELECT candidate."id", candidate."releaseIdentitySha256",
    candidate."runtimeManifestSha256",
    public.template_twin_release_runtime_ready(
      candidate."id", candidate."releaseIdentitySha256"
    )
  FROM public."template_twin_release_candidates" candidate
  WHERE candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
    AND public.template_twin_release_approvals_are_current(
      candidate."id", candidate."releaseIdentitySha256"
    );
$$;
REVOKE ALL ON FUNCTION template_twin_register_runtime_attestation(
  TEXT, TEXT, UUID, CHAR(64), TEXT, TEXT, CHAR(40), TEXT, BIGINT, BIGINT, CHAR(64)
) FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_release_runtime_ready(UUID, CHAR(64))
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_current_runtime_release() FROM PUBLIC;

-- The application may assemble a draft in several statements, but the
-- manifest, replica topology, and checkpoint rail close permanently at the
-- DRAFT -> FROZEN boundary. Hashes are recomputed from database rows using
-- the exact canonical JSON key/row ordering used by the TypeScript contract.
CREATE OR REPLACE FUNCTION template_twin_guard_release_manifest_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  candidate RECORD;
BEGIN
  SELECT release."status", release."releaseIdentitySha256",
    release."sourceCommitSha", release."appImageDigest",
    release."workerImageDigest"
  INTO candidate
  FROM "template_twin_release_candidates" release
  WHERE release."id" = NEW."releaseId"
  FOR SHARE;
  IF NOT FOUND OR candidate."status" <> 'DRAFT'
    OR NEW."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
  THEN
    RAISE EXCEPTION 'Template Twin release manifests accept rows only while the exact candidate is DRAFT';
  END IF;
  IF TG_TABLE_NAME = 'template_twin_release_runtime_requirements' THEN
    IF NEW."sourceCommitSha" <> candidate."sourceCommitSha"
      OR NEW."imageDigest" <> (CASE NEW."component"
        WHEN 'APP' THEN candidate."appImageDigest"
        WHEN 'WORKER' THEN candidate."workerImageDigest"
        ELSE NULL
      END)
    THEN
      RAISE EXCEPTION 'Template Twin runtime requirement is outside the candidate image identity';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER aaa_template_twin_release_practice_draft_insert_guard
BEFORE INSERT ON "template_twin_release_practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_manifest_insert();
CREATE TRIGGER aaa_template_twin_release_checkpoint_draft_insert_guard
BEFORE INSERT ON "template_twin_release_checkpoints"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_manifest_insert();
CREATE TRIGGER aaa_template_twin_release_runtime_draft_insert_guard
BEFORE INSERT ON "template_twin_release_runtime_requirements"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_manifest_insert();

CREATE OR REPLACE FUNCTION template_twin_canonical_json(value JSONB)
RETURNS TEXT LANGUAGE plpgsql IMMUTABLE STRICT
SET search_path = pg_catalog, public
AS $$
DECLARE
  result TEXT;
BEGIN
  CASE jsonb_typeof(value)
    WHEN 'object' THEN
      SELECT '{' || COALESCE(string_agg(
        to_jsonb(entry.key)::TEXT || ':' ||
          public.template_twin_canonical_json(entry.value),
        ',' ORDER BY entry.key COLLATE "C"
      ), '') || '}' INTO result
      FROM jsonb_each(value) entry;
    WHEN 'array' THEN
      SELECT '[' || COALESCE(string_agg(
        public.template_twin_canonical_json(entry.value),
        ',' ORDER BY entry.ordinality
      ), '') || ']' INTO result
      FROM jsonb_array_elements(value) WITH ORDINALITY entry(value, ordinality);
    WHEN 'number' THEN
      result := trim_scale((value #>> '{}')::NUMERIC)::TEXT;
    ELSE
      result := value::TEXT;
  END CASE;
  RETURN result;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_canonical_json(JSONB) FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_guardrail_policy_is_exact(policy JSONB)
RETURNS BOOLEAN LANGUAGE plpgsql IMMUTABLE
SET search_path = pg_catalog, public
AS $$
DECLARE
  stage_name TEXT;
  stage_value JSONB;
  metric RECORD;
  rule JSONB;
  threshold_value NUMERIC;
BEGIN
  IF policy IS NULL OR jsonb_typeof(policy) <> 'object'
    OR (SELECT COUNT(*) FROM jsonb_object_keys(policy)) <> 5
    OR NOT policy ?& ARRAY[
      'schemaVersion', 'maxObservationAgeSeconds',
      'minimumBakeSecondsByStage', 'minimumSampleCountByStage', 'metrics'
    ]
    OR policy->>'schemaVersion' <> 'template-twin-guardrails-v1'
    OR jsonb_typeof(policy->'maxObservationAgeSeconds') <> 'number'
    OR (policy->>'maxObservationAgeSeconds')::NUMERIC <> trunc(
      (policy->>'maxObservationAgeSeconds')::NUMERIC
    )
    OR (policy->>'maxObservationAgeSeconds')::NUMERIC NOT BETWEEN 60 AND 86400
  THEN
    RETURN FALSE;
  END IF;

  FOREACH stage_name IN ARRAY ARRAY[
    'CANARY', 'PERCENT_10', 'PERCENT_25', 'PERCENT_50', 'PERCENT_100'
  ] LOOP
    FOREACH stage_value IN ARRAY ARRAY[
      policy->'minimumBakeSecondsByStage',
      policy->'minimumSampleCountByStage'
    ] LOOP
      IF jsonb_typeof(stage_value) <> 'object'
        OR (SELECT COUNT(*) FROM jsonb_object_keys(stage_value)) <> 5
        OR NOT stage_value ?& ARRAY[
          'CANARY', 'PERCENT_10', 'PERCENT_25', 'PERCENT_50', 'PERCENT_100'
        ]
        OR jsonb_typeof(stage_value->stage_name) <> 'number'
        OR (stage_value->>stage_name)::NUMERIC < 1
        OR (stage_value->>stage_name)::NUMERIC > (CASE
          WHEN stage_value = policy->'minimumBakeSecondsByStage'
            THEN 2592000 ELSE 10000000 END)
        OR (stage_value->>stage_name)::NUMERIC <>
          trunc((stage_value->>stage_name)::NUMERIC)
      THEN
        RETURN FALSE;
      END IF;
    END LOOP;
  END LOOP;

  IF jsonb_typeof(policy->'metrics') <> 'object'
    OR (SELECT COUNT(*) FROM jsonb_object_keys(policy->'metrics')) <> 22
  THEN
    RETURN FALSE;
  END IF;
  FOR metric IN
    SELECT * FROM (VALUES
      ('failed_upload_rate','MAX',0::NUMERIC,1::NUMERIC,FALSE),
      ('malware_inspection_failure_rate','MAX',0,1,FALSE),
      ('render_verification_failure_rate','MAX',0,1,FALSE),
      ('sign_download_block_rate','MAX',0,1,FALSE),
      ('unsafe_bypass_attempt_count','MAX',0,1000000,TRUE),
      ('audit_outbox_delivery_failure_rate','MAX',0,1,FALSE),
      ('audit_outbox_max_lag_seconds','MAX',0,86400,FALSE),
      ('object_storage_failure_rate','MAX',0,1,FALSE),
      ('queue_failure_rate','MAX',0,1,FALSE),
      ('provider_failure_rate','MAX',0,1,FALSE),
      ('provider_ambiguous_outcome_count','MAX',0,1000000,TRUE),
      ('p95_latency_ms','MAX',0,3600000,FALSE),
      ('p99_latency_ms','MAX',0,3600000,FALSE),
      ('error_rate','MAX',0,1,FALSE),
      ('critical_field_accuracy','MIN',0,1,TRUE),
      ('unsupported_field_recall','MIN',0,1,FALSE),
      ('hallucination_rate','MAX',0,1,TRUE),
      ('evidence_anchor_validity','MIN',0,1,TRUE),
      ('exact_dropdown_accuracy','MIN',0,1,TRUE),
      ('negation_accuracy','MIN',0,1,TRUE),
      ('laterality_accuracy','MIN',0,1,TRUE),
      ('table_placement_accuracy','MIN',0,1,TRUE)
    ) definition(name, direction, minimum, maximum, required_critical)
  LOOP
    rule := policy->'metrics'->metric.name;
    IF rule IS NULL OR jsonb_typeof(rule) <> 'object'
      OR (SELECT COUNT(*) FROM jsonb_object_keys(rule)) <> 3
      OR NOT rule ?& ARRAY['direction', 'threshold', 'critical']
      OR rule->>'direction' <> metric.direction
      OR jsonb_typeof(rule->'threshold') <> 'number'
      OR jsonb_typeof(rule->'critical') <> 'boolean'
    THEN
      RETURN FALSE;
    END IF;
    threshold_value := (rule->>'threshold')::NUMERIC;
    IF threshold_value < metric.minimum OR threshold_value > metric.maximum
      OR threshold_value <> round(threshold_value, 6)
      OR (metric.required_critical AND (rule->>'critical')::BOOLEAN <> TRUE)
    THEN
      RETURN FALSE;
    END IF;
  END LOOP;
  RETURN TRUE;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_guardrail_policy_is_exact(JSONB)
  FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_validate_release_freeze_manifest()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public AS $$
DECLARE
  practice_count INTEGER;
  runtime_count INTEGER;
  practice_manifest_json TEXT;
  runtime_manifest_json TEXT;
  computed_practice_sha TEXT;
  computed_runtime_sha TEXT;
  computed_policy_sha TEXT;
  computed_release_identity_sha TEXT;
BEGIN
  IF OLD."status" <> 'DRAFT' OR NEW."status" <> 'FROZEN' THEN
    RETURN NEW;
  END IF;

  SELECT COUNT(*)::INTEGER,
    '{"practices":[' || COALESCE(string_agg(
      '{"activationStage":' || to_jsonb(manifest."activationStage")::TEXT ||
      ',"activationStageOrdinal":' || manifest."activationStageOrdinal"::TEXT ||
      ',"cohortHashSha256":' || to_jsonb(btrim(manifest."cohortHashSha256"))::TEXT ||
      ',"cohortRank":' || manifest."cohortRank"::TEXT ||
      ',"isCanary":' || CASE WHEN manifest."isCanary" THEN 'true' ELSE 'false' END ||
      ',"physicianCountSnapshot":' || manifest."physicianCountSnapshot"::TEXT ||
      ',"practiceId":' || to_jsonb(manifest."practiceId")::TEXT ||
      ',"practiceSlugSnapshot":' || to_jsonb(manifest."practiceSlugSnapshot")::TEXT || '}',
      ',' ORDER BY manifest."cohortRank"
    ), '') || '],"sourceCommitSha":' || to_jsonb(btrim(NEW."sourceCommitSha"))::TEXT ||
    ',"version":"template-twin-authorized-practice-manifest-v1"}'
  INTO practice_count, practice_manifest_json
  FROM "template_twin_release_practices" manifest
  WHERE manifest."releaseId" = NEW."id";

  SELECT COUNT(*)::INTEGER,
    '{"instances":[' || COALESCE(string_agg(
      '{"component":' || to_jsonb(requirement."component")::TEXT ||
      ',"imageDigest":' || to_jsonb(requirement."imageDigest")::TEXT ||
      ',"instanceId":' || to_jsonb(requirement."instanceId")::TEXT || '}',
      ',' ORDER BY requirement."component" COLLATE "C",
        requirement."instanceId" COLLATE "C"
    ), '') || '],"sourceCommitSha":' || to_jsonb(btrim(NEW."sourceCommitSha"))::TEXT ||
    ',"version":"template-twin-runtime-manifest-v1"}'
  INTO runtime_count, runtime_manifest_json
  FROM "template_twin_release_runtime_requirements" requirement
  WHERE requirement."releaseId" = NEW."id";

  computed_practice_sha := encode(digest(
    convert_to(practice_manifest_json, 'UTF8'), 'sha256'
  ), 'hex');
  computed_runtime_sha := encode(digest(
    convert_to(runtime_manifest_json, 'UTF8'), 'sha256'
  ), 'hex');
  computed_policy_sha := encode(digest(convert_to(
    template_twin_canonical_json(NEW."guardrailPolicy"), 'UTF8'
  ), 'sha256'), 'hex');
  computed_release_identity_sha := encode(digest(convert_to(
    template_twin_canonical_json(jsonb_build_object(
      'version', NEW."identityVersion",
      'sourceCommitSha', btrim(NEW."sourceCommitSha"),
      'baseCommitSha', btrim(NEW."baseCommitSha"),
      'images', jsonb_build_object(
        'application', NEW."appImageDigest", 'worker', NEW."workerImageDigest",
        'migrator', NEW."migratorImageDigest"
      ),
      'evidence', jsonb_build_object(
        'testCensus', btrim(NEW."testCensusEvidenceSha256"),
        'independentExactHeadReview', btrim(NEW."independentReviewEvidenceSha256"),
        'securityAndSecretScan', btrim(NEW."securityEvidenceSha256"),
        'migrationAndRestoreRehearsal', btrim(NEW."migrationRestoreEvidenceSha256"),
        'desktopMicrosoftWord', btrim(NEW."officeWordEvidenceSha256")
      ),
      'guardrailPolicySha256', btrim(NEW."guardrailPolicySha256"),
      'authorizedPracticeManifestSha256',
        btrim(NEW."authorizedPracticeManifestSha256"),
      'runtimeManifestSha256', btrim(NEW."runtimeManifestSha256")
    )), 'UTF8'
  ), 'sha256'), 'hex');

  IF practice_count NOT BETWEEN 1 AND 10000
    OR runtime_count NOT BETWEEN 2 AND 256
    OR computed_practice_sha <> NEW."authorizedPracticeManifestSha256"
    OR computed_runtime_sha <> NEW."runtimeManifestSha256"
    OR NOT template_twin_guardrail_policy_is_exact(NEW."guardrailPolicy")
    OR computed_policy_sha <> NEW."guardrailPolicySha256"
    OR computed_release_identity_sha <> NEW."releaseIdentitySha256"
    OR NOT EXISTS (
      SELECT 1 FROM "template_twin_release_runtime_requirements" requirement
      WHERE requirement."releaseId" = NEW."id" AND requirement."component" = 'APP'
    )
    OR NOT EXISTS (
      SELECT 1 FROM "template_twin_release_runtime_requirements" requirement
      WHERE requirement."releaseId" = NEW."id" AND requirement."component" = 'WORKER'
    )
    OR COALESCE((
      SELECT SUM(manifest."physicianCountSnapshot")
      FROM "template_twin_release_practices" manifest
      WHERE manifest."releaseId" = NEW."id" AND manifest."isCanary" = TRUE
    ), 0) <= 0
    OR EXISTS (
      WITH ranked AS (
        SELECT manifest.*,
          row_number() OVER (ORDER BY manifest."isCanary" DESC,
            manifest."cohortHashSha256" COLLATE "C",
            manifest."practiceId" COLLATE "C") AS expected_rank,
          COALESCE(SUM(manifest."physicianCountSnapshot") OVER (
            ORDER BY manifest."cohortRank"
            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
          ), 0) AS physicians_before,
          SUM(manifest."physicianCountSnapshot") OVER () AS total_physicians
        FROM "template_twin_release_practices" manifest
        WHERE manifest."releaseId" = NEW."id"
      ), expected AS (
        SELECT ranked.*,
          CASE
            WHEN ranked."isCanary" THEN 'CANARY'
            WHEN ranked.physicians_before < CEIL(ranked.total_physicians * 0.10)
              THEN 'PERCENT_10'
            WHEN ranked.physicians_before < CEIL(ranked.total_physicians * 0.25)
              THEN 'PERCENT_25'
            WHEN ranked.physicians_before < CEIL(ranked.total_physicians * 0.50)
              THEN 'PERCENT_50'
            ELSE 'PERCENT_100'
          END AS expected_stage
        FROM ranked
      )
      SELECT 1 FROM expected
      WHERE expected."cohortRank" <> expected.expected_rank
        OR btrim(expected."cohortHashSha256") <> encode(digest(convert_to(
          '{"practiceId":' || to_jsonb(expected."practiceId")::TEXT ||
          ',"sourceCommitSha":' || to_jsonb(btrim(NEW."sourceCommitSha"))::TEXT ||
          ',"version":"template-twin-cohort-rank-v1"}', 'UTF8'
        ), 'sha256'), 'hex')
        OR expected."activationStage" <> expected.expected_stage
        OR expected."activationStageOrdinal" <> CASE expected.expected_stage
          WHEN 'CANARY' THEN 1 WHEN 'PERCENT_10' THEN 2
          WHEN 'PERCENT_25' THEN 3 WHEN 'PERCENT_50' THEN 4 ELSE 5 END
        OR expected."isCanary" <> (expected."activationStage" = 'CANARY')
    )
    OR EXISTS (
      SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
      WHERE checkpoint."releaseId" = NEW."id" AND (
        checkpoint."assignedPhysicianCount" <> COALESCE((
          SELECT SUM(manifest."physicianCountSnapshot")
          FROM "template_twin_release_practices" manifest
          WHERE manifest."releaseId" = NEW."id"
            AND manifest."activationStageOrdinal" <= checkpoint."ordinal"
        ), 0)
        OR checkpoint."targetPhysicianCount" <> CASE
          WHEN checkpoint."stage" = 'CANARY' THEN COALESCE((
            SELECT SUM(manifest."physicianCountSnapshot")
            FROM "template_twin_release_practices" manifest
            WHERE manifest."releaseId" = NEW."id" AND manifest."isCanary" = TRUE
          ), 0)
          WHEN checkpoint."targetPercent" = 100 THEN COALESCE((
            SELECT SUM(manifest."physicianCountSnapshot")
            FROM "template_twin_release_practices" manifest
            WHERE manifest."releaseId" = NEW."id"
          ), 0)
          ELSE CEIL(COALESCE((
            SELECT SUM(manifest."physicianCountSnapshot")
            FROM "template_twin_release_practices" manifest
            WHERE manifest."releaseId" = NEW."id"
          ), 0) * checkpoint."targetPercent" / 100.0)::INTEGER
        END
      )
    )
  THEN
    RAISE EXCEPTION 'Template Twin frozen manifest or runtime hash does not match its complete database row set';
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER aaa_template_twin_release_freeze_manifest_guard
BEFORE UPDATE ON "template_twin_release_candidates"
FOR EACH ROW EXECUTE FUNCTION template_twin_validate_release_freeze_manifest();

-- One live discipline per human and four distinct live humans per release.
DROP INDEX "template_twin_one_active_release_authority_key";
CREATE UNIQUE INDEX "template_twin_one_active_release_authority_per_human_key"
  ON "template_twin_release_authorities"("userId")
  WHERE "revokedAt" IS NULL;

-- The release-control role cannot read session tokens. This narrow verifier
-- proves the exact live MFA session and returns only its SHA-256 fingerprint.
CREATE OR REPLACE FUNCTION template_twin_verify_release_actor(
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
SET search_path = pg_catalog, public
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
REVOKE ALL ON FUNCTION template_twin_verify_release_actor(TEXT, TEXT)
  FROM PUBLIC;

CREATE TABLE "template_twin_release_action_receipts" (
  "nonce" UUID NOT NULL,
  "transactionId" BIGINT NOT NULL,
  "backendPid" INTEGER NOT NULL,
  "releaseId" UUID NOT NULL,
  "checkpointId" UUID,
  "action" VARCHAR(16) NOT NULL,
  "discipline" VARCHAR(32),
  "decision" VARCHAR(16),
  "actorId" TEXT NOT NULL,
  "actorSessionSha256" CHAR(64) NOT NULL,
  "confirmationSha256" CHAR(64) NOT NULL,
  "issuedAt" TIMESTAMPTZ(6) NOT NULL,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_release_action_receipts_pkey" PRIMARY KEY ("nonce"),
  CONSTRAINT "template_twin_release_action_receipt_scope_key" UNIQUE (
    "transactionId", "backendPid", "releaseId", "action", "checkpointId"
  ),
  CONSTRAINT "template_twin_release_action_receipt_shape" CHECK (
    "action" IN ('FREEZE', 'APPROVAL', 'ACTIVATE', 'PASS')
    AND "actorSessionSha256" ~ '^[0-9a-f]{64}$'
    AND "confirmationSha256" ~ '^[0-9a-f]{64}$'
    AND "expiresAt" > "issuedAt"
    AND (("action" = 'APPROVAL') = (
      "discipline" IS NOT NULL AND "decision" IS NOT NULL
    ))
    AND (("action" IN ('ACTIVATE', 'PASS')) = ("checkpointId" IS NOT NULL))
  ),
  CONSTRAINT "template_twin_release_action_receipt_release_fkey"
    FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT "template_twin_release_action_receipt_checkpoint_fkey"
    FOREIGN KEY ("checkpointId") REFERENCES "template_twin_release_checkpoints"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT "template_twin_release_action_receipt_actor_fkey"
    FOREIGN KEY ("actorId") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT
);
REVOKE ALL ON "template_twin_release_action_receipts" FROM PUBLIC;
CREATE OR REPLACE FUNCTION template_twin_reject_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin protected receipt history is append-only';
END;
$$;
CREATE TRIGGER template_twin_release_action_receipt_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_action_receipts"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_append_only_mutation();
CREATE TRIGGER template_twin_release_action_receipt_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_action_receipts"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_append_only_mutation();

ALTER TABLE "template_twin_release_candidates"
  ADD CONSTRAINT "template_twin_release_freeze_action_receipt_key"
    UNIQUE ("freezeActionReceiptNonce"),
  ADD CONSTRAINT "template_twin_release_freeze_action_receipt_fkey"
    FOREIGN KEY ("freezeActionReceiptNonce")
    REFERENCES "template_twin_release_action_receipts"("nonce")
    ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "template_twin_release_approval_decisions"
  ADD CONSTRAINT "template_twin_release_approval_action_receipt_key"
    UNIQUE ("actionReceiptNonce"),
  ADD CONSTRAINT "template_twin_release_approval_action_receipt_fkey"
    FOREIGN KEY ("actionReceiptNonce")
    REFERENCES "template_twin_release_action_receipts"("nonce")
    ON DELETE RESTRICT ON UPDATE RESTRICT;
ALTER TABLE "template_twin_release_checkpoints"
  ADD CONSTRAINT "template_twin_release_checkpoint_activation_receipt_key"
    UNIQUE ("activationActionReceiptNonce"),
  ADD CONSTRAINT "template_twin_release_checkpoint_activation_receipt_fkey"
    FOREIGN KEY ("activationActionReceiptNonce")
    REFERENCES "template_twin_release_action_receipts"("nonce")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  ADD CONSTRAINT "template_twin_release_checkpoint_pass_receipt_key"
    UNIQUE ("passActionReceiptNonce"),
  ADD CONSTRAINT "template_twin_release_checkpoint_pass_receipt_fkey"
    FOREIGN KEY ("passActionReceiptNonce")
    REFERENCES "template_twin_release_action_receipts"("nonce")
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE OR REPLACE FUNCTION template_twin_issue_release_action_receipt(
  actor_user_id TEXT,
  actor_session_token TEXT,
  candidate_id UUID,
  checkpoint_id UUID,
  action_name TEXT,
  approval_discipline TEXT,
  approval_decision TEXT,
  exact_confirmation TEXT
)
RETURNS TABLE (
  "nonce" UUID,
  "userId" TEXT,
  "email" TEXT,
  "practiceId" TEXT,
  "sessionSha256" TEXT,
  "issuedAt" TIMESTAMPTZ(6)
)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  actor RECORD;
  candidate RECORD;
  checkpoint RECORD;
  expected_confirmation TEXT;
  receipt_nonce UUID := gen_random_uuid();
  now_at TIMESTAMPTZ := clock_timestamp();
BEGIN
  SELECT verified.* INTO actor
  FROM public.template_twin_verify_release_actor(
    actor_user_id, actor_session_token
  ) verified;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'A live MFA release actor session is required';
  END IF;
  SELECT release."id", release."releaseIdentitySha256", release."status"
    INTO candidate
  FROM public."template_twin_release_candidates" release
  WHERE release."id" = candidate_id FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin release action candidate is unavailable';
  END IF;

  IF action_name = 'FREEZE' THEN
    IF checkpoint_id IS NOT NULL OR approval_discipline IS NOT NULL
      OR approval_decision IS NOT NULL OR candidate."status" <> 'DRAFT'
    THEN
      RAISE EXCEPTION 'Template Twin freeze receipt scope is invalid';
    END IF;
    expected_confirmation := 'FREEZE ' ||
      left(candidate."releaseIdentitySha256", 12);
  ELSIF action_name = 'APPROVAL' THEN
    IF checkpoint_id IS NOT NULL
      OR approval_discipline NOT IN (
        'DESKTOP_WORD', 'CLINICAL_SAFETY', 'PRIVACY_LEGAL', 'OPERATIONS'
      ) OR approval_decision NOT IN ('APPROVE', 'REJECT', 'REVOKE')
      OR candidate."status" NOT IN (
        'FROZEN', 'APPROVED', 'ROLLING_OUT', 'STABLE_100'
      )
    THEN
      RAISE EXCEPTION 'Template Twin approval receipt scope is invalid';
    END IF;
    expected_confirmation := approval_decision || ' ' || approval_discipline ||
      ' ' || left(candidate."releaseIdentitySha256", 12);
  ELSIF action_name IN ('ACTIVATE', 'PASS') THEN
    IF approval_discipline IS NOT NULL OR approval_decision IS NOT NULL
      OR checkpoint_id IS NULL
    THEN
      RAISE EXCEPTION 'Template Twin checkpoint receipt scope is invalid';
    END IF;
    SELECT cp."stage", cp."releaseId" INTO checkpoint
    FROM public."template_twin_release_checkpoints" cp
    WHERE cp."id" = checkpoint_id AND cp."releaseId" = candidate_id
    FOR SHARE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Template Twin checkpoint receipt target is unavailable';
    END IF;
    expected_confirmation := action_name || ' ' || checkpoint."stage" || ' ' ||
      left(candidate."releaseIdentitySha256", 12);
  ELSE
    RAISE EXCEPTION 'Template Twin release action is unsupported';
  END IF;
  IF exact_confirmation IS DISTINCT FROM expected_confirmation THEN
    RAISE EXCEPTION 'Template Twin release action exact confirmation is invalid';
  END IF;

  INSERT INTO public."template_twin_release_action_receipts" (
    "nonce", "transactionId", "backendPid", "releaseId", "checkpointId",
    "action", "discipline", "decision", "actorId", "actorSessionSha256",
    "confirmationSha256", "issuedAt", "expiresAt"
  ) VALUES (
    receipt_nonce, txid_current(), pg_backend_pid(), candidate_id, checkpoint_id,
    action_name, approval_discipline, approval_decision, actor."userId",
    actor."sessionSha256", encode(digest(exact_confirmation, 'sha256'), 'hex'),
    now_at, now_at + INTERVAL '2 minutes'
  );
  RETURN QUERY SELECT receipt_nonce, actor."userId"::TEXT, actor."email"::TEXT,
    actor."practiceId"::TEXT, actor."sessionSha256"::TEXT, now_at;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_issue_release_action_receipt(
  TEXT, TEXT, UUID, UUID, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_guard_release_checkpoint_history()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  receipt RECORD;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin checkpoint history cannot be deleted';
  END IF;
  IF ROW(
    NEW."id", NEW."releaseId", NEW."releaseIdentitySha256", NEW."stage",
    NEW."ordinal", NEW."targetPercent", NEW."targetPhysicianCount",
    NEW."assignedPhysicianCount", NEW."minimumBakeSeconds", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."id", OLD."releaseId", OLD."releaseIdentitySha256", OLD."stage",
    OLD."ordinal", OLD."targetPercent", OLD."targetPhysicianCount",
    OLD."assignedPhysicianCount", OLD."minimumBakeSeconds", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint identity is immutable';
  END IF;
  IF NOT (
    (OLD."status" = 'PENDING' AND NEW."status" = 'ACTIVE')
    OR (OLD."status" = 'ACTIVE' AND NEW."status" IN ('PASSED', 'FAILED', 'REVOKED'))
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint state transition is invalid';
  END IF;

  IF OLD."status" = 'PENDING' THEN
    IF NEW."activatedPhysicianCount" IS NULL OR NEW."activatedById" IS NULL
      OR NEW."activationOutboxEventKey" IS NULL
      OR NEW."activationActionReceiptNonce" IS NULL
      OR NEW."passedPhysicianCount" IS NOT NULL OR NEW."passedAt" IS NOT NULL
      OR NEW."passedById" IS NOT NULL OR NEW."passOutboxEventKey" IS NOT NULL
      OR NEW."passActionReceiptNonce" IS NOT NULL OR NEW."revokedAt" IS NOT NULL
    THEN
      RAISE EXCEPTION 'Template Twin checkpoint activation receipt is missing or invalid';
    END IF;
    SELECT action_receipt.* INTO receipt
    FROM public."template_twin_release_action_receipts" action_receipt
    WHERE action_receipt."nonce" = NEW."activationActionReceiptNonce"
      AND action_receipt."transactionId" = txid_current()
      AND action_receipt."backendPid" = pg_backend_pid()
      AND action_receipt."releaseId" = NEW."releaseId"
      AND action_receipt."checkpointId" = NEW."id"
      AND action_receipt."action" = 'ACTIVATE'
      AND action_receipt."actorId" = NEW."activatedById"
      AND action_receipt."expiresAt" > clock_timestamp();
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Template Twin checkpoint activation receipt is missing or invalid';
    END IF;
    NEW."activatedAt" := receipt."issuedAt";
    NEW."earliestPassAt" := receipt."issuedAt" +
      NEW."minimumBakeSeconds" * INTERVAL '1 second';
  ELSE
    IF ROW(
      NEW."activatedPhysicianCount", NEW."activatedAt", NEW."earliestPassAt",
      NEW."activatedById", NEW."activationOutboxEventKey",
      NEW."activationActionReceiptNonce"
    ) IS DISTINCT FROM ROW(
      OLD."activatedPhysicianCount", OLD."activatedAt", OLD."earliestPassAt",
      OLD."activatedById", OLD."activationOutboxEventKey",
      OLD."activationActionReceiptNonce"
    ) THEN
      RAISE EXCEPTION 'Template Twin checkpoint activation evidence is immutable';
    END IF;
    IF NEW."status" = 'PASSED' THEN
      IF NEW."passedPhysicianCount" IS NULL
        OR NEW."passedById" IS NULL OR NEW."passOutboxEventKey" IS NULL
        OR NEW."passActionReceiptNonce" IS NULL OR NEW."revokedAt" IS NOT NULL
      THEN
        RAISE EXCEPTION 'Template Twin checkpoint pass action receipt is missing or invalid';
      END IF;
      SELECT action_receipt.* INTO receipt
      FROM public."template_twin_release_action_receipts" action_receipt
      WHERE action_receipt."nonce" = NEW."passActionReceiptNonce"
        AND action_receipt."transactionId" = txid_current()
        AND action_receipt."backendPid" = pg_backend_pid()
        AND action_receipt."releaseId" = NEW."releaseId"
        AND action_receipt."checkpointId" = NEW."id"
        AND action_receipt."action" = 'PASS'
        AND action_receipt."actorId" = NEW."passedById"
        AND action_receipt."expiresAt" > clock_timestamp();
      IF NOT FOUND THEN
        RAISE EXCEPTION 'Template Twin checkpoint pass action receipt is missing or invalid';
      END IF;
      NEW."passedAt" := receipt."issuedAt";
    ELSIF NEW."passedPhysicianCount" IS NOT NULL OR NEW."passedAt" IS NOT NULL
      OR NEW."passedById" IS NOT NULL OR NEW."passOutboxEventKey" IS NOT NULL
      OR NEW."passActionReceiptNonce" IS NOT NULL
      OR (NEW."status" = 'REVOKED' AND NEW."revokedAt" IS NULL)
    THEN
      RAISE EXCEPTION 'Template Twin terminal checkpoint evidence is invalid';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_guard_release_checkpoint_history()
  FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_issue_release_capability(
  candidate_id UUID,
  candidate_identity CHAR(64),
  active_checkpoint_id UUID,
  expected_release_generation BIGINT,
  expected_global_generation BIGINT
)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  capability_nonce UUID := gen_random_uuid();
  stage_ordinal INTEGER;
BEGIN
  PERFORM pg_advisory_xact_lock(73119, 20260719);
  SELECT checkpoint."ordinal" INTO stage_ordinal
  FROM public."template_twin_release_candidates" candidate
  JOIN public."template_twin_release_checkpoints" checkpoint
    ON checkpoint."releaseId" = candidate."id"
  WHERE candidate."id" = candidate_id
    AND candidate."releaseIdentitySha256" = candidate_identity
    AND candidate."status" = 'ROLLING_OUT'
    AND candidate."generation" = expected_release_generation
    AND checkpoint."id" = active_checkpoint_id
    AND checkpoint."releaseIdentitySha256" = candidate_identity
    AND checkpoint."status" = 'ACTIVE'
    AND EXISTS (
      SELECT 1 FROM public."template_twin_release_action_receipts" receipt
      WHERE receipt."nonce" = checkpoint."activationActionReceiptNonce"
        AND receipt."transactionId" = txid_current()
        AND receipt."backendPid" = pg_backend_pid()
        AND receipt."releaseId" = candidate_id
        AND receipt."checkpointId" = active_checkpoint_id
        AND receipt."action" = 'ACTIVATE'
        AND receipt."actorId" = checkpoint."activatedById"
        AND receipt."expiresAt" > clock_timestamp()
    );
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin release capability action identity is stale';
  END IF;
  IF NOT public.template_twin_release_approvals_are_current(
    candidate_id, candidate_identity
  ) THEN
    RAISE EXCEPTION 'Template Twin release approvals are incomplete or stale';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public."template_twin_rollout_controls"
    WHERE "id" = 'global'
      AND "generation" = expected_global_generation
      AND "rollbackFenceState" = 'OPEN'
      AND "rollbackOperationId" IS NULL
  ) THEN
    RAISE EXCEPTION 'Template Twin global rollout identity is stale or fenced';
  END IF;
  INSERT INTO public."template_twin_release_capabilities" (
    "nonce", "transactionId", "backendPid", "releaseId",
    "releaseIdentitySha256", "checkpointId", "stageOrdinal",
    "releaseGeneration", "expectedGlobalGeneration", "expiresAt"
  ) VALUES (
    capability_nonce, txid_current(), pg_backend_pid(), candidate_id,
    candidate_identity, active_checkpoint_id, stage_ordinal,
    expected_release_generation, expected_global_generation,
    clock_timestamp() + INTERVAL '5 minutes'
  );
  PERFORM set_config(
    'meddoc.template_twin_release_capability', capability_nonce::TEXT, TRUE
  );
  RETURN capability_nonce;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_issue_release_capability(
  UUID, CHAR(64), UUID, BIGINT, BIGINT
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_release_approvals_are_current(
  candidate_id UUID,
  candidate_identity CHAR(64)
)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  WITH latest AS (
    SELECT DISTINCT ON (decision."discipline")
      decision."discipline", decision."decision",
      decision."authorityAssignmentId", decision."actorId",
      decision."actorSessionSha256", decision."actionReceiptNonce",
      decision."decidedAt"
    FROM "template_twin_release_approval_decisions" decision
    WHERE decision."releaseId" = candidate_id
      AND decision."releaseIdentitySha256" = candidate_identity
    ORDER BY decision."discipline", decision."decidedAt" DESC, decision."id" DESC
  )
  SELECT COUNT(*) = 4
    AND COUNT(DISTINCT latest."actorId") = 4
    AND BOOL_AND(
      latest."decision" = 'APPROVE'
      AND EXISTS (
        SELECT 1 FROM "template_twin_release_authorities" authority
        JOIN "users" account ON account."id" = authority."userId"
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
          AND account."mfaVerifiedAt" IS NOT NULL
          AND 'SUPER_ADMIN'::"Product" = ANY(account."products")
          AND EXISTS (
            SELECT 1 FROM "template_twin_release_action_receipts" receipt
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
REVOKE ALL ON FUNCTION template_twin_release_approvals_are_current(
  UUID, CHAR(64)
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_guard_release_approval_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
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
  FROM "template_twin_release_candidates"
  WHERE "id" = NEW."releaseId";
  IF NOT FOUND OR release_state NOT IN ('FROZEN', 'APPROVED', 'ROLLING_OUT', 'STABLE_100') THEN
    RAISE EXCEPTION 'Template Twin release is not open for a human decision';
  END IF;
  IF NEW."releaseIdentitySha256" <> release_identity
    OR NEW."confirmation" <> NEW."decision" || ' ' || NEW."discipline" || ' ' || left(release_identity, 12)
  THEN
    RAISE EXCEPTION 'Template Twin approval identity or exact confirmation is invalid';
  END IF;
  IF NEW."actorId" = release_creator OR NEW."actorId" = release_finalizer THEN
    RAISE EXCEPTION 'Template Twin release creator/finalizer cannot approve the release';
  END IF;
  IF release_state IN ('ROLLING_OUT', 'STABLE_100') AND NEW."decision" = 'APPROVE' THEN
    RAISE EXCEPTION 'Template Twin approvals cannot be refreshed after rollout begins';
  END IF;
  SELECT action_receipt.* INTO receipt
  FROM "template_twin_release_action_receipts" action_receipt
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
    SELECT 1 FROM "template_twin_release_authorities" authority
    JOIN "users" account ON account."id" = authority."userId"
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
      AND account."mfaVerifiedAt" IS NOT NULL
      AND 'SUPER_ADMIN'::"Product" = ANY(account."products")
  ) THEN
    RAISE EXCEPTION 'Template Twin live human authority is missing or revoked';
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_guard_release_approval_insert()
  FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_guard_release_authority_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin release authority history cannot be deleted';
  END IF;
  IF ROW(
    NEW."id", NEW."userId", NEW."discipline", NEW."sourceRef",
    NEW."effectiveAt", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."id", OLD."userId", OLD."discipline", OLD."sourceRef",
    OLD."effectiveAt", OLD."createdAt"
  ) OR OLD."revokedAt" IS NOT NULL OR NEW."revokedAt" IS NULL
    OR current_setting('meddoc.template_twin_authority_revocation', TRUE)
      IS DISTINCT FROM OLD."id"::TEXT
  THEN
    RAISE EXCEPTION 'Use the atomic Template Twin authority-revocation procedure';
  END IF;
  RETURN NEW;
END;
$$;

DROP FUNCTION IF EXISTS template_twin_revoke_release_authority(
  UUID, TEXT, TEXT, TEXT
);
CREATE FUNCTION template_twin_revoke_release_authority(
  authority_id UUID,
  operator_actor_id TEXT,
  operator_session_token TEXT,
  change_id TEXT,
  reason_code TEXT
)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  authority RECORD;
  candidate RECORD;
  checkpoint RECORD;
  practice_row RECORD;
  operator_email TEXT;
  audit_practice_id TEXT;
  next_global_generation BIGINT;
  next_practice_generation BIGINT;
  now_at TIMESTAMPTZ := clock_timestamp();
BEGIN
  IF change_id !~ '^[A-Z0-9][A-Z0-9_-]{2,79}$'
    OR reason_code !~ '^[A-Z][A-Z0-9_]{2,79}$'
  THEN
    RAISE EXCEPTION 'Template Twin authority revocation identity is invalid';
  END IF;
  PERFORM pg_advisory_xact_lock(73119, 20260719);
  PERFORM 1 FROM public."template_twin_rollout_controls"
    WHERE "id" = 'global' FOR UPDATE;
  SELECT assignment.* INTO authority
  FROM public."template_twin_release_authorities" assignment
  WHERE assignment."id" = authority_id FOR UPDATE;
  IF NOT FOUND OR authority."revokedAt" IS NOT NULL THEN
    RAISE EXCEPTION 'Template Twin authority is missing or already revoked';
  END IF;

  IF operator_actor_id IS NOT NULL THEN
    SELECT actor."email", actor."practiceId"
      INTO operator_email, audit_practice_id
    FROM public.template_twin_verify_release_actor(
      operator_actor_id, operator_session_token
    ) actor;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'A live MFA platform administrator must revoke authority';
    END IF;
  ELSIF operator_session_token IS NOT NULL THEN
    RAISE EXCEPTION 'Automated authority revocation cannot carry an operator token';
  ELSE
    SELECT account."practiceId" INTO audit_practice_id
    FROM public."users" account WHERE account."id" = authority."userId";
  END IF;

  SELECT release.* INTO candidate
  FROM public."template_twin_release_candidates" release
  JOIN public."template_twin_release_approval_decisions" decision
    ON decision."releaseId" = release."id"
  WHERE release."status" IN ('APPROVED', 'ROLLING_OUT', 'STABLE_100')
    AND decision."authorityAssignmentId" = authority_id
    AND decision."id" = (
      SELECT latest."id"
      FROM public."template_twin_release_approval_decisions" latest
      WHERE latest."releaseId" = release."id"
        AND latest."discipline" = decision."discipline"
      ORDER BY latest."decidedAt" DESC, latest."id" DESC LIMIT 1
    )
  FOR UPDATE OF release;

  IF FOUND THEN
    INSERT INTO public."template_twin_audit_outbox" (
      "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
      "action", "targetId", "targetType", "metadata", "status",
      "attemptCount", "updatedAt"
    ) VALUES (
      gen_random_uuid()::TEXT, audit_practice_id, operator_actor_id,
      operator_email,
      'template-twin:release:' || candidate."id"::TEXT ||
        ':revoked:authority:' || change_id,
      'TEMPLATE_TWIN_RELEASE_REVOKED'::public."AuditAction",
      candidate."id"::TEXT, 'TemplateTwinReleaseCandidate',
      jsonb_build_object(
        'releaseIdentitySha256', candidate."releaseIdentitySha256",
        'reasonCode', reason_code, 'changeId', change_id,
        'authorityAssignmentId', authority_id::TEXT,
        'previousReleaseGeneration', candidate."generation"::TEXT
      ), 'PENDING', 0, CURRENT_TIMESTAMP
    );

    SELECT "generation" + 1 INTO next_global_generation
    FROM public."template_twin_rollout_controls" WHERE "id" = 'global';
    UPDATE public."template_twin_rollout_controls"
    SET "enabled" = FALSE, "generation" = next_global_generation,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "id" = 'global';
    INSERT INTO public."template_twin_audit_outbox" (
      "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
      "action", "targetId", "targetType", "metadata", "status",
      "attemptCount", "updatedAt"
    ) VALUES (
      gen_random_uuid()::TEXT, audit_practice_id, operator_actor_id,
      operator_email, 'template-twin:global-rollout:' || next_global_generation::TEXT,
      'TEMPLATE_TWIN_DEACTIVATED'::public."AuditAction", 'global',
      'TemplateTwinRolloutControl', jsonb_build_object(
        'scope', 'global', 'enabled', FALSE, 'reasonCode', reason_code,
        'generation', next_global_generation::TEXT
      ), 'PENDING', 0, CURRENT_TIMESTAMP
    ) ON CONFLICT ("eventKey") DO NOTHING;

    FOR practice_row IN
      SELECT practice."id", practice."templateTwinRolloutGeneration"
      FROM public."template_twin_release_practices" manifest
      JOIN public."practices" practice ON practice."id" = manifest."practiceId"
      WHERE manifest."releaseId" = candidate."id"
        AND practice."templateTwinEnabled" = TRUE
      ORDER BY practice."id" FOR UPDATE OF practice
    LOOP
      next_practice_generation := practice_row."templateTwinRolloutGeneration" + 1;
      UPDATE public."practices"
      SET "templateTwinEnabled" = FALSE,
          "templateTwinRolloutGeneration" = next_practice_generation,
          "updatedAt" = CURRENT_TIMESTAMP
      WHERE "id" = practice_row."id";
      INSERT INTO public."template_twin_audit_outbox" (
        "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
        "action", "targetId", "targetType", "metadata", "status",
        "attemptCount", "updatedAt"
      ) VALUES (
        gen_random_uuid()::TEXT, practice_row."id", operator_actor_id,
        operator_email,
        'template-twin:practice-rollout:' || practice_row."id" || ':' || next_practice_generation::TEXT,
        'TEMPLATE_TWIN_DEACTIVATED'::public."AuditAction",
        practice_row."id", 'Practice', jsonb_build_object(
          'scope', 'practice', 'enabled', FALSE, 'reasonCode', reason_code,
          'generation', next_practice_generation::TEXT
        ), 'PENDING', 0, CURRENT_TIMESTAMP
      ) ON CONFLICT ("eventKey") DO NOTHING;
    END LOOP;

    SELECT cp.* INTO checkpoint
    FROM public."template_twin_release_checkpoints" cp
    WHERE cp."releaseId" = candidate."id" AND cp."status" = 'ACTIVE'
    FOR UPDATE;
    IF FOUND THEN
      UPDATE public."template_twin_release_checkpoints"
      SET "status" = 'REVOKED', "revokedAt" = now_at,
          "updatedAt" = CURRENT_TIMESTAMP
      WHERE "id" = checkpoint."id";
    END IF;
    UPDATE public."template_twin_release_candidates"
    SET "status" = 'REVOKED', "generation" = "generation" + 1,
        "updatedAt" = CURRENT_TIMESTAMP
    WHERE "id" = candidate."id";
  END IF;

  PERFORM set_config(
    'meddoc.template_twin_authority_revocation', authority_id::TEXT, TRUE
  );
  UPDATE public."template_twin_release_authorities"
  SET "revokedAt" = now_at WHERE "id" = authority_id;
  INSERT INTO public."template_twin_audit_outbox" (
    "id", "practiceId", "actorId", "actorEmailSnapshot", "eventKey",
    "action", "targetId", "targetType", "metadata", "status",
    "attemptCount", "updatedAt"
  ) VALUES (
    gen_random_uuid()::TEXT, audit_practice_id, operator_actor_id,
    operator_email,
    'template-twin:release-authority:' || authority_id::TEXT || ':revoked:' || change_id,
    'TEMPLATE_TWIN_RELEASE_REVOKED'::public."AuditAction", authority_id::TEXT,
    'TemplateTwinReleaseAuthority', jsonb_build_object(
      'reasonCode', reason_code, 'changeId', change_id,
      'discipline', authority."discipline"
    ), 'PENDING', 0, CURRENT_TIMESTAMP
  );
END;
$$;
REVOKE ALL ON FUNCTION template_twin_revoke_release_authority(
  UUID, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION template_twin_revoke_release_authority(
  UUID, TEXT, TEXT, TEXT, TEXT
) TO quillmd_release_security;

CREATE OR REPLACE FUNCTION template_twin_revoke_authority_on_user_lifecycle()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  assignment RECORD;
  lifecycle_change_id TEXT;
BEGIN
  IF (
    NEW."isActive" = FALSE OR NEW."deactivatedAt" IS NOT NULL
    OR NEW."suspendedAt" IS NOT NULL OR NEW."softDeletedAt" IS NOT NULL
    OR NEW."mfaEnabled" = FALSE OR NEW."mfaVerifiedAt" IS NULL
    OR NEW."forceLogoutAt" IS DISTINCT FROM OLD."forceLogoutAt"
  ) THEN
    lifecycle_change_id := 'USER_LIFECYCLE_' || upper(substr(md5(
      txid_current()::TEXT || ':' || OLD."id"
    ), 1, 24));
    FOR assignment IN
      SELECT "id" FROM "template_twin_release_authorities"
      WHERE "userId" = OLD."id" AND "revokedAt" IS NULL
      ORDER BY "id"
    LOOP
      PERFORM template_twin_revoke_release_authority(
        assignment."id", NULL, NULL, lifecycle_change_id,
        'AUTHORITY_USER_LIFECYCLE'
      );
    END LOOP;
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_revoke_authority_on_user_lifecycle()
  FROM PUBLIC;
CREATE OR REPLACE FUNCTION template_twin_lock_practice_release_statement()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(73119, 20260719);
  RETURN NULL;
END;
$$;
CREATE TRIGGER aaa_template_twin_user_lifecycle_statement_lock
BEFORE UPDATE OF "isActive", "deactivatedAt", "suspendedAt", "softDeletedAt",
  "mfaEnabled", "mfaVerifiedAt", "forceLogoutAt" ON "users"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_practice_release_statement();
CREATE TRIGGER template_twin_user_lifecycle_authority_revoke
BEFORE UPDATE OF "isActive", "deactivatedAt", "suspendedAt", "softDeletedAt",
  "mfaEnabled", "mfaVerifiedAt", "forceLogoutAt" ON "users"
FOR EACH ROW EXECUTE FUNCTION template_twin_revoke_authority_on_user_lifecycle();

-- Close the practice INSERT path and fail closed on tenant deactivation.
CREATE OR REPLACE FUNCTION template_twin_guard_practice_release_enable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."templateTwinEnabled" = TRUE AND (
    TG_OP = 'INSERT' OR OLD."templateTwinEnabled" = FALSE
  ) THEN
    IF NEW."isActive" <> TRUE THEN
      RAISE EXCEPTION 'An inactive practice cannot enable Template Twin';
    END IF;
    PERFORM template_twin_require_release_capability('practice', NEW."id");
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER aab_template_twin_practice_release_insert_capability_guard
BEFORE INSERT ON "practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_practice_release_enable();

CREATE OR REPLACE FUNCTION template_twin_lock_practice_release_statement()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(73119, 20260719);
  RETURN NULL;
END;
$$;
CREATE TRIGGER aaa_template_twin_practice_insert_statement_lock
BEFORE INSERT ON "practices"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_practice_release_statement();
CREATE TRIGGER aaa_template_twin_practice_update_statement_lock
BEFORE UPDATE OF "templateTwinEnabled", "isActive" ON "practices"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_practice_release_statement();

CREATE OR REPLACE FUNCTION template_twin_disable_on_practice_deactivation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  next_generation BIGINT;
BEGIN
  IF OLD."isActive" = TRUE AND NEW."isActive" = FALSE
    AND OLD."templateTwinEnabled" = TRUE
  THEN
    NEW."templateTwinEnabled" := FALSE;
    NEW."templateTwinRolloutGeneration" := OLD."templateTwinRolloutGeneration" + 1;
    next_generation := NEW."templateTwinRolloutGeneration";
    INSERT INTO "template_twin_audit_outbox" (
      "id", "practiceId", "actorId", "eventKey", "action", "targetId",
      "targetType", "metadata", "status", "attemptCount", "updatedAt"
    ) VALUES (
      gen_random_uuid()::TEXT, NEW."id", NULL,
      'template-twin:practice-rollout:' || NEW."id" || ':' || next_generation::TEXT,
      'TEMPLATE_TWIN_DEACTIVATED'::"AuditAction", NEW."id", 'Practice',
      jsonb_build_object(
        'scope', 'practice', 'enabled', FALSE,
        'reasonCode', 'PRACTICE_DEACTIVATED',
        'previousGeneration', OLD."templateTwinRolloutGeneration"::TEXT,
        'generation', next_generation::TEXT
      ), 'PENDING', 0, CURRENT_TIMESTAMP
    );
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER aaa_template_twin_practice_deactivation_guard
BEFORE UPDATE OF "isActive" ON "practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_disable_on_practice_deactivation();

CREATE CONSTRAINT TRIGGER template_twin_release_practice_flag_insert_coupling_guard
AFTER INSERT ON "practices"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();

-- Protect actual global/practice exposure receipts as release evidence too.
CREATE OR REPLACE FUNCTION template_twin_is_release_audit_identity(event_key TEXT)
RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
  SELECT event_key ~ '^template-twin:release:[0-9a-fA-F-]{36}:'
    OR event_key ~ '^template-twin:release-authority:[0-9a-fA-F-]{36}:'
    OR event_key ~ '^template-twin:global-rollout:[0-9]+$'
    OR event_key ~ '^template-twin:practice-rollout:[A-Za-z0-9_-]+:';
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_release_outbox_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  owner_name TEXT;
  practice_id TEXT;
  generation_text TEXT;
BEGIN
  IF NOT public.template_twin_is_release_audit_identity(NEW."eventKey") THEN
    RETURN NEW;
  END IF;
  NEW."createdAt" := clock_timestamp();
  NEW."updatedAt" := NEW."createdAt";
  SELECT pg_get_userbyid(object.relowner) INTO owner_name
  FROM pg_catalog.pg_class object
  WHERE object.oid = 'public.template_twin_audit_outbox'::regclass;
  IF current_user = owner_name
    OR pg_has_role(current_user, 'quillmd_release_control', 'MEMBER')
    OR pg_has_role(current_user, 'quillmd_release_security', 'MEMBER')
  THEN
    RETURN NEW;
  END IF;
  IF NOT pg_has_role(current_user, 'quillmd_runtime', 'MEMBER')
    OR NEW."action"::TEXT <> 'TEMPLATE_TWIN_DEACTIVATED'
  THEN
    RAISE EXCEPTION 'Template Twin reserved audit identities require release authority';
  END IF;

  IF NEW."eventKey" ~ '^template-twin:global-rollout:[0-9]+$' THEN
    SELECT substring(
      NEW."eventKey" FROM '^template-twin:global-rollout:([0-9]+)$'
    ) INTO generation_text;
    IF NEW."targetType" <> 'TemplateTwinRolloutControl'
      OR NEW."targetId" <> 'global'
      OR NEW."metadata"->>'scope' <> 'global'
      OR COALESCE((NEW."metadata"->>'enabled')::BOOLEAN, TRUE) <> FALSE
      OR NEW."metadata"->>'generation' <> generation_text
      OR NOT EXISTS (
        SELECT 1 FROM public."template_twin_rollout_controls" control
        WHERE control."id" = 'global' AND control."enabled" = FALSE
          AND control."generation"::TEXT = generation_text
      )
    THEN
      RAISE EXCEPTION 'Template Twin runtime global-disable audit receipt is invalid';
    END IF;
    RETURN NEW;
  END IF;

  IF NEW."eventKey" ~
    '^template-twin:practice-rollout:[A-Za-z0-9_-]+:[0-9]+$'
  THEN
    SELECT parts[1], parts[2] INTO practice_id, generation_text
    FROM regexp_match(
      NEW."eventKey",
      '^template-twin:practice-rollout:([A-Za-z0-9_-]+):([0-9]+)$'
    ) parts;
    IF NEW."targetType" <> 'Practice' OR NEW."targetId" <> practice_id
      OR NEW."practiceId" <> practice_id
      OR NEW."metadata"->>'scope' <> 'practice'
      OR COALESCE((NEW."metadata"->>'enabled')::BOOLEAN, TRUE) <> FALSE
      OR NEW."metadata"->>'generation' <> generation_text
      OR NOT EXISTS (
        SELECT 1 FROM public."practices" practice
        WHERE practice."id" = practice_id
          AND practice."templateTwinEnabled" = FALSE
          AND practice."templateTwinRolloutGeneration"::TEXT = generation_text
      )
    THEN
      RAISE EXCEPTION 'Template Twin runtime practice-disable audit receipt is invalid';
    END IF;
    RETURN NEW;
  END IF;

  RAISE EXCEPTION 'Template Twin runtime cannot reserve release-control audit identities';
END;
$$;
REVOKE ALL ON FUNCTION template_twin_guard_release_outbox_insert()
  FROM PUBLIC;
CREATE TRIGGER aaa_template_twin_release_outbox_insert_authority_guard
BEFORE INSERT ON "template_twin_audit_outbox"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_outbox_insert();

CREATE OR REPLACE FUNCTION template_twin_guard_release_outbox_history()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  relevant BOOLEAN;
  owner_name TEXT;
  delivery_timestamp TIMESTAMPTZ;
BEGIN
  relevant := CASE TG_OP
    WHEN 'INSERT' THEN template_twin_is_release_audit_identity(NEW."eventKey")
    WHEN 'DELETE' THEN template_twin_is_release_audit_identity(OLD."eventKey")
    ELSE template_twin_is_release_audit_identity(OLD."eventKey")
      OR template_twin_is_release_audit_identity(NEW."eventKey")
  END;
  IF NOT relevant THEN
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin release audit outbox evidence cannot be deleted';
  END IF;
  IF TG_OP = 'UPDATE' THEN
    SELECT pg_get_userbyid(object.relowner) INTO owner_name
    FROM pg_class object
    WHERE object.oid = 'public.template_twin_audit_outbox'::regclass;
    IF current_user <> owner_name
      AND NOT pg_has_role(current_user, 'quillmd_audit_dispatcher', 'MEMBER')
    THEN
      RAISE EXCEPTION 'Template Twin release audit delivery requires the isolated dispatcher';
    END IF;
    IF ROW(
      NEW."id", NEW."practiceId", NEW."actorId", NEW."actorEmailSnapshot",
      NEW."ipAddress", NEW."userAgent", NEW."eventKey", NEW."action",
      NEW."targetId", NEW."targetType", NEW."metadata", NEW."createdAt"
    ) IS DISTINCT FROM ROW(
      OLD."id", OLD."practiceId", OLD."actorId", OLD."actorEmailSnapshot",
      OLD."ipAddress", OLD."userAgent", OLD."eventKey", OLD."action",
      OLD."targetId", OLD."targetType", OLD."metadata", OLD."createdAt"
    ) THEN
      RAISE EXCEPTION 'Template Twin release audit identity is immutable';
    END IF;
    IF OLD."status" = 'DELIVERED' AND ROW(
      NEW."status", NEW."attemptCount", NEW."availableAt", NEW."deliveredAt",
      NEW."lastErrorCode", NEW."updatedAt"
    ) IS DISTINCT FROM ROW(
      OLD."status", OLD."attemptCount", OLD."availableAt", OLD."deliveredAt",
      OLD."lastErrorCode", OLD."updatedAt"
    ) THEN
      RAISE EXCEPTION 'Template Twin delivered release receipt is immutable';
    END IF;
    IF NEW."status" = 'DELIVERED' AND OLD."status" <> 'DELIVERED' THEN
      SELECT log."timestamp" INTO delivery_timestamp
      FROM public."audit_logs" log
      WHERE log."templateTwinOutboxEventKey" = NEW."eventKey"
        AND log."action" = NEW."action"
        AND log."targetType" IS NOT DISTINCT FROM NEW."targetType"
        AND log."targetId" IS NOT DISTINCT FROM NEW."targetId"
        AND log."practiceId" = NEW."practiceId"
        AND log."userId" IS NOT DISTINCT FROM NEW."actorId"
        AND log."userEmailSnapshot" IS NOT DISTINCT FROM
          NEW."actorEmailSnapshot"
        AND log."ipAddress" IS NOT DISTINCT FROM NEW."ipAddress"
        AND log."userAgent" IS NOT DISTINCT FROM NEW."userAgent"
        AND log."metadata" IS NOT DISTINCT FROM NEW."metadata"
        AND log."success" = TRUE AND log."errorCode" IS NULL
      ORDER BY log."timestamp" DESC
      LIMIT 1;
      IF NOT FOUND THEN
        RAISE EXCEPTION 'Template Twin release delivery requires its exact durable audit receipt';
      END IF;
      NEW."deliveredAt" := delivery_timestamp;
      NEW."updatedAt" := clock_timestamp();
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_release_audit_log_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  owner_name TEXT;
BEGIN
  IF NEW."templateTwinOutboxEventKey" IS NULL
    OR NOT public.template_twin_is_release_audit_identity(
      NEW."templateTwinOutboxEventKey"
    )
  THEN
    RETURN NEW;
  END IF;
  SELECT pg_get_userbyid(object.relowner) INTO owner_name
  FROM pg_class object WHERE object.oid = 'public.audit_logs'::regclass;
  IF current_user <> owner_name
    AND NOT pg_has_role(current_user, 'quillmd_audit_dispatcher', 'MEMBER')
  THEN
    RAISE EXCEPTION 'Template Twin release audit receipt requires the isolated dispatcher';
  END IF;
  NEW."timestamp" := clock_timestamp();
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_guard_release_audit_log_insert()
  FROM PUBLIC;
CREATE TRIGGER aaa_template_twin_release_audit_log_insert_authority_guard
BEFORE INSERT ON "audit_logs"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_release_audit_log_insert();

CREATE OR REPLACE FUNCTION template_twin_assert_release_audit_delivery()
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "template_twin_audit_outbox" outbox
    WHERE template_twin_is_release_audit_identity(outbox."eventKey")
      AND outbox."status" = 'DELIVERED'
      AND (
        outbox."deliveredAt" IS NULL OR NOT EXISTS (
          SELECT 1 FROM "audit_logs" log
          WHERE log."templateTwinOutboxEventKey" = outbox."eventKey"
            AND log."action" = outbox."action"
            AND log."targetType" IS NOT DISTINCT FROM outbox."targetType"
            AND log."targetId" IS NOT DISTINCT FROM outbox."targetId"
            AND log."practiceId" = outbox."practiceId"
            AND log."userId" IS NOT DISTINCT FROM outbox."actorId"
            AND log."userEmailSnapshot" IS NOT DISTINCT FROM outbox."actorEmailSnapshot"
            AND log."ipAddress" IS NOT DISTINCT FROM outbox."ipAddress"
            AND log."userAgent" IS NOT DISTINCT FROM outbox."userAgent"
            AND log."metadata" IS NOT DISTINCT FROM outbox."metadata"
            AND log."timestamp" = outbox."deliveredAt"
            AND log."success" = TRUE AND log."errorCode" IS NULL
        )
      )
  ) OR EXISTS (
    SELECT 1 FROM "audit_logs" log
    WHERE template_twin_is_release_audit_identity(log."templateTwinOutboxEventKey")
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = log."templateTwinOutboxEventKey"
          AND outbox."status" = 'DELIVERED'
          AND outbox."deliveredAt" = log."timestamp"
          AND outbox."action" = log."action"
          AND outbox."practiceId" = log."practiceId"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin release audit delivery is not bidirectionally exact';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_check_release_audit_delivery()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  PERFORM public.template_twin_assert_release_audit_delivery();
  RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_assert_release_audit_delivery()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_check_release_audit_delivery()
  FROM PUBLIC;

-- Runtime requirement identity must match the frozen candidate, and a live
-- exposure may never include an inactive tenant or an unready replica set.
-- Every relevant statement marks the transaction dirty in an owner-only
-- table. The first deferred row trigger performs the global invariant scan
-- once for the exact transaction/backend/epoch; the remaining row triggers
-- become O(1). Custom GUCs are deliberately not trusted because any database
-- client can set them. One row is reused per backend PID, so this receipt
-- table remains bounded by connection concurrency.
CREATE TABLE "template_twin_release_coupling_receipts" (
  "backendPid" INTEGER NOT NULL,
  "transactionId" BIGINT NOT NULL,
  "dirtyEpoch" BIGINT NOT NULL,
  "verifiedEpoch" BIGINT NOT NULL,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_release_coupling_receipts_pkey"
    PRIMARY KEY ("backendPid"),
  CONSTRAINT "template_twin_release_coupling_receipt_epoch" CHECK (
    "dirtyEpoch" > 0 AND "verifiedEpoch" >= 0
      AND "verifiedEpoch" <= "dirtyEpoch"
  )
);
REVOKE ALL ON "template_twin_release_coupling_receipts" FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_mark_release_coupling_dirty()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  INSERT INTO public."template_twin_release_coupling_receipts" (
    "backendPid", "transactionId", "dirtyEpoch", "verifiedEpoch", "updatedAt"
  ) VALUES (
    pg_backend_pid(), txid_current(), 1, 0, clock_timestamp()
  )
  ON CONFLICT ("backendPid") DO UPDATE
  SET "transactionId" = txid_current(),
      "dirtyEpoch" = CASE
        WHEN public."template_twin_release_coupling_receipts"."transactionId" =
          txid_current()
        THEN public."template_twin_release_coupling_receipts"."dirtyEpoch" + 1
        ELSE 1
      END,
      "verifiedEpoch" = 0,
      "updatedAt" = clock_timestamp();
  RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_mark_release_coupling_dirty()
  FROM PUBLIC;

DO $$
DECLARE
  table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'template_twin_release_candidates',
    'template_twin_release_practices',
    'template_twin_release_approval_decisions',
    'template_twin_release_checkpoints',
    'template_twin_release_metric_snapshots',
    'template_twin_release_runtime_requirements',
    'template_twin_audit_outbox',
    'template_twin_rollout_controls',
    'practices'
  ]
  LOOP
    EXECUTE format(
      'DROP TRIGGER IF EXISTS template_twin_release_coupling_dirty ON %I',
      table_name
    );
    EXECUTE format(
      'CREATE TRIGGER template_twin_release_coupling_dirty '
      'AFTER INSERT OR UPDATE OR DELETE OR TRUNCATE ON %I '
      'FOR EACH STATEMENT EXECUTE FUNCTION template_twin_mark_release_coupling_dirty()',
      table_name
    );
  END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_assert_release_control_coupling()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  coupling_receipt RECORD;
BEGIN
  SELECT receipt.* INTO coupling_receipt
  FROM public."template_twin_release_coupling_receipts" receipt
  WHERE receipt."backendPid" = pg_backend_pid()
    AND receipt."transactionId" = txid_current()
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin coupling receipt is missing for this transaction';
  END IF;
  IF coupling_receipt."verifiedEpoch" = coupling_receipt."dirtyEpoch" THEN
    RETURN NULL;
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_practices" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_approval_decisions" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_metric_snapshots" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
      OR child."policySha256" <> candidate."guardrailPolicySha256"
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_runtime_requirements" child
    JOIN "template_twin_release_candidates" candidate ON candidate."id" = child."releaseId"
    WHERE child."releaseIdentitySha256" <> candidate."releaseIdentitySha256"
      OR child."sourceCommitSha" <> candidate."sourceCommitSha"
      OR child."imageDigest" <> CASE child."component"
        WHEN 'APP' THEN candidate."appImageDigest"
        WHEN 'WORKER' THEN candidate."workerImageDigest"
      END
  ) THEN
    RAISE EXCEPTION 'Template Twin release child evidence identity mismatch';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE NOT EXISTS (
      SELECT 1 FROM "template_twin_audit_outbox" outbox
      WHERE outbox."eventKey" = 'template-twin:release:' || candidate."id"::TEXT || ':created'
        AND outbox."action"::TEXT = 'TEMPLATE_TWIN_RELEASE_CREATED'
        AND outbox."targetType" = 'TemplateTwinReleaseCandidate'
        AND outbox."targetId" = candidate."id"::TEXT
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin release creation audit evidence is missing';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE candidate."status" <> 'DRAFT'
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = 'template-twin:release:' || candidate."id"::TEXT || ':frozen'
          AND outbox."action"::TEXT = 'TEMPLATE_TWIN_RELEASE_FROZEN'
          AND outbox."targetId" = candidate."id"::TEXT
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin release freeze audit evidence is missing';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE candidate."status" IN ('APPROVED', 'ROLLING_OUT', 'STABLE_100')
      AND NOT template_twin_release_approvals_are_current(
        candidate."id", candidate."releaseIdentitySha256"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin current human approvals are incomplete';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE candidate."status" = 'STABLE_100'
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
        WHERE checkpoint."releaseId" = candidate."id"
          AND checkpoint."stage" = 'PERCENT_100'
          AND checkpoint."ordinal" = 5
          AND checkpoint."status" = 'PASSED'
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin STABLE_100 requires the exact final checkpoint to pass';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_metric_snapshots" metric
    JOIN "template_twin_release_candidates" candidate
      ON candidate."id" = metric."releaseId"
    WHERE metric."evaluation" = 'CRITICAL_REVOKE'
      AND EXISTS (
        SELECT 1 FROM "template_twin_release_metric_receipts" receipt
        WHERE receipt."releaseId" = metric."releaseId"
          AND receipt."checkpointId" = metric."checkpointId"
          AND receipt."canonicalSha256" = metric."canonicalSha256"
          AND receipt."transactionId" = txid_current()
          AND receipt."backendPid" = pg_backend_pid()
      )
      AND (
      candidate."status" <> 'REVOKED'
      OR EXISTS (
        SELECT 1 FROM "template_twin_rollout_controls" control
        WHERE control."id" = 'global' AND control."enabled" = TRUE
      )
      OR EXISTS (
        SELECT 1
        FROM "template_twin_release_practices" manifest
        JOIN "practices" practice ON practice."id" = manifest."practiceId"
        WHERE manifest."releaseId" = candidate."id"
          AND practice."templateTwinEnabled" = TRUE
      )
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin critical monitoring evidence requires atomic release revocation and disable';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
    WHERE checkpoint."status" IN ('ACTIVE', 'PASSED', 'FAILED', 'REVOKED')
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = checkpoint."activationOutboxEventKey"
          AND outbox."action"::TEXT = 'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_ACTIVATED'
          AND outbox."targetId" = checkpoint."id"::TEXT
      )
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
    WHERE checkpoint."status" = 'PASSED'
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = checkpoint."passOutboxEventKey"
          AND outbox."action"::TEXT = 'TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_PASSED'
          AND outbox."targetId" = checkpoint."id"::TEXT
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint audit evidence is incomplete';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_approval_decisions" decision
    JOIN "users" actor ON actor."id" = decision."actorId"
    WHERE NOT EXISTS (
      SELECT 1 FROM "template_twin_audit_outbox" outbox
      WHERE outbox."eventKey" = decision."auditOutboxEventKey"
        AND outbox."action"::TEXT = 'TEMPLATE_TWIN_RELEASE_APPROVAL_RECORDED'
        AND outbox."targetType" = 'TemplateTwinReleaseApprovalDecision'
        AND outbox."targetId" = decision."id"::TEXT
        AND outbox."actorId" = decision."actorId"
        AND outbox."actorEmailSnapshot" IS NOT DISTINCT FROM decision."actorEmailSnapshot"
        AND outbox."practiceId" = actor."practiceId"
        AND outbox."metadata"->>'releaseId' = decision."releaseId"::TEXT
        AND outbox."metadata"->>'discipline' = decision."discipline"
        AND outbox."metadata"->>'decision' = decision."decision"
        AND outbox."metadata"->>'evidenceSha256' = decision."evidenceSha256"
        AND outbox."metadata"->>'authorityAssignmentId' = decision."authorityAssignmentId"::TEXT
      )
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_metric_snapshots" metric
    JOIN "users" actor ON actor."id" = metric."recordedById"
    WHERE metric."evaluation" = 'CRITICAL_REVOKE' AND NOT EXISTS (
      SELECT 1 FROM "template_twin_audit_outbox" outbox
      WHERE outbox."eventKey" = metric."criticalOutboxEventKey"
        AND outbox."action"::TEXT = 'TEMPLATE_TWIN_ROLLOUT_GUARDRAIL_REVOKED'
        AND outbox."targetType" = 'TemplateTwinReleaseMetricSnapshot'
        AND outbox."targetId" = metric."id"::TEXT
        AND outbox."actorId" = metric."recordedById"
        AND outbox."practiceId" = actor."practiceId"
        AND outbox."metadata"->>'releaseId' = metric."releaseId"::TEXT
        AND outbox."metadata"->>'snapshotSha256' = metric."canonicalSha256"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin approval or critical-metric audit semantics are incomplete';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "template_twin_audit_outbox" outbox
    CROSS JOIN "template_twin_rollout_controls" control
    WHERE control."id" = 'global'
      AND outbox."eventKey" ~ '^template-twin:global-rollout:[0-9]+$'
      AND substring(
        outbox."eventKey" FROM '^template-twin:global-rollout:([0-9]+)$'
      )::NUMERIC > control."generation"
  ) OR EXISTS (
    SELECT 1
    FROM "template_twin_audit_outbox" outbox
    CROSS JOIN LATERAL regexp_match(
      outbox."eventKey",
      '^template-twin:practice-rollout:([A-Za-z0-9_-]+):([0-9]+)$'
    ) parts
    LEFT JOIN "practices" practice ON practice."id" = parts[1]
    WHERE outbox."eventKey" ~
        '^template-twin:practice-rollout:([A-Za-z0-9_-]+):([0-9]+)$'
      AND (
        practice."id" IS NULL
        OR parts[2]::NUMERIC > practice."templateTwinRolloutGeneration"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin rollout audit evidence cannot pre-seed a future or missing control generation';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_rollout_controls" control
    WHERE control."id" = 'global' AND control."generation" > 1
      AND EXISTS (
        SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
        WHERE checkpoint."status" <> 'PENDING'
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = 'template-twin:global-rollout:' || control."generation"::TEXT
          AND outbox."targetType" = 'TemplateTwinRolloutControl'
          AND outbox."targetId" = 'global'
          AND outbox."action"::TEXT = CASE WHEN control."enabled"
            THEN 'TEMPLATE_TWIN_ACTIVATED' ELSE 'TEMPLATE_TWIN_DEACTIVATED' END
          AND outbox."metadata"->>'scope' = 'global'
          AND (outbox."metadata"->>'enabled')::BOOLEAN = control."enabled"
          AND outbox."metadata"->>'generation' = control."generation"::TEXT
      )
  ) OR EXISTS (
    SELECT 1 FROM "practices" practice
    WHERE practice."templateTwinRolloutGeneration" > 1
      AND EXISTS (
        SELECT 1 FROM "template_twin_release_practices" manifest
        JOIN "template_twin_release_checkpoints" checkpoint
          ON checkpoint."releaseId" = manifest."releaseId"
        WHERE manifest."practiceId" = practice."id"
          AND checkpoint."status" <> 'PENDING'
      )
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = 'template-twin:practice-rollout:' || practice."id" || ':' ||
          practice."templateTwinRolloutGeneration"::TEXT
          AND outbox."targetType" = 'Practice'
          AND outbox."targetId" = practice."id"
          AND outbox."practiceId" = practice."id"
          AND outbox."action"::TEXT = CASE WHEN practice."templateTwinEnabled"
            THEN 'TEMPLATE_TWIN_ACTIVATED' ELSE 'TEMPLATE_TWIN_DEACTIVATED' END
          AND outbox."metadata"->>'scope' = 'practice'
          AND (outbox."metadata"->>'enabled')::BOOLEAN = practice."templateTwinEnabled"
          AND outbox."metadata"->>'generation' = practice."templateTwinRolloutGeneration"::TEXT
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin global or practice exposure audit semantics are incomplete';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_release_checkpoints" checkpoint
    WHERE checkpoint."status" = 'ACTIVE'
      AND EXISTS (
        SELECT 1 FROM "template_twin_release_checkpoints" prior
        WHERE prior."releaseId" = checkpoint."releaseId"
          AND prior."ordinal" < checkpoint."ordinal"
          AND prior."status" <> 'PASSED'
      )
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE (
      SELECT COUNT(*) FROM "template_twin_release_checkpoints" checkpoint
      WHERE checkpoint."releaseId" = candidate."id"
        AND checkpoint."stage" IN ('CANARY', 'PERCENT_10', 'PERCENT_25', 'PERCENT_50', 'PERCENT_100')
    ) <> 5
  ) OR EXISTS (
    SELECT 1 FROM "template_twin_release_candidates" candidate
    WHERE (
      SELECT COUNT(*) FROM "template_twin_release_runtime_requirements" requirement
      WHERE requirement."releaseId" = candidate."id"
        AND requirement."component" IN ('APP', 'WORKER')
    ) < 2
  ) THEN
    RAISE EXCEPTION 'Template Twin checkpoint or runtime rail is incomplete';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_rollout_controls" control
    WHERE control."id" = 'global' AND control."enabled" = TRUE
      AND NOT EXISTS (
        SELECT 1 FROM "template_twin_release_candidates" candidate
        WHERE candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
          AND template_twin_release_runtime_ready(
            candidate."id", candidate."releaseIdentitySha256"
          )
      )
  ) OR EXISTS (
    SELECT 1 FROM "practices" practice
    WHERE practice."templateTwinEnabled" = TRUE AND (
      practice."isActive" = FALSE OR NOT EXISTS (
        SELECT 1
        FROM "template_twin_release_practices" manifest
        JOIN "template_twin_release_candidates" candidate
          ON candidate."id" = manifest."releaseId"
        WHERE manifest."practiceId" = practice."id"
          AND candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
          AND manifest."activationStageOrdinal" <= COALESCE((
            SELECT MAX(checkpoint."ordinal")
            FROM "template_twin_release_checkpoints" checkpoint
            WHERE checkpoint."releaseId" = candidate."id"
              AND checkpoint."status" IN ('ACTIVE', 'PASSED')
          ), 0)
      )
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin persisted exposure is outside a ready release checkpoint';
  END IF;
  UPDATE public."template_twin_release_coupling_receipts"
  SET "verifiedEpoch" = coupling_receipt."dirtyEpoch",
      "updatedAt" = clock_timestamp()
  WHERE "backendPid" = pg_backend_pid()
    AND "transactionId" = txid_current()
    AND "dirtyEpoch" = coupling_receipt."dirtyEpoch";
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin coupling receipt changed during verification';
  END IF;
  RETURN NULL;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_assert_release_control_coupling()
  FROM PUBLIC;

CREATE CONSTRAINT TRIGGER template_twin_release_runtime_requirement_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_release_runtime_requirements"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();
CREATE CONSTRAINT TRIGGER template_twin_release_outbox_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_audit_outbox"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_release_control_coupling();

-- Aggregate monitoring evidence is accepted only through a signed,
-- transaction-bound receipt. The monitoring secret remains in the private key
-- table; neither web runtime nor release-control SQL can read it.
ALTER TABLE "template_twin_release_metric_snapshots"
  ADD COLUMN "attestationKeyId" VARCHAR(80),
  ADD COLUMN "attestationNonceSha256" CHAR(64),
  ADD COLUMN "attestationSignatureSha256" CHAR(64),
  ADD COLUMN "releaseGeneration" BIGINT,
  ADD COLUMN "globalGeneration" BIGINT;
ALTER TABLE "template_twin_release_metric_snapshots"
  ALTER COLUMN "attestationKeyId" SET NOT NULL,
  ALTER COLUMN "attestationNonceSha256" SET NOT NULL,
  ALTER COLUMN "attestationSignatureSha256" SET NOT NULL,
  ALTER COLUMN "releaseGeneration" SET NOT NULL,
  ALTER COLUMN "globalGeneration" SET NOT NULL;
ALTER TABLE "template_twin_release_metric_snapshots"
  ADD CONSTRAINT "template_twin_release_metric_attestation_nonce_key"
    UNIQUE ("attestationNonceSha256"),
  ADD CONSTRAINT "template_twin_release_metric_attestation_shape" CHECK (
    "attestationNonceSha256" ~ '^[0-9a-f]{64}$'
    AND "attestationSignatureSha256" ~ '^[0-9a-f]{64}$'
  ),
  ADD CONSTRAINT "template_twin_release_metric_attestation_key_fkey"
    FOREIGN KEY ("attestationKeyId")
    REFERENCES "template_twin_release_attestation_keys"("keyId")
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE "template_twin_release_metric_receipts" (
  "nonce" UUID NOT NULL,
  "transactionId" BIGINT NOT NULL,
  "backendPid" INTEGER NOT NULL,
  "releaseId" UUID NOT NULL,
  "checkpointId" UUID NOT NULL,
  "releaseGeneration" BIGINT NOT NULL,
  "globalGeneration" BIGINT NOT NULL,
  "releaseIdentitySha256" CHAR(64) NOT NULL,
  "policySha256" CHAR(64) NOT NULL,
  "stage" VARCHAR(24) NOT NULL,
  "schemaVersion" VARCHAR(64) NOT NULL,
  "sampleCount" INTEGER NOT NULL,
  "observationStartedAt" TIMESTAMPTZ(6) NOT NULL,
  "observationEndedAt" TIMESTAMPTZ(6) NOT NULL,
  "metrics" JSONB NOT NULL,
  "canonicalSha256" CHAR(64) NOT NULL,
  "evaluation" VARCHAR(24) NOT NULL,
  "missingMetrics" TEXT[] NOT NULL,
  "breachedMetrics" TEXT[] NOT NULL,
  "blockingReasons" TEXT[] NOT NULL,
  "principalUserId" TEXT NOT NULL,
  "attestationKeyId" VARCHAR(80) NOT NULL,
  "attestationNonceSha256" CHAR(64) NOT NULL,
  "attestationSignatureSha256" CHAR(64) NOT NULL,
  "issuedAt" TIMESTAMPTZ(6) NOT NULL,
  "expiresAt" TIMESTAMPTZ(6) NOT NULL,
  CONSTRAINT "template_twin_release_metric_receipts_pkey" PRIMARY KEY ("nonce"),
  CONSTRAINT "template_twin_release_metric_receipt_nonce_key" UNIQUE ("attestationNonceSha256"),
  CONSTRAINT "template_twin_release_metric_receipt_shape" CHECK (
    "expiresAt" > "issuedAt" AND "sampleCount" >= 0
    AND "releaseGeneration" > 0 AND "globalGeneration" > 0
    AND "observationEndedAt" > "observationStartedAt"
    AND "evaluation" IN ('PASS', 'BLOCK', 'CRITICAL_REVOKE')
  ),
  CONSTRAINT "template_twin_release_metric_receipt_release_fkey"
    FOREIGN KEY ("releaseId") REFERENCES "template_twin_release_candidates"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT "template_twin_release_metric_receipt_checkpoint_fkey"
    FOREIGN KEY ("checkpointId") REFERENCES "template_twin_release_checkpoints"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT "template_twin_release_metric_receipt_principal_fkey"
    FOREIGN KEY ("principalUserId") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT "template_twin_release_metric_receipt_key_fkey"
    FOREIGN KEY ("attestationKeyId") REFERENCES "template_twin_release_attestation_keys"("keyId")
    ON DELETE RESTRICT ON UPDATE RESTRICT
);
CREATE INDEX "template_twin_release_metric_receipt_lookup_idx"
  ON "template_twin_release_metric_receipts"("releaseId", "checkpointId", "expiresAt");
REVOKE ALL ON "template_twin_release_metric_receipts" FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_reject_metric_receipt_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin signed metric receipts are immutable';
END;
$$;
CREATE TRIGGER template_twin_metric_receipt_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_release_metric_receipts"
FOR EACH ROW EXECUTE FUNCTION template_twin_reject_metric_receipt_mutation();
CREATE TRIGGER template_twin_metric_receipt_truncate_guard
BEFORE TRUNCATE ON "template_twin_release_metric_receipts"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_metric_receipt_mutation();

CREATE OR REPLACE FUNCTION template_twin_issue_metric_receipt(
  attestation_version TEXT,
  attestation_key_id TEXT,
  attestation_nonce UUID,
  candidate_id UUID,
  rollout_stage TEXT,
  expected_release_generation BIGINT,
  expected_global_generation BIGINT,
  metric_sample_count INTEGER,
  observation_started_epoch_ms BIGINT,
  observation_ended_epoch_ms BIGINT,
  raw_metrics JSONB,
  issued_epoch_seconds BIGINT,
  supplied_signature CHAR(64)
)
RETURNS TABLE (
  "receiptNonce" UUID,
  "principalUserId" TEXT,
  "schemaVersion" TEXT,
  "canonicalSha256" TEXT,
  "evaluation" TEXT,
  "metrics" JSONB,
  "missingMetrics" TEXT[],
  "breachedMetrics" TEXT[],
  "blockingReasons" TEXT[],
  "attestationNonceSha256" TEXT,
  "attestationSignatureSha256" TEXT
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  signing_secret BYTEA;
  monitoring_principal TEXT;
  release RECORD;
  checkpoint RECORD;
  global_generation BIGINT;
  issued_at TIMESTAMPTZ;
  observation_started TIMESTAMPTZ;
  observation_ended TIMESTAMPTZ;
  signing_message TEXT;
  metric_lines TEXT;
  expected_signature TEXT;
  metric_key TEXT;
  metric_text TEXT;
  metric_number NUMERIC;
  metric_min NUMERIC;
  metric_max NUMERIC;
  metric_direction TEXT;
  metric_threshold NUMERIC;
  metric_critical BOOLEAN;
  metric_keys CONSTANT TEXT[] := ARRAY[
    'failed_upload_rate', 'malware_inspection_failure_rate',
    'render_verification_failure_rate', 'sign_download_block_rate',
    'unsafe_bypass_attempt_count', 'audit_outbox_delivery_failure_rate',
    'audit_outbox_max_lag_seconds', 'object_storage_failure_rate',
    'queue_failure_rate', 'provider_failure_rate',
    'provider_ambiguous_outcome_count', 'p95_latency_ms', 'p99_latency_ms',
    'error_rate', 'critical_field_accuracy', 'unsupported_field_recall',
    'hallucination_rate', 'evidence_anchor_validity',
    'exact_dropdown_accuracy', 'negation_accuracy', 'laterality_accuracy',
    'table_placement_accuracy'
  ];
  normalized_metrics JSONB := '{}'::JSONB;
  missing_metrics TEXT[] := ARRAY[]::TEXT[];
  breached_metrics TEXT[] := ARRAY[]::TEXT[];
  blocking_reasons TEXT[] := ARRAY[]::TEXT[];
  critical_breach BOOLEAN := FALSE;
  computed_evaluation TEXT;
  computed_canonical TEXT;
  nonce_sha TEXT;
  signature_sha TEXT;
  new_receipt UUID := gen_random_uuid();
BEGIN
  IF attestation_version <> 'template-twin-metric-attestation-v1'
    OR rollout_stage NOT IN ('CANARY', 'PERCENT_10', 'PERCENT_25', 'PERCENT_50', 'PERCENT_100')
    OR metric_sample_count < 0
    OR jsonb_typeof(raw_metrics) <> 'object'
    OR supplied_signature !~ '^[0-9a-f]{64}$'
  THEN
    RAISE EXCEPTION 'Template Twin aggregate metric attestation shape is invalid';
  END IF;
  issued_at := to_timestamp(issued_epoch_seconds);
  observation_started := to_timestamp(observation_started_epoch_ms / 1000.0);
  observation_ended := to_timestamp(observation_ended_epoch_ms / 1000.0);
  IF issued_at > clock_timestamp() + INTERVAL '30 seconds'
    OR issued_at < clock_timestamp() - INTERVAL '5 minutes'
  THEN
    RAISE EXCEPTION 'Template Twin metric attestation is stale';
  END IF;

  SELECT key."secret", key."principalUserId"
    INTO signing_secret, monitoring_principal
  FROM public."template_twin_release_attestation_keys" key
  JOIN public."users" account ON account."id" = key."principalUserId"
  WHERE key."keyId" = attestation_key_id
    AND key."purpose" = 'METRICS'
    AND key."effectiveAt" <= clock_timestamp()
    AND key."expiresAt" > clock_timestamp()
    AND key."revokedAt" IS NULL
    AND account."isActive" = TRUE
    AND account."deactivatedAt" IS NULL
    AND account."suspendedAt" IS NULL
    AND account."softDeletedAt" IS NULL;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin monitoring attestation key is unavailable';
  END IF;

  SELECT candidate.* INTO release
  FROM public."template_twin_release_candidates" candidate
  WHERE candidate."id" = candidate_id
    AND candidate."generation" >= expected_release_generation
    AND candidate."status" IN ('ROLLING_OUT', 'STABLE_100')
  FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin metric release identity is stale';
  END IF;
  SELECT cp.* INTO checkpoint
  FROM public."template_twin_release_checkpoints" cp
  WHERE cp."releaseId" = candidate_id
    AND cp."releaseIdentitySha256" = release."releaseIdentitySha256"
    AND cp."stage" = rollout_stage
    AND cp."status" IN ('ACTIVE', 'PASSED')
  FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin metric checkpoint is not active';
  END IF;
  SELECT control."generation" INTO global_generation
  FROM public."template_twin_rollout_controls" control
  WHERE control."id" = 'global'
    AND control."generation" >= expected_global_generation
    AND control."enabled" = TRUE
    AND control."rollbackFenceState" = 'OPEN'
    AND control."rollbackOperationId" IS NULL
  FOR SHARE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin metric global rollout identity is stale';
  END IF;

  IF EXISTS (
    SELECT 1 FROM jsonb_each(raw_metrics) item
    WHERE NOT (item.key = ANY(metric_keys))
      OR jsonb_typeof(item.value) <> 'string'
      OR (item.value #>> '{}') !~ '^(0|[1-9][0-9]*)(\.[0-9]{1,12})?$'
  ) THEN
    RAISE EXCEPTION 'Template Twin metrics accept only bounded canonical decimal aggregates';
  END IF;

  FOR metric_key, metric_text IN
    SELECT item.key, item.value #>> '{}'
    FROM jsonb_each(raw_metrics) item ORDER BY item.key
  LOOP
    metric_number := metric_text::NUMERIC;
    metric_min := 0;
    metric_max := CASE metric_key
      WHEN 'unsafe_bypass_attempt_count' THEN 1000000
      WHEN 'provider_ambiguous_outcome_count' THEN 1000000
      WHEN 'audit_outbox_max_lag_seconds' THEN 86400
      WHEN 'p95_latency_ms' THEN 3600000
      WHEN 'p99_latency_ms' THEN 3600000
      ELSE 1
    END;
    IF metric_number < metric_min OR metric_number > metric_max THEN
      RAISE EXCEPTION 'Template Twin aggregate metric is outside its bounded definition';
    END IF;
    normalized_metrics := normalized_metrics || jsonb_build_object(metric_key, metric_number);
    metric_direction := release."guardrailPolicy"->'metrics'->metric_key->>'direction';
    metric_threshold := (release."guardrailPolicy"->'metrics'->metric_key->>'threshold')::NUMERIC;
    metric_critical := (release."guardrailPolicy"->'metrics'->metric_key->>'critical')::BOOLEAN;
    IF metric_direction NOT IN ('MIN', 'MAX') OR metric_threshold IS NULL OR metric_critical IS NULL THEN
      RAISE EXCEPTION 'Template Twin guardrail policy is invalid';
    END IF;
    IF (metric_direction = 'MAX' AND metric_number > metric_threshold)
      OR (metric_direction = 'MIN' AND metric_number < metric_threshold)
    THEN
      breached_metrics := array_append(breached_metrics, metric_key);
      critical_breach := critical_breach OR metric_critical;
    END IF;
  END LOOP;

  SELECT COALESCE(array_agg(key ORDER BY key), ARRAY[]::TEXT[])
    INTO missing_metrics
  FROM unnest(metric_keys) key
  WHERE NOT (raw_metrics ? key);

  IF observation_ended <= observation_started THEN
    blocking_reasons := array_append(blocking_reasons, 'OBSERVATION_INTERVAL_INVALID');
  END IF;
  IF observation_started < checkpoint."activatedAt" THEN
    blocking_reasons := array_append(blocking_reasons, 'OBSERVATION_PRECEDES_CHECKPOINT');
  END IF;
  IF observation_ended > clock_timestamp() THEN
    blocking_reasons := array_append(blocking_reasons, 'OBSERVATION_ENDS_IN_FUTURE');
  END IF;
  IF clock_timestamp() - observation_ended >
    make_interval(secs => (release."guardrailPolicy"->>'maxObservationAgeSeconds')::INTEGER)
  THEN
    blocking_reasons := array_append(blocking_reasons, 'OBSERVATION_STALE');
  END IF;
  IF observation_ended - observation_started <
    make_interval(secs => (release."guardrailPolicy"->'minimumBakeSecondsByStage'->>rollout_stage)::INTEGER)
  THEN
    blocking_reasons := array_append(blocking_reasons, 'BAKE_INTERVAL_INSUFFICIENT');
  END IF;
  IF metric_sample_count <
    (release."guardrailPolicy"->'minimumSampleCountByStage'->>rollout_stage)::INTEGER
  THEN
    blocking_reasons := array_append(blocking_reasons, 'SAMPLE_COUNT_INSUFFICIENT');
  END IF;
  IF cardinality(missing_metrics) > 0 THEN
    blocking_reasons := array_append(blocking_reasons, 'REQUIRED_METRICS_MISSING');
  END IF;
  IF cardinality(breached_metrics) > 0 THEN
    blocking_reasons := array_append(blocking_reasons, 'THRESHOLD_BREACH');
  END IF;
  computed_evaluation := CASE
    WHEN critical_breach THEN 'CRITICAL_REVOKE'
    WHEN cardinality(blocking_reasons) > 0 THEN 'BLOCK'
    ELSE 'PASS'
  END;
  IF computed_evaluation <> 'CRITICAL_REVOKE' AND (
    release."generation" <> expected_release_generation
    OR global_generation <> expected_global_generation
  ) THEN
    RAISE EXCEPTION 'Template Twin noncritical metric generation is stale';
  END IF;

  SELECT COALESCE(string_agg(item.key || '=' || (item.value #>> '{}'), E'\n' ORDER BY item.key), '')
    INTO metric_lines FROM jsonb_each(raw_metrics) item;
  signing_message := concat_ws(E'\n',
    attestation_version, attestation_key_id, attestation_nonce::TEXT,
    candidate_id::TEXT, rollout_stage, expected_release_generation::TEXT,
    expected_global_generation::TEXT, metric_sample_count::TEXT,
    observation_started_epoch_ms::TEXT, observation_ended_epoch_ms::TEXT,
    issued_epoch_seconds::TEXT, metric_lines
  );
  expected_signature := encode(hmac(
    convert_to(signing_message, 'UTF8'), signing_secret, 'sha256'
  ), 'hex');
  IF expected_signature <> supplied_signature THEN
    RAISE EXCEPTION 'Template Twin metric attestation signature is invalid';
  END IF;

  computed_canonical := encode(digest(convert_to(concat_ws(E'\n',
    'template-twin-metric-snapshot-db-v2', release."releaseIdentitySha256",
    release."guardrailPolicySha256", rollout_stage, metric_sample_count::TEXT,
    observation_started_epoch_ms::TEXT, observation_ended_epoch_ms::TEXT,
    metric_lines
  ), 'UTF8'), 'sha256'), 'hex');
  nonce_sha := encode(digest(attestation_nonce::TEXT, 'sha256'), 'hex');
  signature_sha := encode(digest(supplied_signature, 'sha256'), 'hex');

  INSERT INTO public."template_twin_release_metric_receipts" (
    "nonce", "transactionId", "backendPid", "releaseId", "checkpointId",
    "releaseGeneration", "globalGeneration",
    "releaseIdentitySha256", "policySha256", "stage", "schemaVersion",
    "sampleCount", "observationStartedAt", "observationEndedAt", "metrics",
    "canonicalSha256", "evaluation", "missingMetrics", "breachedMetrics",
    "blockingReasons", "principalUserId", "attestationKeyId",
    "attestationNonceSha256", "attestationSignatureSha256", "issuedAt", "expiresAt"
  ) VALUES (
    new_receipt, txid_current(), pg_backend_pid(), candidate_id, checkpoint."id",
    expected_release_generation, expected_global_generation,
    release."releaseIdentitySha256", release."guardrailPolicySha256", rollout_stage,
    'template-twin-guardrails-v1', metric_sample_count, observation_started,
    observation_ended, normalized_metrics, computed_canonical,
    computed_evaluation, missing_metrics, breached_metrics, blocking_reasons,
    monitoring_principal, attestation_key_id, nonce_sha, signature_sha,
    issued_at, clock_timestamp() + INTERVAL '5 minutes'
  );
  PERFORM set_config('meddoc.template_twin_metric_receipt', new_receipt::TEXT, TRUE);

  RETURN QUERY SELECT new_receipt, monitoring_principal,
    'template-twin-guardrails-v1'::TEXT, computed_canonical,
    computed_evaluation, normalized_metrics, missing_metrics,
    breached_metrics, blocking_reasons, nonce_sha, signature_sha;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_issue_metric_receipt(
  TEXT, TEXT, UUID, UUID, TEXT, BIGINT, BIGINT, INTEGER,
  BIGINT, BIGINT, JSONB, BIGINT, CHAR(64)
) FROM PUBLIC;

CREATE OR REPLACE FUNCTION template_twin_require_metric_receipt()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  configured_nonce TEXT;
  receipt RECORD;
BEGIN
  configured_nonce := current_setting('meddoc.template_twin_metric_receipt', TRUE);
  IF configured_nonce IS NULL OR configured_nonce !~
    '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
  THEN
    RAISE EXCEPTION 'Template Twin metric insert requires a signed monitoring receipt';
  END IF;
  SELECT signed.* INTO receipt
  FROM "template_twin_release_metric_receipts" signed
  WHERE signed."nonce" = configured_nonce::UUID
    AND signed."transactionId" = txid_current()
    AND signed."backendPid" = pg_backend_pid()
    AND signed."expiresAt" > clock_timestamp();
  IF NOT FOUND OR ROW(
    NEW."releaseId", NEW."checkpointId", NEW."releaseGeneration",
    NEW."globalGeneration", NEW."releaseIdentitySha256",
    NEW."policySha256", NEW."schemaVersion", NEW."sampleCount",
    NEW."observationStartedAt", NEW."observationEndedAt", NEW."metrics",
    NEW."canonicalSha256", NEW."evaluation", NEW."missingMetrics",
    NEW."breachedMetrics", NEW."blockingReasons", NEW."recordedById",
    NEW."attestationKeyId", NEW."attestationNonceSha256",
    NEW."attestationSignatureSha256"
  ) IS DISTINCT FROM ROW(
    receipt."releaseId", receipt."checkpointId", receipt."releaseGeneration",
    receipt."globalGeneration", receipt."releaseIdentitySha256",
    receipt."policySha256", receipt."schemaVersion", receipt."sampleCount",
    receipt."observationStartedAt", receipt."observationEndedAt", receipt."metrics",
    receipt."canonicalSha256", receipt."evaluation", receipt."missingMetrics",
    receipt."breachedMetrics", receipt."blockingReasons", receipt."principalUserId",
    receipt."attestationKeyId", receipt."attestationNonceSha256",
    receipt."attestationSignatureSha256"
  ) THEN
    RAISE EXCEPTION 'Template Twin metric insert differs from its signed database evaluation';
  END IF;
  NEW."createdAt" := receipt."issuedAt";
  RETURN NEW;
END;
$$;
CREATE TRIGGER aaa_template_twin_release_metric_receipt_guard
BEFORE INSERT ON "template_twin_release_metric_snapshots"
FOR EACH ROW EXECUTE FUNCTION template_twin_require_metric_receipt();

-- ACTIVE -> PASSED is a database safety boundary, not an application hint.
-- The latest snapshot must still join exactly to an immutable signed receipt,
-- its signing key must remain live, the full in-scope cohort must be exposed,
-- and the persisted physician census/audit identity must be exact.
CREATE OR REPLACE FUNCTION template_twin_guard_checkpoint_pass()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public
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
      make_interval(secs => (release."guardrailPolicy"->>'maxObservationAgeSeconds')::INTEGER)
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
        AND receipt."attestationSignatureSha256" = metric."attestationSignatureSha256"
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
        AND actor."mfaVerifiedAt" IS NOT NULL
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
        AND outbox."metadata"->>'releaseIdentitySha256' = NEW."releaseIdentitySha256"
        AND outbox."metadata"->>'stage' = NEW."stage"
        AND outbox."metadata"->>'metricSnapshotSha256' = metric."canonicalSha256"
        AND outbox."metadata"->>'passedPhysicianCount' = expected_physician_count::TEXT
    )
  THEN
    RAISE EXCEPTION 'Template Twin checkpoint pass actor, census, or audit evidence is invalid';
  END IF;
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION template_twin_guard_checkpoint_pass() FROM PUBLIC;
CREATE TRIGGER aaa_template_twin_release_checkpoint_pass_receipt_guard
BEFORE UPDATE ON "template_twin_release_checkpoints"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_checkpoint_pass();

-- Least-privilege split. Ordinary runtime may use the application schema but
-- cannot mutate release evidence/control rows or issue enable capabilities.
-- The pre-existing rollback deferred checks scan protected rollback and audit
-- state at commit.  Run those invariant scans as their migration owner so the
-- restricted release-control and audit-dispatcher roles need no broad read
-- grants.  They remain trigger-only and use a fixed trusted search path.
ALTER FUNCTION template_twin_assert_rollback_fence_coupling()
  SECURITY DEFINER;
ALTER FUNCTION template_twin_assert_rollback_fence_coupling()
  SET search_path TO pg_catalog, public;
ALTER FUNCTION template_twin_check_rollback_outbox_delivery()
  SECURITY DEFINER;
ALTER FUNCTION template_twin_check_rollback_outbox_delivery()
  SET search_path TO pg_catalog, public;
ALTER FUNCTION template_twin_check_rollback_audit_log_delivery()
  SECURITY DEFINER;
ALTER FUNCTION template_twin_check_rollback_audit_log_delivery()
  SET search_path TO pg_catalog, public;
REVOKE ALL ON FUNCTION template_twin_assert_rollback_fence_coupling()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_check_rollback_outbox_delivery()
  FROM PUBLIC;
REVOKE ALL ON FUNCTION template_twin_check_rollback_audit_log_delivery()
  FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO
  quillmd_runtime, quillmd_release_control, quillmd_audit_dispatcher;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO quillmd_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO quillmd_runtime;

REVOKE ALL ON "template_twin_release_attestation_keys" FROM quillmd_runtime, quillmd_release_control;
REVOKE ALL ON "_prisma_migrations" FROM quillmd_runtime, quillmd_release_control;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE
  ON "template_twin_lineage_migration_progress" FROM quillmd_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON "template_twin_audit_outbox" FROM quillmd_runtime;
REVOKE UPDATE, DELETE, TRUNCATE ON "audit_logs" FROM quillmd_runtime;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON
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
  "template_twin_release_runtime_attestations"
FROM quillmd_runtime;

REVOKE SELECT ON
  "template_twin_release_candidates",
  "template_twin_release_practices",
  "template_twin_release_approval_decisions",
  "template_twin_release_checkpoints",
  "template_twin_release_runtime_requirements",
  "template_twin_release_runtime_attestations"
FROM quillmd_runtime;
REVOKE ALL ON
  "template_twin_release_action_receipts",
  "template_twin_release_coupling_receipts"
FROM quillmd_runtime, quillmd_release_control;
GRANT EXECUTE ON FUNCTION template_twin_register_runtime_attestation(
  TEXT, TEXT, UUID, CHAR(64), TEXT, TEXT, CHAR(40), TEXT, BIGINT, BIGINT, CHAR(64)
) TO quillmd_runtime;
GRANT EXECUTE ON FUNCTION template_twin_release_runtime_ready(UUID, CHAR(64))
  TO quillmd_release_control;
GRANT EXECUTE ON FUNCTION template_twin_current_runtime_release()
  TO quillmd_runtime, quillmd_release_control;
REVOKE ALL ON FUNCTION template_twin_issue_release_capability(
  UUID, CHAR(64), UUID, BIGINT, BIGINT
) FROM quillmd_runtime;
REVOKE INSERT, DELETE, TRUNCATE ON "template_twin_rollout_controls"
  FROM quillmd_runtime;
GRANT UPDATE ON "template_twin_rollout_controls" TO quillmd_runtime;
REVOKE UPDATE ON "practices" FROM quillmd_runtime;
DO $$
DECLARE
  updatable_columns TEXT;
BEGIN
  SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position)
    INTO updatable_columns
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'practices'
    AND column_name NOT IN ('templateTwinEnabled', 'templateTwinRolloutGeneration');
  IF updatable_columns IS NOT NULL THEN
    EXECUTE 'GRANT UPDATE (' || updatable_columns || ') ON "practices" TO quillmd_runtime';
  END IF;
END;
$$;
GRANT UPDATE ("templateTwinEnabled", "templateTwinRolloutGeneration", "updatedAt")
  ON "practices" TO quillmd_runtime;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
  FROM quillmd_release_control;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
  FROM quillmd_release_control;
GRANT SELECT ON
  "template_twin_lineage_migration_progress",
  "template_twin_rollback_operations",
  "template_twin_rollout_controls",
  "template_twin_release_candidates",
  "template_twin_release_authorities",
  "template_twin_release_practices",
  "template_twin_release_approval_decisions",
  "template_twin_release_checkpoints",
  "template_twin_release_metric_snapshots",
  "template_twin_release_metric_receipts",
  "template_twin_release_capabilities",
  "template_twin_release_runtime_requirements",
  "template_twin_release_runtime_attestations"
TO quillmd_release_control;
GRANT SELECT (
  "id", "email", "practiceId", "role", "products", "isActive",
  "deactivatedAt", "suspendedAt", "softDeletedAt"
) ON "users" TO quillmd_release_control;
GRANT SELECT (
  "id", "slug", "isActive", "templateTwinEnabled",
  "templateTwinRolloutGeneration", "updatedAt"
) ON "practices" TO quillmd_release_control;
REVOKE ALL ON "template_twin_release_attestation_keys", "user_sessions"
  FROM quillmd_release_control;
REVOKE ALL ON "template_twin_release_attestation_keys"
  FROM quillmd_runtime;
REVOKE ALL ON "template_twin_release_metric_receipts"
FROM quillmd_runtime;
GRANT INSERT, UPDATE ON
  "template_twin_release_candidates",
  "template_twin_release_checkpoints",
  "template_twin_rollout_controls"
TO quillmd_release_control;
GRANT INSERT ON
  "template_twin_release_practices",
  "template_twin_release_approval_decisions",
  "template_twin_release_metric_snapshots",
  "template_twin_release_runtime_requirements",
  "template_twin_audit_outbox"
TO quillmd_release_control;
GRANT UPDATE ("templateTwinEnabled", "templateTwinRolloutGeneration", "updatedAt")
  ON "practices" TO quillmd_release_control;
GRANT EXECUTE ON FUNCTION template_twin_issue_release_capability(
  UUID, CHAR(64), UUID, BIGINT, BIGINT
) TO quillmd_release_control;
GRANT EXECUTE ON FUNCTION template_twin_verify_release_actor(TEXT, TEXT)
  TO quillmd_release_control;
GRANT EXECUTE ON FUNCTION template_twin_issue_release_action_receipt(
  TEXT, TEXT, UUID, UUID, TEXT, TEXT, TEXT, TEXT
) TO quillmd_release_control;
GRANT EXECUTE ON FUNCTION template_twin_release_approvals_are_current(
  UUID, CHAR(64)
) TO quillmd_release_control;
GRANT EXECUTE ON FUNCTION template_twin_issue_metric_receipt(
  TEXT, TEXT, UUID, UUID, TEXT, BIGINT, BIGINT, INTEGER,
  BIGINT, BIGINT, JSONB, BIGINT, CHAR(64)
) TO quillmd_release_control;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
  FROM quillmd_audit_dispatcher;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public
  FROM quillmd_audit_dispatcher;
GRANT SELECT, UPDATE ON "template_twin_audit_outbox"
  TO quillmd_audit_dispatcher;
GRANT SELECT, INSERT ON "audit_logs" TO quillmd_audit_dispatcher;

-- Repeat the locked default-off assertion immediately before commit.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM "template_twin_rollout_controls"
    WHERE "id" = 'global' AND (
      "enabled" = TRUE OR "rollbackFenceState" <> 'OPEN'
      OR "rollbackOperationId" IS NOT NULL
    )
  ) OR EXISTS (
    SELECT 1 FROM "practices" WHERE "templateTwinEnabled" = TRUE
  ) THEN
    RAISE EXCEPTION 'Template Twin hardening v2 lost its disabled, open-fence migration posture';
  END IF;
END;
$$;

COMMIT;
