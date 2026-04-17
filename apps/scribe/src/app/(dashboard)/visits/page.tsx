import Link from 'next/link';
import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';

// Visit list. In M1 this is nearly always an empty-state screen until
// the first row is created via /visits/new. Scoped by practice — a
// clinic only sees its own visits. Soft-deleted rows are excluded.
export default async function VisitsPage() {
  const session = (await getSession())!; // layout already enforced

  const visits = await prisma.scribeVisit.findMany({
    where: {
      ...tenantScope(session),
      deletedAt: null,
    },
    include: {
      patient: { select: { firstName: true, lastName: true, chartId: true } },
      specialty: { select: { displayName: true, slug: true } },
      user: { select: { name: true } },
    },
    orderBy: { createdAt: 'desc' },
    take: 50,
  });

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Visits</h1>
          <p className="text-sm text-slate-400 mt-1">
            Record a live visit or upload an existing recording for transcription.
          </p>
        </div>
        <Link
          href="/visits/new"
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-semibold"
        >
          New visit
        </Link>
      </div>

      {visits.length === 0 ? (
        <div className="border border-dashed border-slate-700 rounded-xl p-12 text-center">
          <p className="text-slate-300 font-medium">No visits yet</p>
          <p className="text-sm text-slate-500 mt-2">
            Create one with <span className="text-slate-300">New visit</span> above.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-slate-800 border border-slate-800 rounded-xl overflow-hidden">
          {/* `prisma` is typed `any` in @meddoc/db (see M0 notes); annotate
              inline to keep implicit-any off. Shape matches the select above. */}
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {visits.map((v: any) => (
            <li key={v.id} className="px-4 py-3 flex items-center justify-between hover:bg-slate-900/50">
              <div className="flex items-center gap-4">
                <span
                  className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800"
                  title={v.status}
                >
                  {v.status}
                </span>
                <span className="font-medium">
                  {v.patient.chartId ? `${v.patient.chartId} · ` : ''}
                  {v.patient.lastName}, {v.patient.firstName}
                </span>
                <span className="text-sm text-slate-400">
                  {v.specialty.displayName} · {v.mode.toLowerCase()}
                </span>
              </div>
              <span className="text-xs text-slate-500">
                {new Date(v.createdAt).toLocaleDateString()}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
