// ============================================================================
// Ultrasound report demo (real model, raw API — CI-excluded, no prisma).
// ----------------------------------------------------------------------------
// Exercises the REAL ultrasound prompt builder (buildUltrasoundSystemPrompt +
// ULTRASOUND_REPORT_TEMPLATE) against synthetic venous-duplex dictations and
// prints the generated REPORTS, to confirm: (1) the output is an imaging
// report (Exam/Indication/Technique/Comparison/Findings/Impression), NOT SOAP;
// (2) per-segment bilateral findings with reflux times in s + diameters in mm;
// (3) a SOAP control specialty still produces a SOAP note.
//
// Uses raw Anthropic fetch (like evidence-anchor-spike) so no DB / AiCall
// logging is needed. The verifier's measurement guard is proven separately +
// deterministically in worker/layers/__tests__/04b-ultrasound-measurement-guard.
// Run: npx tsx scripts/eval/ultrasound-report-demo.ts   (needs ANTHROPIC_API_KEY)
// ============================================================================

import { config as dotenvConfig } from 'dotenv';
import path from 'node:path';
import { buildUltrasoundSystemPrompt } from '../../src/worker/note-templates/build-ultrasound-prompt';
import { ULTRASOUND_REPORT_TEMPLATE } from '../../src/worker/note-templates/ultrasound-report-template';
import { buildSoapSystemPrompt, buildSoapUserPrompt, type ResolvedNoteTemplate } from '../../src/worker/note-templates/build-soap-prompt';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '../../src/worker/note-templates/system-default-template';
import { specialtyGuidance } from '../../src/worker/prompts/specialty-guidance';

const REPO_ROOT = path.resolve(__dirname, '../../../..');
dotenvConfig({ path: path.join(REPO_ROOT, '.env') });
const KEY = process.env.ANTHROPIC_API_KEY;
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8';
if (!KEY) throw new Error('ANTHROPIC_API_KEY required');

async function generate(system: string, user: string): Promise<string> {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'x-api-key': KEY!, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
    body: JSON.stringify({ model: MODEL, max_tokens: 4096, system, messages: [{ role: 'user', content: user }] }),
  });
  const j = (await res.json()) as { content?: { text?: string }[]; error?: { message?: string } };
  if (j.error) throw new Error(j.error.message);
  return j.content?.map((c) => c.text ?? '').join('') ?? '';
}

const OPTS = { audioQualityAlert: null, interpreterAlert: null };

// ── Synthetic, no-PHI vein-clinic dictations ────────────────────────────────
const REFLUX = [
  '[Doctor #0]: Bilateral lower extremity venous reflux study, standing, with distal augmentation.',
  'Right leg. Common femoral vein patent, compressible, phasic, no reflux. Femoral vein patent, no reflux. Popliteal vein patent, no reflux.',
  'Right great saphenous vein: 7.2 millimeters at the saphenofemoral junction, 6.1 in the proximal thigh, 4.0 at the knee. Reflux at the SFJ is 3.4 seconds, thigh 2.8 seconds. SFJ incompetent.',
  'Right small saphenous vein 3.1 millimeters, competent, no reflux, SPJ competent.',
  'A right mid-thigh perforator measures 3.6 millimeters, incompetent, outward flow 1.2 seconds.',
  'Left leg. Common femoral, femoral, and popliteal veins patent with no reflux.',
  'Left great saphenous vein 4.8 millimeters at the SFJ, reflux 0.4 seconds — within normal limits, competent. Left small saphenous vein competent.',
  'Indication: bilateral leg heaviness, aching, and visible varicosities, worse on the right.',
].join('\n');

const DVT = [
  '[Doctor #0]: Left lower extremity venous duplex to rule out DVT. Calf swelling for three days.',
  'Left common femoral vein compressible, phasic flow, augments. Left femoral vein compressible throughout. Left popliteal vein is NON-compressible with echogenic material, no flow, consistent with acute occlusive thrombus.',
  'Left posterior tibial and peroneal veins compressible. Right leg not examined.',
].join('\n');

const SOAP_CONTROL = [
  '[Doctor #0]: 54-year-old here for hypertension follow-up. Home readings around 150 over 92.',
  '[Patient #1]: taking the lisinopril every day, no chest pain or headaches.',
  '[Doctor #0]: BP today 148 over 90, heart rate 78, lungs clear. Adding amlodipine 5 milligrams. Recheck in four weeks.',
].join('\n');

async function main() {
  const usSystem = (sp: string) =>
    buildUltrasoundSystemPrompt(ULTRASOUND_REPORT_TEMPLATE as ResolvedNoteTemplate, {
      specialty: sp, ...OPTS, specialtyGuidanceText: null,
    });
  const user = (sp: string, transcript: string) =>
    buildSoapUserPrompt({ specialty: sp, entitiesJson: '{}', wrappedTranscript: transcript });

  for (const [title, transcript] of [['VENOUS REFLUX', REFLUX], ['VENOUS DVT', DVT]] as const) {
    console.log(`\n\n=================== ULTRASOUND — ${title} ===================\n`);
    console.log(await generate(usSystem('ultrasound'), user('ultrasound', transcript)));
  }

  console.log(`\n\n=================== SOAP CONTROL (primary-care) ===================\n`);
  const soapSys = buildSoapSystemPrompt(SYSTEM_DEFAULT_NOTE_TEMPLATE as ResolvedNoteTemplate, {
    specialty: 'primary-care', ...OPTS, specialtyGuidanceText: specialtyGuidance('primary-care') || null,
  });
  console.log(await generate(soapSys, user('primary-care', SOAP_CONTROL)));

  // Verifier — FLIPPED LATERALITY. The anchored verifier's entailment stage
  // judges whether a claim is supported by its quoted transcript span. A
  // laterality flip is a content mismatch it must reject. Faithful live probe
  // of that judgment (same span-supports-claim question the verifier asks).
  console.log(`\n\n=================== VERIFIER — flipped laterality (entailment) ===================\n`);
  const span = 'the right popliteal vein is non-compressible with echogenic material and no flow';
  const flipped = 'The LEFT popliteal vein is non-compressible with occlusive thrombus.';
  const judge = await generate(
    'You verify clinical documentation. Answer ONLY with strict JSON {"entailed": boolean, "why": "<8 words"}.',
    `Is this CLAIM fully supported by the transcript SPAN (laterality must match)?\nSPAN: "${span}"\nCLAIM: "${flipped}"`
  );
  console.log(`span (transcript): ${span}`);
  console.log(`claim (drafted):   ${flipped}`);
  console.log(`verifier verdict:  ${judge.trim()}`);
}
main().catch((e) => { console.error(e); process.exit(1); });
