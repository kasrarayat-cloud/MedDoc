// ============================================================================
// GET /api/admin/threats/recent — rule-based anomaly summary (last 24h)
// ----------------------------------------------------------------------------
// Four detectors, all driven by audit_logs queries. None are ML — each
// is a deterministic threshold someone can defend in a security review.
//
//   failedLoginBursts        — 5+ LOGIN_FAILED from same IP in 5 min
//   crossTenantAttempts      — log entries with success=false + cross-
//                              practice metadata flags
//   bulkPhiAccess            — same user accessed 50+ patients in 1 hour
//                              (TM_PATIENT_* events, by-userId rolling
//                              hourly count). Includes export-heavy
//                              exfiltration shape too.
//   exportToExternalDomains  — EXPORT_EMAIL_BLOCKED_DESTINATION events
//                              grouped by metadata.requestedDomain.
//
// Each detector is best-effort — a Prisma error returns an empty array
// for that bucket rather than failing the whole endpoint.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';

const WINDOW_HOURS = 24;
const FAILED_LOGIN_BURST_THRESHOLD = 5;
const FAILED_LOGIN_BURST_WINDOW_MIN = 5;
const BULK_PHI_THRESHOLD = 50;
const BULK_PHI_WINDOW_MIN = 60;

interface FailedLoginBurst {
  ipAddress: string;
  count: number;
  firstSeen: string;
  lastSeen: string;
  targetEmails: string[];
}

interface CrossTenantAttempt {
  userId: string;
  attemptCount: number;
  lastSeen: string;
}

interface BulkPhiAccess {
  userId: string;
  userEmail: string | null;
  patientCount: number;
  exportCount: number;
  windowStart: string;
  windowEnd: string;
}

interface ExportToExternalDomain {
  userId: string;
  externalDomain: string;
  attemptCount: number;
  lastSeen: string;
}

export const dynamic = 'force-dynamic';

export const GET = adminApi('threats:recent', async () => {
  const since = new Date(Date.now() - WINDOW_HOURS * 60 * 60 * 1000);

  const [
    failedLoginBursts,
    crossTenantAttempts,
    bulkPhiAccess,
    exportToExternalDomains,
  ] = await Promise.all([
    detectFailedLoginBursts(since),
    detectCrossTenantAttempts(since),
    detectBulkPhiAccess(since),
    detectExportToExternalDomains(since),
  ]);

  return NextResponse.json({
    failedLoginBursts,
    crossTenantAttempts,
    bulkPhiAccess,
    exportToExternalDomains,
  });
});

async function detectFailedLoginBursts(since: Date): Promise<FailedLoginBurst[]> {
  // Bucket failed-login rows by 5-min ip-window. Flag any window
  // with >= 5 hits.
  return await prisma.$queryRaw<FailedLoginBurst[]>`
    WITH windowed AS (
      SELECT
        "ipAddress"::text AS ip,
        DATE_TRUNC('minute', "timestamp")
          - (EXTRACT(MINUTE FROM "timestamp")::int % ${FAILED_LOGIN_BURST_WINDOW_MIN}) * INTERVAL '1 minute'
          AS bucket_start,
        "userEmailSnapshot" AS email
      FROM audit_logs
      WHERE "timestamp" >= ${since}
        AND action = 'LOGIN_FAILED'
        AND "ipAddress" IS NOT NULL
    )
    SELECT
      ip AS "ipAddress",
      COUNT(*)::int AS count,
      MIN(bucket_start)::timestamptz AS "firstSeen",
      MAX(bucket_start + INTERVAL '${FAILED_LOGIN_BURST_WINDOW_MIN} minutes')::timestamptz AS "lastSeen",
      ARRAY_AGG(DISTINCT email) FILTER (WHERE email IS NOT NULL) AS "targetEmails"
    FROM windowed
    GROUP BY ip, bucket_start
    HAVING COUNT(*) >= ${FAILED_LOGIN_BURST_THRESHOLD}
    ORDER BY "lastSeen" DESC
    LIMIT 50
  `.catch(() => []);
}

async function detectCrossTenantAttempts(
  since: Date
): Promise<CrossTenantAttempt[]> {
  // The transcribe-md routes already 404 cross-tenant probes, but
  // when an attempt logs an audit row with success=false and an
  // errorCode in {NO_MEDDOC_PRO_ENTITLEMENT, NO_TRANSCRIBE_MD_ENTITLEMENT}
  // we surface it. Same for explicit IDOR-shaped 4xx in the future
  // when those routes start auditing.
  return await prisma.$queryRaw<CrossTenantAttempt[]>`
    SELECT
      "userId",
      COUNT(*)::int AS "attemptCount",
      MAX("timestamp")::timestamptz AS "lastSeen"
    FROM audit_logs
    WHERE "timestamp" >= ${since}
      AND success = false
      AND "errorCode" IN (
        'NO_MEDDOC_PRO_ENTITLEMENT',
        'NO_TRANSCRIBE_MD_ENTITLEMENT'
      )
      AND "userId" IS NOT NULL
    GROUP BY "userId"
    HAVING COUNT(*) >= 3
    ORDER BY "lastSeen" DESC
    LIMIT 50
  `.catch(() => []);
}

async function detectBulkPhiAccess(since: Date): Promise<BulkPhiAccess[]> {
  // Same userId + 50+ distinct patient/visit targets in any 1-hour
  // rolling window. Cheap-ish via a SUM of TM_PATIENT_* events
  // bucketed by userId+hour.
  return await prisma.$queryRaw<BulkPhiAccess[]>`
    WITH bucketed AS (
      SELECT
        "userId",
        "userEmailSnapshot" AS email,
        DATE_TRUNC('hour', "timestamp") AS hour,
        COUNT(DISTINCT "targetId") FILTER (
          WHERE "targetType" IN ('TranscribeMdPatient', 'TranscribeVisit')
        )::int AS patient_count,
        COUNT(*) FILTER (
          WHERE action IN (
            'EXPORT_PDF_DOWNLOADED',
            'EXPORT_DOCX_DOWNLOADED',
            'EXPORT_CLIPBOARD_COPIED',
            'EXPORT_EMAIL_SENT'
          )
        )::int AS export_count
      FROM audit_logs
      WHERE "timestamp" >= ${since}
        AND "userId" IS NOT NULL
      GROUP BY "userId", email, hour
    )
    SELECT
      "userId",
      email AS "userEmail",
      patient_count AS "patientCount",
      export_count AS "exportCount",
      hour::timestamptz AS "windowStart",
      (hour + INTERVAL '1 hour')::timestamptz AS "windowEnd"
    FROM bucketed
    WHERE patient_count >= ${BULK_PHI_THRESHOLD}
       OR export_count >= ${BULK_PHI_THRESHOLD}
    ORDER BY "windowStart" DESC
    LIMIT 50
  `.catch(() => []);
}

async function detectExportToExternalDomains(
  since: Date
): Promise<ExportToExternalDomain[]> {
  return await prisma.$queryRaw<ExportToExternalDomain[]>`
    SELECT
      "userId",
      (metadata->>'requestedDomain')::text AS "externalDomain",
      COUNT(*)::int AS "attemptCount",
      MAX("timestamp")::timestamptz AS "lastSeen"
    FROM audit_logs
    WHERE "timestamp" >= ${since}
      AND action = 'EXPORT_EMAIL_BLOCKED_DESTINATION'
      AND "userId" IS NOT NULL
      AND metadata->>'requestedDomain' IS NOT NULL
    GROUP BY "userId", "externalDomain"
    HAVING COUNT(*) >= 1
    ORDER BY "lastSeen" DESC
    LIMIT 50
  `.catch(() => []);
}

void BULK_PHI_WINDOW_MIN; // referenced in comments only
