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

      <div className="border border-slate-800 rounded-xl p-6 bg-slate-900/40">
        <h2 className="font-medium">What happens here</h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-300 list-disc list-inside">
          <li>Live recording (mic + streaming transcript) — shipping in Milestone 3.</li>
          <li>Audio upload (drag-drop mp3/m4a/wav) — shipping in Milestone 2.</li>
          <li>Review of SOAP / ICD-10 / Rx / referrals / patient summary — Milestone 4.</li>
        </ul>
        <p className="mt-4 text-xs text-slate-500">
          Visit ID: <span className="font-mono">{visit.id}</span>
        </p>
      </div>
    </div>
  );
}
