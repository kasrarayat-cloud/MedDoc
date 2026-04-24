// ============================================================================
// Mock Patient Data
// ----------------------------------------------------------------------------
// Used for UI development and demos. In production, this is replaced with
// data from PostgreSQL via Prisma + DrChrono sync.
//
// IMPORTANT (HIPAA): All names, MRNs, and IDs below are FICTIONAL.
// Per HIPAA Safe Harbor §164.514, we store birth YEAR only — no full DOB.
// ============================================================================

export type PatientStatus = 'ACTIVE' | 'INACTIVE' | 'ARCHIVED';

export interface MockNote {
  id: string;
  title: string;
  procedureType: string;
  date: string; // ISO
  preview: string;
  status: 'DRAFT' | 'FINALIZED' | 'SIGNED';
}

export interface MockFile {
  id: string;
  name: string;
  sizeBytes: number;
  mimeType: string;
  uploadedAt: string;
  dropboxUrl: string;
}

export interface MockPatient {
  id: string;
  /** Optional after the DrChrono-always-required constraint was lifted —
   *  the CRM can now hold patients that aren't in DrChrono at all. */
  drChronoId?: string;
  firstName: string;
  lastName: string;
  /** Null = DOB not recorded. NEVER substitute a default here — the
   *  caller (UI / LLM prompt) is responsible for saying "Unknown" or
   *  "Not recorded" explicitly. Faking an age (30, whatever) to keep
   *  this non-nullable silently corrupts AI-generated clinical
   *  content and is a patient-safety defect. See audit C1. */
  birthYear: number | null;
  /** MRN (for insurance filings). */
  mrn: string;
  /** Practice-internal chart number (separate from MRN). */
  chartId?: string;
  email?: string;
  /** Back-compat field — last 4 digits of phone. */
  phoneLast4?: string;
  /** Full cell phone — preferred when the practice needs to call out. */
  cellPhone?: string;
  /** Full home phone. */
  homePhone?: string;
  /** Insurance-on-file state. undefined = unknown / not yet checked. */
  insuranceVerified?: boolean;
  /** Biological sex — clinically relevant (dosing, procedures). Non-PHI
   *  under HIPAA Safe Harbor. Matches the PatientSex Prisma enum. */
  sex?: 'UNKNOWN' | 'MALE' | 'FEMALE' | 'OTHER';
  /** Mailing / insurance address. Full street address is PHI — treat
   *  with the same tenant isolation + audit rules as phones. */
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  /** US 2-char state code, e.g. "CA". Loose storage. */
  state?: string;
  postalCode?: string;
  /** Preferred pharmacy for e-prescribing (esp. controlled substances). */
  pharmacyName?: string;
  pharmacyPhone?: string;
  status: PatientStatus;
  tags: string[];
  /** Display name of the assigned provider (joined in the data layer
   *  when possible, falls back to "Unassigned" / "Assigned provider"). */
  assignedDoctor: string;
  /** Actual User.id of the assigned provider — drives the Edit dropdown
   *  and the tenant-guarded update path. Undefined means unassigned. */
  assignedDoctorId?: string;
  lastVisit: string; // ISO
  createdAt: string; // ISO
  briefHistory: string[];
  recentNotes: MockNote[];
  files: MockFile[];
}

export const MOCK_PATIENTS: MockPatient[] = [
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y8v0',
    drChronoId: 'DC-1842031',
    firstName: 'Sarah',
    lastName: 'Mitchell',
    birthYear: 1978,
    mrn: 'MRN-440182',
    email: 's.mitchell@example.com',
    phoneLast4: '4421',
    status: 'ACTIVE',
    tags: ['post-op', 'chronic-pain'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2026-03-28T14:30:00Z',
    createdAt: '2024-11-12T10:00:00Z',
    briefHistory: [
      '2nd LESI for refractory low back pain with bilateral radiculopathy.',
      '1st LESI completed 6 weeks prior with 60% pain relief.',
    ],
    recentNotes: [
      {
        id: 'note_a1',
        title: 'Bilateral L4 LESI Procedure Note',
        procedureType: 'LESI',
        date: '2026-03-28T14:30:00Z',
        preview: 'Bilateral L4 transforaminal lumbar epidural steroid injection under fluoroscopic guidance...',
        status: 'SIGNED',
      },
      {
        id: 'note_a2',
        title: 'Pre-Procedure Consultation',
        procedureType: 'Consult',
        date: '2026-03-21T09:00:00Z',
        preview: 'Patient reports continued lower back pain radiating to bilateral lower extremities...',
        status: 'FINALIZED',
      },
    ],
    files: [
      {
        id: 'file_a1',
        name: 'LESI_BL_L4_Mitchell.docx',
        sizeBytes: 24_576,
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        uploadedAt: '2026-03-28T14:45:00Z',
        dropboxUrl: 'https://www.dropbox.com/scl/fi/example1',
      },
      {
        id: 'file_a2',
        name: 'MRI_Lumbar_2026.pdf',
        sizeBytes: 1_843_201,
        mimeType: 'application/pdf',
        uploadedAt: '2026-02-15T11:20:00Z',
        dropboxUrl: 'https://www.dropbox.com/scl/fi/example2',
      },
    ],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9a1',
    drChronoId: 'DC-1842108',
    firstName: 'James',
    lastName: 'Rodriguez',
    birthYear: 1965,
    mrn: 'MRN-440355',
    email: 'jrodriguez@example.com',
    phoneLast4: '7782',
    status: 'ACTIVE',
    tags: ['cervical', 'follow-up'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2026-04-02T11:00:00Z',
    createdAt: '2024-08-20T09:30:00Z',
    briefHistory: [
      '1st CESI for refractory neck pain with right sided radiculopathy.',
    ],
    recentNotes: [
      {
        id: 'note_b1',
        title: 'CESI C7-T1 Procedure Note',
        procedureType: 'CESI',
        date: '2026-04-02T11:00:00Z',
        preview: 'Cervical interlaminar epidural steroid injection at C7-T1 under fluoroscopic guidance...',
        status: 'SIGNED',
      },
    ],
    files: [
      {
        id: 'file_b1',
        name: 'CESI_Rodriguez.docx',
        sizeBytes: 22_113,
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        uploadedAt: '2026-04-02T11:15:00Z',
        dropboxUrl: 'https://www.dropbox.com/scl/fi/example3',
      },
    ],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9b2',
    drChronoId: 'DC-1842215',
    firstName: 'Emily',
    lastName: 'Chen',
    birthYear: 1989,
    mrn: 'MRN-440422',
    email: 'echen@example.com',
    phoneLast4: '1058',
    status: 'ACTIVE',
    tags: ['PRP', 'sports-injury'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2026-04-05T16:15:00Z',
    createdAt: '2025-01-15T13:00:00Z',
    briefHistory: [
      '1st LE PRP injection for refractory low back pain with left sided radiculopathy.',
    ],
    recentNotes: [
      {
        id: 'note_c1',
        title: 'Left L5 LE PRP Procedure Note',
        procedureType: 'LE PRP',
        date: '2026-04-05T16:15:00Z',
        preview: 'Left L5 transforaminal Lumbar epidural platelet rich plasma injection...',
        status: 'FINALIZED',
      },
    ],
    files: [],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9c3',
    drChronoId: 'DC-1842301',
    firstName: 'Robert',
    lastName: 'Thompson',
    birthYear: 1952,
    mrn: 'MRN-440511',
    phoneLast4: '6630',
    status: 'ACTIVE',
    tags: ['facet-block'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2026-03-19T10:30:00Z',
    createdAt: '2023-09-08T14:00:00Z',
    briefHistory: [
      '1st/2nd LFB for refractory axial low back pain.',
      'Reports 80% improvement on provocation exam after first LFB.',
    ],
    recentNotes: [
      {
        id: 'note_d1',
        title: 'Bilateral L4-L5 / L5-S1 LFB Procedure Note',
        procedureType: 'LFB',
        date: '2026-03-19T10:30:00Z',
        preview: 'Bilateral L4-L5 and L5-S1 facet joint block (Medial Branch Nerve) Injection...',
        status: 'SIGNED',
      },
    ],
    files: [
      {
        id: 'file_d1',
        name: 'LFB_BL_Thompson.docx',
        sizeBytes: 23_891,
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        uploadedAt: '2026-03-19T10:45:00Z',
        dropboxUrl: 'https://www.dropbox.com/scl/fi/example4',
      },
    ],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9d4',
    drChronoId: 'DC-1842410',
    firstName: 'Maria',
    lastName: 'Garcia',
    birthYear: 1971,
    mrn: 'MRN-440622',
    email: 'mgarcia@example.com',
    phoneLast4: '8841',
    status: 'INACTIVE',
    tags: ['lapsed'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2025-11-14T09:00:00Z',
    createdAt: '2024-04-22T10:30:00Z',
    briefHistory: [
      '3rd LESI for refractory low back pain with radiculopathy.',
    ],
    recentNotes: [],
    files: [],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9e5',
    drChronoId: 'DC-1842502',
    firstName: 'David',
    lastName: 'Kim',
    birthYear: 1983,
    mrn: 'MRN-440733',
    email: 'dkim@example.com',
    phoneLast4: '5523',
    status: 'ACTIVE',
    tags: ['new-patient'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2026-04-08T13:45:00Z',
    createdAt: '2026-04-08T13:00:00Z',
    briefHistory: [
      'Initial consultation for chronic neck pain with bilateral upper extremity numbness.',
    ],
    recentNotes: [
      {
        id: 'note_f1',
        title: 'Initial Consult',
        procedureType: 'Consult',
        date: '2026-04-08T13:45:00Z',
        preview: 'Patient presents with 4-month history of neck pain radiating to bilateral shoulders...',
        status: 'DRAFT',
      },
    ],
    files: [],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9f6',
    drChronoId: 'DC-1842611',
    firstName: 'Linda',
    lastName: 'Park',
    birthYear: 1960,
    mrn: 'MRN-440844',
    email: 'lpark@example.com',
    phoneLast4: '2299',
    status: 'ACTIVE',
    tags: ['cervical', 'PRP'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2026-03-30T15:00:00Z',
    createdAt: '2025-06-12T11:00:00Z',
    briefHistory: [
      '1st cervical epidural PRP injection for refractory neck and upper back pain.',
    ],
    recentNotes: [
      {
        id: 'note_g1',
        title: 'CE PRP C7-T1 Procedure Note',
        procedureType: 'CE PRP',
        date: '2026-03-30T15:00:00Z',
        preview: 'Cervical epidural Platelet Rich Plasma injection at C7-T1 under fluoroscopic guidance...',
        status: 'SIGNED',
      },
    ],
    files: [
      {
        id: 'file_g1',
        name: 'CE_PRP_Park.docx',
        sizeBytes: 24_011,
        mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        uploadedAt: '2026-03-30T15:10:00Z',
        dropboxUrl: 'https://www.dropbox.com/scl/fi/example5',
      },
    ],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9g7',
    drChronoId: 'DC-1842720',
    firstName: 'Michael',
    lastName: 'Brown',
    birthYear: 1975,
    mrn: 'MRN-440955',
    phoneLast4: '7104',
    status: 'ACTIVE',
    tags: ['combined-procedure'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2026-04-01T08:30:00Z',
    createdAt: '2024-10-03T09:00:00Z',
    briefHistory: [
      '1st LEFSI for refractory low back pain with bilateral radiculopathy.',
    ],
    recentNotes: [
      {
        id: 'note_h1',
        title: 'LESI + LFB Combined Procedure',
        procedureType: 'LESI+LFB',
        date: '2026-04-01T08:30:00Z',
        preview: 'Bilateral L4 transforaminal lumbar epidural injection & bilateral L4-L5 and L5-S1 facet joint blocks...',
        status: 'FINALIZED',
      },
    ],
    files: [],
  },
  {
    id: 'pt_01h8z3k9m1nq4t2r5w7y9h8',
    drChronoId: 'DC-1842833',
    firstName: 'Jennifer',
    lastName: 'Wilson',
    birthYear: 1992,
    mrn: 'MRN-441066',
    email: 'jwilson@example.com',
    phoneLast4: '3320',
    status: 'ARCHIVED',
    tags: ['discharged'],
    assignedDoctor: 'Dr. Moussazadeh',
    lastVisit: '2025-08-10T14:00:00Z',
    createdAt: '2024-02-19T10:00:00Z',
    briefHistory: [
      'Treatment course completed. Discharged with full pain resolution.',
    ],
    recentNotes: [],
    files: [],
  },
];

// Helper utilities ----------------------------------------------------------

export function findPatientById(id: string): MockPatient | undefined {
  return MOCK_PATIENTS.find((p) => p.id === id);
}

export function searchPatients(query: string): MockPatient[] {
  if (!query.trim()) return MOCK_PATIENTS;
  const q = query.toLowerCase();
  return MOCK_PATIENTS.filter(
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

export function formatLastVisit(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatRelativeDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}
