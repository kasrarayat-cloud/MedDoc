'use server';

/**
 * FIRST-FILL REVIEW — ruling #125, clause 2(d).
 *
 * The first visit rendered through a freshly auto-certified twin carries a
 * one-time banner: "First document on your new format — check field placement
 * before signing."
 *
 * ⚠️ THIS IS THE HUMAN CHECK, PLACED WHERE IT IS REAL. Auto-certification means
 * no doctor sat through eighty confirmations, so the review has to happen
 * somewhere — and the honest somewhere is the first real document, which the
 * doctor must read before signing anyway. A checkbox on a settings page is a
 * ritual; looking at your own letterhead with your own patient's findings on it
 * is a check.
 *
 * ⚠️ A SEPARATE READ RATHER THAN A FIELD ON THE PREVIEW RESULT, DELIBERATELY.
 * `VisitPreviewResult` is returned from six places and consumed by the document
 * surface, the export routes and the cache. Threading a banner flag through it
 * would put a UI concern in a type that decides what bytes a doctor downloads.
 */
import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';

/**
 * Is this visit the FIRST one filled through its template's twin?
 *
 * Counts fill manifests for the same template created before this visit's own.
 * Zero means this is the first document the doctor has seen on that format.
 *
 * ⚠️ FAIL-SAFE TO FALSE. If anything cannot be determined the banner does not
 * show. A missing banner costs a doctor nothing they were not already doing —
 * they review before signing regardless — whereas a banner that fires on every
 * visit forever is noise that teaches them to ignore it.
 */
export async function isFirstFillOnTemplateAction(visitId: string): Promise<boolean> {
  try {
    const session = await requireSession();
    const mine = await prisma.templateTwinFillManifest.findFirst({
      where: { visitId, practiceId: session.user.practiceId },
      select: { noteTemplateId: true, createdAt: true },
    });
    // No manifest for this visit means the twin did not fill it — there is no
    // "new format" to check, so there is nothing to say.
    if (!mine) return false;

    const earlier = await prisma.templateTwinFillManifest.count({
      where: {
        noteTemplateId: mine.noteTemplateId,
        practiceId: session.user.practiceId,
        createdAt: { lt: mine.createdAt },
      },
    });
    return earlier === 0;
  } catch {
    return false;
  }
}
