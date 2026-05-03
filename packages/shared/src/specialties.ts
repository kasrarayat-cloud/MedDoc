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
  { id: 'dermatology',     label: 'Dermatology',     templateId: 'dermatology' },
  { id: 'orthopedics',     label: 'Orthopedics',     templateId: 'orthopedics' },
  { id: 'urgent-care',     label: 'Urgent Care',     templateId: 'urgent-care' },
  { id: 'pain-management', label: 'Pain Management', templateId: 'pain-management' },
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
  'OB-Gyn': 'unspecified',
  'Obstetrics & Gynecology': 'unspecified',
  // users.specialty old short ids
  pain: 'pain-management',
  ortho: 'orthopedics',
  primary: 'primary-care',
  pulmonology: 'unspecified',
  ophthalmology: 'unspecified',
  'internal-medicine': 'primary-care',
  'ob-gyn': 'unspecified',
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
