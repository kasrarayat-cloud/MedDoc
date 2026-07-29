// ============================================================================
// Landing copy — CLAIM-TRUTH PASSED at promote (2026-07-03), on top of the
// approved set from the staging review (docs/landing-split-final.md):
//   · every mechanism claim (anchored lines, machine-verified, review lane
//     labeled "Suggested by AI — not stated in this visit", you sign every
//     note) matches the shipped product — the lane label is the literal
//     UI string in suggestions-lane.tsx;
//   · "Audio kept 90 days after signing, then deleted" is the shipped
//     retention-sweep default (worker/cleanup/retention-sweep.ts, keyed
//     on signedAt);
//   · "US-hosted" verified (Los Angeles, US);
//   · the "Start free" CTA — flagged at the staging review pending a
//     free-trial decision — is NEUTRALIZED to "Get started" here;
//   · three shipped capabilities added: custom note formats incl. tables &
//     checklists (PR #350/#353), ultrasound imaging reports (PR #341),
//     deterministic Rx safety checks with a fail-closed sign gate (PR #288/#351).
// No accuracy %s, no SOC 2, no model version, no invented stats.
// ============================================================================

// Review-lane example: a plausible clinical addition that was NOT stated in the visit —
// held back for the doctor rather than written into the note.
export const REVIEW_SUGGESTION = {
  text: 'Counsel on a low-sodium (DASH) diet.',
  reason: 'Suggested by AI — not stated in this visit',
};

export const STEPS = [
  { n: '01', label: 'Record', body: 'Ambient capture in the room. No typing, no dictation — just the visit.' },
  { n: '02', label: 'Draft', body: 'A structured SOAP note, written from what was actually said.' },
  { n: '03', label: 'Verify', body: 'Every line is anchored to the transcript. Anything it can’t ground goes to the review lane.' },
  { n: '04', label: 'Sign', body: 'You review, edit, and sign. Always. The note is yours.' },
];

export type CompareRow = { f: string; q: string | boolean; e: string };
export const COMPARE: CompareRow[] = [
  { f: 'Pricing', q: '$49 / provider / month, flat', e: 'Custom contracts, per-seat, annual' },
  { f: 'Getting started', q: 'Start today — no sales call', e: 'Sales cycle + onboarding' },
  { f: 'Every line anchored to the transcript', q: true, e: 'varies' },
  { f: 'Review lane for anything unverifiable', q: true, e: 'varies' },
  { f: 'Writes in your own note format — tables & checklists included', q: true, e: 'varies' },
  { f: 'You sign every note', q: true, e: 'varies' },
  { f: 'Audit-logged · US-hosted', q: true, e: 'varies' },
  { f: 'Audio kept 90 days after signing, then deleted', q: true, e: 'varies' },
];

export const PRICE_INCLUDES = [
  'Evidence-anchored SOAP notes',
  'Machine-verified, with a review lane',
  'Your own note format — tables & checklists included',
  'Ultrasound imaging reports (vein studies)',
  'Rx safety checks before you sign',
  'You sign every note',
  'HIPAA-ready · Audit-logged',
  'US-hosted',
  'Audio retained 90 days after signing',
  'Runs on a current frontier model',
];

export const FAQS = [
  {
    q: 'Do I still sign my own notes?',
    a: 'Always. QuillMD writes the first draft; you review, edit, and sign every note. Nothing is filed without you.',
  },
  {
    q: 'How do you keep the note accurate?',
    a: 'Every line is anchored to the visit transcript and machine-verified. Anything it can’t ground from what was actually said goes to a review lane labeled “Suggested by AI — not stated in this visit,” rather than into your note.',
  },
  {
    q: 'Can it write in my note format?',
    a: 'Yes. Upload or paste a sample note and QuillMD learns your structure — headings, style, even tables, checklists, and severity scales. Boxes are only ever ticked when the visit supports them; anything you didn’t address stays blank instead of being guessed.',
  },
  {
    q: 'What about prescriptions?',
    a: 'Rx drafts run through deterministic safety checks — dangerous drug pairs and dose caps included. A critical warning blocks signing until you explicitly review it; the gate fails closed, never open.',
  },
  {
    q: 'Is it HIPAA-compliant?',
    a: 'QuillMD is HIPAA-ready, audit-logged at every layer, and your data is US-hosted.',
  },
  {
    q: 'What happens to the visit audio?',
    a: 'Audio is retained for 90 days after the note is signed, then deleted.',
  },
  {
    q: 'How much does it cost?',
    a: '$49 per provider, per month — flat, with no per-visit fees.',
  },
  {
    q: 'Which AI model does it use?',
    a: 'A current frontier model. The note is always anchored to the transcript and left for you to sign — the model drafts, it doesn’t decide.',
  },
];

export const FOOTER_TRUST = [
  'HIPAA-ready',
  'Audit-logged',
  'US-hosted',
  'Audio kept 90 days after signing',
  'You sign every note',
];
