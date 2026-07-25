// ============================================================================
// POST /api/visits/[id]/export/clipboard-section — audit beacon (S4b)
// ----------------------------------------------------------------------------
// Body: { scope: 'section' | 'summary' | 'full_note', section: string,
//         sizeBytes: number }
// Response: 204.
//
// The sibling /export/clipboard route BUILDS the text server-side, so it can
// audit what it produced. These copies are different: the text is already in
// the browser (it was rendered on the page), so the server has nothing to
// generate. This route exists purely to record the disclosure.
//
// It therefore takes no text and returns no body. It still authenticates and
// re-checks ownership of the visit, so the endpoint cannot be used to write
// audit rows against someone else's visit id — an unowned id 404s exactly like
// every other visit-scoped route, which also stops it being an existence
// oracle.
//
// Writes EXPORT_CLIPBOARD_COPIED (the existing action — no enum change) with
// `scope` in metadata, so the admin PHI-export detector, which filters
// action::text LIKE 'EXPORT_%', picks these up with no change of its own.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { apiError, withApiHandler } from '@/lib/api-error';
import { auth } from '@/lib/nextauth';
import { logAudit } from '@/lib/audit';
import { RATE_LIMITS, rateLimitOr429 } from '@/lib/rate-limit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  scope: z.enum(['section', 'summary', 'full_note']),
  // Free-text label ("Subjective", "Patient summary"). Bounded so a client
  // cannot stuff the audit metadata with arbitrary volume.
  section: z.string().min(1).max(120),
  // Reported by the client and therefore untrusted — it is a volume signal for
  // the export-spike detector, not evidence. Bounded to keep it sane.
  sizeBytes: z.number().int().nonnegative().max(10_000_000),
});

export const POST = withApiHandler<{ id: string }>(
  'api:visits:export:clipboard-section',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await auth();
    const userId = session?.user?.id;
    if (!userId) return apiError('unauthorized', 401);

    const blocked = rateLimitOr429(RATE_LIMITS.SETTINGS, userId);
    if (blocked) return blocked;

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) return apiError('invalid body', 400);

    // Ownership gate. Cheap targeted select — this route never needs the note.
    const visit = await prisma.transcribeVisit.findFirst({
      where: { id: visitId, userId },
      select: { id: true, signedAt: true },
    });
    if (!visit) return apiError('not found', 404);

    await logAudit({
      action: 'EXPORT_CLIPBOARD_COPIED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
      metadata: {
        scope: parsed.data.scope,
        section: parsed.data.section,
        sizeBytes: parsed.data.sizeBytes,
        isSigned: visit.signedAt !== null,
      },
    });

    return new NextResponse(null, { status: 204 });
  }
);
