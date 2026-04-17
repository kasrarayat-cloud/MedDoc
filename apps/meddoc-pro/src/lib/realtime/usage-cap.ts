// ============================================================================
// Realtime voice-minutes daily cap
// ----------------------------------------------------------------------------
// Per-user, per-calendar-day cap on Realtime API session minutes. Not a
// security boundary — purely a cost circuit-breaker so a stuck browser tab
// can't burn the OpenAI bill overnight.
//
// Tracks in memory: resets on dev-server restart, doesn't coordinate across
// app instances. Move to Redis when scaling beyond a single Node process.
// For a solo-doctor VPS, in-memory is fine.
//
// Tunable via env: VOICE_MINUTES_PER_USER_DAILY_CAP (default 120).
// ============================================================================

const DEFAULT_CAP_MINUTES = 120;

interface DayUsage {
  /** YYYY-MM-DD in UTC; resets when the day rolls. */
  day: string;
  /** Minutes consumed today. */
  minutes: number;
}

const usage = new Map<string, DayUsage>();

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

function getCap(): number {
  const raw = process.env.VOICE_MINUTES_PER_USER_DAILY_CAP;
  if (!raw) return DEFAULT_CAP_MINUTES;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : DEFAULT_CAP_MINUTES;
}

export interface CapCheckResult {
  /** True if the user has remaining quota AND can start a new session. */
  ok: boolean;
  /** Minutes used today. */
  used: number;
  /** Daily cap. */
  cap: number;
  /** Minutes remaining (cap - used, floored at 0). */
  remaining: number;
}

/**
 * Check whether the user has remaining quota. Doesn't increment.
 */
export function checkVoiceCap(userId: string): CapCheckResult {
  const cap = getCap();
  const today = todayUtc();
  const entry = usage.get(userId);
  const used = entry && entry.day === today ? entry.minutes : 0;
  const remaining = Math.max(0, cap - used);
  return { ok: remaining > 0, used, cap, remaining };
}

/**
 * Record N minutes against the user's daily total. Called when a session
 * ends (the browser sends a heartbeat / final usage ping).
 *
 * `minutes` may be fractional; we store the running sum.
 */
export function recordVoiceMinutes(userId: string, minutes: number): void {
  if (!Number.isFinite(minutes) || minutes <= 0) return;
  const today = todayUtc();
  const entry = usage.get(userId);
  if (!entry || entry.day !== today) {
    usage.set(userId, { day: today, minutes });
    return;
  }
  entry.minutes += minutes;
}
