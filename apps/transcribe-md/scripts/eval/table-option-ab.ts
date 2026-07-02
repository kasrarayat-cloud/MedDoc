// ============================================================================
// Phase-C cached-draft deterministic A/B — verifier table/option pass.
// Pre-registered: docs/eval-runs/verifier-table-option-fix-20260702T165454Z.md
// (the #346 method: generate anchored drafts ONCE, verify BEFORE vs AFTER on
// identical drafts with entailment held approve-all).
//
//   --phase generate : real Opus L4 drafts (anchors ON) → cache JSON (~$1)
//   --phase verify   : MOCK_AI_CALLS=true (approve-all entailment short-
//                      circuit) → run BOTH verifier versions on the cache,
//                      emit the demotion-set comparison.
//
// The BEFORE verifier is a byte-copy of main's 04b placed at
// src/worker/layers/04b-anchor-verify-MAINREF.ts (temp; deleted after the
// run) so its @/ + package imports resolve identically.
// TEMP eval harness — kept for the eval-run record.
// ============================================================================
import * as fs from 'node:fs';
import { modelClient, wrapAsData } from '@meddoc/ai';
import {
  buildSoapSystemPrompt,
  buildSoapUserPrompt,
  type ResolvedNoteTemplate,
} from '../../src/worker/note-templates/build-soap-prompt';
import { buildUltrasoundSystemPrompt } from '../../src/worker/note-templates/build-ultrasound-prompt';
import { ULTRASOUND_REPORT_TEMPLATE } from '../../src/worker/note-templates/ultrasound-report-template';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '../../src/worker/note-templates/system-default-template';
import { ANCHOR_GENERATION_ADDENDUM } from '../../src/worker/layers/04b-anchor-verify';

const SCRATCH = '/tmp/claude-1000/-opt-meddoc-pro/586b3f3f-7eed-4f8e-ac7f-e25626e93305/scratchpad';
const CACHE = `${SCRATCH}/ab-drafts.json`;

function loadJson(p: string): any {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

// The structured synthetic: checkbox ROS + fixed vitals table (the new shape).
const STRUCTURED_TEMPLATE: ResolvedNoteTemplate = {
  id: 'tmpl_ab_structured',
  version: 1,
  isSystemDefault: false,
  styleProfile: SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile,
  sections: [
    { key: 'hpi', label: 'HPI', order: 1, formatHint: 'prose', styleInstructions: null, defaultText: null, defaultTextMode: 'omit_unless_supported' },
    {
      key: 'ros', label: 'Review of Systems', order: 2, formatHint: 'prose', styleInstructions: null, defaultText: null, defaultTextMode: 'omit_unless_supported',
      structure: { kind: 'options', options: ['Fever', 'Chills', 'Chest pain', 'Palpitations', 'Cough', 'Dyspnea', 'None of the above'], multi: true },
    },
    {
      key: 'vitals', label: 'Vital Signs', order: 3, formatHint: 'prose', styleInstructions: null, defaultText: null, defaultTextMode: 'omit_unless_supported',
      structure: { kind: 'table', columns: ['Vital', 'Value'], rowLabels: ['BP', 'HR', 'RR', 'Temp', 'SpO2'] },
    },
    { key: 'plan', label: 'Plan', order: 4, formatHint: 'numbered', styleInstructions: null, defaultText: null, defaultTextMode: 'omit_unless_supported' },
  ],
};

const STRUCTURED_TRANSCRIPT =
  'Follow-up visit. Reports a dry cough for one week. Denies fever, denies chest pain. Vitals today: blood pressure 128 over 78, heart rate 72, oxygen saturation 98 percent. Plan: supportive care, honey and fluids, return if fever develops or cough lasts beyond three weeks.';

async function generate() {
  const scenarios = loadJson(`${SCRATCH}/scenarios.json`);
  const f4Visit = loadJson(`${SCRATCH}/phase2-artifacts/f4-a-visit.json`);
  const f4Tmpl = loadJson(`${SCRATCH}/phase1-artifacts/f4-template.json`);
  const f4Resolved: ResolvedNoteTemplate = {
    id: f4Tmpl.id, version: f4Tmpl.version, isSystemDefault: false,
    styleProfile: SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile,
    sections: f4Tmpl.sections,
  };
  const cases: Array<{ name: string; system: string; transcript: string }> = [
    {
      name: 'f4-tables',
      system: buildSoapSystemPrompt(f4Resolved, { specialty: 'primary-care', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null }) + ANCHOR_GENERATION_ADDENDUM,
      transcript: f4Visit.rawTextInput,
    },
    {
      name: 'reflux-ultrasound',
      system: buildUltrasoundSystemPrompt(ULTRASOUND_REPORT_TEMPLATE as ResolvedNoteTemplate, { specialty: 'ultrasound', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null }) + ANCHOR_GENERATION_ADDENDUM,
      transcript: scenarios.u.transcript,
    },
    {
      name: 'clean-soap-control',
      system: buildSoapSystemPrompt(SYSTEM_DEFAULT_NOTE_TEMPLATE, { specialty: 'primary-care', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null }) + ANCHOR_GENERATION_ADDENDUM,
      transcript: scenarios.e.transcript,
    },
    {
      name: 'structured-synthetic',
      system: buildSoapSystemPrompt(STRUCTURED_TEMPLATE, { specialty: 'primary-care', audioQualityAlert: null, interpreterAlert: null, specialtyGuidanceText: null }) + ANCHOR_GENERATION_ADDENDUM,
      transcript: STRUCTURED_TRANSCRIPT,
    },
  ];
  const out: Record<string, string> = {};
  for (const c of cases) {
    const user = buildSoapUserPrompt({
      specialty: 'primary-care',
      entitiesJson: '{}',
      wrappedTranscript: wrapAsData(c.transcript, 'transcript').wrapped,
    });
    const { text } = await modelClient.completeText({
      practiceId: 'ab-eval', visitId: null, userId: null,
      purpose: 'tm_soap_draft', provider: 'anthropic',
      model: process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8',
      system: c.system, user, maxTokens: 8192, temperature: 0.2,
    });
    out[c.name] = text;
    console.log(`[generate] ${c.name}: ${text.length} chars, ${(text.match(/⟦A:/g) ?? []).length} anchors`);
  }
  fs.writeFileSync(CACHE, JSON.stringify(out, null, 2));
  console.log(`cached → ${CACHE}`);
}

async function verify() {
  process.env.MOCK_AI_CALLS = 'true'; // entailment approve-all short-circuit
  const { runAnchorVerify } = await import('../../src/worker/layers/04b-anchor-verify');
  // BEFORE = a byte-copy of main's 04b, regenerated at run time (deleted
  // after the eval): git show main:apps/.../04b-anchor-verify.ts > .../04b-anchor-verify-MAINREF.ts
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { runAnchorVerify: runBefore } = (await import(
    /* @vite-ignore */ '../../src/worker/layers/04b-anchor-verify-MAINREF' as string
  )) as any;
  const drafts = loadJson(CACHE) as Record<string, string>;
  const report: any = {};
  let fail = false;
  for (const [name, draft] of Object.entries(drafts)) {
    const before = await runBefore({ visitId: 'ab', practiceId: 'ab', userId: null, anchoredDraft: draft, roleLabeledTranscript: nameToTranscript(name) });
    const after = await runAnchorVerify({ visitId: 'ab', practiceId: 'ab', userId: null, anchoredDraft: draft, roleLabeledTranscript: nameToTranscript(name) });
    const bSet = before.suggestions.map((s: any) => s.text.trim());
    const aSet = after.suggestions.map((s: any) => s.text.trim());
    const newlyDemoted = aSet.filter((t: string) => !bSet.includes(t));
    const recovered = bSet.filter((t: string) => !aSet.includes(t));
    report[name] = {
      before: bSet.length, after: aSet.length,
      newlyDemoted, recovered,
      beforeReasons: before.suggestions.map((s: any) => s.reason),
      afterReasons: after.suggestions.map((s: any) => s.reason),
    };
    if (newlyDemoted.length > 0) fail = true;
    console.log(`[verify] ${name}: before=${bSet.length} after=${aSet.length} newlyDemoted=${newlyDemoted.length} recovered=${recovered.length}`);
    for (const r of recovered) console.log(`  RECOVERED: ${r.slice(0, 110)}`);
    for (const r of newlyDemoted) console.log(`  !! NEWLY DEMOTED: ${r.slice(0, 110)}`);
  }
  fs.writeFileSync(`${SCRATCH}/ab-verify-report.json`, JSON.stringify(report, null, 2));
  console.log(fail ? 'PHASE C: FAIL (newly demoted present)' : 'PHASE C: PASS (AFTER ⊆ BEFORE everywhere)');
  process.exit(fail ? 1 : 0);
}

function nameToTranscript(name: string): string {
  const scenarios = loadJson(`${SCRATCH}/scenarios.json`);
  const f4Visit = loadJson(`${SCRATCH}/phase2-artifacts/f4-a-visit.json`);
  switch (name) {
    case 'f4-tables': return f4Visit.rawTextInput;
    case 'reflux-ultrasound': return scenarios.u.transcript;
    case 'clean-soap-control': return scenarios.e.transcript;
    case 'structured-synthetic': return STRUCTURED_TRANSCRIPT;
    default: throw new Error(name);
  }
}

const phase = process.argv.includes('--phase')
  ? process.argv[process.argv.indexOf('--phase') + 1]
  : '';
if (phase === 'generate') generate();
else if (phase === 'verify') verify();
else { console.error('usage: --phase generate|verify'); process.exit(2); }
