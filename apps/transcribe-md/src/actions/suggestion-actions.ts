'use server';

// ============================================================================
// Suggestions-lane server actions — hybrid anchored generation (2026-06-11).
// ----------------------------------------------------------------------------
// The L4b verifier (worker/layers/04b-anchor-verify.ts) demotes unverifiable
// claims to `transcribe_visits.suggestedClaims` ([{text, reason, section,
// anchor}]). The "Suggested by AI — not stated in this visit" lane renders
// them on READY visits; these actions are the explicit doctor-adoption flow:
//
//   - adoptSuggestionAction  → appends the claim text VERBATIM to soapFinal
//     under its section heading (adoption = doctor attestation; the audit row
//     is the record — no inline label), removes the claim from the lane, and
//     bumps soapVersion in the SAME atomic update. The write is gated on the
//     soapVersion read in this request (the editor-save optimistic-concurrency
//     pattern from actions/soap.ts) so an adopt can never clobber a section
//     save that landed in between.
//   - dismissSuggestionAction → removes the claim from the lane only; never
//     touches soapFinal / soapVersion.
//
// Both actions take the exact claim TEXT the client rendered alongside the
// index and refuse on mismatch — a stale tab whose lane has been re-indexed
// by another tab's adopt/dismiss can therefore never act on the wrong claim.
//
// Both audit with PHI-SAFE metadata: { section, reason, remaining } — NEVER
// claim text. Both reject SIGNED visits (read-only after signing). Neither
// throws raw — every failure is { ok: false, error }.
//
// E/M recompute on adoption — visible-confirm, never silent (2026-06-12,
// prod smoke #311). The E/M level is recomputed on-read (page.tsx) and on
// every client rescore (CodingRail → POST /em-score) — adopting a med-change
// suggestion used to flip the displayed code (99213 → 99214) silently. Both
// actions now run the SAME scoring engine (computeEmScore, same inputs as
// the /em-score route so the result matches what the rail displays) on the
// note BEFORE vs AFTER the action. A changed level is persisted PHI-free to
// `emPendingChange` ({from, to, cause, at}) IN THE SAME atomic update as the
// note write, and audited as EM_LEVEL_CHANGED with metadata EXACTLY
// { from, to, cause }. The sign route then refuses READY→SIGNED until the
// doctor explicitly acknowledges the recorded change (fail-closed). When a
// second action changes the level again before signing, the record keeps the
// ORIGINAL `from` (the level the doctor last reviewed) and the changes
// cancel out to SQL NULL when the level returns to that baseline.
// ============================================================================

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';
import { requireSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { computeDisplayedEmCode } from '@/lib/em-coding/displayed-level';
import { log } from '@/lib/log';
import {
  unacknowledgedEmChange,
  type EmChangeCause,
  type EmPendingChange,
} from '@/lib/em-pending-change';

/** Mirror of the verifier's SuggestedClaim — duplicated here (rather than
 *  imported from the worker layer) so the server-action bundle never pulls
 *  worker/model-client code. */
export interface SuggestedClaimDto {
  text: string;
  reason: string;
  section: string;
  /** The anchor quote(s) the model offered, joined — or 'no anchor'. */
  anchor: string;
}

export interface SuggestionActionResult {
  ok: boolean;
  error?: string;
  /** Populated on a successful ADOPT — the new note text for in-place
   *  client refresh (the lane remounts the editor with it). */
  soapFinal?: string;
  /** Remaining lane claims after the action; null when the lane emptied. */
  suggestedClaims?: SuggestedClaimDto[] | null;
  /** New optimistic-concurrency token after a successful ADOPT. */
  soapVersion?: number;
  /** Post-action UNACKNOWLEDGED E/M change ({from, to} codes only — no
   *  PHI), or null when there is nothing for the doctor to confirm at
   *  signing. Present on every success so the client can update the Sign
   *  & Send confirm control without waiting for the RSC refresh. */
  emPendingChange?: { from: string; to: string } | null;
}

const SuggestionInputSchema = z.object({
  visitId: z.string().min(1),
  index: z.number().int().nonnegative(),
  // Content-identity check: the exact claim text the client rendered at
  // `index`. The DB array can shift under a stale tab (another tab's
  // dismiss/adopt re-indexes it); a bare index would then silently act on
  // the WRONG claim. Text+index must both match or the action refuses.
  expectedText: z.string().min(1),
});

const STALE_LANE_ERROR =
  'The suggestions changed in another tab — reload and try again.';

// ─── Helpers (module-private — 'use server' files may only export async) ────

/** STRICT jsonb coercion: any malformed entry voids the whole array so the
 *  client-rendered indices can never drift from the DB array's indices. */
function parseClaims(raw: unknown): SuggestedClaimDto[] | null {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const out: SuggestedClaimDto[] = [];
  for (const entry of raw) {
    if (entry === null || typeof entry !== 'object') return null;
    const c = entry as Record<string, unknown>;
    if (
      typeof c.text !== 'string' ||
      typeof c.reason !== 'string' ||
      typeof c.section !== 'string' ||
      typeof c.anchor !== 'string'
    ) {
      return null;
    }
    out.push({ text: c.text, reason: c.reason, section: c.section, anchor: c.anchor });
  }
  return out;
}

const HEADING_RE = /^#{1,6}\s+(.*)$/;

function normalizeHeading(s: string): string {
  return s.replace(/\*\*/g, '').replace(/:\s*$/, '').trim().toLowerCase();
}

/** Append `claimText` as a new line at the END of the `section` heading's
 *  block in `soap`. When the heading isn't found (custom-format drift, the
 *  verifier's '(preamble)' / '(entire note)' sentinels), append at the end
 *  of the note. The claim text goes in VERBATIM — no trailing label;
 *  adoption is the doctor's attestation and the audit row is the record. */
function appendClaimToSoap(soap: string, section: string, claimText: string): string {
  const target = normalizeHeading(section);
  const lines = soap.split('\n');

  let headingIdx = -1;
  if (target.length > 0) {
    for (let i = 0; i < lines.length; i++) {
      const m = lines[i].match(HEADING_RE);
      if (m && normalizeHeading(m[1]) === target) {
        headingIdx = i;
        break;
      }
    }
  }

  if (headingIdx === -1) {
    const trimmed = soap.replace(/\s+$/, '');
    return trimmed.length > 0 ? `${trimmed}\n\n${claimText}` : claimText;
  }

  // Section block ends at the next heading (or EOF). Insert before the
  // trailing blank line(s) that separate it from the next heading.
  let end = lines.length;
  for (let i = headingIdx + 1; i < lines.length; i++) {
    if (HEADING_RE.test(lines[i])) {
      end = i;
      break;
    }
  }
  let insertAt = end;
  while (insertAt > headingIdx + 1 && lines[insertAt - 1].trim() === '') insertAt--;
  lines.splice(insertAt, 0, claimText);
  return lines.join('\n');
}

type LoadedVisit = {
  id: string;
  userId: string;
  status: TranscribeVisitStatus;
  deletedAt: Date | null;
  archivedAt: Date | null;
  soapFinal: string | null;
  soapVersion: number;
  suggestedClaims: unknown;
  icdCodes: unknown;
  rxDrafts: unknown;
  cptCodes: unknown;
  emPendingChange: unknown;
};

/** Shared auth + ownership + lifecycle gate (mirrors actions/soap.ts). */
async function loadVisitForSuggestion(
  visitId: string,
  userId: string
): Promise<{ visit: LoadedVisit } | { error: string }> {
  const visit = (await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: {
      id: true,
      userId: true,
      status: true,
      deletedAt: true,
      archivedAt: true,
      soapFinal: true,
      soapVersion: true,
      suggestedClaims: true,
      // E/M visible-confirm — structured signals for the scoring engine
      // (same inputs as the /em-score route) + the existing pending-change
      // record so a second change merges against the doctor's baseline.
      icdCodes: true,
      rxDrafts: true,
      cptCodes: true,
      emPendingChange: true,
    },
  })) as LoadedVisit | null;

  if (!visit || visit.userId !== userId) {
    return { error: 'Visit not found.' };
  }
  if (visit.deletedAt !== null || visit.archivedAt !== null) {
    return { error: 'Visit is no longer active. Restore it first.' };
  }
  if (visit.status === TranscribeVisitStatus.SIGNED) {
    return { error: 'Signed notes cannot be changed.' };
  }
  if (visit.status !== TranscribeVisitStatus.READY) {
    return { error: 'Note is still processing.' };
  }
  return { visit };
}

// ─── E/M level delta (visible-confirm, never silent) ────────────────────────

/** Sentinel recorded when scoring ERRORS — fail toward REQUIRING
 *  confirmation (the GOAL's invariant: never toward a silent sign). `from`
 *  and `to` differ so it survives the merge-cancel and forces the gate; the
 *  sign dialog renders an honest "couldn't recompute — review" prompt. */
const EM_DELTA_INDETERMINATE = { from: 'unknown', to: 'review' } as const;

/** The level change an action produced, as the DOCTOR SEES IT. Computes the
 *  DISPLAYED code (override ?? engine, via the shared computeDisplayedEmCode)
 *  for the note BEFORE vs AFTER — the SAME projection and the SAME extractors
 *  the CodingRail uses (POST /em-score). Sharing that one function is what
 *  makes a rail-vs-gate divergence impossible: if any surface shows the
 *  physician a changed level at sign time, this returns it and the gate fires.
 *  Returns null when the displayed code is unchanged.
 *
 *  Short-circuits on byte-identical text (today's dismiss path is a
 *  guaranteed null; the machinery still runs so the `suggestion_dismissed`
 *  cause is live the day dismiss ever influences scoring).
 *
 *  FAIL TOWARD CONFIRM: a scoring error returns the indeterminate sentinel
 *  (forces confirmation) rather than throwing — the note change still lands
 *  and the doctor must confirm before signing, never silently. */
async function computeEmLevelDelta(args: {
  beforeSoap: string;
  afterSoap: string;
  visitId: string;
  userId: string;
  practiceId?: string;
  icdCodes: unknown;
  rxDrafts: unknown;
  cptCodes: unknown;
}): Promise<{ from: string; to: string } | null> {
  if (args.beforeSoap === args.afterSoap) return null;
  const signals = {
    icdCodes: args.icdCodes,
    rxDrafts: args.rxDrafts,
    cptCodes: args.cptCodes,
  };
  const ctx = {
    practiceId: args.practiceId,
    visitId: args.visitId,
    userId: args.userId,
  };
  try {
    const [from, to] = await Promise.all([
      computeDisplayedEmCode(args.beforeSoap, signals, ctx),
      computeDisplayedEmCode(args.afterSoap, signals, ctx),
    ]);
    if (from === to) return null;
    return { from, to };
  } catch (err) {
    log.warn('suggestion-actions', 'em-delta scoring failed — forcing confirm', {
      visitId: args.visitId,
      error: err instanceof Error ? err.message : String(err),
    });
    return { ...EM_DELTA_INDETERMINATE };
  }
}

/** Merge the per-action delta against an existing UNACKNOWLEDGED record:
 *  `from` stays the level the doctor last reviewed (the baseline), and a
 *  change back to that baseline cancels the record (SQL NULL — nothing to
 *  confirm). Returns the value to write, or undefined for "don't touch the
 *  column" (no delta this action). */
function mergeEmPendingChange(
  existing: EmPendingChange | null,
  delta: { from: string; to: string } | null,
  cause: EmChangeCause
): Prisma.InputJsonValue | typeof Prisma.DbNull | undefined {
  if (!delta) return undefined;
  const baselineFrom = existing?.from ?? delta.from;
  if (baselineFrom === delta.to) return Prisma.DbNull;
  const record: EmPendingChange = {
    from: baselineFrom,
    to: delta.to,
    cause,
    at: new Date().toISOString(),
  };
  return record as unknown as Prisma.InputJsonValue;
}

/** Project the post-action column state → the result's {from, to} (or
 *  null). `write === undefined` means the column was left untouched. */
function pendingChangeForResult(
  existing: EmPendingChange | null,
  write: Prisma.InputJsonValue | typeof Prisma.DbNull | undefined
): { from: string; to: string } | null {
  if (write === undefined) {
    return existing ? { from: existing.from, to: existing.to } : null;
  }
  if (write === Prisma.DbNull) return null;
  const w = write as unknown as EmPendingChange;
  return { from: w.from, to: w.to };
}

// ─── Actions ────────────────────────────────────────────────────────────────

/** Adopt suggestion `index` into the note: append its text verbatim under
 *  its section heading (else at the end), remove it from the lane, bump
 *  soapVersion — all in one version-gated update. Audit: SUGGESTION_ADOPTED
 *  with { section, reason, remaining } only (never claim text). */
export async function adoptSuggestionAction(
  visitId: string,
  index: number,
  expectedText: string
): Promise<SuggestionActionResult> {
  try {
    const session = await requireSession();
    const parsed = SuggestionInputSchema.safeParse({ visitId, index, expectedText });
    if (!parsed.success) {
      return { ok: false, error: 'Invalid input.' };
    }

    const loaded = await loadVisitForSuggestion(parsed.data.visitId, session.user.id);
    if ('error' in loaded) return { ok: false, error: loaded.error };
    const { visit } = loaded;

    const claims = parseClaims(visit.suggestedClaims);
    if (!claims || parsed.data.index >= claims.length) {
      return { ok: false, error: 'Suggestion not found.' };
    }
    const claim = claims[parsed.data.index];
    if (claim.text !== parsed.data.expectedText) {
      return { ok: false, error: STALE_LANE_ERROR };
    }
    const remaining = claims.filter((_, i) => i !== parsed.data.index);
    const newSoap = appendClaimToSoap(visit.soapFinal ?? '', claim.section, claim.text);

    // E/M visible-confirm (prod smoke #311): did THIS adoption change the
    // computed level? Scored BEFORE the write so the pending-change record
    // lands in the SAME atomic update as the note — a crash between "note
    // changed" and "change recorded" (the silent-flip window) cannot exist.
    const emDelta = await computeEmLevelDelta({
      beforeSoap: visit.soapFinal ?? '',
      afterSoap: newSoap,
      visitId: visit.id,
      userId: session.user.id,
      practiceId: session.user.practiceId,
      icdCodes: visit.icdCodes,
      rxDrafts: visit.rxDrafts,
      cptCodes: visit.cptCodes,
    });
    const priorPending = unacknowledgedEmChange(visit.emPendingChange);
    const emPendingWrite = mergeEmPendingChange(
      priorPending,
      emDelta,
      'suggestion_adopted'
    );

    // Single atomic update, gated on the soapVersion we just read — the
    // same optimistic-concurrency pattern as saveSoapDraftAction. count=0
    // means a section save (or another adopt) landed in between.
    const result = await prisma.transcribeVisit.updateMany({
      // status:READY too (auditor WARN-1): the LLM-scoring window between
      // this action's READY check and its write can straddle a concurrent
      // READY→SIGNED transition — the write must MISS a signed row, never
      // mutate it or deposit an unacknowledgeable emPendingChange.
      where: { id: visit.id, soapVersion: visit.soapVersion, status: TranscribeVisitStatus.READY },
      data: {
        soapFinal: newSoap,
        soapVersion: { increment: 1 },
        suggestedClaims:
          remaining.length > 0
            ? (remaining as unknown as Prisma.InputJsonValue)
            : Prisma.DbNull,
        ...(emPendingWrite !== undefined
          ? { emPendingChange: emPendingWrite }
          : {}),
      },
    });
    if (result.count === 0) {
      return {
        ok: false,
        error: 'The note changed in another tab — reload and try again.',
      };
    }

    // PHI-safe metadata: section label + demotion reason + remaining count
    // only. NEVER the claim text — that is clinical content.
    void logAudit({
      action: 'SUGGESTION_ADOPTED',
      targetType: 'TranscribeVisit',
      targetId: visit.id,
      metadata: { section: claim.section, reason: claim.reason, remaining: remaining.length },
    });
    // One row per level-changing action (this leg's own {from, to} — the
    // persisted record may carry an older baseline `from`). Metadata is
    // EXACTLY { from, to, cause }: CPT codes + cause class, never note text.
    if (emDelta) {
      void logAudit({
        action: 'EM_LEVEL_CHANGED',
        targetType: 'TranscribeVisit',
        targetId: visit.id,
        metadata: {
          from: emDelta.from,
          to: emDelta.to,
          cause: 'suggestion_adopted',
        },
      });
    }

    revalidatePath(`/visits/${visit.id}`);
    return {
      ok: true,
      soapFinal: newSoap,
      suggestedClaims: remaining.length > 0 ? remaining : null,
      soapVersion: visit.soapVersion + 1,
      emPendingChange: pendingChangeForResult(priorPending, emPendingWrite),
    };
  } catch {
    return { ok: false, error: 'Something went wrong adopting the suggestion.' };
  }
}

/** Dismiss suggestion `index`: remove it from the lane. Never touches
 *  soapFinal / soapVersion. Audit: SUGGESTION_DISMISSED with the same
 *  PHI-safe { section, reason, remaining } metadata. */
export async function dismissSuggestionAction(
  visitId: string,
  index: number,
  expectedText: string
): Promise<SuggestionActionResult> {
  try {
    const session = await requireSession();
    const parsed = SuggestionInputSchema.safeParse({ visitId, index, expectedText });
    if (!parsed.success) {
      return { ok: false, error: 'Invalid input.' };
    }

    const loaded = await loadVisitForSuggestion(parsed.data.visitId, session.user.id);
    if ('error' in loaded) return { ok: false, error: loaded.error };
    const { visit } = loaded;

    const claims = parseClaims(visit.suggestedClaims);
    if (!claims || parsed.data.index >= claims.length) {
      return { ok: false, error: 'Suggestion not found.' };
    }
    const claim = claims[parsed.data.index];
    if (claim.text !== parsed.data.expectedText) {
      return { ok: false, error: STALE_LANE_ERROR };
    }
    const remaining = claims.filter((_, i) => i !== parsed.data.index);

    // E/M visible-confirm: dismiss never touches the note, and the engine
    // scores ONLY the note body (+ icd/rx signals dismiss also never
    // touches), so the delta short-circuits to null today. The machinery
    // still runs so the `suggestion_dismissed` cause is live the day the
    // lane's content ever influences scoring.
    const emDelta = await computeEmLevelDelta({
      beforeSoap: visit.soapFinal ?? '',
      afterSoap: visit.soapFinal ?? '',
      visitId: visit.id,
      userId: session.user.id,
      practiceId: session.user.practiceId,
      icdCodes: visit.icdCodes,
      rxDrafts: visit.rxDrafts,
      cptCodes: visit.cptCodes,
    });
    const priorPending = unacknowledgedEmChange(visit.emPendingChange);
    const emPendingWrite = mergeEmPendingChange(
      priorPending,
      emDelta,
      'suggestion_dismissed'
    );

    // updateMany + status:READY (auditor WARN-1): a dismiss racing the
    // sign transition must miss the signed row entirely.
    const dismissResult = await prisma.transcribeVisit.updateMany({
      where: { id: visit.id, status: TranscribeVisitStatus.READY },
      data: {
        suggestedClaims:
          remaining.length > 0
            ? (remaining as unknown as Prisma.InputJsonValue)
            : Prisma.DbNull,
        ...(emPendingWrite !== undefined
          ? { emPendingChange: emPendingWrite }
          : {}),
      },
    });
    if (dismissResult.count === 0) {
      return { ok: false, error: 'The visit was signed in another tab — reload.' };
    }

    void logAudit({
      action: 'SUGGESTION_DISMISSED',
      targetType: 'TranscribeVisit',
      targetId: visit.id,
      metadata: { section: claim.section, reason: claim.reason, remaining: remaining.length },
    });
    if (emDelta) {
      void logAudit({
        action: 'EM_LEVEL_CHANGED',
        targetType: 'TranscribeVisit',
        targetId: visit.id,
        metadata: {
          from: emDelta.from,
          to: emDelta.to,
          cause: 'suggestion_dismissed',
        },
      });
    }

    revalidatePath(`/visits/${visit.id}`);
    return {
      ok: true,
      suggestedClaims: remaining.length > 0 ? remaining : null,
      emPendingChange: pendingChangeForResult(priorPending, emPendingWrite),
    };
  } catch {
    return { ok: false, error: 'Something went wrong dismissing the suggestion.' };
  }
}
