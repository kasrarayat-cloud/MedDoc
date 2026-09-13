// ============================================================================
// /visits/new — Linear V1 shell.
// ----------------------------------------------------------------------------
// The underlying flow (PatientPicker → VisitFormStep2 → createVisitAction)
// is preserved end-to-end. Step state is driven by the selected patient
// (absent → step 1, present → step 2).
// ============================================================================

import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

import prisma from '@meddoc/db';
import { visitScope } from '@/lib/practice-scope';
import { getSession } from '@/lib/auth';
import { isSkinBeta } from '@/config/skin-beta';
import { AppFrame } from '@/components/ui/app-frame';
import { Ic } from '@/components/ui/icon';
import { PageHeader } from '@/components/ui/page-header';
import { visibleSpecialties, findSpecialty } from '@meddoc/shared/specialties';
import { displacedByReupload } from '@/lib/template-picker-dedupe';
import { NewVisitClient } from './new-visit-client';
import { NewVisitClientC3 } from './new-visit-client-c3';
import type { SelectedPatient } from './patient-types';

export const metadata: Metadata = { title: 'New visit' };

type SearchParams = Record<string, string | string[] | undefined>;

export default async function NewVisitPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const session = await getSession();
  if (!session) redirect('/login');

  type MinimalUser = {
    name: string | null;
    email: string;
    practiceId: string;
  };
  type MinimalVisit = { specialty: string } | null;

  const [user, mostRecentVisit] = (await Promise.all([
    prisma.user.findUnique({
      where: { id: session.user.id },
      select: { name: true, email: true, practiceId: true },
    }),
    prisma.transcribeVisit.findFirst({
      where: {
        ...visitScope(session.user.practiceId),
        // ⚠️ THE AUTHOR CONJUNCT STAYS HERE, AND IT IS NOT AN OVERSIGHT.
        // This read prefills the new-visit form with the specialty the CALLER
        // last worked in. Its subject is the user, like the personal data
        // export — widening it would prefill a doctor's form from a colleague's
        // last visit, which is a worse product, not a wider permission.
        //
        // §4.1c retires the conjuncts that gate ACTIONS. This gates a default.
        userId: session.user.id,
        deletedAt: null,
        archivedAt: null,
      },
      orderBy: { createdAt: 'desc' },
      select: { specialty: true },
    }),
  ])) as [MinimalUser | null, MinimalVisit];
  if (!user) redirect('/login');

  const params = await searchParams;
  const patientIdParam = Array.isArray(params.patientId)
    ? params.patientId[0]
    : params.patientId;

  let initialPatient: SelectedPatient | null = null;
  if (patientIdParam) {
    type PatientRow = {
      id: string;
      practiceId: string;
      name: string;
      dateOfBirth: Date | null;
      externalId: string | null;
      deletedAt: Date | null;
    };
    const patient: PatientRow | null = await prisma.transcribeMdPatient.findUnique({
      where: { id: patientIdParam },
      select: {
        id: true,
        practiceId: true,
        name: true,
        dateOfBirth: true,
        externalId: true,
        deletedAt: true,
      },
    });
    if (
      !patient ||
      patient.practiceId !== user.practiceId ||
      patient.deletedAt !== null
    ) {
      redirect('/visits/new');
    }
    initialPatient = {
      id: patient.id,
      name: patient.name,
      dateOfBirth: patient.dateOfBirth
        ? patient.dateOfBirth.toISOString().slice(0, 10)
        : null,
      externalId: patient.externalId,
    };
  }

  // Default to the doctor's most recent visit's specialty, normalized
  // through the legacy-value table so a row that still holds a display
  // name maps onto the canonical id the dropdown expects.
  // Flag-aware picker list: Ultrasound appears only when its flag is on
  // (default OFF → exactly the pre-ultrasound list).
  const pickerSpecialties = visibleSpecialties({ forVisitCreate: true });
  const defaultSpecialty = mostRecentVisit?.specialty
    ? findSpecialty(mostRecentVisit.specialty).id
    : pickerSpecialties[0].id;

  // TEMPLATE-CHOICE-1 (#318): the per-visit picker lists (a) the doctor's OWN
  // custom formats (active first, then drafts) AND (b) every CERTIFIED template
  // held by the PRACTICE — so a practice's several certified templates are all
  // choosable. The CERTIFIED filter is the SAME condition the worker + fill honour
  // (native-export/fill-engine require certificationStatus === 'CERTIFIED'), so the
  // list never offers a template the fill would then reject. Empty for the vast
  // majority (no custom or certified template) → the picker is not rendered and the
  // flow is unchanged.
  const noteFormats = (await prisma.noteTemplate.findMany({
    where: {
      isSystemDefault: false,
      OR: [
        { doctorId: session.user.id, status: { in: ['active', 'draft'] } },
        {
          practiceId: session.user.practiceId,
          templateTwinCompiledVersion: { is: { certificationStatus: 'CERTIFIED' } },
        },
      ],
    },
    select: {
      id: true,
      name: true,
      status: true,
      // doctorId + encounterType are the RE-UPLOAD DISPLACEMENT grouping key
      // (with name): same-name collapse only WITHIN one (doctor, encounter), so
      // two different doctors' — or one doctor's two encounters' — same-named
      // certified forms never collapse into one wrong offering.
      doctorId: true,
      encounterType: true,
      // Among a group, the most-recently-created survives unless the default is
      // present.
      createdAt: true,
      templateTwinCompiledVersion: { select: { certificationStatus: true } },
    },
    orderBy: [{ status: 'asc' }, { updatedAt: 'desc' }],
  })) as Array<{
    id: string;
    name: string;
    status: string;
    doctorId: string | null;
    encounterType: string | null;
    createdAt: Date;
    templateTwinCompiledVersion: { certificationStatus: string } | null;
  }>;
  // Dedupe by id (a doctor's own certified template can match both OR arms).
  const seenTemplate = new Set<string>();
  const deduped = noteFormats.filter((t) =>
    seenTemplate.has(t.id) ? false : (seenTemplate.add(t.id), true),
  );
  // The set of CERTIFIED template ids in scope — the only templates the fill will
  // honour. Arm A (the doctor's own rows) carries NO certification filter, so a
  // doctor's own row that was later DE-CERTIFIED (a mapping edit flips its compiled
  // version out of CERTIFIED without touching NoteTemplate.status) is still listed;
  // the default guard below must therefore check CERTIFICATION, not mere listing,
  // or it would pre-select a template the fill then rejects (adversarial F1).
  const certifiedIds = new Set<string>();
  for (const t of deduped) {
    if (t.templateTwinCompiledVersion?.certificationStatus === 'CERTIFIED') {
      certifiedIds.add(t.id);
    }
  }

  // The practice's DEFAULT template (TEMPLATE-CHOICE-1): pre-select it ONLY when
  // it is set AND still a CERTIFIED template in scope — the exact condition the
  // fill honours. A default that was retired or de-certified since it was set
  // degrades to '' (the per-doctor active-template fallback resolves at
  // generation), per the schema contract. Read BEFORE the displacement below so
  // the practice's explicit choice can protect its own row from being collapsed.
  const practice = await prisma.practice.findUnique({
    where: { id: session.user.practiceId },
    select: { defaultNoteTemplateId: true },
  });

  // ⚠️ RE-UPLOAD DISPLACEMENT (owner finding) — ONE CURRENT FORM PER NAME.
  //
  // A re-upload mints a NEW lineage (new id, SAME name) and certifies it, so the
  // practice's certified rows accumulate indistinguishable duplicates — two
  // "Gastroenterology Consultation" entries, and no way to tell which is current.
  // Offer the ONE the practice means: its default when that is among the
  // same-named group (never displace the explicit choice), else the
  // most-recently-created (the re-upload displaces the form it replaced). Drafts
  // and non-certified rows are untouched. Display-only and reversible — no
  // template row is edited or retired. See lib/template-picker-dedupe.
  const displacedTemplateIds = displacedByReupload(
    deduped.map((t) => ({
      id: t.id,
      doctorId: t.doctorId,
      encounterType: t.encounterType,
      name: t.name,
      status: t.status,
      createdAt: t.createdAt,
      certified:
        t.templateTwinCompiledVersion?.certificationStatus === 'CERTIFIED',
    })),
    practice?.defaultNoteTemplateId ?? null,
  );

  const templates = deduped
    .filter((t) => !displacedTemplateIds.has(t.id))
    .map((t) => ({ id: t.id, name: t.name, isActive: t.status === 'active' }));

  const defaultTemplateId =
    practice?.defaultNoteTemplateId &&
    certifiedIds.has(practice.defaultNoteTemplateId) &&
    // The default is never displaced (the survivor prefers it), but assert it:
    // a pre-selected id the list does not contain would be a phantom selection.
    !displacedTemplateIds.has(practice.defaultNoteTemplateId)
      ? practice.defaultNoteTemplateId
      : null;

  // \u2500\u2500 C3 calm "just start" create flow (flag-gated) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  // SKIN-ONLY: identical auth + patient-scope reads + defaultSpecialty above.
  // The 3-step stepper + side rail collapse to one calm card; the SAME
  // PatientPicker + VisitFormStep2 (createVisitAction) do the real work. Flag
  // OFF \u2192 the stepper below renders verbatim.
  if (isSkinBeta()) {
    return (
      <AppFrame>
        <div className="qm-rounds-host qm-c3-nv-top">
          <span className="qm-c3-nv-eyebrow">New visit</span>
          {/* R3.7 — `/board`, not `/dashboard`. R1 made `/dashboard` a config
              307 to `/board`, so this Cancel took the doctor through a redirect
              on every use. The destination is unchanged in intent; the hop is
              gone. */}
          <a href="/board" className="qm-lin-btn" style={{ textDecoration: 'none' }}>
            <Ic.close width={13} height={13} />
            Cancel
          </a>
        </div>
        <NewVisitClientC3
          initialPatient={initialPatient}
          specialties={pickerSpecialties}
          defaultSpecialty={defaultSpecialty}
          templates={templates}
          defaultTemplateId={defaultTemplateId ?? undefined}
        />
      </AppFrame>
    );
  }

  return (
    <AppFrame>
      <PageHeader
        eyebrow="New visit"
        title="Start a new visit"
        subtitle={
          initialPatient
            ? 'Pick a capture mode below and we\u2019ll take it from there.'
            : 'Pick the patient, then choose how you want to capture the encounter.'
        }
        actions={
          <a
            href="/dashboard"
            className="qm-lin-btn"
            style={{ textDecoration: 'none' }}
          >
            <Ic.close width={13} height={13} />
            Cancel
          </a>
        }
      />

      <div style={{ padding: '24px 24px 48px', maxWidth: 1280 }}>
        <NewVisitClient
          initialPatient={initialPatient}
          specialties={pickerSpecialties}
          defaultSpecialty={defaultSpecialty}
          templates={templates}
          defaultTemplateId={defaultTemplateId ?? undefined}
        />
      </div>
    </AppFrame>
  );
}
