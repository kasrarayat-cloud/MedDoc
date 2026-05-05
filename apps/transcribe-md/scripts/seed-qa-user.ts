// ============================================================================
// Seed Script — QA Interaction Auditor test user + non-PHI patient
// ----------------------------------------------------------------------------
// Creates (or resets the password of) `qa-auditor@quillmd.test` as a
// `DOCTOR` on the default `clinic_main` practice + one non-PHI test
// patient ("QA Test Patient", DOB 2000-01-01) owned by that user. The
// QA Interaction Auditor agent (.claude/agents/qa-interaction-auditor/)
// uses this account to walk the visit-ready workflow without ever
// touching real PHI.
//
// Idempotent: safe to run repeatedly. Upserts the user (resets password
// + isActive on re-run) + upserts the patient by (practiceId, name).
//
// Required env:
//   QA_AUDITOR_PASSWORD   — the password to bcrypt + persist. Bail on
//                           missing/empty value; we never invent a
//                           default. The password lives in the operator's
//                           shell only; not in git.
//
// Optional env:
//   QA_AUDITOR_EMAIL      — defaults to qa-auditor@quillmd.test (see
//                           .claude/agents/qa-interaction-auditor/
//                           fixtures/test-user.md for the rationale).
//
// Run with:  pnpm tsx apps/transcribe-md/scripts/seed-qa-user.ts
//
// Side effect: writes the seeded user-id + patient-id to the file
//   .claude/agents/qa-interaction-auditor/fixtures/seeded-ids.json
// (gitignored) so the agent's PASS B browser walk can reuse them
// without re-querying.
// ============================================================================

import 'dotenv/config';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

import bcrypt from 'bcryptjs';

const QA_EMAIL = process.env.QA_AUDITOR_EMAIL ?? 'qa-auditor@quillmd.test';
const QA_PASSWORD = process.env.QA_AUDITOR_PASSWORD;
const PRACTICE_ID = 'clinic_main';
const PATIENT_NAME = 'QA Test Patient';
const PATIENT_DOB = new Date('2000-01-01T00:00:00.000Z');

// Path is relative to the repo root; the script may run from any cwd
// (CI, local, docker exec) so we resolve from this file's location.
const SEEDED_IDS_PATH = resolve(
  __dirname,
  '..',
  '..',
  '..',
  '.claude',
  'agents',
  'qa-interaction-auditor',
  'fixtures',
  'seeded-ids.json'
);

async function main() {
  if (!QA_PASSWORD || QA_PASSWORD.length === 0) {
    console.error(
      'QA_AUDITOR_PASSWORD env var is missing or empty.\n' +
        'Set a strong password in your shell before running:\n' +
        "  export QA_AUDITOR_PASSWORD='<strong-password>'\n" +
        'See .claude/agents/qa-interaction-auditor/fixtures/test-user.md.'
    );
    process.exit(2);
  }
  if (QA_PASSWORD.length < 12) {
    console.error(
      `QA_AUDITOR_PASSWORD is only ${QA_PASSWORD.length} chars — refusing to seed a weak QA-auditor password.\n` +
        'The account has DOCTOR permissions on a real practice in dev. Use 12+ chars.'
    );
    process.exit(2);
  }

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { PrismaClient } = require('@prisma/client');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { PrismaPg } = require('@prisma/adapter-pg');

  const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
  const prisma = new PrismaClient({ adapter });

  try {
    // Ensure clinic_main exists (no-op on a fully-migrated DB).
    await prisma.practice.upsert({
      where: { id: PRACTICE_ID },
      update: {},
      create: {
        id: PRACTICE_ID,
        name: 'Main Clinic',
        slug: 'main-clinic',
        isActive: true,
      },
    });

    const passwordHash = await bcrypt.hash(QA_PASSWORD, 12);

    const user = await prisma.user.upsert({
      where: { email: QA_EMAIL },
      update: {
        // Re-run resets to known-good shape so a stale lockout doesn't
        // block the agent.
        passwordHash,
        role: 'DOCTOR',
        isActive: true,
        lockedUntil: null,
        failedLoginCount: 0,
        practiceId: PRACTICE_ID,
        specialty: 'family-medicine',
        timeZone: 'America/Los_Angeles',
      },
      create: {
        email: QA_EMAIL,
        name: 'QA Interaction Auditor',
        passwordHash,
        role: 'DOCTOR',
        isActive: true,
        practiceId: PRACTICE_ID,
        specialty: 'family-medicine',
        timeZone: 'America/Los_Angeles',
      },
    });

    // Test patient — TranscribeMdPatient (the patient the doctor
    // attaches a visit to). NO PHI: synthetic name + DOB matching
    // fixtures/sample-recordings/README.md's "Test Test, 01/01/2000"
    // pattern. There's no unique constraint on (practiceId, name) so
    // we look up first to keep the script idempotent without a fragile
    // upsert-by-composite-key.
    const existingPatient = await prisma.transcribeMdPatient.findFirst({
      where: { practiceId: PRACTICE_ID, name: PATIENT_NAME },
      select: { id: true },
    });
    const patient =
      existingPatient ??
      (await prisma.transcribeMdPatient.create({
        data: {
          practiceId: PRACTICE_ID,
          name: PATIENT_NAME,
          dateOfBirth: PATIENT_DOB,
        },
        select: { id: true },
      }));

    // Persist ids for the agent.
    const seeded = {
      seededAt: new Date().toISOString(),
      userId: user.id,
      userEmail: QA_EMAIL,
      patientId: patient.id,
      patientName: PATIENT_NAME,
      practiceId: PRACTICE_ID,
    };
    mkdirSync(dirname(SEEDED_IDS_PATH), { recursive: true });
    writeFileSync(SEEDED_IDS_PATH, JSON.stringify(seeded, null, 2) + '\n');

    console.log(`\n  QA test user seeded.`);
    console.log(`  Email:      ${QA_EMAIL}`);
    if (process.env.NODE_ENV !== 'production') {
      console.log(`  Password:   [bcrypt-hashed; supplied via env]`);
    }
    console.log(`  Role:       ${user.role}`);
    console.log(`  Practice:   ${PRACTICE_ID}`);
    console.log(`  User id:    ${user.id}`);
    console.log(`  Patient id: ${patient.id}`);
    console.log(`  Ids file:   ${SEEDED_IDS_PATH}\n`);
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error('Seed failed:', err);
  process.exit(1);
});
