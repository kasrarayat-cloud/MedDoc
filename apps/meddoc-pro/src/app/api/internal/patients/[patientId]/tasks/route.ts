// ============================================================================
// POST /api/internal/patients/:patientId/tasks
// ----------------------------------------------------------------------------
// Service-to-service endpoint: Scribe's Sign flow calls this with the list
// of follow-up tasks extracted from the SOAP plan (M6 loop-closing).
// Idempotent via the composite unique on (sourceScribeOutputId,
// sourceItemIndex) — duplicate calls resolve to the already-created Task
// ids instead of creating dupes.
// ============================================================================

import { NextResponse, type NextRequest } from 'next/server';
import type { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';
import {
  CreateTasksRequestSchema,
  type CreateTasksResponse,
} from '@meddoc/types';
import { verifyInternalRequest } from '@/lib/internal-auth';
import { logAudit } from '@/lib/audit';

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ patientId: string }> }
) {
  const auth = verifyInternalRequest(req);
  if (!auth.ok) {
    return NextResponse.json({ error: auth.error }, { status: auth.status });
  }

  const { patientId } = await params;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body.' }, { status: 400 });
  }
  const parsed = CreateTasksRequestSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Body failed schema validation.', details: parsed.error.issues },
      { status: 400 }
    );
  }
  const payload = parsed.data;

  // Defense-in-depth tenant gate: the assigning clinician must be in the
  // same practice as the patient. Matches the /notes route pattern.
  const [clinician, patient] = await Promise.all([
    prisma.user.findUnique({
      where: { id: payload.assignedUserId },
      select: { id: true, practiceId: true, isActive: true },
    }),
    prisma.patient.findUnique({
      where: { id: patientId },
      select: { id: true, practiceId: true, deletedAt: true },
    }),
  ]);
  if (!clinician || !clinician.isActive) {
    return NextResponse.json({ error: 'Clinician not found or inactive.' }, { status: 400 });
  }
  if (!patient || patient.deletedAt) {
    return NextResponse.json({ error: 'Patient not found.' }, { status: 404 });
  }
  if (clinician.practiceId !== patient.practiceId) {
    return NextResponse.json(
      { error: 'Clinician and patient are in different practices.' },
      { status: 403 }
    );
  }

  // Per-task upsert keyed on (sourceScribeOutputId, sourceItemIndex). The
  // composite unique name from Prisma is task_scribe_source_unique.
  const taskIds: string[] = [];
  for (const item of payload.tasks) {
    const row = await prisma.task.upsert({
      where: {
        task_scribe_source_unique: {
          sourceScribeOutputId: payload.sourceScribeOutputId,
          sourceItemIndex: item.sourceItemIndex,
        },
      },
      create: {
        practiceId: clinician.practiceId,
        patientId: patient.id,
        assignedUserId: payload.assignedUserId,
        createdByUserId: payload.createdByUserId,
        title: item.title,
        description: item.description ?? null,
        dueAt: item.dueAt ? new Date(item.dueAt) : null,
        sourceVisitId: payload.sourceVisitId,
        sourceScribeOutputId: payload.sourceScribeOutputId,
        sourceItemIndex: item.sourceItemIndex,
      } satisfies Prisma.TaskUncheckedCreateInput,
      update: {
        // On idempotent retry, don't overwrite in-progress clinician edits.
        // The upsert just returns the existing row.
      },
      select: { id: true },
    });
    taskIds.push(row.id);
  }

  await logAudit({
    action: 'CREATED_TASK',
    targetId: payload.sourceVisitId,
    targetType: 'ScribeVisit',
    userId: payload.createdByUserId,
    practiceId: clinician.practiceId,
    metadata: {
      via: 'scribe',
      patientId: patient.id,
      taskCount: taskIds.length,
      sourceScribeOutputId: payload.sourceScribeOutputId,
    },
  });

  const resp: CreateTasksResponse = { taskIds };
  return NextResponse.json(resp, { status: 201 });
}
