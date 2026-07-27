// ============================================================================
// Ultrasound IMAGING REPORT template (flag-gated, additive).
// ----------------------------------------------------------------------------
// An ultrasound study is an IMAGING REPORT, not a SOAP encounter. Routing it
// through the S/O/A/P scaffold produces structurally-wrong output. This module
// defines the report as data — the SAME ResolvedNoteTemplate shape L4 already
// consumes — so it flows through the existing template-driven generator
// (build-ultrasound-prompt.ts), the section-label structure validator, and the
// section-AGNOSTIC anchored verifier (which guards every measurement / reflux
// time / laterality exactly as it guards SOAP vitals) with NO change to any of
// those mechanisms.
//
// BACKBONE (every study, so any ultrasound dictation produces a correctly-
// structured report): Exam · Indication · Technique · Comparison · Findings ·
// Impression. The Findings section's styleInstructions carry the STUDY-TYPE
// routing — the model picks the structure (venous reflux / DVT / post-ablation
// / arterial / vein-mapping / Tier-2) from the dictation.
//
// ACCURACY: this template carries NO clinical values — only structure + units
// discipline. Every number/laterality in the output must come from the
// dictation; the immutable anti-hallucination globalRules (reused verbatim from
// the SOAP system-default styleProfile) + the anchored verifier enforce that.
// ============================================================================

import type {
  NoteTemplateSection,
  NoteTemplateStyleProfile,
} from './system-default-template';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from './system-default-template';

/** Stable id for provenance (transcribe_visits.noteTemplateId). */
export const ULTRASOUND_REPORT_TEMPLATE_ID = 'tmpl_ultrasound_report';

// ── Imaging-report safety layer ────────────────────────────────────────────
// Reuse the SOAP system-default's anti-hallucination rules VERBATIM (they are
// report-agnostic — "never add numbers not stated", "[unclear in recording]",
// "don't normalize a garbled term", "don't elaborate beyond what was said").
// These are exactly the rules that keep reflux times + diameters honest. Only
// the SOAP-specific framing differs: a radiology/sonography preamble, an
// imaging-specific measurement-discipline rule, and an imaging output line
// (the SOAP "Output ONLY the SOAP note markdown" line is dropped).
const SOAP_SAFETY = SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile;

/** Anti-hallucination rules shared with SOAP, minus the SOAP-output line (the
 *  last element), which we replace with imaging-specific output framing. */
const SHARED_ANTIHALLUCINATION_RULES = SOAP_SAFETY.globalRules.slice(0, -1);

const ULTRASOUND_PREAMBLE = [
  'You are a vascular sonographer / radiologist transcribing a structured',
  'diagnostic ULTRASOUND REPORT from a dictation. This is an IMAGING REPORT,',
  'NOT a SOAP clinical note — do NOT use Subjective/Objective/Assessment/Plan.',
  'Use ONLY the dictation (and any extracted entities) as evidence. Write in a',
  'concise, professional radiology-report register.',
].join('\n');

const ULTRASOUND_GLOBAL_RULES: string[] = [
  ...SHARED_ANTIHALLUCINATION_RULES,
  // Imaging-specific measurement discipline — the heart of report accuracy.
  [
    '- MEASUREMENTS ARE SACRED. Reproduce every numeric value EXACTLY as',
    '  dictated, with its unit: vein diameters in mm, reflux/reverse-flow',
    '  times in seconds (s), velocities in cm/s, distances in cm/mm. Never',
    '  round, convert, infer, or carry a value from one segment to another.',
    '  If a segment/structure was not assessed or no value was given, write',
    '  "[not documented]" — never a default or a typical value.',
  ].join('\n'),
  [
    '- LATERALITY IS SACRED. Right and Left are never interchangeable. Attribute',
    '  every finding to the side actually stated. If a finding\'s side is',
    '  unclear in the dictation, write "[laterality not specified]" rather than',
    '  guessing. Report the Right side fully, then the Left side.',
  ].join('\n'),
  [
    '- Do NOT assign a final diagnosis the dictation does not support. The',
    '  Impression summarizes the findings (e.g. "GSV reflux, right") — it does',
    '  not add staging, etiology, or recommendations the reading physician did',
    '  not dictate.',
  ].join('\n'),
  '- Output ONLY the ultrasound report markdown. No preamble, no postscript.',
];

const ULTRASOUND_STYLE_PROFILE: NoteTemplateStyleProfile = {
  tense: null,
  tone: 'concise professional radiology report',
  abbreviations: null,
  preamble: ULTRASOUND_PREAMBLE,
  globalRules: ULTRASOUND_GLOBAL_RULES,
};

// ── Section directive blocks ────────────────────────────────────────────────

const EXAM_INSTRUCTIONS = [
  'One line: the study performed + laterality + sub-type, as stated. Examples:',
  '"Venous Duplex Ultrasound — Bilateral Lower Extremities — Reflux/Insufficiency"',
  '"Venous Duplex Ultrasound — Right Lower Extremity — DVT Evaluation"',
  '"Duplex Ultrasound — Left GSV — Post-Ablation Follow-up".',
  'If the study type is ambiguous, state the most specific phrasing the',
  'dictation supports; do not invent a sub-type.',
].join('\n');

const INDICATION_INSTRUCTIONS = [
  'Why the study was ordered (symptoms, prior diagnosis, surveillance), as',
  'stated. e.g. "Leg heaviness, aching, and visible varicosities" /',
  '"Left calf swelling, rule out DVT" / "Surveillance after RFA of the GSV".',
  'If not stated, write "[not documented]".',
].join('\n');

const TECHNIQUE_INSTRUCTIONS = [
  'How the study was performed, only as stated. Typical elements: B-mode +',
  'color + spectral Doppler; patient position (e.g. reverse Trendelenburg /',
  'standing for reflux, supine for DVT); reflux provocation (distal',
  'augmentation / Valsalva / cuff deflation); transverse compression at',
  'intervals for DVT. Do NOT assert a maneuver that was not dictated; if the',
  'technique is not described, write a single neutral line such as "Standard',
  'duplex technique." rather than inventing specifics.',
].join('\n');

const COMPARISON_INSTRUCTIONS = [
  'Prior study referenced for comparison (date/type), if mentioned, plus the',
  'interval change if stated. If no prior is mentioned, write exactly:',
  '"No prior study available for comparison."',
].join('\n');

// The FINDINGS section carries the study-type routing — the model selects the
// structure from the dictation. Each structure lists the segments/structures
// to report and the measurements to attach; the model fills ONLY dictated
// values and marks the rest "[not documented]".
const FINDINGS_INSTRUCTIONS = [
  'Determine the STUDY TYPE from the dictation and structure the Findings with',
  'the matching framework below. Report bilateral studies as a "### Right" block',
  'then a "### Left" block. Attach measurements per segment. Include a segment',
  'line only if it was assessed; otherwise omit it or mark "[not documented]".',
  '',
  '— VENOUS REFLUX / INSUFFICIENCY —',
  'Per leg, per segment. Reflux time = duration of reverse flow after distal',
  'augmentation/Valsalva release, in seconds. Reflux convention (apply ONLY to',
  'label competent vs incompetent; never invent the time): pathologic reflux is',
  'reverse flow > 0.5 s in the superficial veins (GSV, SSV, accessory saphenous,',
  'perforators) and the deep CALF veins, and > 1.0 s in the femoropopliteal deep',
  'veins (CFV, FV, popliteal).',
  '  Deep system — Common Femoral Vein (CFV): patency, compressibility, phasic',
  '    flow, reflux time (s). Femoral Vein (FV): patency, reflux time (s).',
  '    Popliteal Vein: patency, reflux time (s).',
  '  Superficial system — Great Saphenous Vein (GSV): diameter (mm) at the',
  '    saphenofemoral junction (SFJ), proximal thigh, distal thigh, knee, and',
  '    calf as dictated; reflux time (s) per level; SFJ competence.',
  '    Small Saphenous Vein (SSV): diameter (mm), saphenopopliteal junction',
  '    (SPJ) competence, reflux time (s). Anterior accessory saphenous vein',
  '    (AASV) if assessed.',
  '  Perforators: location (e.g. mid-thigh/Hunterian, paratibial, posterior',
  '    tibial/Cockett), diameter (mm), and competence (incompetent if outward',
  '    flow > 0.5 s).',
  '',
  '— VENOUS DVT —',
  'Per leg, per segment: Common Femoral Vein, Femoral Vein (proximal/mid/distal',
  'as dictated), Popliteal Vein, and calf veins (posterior tibial, peroneal,',
  'gastrocnemius/soleal) if assessed. For each: compressibility (fully',
  'compressible / non-compressible / partially compressible), flow (phasic,',
  'augments with distal compression / does not augment), and thrombus — present',
  'or absent; if present: acute (anechoic/hypoechoic, dilated, poorly',
  'compressible, free-floating) vs chronic (echogenic, contracted, recanalized,',
  'collaterals), and occlusive vs non-occlusive. State only what was dictated.',
  '',
  '— POST-ABLATION FOLLOW-UP —',
  'Name the treated vein (e.g. GSV, SSV, AASV) and the modality if stated (RFA,',
  'EVLA/laser, mechanochemical, cyanoacrylate glue). Report: closure status —',
  'occluded/closed (non-compressible, echogenic, no flow) vs patent (flow',
  'present = treatment failure); recanalization (none / partial / complete) and',
  'its segment extent; EHIT (endovenous heat-induced thrombosis) with Kabnick',
  'class if the thrombus reaches the junction — Class 1: thrombus to the level',
  'of the SFJ/SPJ but not into the deep vein; Class 2: extension into the deep',
  'vein, < 50% lumen; Class 3: deep-vein extension ≥ 50% lumen; Class 4:',
  'occlusive deep-vein thrombosis — plus thrombus distance from the junction',
  '(mm/cm) if stated; and a residual-reflux check of untreated GSV/SSV/AASV/',
  'perforator segments.',
  '',
  '— ARTERIAL (lower-extremity, if dictated) —',
  'Per leg: ankle-brachial index (ABI) and segmental pressures if given;',
  'waveform morphology (triphasic / biphasic / monophasic) at the common',
  'femoral, superficial femoral, popliteal, and tibial levels; peak systolic',
  'velocities (cm/s) and any stenosis grade; toe-brachial index (TBI) if stated.',
  '',
  '— VEIN MAPPING (pre-bypass / pre-access, if dictated) —',
  'Target vein(s) (GSV, SSV, cephalic, basilic): diameter (mm) at multiple',
  'levels, patency/continuity, depth from skin (mm), and suitability as stated.',
  '',
  '— OTHER STUDIES (abdominal, pelvic/OB, renal, thyroid & small parts,',
  '  echocardiogram, MSK, etc.) —',
  'Use the standard report structure for that study: report each organ/structure',
  'examined with its standard measurements and laterality where applicable',
  '(e.g. renal length + cortical thickness + hydronephrosis per side; thyroid',
  'lobe dimensions + each nodule\'s size and features; OB biometry GS/CRL/BPD/',
  'HC/AC/FL with EFW, fetal heart rate, presentation, placenta, amniotic fluid).',
  'Report ONLY structures and values the dictation provides; mark the rest',
  '"[not documented]". Do not fabricate a normal organ survey that was not',
  'dictated.',
].join('\n');

const IMPRESSION_INSTRUCTIONS = [
  'Numbered conclusions that summarize the Findings — concise, one finding per',
  'line, with laterality. e.g. "1. Incompetent right great saphenous vein with',
  '3.2 s reflux at the SFJ." / "2. No deep venous thrombosis, bilateral." The',
  'Impression restates findings only; it adds no diagnosis, staging, or',
  'recommendation the dictation did not contain.',
].join('\n');

const ULTRASOUND_SECTIONS: NoteTemplateSection[] = [
  { key: 'exam', label: 'Exam', order: 1, formatHint: 'prose', styleInstructions: EXAM_INSTRUCTIONS, defaultText: null, defaultTextMode: 'omit_unless_supported' },
  { key: 'indication', label: 'Indication', order: 2, formatHint: 'prose', styleInstructions: INDICATION_INSTRUCTIONS, defaultText: null, defaultTextMode: 'omit_unless_supported' },
  // TECHNIQUE is the scan PROTOCOL — the machine settings, the positions, the
  // manoeuvres. It reads the same on every study because it describes how the
  // lab performs the exam, not what this patient turned out to have. A
  // sonographer does not dictate it, so anchoring it to the dictation demoted
  // the whole section and emptied it.
  { key: 'technique', label: 'Technique', order: 3, formatHint: 'prose', styleInstructions: TECHNIQUE_INSTRUCTIONS, defaultText: null, defaultTextMode: 'omit_unless_supported', provenance: 'template' },
  { key: 'comparison', label: 'Comparison', order: 4, formatHint: 'prose', styleInstructions: COMPARISON_INSTRUCTIONS, defaultText: null, defaultTextMode: 'omit_unless_supported' },
  { key: 'findings', label: 'Findings', order: 5, formatHint: 'prose', styleInstructions: FINDINGS_INSTRUCTIONS, defaultText: null, defaultTextMode: 'omit_unless_supported' },
  // The closing sentence is mandated by IMPRESSION_INSTRUCTIONS — every report
  // ends with it. No dictation will ever contain it.
  { key: 'impression', label: 'Impression', order: 6, formatHint: 'numbered', styleInstructions: IMPRESSION_INSTRUCTIONS, defaultText: null, defaultTextMode: 'omit_unless_supported', mandatedLines: ['Clinical correlation with the above findings is required.'] },
];

/** The ultrasound report template, shaped exactly like the resolved templates
 *  L4 already consumes (id/version/isSystemDefault/sections/styleProfile) so it
 *  threads through validateSoapStructure + the anchored verifier unchanged. */
export const ULTRASOUND_REPORT_TEMPLATE = {
  id: ULTRASOUND_REPORT_TEMPLATE_ID,
  version: 1,
  isSystemDefault: true as const,
  sections: ULTRASOUND_SECTIONS,
  styleProfile: ULTRASOUND_STYLE_PROFILE,
};
