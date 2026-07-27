// ============================================================================
// The five false-positive classes that flooded a clean venous-duplex study.
// ----------------------------------------------------------------------------
// Production, 2026-07-27: a normal bilateral reflux study came back with a
// banner saying anchored verification had emptied TECHNIQUE and PROCEDURES /
// E&M, and 22 suggestion cards. Nine of the 22 were literally the HEADINGS of
// the patient-summary section ("What we found", "Your next steps"). Five were
// the section's mandated sign-off and red-flag boilerplate. Two were table rows
// whose only "negation" was an empty-cell placeholder.
//
// The shared root cause: the verifier assumed every line in the composed
// document was a transcript-derived clinical assertion. It had no notion of
// what a line IS (heading / scaffolding / assertion) or where a section's
// content COMES FROM. So it asked "did the doctor dictate this?" of a scan
// protocol, of the coding step's output, and of a heading.
//
// THE GATE IS NOT LOOSENED. The last describe block is the other direction: a
// draft that contradicts the dictation must still demote, and these tests fail
// if it stops doing so.
//
// Synthetic data throughout. No PHI.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: mocks.modelComplete, completeText: mocks.modelCompleteText },
  };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import {
  assertionText,
  extractClinicalFacts,
  runAnchorVerify,
} from '../04b-anchor-verify';
import { ULTRASOUND_REPORT_TEMPLATE } from '../../note-templates/ultrasound-report-template';

/** A bilateral venous-reflux dictation, shaped like the real one. */
const TRANSCRIPT = [
  '[Doctor #0, 0:05]: Bilateral lower extremity venous reflux study.',
  '[Doctor #0, 0:20]: Right great saphenous vein at the saphenofemoral junction',
  'measures 6.2 millimetres with reflux of 3.4 seconds.',
  '[Doctor #0, 0:40]: Right great saphenous vein at the knee measures 3.4 millimetres.',
  '[Doctor #0, 0:55]: Right accessory saphenous at the saphenofemoral junction is 3.0 millimetres.',
  '[Doctor #0, 1:10]: No deep venous thrombosis identified bilaterally.',
  '[Doctor #0, 1:20]: No reflux in the left great saphenous vein.',
].join('\n');

/** Everything the verifier sees for this study — including the sections other
 *  steps produce, which is exactly the situation that broke it. */
const DRAFT = [
  '## Technique',
  'A duplex Doppler color flow ultrasound study was performed in the upright position.',
  '',
  '## Findings',
  'Right Leg:',
  'The great saphenous vein at the saphenofemoral junction measures 6.2 mm with reflux of 3.4 seconds. ⟦A:"Right great saphenous vein at the saphenofemoral junction measures 6.2 millimetres with reflux of 3.4 seconds."⟧',
  'Left Leg:',
  '',
  '## Impression',
  'Clinical correlation with the above findings is required.',
  '',
  '## DIAMETER AND REFLUX TIME',
  'Right Leg:',
  '| Segment | Diameter (mm) | Reflux (sec) |',
  '| --- | --- | --- |',
  '| AAGSV at the SFJ | 3.0 | — |',
  '| GSV at the Knee | 3.4 | [not documented] |',
  '',
  '## PROCEDURES / E&M',
  'Bilateral detailed lower extremity venous reflux study. Coding values are produced by a separate step.',
  '',
  '## PATIENT SUMMARY',
  'What we talked about today',
  'You came in because of aching and heaviness in your legs.',
  'What we found',
  'In your right leg, the great saphenous vein has valves that are not closing properly.',
  "What we're doing about it",
  'Your medications',
  'Your next steps',
  '- Your doctor will review these ultrasound results with you.',
  'When to call us',
  'Please call us right away or go to the nearest emergency room if you notice any of the following:',
  '- Sudden swelling, redness, warmth, or worsening pain in a leg',
  '- Shortness of breath or chest pain',
  'Take care,',
].join('\n');

const INPUT = {
  visitId: 'v_fixture',
  practiceId: 'p_fixture',
  userId: null,
  roleLabeledTranscript: TRANSCRIPT,
  templateSections: ULTRASOUND_REPORT_TEMPLATE.sections,
};

beforeEach(() => {
  vi.clearAllMocks();
  // Every claim that reaches entailment is entailed — so anything that lands in
  // the lane got there DETERMINISTICALLY, which is what these tests are about.
  // Entail EVERY index. Anything that still lands in the lane got there from a
  // DETERMINISTIC rule, which is what this file is about. (A stingier mock made
  // the fail-closed contract demote for a missing verdict — correct behaviour,
  // but it was measuring the mock rather than the classifier.)
  // The ensemble calls completeText and parses ONE JSON object out of the text.
  // Entail every position, so anything still in the lane got there from a
  // DETERMINISTIC rule — which is what this file is about.
  const verdicts = Array.from({ length: 200 }, (_, i) => ({ i, entailed: true }));
  mocks.modelCompleteText.mockResolvedValue({ text: JSON.stringify({ verdicts }) });
});

describe('the WM_IOV venous-duplex fixture produces a clean review', () => {
  it('demotes NOTHING', async () => {
    const r = await runAnchorVerify({ ...INPUT, anchoredDraft: DRAFT });
    expect(
      r.suggestions.map((s) => `${s.section} :: ${s.reason} :: ${s.text}`),
      'every one of these is a false positive',
    ).toEqual([]);
  });

  it('leaves TECHNIQUE and PROCEDURES / E&M populated — never evacuated', async () => {
    const r = await runAnchorVerify({ ...INPUT, anchoredDraft: DRAFT });
    expect(r.stats.filledEmptySections ?? []).toEqual([]);
    expect(r.body).toContain('A duplex Doppler color flow ultrasound study');
    expect(r.body).toContain('Coding values are produced by a separate step');
  });
});

describe('class 1 — structural headings are never claims', () => {
  it.each([
    'Right Leg:',
    'Left Leg:',
    'What we talked about today',
    'What we found',
    "What we're doing about it",
    'Your medications',
    'Your next steps',
    'When to call us',
  ])('%s does not enter the review lane', async (heading) => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: ['## Findings', heading, 'Some content beneath it.'].join('\n'),
    });
    expect(r.suggestions.map((s) => s.text)).not.toContain(heading);
  });

  it('a short FINDING is still verified — a heading needs a body under it', async () => {
    // "No reflux" at the end of a block is a claim, not a title. If the title
    // rule swallowed it, a real assertion would stop being checked.
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: ['## Findings', 'Widespread thrombus'].join('\n'),
    });
    expect(r.suggestions.map((s) => s.text)).toContain('Widespread thrombus');
  });
});

describe('class 2 + 3 — template boilerplate and patient-facing paraphrase', () => {
  const summary = (line: string) => ['## PATIENT SUMMARY', line].join('\n');

  it.each([
    'Take care,',
    'Please call us right away or go to the nearest emergency room if you notice any of the following:',
    '- Sudden swelling, redness, warmth, or worsening pain in a leg',
    '- Shortness of breath or chest pain',
    '- Your doctor will review these ultrasound results with you.',
  ])('boilerplate is exempt: %s', async (line) => {
    const r = await runAnchorVerify({ ...INPUT, anchoredDraft: summary(line) });
    expect(r.suggestions).toEqual([]);
  });

  it('narrative phrasing in the summary is never "couldn\'t verify"', async () => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: summary(
        'In your right leg, the great saphenous vein has valves that are not closing properly, so blood flows backward.',
      ),
    });
    expect(r.suggestions).toEqual([]);
  });

  it('but a WRONG measurement inside the summary still surfaces', async () => {
    // The facts are checkable even when the phrasing is not: 9.9 mm was never
    // dictated. This is the half of class 3 that must keep working.
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: summary('Your great saphenous vein measured 9.9 mm.'),
    });
    expect(r.suggestions).toHaveLength(1);
    expect(r.suggestions[0].text).toContain('9.9');
  });
});

describe('class 4 — a placeholder is an empty cell, not a denial', () => {
  it('strips placeholders before polarity is judged', () => {
    expect(assertionText('| GSV at the Knee | 3.4 | [not documented] |')).not.toMatch(/\bnot\b/);
    expect(assertionText('| AAGSV at the SFJ | 3.0 | — |')).toBe('| AAGSV at the SFJ | 3.0 | |');
  });

  it.each([
    '| AAGSV at the SFJ | 3.0 | — |',
    '| GSV at the Knee | 3.4 | [not documented] |',
  ])('%s is not a negation mismatch', async (row) => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: ['## Findings', row + ' ⟦A:"saphenofemoral junction"⟧'].join('\n'),
    });
    expect(r.suggestions.filter((s) => s.reason === 'negation_mismatch')).toEqual([]);
  });

  it('an unrelated denial in the anchor span no longer flips polarity', async () => {
    // The span speaks of the SFJ; the transcript elsewhere says "no deep venous
    // thrombosis". The claim denies nothing. That is not a mismatch.
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: [
        '## Findings',
        'The saphenofemoral junction measures 6.2 mm. ⟦A:"saphenofemoral junction"⟧',
      ].join('\n'),
    });
    expect(r.suggestions.filter((s) => s.reason === 'negation_mismatch')).toEqual([]);
  });
});

describe('class 5 — a section anchors to the step that produced it', () => {
  it('TECHNIQUE is protocol boilerplate, not a dictated finding', async () => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: [
        '## Technique',
        'A duplex Doppler color flow ultrasound study was performed in the upright position with and without augmentation.',
      ].join('\n'),
    });
    expect(r.suggestions).toEqual([]);
  });

  it('PROCEDURES / E&M belongs to the coding step', async () => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: [
        '## PROCEDURES / E&M',
        'Bilateral detailed lower extremity venous reflux study. Coding values are produced by a separate step.',
      ].join('\n'),
    });
    expect(r.suggestions).toEqual([]);
  });

  it('a table CAPTION rendered as a heading is not a section to verify', async () => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: ['## DIAMETER AND REFLUX TIME', 'Right Leg:', '| a | b |'].join('\n'),
    });
    expect(r.suggestions).toEqual([]);
  });

  it('with NO template supplied, every section still verifies (unchanged)', async () => {
    // The policy is opt-in. Absent it, behaviour is byte-identical to before —
    // which is what keeps every existing caller and test honest.
    const r = await runAnchorVerify({
      visitId: 'v', practiceId: 'p', userId: null,
      roleLabeledTranscript: TRANSCRIPT,
      anchoredDraft: ['## PROCEDURES / E&M', 'Something undictated entirely.'].join('\n'),
    });
    expect(r.suggestions).toHaveLength(1);
  });
});

// ─── THE OTHER DIRECTION ────────────────────────────────────────────────────
describe('the gate still catches a real contradiction', () => {
  it('a draft asserting reflux the dictation DENIED surfaces, and only that', async () => {
    const draft = [
      '## Findings',
      'Right Leg:',
      'The great saphenous vein at the saphenofemoral junction measures 6.2 mm with reflux of 3.4 seconds. ⟦A:"Right great saphenous vein at the saphenofemoral junction measures 6.2 millimetres with reflux of 3.4 seconds."⟧',
      'Left Leg:',
      // The dictation says "No reflux in the left great saphenous vein."
      'The left great saphenous vein shows reflux. ⟦A:"No reflux in the left great saphenous vein"⟧',
    ].join('\n');
    const r = await runAnchorVerify({ ...INPUT, anchoredDraft: draft });
    expect(r.suggestions).toHaveLength(1);
    expect(r.suggestions[0].text).toContain('left great saphenous vein shows reflux');
    // The dictation DENIES what the draft asserts, about the same vessel.
    expect(r.suggestions[0].reason).toBe('negation_mismatch');
    // And the contradicted line is OUT of the body — it is the lane's now.
    expect(r.body).not.toContain('left great saphenous vein shows reflux');
  });

  it('a fabricated measurement is still demoted', async () => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: [
        '## Findings',
        // Anchored to a span that does not carry 9.9 — which is the point.
        'The saphenofemoral junction measures 9.9 mm. ⟦A:"saphenofemoral junction"⟧',
      ].join('\n'),
    });
    expect(r.suggestions).toHaveLength(1);
    expect(r.suggestions[0].reason).toBe('digits_unsupported');
  });

  it('an unanchored clinical assertion is still demoted', async () => {
    const r = await runAnchorVerify({
      ...INPUT,
      anchoredDraft: ['## Findings', 'There is extensive iliac thrombosis.'].join('\n'),
    });
    expect(r.suggestions).toHaveLength(1);
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });
});

describe('extractClinicalFacts', () => {
  it('finds the side, the vessel and the measurement, not the phrasing', () => {
    const f = extractClinicalFacts(
      'In your right leg the great saphenous vein measured 6.2 mm.',
    );
    // Normalized for transcript matching — norm() maps '6.2' to '6 2'.
    expect(f).toContain('great saphenous');
    expect(f).toContain('6 2');
  });

  it('does NOT treat a bare number in prose as a measurement', () => {
    expect(extractClinicalFacts('one of the main veins in your leg')).toEqual([]);
  });
});
