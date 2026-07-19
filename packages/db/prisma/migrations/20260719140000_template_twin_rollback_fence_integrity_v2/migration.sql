-- Template Twin rollback-fence integrity v2.
--
-- Additive hardening for the v1 operational fence. This migration does not
-- enable rollout, alter physician documents, rewrite historical operations,
-- or discard clinical/audit/object evidence. It makes the singleton and its
-- incident ledger inseparable at transaction commit and adds a database
-- backstop against activating a Template Twin while maintenance is fenced.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

CREATE UNIQUE INDEX "template_twin_one_prepared_rollback_operation_key"
  ON "template_twin_rollback_operations" (("state"))
  WHERE "state" = 'PREPARED';

CREATE OR REPLACE FUNCTION template_twin_guard_rollout_singleton_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    RAISE EXCEPTION 'Template Twin rollout singleton cannot be inserted';
  ELSIF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin rollout singleton cannot be deleted';
  ELSE
    RAISE EXCEPTION 'Template Twin rollout singleton identity is immutable';
  END IF;
END;
$$;

CREATE TRIGGER template_twin_rollout_singleton_insert_delete_guard
BEFORE INSERT OR DELETE ON "template_twin_rollout_controls"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_rollout_singleton_history();

CREATE TRIGGER template_twin_rollout_singleton_identity_guard
BEFORE UPDATE OF "id" ON "template_twin_rollout_controls"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_rollout_singleton_history();

CREATE OR REPLACE FUNCTION template_twin_reject_rollback_control_truncate()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'Template Twin rollback control history cannot be truncated';
END;
$$;

CREATE TRIGGER template_twin_rollout_singleton_truncate_guard
BEFORE TRUNCATE ON "template_twin_rollout_controls"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_rollback_control_truncate();

CREATE TRIGGER template_twin_rollback_operation_truncate_guard
BEFORE TRUNCATE ON "template_twin_rollback_operations"
FOR EACH STATEMENT EXECUTE FUNCTION template_twin_reject_rollback_control_truncate();

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
      SELECT 1
      FROM "visit_automation_provider_executions" execution
      WHERE execution."status" IN ('RESERVED', 'IN_FLIGHT', 'UNKNOWN_OUTCOME')
        AND (
          execution."stagingAdmissionId" IS NOT NULL
          OR execution."stagingRunId" IS NOT NULL
          OR EXISTS (
            SELECT 1 FROM "template_twin_fill_manifests" fill
            WHERE fill."visitId" = execution."visitId"
          )
          OR EXISTS (
            SELECT 1
            FROM "transcribe_visits" visit
            JOIN "note_templates" template
              ON template."id" = visit."noteTemplateId"
            WHERE visit."id" = execution."visitId"
              AND template."templateKind" = 'template_twin_docx'
          )
        )
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires provider work drained';
    END IF;
    IF EXISTS (
      SELECT 1
      FROM "visit_automation_manifests" manifest
      WHERE manifest."status" IN ('PENDING', 'RUNNING')
        AND (
          manifest."stagingAdmissionId" IS NOT NULL
          OR manifest."stagingRunId" IS NOT NULL
          OR EXISTS (
            SELECT 1 FROM "template_twin_fill_manifests" fill
            WHERE fill."visitId" = manifest."visitId"
          )
          OR EXISTS (
            SELECT 1
            FROM "transcribe_visits" visit
            JOIN "note_templates" template
              ON template."id" = visit."noteTemplateId"
            WHERE visit."id" = manifest."visitId"
              AND template."templateKind" = 'template_twin_docx'
          )
        )
    ) THEN
      RAISE EXCEPTION 'Template Twin revoked fence requires automation work drained';
    END IF;
  ELSE
    RAISE EXCEPTION 'Template Twin rollback fence state is invalid';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "template_twin_rollback_operations" operation
    WHERE operation."state" = 'PREPARED'
      AND operation."id" IS DISTINCT FROM control_operation
  ) THEN
    RAISE EXCEPTION 'Template Twin prepared operation must own the fence';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "template_twin_rollback_operations" operation
    WHERE NOT EXISTS (
      SELECT 1
      FROM "template_twin_audit_outbox" audit
      WHERE audit."eventKey" =
        'template-twin:rollback:' || operation."id"::TEXT ||
        CASE operation."state"
          WHEN 'PREPARED' THEN ':prepared'
          WHEN 'CANCELLED' THEN ':cancelled'
          WHEN 'REVOKED' THEN ':revoked'
        END
        AND audit."targetType" = 'TemplateTwinRollbackOperation'
        AND audit."targetId" = operation."id"::TEXT
        AND audit."practiceId" = operation."actorPracticeId"
        AND audit."action" = CASE operation."state"
          WHEN 'PREPARED' THEN 'TEMPLATE_TWIN_ROLLBACK_PREPARED'::"AuditAction"
          WHEN 'CANCELLED' THEN 'TEMPLATE_TWIN_ROLLBACK_CANCELLED'::"AuditAction"
          WHEN 'REVOKED' THEN 'TEMPLATE_TWIN_ROLLOUT_REVOKED'::"AuditAction"
        END
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin rollback operation audit evidence is missing';
  END IF;

  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER template_twin_rollout_fence_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_rollout_controls"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_rollback_fence_coupling();

CREATE CONSTRAINT TRIGGER template_twin_rollback_operation_coupling_guard
AFTER INSERT OR UPDATE OR DELETE ON "template_twin_rollback_operations"
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION template_twin_assert_rollback_fence_coupling();

CREATE OR REPLACE FUNCTION template_twin_guard_active_version_during_rollback()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."templateKind" = 'template_twin_docx'
    AND NEW."status" = 'active'
    AND NOT EXISTS (
      SELECT 1
      FROM "template_twin_rollout_controls"
      WHERE "id" = 'global' AND "rollbackFenceState" = 'OPEN'
    )
  THEN
    RAISE EXCEPTION 'Template Twin version cannot be activated while rollback is fenced';
  END IF;
  RETURN NEW;
END;
$$;

-- The aa_ prefix is deliberate: PostgreSQL fires same-kind triggers in name
-- order, so the maintenance fence rejects first and cannot be obscured by a
-- later source-admission error.
CREATE TRIGGER aa_template_twin_active_version_rollback_insert_guard
BEFORE INSERT ON "note_templates"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_active_version_during_rollback();

CREATE TRIGGER aa_template_twin_active_version_rollback_update_guard
BEFORE UPDATE OF "templateKind", "status" ON "note_templates"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_active_version_during_rollback();

COMMIT;
