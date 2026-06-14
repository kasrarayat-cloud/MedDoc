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
