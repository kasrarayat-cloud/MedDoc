// ============================================================================
// Seed Script — E2E test admin
// ----------------------------------------------------------------------------
// Creates (or resets the password of) `admin@test.dev` as a SUPER_ADMIN on
// the default `clinic_main` practice, so Playwright tests can log in and
// land on `/system-admin`.
//
// Idempotent: safe to run repeatedly. Upserts the user; upserts the practice
// so it works on a fresh DB that hasn't run the baseline migration yet.
//
// Run with: npx tsx scripts/seed-e2e-admin.ts
// ============================================================================

import 'dotenv/config';
import bcrypt from 'bcryptjs';
import { assertNonProdDatabase } from '@meddoc/db/guard';

async function main() {
  // FAIL-CLOSED: never seed prod (see packages/db/src/db-guard.ts).
  assertNonProdDatabase();

  const { PrismaClient } = require('@prisma/client');
  const { PrismaPg } = require('@prisma/adapter-pg');

  const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
  const prisma = new PrismaClient({ adapter });

  const email = 'admin@test.dev';
  const password = 'admin-password';
  const practiceId = 'clinic_main';

  // Ensure the default practice exists — the baseline migration also does
  // this, but a fresh dev DB that hasn't been migrated yet won't have it.
  await prisma.practice.upsert({
    where: { id: practiceId },
    update: {},
    create: {
      id: practiceId,
      name: 'Main Clinic',
      slug: 'main-clinic',
      isActive: true,
    },
  });

  const passwordHash = await bcrypt.hash(password, 12);

  const user = await prisma.user.upsert({
    where: { email },
    update: {
      // On re-run, reset password + role + active state so the E2E
      // environment is always in a known-good shape.
      passwordHash,
      role: 'SUPER_ADMIN',
      isActive: true,
      lockedUntil: null,
      failedLoginCount: 0,
      practiceId,
      practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
    },
    create: {
      email,
      name: 'E2E Admin',
      passwordHash,
      role: 'SUPER_ADMIN',
      isActive: true,
      practiceId,
      practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
    },
  });

  console.log(`\n  E2E admin seeded.`);
  console.log(`  Email:      ${email}`);
  // T-M16.4 L6: gate the plaintext password on non-production — the
  // e2e admin script shouldn't run in prod anyway, but this is
  // belt-and-braces so a misdirected invocation doesn't dump a
  // credential into the ops log.
  if (process.env.NODE_ENV !== 'production') {
    console.log(`  Password:   ${password}`);
  } else {
    console.log(`  Password:   [hidden in production]`);
  }
  console.log(`  Role:       ${user.role}`);
  console.log(`  Practice:   ${practiceId}`);
  console.log(`  User ID:    ${user.id}\n`);

  await prisma.$disconnect();
}

main().catch((err) => {
  console.error('Seed failed:', err);
  process.exit(1);
});
