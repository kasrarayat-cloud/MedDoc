// ============================================================================
// Patient form — shared shape between Add and Edit modals
// ----------------------------------------------------------------------------
// Both modals hit the same Patient row, but each had its own FormState
// interface. That drift caused real bugs: a field added to Add Patient
// without a matching update to Edit Patient would silently ship. Each
// modal still has its own form state (they differ on a few fields —
// Add has initialHistory + chartId, Edit has briefHistory + status), but
// the PROFILE subset — everything that's a 1:1 column on the Patient
// row — is modeled here so a schema expansion only needs to touch ONE
// type and all call sites break until they handle it.
//
// Rule: if you add a column to `Patient` that the doctor should be able
// to edit, add it here first. Typescript will then flag every modal /
// payload builder / extractor that hasn't been updated.
// ============================================================================

import type { PatientView } from '@/lib/data/patients';

export type PatientSex = 'UNKNOWN' | 'MALE' | 'FEMALE' | 'OTHER';

/**
 * Fields both Add and Edit capture. String-typed (form-state shape) —
 * the payload builder converts to the right types for the server action.
 *
 * NOT included here: chartId (Add-only, Edit treats it as immutable via
 * the non-null unique constraint), initialHistory / briefHistory (each
 * modal handles its own flavor), status (Edit-only), assignedDoctorId
 * (both capture it but with different "touched"/"preserve current"
 * semantics — treated as local state per modal).
 */
export interface PatientProfileFormState {
  firstName: string;
  lastName: string;
  mrn: string;
  /** Practice-internal chart ID. Unique per practice (DB constraint).
   *  On Add, leaving blank triggers auto-assignment of C-<n>. On Edit,
   *  blank means "clear the chart ID" — rare but allowed. */
  chartId: string;
  birthYear: string;
  email: string;
  phoneLast4: string;
  cellPhone: string;
  homePhone: string;
  insuranceVerified: boolean;
  sex: PatientSex;
  addressLine1: string;
  addressLine2: string;
  city: string;
  state: string;
  postalCode: string;
  pharmacyName: string;
  pharmacyPhone: string;
  tags: string;
}

/** Fresh empty state — for Add Patient's initial mount. */
export function emptyPatientProfile(): PatientProfileFormState {
  return {
    firstName: '',
    lastName: '',
    mrn: '',
    chartId: '',
    birthYear: '',
    email: '',
    phoneLast4: '',
    cellPhone: '',
    homePhone: '',
    insuranceVerified: false,
    sex: 'UNKNOWN',
    addressLine1: '',
    addressLine2: '',
    city: '',
    state: '',
    postalCode: '',
    pharmacyName: '',
    pharmacyPhone: '',
    tags: '',
  };
}

/** Seed the Edit modal's form from an existing PatientView. */
export function patientViewToProfile(p: PatientView): PatientProfileFormState {
  return {
    firstName: p.firstName,
    lastName: p.lastName,
    mrn: p.mrn ?? '',
    chartId: p.chartId ?? '',
    birthYear: p.birthYear ? String(p.birthYear) : '',
    email: p.email ?? '',
    phoneLast4: p.phoneLast4 ?? '',
    cellPhone: p.cellPhone ?? '',
    homePhone: p.homePhone ?? '',
    insuranceVerified: p.insuranceVerified ?? false,
    sex: p.sex ?? 'UNKNOWN',
    addressLine1: p.addressLine1 ?? '',
    addressLine2: p.addressLine2 ?? '',
    city: p.city ?? '',
    state: p.state ?? '',
    postalCode: p.postalCode ?? '',
    pharmacyName: p.pharmacyName ?? '',
    pharmacyPhone: p.pharmacyPhone ?? '',
    tags: p.tags.join(', '),
  };
}

/** Shape the server action expects for the profile-subset of fields. */
export interface PatientProfilePayload {
  firstName: string;
  lastName: string;
  mrn: string | null;
  chartId: string | null;
  birthYear: number | null;
  email: string | null;
  phoneLast4: string | null;
  cellPhone: string | null;
  homePhone: string | null;
  insuranceVerified: boolean;
  sex: PatientSex | null;
  addressLine1: string | null;
  addressLine2: string | null;
  city: string | null;
  state: string | null;
  postalCode: string | null;
  pharmacyName: string | null;
  pharmacyPhone: string | null;
  tags: string[];
}

/**
 * Convert form state → action payload. Identical rules for Add and Edit:
 * trim strings, empty → null, UNKNOWN sex → null (server treats it as
 * "clear to default"), tags split on commas, state uppercased.
 */
export function profileToPayload(
  form: PatientProfileFormState
): PatientProfilePayload {
  return {
    firstName: form.firstName.trim(),
    lastName: form.lastName.trim(),
    mrn: form.mrn.trim() || null,
    chartId: form.chartId.trim() || null,
    birthYear: form.birthYear ? parseInt(form.birthYear, 10) : null,
    email: form.email.trim() || null,
    phoneLast4: form.phoneLast4.trim() || null,
    cellPhone: form.cellPhone.trim() || null,
    homePhone: form.homePhone.trim() || null,
    insuranceVerified: form.insuranceVerified,
    sex: form.sex === 'UNKNOWN' ? null : form.sex,
    addressLine1: form.addressLine1.trim() || null,
    addressLine2: form.addressLine2.trim() || null,
    city: form.city.trim() || null,
    state: form.state.trim().toUpperCase() || null,
    postalCode: form.postalCode.trim() || null,
    pharmacyName: form.pharmacyName.trim() || null,
    pharmacyPhone: form.pharmacyPhone.trim() || null,
    tags: form.tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean),
  };
}
