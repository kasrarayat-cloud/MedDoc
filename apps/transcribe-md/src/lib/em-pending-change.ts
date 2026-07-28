// ============================================================================
// E/M pending-change record — single source of truth for the shape
// ----------------------------------------------------------------------------
// "E/M recompute on adoption: visible-confirm, never silent" (2026-06-12,
// prod smoke #311 follow-up). The E/M level is never persisted per visit —
// it is recomputed on-read (page.tsx initial render) and on every client
// rescore (CodingRail → POST /em-score), so adopting a suggestion that
// changes the computed level used to flip the displayed code silently.
//
// The adopt/dismiss suggestion actions (actions/suggestion-actions.ts) now
// compare the computed level before vs after the action and persist a
// delta record to `transcribe_visits.emPendingChange`:
//
//   { from, to, cause, at, acknowledgedAt? }
//
// PHI-SAFE by construction: CPT codes + cause class + ISO timestamps only —
// never note text. Three consumers must agree on this shape, byte-for-byte:
//
//   1. the suggestion actions — WRITE the record (and merge against an
//      existing unacknowledged one so `from` stays the level the doctor
//      last reviewed);
//   2. the sign route (api/visits/[id]/sign/route.ts) — REJECTS a sign
//      request when an UNACKNOWLEDGED record exists and the request does
//      not echo {from, to} back as the explicit acknowledgement
//      (fail-closed server-side, not just UI);
//   3. the visit page (app/visits/[id]/page.tsx) — hydrates the Sign &
//      Send modal's "Documentation level changed" confirm control.
//
// STRICT parse: any malformed entry reads as null. For the WRITERS that is
// the conservative direction (a fresh delta starts a new record). The sign
// gate intentionally does NOT use the strict parse alone — see
// `unacknowledgedEmChange`, which fails CLOSED on malformed-but-present
// values so a corrupted record can never silently unlock signing.
// ============================================================================

export const EM_CHANGE_CAUSES = [
  'suggestion_adopted',
  'suggestion_dismissed',
  // A doctor (or the chat, on their instruction) changed the note and the
  // re-score found the level had moved. Added with the E/M-stale unification:
  // without it every record the re-score wrote was malformed by THIS parser,
  // coerced to the unknown→unknown sentinel, and the doctor who confirmed the
  // correct code was refused — the confirm card reading "unknown, up from
  // unknown" on the one path the gate exists to protect.
  'note_edited',
  // The doctor set the level themselves, from the gate stack. Same rule as
  // above and the same reason for spelling it out: a cause this parser does not
  // recognise is coerced to the unknown→unknown sentinel, so an override
  // recorded under an unlisted cause would confront the doctor with a confirm
  // card reading "unknown, up from unknown" — for a code they had just chosen.
  //
  // It is a PENDING CHANGE and not a silent write on purpose. A doctor may
  // disagree with the scored level; they may not skip confirming what they are
  // about to sign, and the surface that asks is the same one that asks after
  // the model moves a level.
  'doctor_override',
] as const;

export type EmChangeCause = (typeof EM_CHANGE_CAUSES)[number];

export interface EmPendingChange {
  /** E/M code computed BEFORE the suggestion action (e.g. '99213'). */
  from: string;
  /** E/M code computed AFTER the suggestion action (e.g. '99214'). */
  to: string;
  cause: EmChangeCause;
  /** ISO 8601 — when the suggestion action recorded the change. */
  at: string;
  /** ISO 8601 — stamped by the winning READY→SIGNED transition once the
   *  doctor explicitly confirmed the change. Absent = unacknowledged. */
  acknowledgedAt?: string;
}

/** STRICT jsonb coercion — null on any malformed value (same posture as
 *  the suggestedClaims parser in actions/suggestion-actions.ts). */
export function parseEmPendingChange(raw: unknown): EmPendingChange | null {
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }
  const c = raw as Record<string, unknown>;
  if (
    typeof c.from !== 'string' ||
    c.from.length === 0 ||
    typeof c.to !== 'string' ||
    c.to.length === 0 ||
    typeof c.cause !== 'string' ||
    !(EM_CHANGE_CAUSES as readonly string[]).includes(c.cause) ||
    typeof c.at !== 'string'
  ) {
    return null;
  }
  if (c.acknowledgedAt !== undefined && typeof c.acknowledgedAt !== 'string') {
    return null;
  }
  const out: EmPendingChange = {
    from: c.from,
    to: c.to,
    cause: c.cause as EmChangeCause,
    at: c.at,
  };
  if (typeof c.acknowledgedAt === 'string') {
    out.acknowledgedAt = c.acknowledgedAt;
  }
  return out;
}

/** The sign gate's view: the UNACKNOWLEDGED pending change, or null when
 *  there is nothing to confirm (no record, or already acknowledged).
 *
 *  FAIL-CLOSED on corruption: a present-but-malformed value coerces to a
 *  deterministic 'unknown' sentinel record instead of null — the sign
 *  route then still demands an explicit acknowledgement (the dialog shows
 *  "unknown → unknown" and the doctor must confirm), rather than treating
 *  garbage as "nothing to confirm" and silently unlocking the sign. */
export function unacknowledgedEmChange(raw: unknown): EmPendingChange | null {
  if (raw === null || raw === undefined) return null;
  const parsed = parseEmPendingChange(raw);
  if (parsed === null) {
    // Present but malformed — fail closed.
    return {
      from: 'unknown',
      to: 'unknown',
      cause: 'suggestion_adopted',
      at: '',
    };
  }
  return parsed.acknowledgedAt === undefined ? parsed : null;
}
