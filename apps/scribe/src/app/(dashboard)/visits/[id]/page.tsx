import Link from 'next/link';
import { notFound } from 'next/navigation';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';

// M1 placeholder. Live recording (M3), batch upload (M2), review UI (M4)
// all land on this route. For now it just confirms the visit row exists
// and displays the metadata.
export default async function VisitDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = (await getSession())!;

  const visit = await prisma.scribeVisit.findFirst({
    where: {
      id,
      ...tenantScope(session),
      deletedAt: null,
    },
    include: {
      patient: { select: { firstName: true, lastName: true, chartId: true } },
      specialty: { select: { displayName: true, slug: true, version: true } },
    },
  });
  if (!visit) notFound();

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <Link href="/visits" className="text-sm text-slate-400 hover:text-slate-200">
          ← Visits
        </Link>
      </div>
      <div>
        <h1 className="text-2xl font-semibold">
          {visit.patient.chartId ? `${visit.patient.chartId} · ` : ''}
          {visit.patient.lastName}, {visit.patient.firstName}
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          {visit.specialty.displayName} · {visit.mode.toLowerCase()} ·{' '}
          <span className="font-mono text-slate-300">{visit.status}</span>
        </p>
      </div>

      <div className="border border-slate-800 rounded-xl p-6 bg-slate-900/40 space-y-4">
        {visit.mode === 'BATCH' && (visit.status === 'DRAFT' || visit.status === 'UPLOADING') && (
          <Link
            href={`/visits/${visit.id}/upload`}
            className="inline-block px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-semibold"
          >
            Upload audio
          </Link>
        )}
        {visit.mode === 'LIVE' && (visit.status === 'DRAFT' || visit.status === 'RECORDING') && (
          <Link
            href={`/visits/${visit.id}/record`}
            className="inline-block px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-semibold"
          >
            {visit.status === 'RECORDING' ? 'Resume recording' : 'Start recording'}
          </Link>
        )}
        {visit.status === 'PROCESSING' && (
          <div className="text-sm text-slate-300">
            Transcribing… refresh in a minute or two.
          </div>
        )}
        {visit.status === 'READY_FOR_REVIEW' && (
          <Link
            href={`/visits/${visit.id}/review`}
            className="inline-block px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-semibold"
          >
            Review SOAP note
          </Link>
        )}
        {visit.status === 'SIGNED' && (
          <div className="text-sm text-slate-300">
            Signed. SOAP note has been sent to MedDoc Pro.
          </div>
        )}
        {visit.status === 'ERROR' && (
          <div className="text-sm text-amber-300">
            Processing errored. Check the audit log or retry upload.
          </div>
        )}
        <p className="text-xs text-slate-500 pt-2 border-t border-slate-800">
          Visit ID: <span className="font-mono">{visit.id}</span> · Mode:{' '}
          <span className="font-mono">{visit.mode}</span>
        </p>
      </div>
    </div>
  );
}
