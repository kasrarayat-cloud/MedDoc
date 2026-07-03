// ============================================================================
// Shared demo content for the split-screen landing (promoted from the
// staging.quillmd.com/final review build, PR #325 → prod promote 2026-07-03).
// Synthetic, no-PHI vignette: one hypertension follow-up reused by the hero
// note and the verification split. Every product claim on the page is in the
// approved set (docs/landing-split-final.md) + verified against the shipped
// product at promote time — see the trust list note in content.ts.
// ============================================================================

export const TRUST = ['HIPAA-ready', 'BAA included', 'US-hosted', 'You sign every note'];

// One sample SOAP draft, shared by the hero card and the verification split.
export const SOAP = [
  { tag: 'S', text: '54M, 3-mo HTN follow-up, home BP ~150/90.' },
  { tag: 'O', text: 'BP 148/92, HR 78, lungs clear.' },
  { tag: 'A', text: 'Hypertension, uncontrolled.' },
  { tag: 'P', text: 'Add amlodipine 5 mg; f/u 4 wks.' },
];

export type Utterance = { who: 'dr' | 'pt'; text: string; soap?: string };

export const TRANSCRIPT: Utterance[] = [
  { who: 'dr', text: 'Good to see you again. How have things been since we adjusted the lisinopril?' },
  { who: 'pt', text: "Alright, I think. I've been checking at home like you asked — it's been about 150 over 90 most mornings.", soap: 'S' },
  { who: 'dr', text: "Let's take a look today. 148 over 92, heart rate 78. And your lungs are clear.", soap: 'O' },
  { who: 'dr', text: "So the pressure is still higher than I'd like — the hypertension isn't controlled yet.", soap: 'A' },
  { who: 'dr', text: "I'd like to add amlodipine, 5 milligrams, and recheck in four weeks.", soap: 'P' },
];
