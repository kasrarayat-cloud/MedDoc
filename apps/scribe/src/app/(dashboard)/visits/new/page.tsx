import prisma from '@meddoc/db';
import { getSession } from '@/lib/auth';
import { patientAccessWhere } from '@meddoc/auth';
import { createVisitAction } from './actions';

// New-visit form. Three choices: patient (scoped by practice + role),
// specialty (global active list — Primary Care only in M1), mode
// (LIVE vs BATCH). Submit creates a DRAFT ScribeVisit and redirects
// to the detail page (placeholder in M1).
export default async function NewVisitPage() {
  const session = (await getSession())!;

  const [patients, specialties] = await Promise.all([
    prisma.patient.findMany({
      where: patientAccessWhere(session),
      select: { id: true, firstName: true, lastName: true, chartId: true },
      orderBy: [{ lastName: 'asc' }, { firstName: 'asc' }],
      take: 200,
    }),
    prisma.scribeSpecialtyTemplate.findMany({
      where: { active: true },
      select: { id: true, displayName: true, slug: true, version: true },
      orderBy: { displayName: 'asc' },
    }),
  ]);

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">New visit</h1>
        <p className="text-sm text-slate-400 mt-1">
          Pick the patient, specialty, and recording mode. You&apos;ll start the
          recording or upload the audio on the next screen.
        </p>
      </div>

      <form action={createVisitAction} className="space-y-5">
        <label className="block">
          <span className="text-sm font-medium">Patient</span>
          <select
            name="patientId"
            required
            defaultValue=""
            className="mt-1 w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2"
          >
            <option value="" disabled>
              Select a patient…
            </option>
            {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
            {patients.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.chartId ? `${p.chartId} · ` : ''}
                {p.lastName}, {p.firstName}
              </option>
            ))}
          </select>
          {patients.length === 0 && (
            <span className="text-xs text-amber-400 mt-1 block">
              No patients visible to your account. Create one in MedDoc Pro first.
            </span>
          )}
        </label>

        <label className="block">
          <span className="text-sm font-medium">Specialty</span>
          <select
            name="specialtyId"
            required
            defaultValue={specialties[0]?.id ?? ''}
            className="mt-1 w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2"
          >
            {specialties.length === 0 ? (
              <option value="" disabled>
                No specialties seeded — run npm run seed:specialties
              </option>
            ) : (
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              specialties.map((s: any) => (
                <option key={s.id} value={s.id}>
                  {s.displayName} (v{s.version})
                </option>
              ))
            )}
          </select>
        </label>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Mode</legend>
          <label className="flex items-start gap-3 border border-slate-700 rounded-lg p-3 cursor-pointer hover:border-slate-500">
            <input type="radio" name="mode" value="LIVE" defaultChecked className="mt-1" />
            <div>
              <div className="font-medium">Live recording</div>
              <div className="text-xs text-slate-400">
                Record the visit in real time and get a streaming transcript.
              </div>
            </div>
          </label>
          <label className="flex items-start gap-3 border border-slate-700 rounded-lg p-3 cursor-pointer hover:border-slate-500">
            <input type="radio" name="mode" value="BATCH" className="mt-1" />
            <div>
              <div className="font-medium">Upload a recording</div>
              <div className="text-xs text-slate-400">
                Drag in an mp3/m4a/wav file — up to 2 hours per visit.
              </div>
            </div>
          </label>
        </fieldset>

        <button
          type="submit"
          disabled={patients.length === 0 || specialties.length === 0}
          className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-sm font-semibold"
        >
          Create visit
        </button>
      </form>
    </div>
  );
}
