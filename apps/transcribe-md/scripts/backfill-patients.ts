// ============================================================================
// T-M17.2 Phase 1 — Backfill TranscribeMdPatient rows from legacy
// TranscribeVisit.patientName values.
// ----------------------------------------------------------------------------
// Run inside the container:
//   docker compose exec transcribe-md-worker npx tsx scripts/backfill-patients.ts
// Or from the host:
//   npm run patients:backfill -w transcribe-md
//
// Algorithm:
//   For each practice:
//     1. Group existing visits by LOWER(TRIM(patientName)). Each group
//        → one TranscribeMdPatient; the canonical `name` is the most-
//        recent casing the doctor used.
//     2. Visits where patientName is NULL or whitespace-only are bucketed
//        into a single "Unknown patient" row per practice. The doctor
//        can reassign these from the Phase 3 UI later.
//     3. Write each TranscribeVisit.patientId in a single atomic
//        transaction per practice — partial state after a crash is
//        painful to reason about.
//
// Idempotent: running twice is a no-op once visits have patientId set.
// Reports a summary at the end; exit code non-zero on any error.
// ============================================================================

import 'dotenv/config';

import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';

const PLACEHOLDER_NAME = 'Unknown patient';

function normalizeName(raw: string | null): string | null {
  if (raw == null) return null;
  const trimmed = raw.trim();
  return trimmed === '' ? null : trimmed;
}

function bucketKey(normalized: string | null): string {
  return normalized == null ? '__null__' : normalized.toLowerCase();
}

interface PracticeStats {
  practiceId: string;
  patientsCreated: number;
  visitsUpdated: number;
  unknownBucketVisits: number;
  alreadyLinked: number;
}

async function backfillPractice(
  prisma: PrismaClient,
  practiceId: string
): Promise<PracticeStats> {
  const stats: PracticeStats = {
    practiceId,
    patientsCreated: 0,
    visitsUpdated: 0,
    unknownBucketVisits: 0,
    alreadyLinked: 0,
  };

  // Pull every visit for users in this practice. Cheap for our volume.
  const visits = await prisma.transcribeVisit.findMany({
    where: { user: { practiceId } },
    select: {
      id: true,
      patientName: true,
      patientId: true,
      createdAt: true,
    },
    orderBy: { createdAt: 'desc' },
  });

  if (visits.length === 0) return stats;

  // Group by lowercased normalized name. Record the most-recent casing
  // per bucket (visits are ORDER BY createdAt DESC, so the first visit
  // we see in a bucket is the most recent). The null bucket collapses
  // every unnamed visit under a single placeholder patient.
  const buckets = new Map<
    string,
    { canonicalName: string; visitIds: string[] }
  >();

  for (const v of visits) {
    if (v.patientId !== null) {
      stats.alreadyLinked += 1;
      continue;
    }
    const normalized = normalizeName(v.patientName);
    const key = bucketKey(normalized);
    const existing = buckets.get(key);
    if (existing) {
      existing.visitIds.push(v.id);
    } else {
      buckets.set(key, {
        canonicalName: normalized ?? PLACEHOLDER_NAME,
        visitIds: [v.id],
      });
    }
  }

  if (buckets.size === 0) return stats;

  // One transaction per practice: all patients + visit updates commit
  // together. If this fails partway, nothing is persisted — rerun.
  await prisma.$transaction(async (tx) => {
    for (const [key, { canonicalName, visitIds }] of buckets) {
      const patient = await tx.transcribeMdPatient.create({
        data: {
          practiceId,
          name: canonicalName,
          // dateOfBirth left NULL — legacy visits never captured it.
        },
        select: { id: true },
      });
      stats.patientsCreated += 1;
      if (key === '__null__') {
        stats.unknownBucketVisits += visitIds.length;
      }
      // Single bulk update scoped to these visit ids.
      const updated = await tx.transcribeVisit.updateMany({
        where: { id: { in: visitIds } },
        data: { patientId: patient.id },
      });
      stats.visitsUpdated += updated.count;
    }
  });

  return stats;
}

async function main() {
  const adapter = new PrismaPg({
    connectionString: process.env.DATABASE_URL,
  });
  const prisma = new PrismaClient({ adapter });

  try {
    const practices = await prisma.practice.findMany({
      select: { id: true, name: true },
    });

    console.log(
      `\n[backfill-patients] T-M17.2 Phase 1 — ${practices.length} practices to scan\n`
    );

    const allStats: PracticeStats[] = [];
    for (const p of practices) {
      const stats = await backfillPractice(prisma, p.id);
      allStats.push(stats);
      if (
        stats.patientsCreated === 0 &&
        stats.alreadyLinked === 0
      ) {
        console.log(`  · ${p.name} (${p.id}): no visits, skipped`);
        continue;
      }
      console.log(
        `  · ${p.name} (${p.id}): created ${stats.patientsCreated} patient(s), ` +
          `linked ${stats.visitsUpdated} visit(s)` +
          (stats.unknownBucketVisits > 0
            ? ` (${stats.unknownBucketVisits} under "Unknown patient")`
            : '') +
          (stats.alreadyLinked > 0
            ? ` (skipped ${stats.alreadyLinked} already-linked)`
            : '')
      );
    }

    const totalPatients = allStats.reduce((a, s) => a + s.patientsCreated, 0);
    const totalVisits = allStats.reduce((a, s) => a + s.visitsUpdated, 0);
    const unlinked = await prisma.transcribeVisit.count({
      where: { patientId: null },
    });

    console.log(
      `\n[backfill-patients] done — ${totalPatients} patient(s), ${totalVisits} visit(s) linked.`
    );
    console.log(
      `[backfill-patients] visits still unlinked after backfill: ${unlinked}`
    );
    if (unlinked > 0) {
      console.error(
        '[backfill-patients] WARNING: unlinked visits remain — Phase 1 Commit 3 (NOT NULL) will fail until this is zero.'
      );
      process.exitCode = 2;
    }
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error('[backfill-patients] failed:', err);
  process.exit(1);
});
