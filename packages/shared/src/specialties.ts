// ============================================================================
// Single source of truth for the clinician specialty catalog.
// ----------------------------------------------------------------------------
// Consumed by:
//   - apps/transcribe-md/src/app/settings/profile-form.tsx
//   - apps/transcribe-md/src/app/visits/new/* (page + step-2 form)
//   - apps/transcribe-md/src/actions/{profile,visits}.ts (Zod input)
//   - apps/transcribe-md/src/app/api/visits/[id]/route.ts (Zod input)
//   - apps/transcribe-md/src/worker/prompts/specialty-guidance.ts
//     (templateId here MUST have a matching SPECIALTY_GUIDANCE entry
//     OR fall through to the generic prompt)
//   - apps/marketing/src/components/home/Specialties.tsx
//
// Adding a specialty: append a row, add the matching guidance text in
// the worker, ship in one PR. Removing one: drop the row, audit the
// users.specialty column for the value, write a migration if any rows
// hold it. The catalog drives Zod validation so unknown ids are
// rejected at the API edge — DB rows can only contain values that
// exist here.
// ============================================================================

export const SPECIALTIES = [
  { id: 'unspecified',     label: 'Unspecified',     templateId: 'generic' },
  { id: 'primary-care',    label: 'Primary Care',    templateId: 'primary-care' },
  { id: 'cardiology',      label: 'Cardiology',      templateId: 'cardiology' },
  { id: 'psychiatry',      label: 'Psychiatry',      templateId: 'psychiatry' },
  { id: 'pediatrics',      label: 'Pediatrics',      templateId: 'pediatrics' },
  { id: 'ob-gyn',          label: 'OB-GYN',          templateId: 'ob-gyn' },
  { id: 'dermatology',     label: 'Dermatology',     templateId: 'dermatology' },
  { id: 'orthopedics',     label: 'Orthopedics',     templateId: 'orthopedics' },
  { id: 'urgent-care',     label: 'Urgent Care',     templateId: 'urgent-care' },
  { id: 'pain-management', label: 'Pain Management', templateId: 'pain-management' },
  { id: 'weight-management', label: 'Weight Management', templateId: 'weight-management' },
  { id: 'bariatric-surgery', label: 'Bariatric Surgery', templateId: 'bariatric-surgery' },
  { id: 'vascular-surgery', label: 'Vascular Surgery', templateId: 'vascular-surgery' },
  // Ultrasound is an IMAGING-REPORT specialty, NOT a SOAP clinic visit: its
  // templateId routes L4 to the ultrasound report generator (Exam/Indication/
  // Technique/Comparison/Findings/Impression), not the SOAP scaffold. Kept in
  // the catalog so Zod accepts it; the PICKER only shows it when the
  // NEXT_PUBLIC_ULTRASOUND_SPECIALTY flag is on (default OFF — see
  // ultrasoundSpecialtyEnabled / visibleSpecialties below).
  { id: 'ultrasound', label: 'Ultrasound', templateId: 'ultrasound' },
] as const;

export type Specialty = (typeof SPECIALTIES)[number];
export type SpecialtyId = Specialty['id'];

/** Tuple form for `z.enum(SPECIALTY_IDS)`. */
export const SPECIALTY_IDS = SPECIALTIES.map((s) => s.id) as unknown as readonly [
  SpecialtyId,
  ...SpecialtyId[],
];

/** Visit-create flow requires the doctor to pick a real specialty.
 *  'unspecified' belongs in the Settings dropdown only — it's the
 *  "haven't set my profile yet" sentinel, not a clinical category. */
export const SPECIALTIES_FOR_VISIT_CREATE: readonly Specialty[] =
  SPECIALTIES.filter((s) => s.id !== 'unspecified');

// ── Ultrasound specialty flag (default OFF) ─────────────────────────────────
// Gates VISIBILITY of the Ultrasound option in the specialty pickers + the L4
// imaging-report routing. NEXT_PUBLIC_ so the same value is readable at build
// time in the frontend and at runtime in the worker. Default OFF: prod is
// byte-identical (Ultrasound is never offered and the report path never runs)
// until Kasra enables it. Rollback = unset the env var.
export const ULTRASOUND_SPECIALTY_FLAG = 'NEXT_PUBLIC_ULTRASOUND_SPECIALTY';
export function ultrasoundSpecialtyEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY === 'true';
}

/** Specialty ids that produce an IMAGING REPORT (not a SOAP clinic note).
 *  Drives the L4 report-type routing + the E/M suppression (an imaging report
 *  has no office-visit E/M level). */
export function isImagingReportSpecialty(id: string | null | undefined): boolean {
  return id === 'ultrasound';
}

/** DOES AN OFFICE-VISIT E/M LEVEL APPLY TO THIS VISIT AT ALL?
 *
 *  THE ONE SWITCH. `!(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(x))`
 *  had been open-coded in seven places — the page, the sign route, two E/M
 *  routes, two server actions and an L4 worker layer. Seven copies of a
 *  conjunction is seven chances for one of them to be spelled differently, and
 *  that is not hypothetical here: the ORIGINAL bug in this area was one call
 *  site passing `specialtyLabel(...)` ('Ultrasound') where the predicate wanted
 *  the id ('ultrasound'), which made the comparison silently and permanently
 *  false. Every ultrasound visit then computed and stored an office E/M level.
 *
 *  So: one named function, one meaning, and callers that read as the question
 *  they are actually asking.
 *
 *  ⚠️ TAKES THE SPECIALTY **ID**, never a display label. `findSpecialty('Ultrasound').id`
 *  is `'unspecified'` — quietly the wrong specialty, no throw. If you have a
 *  label, canonicalise it first.
 *
 *  Enforced at THREE layers, because a data invariant needs to hold wherever the
 *  column is read, not only where it is written:
 *    COMPUTE — the page skips scoring (`emNotApplicable`)
 *    STORE   — `seedEmBaselineIfUnset` takes `applies` as a required param
 *    EXPORT  — the projection returns null (`projectDisplayedEmCode`)
 *  The export layer was the gap: a row that had ALREADY acquired an `em` blob
 *  printed an office code on an ultrasound report regardless of specialty. */
export function emAppliesToSpecialty(id: string | null | undefined): boolean {
  return !(ultrasoundSpecialtyEnabled() && isImagingReportSpecialty(id));
}

/** Catalog filtered for the pickers: hides flag-gated specialties (Ultrasound)
 *  unless their flag is on. `forVisitCreate` additionally drops 'unspecified'.
 *  When the flag is OFF this returns exactly the pre-ultrasound list. */
export function visibleSpecialties(opts?: {
  forVisitCreate?: boolean;
}): readonly Specialty[] {
  const usOn = ultrasoundSpecialtyEnabled();
  return (opts?.forVisitCreate ? SPECIALTIES_FOR_VISIT_CREATE : SPECIALTIES).filter(
    (s) => (s.id === 'ultrasound' ? usOn : true)
  );
}

/** Pre-catalog DB rows used display names ('Cardiology', 'Primary
 *  Care / Family Medicine') in transcribe_visits.specialty and a
 *  smaller set of lowercase ids ('pain', 'ortho', 'primary') in
 *  users.specialty. Map them onto the canonical catalog so the UI
 *  doesn't render "Unspecified" for a visit whose old value lost
 *  meaning to the schema. New writes always use canonical ids; this
 *  table only matters until the one-time migration normalizes the
 *  rows in place. */
const LEGACY_TO_ID: Record<string, SpecialtyId> = {
  // transcribe_visits display names
  'Cardiology': 'cardiology',
  'Orthopedics': 'orthopedics',
  'Pediatrics': 'pediatrics',
  'Psychiatry': 'psychiatry',
  'Dermatology': 'dermatology',
  'Primary Care / Family Medicine': 'primary-care',
  'Primary Care': 'primary-care',
  'Internal Medicine': 'primary-care',
  'Urgent Care': 'urgent-care',
  'Pain Management': 'pain-management',
  'OB-Gyn': 'ob-gyn',
  'OB/Gyn': 'ob-gyn',
  'Obstetrics & Gynecology': 'ob-gyn',
  'Obstetrics-Gynecology': 'ob-gyn',
  // users.specialty old short ids
  pain: 'pain-management',
  ortho: 'orthopedics',
  primary: 'primary-care',
  pulmonology: 'unspecified',
  ophthalmology: 'unspecified',
  'internal-medicine': 'primary-care',
  // 'ob-gyn' is the canonical id post Q1 #9; no legacy mapping needed.
  obstetrics: 'ob-gyn',
  gynecology: 'ob-gyn',
  'obstetrics-gynecology': 'ob-gyn',
};

/** Look up the catalog entry by id, with legacy-value fallback.
 *  Returns 'unspecified' for any id we can't resolve so callers
 *  always get a usable label/template reference. Zod rejects unknown
 *  ids at the API edge — this fallback exists for legacy DB rows. */
export function findSpecialty(id: string | null | undefined): Specialty {
  if (!id) return SPECIALTIES[0];
  const direct = SPECIALTIES.find((s) => s.id === id);
  if (direct) return direct;
  const legacy = LEGACY_TO_ID[id];
  if (legacy) return SPECIALTIES.find((s) => s.id === legacy)!;
  return SPECIALTIES[0];
}
