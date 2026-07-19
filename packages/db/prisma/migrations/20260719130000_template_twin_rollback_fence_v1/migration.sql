-- Audited Template Twin rollback preparation and revocation fence.
--
-- Additive only. The singleton remains rollout-disabled by default. This
-- migration adds an independent maintenance fence and an immutable operation
-- record; it does not activate Template Twin, mutate visits/fills, or remove
-- any document, lineage, certification, audit, or object-ledger evidence.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ROLLBACK_PREPARED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ROLLBACK_CANCELLED';
ALTER TYPE "AuditAction"
  ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_ROLLOUT_REVOKED';

CREATE TABLE "template_twin_rollback_operations" (
  "id" UUID NOT NULL,
  "state" TEXT NOT NULL,
  "reasonCode" VARCHAR(80) NOT NULL,
  "changeId" VARCHAR(80) NOT NULL,
  "requestedById" TEXT NOT NULL,
  "actorPracticeId" TEXT NOT NULL,
  "actorEmailSnapshot" TEXT,
  "preparedSnapshot" JSONB NOT NULL,
  "revokedSnapshot" JSONB,
  "preparedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "revokedAt" TIMESTAMPTZ(6),
  "cancelledAt" TIMESTAMPTZ(6),
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "template_twin_rollback_operations_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_rollback_operation_state" CHECK (
    "state" IN ('PREPARED', 'REVOKED', 'CANCELLED')
  ),
  CONSTRAINT "template_twin_rollback_operation_reason" CHECK (
    "reasonCode" ~ '^[A-Z][A-Z0-9_]{2,79}$'
  ),
  CONSTRAINT "template_twin_rollback_operation_change" CHECK (
    "changeId" ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{2,79}$'
  ),
  CONSTRAINT "template_twin_rollback_operation_terminal_shape" CHECK (
    (
      "state" = 'PREPARED'
      AND "revokedAt" IS NULL
      AND "cancelledAt" IS NULL
      AND "revokedSnapshot" IS NULL
    )
    OR (
      "state" = 'REVOKED'
      AND "revokedAt" IS NOT NULL
      AND "cancelledAt" IS NULL
      AND "revokedSnapshot" IS NOT NULL
    )
    OR (
      "state" = 'CANCELLED'
      AND "revokedAt" IS NULL
      AND "cancelledAt" IS NOT NULL
      AND "revokedSnapshot" IS NULL
    )
  ),
  CONSTRAINT "template_twin_rollback_operation_actor_fkey"
    FOREIGN KEY ("requestedById") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT "template_twin_rollback_operation_practice_fkey"
    FOREIGN KEY ("actorPracticeId") REFERENCES "practices"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX "template_twin_rollback_operations_state_created_idx"
  ON "template_twin_rollback_operations"("state", "createdAt");
CREATE INDEX "template_twin_rollback_operations_practice_created_idx"
  ON "template_twin_rollback_operations"("actorPracticeId", "createdAt");

-- The operation row is a stateful audit ledger, not an editable admin record.
-- It must be created as PREPARED, can make exactly one terminal transition,
-- and can never be rewritten or deleted afterward. Application checks remain
-- useful for clear operator errors; this trigger is the database backstop.
CREATE FUNCTION template_twin_guard_rollback_operation_history()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW."state" IS DISTINCT FROM 'PREPARED' THEN
      RAISE EXCEPTION 'Template Twin rollback operation must start prepared';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Template Twin rollback operation history cannot be deleted';
  END IF;

  IF ROW(
    NEW."id", NEW."reasonCode", NEW."changeId", NEW."requestedById",
    NEW."actorPracticeId", NEW."actorEmailSnapshot", NEW."preparedSnapshot",
    NEW."preparedAt", NEW."createdAt"
  ) IS DISTINCT FROM ROW(
    OLD."id", OLD."reasonCode", OLD."changeId", OLD."requestedById",
    OLD."actorPracticeId", OLD."actorEmailSnapshot", OLD."preparedSnapshot",
    OLD."preparedAt", OLD."createdAt"
  ) THEN
    RAISE EXCEPTION 'Template Twin rollback operation identity is immutable';
  END IF;

  IF NEW."updatedAt" < OLD."updatedAt" THEN
    RAISE EXCEPTION 'Template Twin rollback operation timestamp cannot decrease';
  END IF;

  IF OLD."state" IS DISTINCT FROM 'PREPARED'
    OR NEW."state" NOT IN ('REVOKED', 'CANCELLED')
  THEN
    RAISE EXCEPTION 'Template Twin rollback operation transition is invalid';
  END IF;

  IF NEW."state" = 'REVOKED' AND (
    NEW."revokedAt" IS NULL
    OR NEW."revokedSnapshot" IS NULL
    OR NEW."cancelledAt" IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Template Twin rollback revoke evidence is incomplete';
  END IF;

  IF NEW."state" = 'CANCELLED' AND (
    NEW."revokedAt" IS NOT NULL
    OR NEW."revokedSnapshot" IS NOT NULL
    OR NEW."cancelledAt" IS NULL
  ) THEN
    RAISE EXCEPTION 'Template Twin rollback cancellation evidence is incomplete';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_rollback_operation_history_guard
BEFORE INSERT OR UPDATE OR DELETE ON "template_twin_rollback_operations"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_rollback_operation_history();

ALTER TABLE "template_twin_rollout_controls"
  ADD COLUMN "rollbackFenceState" TEXT NOT NULL DEFAULT 'OPEN',
  ADD COLUMN "rollbackFenceGeneration" BIGINT NOT NULL DEFAULT 1,
  ADD COLUMN "rollbackOperationId" UUID,
  ADD COLUMN "rollbackPreparedAt" TIMESTAMPTZ(6),
  ADD COLUMN "rollbackRevokedAt" TIMESTAMPTZ(6),
  ADD CONSTRAINT "template_twin_rollback_fence_state" CHECK (
    "rollbackFenceState" IN ('OPEN', 'PREPARED', 'REVOKED')
  ),
  ADD CONSTRAINT "template_twin_rollback_fence_generation_positive" CHECK (
    "rollbackFenceGeneration" > 0
  ),
  ADD CONSTRAINT "template_twin_rollback_fence_shape" CHECK (
    (
      "rollbackFenceState" = 'OPEN'
      AND "rollbackOperationId" IS NULL
      AND "rollbackPreparedAt" IS NULL
      AND "rollbackRevokedAt" IS NULL
    )
    OR (
      "rollbackFenceState" = 'PREPARED'
      AND "rollbackOperationId" IS NOT NULL
      AND "rollbackPreparedAt" IS NOT NULL
      AND "rollbackRevokedAt" IS NULL
    )
    OR (
      "rollbackFenceState" = 'REVOKED'
      AND "rollbackOperationId" IS NOT NULL
      AND "rollbackPreparedAt" IS NOT NULL
      AND "rollbackRevokedAt" IS NOT NULL
    )
  ),
  ADD CONSTRAINT "template_twin_rollback_operation_fkey"
    FOREIGN KEY ("rollbackOperationId")
    REFERENCES "template_twin_rollback_operations"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;

CREATE UNIQUE INDEX "template_twin_rollout_active_rollback_operation_key"
  ON "template_twin_rollout_controls"("rollbackOperationId")
  WHERE "rollbackOperationId" IS NOT NULL;

-- State transitions and their epoch are monotonic. REVOKED is terminal in
-- this rollback surface: a later release must use the separately reviewed
-- rollout-enable workflow rather than silently reopening this incident.
CREATE FUNCTION template_twin_guard_rollback_fence()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."rollbackFenceGeneration" < OLD."rollbackFenceGeneration" THEN
    RAISE EXCEPTION 'Template Twin rollback fence generation cannot decrease';
  END IF;

  IF NEW."rollbackFenceState" IS DISTINCT FROM OLD."rollbackFenceState"
    AND NEW."rollbackFenceGeneration" <= OLD."rollbackFenceGeneration"
  THEN
    NEW."rollbackFenceGeneration" := OLD."rollbackFenceGeneration" + 1;
  END IF;

  IF NOT (
    NEW."rollbackFenceState" = OLD."rollbackFenceState"
    OR (
      OLD."rollbackFenceState" = 'OPEN'
      AND NEW."rollbackFenceState" = 'PREPARED'
    )
    OR (
      OLD."rollbackFenceState" = 'PREPARED'
      AND NEW."rollbackFenceState" IN ('OPEN', 'REVOKED')
    )
  ) THEN
    RAISE EXCEPTION 'Template Twin rollback fence transition is invalid';
  END IF;

  IF NEW."rollbackFenceState" = OLD."rollbackFenceState"
    AND ROW(
      NEW."rollbackFenceGeneration", NEW."rollbackOperationId",
      NEW."rollbackPreparedAt", NEW."rollbackRevokedAt"
    ) IS DISTINCT FROM ROW(
      OLD."rollbackFenceGeneration", OLD."rollbackOperationId",
      OLD."rollbackPreparedAt", OLD."rollbackRevokedAt"
    )
  THEN
    RAISE EXCEPTION 'Template Twin rollback fence metadata cannot change without a transition';
  END IF;

  IF OLD."rollbackFenceState" = 'PREPARED'
    AND NEW."rollbackFenceState" = 'REVOKED'
    AND (
      NEW."rollbackOperationId" IS DISTINCT FROM OLD."rollbackOperationId"
      OR NEW."rollbackPreparedAt" IS DISTINCT FROM OLD."rollbackPreparedAt"
    )
  THEN
    RAISE EXCEPTION 'Template Twin rollback fence operation linkage is immutable';
  END IF;

  IF NEW."enabled" = true
    AND OLD."enabled" = false
    AND NEW."rollbackFenceState" <> 'OPEN'
  THEN
    RAISE EXCEPTION 'Template Twin cannot be enabled while rollback is fenced';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_rollback_fence_guard
BEFORE UPDATE OF
  "enabled", "rollbackFenceState", "rollbackFenceGeneration",
  "rollbackOperationId", "rollbackPreparedAt", "rollbackRevokedAt"
ON "template_twin_rollout_controls"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_rollback_fence();

-- Direct practice enablement also fails closed while the global maintenance
-- fence is engaged. Approved application mutations already lock global before
-- practice; this is a database backstop, not an approved SQL operating path.
CREATE FUNCTION template_twin_guard_practice_enable_during_rollback()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."templateTwinEnabled" = true
    AND OLD."templateTwinEnabled" = false
    AND EXISTS (
      SELECT 1
      FROM "template_twin_rollout_controls" control
      WHERE control."id" = 'global'
        AND control."rollbackFenceState" <> 'OPEN'
    )
  THEN
    RAISE EXCEPTION 'Template Twin practice cannot be enabled while rollback is fenced';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_practice_rollback_fence_guard
BEFORE UPDATE OF "templateTwinEnabled" ON "practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_practice_enable_during_rollback();

COMMIT;
