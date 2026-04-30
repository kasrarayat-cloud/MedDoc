// ============================================================================
// Specialty → Clinician avatar tone (pure derivation, UI-only).
// ----------------------------------------------------------------------------
// Phase 3 Wave 2 (dashboard density). The mockup picks a deterministic
// avatar tint per specialty so the patient list reads like a coherent
// schedule rather than a randomized rainbow:
//
//   Cardiology     → coral
//   Pediatrics     → teal
//   Primary Care   → sage   (covers "internal-medicine", "family medicine")
//   Dermatology    → amber
//   Ortho          → sky
//   OB-GYN         → coral
//   Psychiatry     → teal
//
// Anything else falls back to a name-hashed tone so brand-new specialty
// strings still render with stable, recognisable colors.
//
// Lives in `lib/` because it is a pure UI helper — no Prisma imports,
// no `'use server'`, no business logic. Per PROTECTED_CONTRACTS.md §8,
// the protected-zone covers files that touch Prisma / Redis / MinIO /
// auth / email / queue / audit / rate-limit / EHR formatters / visit
// exports / edit tracking / code generators. Pure-derive helpers are
// the explicit safe bucket alongside `cn.ts`, `format-time.ts`,
// `dob.ts`, `specialties.ts`, `shortcuts.ts`, etc.
// ============================================================================

export type ClinicianAvatarTone = 'sage' | 'teal' | 'amber' | 'coral' | 'sky';

const TONES: readonly ClinicianAvatarTone[] = [
  'sage',
  'teal',
  'amber',
  'coral',
  'sky',
] as const;

/** Deterministic specialty → avatar tone mapping. Keys are normalised
 *  (lowercased + trimmed + non-alphanumerics → '') so the same logical
 *  specialty resolves consistently whether the upstream value reads
 *  "Cardiology", "cardiology", "CARDIOLOGY", or "cardio".
 */
const SPECIALTY_TONES: Record<string, ClinicianAvatarTone> = {
  // Cardiology family
  cardiology: 'coral',
  cardio: 'coral',
  cardiologist: 'coral',

  // Primary care family — sage matches "calm + steady" mockup pairing
  primarycare: 'sage',
  primary: 'sage',
  family: 'sage',
  familymedicine: 'sage',
  internalmedicine: 'sage',
  internal: 'sage',
  generalpractice: 'sage',
  gp: 'sage',

  // Pediatrics — teal in the mockup
  pediatrics: 'teal',
  pediatric: 'teal',
  peds: 'teal',

  // Dermatology — amber
  dermatology: 'amber',
  dermatologist: 'amber',
  derm: 'amber',

  // Ortho — sky
  orthopedics: 'sky',
  orthopaedics: 'sky',
  orthopedic: 'sky',
  ortho: 'sky',

  // OB-GYN — coral
  obgyn: 'coral',
  obstetrics: 'coral',
  gynecology: 'coral',
  obstetricsgynecology: 'coral',

  // Psychiatry — teal
  psychiatry: 'teal',
  psych: 'teal',

  // Other specialties present in the spec-chip catalog
  pulmonology: 'sky',
  ophthalmology: 'amber',
  pain: 'coral',
};

function normaliseSpecialty(raw: string | null | undefined): string {
  if (!raw) return '';
  return raw.toLowerCase().replace(/[^a-z0-9]/g, '');
}

/** Pick a stable Clinician avatar tone given a specialty string. Falls
 *  back to a name-hashed tone when the specialty is unknown so every
 *  patient still gets a deterministic tint. The fallback is keyed on
 *  the (specialty, name) pair when both are provided so two patients
 *  in the same unknown specialty don't all collapse to the same tone.
 */
export function clinicianToneForSpecialty(
  specialty: string | null | undefined,
  fallbackKey: string | null | undefined = null
): ClinicianAvatarTone {
  const norm = normaliseSpecialty(specialty);
  if (norm && SPECIALTY_TONES[norm]) {
    return SPECIALTY_TONES[norm]!;
  }
  // Stable hash on whichever signal we have. If neither, default to
  // sage (the "primary care" tone) — the calmest of the five.
  const key = `${norm}:${fallbackKey ?? ''}`;
  if (!key.replace(/:/g, '')) return 'sage';
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  }
  return TONES[hash % TONES.length]!;
}

/** Two-letter initials for the avatar pill. Empty input → '?'. */
export function clinicianInitials(name: string | null | undefined): string {
  if (!name) return '?';
  const out = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0] ?? '')
    .join('')
    .toUpperCase();
  return out || '?';
}
