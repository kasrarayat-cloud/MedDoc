-- Template Twin rollback-fence linearization and exact audit receipts v3.
--
-- Additive hardening for the accepted v1/v2 rollback surface. The release
-- remains disabled. This migration serializes every mutation that can create
-- revocation work, preserves the complete operation event history, and binds
-- delivered outbox events to one exact immutable audit-log receipt.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TABLE "audit_logs"
  ADD COLUMN "templateTwinOutboxEventKey" TEXT;

CREATE UNIQUE INDEX "audit_logs_template_twin_outbox_event_key"
  ON "audit_logs"("templateTwinOutboxEventKey");

-- A v2 rollback may have been rehearsed before this additive migration. Only
-- an unambiguous action/target/tenant/actor match is safe to bind. Ambiguous
-- or missing historical delivery evidence fails the migration closed.
WITH rollback_receipts AS (
  SELECT
    outbox."eventKey",
    MIN(log."id") AS "auditLogId"
  FROM "template_twin_audit_outbox" outbox
  JOIN "audit_logs" log
    ON log."action" = outbox."action"
   AND log."targetType" = outbox."targetType"
   AND log."targetId" = outbox."targetId"
   AND log."practiceId" = outbox."practiceId"
   AND log."userId" IS NOT DISTINCT FROM outbox."actorId"
   AND log."userEmailSnapshot" IS NOT DISTINCT FROM outbox."actorEmailSnapshot"
   AND log."success" = TRUE
   AND log."errorCode" IS NULL
   AND log."templateTwinOutboxEventKey" IS NULL
  WHERE outbox."eventKey" ~
      '^template-twin:rollback:[0-9a-fA-F-]{36}:'
    AND outbox."status" = 'DELIVERED'
  GROUP BY outbox."eventKey"
  HAVING COUNT(*) = 1
)
UPDATE "audit_logs" log
SET "templateTwinOutboxEventKey" = receipt."eventKey"
FROM rollback_receipts receipt
WHERE log."id" = receipt."auditLogId";

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "template_twin_audit_outbox" outbox
    WHERE outbox."eventKey" ~
        '^template-twin:rollback:[0-9a-fA-F-]{36}:'
      AND outbox."status" = 'DELIVERED'
      AND NOT EXISTS (
        SELECT 1
        FROM "audit_logs" log
        WHERE log."templateTwinOutboxEventKey" = outbox."eventKey"
      )
  ) THEN
    RAISE EXCEPTION
      'Template Twin delivered rollback audit evidence cannot be bound exactly';
  END IF;
END;
$$;

ALTER TABLE "audit_logs"
  ADD CONSTRAINT "audit_logs_template_twin_outbox_event_fkey"
  FOREIGN KEY ("templateTwinOutboxEventKey")
  REFERENCES "template_twin_audit_outbox"("eventKey")
  ON DELETE RESTRICT ON UPDATE RESTRICT
  NOT VALID;

ALTER TABLE "audit_logs"
  VALIDATE CONSTRAINT "audit_logs_template_twin_outbox_event_fkey";

CREATE OR REPLACE FUNCTION template_twin_is_rollback_audit_identity(
  event_key TEXT,
  event_action "AuditAction",
  target_type TEXT
)
RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
  SELECT
    event_key ~
      '^template-twin:rollback:[0-9a-fA-F-]{36}:'
    OR (
      event_action IN (
        'TEMPLATE_TWIN_ROLLBACK_PREPARED'::"AuditAction",
        'TEMPLATE_TWIN_ROLLBACK_CANCELLED'::"AuditAction",
        'TEMPLATE_TWIN_ROLLOUT_REVOKED'::"AuditAction"
      )
      AND target_type = 'TemplateTwinRollbackOperation'
    );
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_rollback_outbox_history()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  old_is_rollback BOOLEAN;
  new_is_rollback BOOLEAN;
BEGIN
  old_is_rollback := FALSE;
  new_is_rollback := FALSE;
  IF TG_OP <> 'INSERT' THEN
    old_is_rollback := template_twin_is_rollback_audit_identity(
      OLD."eventKey", OLD."action", OLD."targetType"
    );
  END IF;
  IF TG_OP <> 'DELETE' THEN
    new_is_rollback := template_twin_is_rollback_audit_identity(
      NEW."eventKey", NEW."action", NEW."targetType"
    );
  END IF;

  IF TG_OP = 'DELETE' AND old_is_rollback THEN
    RAISE EXCEPTION 'Template Twin rollback outbox evidence cannot be deleted';
  END IF;

  IF TG_OP = 'UPDATE' AND (old_is_rollback OR new_is_rollback) THEN
    IF ROW(
      NEW."id", NEW."practiceId", NEW."actorId",
      NEW."actorEmailSnapshot", NEW."ipAddress", NEW."userAgent",
      NEW."eventKey", NEW."action", NEW."targetId", NEW."targetType",
      NEW."metadata", NEW."createdAt"
    ) IS DISTINCT FROM ROW(
      OLD."id", OLD."practiceId", OLD."actorId",
      OLD."actorEmailSnapshot", OLD."ipAddress", OLD."userAgent",
      OLD."eventKey", OLD."action", OLD."targetId", OLD."targetType",
      OLD."metadata", OLD."createdAt"
    ) THEN
      RAISE EXCEPTION 'Template Twin rollback outbox identity is immutable';
    END IF;

    IF OLD."status" = 'DELIVERED' AND ROW(
      NEW."status", NEW."attemptCount", NEW."availableAt",
      NEW."deliveredAt", NEW."lastErrorCode", NEW."updatedAt"
    ) IS DISTINCT FROM ROW(
      OLD."status", OLD."attemptCount", OLD."availableAt",
      OLD."deliveredAt", OLD."lastErrorCode", OLD."updatedAt"
    ) THEN
      RAISE EXCEPTION 'Template Twin delivered rollback receipt is immutable';
    END IF;

    IF NEW."status" = 'DELIVERED' AND NEW."deliveredAt" IS NULL THEN
      RAISE EXCEPTION 'Template Twin delivered rollback receipt is incomplete';
    END IF;
  END IF;

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_rollback_outbox_history_guard
BEFORE UPDATE OR DELETE ON "template_twin_audit_outbox"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_rollback_outbox_history();

CREATE OR REPLACE FUNCTION template_twin_guard_rollback_audit_log_history()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  old_is_rollback BOOLEAN;
  new_is_rollback BOOLEAN;
BEGIN
  old_is_rollback := FALSE;
  new_is_rollback := FALSE;
  IF TG_OP <> 'INSERT' THEN
    old_is_rollback := template_twin_is_rollback_audit_identity(
      OLD."templateTwinOutboxEventKey", OLD."action", OLD."targetType"
    );
  END IF;
  IF TG_OP <> 'DELETE' THEN
    new_is_rollback := template_twin_is_rollback_audit_identity(
      NEW."templateTwinOutboxEventKey", NEW."action", NEW."targetType"
    );
  END IF;

  IF TG_OP = 'DELETE' AND old_is_rollback THEN
    RAISE EXCEPTION 'Template Twin rollback audit receipt cannot be deleted';
  END IF;
  IF TG_OP = 'UPDATE' AND (old_is_rollback OR new_is_rollback) THEN
    RAISE EXCEPTION 'Template Twin rollback audit receipt is immutable';
  END IF;

  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_rollback_audit_log_history_guard
BEFORE UPDATE OR DELETE ON "audit_logs"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_rollback_audit_log_history();

CREATE OR REPLACE FUNCTION template_twin_reject_rollback_audit_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin rollback audit evidence cannot be truncated';
END;
$$;

CREATE TRIGGER template_twin_rollback_outbox_truncate_guard
BEFORE TRUNCATE ON "template_twin_audit_outbox"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_rollback_audit_truncate();

CREATE TRIGGER template_twin_rollback_audit_log_truncate_guard
BEFORE TRUNCATE ON "audit_logs"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_rollback_audit_truncate();

CREATE OR REPLACE FUNCTION template_twin_assert_rollback_audit_delivery()
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "template_twin_audit_outbox" outbox
    WHERE template_twin_is_rollback_audit_identity(
        outbox."eventKey", outbox."action", outbox."targetType"
      )
      AND outbox."status" = 'DELIVERED'
      AND (
        outbox."deliveredAt" IS NULL
        OR NOT EXISTS (
          SELECT 1
          FROM "audit_logs" log
          WHERE log."templateTwinOutboxEventKey" = outbox."eventKey"
            AND log."action" = outbox."action"
            AND log."targetType" = outbox."targetType"
            AND log."targetId" = outbox."targetId"
            AND log."practiceId" = outbox."practiceId"
            AND log."userId" IS NOT DISTINCT FROM outbox."actorId"
            AND log."userEmailSnapshot" IS NOT DISTINCT FROM
              outbox."actorEmailSnapshot"
            AND log."success" = TRUE
            AND log."errorCode" IS NULL
        )
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin delivered rollback audit receipt is missing';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "audit_logs" log
    WHERE template_twin_is_rollback_audit_identity(
        log."templateTwinOutboxEventKey", log."action", log."targetType"
      )
      AND NOT EXISTS (
        SELECT 1
        FROM "template_twin_audit_outbox" outbox
        WHERE outbox."eventKey" = log."templateTwinOutboxEventKey"
          AND outbox."status" = 'DELIVERED'
          AND outbox."deliveredAt" IS NOT NULL
          AND outbox."action" = log."action"
          AND outbox."targetType" = log."targetType"
          AND outbox."targetId" = log."targetId"
          AND outbox."practiceId" = log."practiceId"
      )
  ) THEN
    RAISE EXCEPTION 'Template Twin rollback audit receipt is not bound to delivery';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_check_rollback_outbox_delivery()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  relevant BOOLEAN;
BEGIN
  IF TG_OP = 'INSERT' THEN
    relevant := template_twin_is_rollback_audit_identity(
      NEW."eventKey", NEW."action", NEW."targetType"
    );
  ELSIF TG_OP = 'DELETE' THEN
    relevant := template_twin_is_rollback_audit_identity(
      OLD."eventKey", OLD."action", OLD."targetType"
    );
  ELSE
    relevant := template_twin_is_rollback_audit_identity(
      OLD."eventKey", OLD."action", OLD."targetType"
    ) OR template_twin_is_rollback_audit_identity(
      NEW."eventKey", NEW."action", NEW."targetType"
    );
  END IF;
  IF relevant THEN
    PERFORM template_twin_assert_rollback_audit_delivery();
  END IF;
  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER template_twin_rollback_outbox_delivery_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_audit_outbox"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_check_rollback_outbox_delivery();

CREATE OR REPLACE FUNCTION template_twin_check_rollback_audit_log_delivery()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  relevant BOOLEAN;
BEGIN
  IF TG_OP = 'INSERT' THEN
    relevant := template_twin_is_rollback_audit_identity(
      NEW."templateTwinOutboxEventKey", NEW."action", NEW."targetType"
    );
  ELSIF TG_OP = 'DELETE' THEN
    relevant := template_twin_is_rollback_audit_identity(
      OLD."templateTwinOutboxEventKey", OLD."action", OLD."targetType"
    );
  ELSE
    relevant := template_twin_is_rollback_audit_identity(
      OLD."templateTwinOutboxEventKey", OLD."action", OLD."targetType"
    ) OR template_twin_is_rollback_audit_identity(
      NEW."templateTwinOutboxEventKey", NEW."action", NEW."targetType"
    );
  END IF;
  IF relevant THEN
    PERFORM template_twin_assert_rollback_audit_delivery();
  END IF;
  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER template_twin_rollback_audit_log_delivery_guard
AFTER INSERT OR UPDATE OR DELETE ON "audit_logs"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_check_rollback_audit_log_delivery();

-- One advisory transaction lock serializes a rollback transition with every
-- mutation that can enter the drain inventory. The lock is acquired before
-- direct control DML and explicitly before the application locks the singleton.
CREATE OR REPLACE FUNCTION template_twin_acquire_rollback_linearization_lock()
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(73119, 20260719);
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_lock_rollback_control_statement()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM template_twin_acquire_rollback_linearization_lock();
  RETURN NULL;
END;
$$;

CREATE TRIGGER aaa_template_twin_rollout_control_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_rollout_controls"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_rollback_control_statement();

CREATE TRIGGER aaa_template_twin_rollback_operation_linearization_lock
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_rollback_operations"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_lock_rollback_control_statement();

CREATE OR REPLACE FUNCTION template_twin_require_open_rollback_fence(
  rejection_message TEXT
)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
  current_state TEXT;
BEGIN
  PERFORM template_twin_acquire_rollback_linearization_lock();
  SELECT "rollbackFenceState" INTO current_state
  FROM "template_twin_rollout_controls"
  WHERE "id" = 'global';

  IF NOT FOUND OR current_state <> 'OPEN' THEN
    RAISE EXCEPTION '%', rejection_message USING ERRCODE = '55000';
  END IF;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_practice_enable_during_rollback()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."templateTwinEnabled" = TRUE AND (
    TG_OP = 'INSERT'
    OR OLD."templateTwinEnabled" = FALSE
  ) THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin practice cannot be enabled while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aa_template_twin_practice_rollback_insert_guard
BEFORE INSERT ON "practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_practice_enable_during_rollback();

-- Replaces the v2 body used by its existing INSERT/UPDATE triggers. Creating
-- any new Twin version, converting a legacy version, or activating an existing
-- Twin now participates in the same linearization lock.
CREATE OR REPLACE FUNCTION template_twin_guard_active_version_during_rollback()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."templateKind" = 'template_twin_docx' AND (
    TG_OP = 'INSERT'
    OR OLD."templateKind" IS DISTINCT FROM 'template_twin_docx'
    OR (
      NEW."status" = 'active'
      AND OLD."status" IS DISTINCT FROM 'active'
    )
  ) THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin version cannot be activated while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_fill_entering_rollback_inventory()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  deleted_fill_would_pin_visit BOOLEAN := FALSE;
BEGIN
  IF TG_OP = 'DELETE' THEN
    SELECT EXISTS (
      SELECT 1
      FROM "transcribe_visits" visit
      JOIN "note_templates" template ON template."id" = visit."noteTemplateId"
      WHERE visit."id" = OLD."visitId"
        AND visit."status" NOT IN ('FAILED', 'SIGNED')
        AND template."templateKind" = 'template_twin_docx'
    ) INTO deleted_fill_would_pin_visit;
    IF deleted_fill_would_pin_visit THEN
      PERFORM template_twin_require_open_rollback_fence(
        'Template Twin fill work cannot be removed while rollback is fenced'
      );
    END IF;
    RETURN OLD;
  END IF;

  IF TG_OP = 'INSERT' OR (
    NEW."status" IN ('RESOLVING', 'NEEDS_REVIEW', 'VERIFIED')
    AND OLD."status" NOT IN ('RESOLVING', 'NEEDS_REVIEW', 'VERIFIED')
  ) THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin fill work cannot start while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aa_template_twin_fill_rollback_insert_guard
BEFORE INSERT ON "template_twin_fill_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_fill_entering_rollback_inventory();

CREATE TRIGGER aa_template_twin_fill_rollback_update_guard
BEFORE UPDATE OF "status" ON "template_twin_fill_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_fill_entering_rollback_inventory();

CREATE TRIGGER aa_template_twin_fill_rollback_delete_guard
BEFORE DELETE ON "template_twin_fill_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_fill_entering_rollback_inventory();

CREATE OR REPLACE FUNCTION template_twin_guard_visit_entering_rollback_inventory()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  new_is_twin BOOLEAN;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM "note_templates" template
    WHERE template."id" = NEW."noteTemplateId"
      AND template."templateKind" = 'template_twin_docx'
  ) INTO new_is_twin;

  IF new_is_twin
    AND NEW."status" NOT IN ('FAILED', 'SIGNED')
    AND (
      TG_OP = 'INSERT'
      OR OLD."noteTemplateId" IS DISTINCT FROM NEW."noteTemplateId"
      OR OLD."status" IN ('FAILED', 'SIGNED')
    )
  THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin pinned visit cannot start while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aa_template_twin_visit_rollback_insert_guard
BEFORE INSERT ON "transcribe_visits"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_visit_entering_rollback_inventory();

CREATE TRIGGER aa_template_twin_visit_rollback_update_guard
BEFORE UPDATE OF "noteTemplateId", "status" ON "transcribe_visits"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_visit_entering_rollback_inventory();

CREATE OR REPLACE FUNCTION template_twin_guard_synthetic_run_entering_rollback_inventory()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."status" NOT IN ('COMPLETED', 'PROCESSING_FAILED') AND (
    TG_OP = 'INSERT'
    OR OLD."status" IN ('COMPLETED', 'PROCESSING_FAILED')
  ) THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin synthetic run cannot start while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aa_template_twin_synthetic_run_rollback_insert_guard
BEFORE INSERT ON "template_twin_synthetic_qa_runs"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_run_entering_rollback_inventory();

CREATE TRIGGER aa_template_twin_synthetic_run_rollback_update_guard
BEFORE UPDATE OF "status" ON "template_twin_synthetic_qa_runs"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_run_entering_rollback_inventory();

CREATE OR REPLACE FUNCTION template_twin_guard_synthetic_admission_entering_rollback_inventory()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."phase" NOT IN ('SIGNED', 'FAILED', 'REVOKED') AND (
    TG_OP = 'INSERT'
    OR OLD."phase" IN ('SIGNED', 'FAILED', 'REVOKED')
  ) THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin synthetic admission cannot start while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aa_template_twin_synthetic_admission_rollback_insert_guard
BEFORE INSERT ON "template_twin_synthetic_qa_admissions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_admission_entering_rollback_inventory();

CREATE TRIGGER aa_template_twin_synthetic_admission_rollback_update_guard
BEFORE UPDATE OF "phase" ON "template_twin_synthetic_qa_admissions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_synthetic_admission_entering_rollback_inventory();

CREATE OR REPLACE FUNCTION template_twin_manifest_has_rollback_context(
  visit_id TEXT,
  staging_admission_id TEXT,
  staging_run_id TEXT
)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
  SELECT
    staging_admission_id IS NOT NULL
    OR staging_run_id IS NOT NULL
    OR EXISTS (
      SELECT 1 FROM "template_twin_fill_manifests" fill
      WHERE fill."visitId" = visit_id
    )
    OR EXISTS (
      SELECT 1
      FROM "transcribe_visits" visit
      JOIN "note_templates" template ON template."id" = visit."noteTemplateId"
      WHERE visit."id" = visit_id
        AND template."templateKind" = 'template_twin_docx'
    );
$$;

CREATE OR REPLACE FUNCTION template_twin_guard_manifest_entering_rollback_inventory()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  new_has_context BOOLEAN;
  old_has_context BOOLEAN := FALSE;
BEGIN
  new_has_context := template_twin_manifest_has_rollback_context(
    NEW."visitId", NEW."stagingAdmissionId", NEW."stagingRunId"
  );
  IF TG_OP = 'UPDATE' THEN
    old_has_context := template_twin_manifest_has_rollback_context(
      OLD."visitId", OLD."stagingAdmissionId", OLD."stagingRunId"
    );
  END IF;

  IF new_has_context
    AND NEW."status" IN ('PENDING', 'RUNNING')
    AND (
      TG_OP = 'INSERT'
      OR OLD."status" NOT IN ('PENDING', 'RUNNING')
      OR NOT old_has_context
    )
  THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin automation work cannot start while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aa_template_twin_manifest_rollback_insert_guard
BEFORE INSERT ON "visit_automation_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_manifest_entering_rollback_inventory();

CREATE TRIGGER aa_template_twin_manifest_rollback_update_guard
BEFORE UPDATE OF "status", "visitId", "stagingAdmissionId", "stagingRunId"
ON "visit_automation_manifests"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_manifest_entering_rollback_inventory();

CREATE OR REPLACE FUNCTION template_twin_guard_provider_entering_rollback_inventory()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  new_has_context BOOLEAN;
  old_has_context BOOLEAN := FALSE;
BEGIN
  new_has_context := template_twin_manifest_has_rollback_context(
    NEW."visitId", NEW."stagingAdmissionId", NEW."stagingRunId"
  );
  IF TG_OP = 'UPDATE' THEN
    old_has_context := template_twin_manifest_has_rollback_context(
      OLD."visitId", OLD."stagingAdmissionId", OLD."stagingRunId"
    );
  END IF;

  IF new_has_context
    AND NEW."status" IN ('RESERVED', 'IN_FLIGHT', 'UNKNOWN_OUTCOME')
    AND (
      TG_OP = 'INSERT'
      OR OLD."status" NOT IN ('RESERVED', 'IN_FLIGHT', 'UNKNOWN_OUTCOME')
      OR NOT old_has_context
    )
  THEN
    PERFORM template_twin_require_open_rollback_fence(
      'Template Twin provider work cannot start while rollback is fenced'
    );
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER aa_template_twin_provider_rollback_insert_guard
BEFORE INSERT ON "visit_automation_provider_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_provider_entering_rollback_inventory();

CREATE TRIGGER aa_template_twin_provider_rollback_update_guard
BEFORE UPDATE OF "status", "visitId", "stagingAdmissionId", "stagingRunId"
ON "visit_automation_provider_executions"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_provider_entering_rollback_inventory();

-- Replace the v2 commit assertion so PREPARED evidence remains required after
-- cancellation or revocation instead of accepting only the current state.
CREATE OR REPLACE FUNCTION template_twin_assert_rollback_fence_coupling()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  control_state TEXT;
  control_operation UUID;
  control_enabled BOOLEAN;
  linked_operation_state TEXT;
BEGIN
  SELECT "rollbackFenceState", "rollbackOperationId", "enabled"
    INTO control_state, control_operation, control_enabled
  FROM "template_twin_rollout_controls"
  WHERE "id" = 'global';

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Template Twin rollout singleton is missing';
  END IF;
  IF EXISTS (
    SELECT 1 FROM "template_twin_rollout_controls" WHERE "id" <> 'global'
  ) THEN
    RAISE EXCEPTION 'Template Twin rollout singleton cardinality is invalid';
  END IF;

  IF control_operation IS NOT NULL THEN
    SELECT "state" INTO linked_operation_state
    FROM "template_twin_rollback_operations"
    WHERE "id" = control_operation;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Template Twin rollback fence operation is missing';
    END IF;
  END IF;

  IF control_state = 'OPEN' THEN
    IF control_operation IS NOT NULL THEN
      RAISE EXCEPTION 'Template Twin open fence cannot retain an operation';
    END IF;
  ELSIF control_state = 'PREPARED' THEN
    IF control_operation IS NULL OR linked_operation_state <> 'PREPARED' THEN
      RAISE EXCEPTION 'Template Twin prepared fence must link a prepared operation';
    END IF;
  ELSIF control_state = 'REVOKED' THEN
    IF control_operation IS NULL OR linked_operation_state <> 'REVOKED' THEN
      RAISE EXCEPTION 'Template Twin revoked fence must link a revoked operation';
    END IF;
    IF control_enabled THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires global rollout disabled';
    END IF;
    IF EXISTS (
      SELECT 1 FROM "practices" WHERE "templateTwinEnabled" = TRUE
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires all practices disabled';
    END IF;
    IF EXISTS (
      SELECT 1 FROM "note_templates"
      WHERE "templateKind" = 'template_twin_docx' AND "status" = 'active'
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires all versions inactive';
    END IF;
    IF EXISTS (
      SELECT 1 FROM "template_twin_fill_manifests"
      WHERE "status" IN ('RESOLVING', 'NEEDS_REVIEW', 'VERIFIED')
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires fill work drained';
    END IF;
    IF EXISTS (
      SELECT 1
      FROM "transcribe_visits" visit
      JOIN "note_templates" template ON template."id" = visit."noteTemplateId"
      LEFT JOIN "template_twin_fill_manifests" fill ON fill."visitId" = visit."id"
      WHERE template."templateKind" = 'template_twin_docx'
        AND visit."status" NOT IN ('FAILED', 'SIGNED')
        AND fill."id" IS NULL
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires pinned visits drained';
    END IF;
    IF EXISTS (
      SELECT 1 FROM "template_twin_synthetic_qa_runs"
      WHERE "status" NOT IN ('COMPLETED', 'PROCESSING_FAILED')
    ) OR EXISTS (
      SELECT 1 FROM "template_twin_synthetic_qa_admissions"
      WHERE "phase" NOT IN ('SIGNED', 'FAILED', 'REVOKED')
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires synthetic work drained';
    END IF;
    IF EXISTS (
      SELECT 1 FROM "visit_automation_provider_executions" execution
      WHERE execution."status" IN ('RESERVED', 'IN_FLIGHT', 'UNKNOWN_OUTCOME')
        AND template_twin_manifest_has_rollback_context(
          execution."visitId", execution."stagingAdmissionId",
          execution."stagingRunId"
        )
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires provider work drained';
    END IF;
    IF EXISTS (
      SELECT 1 FROM "visit_automation_manifests" manifest
      WHERE manifest."status" IN ('PENDING', 'RUNNING')
        AND template_twin_manifest_has_rollback_context(
          manifest."visitId", manifest."stagingAdmissionId",
          manifest."stagingRunId"
        )
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires automation work drained';
    END IF;
  ELSE
    RAISE EXCEPTION 'Template Twin rollback fence state is invalid';
  END IF;

  IF EXISTS (
    SELECT 1 FROM "template_twin_rollback_operations" operation
    WHERE operation."state" = 'PREPARED'
      AND operation."id" IS DISTINCT FROM control_operation
  ) THEN
    RAISE EXCEPTION 'Template Twin prepared operation must own the fence';
  END IF;

  IF EXISTS (
    WITH expected AS (
      SELECT
        operation."id", operation."actorPracticeId",
        operation."requestedById", operation."actorEmailSnapshot",
        'prepared'::TEXT AS stage,
        'TEMPLATE_TWIN_ROLLBACK_PREPARED'::"AuditAction" AS action
      FROM "template_twin_rollback_operations" operation
      UNION ALL
      SELECT
        operation."id", operation."actorPracticeId",
        operation."requestedById", operation."actorEmailSnapshot",
        CASE operation."state"
          WHEN 'CANCELLED' THEN 'cancelled'
          WHEN 'REVOKED' THEN 'revoked'
        END,
        CASE operation."state"
          WHEN 'CANCELLED' THEN
            'TEMPLATE_TWIN_ROLLBACK_CANCELLED'::"AuditAction"
          WHEN 'REVOKED' THEN
            'TEMPLATE_TWIN_ROLLOUT_REVOKED'::"AuditAction"
        END
      FROM "template_twin_rollback_operations" operation
      WHERE operation."state" IN ('CANCELLED', 'REVOKED')
    )
    SELECT 1
    FROM expected
    WHERE NOT EXISTS (
      SELECT 1
      FROM "template_twin_audit_outbox" audit
      WHERE audit."eventKey" =
          'template-twin:rollback:' || expected."id"::TEXT || ':' || expected.stage
        AND audit."targetType" = 'TemplateTwinRollbackOperation'
        AND audit."targetId" = expected."id"::TEXT
        AND audit."practiceId" = expected."actorPracticeId"
        AND audit."actorId" = expected."requestedById"
        AND audit."actorEmailSnapshot" IS NOT DISTINCT FROM
          expected."actorEmailSnapshot"
        AND audit."action" = expected.action
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin rollback operation audit history is incomplete';
  END IF;

  RETURN NULL;
END;
$$;

COMMIT;
