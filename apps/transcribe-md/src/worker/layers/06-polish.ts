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
import { logAudit } from '@/lib/audit';
import {
  classifyCritique,
  type CritiqueReport,
  type CritiqueIssue,
} from './05-self-critique';
import { validateSoapStructure } from './soap-structure-validator';
import {
  requiredSectionLabels,
  type ResolvedNoteTemplate,
} from '../note-templates/build-soap-prompt';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '../note-templates/system-default-template';

const MODEL = 'claude-sonnet-4-6';

export interface Layer6Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  soapDraft: string;
  critique: CritiqueReport;
  /** Phase 1: the resolved template, so polish validates against ITS
   *  structure (not the fixed 4 SOAP headers). Defaults to the system
   *  default — whose labels ARE the 4 SOAP headers, so behavior is
   *  unchanged for non-customizing doctors. The polish prompt already
   *  preserves "the same markdown structure as the draft", so the model
   *  polishes in whatever structure the draft has. */
  noteTemplate?: ResolvedNoteTemplate;
}

export interface Layer6Output {
  soapFinal: string;
  needsReview: boolean;
  reviewReason: string | null;
  unfixable: CritiqueIssue[];
}

export async function runLayer6Polish(input: Layer6Input): Promise<Layer6Output> {
  const { fixable, unfixable } = classifyCritique(input.critique);
  // Phase 1: validate the polished note against the resolved template's
  // required sections. System default → the 4 SOAP headers → unchanged.
  const template: ResolvedNoteTemplate =
    input.noteTemplate ?? SYSTEM_DEFAULT_NOTE_TEMPLATE;
  const requiredSections = requiredSectionLabels(template);
  let soapFinal: string;
  // FIND-P1-016 (2026-05-14) — when the model edits the draft, the
  // output goes through the same SOAP-structure validator L4 uses.
  // Passthrough branch (fixable.length === 0) doesn't need re-validation
  // because L4 already validated `soapDraft` when it landed in the row.
  // On model-call validation fail, the layer still persists the raw
  // output and flips needsReview so a doctor can fix it manually; the
  // audit row gives operators a grep target for prompt regressions.
  let polishValidationFailReason: string | null = null;

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
      // Q2 fix-pack — polish is constrained edit ("apply these fixes").
      // Tightened from 0.2 to 0.1 so the same draft + critique produce
      // the same revised SOAP run-to-run.
      temperature: 0.1,
    });
    soapFinal = text;

    // FIND-P1-016 — same validator L4 uses, now scoped to the resolved
    // template's required sections. Fail → keep raw output, flag the
    // validation reason so the reviewReason calculation below includes it
    // alongside the unfixable-criticals reason.
    const validation = validateSoapStructure(text, requiredSections);
    if (!validation.ok) {
      void logAudit({
        action: 'MODEL_OUTPUT_VALIDATION_FAIL',
        targetType: 'transcribe_visit',
        targetId: input.visitId,
        userId: input.userId,
        practiceId: input.practiceId,
        success: false,
        metadata: {
          layer: 'L6',
          reason: validation.reason,
          outputLength: validation.outputLength,
          missingSections: validation.missingSections,
          // NO raw output — PHI surface.
        },
      });
      polishValidationFailReason = `Polish output didn't match expected markdown structure — manual review required (${validation.reason}).`;
    }
  }

  // Surface unfixable critical issues as a review banner reason. The
  // FIND-P1-016 validation-fail reason (when present) prepends so the
  // operator/clinician sees the most urgent structural issue first.
  const baseReason =
    unfixable.length > 0
      ? `Auto-polish could not fix ${unfixable.length} critical issue${
          unfixable.length === 1 ? '' : 's'
        }: ${unfixable.map((i) => i.description).join('; ')}`
      : !input.critique.safe_to_sign_without_review
        ? 'Auditor flagged issues worth a quick review before signing.'
        : null;
  const reviewReason = polishValidationFailReason
    ? baseReason
      ? `${polishValidationFailReason} ${baseReason}`
      : polishValidationFailReason
    : baseReason;

  const needsReview =
    unfixable.length > 0 ||
    !input.critique.safe_to_sign_without_review ||
    polishValidationFailReason !== null;

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
