// ============================================================================
// Layer 6 — Final polish (T-M4)
// ----------------------------------------------------------------------------
// Applies the fixable issues from Layer 5's critique to the draft,
// returning the polished SOAP. Unfixable critical issues (e.g. "no
// red-flag screening") are not auto-patched; the note is saved as-is
// with needsReview=true so the clinician sees the gap.
// ============================================================================

import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import {
  classifyCritique,
  type CritiqueReport,
  type CritiqueIssue,
} from './05-self-critique';

const MODEL = 'claude-sonnet-4-6';

export interface Layer6Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  soapDraft: string;
  critique: CritiqueReport;
}

export interface Layer6Output {
  soapFinal: string;
  needsReview: boolean;
  reviewReason: string | null;
  unfixable: CritiqueIssue[];
}

export async function runLayer6Polish(input: Layer6Input): Promise<Layer6Output> {
  const { fixable, unfixable } = classifyCritique(input.critique);
  let soapFinal: string;

  if (fixable.length === 0) {
    // Nothing to auto-patch — the draft itself is our final note.
    // Still persist it so /visits/[id] renders soapFinal rather than
    // soapDraft (simpler UI state machine).
    soapFinal = input.soapDraft;
  } else {
    const system = [
      'You are a clinician editing a SOAP note. A separate auditor has',
      'flagged specific issues; apply ONLY those fixes and return the',
      'complete revised SOAP note in the same markdown structure as the',
      'draft.',
      '',
      'Rules:',
      '- Preserve all clinical content that the auditor did not flag.',
      '- Apply each "suggested_fix" as closely as possible.',
      '- Do NOT introduce new clinical facts. If a fix requires',
      '  information that is not in the draft, leave the flagged area',
      '  as-is and keep moving.',
      '- Output ONLY the revised SOAP markdown. No preamble, no summary',
      '  of changes.',
    ].join('\n');

    const user = [
      'Draft:',
      input.soapDraft,
      '',
      'Issues to apply (apply in order):',
      fixable
        .map(
          (i, idx) =>
            `${idx + 1}. [${i.severity}] ${i.location}: ${i.description}\n    Fix: ${i.suggested_fix}`
        )
        .join('\n'),
    ].join('\n');

    const { text } = await modelClient.completeText({
      practiceId: input.practiceId,
      visitId: input.visitId,
      userId: input.userId,
      purpose: 'tm_polish',
      provider: 'anthropic',
      model: MODEL,
      system,
      user,
      maxTokens: 8192,
      temperature: 0.2,
    });
    soapFinal = text;
  }

  // Surface unfixable critical issues as a review banner reason.
  const reviewReason =
    unfixable.length > 0
      ? `Auto-polish could not fix ${unfixable.length} critical issue${
          unfixable.length === 1 ? '' : 's'
        }: ${unfixable.map((i) => i.description).join('; ')}`
      : !input.critique.safe_to_sign_without_review
        ? 'Auditor flagged issues worth a quick review before signing.'
        : null;

  const needsReview = unfixable.length > 0 || !input.critique.safe_to_sign_without_review;

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      soapFinal,
      // T-M14.1: immutable snapshot of the AI's final output. soapFinal
      // gets overwritten when the doctor edits; soapL6Original does not.
      // The sign-time capture hook reads this to record the
      // (original_ai, doctor_edited) pair into doctor_edit_patterns.
      // Always written alongside soapFinal so the two columns agree at
      // the end of a clean pipeline run.
      soapL6Original: soapFinal,
      ...(needsReview
        ? { needsReview: true, reviewReason }
        : {}),
    },
  });

  return { soapFinal, needsReview, reviewReason, unfixable };
}
