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
// Both audit with PHI-SAFE metadata: { section, reason, remaining } — NEVER
// claim text. Both reject SIGNED visits (read-only after signing). Neither
// throws raw — every failure is { ok: false, error }.
// ============================================================================

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, TranscribeVisitStatus } from '@prisma/client';
import { requireSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';

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
}

const SuggestionInputSchema = z.object({
  visitId: z.string().min(1),
  index: z.number().int().nonnegative(),
});

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

// ─── Actions ────────────────────────────────────────────────────────────────

/** Adopt suggestion `index` into the note: append its text verbatim under
 *  its section heading (else at the end), remove it from the lane, bump
 *  soapVersion — all in one version-gated update. Audit: SUGGESTION_ADOPTED
 *  with { section, reason, remaining } only (never claim text). */
export async function adoptSuggestionAction(
  visitId: string,
  index: number
): Promise<SuggestionActionResult> {
  try {
    const session = await requireSession();
    const parsed = SuggestionInputSchema.safeParse({ visitId, index });
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
    const remaining = claims.filter((_, i) => i !== parsed.data.index);
    const newSoap = appendClaimToSoap(visit.soapFinal ?? '', claim.section, claim.text);

    // Single atomic update, gated on the soapVersion we just read — the
    // same optimistic-concurrency pattern as saveSoapDraftAction. count=0
    // means a section save (or another adopt) landed in between.
    const result = await prisma.transcribeVisit.updateMany({
      where: { id: visit.id, soapVersion: visit.soapVersion },
      data: {
        soapFinal: newSoap,
        soapVersion: { increment: 1 },
        suggestedClaims:
          remaining.length > 0
            ? (remaining as unknown as Prisma.InputJsonValue)
            : Prisma.DbNull,
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

    revalidatePath(`/visits/${visit.id}`);
    return {
      ok: true,
      soapFinal: newSoap,
      suggestedClaims: remaining.length > 0 ? remaining : null,
      soapVersion: visit.soapVersion + 1,
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
  index: number
): Promise<SuggestionActionResult> {
  try {
    const session = await requireSession();
    const parsed = SuggestionInputSchema.safeParse({ visitId, index });
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
    const remaining = claims.filter((_, i) => i !== parsed.data.index);

    await prisma.transcribeVisit.update({
      where: { id: visit.id },
      data: {
        suggestedClaims:
          remaining.length > 0
            ? (remaining as unknown as Prisma.InputJsonValue)
            : Prisma.DbNull,
      },
    });

    void logAudit({
      action: 'SUGGESTION_DISMISSED',
      targetType: 'TranscribeVisit',
      targetId: visit.id,
      metadata: { section: claim.section, reason: claim.reason, remaining: remaining.length },
    });

    revalidatePath(`/visits/${visit.id}`);
    return {
      ok: true,
      suggestedClaims: remaining.length > 0 ? remaining : null,
    };
  } catch {
    return { ok: false, error: 'Something went wrong dismissing the suggestion.' };
  }
}
