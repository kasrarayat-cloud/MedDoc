// ============================================================================
// Seed Script — Create the first admin/doctor user
// ============================================================================
// Run with: npx tsx scripts/seed-admin.ts
//
// This creates Dr. Moussazadeh's account so you can log in with real auth.
// ============================================================================

import bcrypt from 'bcryptjs';
import { assertNonProdDatabase } from '@meddoc/db/guard';

async function main() {
  // FAIL-CLOSED: never seed prod (see packages/db/src/db-guard.ts).
  assertNonProdDatabase();

  // Dynamic import to avoid top-level Prisma init issues
  const { PrismaClient } = require('@prisma/client');
  const { PrismaPg } = require('@prisma/adapter-pg');

  const adapter = new PrismaPg({
    connectionString: process.env.DATABASE_URL,
  });
  const prisma = new PrismaClient({ adapter });

  const email = 'doctor@meddoc.pro';
  const password = 'MedDoc2026!';
  const passwordHash = await bcrypt.hash(password, 12);

  const user = await prisma.user.upsert({
    where: { email },
    update: {},
    create: {
      email,
      name: 'Dr. Bakhtiar Moussazadeh',
      passwordHash,
      role: 'DOCTOR',
      isActive: true,
    },
  });

  console.log(`\n  User seeded successfully!`);
  console.log(`  Email:    ${email}`);
  // T-M16.4 L6: don't print the plaintext password when NODE_ENV is
  // production — prevents a pasted ops log from leaking a live
  // credential. Dev-box runs still need it to complete the flow.
  if (process.env.NODE_ENV !== 'production') {
    console.log(`  Password: ${password}`);
  } else {
    console.log(`  Password: [hidden in production — check the value you just passed in]`);
  }
  console.log(`  Role:     ${user.role}`);
  console.log(`  ID:       ${user.id}\n`);

  await prisma.$disconnect();
}

main().catch((err) => {
  console.error('Seed failed:', err);
  process.exit(1);
});
