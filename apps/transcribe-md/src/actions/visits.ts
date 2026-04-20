'use server';

import { redirect } from 'next/navigation';
import { revalidatePath } from 'next/cache';
import { z } from 'zod';

import prisma from '@meddoc/db';
import { requireSession } from '@/lib/auth';

const INPUT_MODES = ['audio_upload', 'voice_dictation', 'text_notes'] as const;

const CreateVisitSchema = z.object({
  patientName: z
    .string()
    .trim()
    .max(120)
    .transform((v) => (v === '' ? null : v))
    .nullable()
    .optional(),
  specialty: z.string().min(1, 'Pick a specialty'),
  chiefComplaint: z
    .string()
    .trim()
    .max(500)
    .transform((v) => (v === '' ? null : v))
    .nullable()
    .optional(),
  inputMode: z.enum(INPUT_MODES),
});

export async function createVisitAction(formData: FormData): Promise<void> {
  const session = await requireSession();
  const raw = Object.fromEntries(formData.entries());
  const parsed = CreateVisitSchema.safeParse({
    ...raw,
    // HTML checkbox/select can coerce empty strings we'd like to nullify.
    patientName: raw.patientName ?? null,
    chiefComplaint: raw.chiefComplaint ?? null,
  });
  if (!parsed.success) {
    // The form's client component re-renders and shows the error. With
    // a 1-field reason (usually invalid inputMode via query tamper) we
    // just throw — this path shouldn't be reached from the legit UI.
    throw new Error('Invalid visit input');
  }

  const visit = await prisma.transcribeVisit.create({
    data: {
      userId: session.user.id,
      patientName: parsed.data.patientName ?? null,
      specialty: parsed.data.specialty,
      chiefComplaint: parsed.data.chiefComplaint ?? null,
      inputMode: parsed.data.inputMode,
    },
    select: { id: true },
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
// subsequent pages. Page size is 20 visits.
//
// Cursor shape = the (createdAt, id) of the LAST visit in the prior
// page. TranscribeVisit has @@index([userId, createdAt]); the id
// tiebreaker handles the rare case of two visits created inside the
// same millisecond.

export const DASHBOARD_PAGE_SIZE = 20;

export interface DashboardCursor {
  /** ISO string — JSON-safe across the server-action boundary. */
  createdAt: string;
  id: string;
}

export interface LoadMoreVisitsResult {
  visits: Array<{
    id: string;
    patientName: string | null;
    specialty: string;
    status: import('@prisma/client').TranscribeVisitStatus;
    createdAt: Date;
  }>;
  /** Null when this was the last page. */
  nextCursor: DashboardCursor | null;
}

export async function loadMoreVisitsAction(
  cursor: DashboardCursor
): Promise<LoadMoreVisitsResult> {
  const session = await requireSession();

  const cursorDate = new Date(cursor.createdAt);
  if (Number.isNaN(cursorDate.getTime())) {
    throw new Error('Invalid cursor');
  }

  // Fetch one extra so we can set nextCursor without a second query.
  // Compound "older than" via OR because Prisma lacks native tuple
  // comparison. Query is always scoped to the authed userId regardless
  // of cursor contents.
  const rows = await prisma.transcribeVisit.findMany({
    where: {
      userId: session.user.id,
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
