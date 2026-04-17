import Link from 'next/link';
import { notFound } from 'next/navigation';
import prisma from '@meddoc/db';
import { SoapNoteSchema, type SoapNote } from '@meddoc/types';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';
import ReviewClient from './ReviewClient';

export const dynamic = 'force-dynamic';

export default async function ReviewPage({
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
      status: true,
      patient: { select: { firstName: true, lastName: true, chartId: true } },
      specialty: { select: { displayName: true, version: true } },
    },
  });
  if (!visit) notFound();

  const output = await prisma.scribeOutput.findFirst({
    where: { visitId: visit.id, type: 'SOAP' },
    orderBy: { createdAt: 'desc' },
  });

  if (visit.status === 'SIGNED') {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Link href={`/visits/${visit.id}`} className="text-sm text-slate-400 hover:text-slate-200">
          ← Visit
        </Link>
        <div className="border border-slate-700 rounded-xl p-6 bg-slate-900/50 text-sm">
          This visit has been signed and sent to MedDoc Pro. SOAP is now a clinical
          note on the patient chart.
        </div>
      </div>
    );
  }

  if (!output) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Link href={`/visits/${visit.id}`} className="text-sm text-slate-400 hover:text-slate-200">
          ← Visit
        </Link>
        <div className="border border-amber-600/40 rounded-xl p-4 bg-amber-500/5 text-sm text-amber-200">
          No SOAP output yet. Transcription may still be running, or the
          pipeline errored — check the visit page.
        </div>
      </div>
    );
  }

  const soap = SoapNoteSchema.parse(output.content) as SoapNote;

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <Link href={`/visits/${visit.id}`} className="text-sm text-slate-400 hover:text-slate-200">
            ← Visit
          </Link>
          <h1 className="text-2xl font-semibold mt-1">
            {visit.patient.chartId ? `${visit.patient.chartId} · ` : ''}
            {visit.patient.lastName}, {visit.patient.firstName}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {visit.specialty.displayName} v{visit.specialty.version} · SOAP review
          </p>
        </div>
      </div>

      <ReviewClient
        visitId={visit.id}
        initial={soap}
        canSign={visit.status === 'READY_FOR_REVIEW'}
      />
    </div>
  );
}
