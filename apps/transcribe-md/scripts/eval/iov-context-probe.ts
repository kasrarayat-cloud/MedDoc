// TEMP eval — context-field defaults, deterministic (isolated from parse
// variance). Builds the IOV template + sets styleProfile.contextDefaults,
// mirrors 04-generate-soap's wiring (applyContextDefaults BEFORE prompt +
// scaffold), generates (real Opus), and confirms the context fields render the
// doctor's picks while dictatable slots still fill and the body stays full.
import { readFileSync } from 'node:fs';
import { modelClient, wrapAsData } from '@meddoc/ai';
import { buildSoapUserPrompt, type ResolvedNoteTemplate } from '../../src/worker/note-templates/build-soap-prompt';
import { buildUltrasoundSystemPrompt } from '../../src/worker/note-templates/build-ultrasound-prompt';
import { ULTRASOUND_REPORT_TEMPLATE } from '../../src/worker/note-templates/ultrasound-report-template';
import { ANCHOR_GENERATION_ADDENDUM, runAnchorVerify } from '../../src/worker/layers/04b-anchor-verify';
import { buildTemplateScaffold } from '../../src/worker/note-templates/template-scaffold';
import { applyContextDefaults } from '../../src/lib/note-template-context';
import { docxToText } from '../../src/lib/note-template-parse/docx-to-text';

// docx path from argv[2] (like the sibling probes); scratch dir for outputs.
const DOCX = process.argv[2] ?? `${process.env.HOME}/WM_IOV_Template.docx`;
const S = process.env.IOV_SCRATCH ?? '/tmp/iov-eval';
function slice(t: string, a: string, b: string | null) {
  const i = t.indexOf(a); if (i < 0) return ''; const from = i + a.length;
  const j = b ? t.indexOf(b, from) : t.length; return t.slice(from, j < 0 ? t.length : j).trim();
}

const CONTEXT_DEFAULTS = {
  referringPhysician: 'Khashayar Sarabi, MD, RPVI',
  machine: 'Mindray M7, L12-4s MHz Transducer',
  location: 'Long Beach, CA',
};
const DICTATION = [
  'This is a bilateral detailed venous duplex ultrasound of the lower extremities.',
  'The patient presents with leg pain, swelling, and heaviness in the legs.',
  'On the right side, the great saphenous vein had previous endovenous ablation and there has been a recurrence,',
  'with reflux now seen from the saphenofemoral junction down to the mid thigh.',
  'The right great saphenous vein diameter at the saphenofemoral junction is 6.2 millimeters with a reflux time of 3.4 seconds.',
  'Impression: the right great saphenous vein is reflux positive.',
  'The right deep venous system shows no evidence of acute or chronic deep vein thrombosis.',
  'The diagnosis is varicose veins of the right lower extremity with other complications.',
  'The left leg was screened and is essentially normal, with no significant saphenous reflux and a normal deep system.',
].join(' ');

async function main() {
  const text = await docxToText(new Uint8Array(readFileSync(DOCX)));
  const sp = { ...ULTRASOUND_REPORT_TEMPLATE.styleProfile, contextDefaults: CONTEXT_DEFAULTS };
  const sect = (key: string, label: string, order: number, dt: string | null, structure: any = null) => ({
    key, label, order, formatHint: 'prose' as const, styleInstructions: null, defaultText: dt,
    defaultTextMode: (dt ? 'scaffold_confirm' : 'omit_unless_supported') as any, structure,
  });
  const rows = ['GSV at the SFJ', 'GSV at the Proximal Thigh', 'GSV at the Knee', 'GSV Below Knee', 'SSV at the SPJ', 'SSV at the Proximal Calf', 'AAGSV at the SFJ', 'AAGSV at the Proximal Thigh', 'PAGSV at the SFJ', 'PAGSV at the Proximal Thigh'];
  const resolvedTemplate = {
    id: 'tmpl_iov', version: 1, isSystemDefault: false, styleProfile: sp, sections: [
      sect('exam_metadata', 'Exam Metadata', 1, 'SIDE OF EXAM: ' + slice(text, 'SIDE OF EXAM:', 'TECHNIQUE')),
      sect('technique', 'Technique', 2, slice(text, 'TECHNIQUE', 'FINDINGS')),
      sect('findings', 'Findings', 3, slice(text, 'FINDINGS', 'IMPRESSION')),
      sect('impression', 'Impression', 4, slice(text, 'IMPRESSION', 'DIAMETER AND REFLUX')),
      sect('diameter_reflux', 'Diameter and Reflux Time', 5, null, { kind: 'table', columns: ['Vein / Segment', 'Diameter (mm)', 'Reflux Time (ms)'], rowLabels: rows }),
    ],
  } as ResolvedNoteTemplate;

  // MIRROR 04-generate-soap: apply context defaults BEFORE prompt + scaffold.
  const template: ResolvedNoteTemplate = {
    ...resolvedTemplate,
    sections: applyContextDefaults(resolvedTemplate.sections, resolvedTemplate.styleProfile.contextDefaults ?? null),
  };
  const scaffold = buildTemplateScaffold(template.sections);
  const system = buildUltrasoundSystemPrompt(template, { specialty: 'ultrasound', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null }) + ANCHOR_GENERATION_ADDENDUM;
  const user = buildSoapUserPrompt({ specialty: 'ultrasound', entitiesJson: '{}', wrappedTranscript: wrapAsData(DICTATION, 'transcript').wrapped });
  const { text: raw } = await modelClient.completeText({ practiceId: 'iov-eval', visitId: null, userId: null, purpose: 'tm_soap_draft', provider: 'anthropic', model: process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8', system, user, maxTokens: 8192, temperature: 0.2 });
  const v = await runAnchorVerify({ visitId: 'iov', practiceId: 'iov', userId: null, anchoredDraft: raw, roleLabeledTranscript: DICTATION, templateScaffold: scaffold });

  const body = v.body;
  console.log('=== prompt shows RESOLVED context (no context slot for the model) ===');
  console.log('  REFERRING PHYSICIAN resolved in prompt:', system.includes('REFERRING PHYSICIAN: Khashayar Sarabi, MD, RPVI'));
  console.log('  MACHINE resolved in prompt:', system.includes('MACHINE: Mindray M7, L12-4s MHz Transducer'));
  console.log('  LOCATION resolved in prompt:', system.includes('LOCATION: Long Beach, CA'));
  console.log('  ULTRASOUND TECHNOLOGIST (per-visit) → [not documented]:', system.includes('ULTRASOUND TECHNOLOGIST: [not documented]'));
  console.log('  no context {{one of}} left in prompt for physician/machine/location:', !/REFERRING PHYSICIAN: \{\{one of/.test(system) && !/MACHINE: \{\{one of/.test(system) && !/LOCATION: \{\{one of/.test(system));
  console.log('  SIDE OF EXAM still a dictatable slot in prompt:', /SIDE OF EXAM: \{\{one of/.test(system));
  console.log('\n=== BODY renders context defaults + dictatable picks ===');
  for (const p of ['Khashayar Sarabi, MD, RPVI', 'Mindray M7, L12-4s MHz Transducer', 'Long Beach, CA', 'Leg pain', 'Varicose veins', 'reflux positive', 'saphenofemoral junction to the mid thigh']) {
    console.log(`  body has ${JSON.stringify(p)}:`, body.includes(p));
  }
  console.log('  body has NO raw markers:', !/\{\{one of:/.test(body));
  console.log('  lane size:', v.suggestions.length);
}
main().then(() => process.exit(0)).catch((e) => { console.error(e); process.exit(1); });
