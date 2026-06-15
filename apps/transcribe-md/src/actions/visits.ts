'use server';

import { redirect } from 'next/navigation';
import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { Prisma, type TranscribeVisitStatus } from '@prisma/client';
import { SPECIALTY_IDS } from '@meddoc/shared/specialties';
import { requireSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import {
  DASHBOARD_PAGE_SIZE,
  type DashboardCursor,
  type LoadMoreVisitsResult,
} from '@/lib/dashboard-pagination';
import {
  C3_INBOX_PAGE_SIZE,
  type C3InboxPageResult,
} from '@/lib/c3-list-pagination';

const INPUT_MODES = ['audio_upload', 'voice_dictation', 'text_notes'] as const;

// Placeholder name used when the form submits neither a patientId nor a
// patientName (legacy free-form flow where the doctor skipped the
// field). Matches the label used by the Phase 1 backfill so a practice
// never grows two different "Unknown patient" rows.
const UNKNOWN_PATIENT_NAME = 'Unknown patient';

const CreateVisitSchema = z.object({
  /** T-M17.2: new picker-driven path. When set, `patientName` is
   *  ignored and we validate this ID belongs to the caller's practice
   *  and is not soft-deleted. */
  patientId: z
    .string()
    .trim()
    .min(1)
    .optional()
    .transform((v) => (v === '' || v === undefined ? null : v))
    .nullable(),
  /** Legacy free-text path. Kept for backward compat — the Phase 3
   *  Commit 9 UI replaces it with the picker. */
  patientName: z
    .string()
    .trim()
    .max(120)
    .transform((v) => (v === '' ? null : v))
    .nullable()
    .optional(),
  // Bound to the canonical catalog so the column can only ever hold
  // an enum value. New writes are normalized at the source — legacy
  // display-name rows are mapped at read time via findSpecialty().
  specialty: z.enum(SPECIALTY_IDS, { message: 'Pick a specialty' }),
  chiefComplaint: z
    .string()
    .trim()
    .max(500)
    .transform((v) => (v === '' ? null : v))
    .nullable()
    .optional(),
  inputMode: z.enum(INPUT_MODES),
  // 2026-05-12 interpreter-mode (Sylvia incident follow-up). FormData
  // checkboxes arrive as the literal string 'on' when checked + omitted
  // entirely when unchecked, so the coercion accepts both 'on' (true)
  // and 'true' (the explicit JSON-form value future API callers may use).
  interpreterMode: z
    .preprocess(
      (v) => (v === 'on' || v === 'true' || v === true ? true : false),
      z.boolean(),
    )
    .default(false),
});

/** Resolve the (patientId, patientName) pair into a real TranscribeMdPatient.
 *  Three paths:
 *    - patientId supplied → validate scope + return it verbatim.
 *    - patientName supplied → case-insensitive exact match within
 *      practice, or create a new row (DOB null; doctor can fill from
 *      the Edit Patient UI later).
 *    - Neither supplied → match-or-create a single "Unknown patient"
 *      row per practice.
 *  Throws on a bad patientId so the caller's try/catch surfaces the
 *  problem to the UI instead of silently dropping the relation. */
async function resolvePatient(
  practiceId: string,
  patientId: string | null,
  patientName: string | null
): Promise<{ id: string; name: string }> {
  if (patientId) {
    const patient = await prisma.transcribeMdPatient.findUnique({
      where: { id: patientId },
      select: {
        id: true,
        name: true,
        practiceId: true,
        deletedAt: true,
      },
    });
    if (
      !patient ||
      patient.practiceId !== practiceId ||
      patient.deletedAt !== null
    ) {
      throw new Error('Invalid patient');
    }
    return { id: patient.id, name: patient.name };
  }

  // Free-text name (or the fallback "Unknown patient" bucket).
  const canonicalName = patientName ?? UNKNOWN_PATIENT_NAME;
  const existing = await prisma.transcribeMdPatient.findFirst({
    where: {
      practiceId,
      deletedAt: null,
      name: { equals: canonicalName, mode: 'insensitive' },
    },
    select: { id: true, name: true },
  });
  if (existing) return existing;

  const created = await prisma.transcribeMdPatient.create({
    data: {
      practiceId,
      name: canonicalName,
      // dateOfBirth intentionally null — the doctor can set it later
      // from the Phase 3 Edit Patient UI. New-patient creation via
      // the explicit /api/patients POST requires DOB; this auto-
      // create path is the backward-compat safety net.
    },
    select: { id: true, name: true },
  });
  return created;
}

export async function createVisitAction(formData: FormData): Promise<void> {
  const session = await requireSession();
  const raw = Object.fromEntries(formData.entries());
  const parsed = CreateVisitSchema.safeParse({
    ...raw,
    // HTML checkbox/select can coerce empty strings we'd like to nullify.
    patientId: raw.patientId ?? null,
    patientName: raw.patientName ?? null,
    chiefComplaint: raw.chiefComplaint ?? null,
  });
  if (!parsed.success) {
    // The form's client component re-renders and shows the error. With
    // a 1-field reason (usually invalid inputMode via query tamper) we
    // just throw — this path shouldn't be reached from the legit UI.
    throw new Error('Invalid visit input');
  }

  const patient = await resolvePatient(
    session.user.practiceId,
    parsed.data.patientId ?? null,
    parsed.data.patientName ?? null
  );

  const visit = await prisma.transcribeVisit.create({
    data: {
      userId: session.user.id,
      patientId: patient.id,
      // patientName column stays populated (schema.prisma notes its
      // removal is deferred to a follow-up). Prefer the resolved
      // patient's canonical name over whatever free-text the form
      // sent, so the legacy column and the FK never disagree.
      patientName: patient.name,
      specialty: parsed.data.specialty,
      chiefComplaint: parsed.data.chiefComplaint ?? null,
      inputMode: parsed.data.inputMode,
      interpreterMode: parsed.data.interpreterMode,
    },
    select: { id: true },
  });

  // §164.312(b) — F-10 from QA agent v3.2 discovery report. Visit
  // creation was previously silent at write-time; only VIEWED_VISIT
  // fired later when the doctor navigated into the row, so the
  // create-event itself was invisible in the audit trail. Fire-and-
  // forget per the file's other audit precedents — `logAudit` is
  // internally try/wrapped so failures never break the create path.
  // PHI: only the patient FK + non-clinical metadata go into the row;
  // the patient's name + chiefComplaint stay out.
  void logAudit({
    action: 'VISIT_CREATED',
    targetType: 'TranscribeVisit',
    targetId: visit.id,
    metadata: {
      source: 'action:createVisitAction',
      inputMode: parsed.data.inputMode,
      specialty: parsed.data.specialty,
      patientId: patient.id,
      interpreterMode: parsed.data.interpreterMode,
    },
  });

  revalidatePath('/dashboard');
  redirect(`/visits/${visit.id}`);
}

// ---------------------------------------------------------------------------
// T-M16.4: dashboard pagination (M5)
// ---------------------------------------------------------------------------
//
// Cursor-based — dashboard/page.tsx server-renders the first page via a
// direct Prisma call (so the initial paint is SSR'd without a client
// round-trip), and the "Load more" button calls this action for
// subsequent pages. Page size + cursor types live in
// @/lib/dashboard-pagination because Next 16's 'use server' directive
// forbids non-async exports from this file.

export async function loadMoreVisitsAction(
  cursor: DashboardCursor,
  opts?: { includeArchived?: boolean }
): Promise<LoadMoreVisitsResult> {
  const session = await requireSession();
  const includeArchived = opts?.includeArchived ?? false;

  const cursorDate = new Date(cursor.createdAt);
  if (Number.isNaN(cursorDate.getTime())) {
    throw new Error('Invalid cursor');
  }

  // Fetch one extra so we can set nextCursor without a second query.
  // Compound "older than" via OR because Prisma lacks native tuple
  // comparison. Query is always scoped to the authed userId regardless
  // of cursor contents.
  //
  // T-M17.3: honour the caller's includeArchived flag so paging past
  // the first page keeps the same filter as the SSR'd initial
  // render.
  const rows = await prisma.transcribeVisit.findMany({
    where: {
      userId: session.user.id,
      deletedAt: null,
      ...(includeArchived ? {} : { archivedAt: null }),
      OR: [
        { createdAt: { lt: cursorDate } },
        {
          createdAt: cursorDate,
          id: { lt: cursor.id },
        },
      ],
    },
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: DASHBOARD_PAGE_SIZE + 1,
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      createdAt: true,
      archivedAt: true,
    },
  });

  const hasMore = rows.length > DASHBOARD_PAGE_SIZE;
  const visits = hasMore ? rows.slice(0, DASHBOARD_PAGE_SIZE) : rows;
  const last = visits[visits.length - 1];
  const nextCursor: DashboardCursor | null =
    hasMore && last
      ? { createdAt: last.createdAt.toISOString(), id: last.id }
      : null;

  return { visits, nextCursor };
}

// ---------------------------------------------------------------------------
// C3 calm-skin "Ready to sign" inbox — read-only search + cursor pagination.
// ---------------------------------------------------------------------------
//
// Powers the flag-gated dashboard inbox (dashboard-inbox-c3.tsx). PURELY
// READ-ONLY: same user-scoped READY + unsigned filter the existing dashboard
// already runs, plus an optional case-insensitive search (whole queue, all
// pages) and BOUNDED OFFSET pages (Page X of N) so a sign queue stays finite
// and never runs off the screen. No write path, no behavior change, no gate
// touched. The tenant filter is ALWAYS the authed user — neither `query` nor
// `page` can widen it (page is clamped to [1, totalPages] server-side).
export async function searchInboxAction(
  query: string,
  page: number
): Promise<C3InboxPageResult> {
  const session = await requireSession();
  const q = query.trim().slice(0, 100);

  const where: Prisma.TranscribeVisitWhereInput = {
    userId: session.user.id,
    deletedAt: null,
    archivedAt: null,
    status: 'READY',
    signedAt: null,
    ...(q
      ? {
          OR: [
            { patient: { is: { name: { contains: q, mode: 'insensitive' } } } },
            { patientName: { contains: q, mode: 'insensitive' } },
            { chiefComplaint: { contains: q, mode: 'insensitive' } },
          ],
        }
      : {}),
  };

  const total = await prisma.transcribeVisit.count({ where });
  const pageSize = C3_INBOX_PAGE_SIZE;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  // Clamp caller-supplied page into range (never trust client input to widen
  // the read; an out-of-range page just lands on a valid bounded page).
  const safePage = Number.isFinite(page)
    ? Math.min(Math.max(1, Math.trunc(page)), totalPages)
    : 1;

  type C3InboxRaw = {
    id: string;
    patientName: string | null;
    specialty: string;
    status: TranscribeVisitStatus;
    needsReview: boolean;
    chiefComplaint: string | null;
    createdAt: Date;
    patient: { name: string } | null;
  };
  const rows = (await prisma.transcribeVisit.findMany({
    where,
    orderBy: [{ updatedAt: 'desc' }, { id: 'desc' }],
    skip: (safePage - 1) * pageSize,
    take: pageSize,
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      needsReview: true,
      chiefComplaint: true,
      createdAt: true,
      patient: { select: { name: true } },
    },
  })) as C3InboxRaw[];

  return {
    rows: rows.map((r) => ({
      id: r.id,
      patientName: r.patient?.name ?? r.patientName,
      specialty: r.specialty,
      status: r.status,
      needsReview: r.needsReview,
      chiefComplaint: r.chiefComplaint,
      createdAt: r.createdAt.toISOString(),
    })),
    total,
    page: safePage,
    pageSize,
    totalPages,
  };
}
