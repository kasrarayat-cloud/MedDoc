import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { OutputType } from '@prisma/client';
import prisma from '@meddoc/db';
import {
  SoapNoteSchema,
  CodingOutputSchema,
  RxOutputSchema,
  ReferralOutputSchema,
  PatientSummarySchema,
  OutputErrorSchema,
  type SoapNote,
  type CodingOutput,
  type RxOutput,
  type ReferralOutput,
  type PatientSummary,
  type OutputError,
} from '@meddoc/types';
import type { z } from 'zod';
import { getSession } from '@/lib/auth';
import { tenantScope } from '@meddoc/auth';
import ReviewClient, { type LoadedOutput } from './ReviewClient';

export const dynamic = 'force-dynamic';

/**
 * Narrow one ScribeOutput row's content blob into a success-shaped
 * LoadedOutput or an OutputError-shaped LoadedOutput. An unparseable
 * blob falls back to a generic error so the UI shows something useful
 * instead of crashing.
 */
function loadOutput<T>(
  content: unknown,
  successSchema: z.ZodType<T>
): LoadedOutput<T> {
  const successParse = successSchema.safeParse(content);
  if (successParse.success) {
    return { kind: 'ok', data: successParse.data };
  }
  const errorParse = OutputErrorSchema.safeParse(content);
  if (errorParse.success) {
    return { kind: 'error', error: errorParse.data._error };
  }
  // Corrupted row — surface as an error so the reviewer isn't silently
  // stuck.
  const fallback: OutputError['_error'] = {
    code: 'SCHEMA_FAIL',
    message: 'Stored output does not match any known schema for this type.',
    attempts: 0,
    occurredAt: new Date().toISOString(),
  };
  return { kind: 'error', error: fallback };
}

async function latestOutput(visitId: string, type: OutputType) {
  return prisma.scribeOutput.findFirst({
    where: { visitId, type },
    orderBy: { createdAt: 'desc' },
    select: { content: true },
  });
}

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = (await getSession())!;

  const visit = await prisma.scribeVisit.findFirst({
    where: { id, ...tenantScope(session), deletedAt: null },
    select: {
      id: true,
      status: true,
      patient: { select: { firstName: true, lastName: true, chartId: true } },
      specialty: { select: { displayName: true, version: true } },
    },
  });
  if (!visit) notFound();

  const [soapRow, codingRow, rxRow, referralsRow, summaryRow] = await Promise.all([
    latestOutput(visit.id, 'SOAP'),
    latestOutput(visit.id, 'ICD10_CPT'),
    latestOutput(visit.id, 'RX'),
    latestOutput(visit.id, 'REFERRAL'),
    latestOutput(visit.id, 'PATIENT_SUMMARY'),
  ]);

  if (visit.status === 'SIGNED') {
    return (
      <div className="max-w-3xl mx-auto space-y-4">
        <Link href={`/visits/${visit.id}`} className="text-sm text-slate-400 hover:text-slate-200">
          ← Visit
        </Link>
        <div className="border border-slate-700 rounded-xl p-6 bg-slate-900/50 text-sm">
          This visit has been signed and sent to MedDoc Pro. The SOAP note is
          now a clinical note on the patient chart. Other outputs (codes, Rx,
          referrals, patient summary) are locked and visible in Scribe.
        </div>
      </div>
    );
  }

  if (!soapRow) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Link href={`/visits/${visit.id}`} className="text-sm text-slate-400 hover:text-slate-200">
          ← Visit
        </Link>
        <div className="border border-amber-600/40 rounded-xl p-4 bg-amber-500/5 text-sm text-amber-200">
          No outputs yet. Transcription may still be running, or the pipeline
          errored — check the visit page.
        </div>
      </div>
    );
  }

  const initial = {
    soap: loadOutput<SoapNote>(soapRow?.content, SoapNoteSchema),
    coding: codingRow
      ? loadOutput<CodingOutput>(codingRow.content, CodingOutputSchema)
      : ({ kind: 'missing' } as LoadedOutput<CodingOutput>),
    rx: rxRow
      ? loadOutput<RxOutput>(rxRow.content, RxOutputSchema)
      : ({ kind: 'missing' } as LoadedOutput<RxOutput>),
    referrals: referralsRow
      ? loadOutput<ReferralOutput>(referralsRow.content, ReferralOutputSchema)
      : ({ kind: 'missing' } as LoadedOutput<ReferralOutput>),
    summary: summaryRow
      ? loadOutput<PatientSummary>(summaryRow.content, PatientSummarySchema)
      : ({ kind: 'missing' } as LoadedOutput<PatientSummary>),
  };

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div>
        <Link href={`/visits/${visit.id}`} className="text-sm text-slate-400 hover:text-slate-200">
          ← Visit
        </Link>
        <h1 className="text-2xl font-semibold mt-1">
          {visit.patient.chartId ? `${visit.patient.chartId} · ` : ''}
          {visit.patient.lastName}, {visit.patient.firstName}
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          {visit.specialty.displayName} v{visit.specialty.version} · review
        </p>
      </div>

      <ReviewClient
        visitId={visit.id}
        initial={initial}
        canSign={visit.status === 'READY_FOR_REVIEW'}
      />
    </div>
  );
}
