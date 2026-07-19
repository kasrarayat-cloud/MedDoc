-- Template Twin linearizable rollout revocation.
--
-- This is additive and does not rewrite existing Template Twin migrations.
-- The persisted global gate is deliberately seeded disabled. Existing
-- practice flags also remain default-off. Operators must explicitly enable
-- both database scopes in addition to disabling the environment kill switch.

-- Prisma Migrate executes this explicit transaction as written. Every table,
-- trigger, and constraint lock below is therefore covered by one
-- transaction-local timeout. A conflicting workload fails the migration
-- quickly and rolls back the complete rollout-generation contract; no session
-- setting leaks into a later migration attempt.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';

ALTER TABLE "practices"
  ADD COLUMN "templateTwinRolloutGeneration" BIGINT NOT NULL DEFAULT 1;

ALTER TABLE "practices"
  ADD CONSTRAINT "practices_template_twin_rollout_generation_positive"
  CHECK ("templateTwinRolloutGeneration" > 0);

CREATE TABLE "template_twin_rollout_controls" (
  "id" TEXT NOT NULL,
  "enabled" BOOLEAN NOT NULL DEFAULT false,
  "generation" BIGINT NOT NULL DEFAULT 1,
  "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "template_twin_rollout_controls_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "template_twin_rollout_generation_positive"
    CHECK ("generation" > 0),
  CONSTRAINT "template_twin_rollout_singleton"
    CHECK ("id" = 'global')
);

INSERT INTO "template_twin_rollout_controls" (
  "id", "enabled", "generation"
) VALUES ('global', false, 1);

-- Direct SQL/config paths cannot change enabled state without advancing the
-- epoch. Explicit service updates may provide OLD+1; ad-hoc state changes are
-- normalized to OLD+1. Generation rollback is always rejected.
CREATE FUNCTION template_twin_guard_global_rollout_generation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."generation" < OLD."generation" THEN
    RAISE EXCEPTION 'Template Twin global rollout generation cannot decrease';
  END IF;
  IF NEW."enabled" IS DISTINCT FROM OLD."enabled"
     AND NEW."generation" <= OLD."generation" THEN
    NEW."generation" := OLD."generation" + 1;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_global_rollout_generation_guard
BEFORE UPDATE ON "template_twin_rollout_controls"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_global_rollout_generation();

CREATE FUNCTION template_twin_guard_practice_rollout_generation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW."templateTwinRolloutGeneration" <
     OLD."templateTwinRolloutGeneration" THEN
    RAISE EXCEPTION 'Template Twin practice rollout generation cannot decrease';
  END IF;
  IF NEW."templateTwinEnabled" IS DISTINCT FROM OLD."templateTwinEnabled"
     AND NEW."templateTwinRolloutGeneration" <=
       OLD."templateTwinRolloutGeneration" THEN
    NEW."templateTwinRolloutGeneration" :=
      OLD."templateTwinRolloutGeneration" + 1;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER template_twin_practice_rollout_generation_guard
BEFORE UPDATE OF "templateTwinEnabled", "templateTwinRolloutGeneration"
ON "practices"
FOR EACH ROW EXECUTE FUNCTION template_twin_guard_practice_rollout_generation();

ALTER TABLE "template_twin_fill_manifests"
  ADD COLUMN "pinnedGlobalRolloutGeneration" BIGINT,
  ADD COLUMN "pinnedPracticeRolloutGeneration" BIGINT,
  ADD COLUMN "signedGlobalRolloutGeneration" BIGINT,
  ADD COLUMN "signedPracticeRolloutGeneration" BIGINT;

ALTER TABLE "template_twin_fill_manifests"
  ADD CONSTRAINT "template_twin_fill_pinned_rollout_pair" CHECK (
    ("pinnedGlobalRolloutGeneration" IS NULL
      AND "pinnedPracticeRolloutGeneration" IS NULL)
    OR
    ("pinnedGlobalRolloutGeneration" > 0
      AND "pinnedPracticeRolloutGeneration" > 0)
  ),
  ADD CONSTRAINT "template_twin_fill_signed_rollout_pair" CHECK (
    ("signedGlobalRolloutGeneration" IS NULL
      AND "signedPracticeRolloutGeneration" IS NULL)
    OR
    ("signedGlobalRolloutGeneration" > 0
      AND "signedPracticeRolloutGeneration" > 0
      AND "pinnedGlobalRolloutGeneration" IS NOT NULL
      AND "pinnedPracticeRolloutGeneration" IS NOT NULL)
  ),
  -- Existing signed prototype rows remain immutable and are not rewritten.
  -- PostgreSQL enforces this constraint for every new/updated row even while
  -- NOT VALID leaves those legacy rows unscanned.
  ADD CONSTRAINT "template_twin_fill_signed_rollout_matches_pinned" CHECK (
    "status" <> 'SIGNED'
    OR (
      "signedGlobalRolloutGeneration" =
        "pinnedGlobalRolloutGeneration"
      AND "signedPracticeRolloutGeneration" =
        "pinnedPracticeRolloutGeneration"
    )
  ) NOT VALID;

COMMIT;
