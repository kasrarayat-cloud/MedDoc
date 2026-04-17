'use server';

import { revalidatePath } from 'next/cache';
import type { OutputType } from '@prisma/client';
import type { z } from 'zod';
import prisma from '@meddoc/db';
import {
  SoapNoteSchema,
  CodingOutputSchema,
  RxOutputSchema,
  ReferralOutputSchema,
  PatientSummarySchema,
  CreateClinicalNoteRequestSchema,
  type SoapNote,
  type CodingOutput,
  type RxOutput,
  type ReferralOutput,
  type PatientSummary,
  type CreateClinicalNoteResponse,
} from '@meddoc/types';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';

const MEDDOC_PRO_INTERNAL_URL =
  process.env.MEDDOC_PRO_INTERNAL_URL?.trim() || 'http://meddoc-pro:3000';

function getInternalToken(): string {
  const token = process.env.SCRIBE_SERVICE_TOKEN;
  if (!token) throw new Error('SCRIBE_SERVICE_TOKEN is not set.');
  return token;
}

/**
 * Shared save-edit helper. Re-validates the edited blob with the output's
 * success schema (the schema is .strict() so it refuses to accept an
 * OutputError sentinel, per D2), finds the latest row of this type, and
 * updates its content + marks editedByClinician.
 */
async function saveEditedOutput<T>(args: {
  visitId: string;
  type: OutputType;
  schema: z.ZodType<T>;
  value: T;
  editAction: string;
}): Promise<void> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const parsed = args.schema.safeParse(args.value);
  if (!parsed.success) {
    throw new Error(
      `Edited ${args.type} failed schema validation: ${JSON.stringify(parsed.error.issues)}`
    );
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: args.visitId, ...tenantScope(session), deletedAt: null },
    select: { id: true, practiceId: true },
  });
  if (!visit) throw new Error('Visit not found.');

  const existing = await prisma.scribeOutput.findFirst({
    where: { visitId: visit.id, type: args.type },
    orderBy: { createdAt: 'desc' },
  });
  if (!existing) throw new Error(`No ${args.type} output for this visit.`);

  await prisma.scribeOutput.update({
    where: { id: existing.id },
    data: {
      content: parsed.data as object,
      editedByClinician: true,
    },
  });

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: args.editAction,
      diff: { previous: existing.content, next: parsed.data },
    },
  });

  revalidatePath(`/visits/${visit.id}/review`);
}

export async function saveEditedSoapAction(args: { visitId: string; soap: SoapNote }): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'SOAP',
    schema: SoapNoteSchema,
    value: args.soap,
    editAction: 'EDITED_SOAP',
  });
}

export async function saveEditedCodingAction(args: {
  visitId: string; coding: CodingOutput;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'ICD10_CPT',
    schema: CodingOutputSchema,
    value: args.coding,
    editAction: 'EDITED_CODING',
  });
}

export async function saveEditedRxAction(args: {
  visitId: string; rx: RxOutput;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'RX',
    schema: RxOutputSchema,
    value: args.rx,
    editAction: 'EDITED_RX',
  });
}

export async function saveEditedReferralsAction(args: {
  visitId: string; referrals: ReferralOutput;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'REFERRAL',
    schema: ReferralOutputSchema,
    value: args.referrals,
    editAction: 'EDITED_REFERRAL',
  });
}

export async function saveEditedPatientSummaryAction(args: {
  visitId: string; summary: PatientSummary;
}): Promise<void> {
  await saveEditedOutput({
    visitId: args.visitId,
    type: 'PATIENT_SUMMARY',
    schema: PatientSummarySchema,
    value: args.summary,
    editAction: 'EDITED_PATIENT_SUMMARY',
  });
}

import { runBillingPush } from '@/server/push/billing';
import { runMedicationsPush } from '@/server/push/medications';
import { runReferralsPush } from '@/server/push/referrals';
import { runTasksPush } from '@/server/push/tasks';
import { runProblemListPush } from '@/server/push/problem-list';
import type {
  PushOutcome,
  PushTarget,
  SignPushResults,
} from '@/server/push/types';

interface LatestOutputRow {
  id: string;
  content: unknown;
}

/**
 * Fetch the latest ScribeOutput row per type in a single query pass.
 * Returns a Map keyed by OutputType — missing types are simply absent.
 */
async function loadLatestOutputs(
  visitId: string
): Promise<Map<OutputType, LatestOutputRow>> {
  const rows = await prisma.scribeOutput.findMany({
    where: { visitId },
    orderBy: { createdAt: 'desc' },
    select: { id: true, type: true, content: true },
  });
  const out = new Map<OutputType, LatestOutputRow>();
  for (const r of rows) {
    if (!out.has(r.type)) out.set(r.type, { id: r.id, content: r.content });
  }
  return out;
}

/**
 * Sign the visit — M6 full CRM loop-closing flow:
 *   1. Push SOAP to MedDoc Pro (REQUIRED — failure blocks SIGNED)
 *   2. Push the four best-effort targets in parallel:
 *        billing (coding → BillingEvent)
 *        medications (Rx → Medication)
 *        referrals (REFERRAL → Document)
 *        tasks (SOAP.plan → Task)
 *        problem_list (SOAP.assessment → Patient.briefHistory)
 *   3. Stamp signedAt on all ScribeOutput rows; transition visit to SIGNED
 *   4. Return the full PushOutcome set so the UI can show per-push status +
 *      a "Retry failed pushes" button (M6 critical addition).
 *
 * Best-effort semantics (D5): only the SOAP push blocks SIGNED. Every
 * other push's failure is logged + surfaced, but doesn't rollback the
 * visit status. Idempotency guarantees (D6) make the Retry button safe.
 */
export async function signAndSendVisitAction(args: {
  visitId: string;
}): Promise<{ documentId: string; pushResults: SignPushResults }> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: args.visitId, ...tenantScope(session), deletedAt: null },
    select: {
      id: true,
      practiceId: true,
      userId: true,
      patientId: true,
      status: true,
      specialty: { select: { displayName: true, version: true } },
      patient: { select: { firstName: true, lastName: true, chartId: true } },
    },
  });
  if (!visit) throw new Error('Visit not found.');
  if (visit.status !== 'READY_FOR_REVIEW') {
    throw new Error(`Visit is in status ${visit.status}; cannot sign.`);
  }

  const latestByType = await loadLatestOutputs(visit.id);
  const soapRow = latestByType.get('SOAP');
  if (!soapRow) throw new Error('No SOAP output to sign.');
  const soapValidated = SoapNoteSchema.parse(soapRow.content);
  const signedAt = new Date();
  const signedAtIso = signedAt.toISOString();

  // ── Step 1: SOAP push (REQUIRED) ────────────────────────────────
  const reqBody = CreateClinicalNoteRequestSchema.parse({
    sourceVisitId: visit.id,
    clinicianUserId: session.user.id,
    title: `${signedAtIso.slice(0, 10)} • ${visit.specialty.displayName} visit — ${visit.patient.lastName}, ${visit.patient.firstName}`,
    procedureType: visit.specialty.displayName,
    soap: soapValidated,
    signedAt: signedAtIso,
  });

  const resp = await fetch(
    `${MEDDOC_PRO_INTERNAL_URL}/api/internal/patients/${visit.patientId}/notes`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getInternalToken()}`,
      },
      body: JSON.stringify(reqBody),
    }
  );
  if (!resp.ok) {
    // SOAP is the hard prerequisite — if it fails, bail and leave the
    // visit in READY_FOR_REVIEW so the clinician can retry the whole
    // Sign once the transient issue clears.
    const txt = await resp.text().catch(() => '');
    throw new Error(`MedDoc Pro internal API returned ${resp.status}: ${txt.slice(0, 300)}`);
  }
  const respBody = (await resp.json()) as CreateClinicalNoteResponse;

  const noteOutcome: PushOutcome = {
    target: 'note',
    status: 'ok',
    summary: 'Clinical note pushed to chart.',
    createdIds: [respBody.documentId],
  };

  // ── Step 2: parallel best-effort pushes (M6 D5 + D7) ───────────────
  const patientDisplayName = `${visit.patient.lastName}, ${visit.patient.firstName}`;
  const bestEffort = await runBestEffortPushes({
    visitId: visit.id,
    patientId: visit.patientId,
    patientDisplayName,
    clinicianUserId: session.user.id,
    latestByType,
  });

  // ── Step 3: stamp signedAt + transition to SIGNED ─────────────────
  const types: OutputType[] = ['SOAP', 'ICD10_CPT', 'RX', 'REFERRAL', 'PATIENT_SUMMARY'];
  for (const type of types) {
    const latest = latestByType.get(type);
    if (!latest) continue;
    await prisma.scribeOutput.update({
      where: { id: latest.id },
      data: { signedAt, signedBy: session.user.id },
    });
  }

  await prisma.scribeVisit.update({
    where: { id: visit.id },
    data: { status: 'SIGNED' },
  });

  const allOutcomes: PushOutcome[] = [noteOutcome, ...bestEffort];
  const failedTargets = allOutcomes
    .filter((o): o is Extract<PushOutcome, { status: 'error' }> => o.status === 'error')
    .map((o) => o.target);

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: 'SIGNED_VISIT',
      diff: {
        documentId: respBody.documentId,
        signedAt: signedAtIso,
        outputsStamped: types,
        pushOutcomes: allOutcomes.map((o) => ({
          target: o.target,
          status: o.status,
          summary: 'summary' in o ? o.summary : undefined,
          reason: 'reason' in o ? o.reason : undefined,
          message: 'message' in o ? o.message : undefined,
          httpStatus: 'httpStatus' in o ? o.httpStatus : undefined,
        })),
        failedTargets,
      },
    },
  });

  revalidatePath(`/visits/${visit.id}`);
  revalidatePath(`/visits/${visit.id}/review`);
  return {
    documentId: respBody.documentId,
    pushResults: { outcomes: allOutcomes, failedTargets },
  };
}

/**
 * Extracted so retryFailedPushesAction can reuse the same orchestration
 * with a filter on which targets to attempt.
 */
async function runBestEffortPushes(args: {
  visitId: string;
  patientId: string;
  patientDisplayName: string;
  clinicianUserId: string;
  latestByType: Map<OutputType, LatestOutputRow>;
  /** Optional subset — if omitted, all 5 best-effort pushes run. */
  onlyTargets?: PushTarget[];
}): Promise<PushOutcome[]> {
  const { latestByType, onlyTargets } = args;
  const soapRow = latestByType.get('SOAP');
  const codingRow = latestByType.get('ICD10_CPT');
  const rxRow = latestByType.get('RX');
  const referralRow = latestByType.get('REFERRAL');

  const wants = (t: PushTarget): boolean => !onlyTargets || onlyTargets.includes(t);
  const tasks: Array<Promise<PushOutcome>> = [];

  if (wants('billing')) {
    tasks.push(
      codingRow
        ? runBillingPush({
            patientId: args.patientId,
            sourceVisitId: args.visitId,
            sourceScribeOutputId: codingRow.id,
            clinicianUserId: args.clinicianUserId,
            rawContent: codingRow.content,
          })
        : Promise.resolve<PushOutcome>({
            target: 'billing',
            status: 'skipped',
            reason: 'No ICD-10/CPT output for this visit.',
          })
    );
  }

  if (wants('medications')) {
    tasks.push(
      rxRow
        ? runMedicationsPush({
            patientId: args.patientId,
            sourceVisitId: args.visitId,
            sourceScribeOutputId: rxRow.id,
            clinicianUserId: args.clinicianUserId,
            rawContent: rxRow.content,
          })
        : Promise.resolve<PushOutcome>({
            target: 'medications',
            status: 'skipped',
            reason: 'No Rx output for this visit.',
          })
    );
  }

  if (wants('referrals')) {
    tasks.push(
      referralRow
        ? runReferralsPush({
            patientId: args.patientId,
            sourceVisitId: args.visitId,
            sourceScribeOutputId: referralRow.id,
            clinicianUserId: args.clinicianUserId,
            rawContent: referralRow.content,
          })
        : Promise.resolve<PushOutcome>({
            target: 'referrals',
            status: 'skipped',
            reason: 'No referral output for this visit.',
          })
    );
  }

  if (wants('tasks')) {
    tasks.push(
      soapRow
        ? runTasksPush({
            patientId: args.patientId,
            patientDisplayName: args.patientDisplayName,
            sourceVisitId: args.visitId,
            sourceScribeOutputId: soapRow.id,
            clinicianUserId: args.clinicianUserId,
            rawSoapContent: soapRow.content,
          })
        : Promise.resolve<PushOutcome>({
            target: 'tasks',
            status: 'skipped',
            reason: 'No SOAP output to derive tasks from.',
          })
    );
  }

  if (wants('problem_list')) {
    tasks.push(
      soapRow
        ? runProblemListPush({
            patientId: args.patientId,
            sourceVisitId: args.visitId,
            sourceScribeOutputId: soapRow.id,
            rawSoapContent: soapRow.content,
          })
        : Promise.resolve<PushOutcome>({
            target: 'problem_list',
            status: 'skipped',
            reason: 'No SOAP output to derive problem-list lines from.',
          })
    );
  }

  const settled = await Promise.allSettled(tasks);
  return settled.map((s): PushOutcome => {
    if (s.status === 'fulfilled') return s.value;
    // An unexpected throw past the module's try/catch — treat as error.
    return {
      target: 'note', // overwritten below; placeholder
      status: 'error',
      message: s.reason instanceof Error ? s.reason.message : String(s.reason),
    };
  });
}

/**
 * Retry only the targets that failed on the original Sign. Idempotency
 * on the MedDoc Pro side makes succeeded pushes no-ops (D6) — so it's
 * safe to pass the whole failed set even if a partial retry already
 * succeeded server-side.
 */
export async function retryFailedPushesAction(args: {
  visitId: string;
  targets: PushTarget[];
}): Promise<SignPushResults> {
  const session = await getSession();
  if (!session) throw new Error('Not authenticated.');

  if (args.targets.length === 0) {
    return { outcomes: [], failedTargets: [] };
  }

  const visit = await prisma.scribeVisit.findFirst({
    where: { id: args.visitId, ...tenantScope(session), deletedAt: null },
    select: {
      id: true,
      practiceId: true,
      patientId: true,
      status: true,
      patient: { select: { firstName: true, lastName: true } },
    },
  });
  if (!visit) throw new Error('Visit not found.');
  if (visit.status !== 'SIGNED') {
    throw new Error(`Visit is in status ${visit.status}; retry only applies to SIGNED visits.`);
  }

  const latestByType = await loadLatestOutputs(visit.id);
  const patientDisplayName = `${visit.patient.lastName}, ${visit.patient.firstName}`;

  // Only retry best-effort targets — 'note' (SOAP) is a hard prerequisite
  // that must succeed on the original Sign.
  const bestEffortTargets = args.targets.filter((t) => t !== 'note') as PushTarget[];

  const outcomes = await runBestEffortPushes({
    visitId: visit.id,
    patientId: visit.patientId,
    patientDisplayName,
    clinicianUserId: session.user.id,
    latestByType,
    onlyTargets: bestEffortTargets,
  });

  const failedTargets = outcomes
    .filter((o): o is Extract<PushOutcome, { status: 'error' }> => o.status === 'error')
    .map((o) => o.target);

  await prisma.scribeAuditEvent.create({
    data: {
      practiceId: visit.practiceId,
      visitId: visit.id,
      actorId: session.user.id,
      action: 'RETRIED_PUSHES',
      diff: {
        retriedTargets: bestEffortTargets,
        outcomes: outcomes.map((o) => ({
          target: o.target,
          status: o.status,
          summary: 'summary' in o ? o.summary : undefined,
          reason: 'reason' in o ? o.reason : undefined,
          message: 'message' in o ? o.message : undefined,
          httpStatus: 'httpStatus' in o ? o.httpStatus : undefined,
        })),
        failedTargets,
      },
    },
  });

  revalidatePath(`/visits/${visit.id}/review`);
  return { outcomes, failedTargets };
}
