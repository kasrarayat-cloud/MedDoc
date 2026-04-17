import { notFound } from 'next/navigation';
import Link from 'next/link';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';
import UploadClient from './UploadClient';

export const dynamic = 'force-dynamic';

export default async function UploadPage({
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
      mode: true,
      status: true,
      patient: { select: { firstName: true, lastName: true, chartId: true } },
    },
  });
  if (!visit) notFound();

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <Link href={`/visits/${visit.id}`} className="text-sm text-slate-400 hover:text-slate-200">
          ← Visit
        </Link>
      </div>
      <div>
        <h1 className="text-2xl font-semibold">Upload audio</h1>
        <p className="text-sm text-slate-400 mt-1">
          {visit.patient.lastName}, {visit.patient.firstName}
          {visit.patient.chartId ? ` · ${visit.patient.chartId}` : ''}
        </p>
      </div>

      {visit.mode !== 'BATCH' ? (
        <div className="border border-amber-600/40 rounded-xl p-4 bg-amber-500/5 text-sm text-amber-200">
          This visit is live-recording mode. Upload is only for BATCH visits.
        </div>
      ) : visit.status === 'PROCESSING' || visit.status === 'READY_FOR_REVIEW' ? (
        <div className="border border-slate-700 rounded-xl p-4 bg-slate-900/50 text-sm">
          Audio already uploaded. <Link href={`/visits/${visit.id}`} className="text-blue-400">Back to visit</Link>.
        </div>
      ) : (
        <UploadClient visitId={visit.id} />
      )}
    </div>
  );
}
