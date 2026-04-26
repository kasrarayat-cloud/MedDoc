// ============================================================================
// POST /api/admin/threats/[id]/investigate — Phase 6H drawer payload
// ----------------------------------------------------------------------------
// Enriches a single threat with the underlying audit rows so the
// InvestigateDrawer can render a proper timeline + actor profile +
// IP context. Writes a THREAT_INVESTIGATED audit row so we can later
// answer "who looked at this and when".
//
// The threat id is opaque here; we decode it the same way the
// detector built it ("burst:<ip>:<iso>", "cross:<userId>:<iso>", ...)
// and pull the related rows. Anything we can't decode comes back as
// an empty timeline — the UI still renders the resolved metadata.
// ============================================================================

import { NextResponse } from 'next/server';

import prisma from '@meddoc/db';

import { adminApi } from '@/lib/admin-api-gate';
import { logAudit } from '@/lib/audit';

export const dynamic = 'force-dynamic';

interface AuditTimelineRow {
  id: string;
  timestamp: string;
  action: string;
  userEmailSnapshot: string | null;
  ipAddress: string | null;
  targetType: string | null;
  targetId: string | null;
  success: boolean | null;
  errorCode: string | null;
}

interface UserProfile {
  id: string;
  email: string | null;
  fullName: string | null;
  practiceId: string | null;
  isActive: boolean;
  lastLoginAt: string | null;
}

interface IpContext {
  ipAddress: string;
  totalEventsLast7d: number;
  failedLoginsLast7d: number;
  distinctUsersLast7d: number;
  firstSeen: string | null;
  lastSeen: string | null;
}

interface InvestigateResponse {
  threatId: string;
  kind: string;
  timeline: AuditTimelineRow[];
  user: UserProfile | null;
  ip: IpContext | null;
}

export const POST = adminApi('threats:investigate', async (req, ctx) => {
  const segs = new URL(req.url).pathname.split('/').filter(Boolean);
  // Path: /api/admin/threats/<id>/investigate
  const idIdx = segs.indexOf('threats') + 1;
  const rawId = segs[idIdx];
  if (!rawId) return NextResponse.json({ error: 'Bad path' }, { status: 400 });
  const threatId = decodeURIComponent(rawId);

  const parts = threatId.split(':');
  const kind = parts[0] ?? 'unknown';

  let timeline: AuditTimelineRow[] = [];
  let user: UserProfile | null = null;
  let ip: IpContext | null = null;

  try {
    switch (kind) {
      case 'burst': {
        // burst:<ip>:<isoTimestamp>
        const ipAddr = parts[1];
        if (ipAddr) {
          [timeline, ip] = await Promise.all([
            loadAuditByIp(ipAddr, 50),
            loadIpContext(ipAddr),
          ]);
        }
        break;
      }
      case 'cross':
      case 'bulk': {
        // <kind>:<userId>:<isoTimestamp>
        const userId = parts[1];
        if (userId) {
          [timeline, user] = await Promise.all([
            loadAuditByUser(userId, 50),
            loadUserProfile(userId),
          ]);
        }
        break;
      }
      case 'xdom': {
        // xdom:<userId>:<domain>
        const userId = parts[1];
        if (userId) {
          [timeline, user] = await Promise.all([
            loadAuditByUser(userId, 50),
            loadUserProfile(userId),
          ]);
        }
        break;
      }
      case 'grant-admin': {
        // grant-admin:<auditLogId>
        const logId = parts[1];
        if (logId) {
          timeline = await loadAuditAround(logId, 25);
          // First row's actor is the granter; metadata.targetEmail
          // points at the grantee. We surface the grantee's profile
          // since "did this user keep their access" is what an admin
          // would want to see next.
          const root = timeline.find((r) => r.id === logId);
          if (root?.targetId) {
            user = await loadUserProfile(root.targetId);
          }
        }
        break;
      }
      default:
        // Unknown kind — leave timeline/user/ip null. The audit row
        // below still records the click, so we know admins are
        // poking at malformed ids if it shows up in logs.
        break;
    }
  } catch (err) {
    console.error('[threats:investigate] enrichment failed:', err);
  }

  await logAudit({
    action: 'THREAT_INVESTIGATED',
    targetType: 'Threat',
    targetId: threatId,
    metadata: {
      kind,
      actorEmail: ctx.session.user.email,
      timelineRows: timeline.length,
      userProfileFound: !!user,
    },
  });

  const body: InvestigateResponse = { threatId, kind, timeline, user, ip };
  return NextResponse.json(body);
});

async function loadAuditByIp(
  ipAddress: string,
  limit: number
): Promise<AuditTimelineRow[]> {
  const rows = await prisma.$queryRaw<
    Array<{
      id: string;
      timestamp: Date;
      action: string;
      userEmailSnapshot: string | null;
      ipAddress: string | null;
      targetType: string | null;
      targetId: string | null;
      success: boolean | null;
      errorCode: string | null;
    }>
  >`
    SELECT
      id, timestamp, action, "userEmailSnapshot", "ipAddress",
      "targetType", "targetId", success, "errorCode"
    FROM audit_logs
    WHERE "ipAddress" = ${ipAddress}
    ORDER BY timestamp DESC
    LIMIT ${limit}
  `;
  return rows.map(serializeRow);
}

async function loadAuditByUser(
  userId: string,
  limit: number
): Promise<AuditTimelineRow[]> {
  const rows = await prisma.$queryRaw<
    Array<{
      id: string;
      timestamp: Date;
      action: string;
      userEmailSnapshot: string | null;
      ipAddress: string | null;
      targetType: string | null;
      targetId: string | null;
      success: boolean | null;
      errorCode: string | null;
    }>
  >`
    SELECT
      id, timestamp, action, "userEmailSnapshot", "ipAddress",
      "targetType", "targetId", success, "errorCode"
    FROM audit_logs
    WHERE "userId" = ${userId}
    ORDER BY timestamp DESC
    LIMIT ${limit}
  `;
  return rows.map(serializeRow);
}

async function loadAuditAround(
  rootId: string,
  bracket: number
): Promise<AuditTimelineRow[]> {
  // Pull the root row plus a few neighbours by timestamp so we can
  // show "what happened just before/after this admin grant".
  const root = await prisma.auditLog.findUnique({
    where: { id: rootId },
    select: { id: true, timestamp: true },
  });
  if (!root) return [];

  const before = new Date(root.timestamp.getTime() - 24 * 60 * 60 * 1000);
  const after = new Date(root.timestamp.getTime() + 24 * 60 * 60 * 1000);
  const rows = await prisma.$queryRaw<
    Array<{
      id: string;
      timestamp: Date;
      action: string;
      userEmailSnapshot: string | null;
      ipAddress: string | null;
      targetType: string | null;
      targetId: string | null;
      success: boolean | null;
      errorCode: string | null;
    }>
  >`
    SELECT
      id, timestamp, action, "userEmailSnapshot", "ipAddress",
      "targetType", "targetId", success, "errorCode"
    FROM audit_logs
    WHERE timestamp >= ${before}
      AND timestamp <= ${after}
    ORDER BY timestamp DESC
    LIMIT ${bracket}
  `;
  return rows.map(serializeRow);
}

async function loadUserProfile(userId: string): Promise<UserProfile | null> {
  // Phase 6Z fix: the prior version selected `fullName` and `lastLoginAt`
  // — neither exists on the User model (display name is `name` and the
  // last-login timestamp is `lastLogin` per packages/db/prisma/
  // schema.prisma). Prisma threw, the outer try/catch in the handler
  // swallowed the error, and the InvestigateDrawer silently rendered
  // without the actor profile for every user-related threat (cross,
  // bulk, xdom, grant-admin). The interface fields stay named
  // `fullName`/`lastLoginAt` because the UI consumer expects those
  // names; we just map from the actual schema columns.
  const u = await prisma.user.findUnique({
    where: { id: userId },
    select: {
      id: true,
      email: true,
      name: true,
      practiceId: true,
      isActive: true,
      lastLogin: true,
    },
  });
  if (!u) return null;
  return {
    id: u.id,
    email: u.email,
    fullName: u.name,
    practiceId: u.practiceId,
    isActive: u.isActive,
    lastLoginAt: u.lastLogin ? u.lastLogin.toISOString() : null,
  };
}

async function loadIpContext(ipAddress: string): Promise<IpContext> {
  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const rows = await prisma.$queryRaw<
    Array<{
      total: bigint;
      failed: bigint;
      distinct_users: bigint;
      first_seen: Date | null;
      last_seen: Date | null;
    }>
  >`
    SELECT
      COUNT(*)::bigint AS total,
      COUNT(*) FILTER (WHERE action = 'LOGIN_FAILED')::bigint AS failed,
      COUNT(DISTINCT "userId")::bigint AS distinct_users,
      MIN(timestamp) AS first_seen,
      MAX(timestamp) AS last_seen
    FROM audit_logs
    WHERE "ipAddress" = ${ipAddress}
      AND timestamp >= ${since}
  `;
  const r = rows[0];
  return {
    ipAddress,
    totalEventsLast7d: r ? Number(r.total) : 0,
    failedLoginsLast7d: r ? Number(r.failed) : 0,
    distinctUsersLast7d: r ? Number(r.distinct_users) : 0,
    firstSeen: r?.first_seen ? r.first_seen.toISOString() : null,
    lastSeen: r?.last_seen ? r.last_seen.toISOString() : null,
  };
}

function serializeRow(r: {
  id: string;
  timestamp: Date;
  action: string;
  userEmailSnapshot: string | null;
  ipAddress: string | null;
  targetType: string | null;
  targetId: string | null;
  success: boolean | null;
  errorCode: string | null;
}): AuditTimelineRow {
  return {
    id: r.id,
    timestamp: r.timestamp.toISOString(),
    action: r.action,
    userEmailSnapshot: r.userEmailSnapshot,
    ipAddress: r.ipAddress,
    targetType: r.targetType,
    targetId: r.targetId,
    success: r.success,
    errorCode: r.errorCode,
  };
}
