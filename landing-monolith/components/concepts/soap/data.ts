// Synthetic, no-PHI sample data for the SOAP-review concept mockups. NOT wired to the real
// visit pipeline — these are static props. Clinical facts are generic; the "patient" is an
// explicit synthetic placeholder. The critical Rx interaction (amlodipine × simvastatin) is a
// real, well-known guideline interaction directly caused by the new prescription, so the
// blocking-override flow has something genuine to demo.

export const SAMPLE_BANNER = 'Synthetic sample — not a real patient or visit';

export const VISIT = {
  patient: 'Sample patient',
  meta: '54 M · Hypertension follow-up',
  mrn: 'SYN-0000',
  when: 'Today · 11:24',
  status: 'Ready to sign',
};

export type Section = { tag: 'S' | 'O' | 'A' | 'P'; label: string; text: string };
export const SOAP: Section[] = [
  { tag: 'S', label: 'Subjective', text: '54-year-old here for a 3-month hypertension follow-up. Home blood-pressure readings averaging ~150/90 over the past month. Reports good adherence to lisinopril. Denies chest pain, shortness of breath, headache, or visual changes.' },
  { tag: 'O', label: 'Objective', text: 'BP 148/92 mmHg (repeat 146/90). HR 78, regular. Lungs clear to auscultation bilaterally. No peripheral edema.' },
  { tag: 'A', label: 'Assessment', text: 'Essential hypertension, uncontrolled on lisinopril monotherapy.' },
  { tag: 'P', label: 'Plan', text: 'Add amlodipine 5 mg daily. Continue lisinopril 20 mg daily. Counseled on adherence and home BP monitoring. Follow up in 4 weeks; recheck BP and a basic metabolic panel.' },
];

// INVARIANT for the concepts: LANE holds exactly one 'grounded' + one 'held' item, and RX holds
// exactly one 'critical' (blocking) + one 'info' item. C6/C7/C8/C10 select these via .find(...)!
// — keep one of each kind if you edit this data, or those non-null assertions will throw.
export type LaneItem = { id: string; text: string; section: string; kind: 'grounded' | 'held'; note: string };
export const LANE: LaneItem[] = [
  { id: 'L1', text: 'Order a basic metabolic panel at the 4-week follow-up.', section: 'Plan', kind: 'grounded', note: 'Grounded in the visit — “…recheck a BMP in a month.”' },
  { id: 'L2', text: 'Counseled on a low-sodium (DASH) diet.', section: 'Plan', kind: 'held', note: 'Suggested by AI — not stated in this visit' },
];

export type RxWarn = { id: string; pair: string; severity: 'critical' | 'info'; text: string; blocking: boolean };
export const RX: RxWarn[] = [
  { id: 'R-001', pair: 'Amlodipine 5 mg (new) × Simvastatin 40 mg', severity: 'critical', text: 'Amlodipine raises simvastatin levels — guideline max is 20 mg/day with amlodipine. Risk of myopathy / rhabdomyolysis.', blocking: true },
  { id: 'R-002', pair: 'Lisinopril 20 mg × Amlodipine 5 mg', severity: 'info', text: 'Additive blood-pressure lowering — monitor for hypotension and dizziness.', blocking: false },
];

export const EM = {
  current: '99213',
  suggested: '99214',
  delta: '+$32',
  basis: 'Documentation supports a moderate-complexity visit (2 stable chronic problems + prescription management).',
};

// Synthetic visit transcript — the dialogue the note was drafted from. Used by the
// before/after split (C5) and as provenance anchors. No PHI; generic clinical content.
export type Utterance = { who: 'dr' | 'pt'; text: string; tag?: 'S' | 'O' | 'A' | 'P' };
export const TRANSCRIPT: Utterance[] = [
  { who: 'dr', text: 'Good to see you again. How have things been since we adjusted the lisinopril?' },
  { who: 'pt', text: "Pretty good. I've been checking at home like you asked — it's been about 150 over 90 most mornings.", tag: 'S' },
  { who: 'dr', text: 'And you’re taking the lisinopril every day?' },
  { who: 'pt', text: 'Every morning, yeah. No chest pain, no headaches, breathing’s fine.', tag: 'S' },
  { who: 'dr', text: 'Let’s take a look. 148 over 92… let me recheck that. 146 over 90. Heart rate’s 78, and your lungs are clear.', tag: 'O' },
  { who: 'dr', text: 'So your pressure’s still higher than I’d like — it’s not controlled on the lisinopril alone yet.', tag: 'A' },
  { who: 'dr', text: 'I’m going to add a second medicine, amlodipine, 5 milligrams. Keep taking the lisinopril at 20.', tag: 'P' },
  { who: 'dr', text: 'Come back in about four weeks and we’ll recheck your pressure and a basic metabolic panel.', tag: 'P' },
];

// The note decomposed into atomic, individually-reviewable claims, each tied back to a
// transcript anchor. Used by the line-by-line approval concept (C6) and the margin pins (C8).
export type Claim = { id: string; section: 'S' | 'O' | 'A' | 'P'; text: string; anchor?: string };
export const CLAIMS: Claim[] = [
  { id: 'c1', section: 'S', text: '54-year-old, 3-month hypertension follow-up.' },
  { id: 'c2', section: 'S', text: 'Home BP averaging ~150/90 over the past month.', anchor: '“…about 150 over 90 most mornings.”' },
  { id: 'c3', section: 'S', text: 'Good adherence to lisinopril; denies chest pain, SOB, headache.', anchor: '“Every morning… no chest pain, no headaches.”' },
  { id: 'c4', section: 'O', text: 'BP 148/92 (repeat 146/90), HR 78, lungs clear, no edema.', anchor: '“148 over 92… 146 over 90. Heart rate’s 78… lungs are clear.”' },
  { id: 'c5', section: 'A', text: 'Essential hypertension, uncontrolled on lisinopril monotherapy.', anchor: '“…it’s not controlled on the lisinopril alone yet.”' },
  { id: 'c6', section: 'P', text: 'Add amlodipine 5 mg daily; continue lisinopril 20 mg.', anchor: '“…add amlodipine, 5 milligrams. Keep taking the lisinopril at 20.”' },
  { id: 'c7', section: 'P', text: 'Follow up 4 weeks; recheck BP and a basic metabolic panel.', anchor: '“Come back in about four weeks… recheck your pressure and a basic metabolic panel.”' },
];
