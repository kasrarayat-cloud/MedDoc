// TEMP eval — generation coherence for the WM_IOV template (real Opus, anchors
// ON). Assembles the template DETERMINISTICALLY from the content-control
// extraction (isolating GENERATION behaviour from parse-LLM variance), routes
// it through the ultrasound builder via a dense synthetic reflux dictation,
// and prints the filled report + verifier split for grading.
import { readFileSync } from 'node:fs';
import { modelClient, wrapAsData } from '@meddoc/ai';
import {
  buildSoapUserPrompt,
  type ResolvedNoteTemplate,
} from '../../src/worker/note-templates/build-soap-prompt';
import { buildUltrasoundSystemPrompt } from '../../src/worker/note-templates/build-ultrasound-prompt';
import { ULTRASOUND_REPORT_TEMPLATE } from '../../src/worker/note-templates/ultrasound-report-template';
import { ANCHOR_GENERATION_ADDENDUM, runAnchorVerify } from '../../src/worker/layers/04b-anchor-verify';
import { docxToText } from '../../src/lib/note-template-parse/docx-to-text';

// Slice the extracted marker text into the report's sections (deterministic).
function slice(text: string, start: string, end: string | null): string {
  const i = text.indexOf(start);
  if (i < 0) return '';
  const from = i + start.length;
  const j = end ? text.indexOf(end, from) : text.length;
  return text.slice(from, j < 0 ? text.length : j).trim();
}

async function buildTemplate(docxPath: string): Promise<ResolvedNoteTemplate> {
  const text = await docxToText(new Uint8Array(readFileSync(docxPath)));
  const metadata = slice(text, 'SIDE OF EXAM:', 'TECHNIQUE');
  const technique = slice(text, 'TECHNIQUE', 'FINDINGS');
  const findings = slice(text, 'FINDINGS', 'IMPRESSION');
  const impression = slice(text, 'IMPRESSION', 'DIAMETER AND REFLUX');
  const sp = ULTRASOUND_REPORT_TEMPLATE.styleProfile;
  const sect = (
    key: string,
    label: string,
    order: number,
    defaultText: string | null,
    structure: ResolvedNoteTemplate['sections'][number]['structure'] = null
  ) => ({
    key, label, order, formatHint: 'prose' as const,
    styleInstructions: null, defaultText,
    defaultTextMode: (defaultText ? 'scaffold_confirm' : 'omit_unless_supported') as
      | 'scaffold_confirm' | 'omit_unless_supported',
    structure,
  });
  const veinRows = [
    'GSV at the SFJ', 'GSV at the Proximal Thigh', 'GSV at the Knee', 'GSV Below Knee',
    'SSV at the SPJ', 'SSV at the Proximal Calf', 'AAGSV at the SFJ', 'AAGSV at the Proximal Thigh',
    'PAGSV at the SFJ', 'PAGSV at the Proximal Thigh',
  ];
  return {
    id: 'tmpl_iov', version: 1, isSystemDefault: false, styleProfile: sp,
    sections: [
      sect('exam_metadata', 'Exam Metadata', 1, 'SIDE OF EXAM: ' + metadata),
      sect('technique', 'Technique', 2, technique),
      sect('findings', 'Findings', 3, findings),
      sect('impression', 'Impression', 4, impression),
      sect('diameter_reflux', 'Diameter and Reflux Time', 5, null, {
        kind: 'table', columns: ['Vein / Segment', 'Diameter (mm)', 'Reflux Time (ms)'], rowLabels: veinRows,
      }),
    ],
  } as ResolvedNoteTemplate;
}

const DICTATION = [
  'Doctor: This is a bilateral detailed venous duplex ultrasound of the lower extremities.',
  'The patient presents with leg pain, swelling, and heaviness in the legs.',
  'On the right side, the great saphenous vein had previous endovenous ablation and there has been a recurrence,',
  'with reflux now seen from the saphenofemoral junction down to the mid thigh.',
  'The right great saphenous vein diameter at the saphenofemoral junction is 6.2 millimeters with a reflux time of 3.4 seconds.',
  'At the knee, the right great saphenous vein measures 4.1 millimeters with a reflux time of 1.8 seconds.',
  'Impression: the right great saphenous vein is reflux positive.',
  'The right deep venous system shows no evidence of acute or chronic deep vein thrombosis.',
  'The diagnosis is varicose veins of the right lower extremity with other complications.',
  'The left leg was screened and is essentially normal, with no significant saphenous reflux and a normal deep system.',
].join(' ');

async function main() {
  const template = await buildTemplate(process.argv[2]);
  const system =
    buildUltrasoundSystemPrompt(template, {
      specialty: 'ultrasound', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null,
    }) + ANCHOR_GENERATION_ADDENDUM;
  const user = buildSoapUserPrompt({
    specialty: 'ultrasound', entitiesJson: '{}', wrappedTranscript: wrapAsData(DICTATION, 'transcript').wrapped,
  });
  const { text: raw } = await modelClient.completeText({
    practiceId: 'iov-eval', visitId: null, userId: null, purpose: 'tm_soap_draft', provider: 'anthropic',
    model: process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8',
    system, user, maxTokens: 8192, temperature: 0.2,
  });
  const verified = await runAnchorVerify({
    visitId: 'iov', practiceId: 'iov', userId: null, anchoredDraft: raw, roleLabeledTranscript: DICTATION,
  });
  console.log('=== VERIFIED BODY (into note) ===\n' + verified.body);
  console.log('\n=== SUGGESTIONS LANE (held back) ===');
  for (const s of verified.suggestions) console.log(`  [${s.reason}] ${s.text.slice(0, 120)}`);
  const out = process.argv[3];
  if (out) {
    const { writeFileSync } = await import('node:fs');
    writeFileSync(out, JSON.stringify({ raw, body: verified.body, suggestions: verified.suggestions }, null, 2));
    console.log('\n[wrote]', out);
  }
}
main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
