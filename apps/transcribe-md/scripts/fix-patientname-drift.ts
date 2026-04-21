// ============================================================================
// T-M18.2 A6 — One-shot fix for visit.patientName drift from patient.name
// ----------------------------------------------------------------------------
// The T-M17.2 Phase 1 backfill picked the "most recent casing" as each
// patient's canonical name but didn't rewrite older visits' legacy
// `patientName` column. Result: a handful of rows render one spelling
// on the dashboard (VisitCard reads visit.patientName) and a different
// spelling on the patient detail page (reads patient.name).
//
// This script aligns them by overwriting visit.patientName with
// patient.name where they differ, and where visit.patientName was set
// to begin with. The legacy column is kept — Commit 6's visit action
// always writes it via the resolved patient's canonical name, so new
// visits are fine; this just backfills the pre-Phase-1 stragglers.
//
// Idempotent: a re-run after fix is a no-op (the WHERE clause matches
// zero rows).
//
// Run:
//   docker compose exec transcribe-md-worker npx tsx scripts/fix-patientname-drift.ts
// Or from the host (with DATABASE_URL pointing at the live DB):
//   npm run patients:fix-drift -w transcribe-md
// ============================================================================

import 'dotenv/config';

import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';

async function main() {
  const adapter = new PrismaPg({
    connectionString: process.env.DATABASE_URL,
  });
  const prisma = new PrismaClient({ adapter });

  try {
    const result = await prisma.$executeRaw`
      UPDATE transcribe_visits v
      SET "patientName" = p.name
      FROM transcribe_md_patients p
      WHERE p.id = v."patientId"
        AND v."patientName" IS NOT NULL
        AND v."patientName" IS DISTINCT FROM p.name
    `;
    console.log(`[fix-patientname-drift] updated ${result} visit row(s).`);
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error('[fix-patientname-drift] failed:', err);
  process.exit(1);
});
