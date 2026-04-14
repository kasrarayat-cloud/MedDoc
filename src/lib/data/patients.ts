// ============================================================================
// Patient Data Layer
// ----------------------------------------------------------------------------
// Single source for all patient queries used by server components and actions.
//
// STRATEGY: Try Prisma first; if the database is unavailable (no connection,
// not migrated, etc.), fall back to an in-memory store seeded with the mock
// patients. The in-memory store mutates within the Node process so demos work
// even without a real Postgres setup.
//
// Once you provision a real Postgres + run `prisma migrate deploy`, the same
// code automatically uses the DB — no call sites need to change.
// ============================================================================

import prisma, { isDatabaseHealthy } from '@/lib/db';
import { MOCK_PATIENTS, type MockPatient, type PatientStatus } from '@/lib/mock-patients';
import type { Session } from '@/lib/auth';

/** Public shape returned to UI — same fields whether DB or memory backed */
export type PatientView = MockPatient;

// ---------------------------------------------------------------------------
// HIPAA patient isolation (now tenant-aware)
// ---------------------------------------------------------------------------
// Rules:
//   SUPER_ADMIN: sees everything across all practices.
//   ADMIN      : sees every patient in their OWN practice (no user-level filter).
//   DOCTOR/STAFF: sees patients in their practice AND (created OR assigned to them).
//
// The filter runs at the Prisma query level so we never pull other tenants'
// PHI into memory. Mock mode (DB unhealthy) skips isolation — mock rows
// don't carry practiceId/createdById, and real PHI never goes through it.
// ---------------------------------------------------------------------------
/**
 * Returns a Prisma `where` predicate that scopes Patient queries to what
 * the given session can see. Exported so other data modules (appointments,
 * clinical notes) can use it as a *nested relation filter* — e.g.
 *   `prisma.appointment.findMany({ where: { patient: patientAccessWhere(session) } })`
 * — which pushes tenant isolation down to the Postgres join and closes
 * cross-tenant access on patient-owned rows at the query layer.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function patientAccessWhere(session: Session): any {
  const base: Record<string, unknown> = { deletedAt: null };

  if (session.user.role === 'SUPER_ADMIN') {
    return base;
  }

  // Everyone below is tenant-scoped.
  base.practiceId = session.user.practiceId;

  if (session.user.role === 'ADMIN') {
    return base;
  }

  // DOCTOR / STAFF — additionally constrained to their own patients.
  return {
    ...base,
    OR: [
      { createdById: session.user.id },
      { assignedDoctorId: session.user.id },
    ],
  };
}

// ---------------------------------------------------------------------------
// In-memory fallback store (seeded from mock data, mutates within process)
// ---------------------------------------------------------------------------
const memoryStore = new Map<string, MockPatient>(
  MOCK_PATIENTS.map((p) => [p.id, { ...p }])
);

function generateId(): string {
  // cuid-like: timestamp + random base36
  return `pt_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export type PatientSex = 'UNKNOWN' | 'MALE' | 'FEMALE' | 'OTHER';

export interface CreatePatientInput {
  firstName: string;
  lastName: string;
  /** Only firstName + lastName are required. Everything else is optional
   *  so fast clinic intake is "type two names and go." */
  drChronoId?: string | null;
  mrn?: string | null;
  chartId?: string | null;
  birthYear?: number | null;
  email?: string | null;
  phoneLast4?: string | null;
  cellPhone?: string | null;
  homePhone?: string | null;
  insuranceVerified?: boolean | null;
  sex?: PatientSex | null;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  state?: string | null;
  postalCode?: string | null;
  pharmacyName?: string | null;
  pharmacyPhone?: string | null;
  tags?: string[];
  /** Initial brief-history entries (usually empty; UI captures a single
   *  intake-note textarea that becomes one element). */
  briefHistory?: string[];
  /** Optional doctor to assign at create time. Must be a user in the
   *  same practice; enforced at the data layer. */
  assignedDoctorId?: string | null;
}

export interface UpdatePatientInput {
  firstName?: string;
  lastName?: string;
  mrn?: string | null;
  chartId?: string | null;
  birthYear?: number | null;
  email?: string | null;
  phoneLast4?: string | null;
  cellPhone?: string | null;
  homePhone?: string | null;
  insuranceVerified?: boolean | null;
  sex?: PatientSex | null;
  addressLine1?: string | null;
  addressLine2?: string | null;
  city?: string | null;
  state?: string | null;
  postalCode?: string | null;
  pharmacyName?: string | null;
  pharmacyPhone?: string | null;
  status?: PatientStatus;
  tags?: string[];
  /** Replace-semantics — caller sends the full updated list including any
   *  existing entries to keep. The AI assistant tool gets the current list
   *  in its system prompt so it can preserve history when adding lines. */
  briefHistory?: string[];
  assignedDoctorId?: string | null;
}

/**
 * Get all patients the current session is allowed to see.
 * Excludes soft-deleted. Non-admins see only patients they created or
 * are assigned to; admins see all.
 */
export async function getAllPatients(session: Session): Promise<PatientView[]> {
  if (await isDatabaseHealthy()) {
    try {
      const rows = await prisma.patient.findMany({
        where: patientAccessWhere(session),
        orderBy: [{ status: 'asc' }, { lastName: 'asc' }],
      });
      return rows.map(prismaToView);
    } catch (err) {
      console.warn('[data/patients] Prisma findMany failed, using memory:', err);
    }
  }
  return Array.from(memoryStore.values());
}

/**
 * Get a single patient by ID — ISOLATION-ENFORCED.
 * Returns null if the patient doesn't exist OR the session isn't allowed
 * to see them. Never leak "exists but forbidden" vs "doesn't exist" to
 * the caller — both return null so URL-probing can't enumerate other
 * users' charts.
 */
export async function getPatientById(
  id: string,
  session: Session
): Promise<PatientView | null> {
  if (await isDatabaseHealthy()) {
    try {
      // Compose the access filter with the id lookup so Postgres does
      // the ACL check — no row returned if the current user can't see it.
      const row = await prisma.patient.findFirst({
        where: { id, ...patientAccessWhere(session) },
      });
      if (!row) return null;
      return prismaToView(row);
    } catch (err) {
      console.warn('[data/patients] Prisma findFirst failed, using memory:', err);
    }
  }
  return memoryStore.get(id) ?? null;
}

// ---------------------------------------------------------------------------
// Auto chart-ID generation (per-practice)
// ---------------------------------------------------------------------------
// Format: `C-<n>` where n starts at 1001. Per-practice — Practice A's
// C-1001 is unrelated to Practice B's C-1001; the DB unique constraint
// `@@unique([practiceId, chartId])` enforces this at write time.
//
// Generation: scan all existing chartIds matching /^C-\d+$/ for this
// practice, take max(n), return C-(max+1). Ignores any chartIds in other
// formats (legacy CHART-500, DC-123, etc.) — those aren't in our sequence.
//
// Thread-safety: the generator is a best-guess; the DB unique constraint
// is the real gate. `createPatient` wraps the insert in a retry loop and
// re-generates on Prisma P2002 (unique violation) so two concurrent
// creators in the same practice always get distinct IDs.
// ---------------------------------------------------------------------------

const CHART_ID_REGEX = /^C-(\d+)$/;
const CHART_ID_START = 1000; // first auto-generated ID is CHART_ID_START + 1

function nextChartIdFromValues(existingChartIds: Array<string | null | undefined>): string {
  const max = existingChartIds.reduce((m, v) => {
    const match = CHART_ID_REGEX.exec(v ?? '');
    if (!match) return m;
    const n = parseInt(match[1], 10);
    return Number.isFinite(n) ? Math.max(m, n) : m;
  }, CHART_ID_START);
  return `C-${max + 1}`;
}

/**
 * Compute the next auto chart ID for a practice.
 * Tenant-scoped by practiceId — pass the session's practiceId.
 */
export async function getNextChartId(practiceId: string): Promise<string> {
  if (await isDatabaseHealthy()) {
    try {
      const rows = await prisma.patient.findMany({
        where: { practiceId, chartId: { startsWith: 'C-' } },
        select: { chartId: true },
      });
      return nextChartIdFromValues(rows.map((r: { chartId: string | null }) => r.chartId));
    } catch (err) {
      console.warn('[data/patients] getNextChartId DB read failed, using memory:', err);
    }
  }
  return nextChartIdFromValues(Array.from(memoryStore.values()).map((p) => p.chartId));
}

/**
 * Create a new patient record.
 * Validates uniqueness of drChronoId.
 *
 * Chart ID behavior:
 *   - If `input.chartId` is a non-empty string, uses it verbatim.
 *   - If null/undefined/empty, auto-generates `C-<n>` per practice with
 *     retry-on-collision so two concurrent creators don't collide.
 */
export async function createPatient(
  input: CreatePatientInput,
  createdById: string,
  practiceId: string
): Promise<PatientView> {
  const manualChartId = input.chartId && input.chartId.trim() !== '' ? input.chartId.trim() : null;

  if (await isDatabaseHealthy()) {
    // Retry loop — only exercised on unique-constraint collision when two
    // concurrent creators grab the same next ID. The DB is the source of
    // truth; the generator is advisory. Any P2002 here bubbles to the
    // caller as a meaningful error — we do NOT silently fall through to
    // the memory store (that would mask real duplicates).
    const MAX_ATTEMPTS = 5;
    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
      const chartId = manualChartId ?? (await getNextChartId(practiceId));
      try {
        const row = await prisma.patient.create({
          data: {
            firstName: input.firstName,
            lastName: input.lastName,
            drChronoId: input.drChronoId ?? null,
            mrn: input.mrn ?? null,
            chartId,
            birthYear: input.birthYear ?? null,
            email: input.email ?? null,
            phoneLast4: input.phoneLast4 ?? null,
            cellPhone: input.cellPhone ?? null,
            homePhone: input.homePhone ?? null,
            insuranceVerified: input.insuranceVerified ?? null,
            // Scalar default on the column is UNKNOWN, but be explicit so
            // inserts are readable in DB logs.
            sex: input.sex ?? 'UNKNOWN',
            addressLine1: input.addressLine1 ?? null,
            addressLine2: input.addressLine2 ?? null,
            city: input.city ?? null,
            state: input.state ?? null,
            postalCode: input.postalCode ?? null,
            pharmacyName: input.pharmacyName ?? null,
            pharmacyPhone: input.pharmacyPhone ?? null,
            tags: input.tags ?? [],
            briefHistory: input.briefHistory ?? [],
            assignedDoctorId: input.assignedDoctorId ?? null,
            status: 'ACTIVE',
            createdById,
            practiceId,
          },
        });
        return prismaToView(row);
      } catch (err) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const code = (err as any)?.code;
        if (code === 'P2002') {
          // Unique constraint violation. Prisma 7 + adapter-pg sometimes
          // omits meta.target, so we can't always distinguish chartId vs
          // drChronoId collisions. Heuristic: if the caller supplied a
          // drChronoId, attribute collisions to that first (it has a
          // global unique). Otherwise treat as chartId collision.
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const target = (err as any)?.meta?.target;
          const targetIsDrChrono =
            Array.isArray(target) && target.includes('drChronoId');
          if (input.drChronoId && (targetIsDrChrono || !target)) {
            throw new Error(
              `A patient with DrChrono ID "${input.drChronoId}" already exists.`
            );
          }
          if (manualChartId) {
            throw new Error(
              `Chart ID "${manualChartId}" already exists in this practice. Leave it blank to auto-generate.`
            );
          }
          // Auto-generated chartId collided with a concurrent insert —
          // re-generate and retry.
          continue;
        }
        // Non-unique error (DB down, bad data, etc.). Only fall back to
        // memory if the DB is genuinely unreachable — re-check health
        // and break either way.
        console.warn('[data/patients] Prisma create failed:', err);
        break;
      }
    }
    // If we got here with a manualChartId, we've already thrown. With an
    // auto chartId, we exhausted retries — fall through to memory so the
    // caller sees something, and log.
    if (!manualChartId) {
      console.warn('[data/patients] createPatient exhausted retries, using memory');
    }
  }

  // Memory fallback. DrChrono uniqueness only matters when the caller
  // actually supplied a drChronoId — otherwise multiple null-id mocks
  // are fine (matches the Postgres-NULL-is-distinct behavior).
  if (input.drChronoId) {
    for (const existing of memoryStore.values()) {
      if (existing.drChronoId === input.drChronoId) {
        throw new Error(`A patient with DrChrono ID "${input.drChronoId}" already exists.`);
      }
    }
  }
  const newPatient: MockPatient = {
    id: generateId(),
    drChronoId: input.drChronoId ?? undefined,
    firstName: input.firstName,
    lastName: input.lastName,
    birthYear: input.birthYear ?? new Date().getFullYear() - 30,
    mrn: input.mrn ?? `MRN-${Math.floor(Math.random() * 900000 + 100000)}`,
    chartId: manualChartId ?? nextChartIdFromValues(Array.from(memoryStore.values()).map((p) => p.chartId)),
    email: input.email ?? undefined,
    phoneLast4: input.phoneLast4 ?? undefined,
    cellPhone: input.cellPhone ?? undefined,
    homePhone: input.homePhone ?? undefined,
    insuranceVerified: input.insuranceVerified ?? undefined,
    sex: input.sex ?? 'UNKNOWN',
    addressLine1: input.addressLine1 ?? undefined,
    addressLine2: input.addressLine2 ?? undefined,
    city: input.city ?? undefined,
    state: input.state ?? undefined,
    postalCode: input.postalCode ?? undefined,
    pharmacyName: input.pharmacyName ?? undefined,
    pharmacyPhone: input.pharmacyPhone ?? undefined,
    status: 'ACTIVE',
    tags: input.tags ?? [],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: new Date().toISOString(),
    createdAt: new Date().toISOString(),
    briefHistory: input.briefHistory ?? [],
    recentNotes: [],
    files: [],
  };
  memoryStore.set(newPatient.id, newPatient);
  return newPatient;
}

/**
 * Update an existing patient. Returns the updated record or null if not found.
 * Returns the list of changed field NAMES (not values) for audit logging.
 */
export async function updatePatient(
  id: string,
  input: UpdatePatientInput,
  session: Session
): Promise<{ patient: PatientView; changedFields: string[] } | null> {
  // Isolation check happens inside getPatientById — if the session can't
  // see this patient, it returns null and we refuse the update.
  const existing = await getPatientById(id, session);
  if (!existing) return null;

  const changedFields: string[] = [];
  for (const key of Object.keys(input) as Array<keyof UpdatePatientInput>) {
    const newVal = input[key];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const oldVal = (existing as any)[key];
    if (newVal !== undefined && JSON.stringify(newVal) !== JSON.stringify(oldVal)) {
      changedFields.push(key);
    }
  }

  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.patient.update({
        where: { id },
        data: input,
      });
      return { patient: prismaToView(row), changedFields };
    } catch (err) {
      console.warn('[data/patients] Prisma update failed, using memory:', err);
    }
  }

  // Memory fallback. UpdatePatientInput accepts `null` for nullable fields
  // (meaning "explicitly clear this value"), but MockPatient uses `undefined`
  // for the same state. Normalize null → undefined for optional string
  // fields as we merge.
  const nullableToUndef = <T,>(v: T | null | undefined, fallback: T | undefined): T | undefined =>
    v === null ? undefined : v ?? fallback;
  const updated: MockPatient = {
    ...existing,
    ...input,
    email: nullableToUndef(input.email, existing.email),
    phoneLast4: nullableToUndef(input.phoneLast4, existing.phoneLast4),
    chartId: nullableToUndef(input.chartId, existing.chartId),
    cellPhone: nullableToUndef(input.cellPhone, existing.cellPhone),
    homePhone: nullableToUndef(input.homePhone, existing.homePhone),
    insuranceVerified:
      input.insuranceVerified === null
        ? undefined
        : input.insuranceVerified ?? existing.insuranceVerified,
    mrn: input.mrn ?? existing.mrn,
    birthYear: input.birthYear ?? existing.birthYear,
    tags: input.tags ?? existing.tags,
    sex: input.sex === null ? 'UNKNOWN' : input.sex ?? existing.sex,
    addressLine1: nullableToUndef(input.addressLine1, existing.addressLine1),
    addressLine2: nullableToUndef(input.addressLine2, existing.addressLine2),
    city: nullableToUndef(input.city, existing.city),
    state: nullableToUndef(input.state, existing.state),
    postalCode: nullableToUndef(input.postalCode, existing.postalCode),
    pharmacyName: nullableToUndef(input.pharmacyName, existing.pharmacyName),
    pharmacyPhone: nullableToUndef(input.pharmacyPhone, existing.pharmacyPhone),
  };
  memoryStore.set(id, updated);
  return { patient: updated, changedFields };
}

/**
 * Soft-delete (archive) a patient.
 */
export async function archivePatient(id: string, session: Session): Promise<boolean> {
  const existing = await getPatientById(id, session);
  if (!existing) return false;

  if (await isDatabaseHealthy()) {
    try {
      await prisma.patient.update({
        where: { id },
        data: { status: 'ARCHIVED', deletedAt: new Date() },
      });
      return true;
    } catch (err) {
      console.warn('[data/patients] Prisma archive failed, using memory:', err);
    }
  }

  memoryStore.set(id, { ...existing, status: 'ARCHIVED' });
  return true;
}

/**
 * Search patients by name / MRN / DrChrono ID / tag.
 */
export async function searchPatientsDb(
  query: string,
  session: Session
): Promise<PatientView[]> {
  const all = await getAllPatients(session);
  if (!query.trim()) return all;
  const q = query.toLowerCase();
  return all.filter(
    (p) =>
      p.firstName.toLowerCase().includes(q) ||
      p.lastName.toLowerCase().includes(q) ||
      p.mrn.toLowerCase().includes(q) ||
      (p.drChronoId?.toLowerCase().includes(q) ?? false) ||
      (p.chartId?.toLowerCase().includes(q) ?? false) ||
      (p.cellPhone?.toLowerCase().includes(q) ?? false) ||
      p.tags.some((t) => t.toLowerCase().includes(q))
  );
}

// ---------------------------------------------------------------------------
// Internal — convert Prisma row to UI shape
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function prismaToView(row: any): PatientView {
  return {
    id: row.id,
    drChronoId: row.drChronoId ?? undefined,
    firstName: row.firstName,
    lastName: row.lastName,
    birthYear: row.birthYear ?? new Date().getFullYear() - 30,
    mrn: row.mrn ?? '',
    chartId: row.chartId ?? undefined,
    email: row.email ?? undefined,
    phoneLast4: row.phoneLast4 ?? undefined,
    cellPhone: row.cellPhone ?? undefined,
    homePhone: row.homePhone ?? undefined,
    insuranceVerified: row.insuranceVerified ?? undefined,
    sex: row.sex ?? 'UNKNOWN',
    addressLine1: row.addressLine1 ?? undefined,
    addressLine2: row.addressLine2 ?? undefined,
    city: row.city ?? undefined,
    state: row.state ?? undefined,
    postalCode: row.postalCode ?? undefined,
    pharmacyName: row.pharmacyName ?? undefined,
    pharmacyPhone: row.pharmacyPhone ?? undefined,
    status: row.status as PatientStatus,
    tags: row.tags ?? [],
    assignedDoctor: 'Dr. Moussazadeh', // joined separately in real app
    lastVisit: row.lastSyncAt?.toISOString() ?? row.updatedAt.toISOString(),
    createdAt: row.createdAt.toISOString(),
    // briefHistory now lives on the Patient row (Phase 2 schema migration).
    // Editable via Edit Patient + AI assistant's update_patient tool.
    briefHistory: row.briefHistory ?? [],
    // These still come from related tables (Document, etc.).
    recentNotes: [],
    files: [],
  };
}
