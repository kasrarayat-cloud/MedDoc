-- Note-format customization — PHASE 0 (foundation, zero behavior change).
--
-- ADDITIVE ONLY. Creates the `note_templates` table, adds two NULLABLE
-- provenance columns to `transcribe_visits`, and seeds the single system-
-- default template (today's L4 SOAP format expressed as data). No existing
-- column is altered; the new provenance columns stay NULL until Phase 1
-- wires resolveActiveTemplate() into L4. A non-customizing doctor's note is
-- therefore byte-identical to today's.
--
-- Seed content is kept in lockstep with the single source of truth at
-- apps/transcribe-md/src/worker/note-templates/system-default-template.ts —
-- a sibling drift test deep-equals the JSON below against that constant.

-- CreateTable
CREATE TABLE "note_templates" (
    "id" TEXT NOT NULL,
    "doctorId" TEXT,
    "name" TEXT NOT NULL,
    "encounterType" TEXT,
    "specialtyBaseline" TEXT,
    "sections" JSONB NOT NULL,
    "styleProfile" JSONB,
    "version" INTEGER NOT NULL DEFAULT 1,
    "status" TEXT NOT NULL DEFAULT 'active',
    "isSystemDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "note_templates_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "note_templates_doctorId_status_idx" ON "note_templates"("doctorId", "status");

-- CreateIndex
CREATE INDEX "note_templates_isSystemDefault_idx" ON "note_templates"("isSystemDefault");

-- AlterTable — additive, nullable columns are safe on the populated
-- transcribe_visits table (no rewrite, no default backfill).
ALTER TABLE "transcribe_visits" ADD COLUMN     "noteTemplateId" TEXT,
ADD COLUMN     "noteTemplateVersion" INTEGER;

-- CreateIndex
CREATE INDEX "transcribe_visits_noteTemplateId_idx" ON "transcribe_visits"("noteTemplateId");

-- AddForeignKey
ALTER TABLE "note_templates" ADD CONSTRAINT "note_templates_doctorId_fkey" FOREIGN KEY ("doctorId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "transcribe_visits" ADD CONSTRAINT "transcribe_visits_noteTemplateId_fkey" FOREIGN KEY ("noteTemplateId") REFERENCES "note_templates"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- One-system-default invariant. Prisma's schema DSL can't express a PARTIAL
-- unique index, so it is hand-managed here (same posture as the partial-index
-- notes on transcribe_visits). Production deploys via `prisma migrate deploy`
-- (no schema-drift check), so this living outside schema.prisma is fine.
CREATE UNIQUE INDEX IF NOT EXISTS "note_templates_one_system_default"
    ON "note_templates"("isSystemDefault")
    WHERE "isSystemDefault" = true;

-- Seed the singleton system-default template (idempotent: no-op if one
-- already exists). Each JSONB literal is on its own line so the drift test
-- can extract + deep-equal it against the TS source of truth.
INSERT INTO "note_templates"
    ("id", "doctorId", "name", "encounterType", "specialtyBaseline",
     "sections", "styleProfile", "version", "status", "isSystemDefault",
     "createdAt", "updatedAt")
SELECT
    'tmpl_system_default_soap', NULL, 'System Default — SOAP', NULL, NULL,
    /* @seed:sections */ '[{"key":"subjective","label":"Subjective","order":1,"formatHint":"prose","styleInstructions":"**Chief Complaint:** …\n**HPI:** narrative paragraph incorporating onset, duration, quality,\n  severity, location, timing, context, modifying factors, associated\n  symptoms.\n**PMH:** bullet list or \"[not documented]\" if silent.\n**Medications:** bullet list with dose/route/frequency where stated.\n**Allergies:** bullet list with reactions where stated.\n**Family History:** brief list or \"[not documented]\".\n**Social History:** smoking / alcohol / drugs / occupation if mentioned;\n  omit unmentioned lines.\n**ROS:** by system when documented; else the single line\n  \"ROS not formally documented in this encounter.\"","defaultText":null,"defaultTextMode":"omit_unless_supported"},{"key":"objective","label":"Objective","order":2,"formatHint":"prose","styleInstructions":"Physical exam findings grouped by system. Include vitals if mentioned.\nInclude test results mentioned. If no formal exam was discussed, write\nexactly: \"Formal exam not documented in this encounter.\"","defaultText":null,"defaultTextMode":"omit_unless_supported"},{"key":"assessment","label":"Assessment","order":3,"formatHint":"prose","styleInstructions":"Primary clinical consideration with supporting reasoning. Differentials\nif the doctor discussed them. Severity/staging if applicable. Use [not\ndocumented] rather than inventing.","defaultText":null,"defaultTextMode":"omit_unless_supported"},{"key":"plan","label":"Plan","order":4,"formatHint":"numbered","styleInstructions":"Numbered list: diagnostics ordered, medications changed/started, follow-\nup, referrals, patient education. Each item should be actionable.","defaultText":null,"defaultTextMode":"omit_unless_supported"}]'::jsonb,
    /* @seed:styleProfile */ '{"tense":null,"tone":"professional medical","abbreviations":null,"preamble":"You are a senior clinician writing a SOAP note from a clinical visit. Use ONLY the entities provided and the transcript as evidence. Write in a professional medical tone.","globalRules":["Do NOT invent clinical findings. If a claim lacks transcript evidence, either omit it or explicitly mark it \"[not documented]\".","When information came exclusively from the patient, prefix with \"Per patient, …\" so the source is clear on downstream review.","Never add test results, medication doses, or vital-sign numbers that were not stated.","Don''t add diagnostic qualifiers (acute, chronic, undiagnosed, severe, mild, sudden, gradual) unless the transcript uses them explicitly. \"Migraines\" stays \"migraines\" — not \"undiagnosed migraines.\" Onset is \"sudden\" only if the patient said sudden.","Don''t infer maternal/paternal side or a specific relative when the transcript only mentions a relative type. \"My grandmother\" stays \"grandmother\" — not \"maternal grandmother\" unless stated.","When a dose, frequency, or strength is ambiguous in the transcript, write what was actually said and append ''[clarify with patient]'' rather than picking the most likely value. Don''t silently resolve \"two tablets... one tablet twice a day\" to a single interpretation.","Output ONLY the SOAP note markdown. No preamble, no postscript."]}'::jsonb,
    1, 'active', true,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1 FROM "note_templates" WHERE "isSystemDefault" = true
);
