// ============================================================================
// Layer 4 — SOAP note generation (T-M4)
// ----------------------------------------------------------------------------
// Input: entities (Layer 3) + role-labeled transcript + specialty slug.
// Output: a markdown SOAP draft that tries hard to stay within what the
// transcript actually supports. The prompt forces the model to signal
// uncertainty rather than paper over it — "[not documented]" or
// "Per patient, …" are encouraged where the ground truth is weak.
// ============================================================================

import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { specialtyGuidance } from '../prompts/specialty-guidance';
import type { ExtractedEntities } from './03-extract-entities';

const MODEL = 'claude-sonnet-4-6';

export interface Layer4Input {
  visitId: string;
  practiceId: string;
  specialty: string;
  roleLabeledTranscript: string;
  entities: ExtractedEntities;
}

export async function runLayer4GenerateSoap(
  input: Layer4Input
): Promise<string> {
  const guidance = specialtyGuidance(input.specialty);

  const system = [
    'You are a senior clinician writing a SOAP note from a clinical',
    'visit. Use ONLY the entities provided and the transcript as',
    'evidence. Write in a professional medical tone.',
    '',
    'Structure the note with these markdown headings exactly:',
    '',
    '## Subjective',
    '**Chief Complaint:** …',
    '**HPI:** narrative paragraph incorporating onset, duration,',
    '  quality, severity, location, timing, context, modifying factors,',
    '  associated symptoms.',
    '**PMH:** bullet list or "[not documented]" if silent.',
    '**Medications:** bullet list with dose/route/frequency where stated.',
    '**Allergies:** bullet list with reactions where stated.',
    '**Family History:** brief list or "[not documented]".',
    '**Social History:** smoking / alcohol / drugs / occupation if',
    '  mentioned; omit unmentioned lines.',
    '**ROS:** by system when documented; else the single line',
    '  "ROS not formally documented in this encounter."',
    '',
    '## Objective',
    'Physical exam findings grouped by system. Include vitals if',
    'mentioned. Include test results mentioned. If no formal exam was',
    'discussed, write exactly: "Formal exam not documented in this',
    'encounter."',
    '',
    '## Assessment',
    'Primary clinical consideration with supporting reasoning.',
    'Differentials if the doctor discussed them. Severity/staging if',
    'applicable. Use [not documented] rather than inventing.',
    '',
    '## Plan',
    'Numbered list: diagnostics ordered, medications changed/started,',
    'follow-up, referrals, patient education. Each item should be',
    'actionable.',
    '',
    'Critical rules:',
    '- Do NOT invent clinical findings. If a claim lacks transcript',
    '  evidence, either omit it or explicitly mark it "[not documented]".',
    '- When information came exclusively from the patient, prefix with',
    '  "Per patient, …" so the source is clear on downstream review.',
    '- Never add test results, medication doses, or vital-sign numbers',
    '  that were not stated.',
    '- Output ONLY the SOAP note markdown. No preamble, no postscript.',
    guidance ? '' : undefined,
    guidance ? `Specialty guidance (${input.specialty}):\n${guidance}` : undefined,
  ]
    .filter((l): l is string => typeof l === 'string')
    .join('\n');

  const user = [
    `Specialty: ${input.specialty}`,
    '',
    'Extracted entities (structured, with evidence):',
    JSON.stringify(input.entities, null, 2),
    '',
    'Role-labeled transcript:',
    input.roleLabeledTranscript,
  ].join('\n');

  const { text } = await modelClient.completeText({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_soap_draft',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    maxTokens: 8192,
    temperature: 0.2,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { soapDraft: text },
  });

  return text;
}
