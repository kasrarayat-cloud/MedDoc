// ============================================================================
// POST /api/visits/[id]/export/clipboard (T-M7)
// ----------------------------------------------------------------------------
// Body: { format: 'epic' | 'athena' | 'cerner' | 'eclinicalworks' | 'generic' }
// Response: { text: string }  — what the browser pastes into the EHR.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import { z } from 'zod';

import { auth } from '@/lib/nextauth';
import { loadVisitExportData } from '@/lib/visit-export-server';
import { formatForEhr } from '@/lib/ehr-formatters';
import { logDelivery, type DeliveryChannel } from '@/lib/deliveries';

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

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: visitId } = await params;

  const session = await auth();
  const userId = session?.user?.id;
  if (!userId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 });
  }
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'format must be epic | athena | cerner | eclinicalworks | generic' },
      { status: 400 }
    );
  }

  const data = await loadVisitExportData(visitId, userId);
  if (!data) {
    return NextResponse.json({ error: 'not found' }, { status: 404 });
  }

  const text = formatForEhr(parsed.data.format, data);

  logDelivery({
    visitId,
    channel: CHANNEL_BY_FORMAT[parsed.data.format],
    sizeBytes: Buffer.byteLength(text, 'utf8'),
  });

  return NextResponse.json({ text }, { status: 200 });
}
