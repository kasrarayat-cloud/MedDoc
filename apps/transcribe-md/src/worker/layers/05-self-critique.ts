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
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import type { ExtractedEntities } from './03-extract-entities';

const MODEL = 'claude-sonnet-4-6';

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
}

export async function runLayer5SelfCritique(
  input: Layer5Input
): Promise<CritiqueReport> {
  const system = [
    'You are an auditor reviewing a SOAP note for clinical quality. The',
    'note was generated from a transcript + extracted entities by a',
    'separate system. Your job is to identify issues using these rules:',
    '',
    'CRITICAL issues (must fix):',
    '1. Any factual claim in the SOAP that CANNOT be traced to the',
    '   transcript or entities — i.e. hallucination.',
    '2. Internal contradictions between sections (e.g. Assessment',
    '   disagrees with Subjective).',
    '3. Missing red-flag screening for the presenting complaint.',
    '   Examples: "chest pain" without SOB/radiation/diaphoresis',
    '   screen; new-onset headache in an adult without red-flag',
    '   questions; pediatric fever without hydration/activity check.',
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
  ].join('\n');

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
    input.roleLabeledTranscript,
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
    temperature: 0.2,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
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
  return true;
}
