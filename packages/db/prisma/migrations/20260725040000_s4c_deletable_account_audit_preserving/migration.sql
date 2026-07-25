-- ============================================================================
-- S4c — make account deletion possible WITHOUT deleting the audit trail.
-- ----------------------------------------------------------------------------
-- Account deletion was deterministically broken. POST /api/settings/delete-account
-- ends in a transaction that deletes the User then the Practice, and FIFTEEN
-- foreign keys referencing practices/users were ON DELETE RESTRICT — so the
-- transaction always rolled back and the route always returned 500. Nobody
-- could delete their account. Two consequences worth naming:
--
--   * the ACCOUNT_DELETED audit row is written AFTER the transaction, so it
--     was never reached — and it passed the now-deleted practiceId, so it
--     would have FK-violated anyway. The call is `void logAudit(...)`, so that
--     violation was swallowed silently.
--   * rx_warning_overrides.visitId was RESTRICT, which also blocked the
--     User -> TranscribeVisit cascade for any doctor who had ever overridden
--     an Rx warning. Independent of the practice problem.
--
-- The principle applied here, per the audit-preserving pattern:
--
--   AUDIT AND FINANCIAL RECORDS ARE NEVER DELETED. Their references are
--   DETACHED (SET NULL) so the row outlives the entity it describes.
--   Everything that is genuinely the user's own content CASCADES.
--
-- audit_logs additionally gains practiceIdSnapshot, a tombstone with no FK, so
-- "which tenant did this happen in" stays answerable after the practice row is
-- gone — the same role userEmailSnapshot already plays for the user.
--
-- ADDITIVE / NON-DESTRUCTIVE: no row is deleted by this migration. One column
-- is added and backfilled; the rest are nullability and FK-action changes.
--
-- ROLLBACK: re-assert NOT NULL and restore RESTRICT on each constraint below
-- (safe only while no row has a NULL in these columns — i.e. before the first
-- account deletion). practiceIdSnapshot can be left in place; it is inert.
-- ============================================================================

-- ── audit_logs — DETACH, never delete ───────────────────────────────────────
ALTER TABLE "audit_logs" ADD COLUMN "practiceIdSnapshot" TEXT;
UPDATE "audit_logs" SET "practiceIdSnapshot" = "practiceId" WHERE "practiceIdSnapshot" IS NULL;
ALTER TABLE "audit_logs" ALTER COLUMN "practiceId" DROP NOT NULL;
ALTER TABLE "audit_logs" DROP CONSTRAINT "audit_logs_practiceId_fkey";
ALTER TABLE "audit_logs" ADD CONSTRAINT "audit_logs_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- ── billing_events — a financial record must outlive both refs ──────────────
ALTER TABLE "billing_events" ALTER COLUMN "practiceId" DROP NOT NULL;
ALTER TABLE "billing_events" ALTER COLUMN "clinicianUserId" DROP NOT NULL;
ALTER TABLE "billing_events" DROP CONSTRAINT "billing_events_practiceId_fkey";
ALTER TABLE "billing_events" ADD CONSTRAINT "billing_events_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "billing_events" DROP CONSTRAINT "billing_events_clinicianUserId_fkey";
ALTER TABLE "billing_events" ADD CONSTRAINT "billing_events_clinicianUserId_fkey"
  FOREIGN KEY ("clinicianUserId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- ── rx_warning_overrides — annotation dies with its visit; actor detaches ───
-- The override is a per-visit clinical annotation: once the visit is gone it
-- describes nothing, so it cascades. The ACTOR reference is detached rather
-- than blocking, for the case where the user is removed first.
ALTER TABLE "rx_warning_overrides" ALTER COLUMN "overriddenBy" DROP NOT NULL;
ALTER TABLE "rx_warning_overrides" DROP CONSTRAINT "rx_warning_overrides_visitId_fkey";
ALTER TABLE "rx_warning_overrides" ADD CONSTRAINT "rx_warning_overrides_visitId_fkey"
  FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "rx_warning_overrides" DROP CONSTRAINT "rx_warning_overrides_overriddenBy_fkey";
ALTER TABLE "rx_warning_overrides" ADD CONSTRAINT "rx_warning_overrides_overriddenBy_fkey"
  FOREIGN KEY ("overriddenBy") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- ── template_twin_* — the doctor's own uploaded templates, so they cascade ──
-- These RESTRICTs were introduced by 20260722063000 (applied 2026-07-25) and
-- would have re-broken deletion the moment the native-DOCX flag was switched
-- on, even after the fixes above.
ALTER TABLE "template_twin_source_artifacts" DROP CONSTRAINT "template_twin_source_artifacts_practiceId_fkey";
ALTER TABLE "template_twin_source_artifacts" ADD CONSTRAINT "template_twin_source_artifacts_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_compiled_versions" DROP CONSTRAINT "template_twin_compiled_versions_sourceArtifactId_fkey";
ALTER TABLE "template_twin_compiled_versions" ADD CONSTRAINT "template_twin_compiled_versions_sourceArtifactId_fkey"
  FOREIGN KEY ("sourceArtifactId") REFERENCES "template_twin_source_artifacts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_compiled_versions" DROP CONSTRAINT "template_twin_compiled_versions_noteTemplateId_fkey";
ALTER TABLE "template_twin_compiled_versions" ADD CONSTRAINT "template_twin_compiled_versions_noteTemplateId_fkey"
  FOREIGN KEY ("noteTemplateId") REFERENCES "note_templates"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_certifications" DROP CONSTRAINT "template_twin_certifications_compiledVersionId_fkey";
ALTER TABLE "template_twin_certifications" ADD CONSTRAINT "template_twin_certifications_compiledVersionId_fkey"
  FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- The certifier is an ACTOR on a compliance record: detach, never block.
ALTER TABLE "template_twin_certifications" ALTER COLUMN "certifiedById" DROP NOT NULL;
ALTER TABLE "template_twin_certifications" DROP CONSTRAINT "template_twin_certifications_certifiedById_fkey";
ALTER TABLE "template_twin_certifications" ADD CONSTRAINT "template_twin_certifications_certifiedById_fkey"
  FOREIGN KEY ("certifiedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE "template_twin_fill_manifests" DROP CONSTRAINT "template_twin_fill_manifests_practiceId_fkey";
ALTER TABLE "template_twin_fill_manifests" ADD CONSTRAINT "template_twin_fill_manifests_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_fill_manifests" DROP CONSTRAINT "template_twin_fill_manifests_compiledVersionId_fkey";
ALTER TABLE "template_twin_fill_manifests" ADD CONSTRAINT "template_twin_fill_manifests_compiledVersionId_fkey"
  FOREIGN KEY ("compiledVersionId") REFERENCES "template_twin_compiled_versions"("id") ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_review_decisions" DROP CONSTRAINT "template_twin_review_decisions_fieldDefinitionId_fkey";
ALTER TABLE "template_twin_review_decisions" ADD CONSTRAINT "template_twin_review_decisions_fieldDefinitionId_fkey"
  FOREIGN KEY ("fieldDefinitionId") REFERENCES "template_twin_field_definitions"("id") ON DELETE CASCADE ON UPDATE CASCADE;
