-- Note-format customization — Phase 2b: enforce ONE active template per
-- (doctorId, encounterType) for a doctor's own templates.
-- ----------------------------------------------------------------------------
-- ADDITIVE ONLY — adds a partial-unique index; no column / data changes.
--
-- Activation supersedes the prior active template in an application-level
-- transaction (activateTemplateAction). This index is the DATABASE BACKSTOP so
-- that "two active for the same (doctor, encounterType)" can NEVER occur, even
-- under a concurrent-activation race the transaction alone wouldn't serialize.
--
-- NULLS NOT DISTINCT (PostgreSQL 15+; prod runs pg16) treats the catch-all
-- template (encounterType IS NULL = "all my visits") as a single slot per
-- doctor — without it, two NULL-encounterType active rows would both be
-- allowed because NULLs are distinct in a normal unique index.
--
-- Predicate excludes:
--   * the system default + any system-level row (doctorId IS NULL), which the
--     separate note_templates_one_system_default index already governs;
--   * draft / inactive (superseded) rows — only one ACTIVE row is constrained,
--     so a doctor may keep many drafts + a history of superseded versions.
--
-- Prisma's schema DSL can't express partial / NULLS-NOT-DISTINCT uniqueness
-- (same reason the system-default index is hand-written), so this lives in raw
-- SQL and is documented as a comment on the NoteTemplate model.
CREATE UNIQUE INDEX IF NOT EXISTS "note_templates_one_active_per_doctor_encounter"
    ON "note_templates" ("doctorId", "encounterType")
    NULLS NOT DISTINCT
    WHERE "status" = 'active' AND "doctorId" IS NOT NULL;
