// ============================================================================
// Layer 5 — Self-critique (T-M4)
// ----------------------------------------------------------------------------
// Input: Layer 4 SOAP draft + Layer 3 entities + role-labeled transcript.
// Output: a list of issues (critical / major / minor) with suggested
// fixes, an overall quality rating, and a boolean
// safe_to_sign_without_review. Layer 6 consumes this.
//
// Done as a fresh prompt rather than chain-of-thought because we want
// the audit to be an INDEPENDENT pass that can disagree with the
// draft. Keep Layer 6 the only place that edits the note.
// ============================================================================

import { z } from 'zod';
import { modelClient, wrapAsData, delimiterSystemSuffix } from '@meddoc/ai';
import { updateTemplateTwinSyntheticQaClaimBoundVisit } from '@/worker/staging-qa-mutation-fence';
import type { ExtractedEntities } from './03-extract-entities';
import { logAudit } from '@/lib/audit';
import {
  shouldFlagForReview,
  LOW_CONFIDENCE_THRESHOLD,
  type AudioConfidenceStats,
} from './audio-confidence';
import {
  insertedDefaultSections,
  type ResolvedNoteTemplate,
} from '../note-templates/build-soap-prompt';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '../note-templates/system-default-template';

// TRANSCRIBE_MD_CLINICAL_MODEL — eval override (feat/fable5-eval); unset → default unchanged.
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8';

export const CritiqueIssue = z.object({
  severity: z.enum(['critical', 'major', 'minor']),
  location: z.string(),
  description: z.string(),
  suggested_fix: z.string(),
});
export type CritiqueIssue = z.infer<typeof CritiqueIssue>;

export const CritiqueReport = z.object({
  issues: z.array(CritiqueIssue).default([]),
  overall_quality: z.enum(['high', 'medium', 'low']),
  safe_to_sign_without_review: z.boolean(),
});
export type CritiqueReport = z.infer<typeof CritiqueReport>;

export interface Layer5Input {
  visitId: string;
  practiceId: string;
  userId: string | null;
  specialty: string;
  soapDraft: string;
  roleLabeledTranscript: string;
  entities: ExtractedEntities;
  /** Round 3 quality fix-pack Q0-5 — visit-level Deepgram confidence
   *  signal. When set AND `shouldFlagForReview(...)` is true, the
   *  L5 critique prompt is expanded so the auditor is more willing
   *  to flag SOAP content that asserts as fact something the audio
   *  doesn't clearly support. Null for text_notes and dictation runs
   *  without utterance segmentation. Closes audit Findings 02.5 + 07.3. */
  audioConfidenceStats: AudioConfidenceStats | null;
  /** Phase 1: the resolved template. When it inserted scaffold/always-include
   *  defaults, L5 gains a normals-scrutiny block that flags unsupported
   *  inserted findings for review. Defaults to the system default — whose
   *  sections are all omit_unless_supported, so NOTHING is inserted and the
   *  critique prompt is byte-identical to today. */
  noteTemplate?: ResolvedNoteTemplate;
}

export async function runLayer5SelfCritique(
  input: Layer5Input,
): Promise<CritiqueReport> {
  // Round 3 PR-J — A07-P0 prompt-injection delimiter (mirrors L4).
  const wrap = wrapAsData(input.roleLabeledTranscript, 'transcript');
  if (wrap.injectionAttemptDetected) {
    void logAudit({
      action: 'PIPELINE_REJECTED_INJECTION_DELIMITER',
      targetType: 'transcribe_visit',
      targetId: input.visitId,
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      errorCode: 'INJECTION_DELIMITER_DETECTED',
      metadata: { layer: 'L5', suffix: wrap.suffix },
    });
  }

  // Round 3 quality fix-pack Q0-5 (audit Findings 02.5 + 07.3) —
  // when L1 reports the audio was mostly low-confidence, expand the
  // prompt so the auditor is MORE willing to flag SOAP content that
  // asserts as fact something the audio didn't clearly support. The
  // critique then surfaces these cases as critical issues for L6 to
  // hedge / strip during polish.
  const audioStats = input.audioConfidenceStats;
  const lowConfidence = audioStats ? shouldFlagForReview(audioStats) : false;
  const audioQualityAlert =
    lowConfidence && audioStats
      ? [
          'AUDIO QUALITY ALERT: this transcript was produced from audio',
          `with median confidence ${audioStats.median.toFixed(2)} and`,
          `${audioStats.lowConfPct.toFixed(0)}% of utterances below ${LOW_CONFIDENCE_THRESHOLD} confidence.`,
          'Be MORE willing to flag SOAP content that asserts as fact',
          "something the audio doesn't clearly support. When a quoted",
          'detail (specific numbers, doses, durations) does not appear',
          'in the transcript, treat that as a CRITICAL hallucination',
          'issue regardless of how plausible the value sounds.',
        ].join('\n')
      : null;

  // Phase 1 normals-scrutiny (additive — strengthens L5, removes nothing).
  // When the resolved template inserted default text (scaffold_confirm /
  // always_include), instruct the auditor to verify those inserted findings
  // against the transcript and flag unsupported ones. Empty for the system
  // default (all sections omit_unless_supported → nothing inserted) → null →
  // the critique prompt is byte-identical to today.
  const template: ResolvedNoteTemplate =
    input.noteTemplate ?? SYSTEM_DEFAULT_NOTE_TEMPLATE;
  const insertedSections = insertedDefaultSections(template);
  const normalsScrutinyAlert =
    insertedSections.length > 0
      ? [
          'TEMPLATE-DEFAULT SCRUTINY: the SOAP draft may contain text inserted',
          'from the note template as a default/scaffold (NOT derived from this',
          `encounter) in these sections: ${insertedSections
            .map((s) => s.label)
            .join(', ')}.`,
          'For each such inserted finding, verify it is actually supported by',
          'the transcript or entities. If an inserted finding is NOT supported,',
          'raise it as a CRITICAL issue whose description begins "Unsupported',
          'template default:" so it is surfaced for clinician review rather',
          'than silently kept. Supported inserted content needs no issue.',
        ].join('\n')
      : null;

  const system = [
    'You are an auditor reviewing a SOAP note for clinical quality. The',
    'note was generated from a transcript + extracted entities by a',
    'separate system. Your job is to identify issues using these rules:',
    '',
    audioQualityAlert,
    audioQualityAlert ? '' : null,
    normalsScrutinyAlert,
    normalsScrutinyAlert ? '' : null,
    'CRITICAL issues (must fix):',
    '1. Any factual claim in the SOAP that CANNOT be traced to the',
    '   transcript or entities — i.e. hallucination.',
    '2. Internal contradictions between sections (e.g. Assessment',
    '   disagrees with Subjective).',
    '3. Missing red-flag screening for the presenting complaint.',
    '   Examples: "chest pain" without SOB/radiation/diaphoresis',
    '   screen; new-onset headache in an adult without red-flag',
    '   questions; pediatric fever without hydration/activity check.',
    // 2026-06-11 inaudible-span hardening — aim the critique at the class
    // the transcript markers now make visible.
    '3b. Any claim whose only transcript support overlaps an',
    '   "[unclear in recording]" marker — a medication, dose, diagnosis,',
    '   finding, or name asserted where the audio was unintelligible is a',
    '   CRITICAL hallucination-class issue: the note must carry the marker',
    '   (hedged), never a guessed value. Also flag patient-reported',
    '   sensations rewritten as examination findings when no exam is',
    '   documented in the transcript.',
    '',
    'MAJOR issues (should fix):',
    '4. Assessment not supported by Subjective + Objective.',
    '5. Plan does not address the Assessment.',
    '6. Significant information in the transcript omitted from the note.',
    '7. Specialty-inappropriate framing.',
    '',
    'MINOR issues (nice to fix):',
    '8. Unclear phrasing.',
    '9. Redundancy across sections.',
    '10. Suboptimal structure.',
    '',
    'For overall_quality: "high" when there are zero critical issues',
    'and at most one major; "medium" when there are <=1 critical and',
    '<=3 major; "low" otherwise.',
    '',
    'For safe_to_sign_without_review: true ONLY when there are zero',
    'critical issues AND overall_quality is high.',
    '',
    'Respond with VALID JSON ONLY, no markdown fences:',
    '{',
    '  "issues": [ { "severity": "critical|major|minor",',
    '                "location": "Subjective/HPI",',
    '                "description": "...",',
    '                "suggested_fix": "..." } ],',
    '  "overall_quality": "high|medium|low",',
    '  "safe_to_sign_without_review": true|false',
    '}',
    // Round 3 PR-J — instruction-as-data boundary.
    delimiterSystemSuffix('transcript'),
  ]
    .filter((l): l is string => typeof l === 'string')
    .join('\n');

  const user = [
    `Specialty: ${input.specialty}`,
    '',
    'SOAP draft (the artifact under audit):',
    input.soapDraft,
    '',
    'Extracted entities (the structured inputs the draft was built from):',
    JSON.stringify(input.entities, null, 2),
    '',
    'Role-labeled transcript (the ground truth):',
    wrap.wrapped,
  ].join('\n');

  const report = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: 'tm_critique',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: CritiqueReport,
    maxTokens: 4096,
    // Q2 fix-pack §08.2 — critique is the audit pass. Same SOAP audited
    // twice should produce the same critique. Tightened from 0.2 to 0.1
    // so safe_to_sign_without_review doesn't oscillate run-to-run.
    temperature: 0.1,
  });

  await updateTemplateTwinSyntheticQaClaimBoundVisit({
    visitId: input.visitId,
    userId: input.userId ?? '',
    practiceId: input.practiceId,
    data: { critique: report as unknown as object },
  });

  return report;
}

/** Classifies issues the automation can fix vs ones that require a
 *  human (e.g. "no red-flag screening documented" — Layer 6 can't
 *  invent red-flag answers). */
export function classifyCritique(report: CritiqueReport): {
  fixable: CritiqueIssue[];
  unfixable: CritiqueIssue[];
} {
  const fixable: CritiqueIssue[] = [];
  const unfixable: CritiqueIssue[] = [];
  for (const issue of report.issues) {
    if (isStructurallyFixable(issue)) fixable.push(issue);
    else unfixable.push(issue);
  }
  return { fixable, unfixable };
}

function isStructurallyFixable(issue: CritiqueIssue): boolean {
  // Criteria for "Layer 6 can apply this without new clinical data":
  // - All minor/major issues are by definition prose-level fixable.
  // - Critical "hallucination" and "contradiction" are fixable (remove
  //   or rewrite the offending line).
  // - Critical "missing red-flag screening" is NOT fixable — we don't
  //   have the answers; the clinician has to add them manually.
  if (issue.severity !== 'critical') return true;
  const d = issue.description.toLowerCase();
  if (
    d.includes('red flag') ||
    d.includes('red-flag') ||
    d.includes('screening missing') ||
    d.includes('missing red')
  ) {
    return false;
  }
  // Phase 1 normals-scrutiny: an unsupported template-default finding must
  // NOT be auto-patched away — it surfaces for clinician review, same posture
  // as missing red-flag screening. Additive; existing classes unchanged.
  if (
    d.includes('unsupported template default') ||
    d.includes('unsupported inserted')
  ) {
    return false;
  }
  return true;
}
