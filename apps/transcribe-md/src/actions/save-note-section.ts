'use server';

// ============================================================================
// saveNoteSectionAction — edit ONE section, save the WHOLE note.
// ----------------------------------------------------------------------------
// On the document view a doctor taps a section and edits just that. The note is
// still stored and saved as one markdown blob, so this splices the new body
// back in and hands the result to the existing `saveSoapDraftAction`.
//
// THAT DELEGATION IS THE POINT. Draft saves already have a class, a
// concurrency rule (optimistic on soapVersion), a set of refusals (signed,
// archived, still-processing) and an edit-forensics capture. A section edit is
// a draft save — it must not acquire a second, subtly different set of any of
// those. Everything here happens BEFORE the save: read the note, splice,
// delegate.
//
// It REFUSES rather than guesses. If the heading is gone or appears twice we
// cannot say which section the doctor edited, and writing their words into the
// wrong part of a clinical note is worse than declining to save.
// ============================================================================

import prisma from '@meddoc/db';

import { requireSession } from '@/lib/auth';
import { visitByIdScope } from '@/lib/practice-scope';
import { invalidateVisitFills } from '@/lib/docx-preview/fill-cache';
import { spliceNoteSection } from '@/lib/splice-note-section';

import { saveSoapDraftAction } from './soap';

export interface SaveNoteSectionResult {
  ok: boolean;
  error?: string;
  /** The full note after the edit, so the caller can re-render without a round
   *  trip — the same payload shape the adopt action returns. */
  soapFinal?: string;
  soapVersion?: number;
}

export async function saveNoteSectionAction(
  visitId: string,
  sectionLabel: string,
  body: string,
  /** The version the EDITOR WAS OPENED AGAINST. Without it the optimistic
   *  concurrency gate is a no-op: reading the current version here and handing
   *  it straight back to the save means the WHERE clause always matches, and a
   *  suggestion adopted while the editor sat open is silently overwritten by
   *  the stale body the doctor still has on screen. */
  expectedVersion?: number,
): Promise<SaveNoteSectionResult> {
  const session = await requireSession();

  const visit = await prisma.transcribeVisit.findFirst({
    where: {
      ...visitByIdScope(visitId, session.user.practiceId),
      // ACTION, not a read: the author conjunct stays until T6's role
      // gate decides who else may edit. Widening SEE never widens DO.
      userId: session.user.id,
      deletedAt: null,
      archivedAt: null,
    },
    select: { soapFinal: true, soapVersion: true },
  });
  if (!visit?.soapFinal) return { ok: false, error: 'Visit not found.' };

  // The note moved under the open editor. Refuse — the doctor is looking at
  // text that is no longer what the note says, and saving it would erase
  // whatever changed it.
  if (expectedVersion !== undefined && expectedVersion !== visit.soapVersion) {
    return {
      ok: false,
      error: 'The note changed while you were editing — reload to see it, then re-apply your change.',
    };
  }

  const spliced = spliceNoteSection(visit.soapFinal, sectionLabel, body);
  if (!spliced) {
    return {
      ok: false,
      error:
        "We couldn't find that section in the note any more — reload the page and try again.",
    };
  }
  if (spliced.text === visit.soapFinal) {
    // Nothing changed. Don't burn a version, don't invalidate a cache.
    return { ok: true, soapFinal: visit.soapFinal, soapVersion: visit.soapVersion };
  }

  // The existing save: same class, same concurrency rule, same refusals.
  const saved = await saveSoapDraftAction(visitId, spliced.text, visit.soapVersion);
  if (!saved.ok) {
    // 'conflict' is the action's internal code, not something to show a doctor.
    return {
      ok: false,
      error:
        saved.error === 'conflict'
          ? 'The note changed in another tab — reload and try again.'
          : saved.error,
    };
  }

  // The document must not keep showing the sentence they just replaced.
  await invalidateVisitFills(visitId);

  return {
    ok: true,
    soapFinal: spliced.text,
    soapVersion: visit.soapVersion + 1,
  };
}
