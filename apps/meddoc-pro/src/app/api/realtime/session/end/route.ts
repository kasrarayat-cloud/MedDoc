import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { logApiUsage } from '@/lib/usage';
import { logAudit } from '@/lib/audit';
import { recordVoiceMinutes } from '@/lib/realtime/usage-cap';

// ============================================================================
// /api/realtime/session/end — record voice session duration when the
// browser closes its WebRTC peer connection
// ----------------------------------------------------------------------------
// Why a dedicated endpoint: the doctor's WebRTC audio goes browser ↔ OpenAI
// DIRECTLY (that's what makes Realtime fast). Our server never sees the
// audio bytes, so we can't meter them passively. The browser knows when
// the session opened and closed; this endpoint lets it tell us the delta
// so the metrics page can price Realtime minutes correctly.
//
// Called from useRealtimeSession.stop() AND via navigator.sendBeacon on
// unmount / page-unload (best-effort — beacon is fire-and-forget and may
// drop on hard close, but that's fine; metrics lose a few seconds, not
// a whole session).
// ============================================================================

const MAX_SESSION_SECONDS = 8 * 60 * 60; // 8 hours — guards against replay

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: { durationSeconds?: number };
  try {
    body = (await request.json()) as { durationSeconds?: number };
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const raw = body.durationSeconds;
  if (typeof raw !== 'number' || !Number.isFinite(raw) || raw <= 0) {
    return NextResponse.json({ error: 'Invalid durationSeconds' }, { status: 400 });
  }
  // Clamp — a client that claims 24h of usage in one beacon is buggy or
  // malicious; cap at 8h so the metrics page doesn't get polluted.
  const durationSeconds = Math.min(Math.round(raw), MAX_SESSION_SECONDS);

  // Roll into the daily cap counter so future /session POSTs can refuse
  // when the doctor has burned their budget.
  recordVoiceMinutes(session.user.id, durationSeconds / 60);

  // Fire-and-forget usage log. Feature name is the one metrics will
  // aggregate against — keep it stable.
  void logApiUsage({
    feature: 'REALTIME_VOICE',
    userId: session.user.id,
    practiceId: session.user.practiceId,
    durationSeconds,
  }).catch((err) => {
    console.error('[realtime/session/end] logApiUsage rejected:', err);
  });

  // Phase 19 — h16-audit-gap-realtime. The clamped duration is what
  // we trust; raw + clamped both go into metadata so an auditor can
  // see whether the client over-claimed.
  void logAudit({
    action: 'REALTIME_SESSION_ENDED',
    targetType: 'realtime_session',
    targetId: null,
    metadata: {
      durationSeconds,
      rawDurationSeconds: Math.round(raw),
      clamped: durationSeconds < Math.round(raw),
    },
  });

  return NextResponse.json({ ok: true, durationSeconds });
}
