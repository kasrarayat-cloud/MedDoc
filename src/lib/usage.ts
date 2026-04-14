// ============================================================================
// API Usage Logger
// ----------------------------------------------------------------------------
// Counts authenticated API hits for the admin Metrics page. Distinct from
// `audit.ts` (HIPAA PHI trail) and `ApiUsageLog` (AI model cost tracking):
// this is a thin "who called which endpoint, and when" counter.
//
// Must be fire-and-forget. API routes call this after a successful response,
// so any failure here must NOT surface to the caller. If the DB is down,
// we swallow silently — admin metrics will just be a bit short.
// ============================================================================

import prisma, { isDatabaseHealthy } from './db';
import { getSession } from './auth';

export interface ApiUsageInput {
  /** Semantic feature tag, e.g. "TRANSCRIBE" or "DOC_EDITOR". Keep stable —
   *  the admin UI groups by this. Prefer UPPERCASE identifiers over route
   *  paths so feature names survive route renames. */
  feature: string;
  /** OpenAI-style total_tokens. Use for token-billed features (DOC_EDITOR). */
  tokens?: number | null;
  /** Audio seconds. Use for duration-billed features (TRANSCRIBE → Whisper). */
  durationSeconds?: number | null;
  /**
   * Override the user ID. Usually omitted — we'll pull from the current
   * session. Pass this only when the call site already has the ID and
   * wants to skip the session round-trip.
   */
  userId?: string;
  /** Override the practice ID. Same rationale as userId — pass when the
   *  call site has it (e.g., from its session) to skip the session lookup
   *  inside logApiUsage. */
  practiceId?: string;
}

export async function logApiUsage(input: ApiUsageInput): Promise<void> {
  let userId = input.userId;
  let practiceId = input.practiceId;
  try {
    // One session lookup covers both userId and practiceId if neither is
    // passed. Callers that have the session in scope should pass both to
    // skip this round-trip entirely.
    if (!userId || !practiceId) {
      const session = await getSession();
      userId = userId ?? session?.user?.id;
      practiceId = practiceId ?? session?.user?.practiceId;
    }
    // Name each silent-skip path so docker logs tell us WHICH guard tripped.
    if (!userId) {
      console.warn(
        `[usage] skip feature=${input.feature}: no userId (session unavailable in this route context)`
      );
      return;
    }
    if (!practiceId) {
      console.warn(
        `[usage] skip feature=${input.feature} userId=${userId}: no practiceId (session missing multi-tenancy claim)`
      );
      return;
    }
    if (!(await isDatabaseHealthy())) {
      console.warn(
        `[usage] skip feature=${input.feature} userId=${userId}: database unhealthy`
      );
      return;
    }

    await prisma.apiUsage.create({
      data: {
        userId,
        practiceId,
        feature: input.feature,
        tokens: input.tokens ?? null,
        durationSeconds: input.durationSeconds ?? null,
      },
    });
  } catch (err) {
    // Prisma write failures land here — most commonly a schema/column
    // mismatch between the running Prisma client and the DB. Log the
    // feature + userId so grep narrows fast.
    console.error(
      `[usage] write failed feature=${input.feature} userId=${userId}:`,
      err
    );
  }
}
