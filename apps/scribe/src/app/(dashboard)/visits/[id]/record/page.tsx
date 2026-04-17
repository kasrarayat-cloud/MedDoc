import { notFound, redirect } from 'next/navigation';
import Link from 'next/link';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';
import RecordClient from './RecordClient';

export const dynamic = 'force-dynamic';

/**
 * Live-recording page (M3). Only renders when the visit is LIVE mode and
 * in a pre-finalize status (DRAFT or RECORDING — the latter handles a
 * tab reload mid-visit since the WS server also accepts RECORDING).
 *
 * Status beyond RECORDING means the visit has already been flushed —
 * redirect back to /visits/[id] so the clinician follows the normal
 * review flow.
 */
export default async function RecordPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = (await getSession())!;

  const visit = await prisma.scribeVisit.findFirst({
    where: { id, ...tenantScope(session), deletedAt: null },
    select: {
      id: true,
      userId: true,
      mode: true,
      status: true,
      patient: { select: { firstName: true, lastName: true, chartId: true } },
      specialty: { select: { displayName: true, version: true } },
    },
  });
  if (!visit) notFound();

  if (visit.mode !== 'LIVE') {
    redirect(`/visits/${id}`);
  }
  if (visit.status !== 'DRAFT' && visit.status !== 'RECORDING') {
    redirect(`/visits/${id}`);
  }
  if (visit.userId !== session.user.id) {
    // Another clinician's visit — refuse.
    notFound();
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <Link
          href={`/visits/${visit.id}`}
          className="text-sm text-slate-400 hover:text-slate-200"
        >
          ← Visit
        </Link>
      </div>
      <div>
        <h1 className="text-2xl font-semibold">Live recording</h1>
        <p className="text-sm text-slate-400 mt-1">
          {visit.patient.lastName}, {visit.patient.firstName}
          {visit.patient.chartId ? ` · ${visit.patient.chartId}` : ''} ·{' '}
          {visit.specialty.displayName} (v{visit.specialty.version})
        </p>
      </div>

      <RecordClient visitId={visit.id} />
    </div>
  );
}
