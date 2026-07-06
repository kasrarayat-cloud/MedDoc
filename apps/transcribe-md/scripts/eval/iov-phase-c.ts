// TEMP eval — Phase C of the scaffold-exemption pre-registration.
// Generate the WM_IOV anchored draft ONCE (real Opus), then run runAnchorVerify
// BEFORE (no scaffold = main behavior, proven byte-identical) vs AFTER (scaffold
// supplied), BOTH with the REAL entailment judge, and report body/lane deltas.
// Pre-reg: docs/eval-runs/verifier-scaffold-exemption-20260706T202636Z.md
import { readFileSync, writeFileSync } from 'node:fs';
import { modelClient, wrapAsData } from '@meddoc/ai';
import { buildSoapUserPrompt, type ResolvedNoteTemplate } from '../../src/worker/note-templates/build-soap-prompt';
import { buildUltrasoundSystemPrompt } from '../../src/worker/note-templates/build-ultrasound-prompt';
import { ULTRASOUND_REPORT_TEMPLATE } from '../../src/worker/note-templates/ultrasound-report-template';
import { ANCHOR_GENERATION_ADDENDUM, runAnchorVerify } from '../../src/worker/layers/04b-anchor-verify';
import { buildTemplateScaffold } from '../../src/worker/note-templates/template-scaffold';
import { docxToText } from '../../src/lib/note-template-parse/docx-to-text';

const SCRATCH = '/tmp/claude-1000/-opt-meddoc-pro/586b3f3f-7eed-4f8e-ac7f-e25626e93305/scratchpad/iov';

function slice(text: string, start: string, end: string | null): string {
  const i = text.indexOf(start); if (i < 0) return '';
  const from = i + start.length; const j = end ? text.indexOf(end, from) : text.length;
  return text.slice(from, j < 0 ? text.length : j).trim();
}
async function buildTemplate(): Promise<ResolvedNoteTemplate> {
  const text = await docxToText(new Uint8Array(readFileSync(`${SCRATCH}/WM_IOV_Template.docx`)));
  const sp = ULTRASOUND_REPORT_TEMPLATE.styleProfile;
  const sect = (key: string, label: string, order: number, defaultText: string | null, structure: any = null) => ({
    key, label, order, formatHint: 'prose' as const, styleInstructions: null, defaultText,
    defaultTextMode: (defaultText ? 'scaffold_confirm' : 'omit_unless_supported') as any, structure,
  });
  const rows = ['GSV at the SFJ','GSV at the Proximal Thigh','GSV at the Knee','GSV Below Knee','SSV at the SPJ','SSV at the Proximal Calf','AAGSV at the SFJ','AAGSV at the Proximal Thigh','PAGSV at the SFJ','PAGSV at the Proximal Thigh'];
  return { id: 'tmpl_iov', version: 1, isSystemDefault: false, styleProfile: sp, sections: [
    sect('exam_metadata', 'Exam Metadata', 1, 'SIDE OF EXAM: ' + slice(text, 'SIDE OF EXAM:', 'TECHNIQUE')),
    sect('technique', 'Technique', 2, slice(text, 'TECHNIQUE', 'FINDINGS')),
    sect('findings', 'Findings', 3, slice(text, 'FINDINGS', 'IMPRESSION')),
    sect('impression', 'Impression', 4, slice(text, 'IMPRESSION', 'DIAMETER AND REFLUX')),
    sect('diameter_reflux', 'Diameter and Reflux Time', 5, null, { kind: 'table', columns: ['Vein / Segment', 'Diameter (mm)', 'Reflux Time (ms)'], rowLabels: rows }),
  ] } as ResolvedNoteTemplate;
}

const DICTATION = [
  'This is a bilateral detailed venous duplex ultrasound of the lower extremities.',
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

const bodyLines = (b: string) => b.split('\n').filter((l) => l.trim() && !/^##\s/.test(l) && !/All AI-drafted content/.test(l));

async function main() {
  const template = await buildTemplate();
  const scaffold = buildTemplateScaffold(template.sections);
  const system = buildUltrasoundSystemPrompt(template, { specialty: 'ultrasound', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null }) + ANCHOR_GENERATION_ADDENDUM;
  const user = buildSoapUserPrompt({ specialty: 'ultrasound', entitiesJson: '{}', wrappedTranscript: wrapAsData(DICTATION, 'transcript').wrapped });
  const { text: raw } = await modelClient.completeText({
    practiceId: 'iov-eval', visitId: null, userId: null, purpose: 'tm_soap_draft', provider: 'anthropic',
    model: process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8', system, user, maxTokens: 8192, temperature: 0.2,
  });
  console.log(`[gen] draft ${raw.length} chars, ${(raw.match(/⟦A:/g) ?? []).length} anchors`);

  const ids = { visitId: 'iov', practiceId: 'iov', userId: null };
  const before = await runAnchorVerify({ ...ids, anchoredDraft: raw, roleLabeledTranscript: DICTATION }); // no scaffold = main
  const after = await runAnchorVerify({ ...ids, anchoredDraft: raw, roleLabeledTranscript: DICTATION, templateScaffold: scaffold });

  const bBody = bodyLines(before.body), aBody = bodyLines(after.body);
  const bLane = before.suggestions.map((s) => s.text.trim());
  const aLane = after.suggestions.map((s) => s.text.trim());
  const recovered = aBody.filter((l) => !bBody.includes(l));
  const newlyDemoted = aLane.filter((t) => !bLane.includes(t));

  console.log(`\n[BEFORE] body lines=${bBody.length}  lane=${before.suggestions.length}`);
  console.log(`[AFTER ] body lines=${aBody.length}  lane=${after.suggestions.length}`);
  console.log(`\n[RECOVERED into body] (${recovered.length}):`);
  for (const l of recovered) {
    const kind = scaffold.fixedLines.has(l.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim()) ? 'FIXED' : 'carrier/other';
    console.log(`  [${kind}] ${l.slice(0, 110)}`);
  }
  console.log(`\n[NEWLY DEMOTED] (must be 0): ${newlyDemoted.length}`);
  for (const l of newlyDemoted) console.log(`  !! ${l.slice(0, 110)}`);
  console.log(`\n[AFTER lane — still demoted]:`);
  for (const s of after.suggestions) console.log(`  [${s.reason}] ${s.text.slice(0, 100)}`);
  writeFileSync(`${SCRATCH}/phase-c.json`, JSON.stringify({ raw, before: { body: before.body, lane: before.suggestions }, after: { body: after.body, lane: after.suggestions } }, null, 2));
}
main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
