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

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

import bcrypt from 'bcryptjs';

import { assertNonProdDatabase } from '@meddoc/db/guard';

export const QA_EMAIL_DEFAULT = 'qa-auditor@quillmd.test';
export const PRACTICE_ID = 'clinic_main';
export const PATIENT_NAME = 'QA Test Patient';
export const PATIENT_DOB = new Date('2000-01-01T00:00:00.000Z');

/** Pure builder for the user.upsert() payload — extracted so unit
 *  tests can verify the F-07 / F-08 fixes without spinning up a real
 *  Prisma client. The seed-qa-user.test.ts guard imports this directly.
 *
 *  Both branches set `emailVerified` + `products` so an idempotent
 *  re-seed restores them on a partially-broken row (e.g. emailVerified
 *  cleared by some other migration / fixture reset).
 */
export function buildUserUpsertPayload(args: {
  email: string;
  passwordHash: string;
}) {
  return {
    where: { email: args.email },
    update: {
      passwordHash: args.passwordHash,
      role: 'DOCTOR' as const,
      isActive: true,
      lockedUntil: null,
      failedLoginCount: 0,
      emailVerified: new Date(),
      products: ['TRANSCRIBE_MD'] as const,
      practiceId: PRACTICE_ID,
      specialty: 'family-medicine',
      timeZone: 'America/Los_Angeles',
    },
    create: {
      email: args.email,
      name: 'QA Interaction Auditor',
      passwordHash: args.passwordHash,
      role: 'DOCTOR' as const,
      isActive: true,
      emailVerified: new Date(),
      products: ['TRANSCRIBE_MD'] as const,
      practiceId: PRACTICE_ID,
      specialty: 'family-medicine',
      timeZone: 'America/Los_Angeles',
    },
  };
}

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
  // dotenv/config is dynamically required so the unit test (which sets
  // env vars directly) doesn't trip on a missing .env file.
  await import('dotenv/config').catch(() => null);

  // FAIL-CLOSED: never seed prod (see packages/db/src/db-guard.ts).
  assertNonProdDatabase();

  const QA_EMAIL = process.env.QA_AUDITOR_EMAIL ?? QA_EMAIL_DEFAULT;
  const QA_PASSWORD = process.env.QA_AUDITOR_PASSWORD;

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

    // F-07 + F-08 (caught by the agent's own first PASS B browser walk
    // on 2026-05-06 — see docs/qa-reports/20260506T005713Z.md):
    //   - emailVerified must be set, or the login flow rejects with
    //     "Please verify your email before signing in."
    //   - products must include TRANSCRIBE_MD, or the cross-app gate
    //     (apps/transcribe-md/src/actions/auth.ts:213) bounces login
    //     to the MedDoc Pro app with "This account is for MedDoc Pro,
    //     not TranscribeMD."
    // The payload (with both branches setting these) is built by the
    // exported buildUserUpsertPayload so the unit test can assert the
    // shape without reaching for Prisma.
    const user = await prisma.user.upsert(
      buildUserUpsertPayload({ email: QA_EMAIL, passwordHash })
    );

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

// CLI entry — only runs main() when this file is the entrypoint, so a
// dynamic import from the unit test doesn't kick off a real DB run.
const isCli =
  typeof require !== 'undefined' && require.main === module;
if (isCli) {
  main().catch((err) => {
    console.error('Seed failed:', err);
    process.exit(1);
  });
}
