// ============================================================================
// POST /api/visits/[id]/export/clipboard (T-M7)
// ----------------------------------------------------------------------------
// Body: { format: 'epic' | 'athena' | 'cerner' | 'eclinicalworks' | 'generic' }
// Response: { text: string }  — what the browser pastes into the EHR.
// ============================================================================

import { NextResponse } from 'next/server';
import { z } from 'zod';

import { getSession } from '@/lib/auth';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { formatForEhr } from '@/lib/ehr-formatters';
import { logDelivery, type DeliveryChannel } from '@/lib/deliveries';

import { apiError, withApiHandler } from '@/lib/api-error';
import { logAudit } from '@/lib/audit';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const BodySchema = z.object({
  format: z.enum(['epic', 'athena', 'cerner', 'eclinicalworks', 'generic']),
});

const CHANNEL_BY_FORMAT: Record<
  z.infer<typeof BodySchema>['format'],
  DeliveryChannel
> = {
  epic: 'clipboard_epic',
  athena: 'clipboard_athena',
  cerner: 'clipboard_cerner',
  eclinicalworks: 'clipboard_eclinicalworks',
  generic: 'clipboard_generic',
};

export const POST = withApiHandler<{ id: string }>(
  'api:visits:export:clipboard',
  async (req, { params }) => {
    const { id: visitId } = await params;

    const session = await getSession();
    const userId = session?.user.id;
    if (!userId) return apiError('unauthorized', 401);

    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return apiError('invalid JSON body', 400);
    }
    const parsed = BodySchema.safeParse(body);
    if (!parsed.success) {
      return apiError(
        'format must be epic | athena | cerner | eclinicalworks | generic',
        400
      );
    }

    const data = await loadVisitExportData(visitId, session.user.practiceId);
    // loadVisitExportData returns null for both missing-visit and
    // not-yours; 404 guards against ID enumeration.
    if (!data) return apiError('not found', 404);

    const text = formatForEhr(parsed.data.format, data);

    logDelivery({
      visitId,
      practiceId: session.user.practiceId,
      channel: CHANNEL_BY_FORMAT[parsed.data.format],
      sizeBytes: Buffer.byteLength(text, 'utf8'),
    });
    void logAudit({
      action: 'EXPORT_CLIPBOARD_COPIED',
      targetType: 'TranscribeVisit',
      targetId: visitId,
      metadata: {
        format: parsed.data.format,
        sizeBytes: Buffer.byteLength(text, 'utf8'),
        isSigned: data.signedAt !== null,
      },
    });

    return NextResponse.json({ text }, { status: 200 });
  }
);
