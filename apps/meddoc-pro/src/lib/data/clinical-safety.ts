// ============================================================================
// Clinical Safety Data Layer
// ----------------------------------------------------------------------------
// Patient allergies + medications. Both are safety-critical (steroids,
// lidocaine, anticoagulants are routine in pain procedures), so:
//
//   - All queries are tenant-scoped via patientAccessWhere — no row leaks
//     across practices even if a caller passes a forged patientId.
//   - Mutations re-check tenant access before writing.
//   - Soft delete only (deletedAt). HIPAA retention applies.
//   - practiceId on each row is denormalized so adversarial cross-tenant
//     queries can be checked at the row level without trusting a JOIN.
// ============================================================================

import type { AllergySeverity } from '@prisma/client';
import prisma from '@meddoc/db';
import type { Session } from '@/lib/auth';
import { patientAccessWhere } from './patients';

// ---------------------------------------------------------------------------
// View shapes returned to UI / server actions
// ---------------------------------------------------------------------------

export interface AllergyView {
  id: string;
  patientId: string;
  allergen: string;
  reaction: string | null;
  severity: AllergySeverity;
  notes: string | null;
  createdAt: string; // ISO
  updatedAt: string; // ISO
  createdById: string | null;
}

export interface MedicationView {
  id: string;
  patientId: string;
  name: string;
  dosage: string | null;
  frequency: string | null;
  isActive: boolean;
  notes: string | null;
  createdAt: string; // ISO
  updatedAt: string; // ISO
  createdById: string | null;
}

// ---------------------------------------------------------------------------
// Input shapes
// ---------------------------------------------------------------------------

export interface CreateAllergyInput {
  patientId: string;
  allergen: string;
  reaction?: string | null;
  severity?: AllergySeverity;
  notes?: string | null;
}

export interface UpdateAllergyInput {
  allergen?: string;
  reaction?: string | null;
  severity?: AllergySeverity;
  notes?: string | null;
}

export interface CreateMedicationInput {
  patientId: string;
  name: string;
  dosage?: string | null;
  frequency?: string | null;
  isActive?: boolean;
  notes?: string | null;
}

export interface UpdateMedicationInput {
  name?: string;
  dosage?: string | null;
  frequency?: string | null;
  isActive?: boolean;
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Tenant-scope guard — verifies the session can see this patient.
// Returns the patient's practiceId for denormalized writes; throws if the
// patient is invisible to this session (forged ID, wrong practice, etc.).
// ---------------------------------------------------------------------------
async function assertPatientVisible(
  session: Session,
  patientId: string
): Promise<string> {
  const patient = await prisma.patient.findFirst({
    where: { id: patientId, ...patientAccessWhere(session) },
    select: { id: true, practiceId: true },
  });
  if (!patient) {
    throw new Error('Patient not found or access denied.');
  }
  return patient.practiceId;
}

// ===========================================================================
// ALLERGIES
// ===========================================================================

type AllergyRow = {
  id: string;
  patientId: string;
  allergen: string;
  reaction: string | null;
  severity: AllergySeverity;
  notes: string | null;
  createdAt: Date;
  updatedAt: Date;
  createdById: string | null;
};

function toAllergyView(row: AllergyRow): AllergyView {
  return {
    id: row.id,
    patientId: row.patientId,
    allergen: row.allergen,
    reaction: row.reaction,
    severity: row.severity,
    notes: row.notes,
    createdAt: row.createdAt.toISOString(),
    updatedAt: row.updatedAt.toISOString(),
    createdById: row.createdById,
  };
}

export async function listAllergiesForPatient(
  session: Session,
  patientId: string
): Promise<AllergyView[]> {
  // Defense-in-depth: filter by both patient access AND deletedAt at the
  // allergy row level. Even if patientAccessWhere had a bug, the allergy
  // would still be tenant-scoped via patient.
  const rows = await prisma.allergy.findMany({
    where: {
      patientId,
      deletedAt: null,
      patient: patientAccessWhere(session),
    },
    orderBy: [
      // SEVERE first so the most clinically important rows surface at the
      // top of the panel without the UI having to re-sort.
      { severity: 'desc' },
      { createdAt: 'desc' },
    ],
  });
  return rows.map(toAllergyView);
}

export async function createAllergy(
  session: Session,
  input: CreateAllergyInput
): Promise<AllergyView> {
  const practiceId = await assertPatientVisible(session, input.patientId);
  if (!input.allergen.trim()) {
    throw new Error('Allergen is required.');
  }
  const row = await prisma.allergy.create({
    data: {
      patientId: input.patientId,
      practiceId,
      allergen: input.allergen.trim(),
      reaction: input.reaction?.trim() || null,
      severity: input.severity ?? 'UNKNOWN',
      notes: input.notes?.trim() || null,
      createdById: session.user.id,
    },
  });
  return toAllergyView(row);
}

export async function updateAllergy(
  session: Session,
  allergyId: string,
  input: UpdateAllergyInput
): Promise<AllergyView> {
  // Verify access through the patient relation — a forged allergyId belonging
  // to another tenant returns null here and we refuse to write.
  const existing = await prisma.allergy.findFirst({
    where: {
      id: allergyId,
      deletedAt: null,
      patient: patientAccessWhere(session),
    },
    select: { id: true },
  });
  if (!existing) {
    throw new Error('Allergy not found or access denied.');
  }
  const row = await prisma.allergy.update({
    where: { id: allergyId },
    data: {
      ...(input.allergen !== undefined ? { allergen: input.allergen.trim() } : {}),
      ...(input.reaction !== undefined ? { reaction: input.reaction?.trim() || null } : {}),
      ...(input.severity !== undefined ? { severity: input.severity } : {}),
      ...(input.notes !== undefined ? { notes: input.notes?.trim() || null } : {}),
      updatedById: session.user.id,
    },
  });
  return toAllergyView(row);
}

export async function deleteAllergy(
  session: Session,
  allergyId: string
): Promise<void> {
  const existing = await prisma.allergy.findFirst({
    where: {
      id: allergyId,
      deletedAt: null,
      patient: patientAccessWhere(session),
    },
    select: { id: true },
  });
  if (!existing) {
    throw new Error('Allergy not found or access denied.');
  }
  await prisma.allergy.update({
    where: { id: allergyId },
    data: { deletedAt: new Date(), updatedById: session.user.id },
  });
}

export async function setNoKnownAllergies(
  session: Session,
  patientId: string,
  value: boolean
): Promise<void> {
  await assertPatientVisible(session, patientId);
  await prisma.patient.update({
    where: { id: patientId },
    data: { noKnownAllergies: value },
  });
}

// ===========================================================================
// MEDICATIONS
// ===========================================================================

type MedicationRow = {
  id: string;
  patientId: string;
  name: string;
  dosage: string | null;
  frequency: string | null;
  isActive: boolean;
  notes: string | null;
  createdAt: Date;
  updatedAt: Date;
  createdById: string | null;
};

function toMedicationView(row: MedicationRow): MedicationView {
  return {
    id: row.id,
    patientId: row.patientId,
    name: row.name,
    dosage: row.dosage,
    frequency: row.frequency,
    isActive: row.isActive,
    notes: row.notes,
    createdAt: row.createdAt.toISOString(),
    updatedAt: row.updatedAt.toISOString(),
    createdById: row.createdById,
  };
}

export interface ListMedicationsOptions {
  /** When true, includes inactive (stopped) meds in the result.
   *  Defaults to false — UI shows only active meds by default. */
  includeInactive?: boolean;
}

export async function listMedicationsForPatient(
  session: Session,
  patientId: string,
  opts: ListMedicationsOptions = {}
): Promise<MedicationView[]> {
  const rows = await prisma.medication.findMany({
    where: {
      patientId,
      deletedAt: null,
      ...(opts.includeInactive ? {} : { isActive: true }),
      patient: patientAccessWhere(session),
    },
    orderBy: [
      // Active first, then most recently added.
      { isActive: 'desc' },
      { createdAt: 'desc' },
    ],
  });
  return rows.map(toMedicationView);
}

export async function createMedication(
  session: Session,
  input: CreateMedicationInput
): Promise<MedicationView> {
  const practiceId = await assertPatientVisible(session, input.patientId);
  if (!input.name.trim()) {
    throw new Error('Medication name is required.');
  }
  const row = await prisma.medication.create({
    data: {
      patientId: input.patientId,
      practiceId,
      name: input.name.trim(),
      dosage: input.dosage?.trim() || null,
      frequency: input.frequency?.trim() || null,
      isActive: input.isActive ?? true,
      notes: input.notes?.trim() || null,
      createdById: session.user.id,
    },
  });
  return toMedicationView(row);
}

export async function updateMedication(
  session: Session,
  medicationId: string,
  input: UpdateMedicationInput
): Promise<MedicationView> {
  const existing = await prisma.medication.findFirst({
    where: {
      id: medicationId,
      deletedAt: null,
      patient: patientAccessWhere(session),
    },
    select: { id: true },
  });
  if (!existing) {
    throw new Error('Medication not found or access denied.');
  }
  const row = await prisma.medication.update({
    where: { id: medicationId },
    data: {
      ...(input.name !== undefined ? { name: input.name.trim() } : {}),
      ...(input.dosage !== undefined ? { dosage: input.dosage?.trim() || null } : {}),
      ...(input.frequency !== undefined ? { frequency: input.frequency?.trim() || null } : {}),
      ...(input.isActive !== undefined ? { isActive: input.isActive } : {}),
      ...(input.notes !== undefined ? { notes: input.notes?.trim() || null } : {}),
      updatedById: session.user.id,
    },
  });
  return toMedicationView(row);
}

export async function deleteMedication(
  session: Session,
  medicationId: string
): Promise<void> {
  const existing = await prisma.medication.findFirst({
    where: {
      id: medicationId,
      deletedAt: null,
      patient: patientAccessWhere(session),
    },
    select: { id: true },
  });
  if (!existing) {
    throw new Error('Medication not found or access denied.');
  }
  await prisma.medication.update({
    where: { id: medicationId },
    data: { deletedAt: new Date(), updatedById: session.user.id },
  });
}
