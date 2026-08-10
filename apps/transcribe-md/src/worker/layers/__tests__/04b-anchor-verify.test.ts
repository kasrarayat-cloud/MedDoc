// ============================================================================
// L4b anchor verification — canary suite (CI unit gate).
// ----------------------------------------------------------------------------
// Pins, deterministically:
//   1. the HISTORICAL WORST OFFENDERS as fixed claim+anchor fixtures the
//      verifier MUST demote (olecranon-bursitis class = no anchor; COC/aura
//      risk chain = anchored-but-not-entailed; sphenitol class = anchor over
//      [unclear]; unstated negatives = no anchor / negation mismatch;
//      process boilerplate = no anchor);
//   2. supported register translation it MUST pass ("No. No." → "No prior
//      diagnosis of migraines", entailment-approved);
//   3. deterministic overrides that the model verdict CANNOT overrule
//      (digits, negation polarity) — pinned by approving-the-claim mocks
//      that still demote;
//   4. the FAIL-CLOSED error paths (API throw, malformed verdict, missing/
//      duplicate per-claim verdicts, ambiguous multi-JSON, no .default()
//      fail-opens — the L6b BLOCK-1 class);
//   5. flag-off byte-identity of the L4 prompt + behavior.
// Entailment verdicts are MOCKED (deterministic CI); the model-level
// behavior is measured by the pre-registered n=30 protocol run.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText },
  };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { Prisma } from '@prisma/client';
import { runAnchorVerify } from '../04b-anchor-verify';
import { runLayer4GenerateSoap } from '../04-generate-soap';
import { buildSoapSystemPrompt } from '../../note-templates/build-soap-prompt';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '../../note-templates/system-default-template';
import { specialtyGuidance } from '../../prompts/specialty-guidance';

const TRANSCRIPT = [
  '[Doctor #0, 0:10]: have I told you you have had migraines in the past? No. No.',
  '[Patient #1, 0:20]: I take the pill Microgynon. For contraception.',
  '[Doctor #0, 0:30]: take 500 milligrams twice daily for three days.',
  '[Patient #1, 0:40]: my elbow is swollen and it hurts when I lean on it.',
  `[Doctor #0, 0:50]: the medication is called [unclear in recording] one tablet daily.`,
].join('\n');

const IDS = { visitId: 'vis-anchor', practiceId: 'p1', userId: 'u1' };

/** Mock ONLY the entailment call (purpose tm_anchor_entailment). */
function mockEntailment(responder: (user: string) => string | Error) {
  mocks.modelCompleteText.mockImplementation(async (args: { purpose?: string; user?: string }) => {
    if (args?.purpose === 'tm_anchor_entailment') {
      const r = responder(args.user ?? '');
      if (r instanceof Error) throw r;
      return { text: r };
    }
    throw new Error(`unexpected purpose ${args?.purpose}`);
  });
}
const entailAll = () =>
  mockEntailment((user) => {
    const n = (user.match(/^CLAIM \d+:/gm) ?? []).length;
    return JSON.stringify({ verdicts: Array.from({ length: n }, (_, i) => ({ i, entailed: true })) });
  });

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.TRANSCRIBE_MD_EVIDENCE_ANCHORS;
  delete process.env.MOCK_AI_CALLS;
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('canaries — the historical offenders MUST demote', () => {
  it('olecranon-bursitis class: a diagnosis with NO anchor → suggestions lane', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Assessment\nLikely olecranon bursitis.',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('bursitis');
    expect(r.suggestions).toHaveLength(1);
    expect(r.suggestions[0]).toMatchObject({ reason: 'no_anchor', anchor: 'no anchor' });
    expect(r.suggestions[0].text).toContain('olecranon bursitis');
  });

  it('COC/aura chain: demoted DETERMINISTICALLY since iteration 5 — "oral contraceptive" is form/class specification the span never states (an approving mock cannot save it)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Assessment\nCombined oral contraceptive use carries increased ischaemic stroke risk; urgent review. ⟦A:"I take the pill Microgynon."⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('stroke');
    expect(r.suggestions[0]).toMatchObject({ reason: 'form_route_unsupported' });
    expect(r.suggestions[0].anchor).toContain('Microgynon');
  });

  it('sphenitol class: anchor overlapping [unclear in recording] anchors nothing → demoted', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\n1. Sphenitol one tablet daily. ⟦A:"the medication is called [unclear in recording] one tablet daily."⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('Sphenitol');
    expect(r.suggestions[0].reason).toBe('anchor_overlaps_unclear');
  });

  it('unstated negative: "No vomiting." anchored to a span WITHOUT negation → negation_mismatch (deterministic)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Subjective\nNo vomiting. ⟦A:"my elbow is swollen and it hurts when I lean on it."⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('vomiting');
    expect(r.suggestions[0].reason).toBe('negation_mismatch');
  });

  it('process boilerplate with no anchor ("Shared decision-making discussion conducted.") → demoted', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Plan\nShared decision-making discussion conducted.',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('Shared decision-making');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });

  it('model-proposed ⟦S⟧ suggestions route to the lane as model_suggested', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Plan\nConsider urine dipstick testing. ⟦S⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('dipstick');
    expect(r.suggestions[0].reason).toBe('model_suggested');
  });
});

describe('canaries — supported claims MUST pass', () => {
  it('register translation: "No prior diagnosis of migraines." anchored to "No. No." span, entailed → BODY', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nNo prior diagnosis of migraines. ⟦A:"have I told you you have had migraines in the past? No. No."⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('No prior diagnosis of migraines.');
    expect(r.body).not.toContain('⟦'); // anchors stripped
    expect(r.suggestions).toHaveLength(0);
  });

  it('anchored dose with matching digits passes; both anchor grammars accepted', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: [
        '## Plan',
        '1. Take 500 milligrams twice daily for three days. ⟦A:"take 500 milligrams twice daily" ... "for three days."⟧',
      ].join('\n'),
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('500 milligrams');
    expect(r.suggestions).toHaveLength(0);
  });

  it('headers + [not documented] placeholders are exempt (no anchor needed)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Subjective\n**Allergies:** [not documented]\n\n## Objective\nFormal exam not documented in this encounter.',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('**Allergies:** [not documented]');
    expect(r.suggestions).toHaveLength(0);
    // exempt-only note → zero entailment calls
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });
});

describe('deterministic overrides CANNOT be overruled by the model', () => {
  it('digits not in the anchored span demote EVEN with an approving entailment mock', async () => {
    entailAll(); // approves everything it is asked
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Plan\n1. Take 800 milligrams daily. ⟦A:"take 500 milligrams twice daily"⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.suggestions[0].reason).toBe('digits_unsupported');
    // the demoted claim never reached the entailment call
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('fabricated quote (not in transcript) demotes before entailment', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Subjective\nChest pain radiating to the arm. ⟦A:"crushing chest pain radiating down the left arm"⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.suggestions[0].reason).toBe('anchor_not_in_transcript');
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });
});

describe('FAIL-CLOSED — every verifier failure demotes', () => {
  const ANCHORED = '## Subjective\nNo prior diagnosis of migraines. ⟦A:"have I told you you have had migraines in the past? No. No."⟧';

  it('entailment API throw → verifier_failed, claim demoted', async () => {
    mockEntailment(() => new Error('529 overloaded'));
    const r = await runAnchorVerify({ ...IDS, anchoredDraft: ANCHORED, roleLabeledTranscript: TRANSCRIPT });
    expect(r.body).not.toContain('migraines');
    expect(r.suggestions[0].reason).toBe('verifier_failed');
    expect(r.stats.verifierErrored).toBe(true);
  });

  it('malformed verdict JSON → demote (no .default() rescue — the L6b BLOCK-1 class)', async () => {
    mockEntailment(() => '{"something":"else"}');
    const r = await runAnchorVerify({ ...IDS, anchoredDraft: ANCHORED, roleLabeledTranscript: TRANSCRIPT });
    expect(r.suggestions[0].reason).toBe('verifier_failed');
  });

  it('missing per-claim verdict → that claim demotes', async () => {
    mockEntailment(() => JSON.stringify({ verdicts: [] }));
    const r = await runAnchorVerify({ ...IDS, anchoredDraft: ANCHORED, roleLabeledTranscript: TRANSCRIPT });
    expect(r.suggestions[0].reason).toBe('not_entailed');
  });

  it('duplicate verdicts for one claim → demote (ambiguity resolves against passing)', async () => {
    mockEntailment(() =>
      JSON.stringify({ verdicts: [{ i: 0, entailed: true }, { i: 0, entailed: false }] })
    );
    const r = await runAnchorVerify({ ...IDS, anchoredDraft: ANCHORED, roleLabeledTranscript: TRANSCRIPT });
    expect(r.suggestions[0].reason).toBe('not_entailed');
  });

  it('multiple valid verdict objects in the output → ambiguous → demote all', async () => {
    mockEntailment(() => '{"verdicts":[{"i":0,"entailed":true}]} and again {"verdicts":[{"i":0,"entailed":true}]}');
    const r = await runAnchorVerify({ ...IDS, anchoredDraft: ANCHORED, roleLabeledTranscript: TRANSCRIPT });
    expect(r.suggestions[0].reason).toBe('verifier_failed');
  });

  it('runAnchorVerify never throws on hostile input', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '⟦A:"unterminated\n## ⟦S⟧⟦A:⟧',
      roleLabeledTranscript: '',
    });
    expect(r).toBeDefined();
  });
});

describe('flag-off byte-identity (the rollout guarantee)', () => {
  const L4_INPUT = {
    visitId: 'vis-flag', practiceId: 'p1', userId: 'u1', specialty: 'primary-care',
    roleLabeledTranscript: TRANSCRIPT,
    entities: {
      chief_complaint: null, hpi: null, past_medical_history: [], medications: [],
      allergies: [], family_history: [], social_history: {}, ros: [],
      exam_findings: [], tests_mentioned: [], assessment_discussed: [], plan_discussed: [],
    },
    audioConfidenceStats: null, interpreterMode: false,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any;

  const SOAP = '## Subjective\nx\n\n## Objective\ny\n\n## Assessment\nz\n\n## Plan\n1. w';

  it('flag OFF: L4 system prompt has NO anchor addendum; output persists unmodified; no verify call', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: SOAP });
    const out = await runLayer4GenerateSoap(L4_INPUT);
    const { system, purpose } = mocks.modelCompleteText.mock.calls[0][0];
    expect(purpose).toBe('tm_soap_draft');
    expect(system).not.toContain('EVIDENCE ANCHORS');
    // byte-identical to the builder output — the addendum string is absent.
    // (mirror the layer exactly: it passes the specialty's real guidance)
    const expected = buildSoapSystemPrompt(SYSTEM_DEFAULT_NOTE_TEMPLATE, {
      specialty: 'primary-care',
      specialtyGuidanceText: specialtyGuidance('primary-care') || null,
      audioQualityAlert: null, interpreterAlert: null,
    });
    expect(system).toBe(expected);
    expect(out).toBe(SOAP);
    expect(mocks.modelCompleteText).toHaveBeenCalledTimes(1); // no entailment call
    expect(mocks.prismaUpdate.mock.calls[0][0].data.suggestedClaims).toBeUndefined();
  });

  it('flag ON: AUDIT-ONLY — the whole draft is served, nothing is staged', async () => {
    process.env.TRANSCRIBE_MD_EVIDENCE_ANCHORS = 'true';
    const anchoredOut = [
      '## Subjective',
      'No prior diagnosis of migraines. ⟦A:"have I told you you have had migraines in the past? No. No."⟧',
      'Likely olecranon bursitis.',
      '', '## Objective', 'Formal exam not documented in this encounter.',
      '', '## Assessment', '[not documented]',
      '', '## Plan', '1. Take 500 milligrams twice daily for three days. ⟦A:"take 500 milligrams twice daily for three days."⟧',
    ].join('\n');
    mocks.modelCompleteText.mockImplementation(async (args: { purpose?: string; user?: string }) => {
      if (args?.purpose === 'tm_soap_draft') return { text: anchoredOut };
      if (args?.purpose === 'tm_anchor_entailment') {
        const n = ((args.user ?? '').match(/^CLAIM \d+:/gm) ?? []).length;
        return { text: JSON.stringify({ verdicts: Array.from({ length: n }, (_, i) => ({ i, entailed: true })) }) };
      }
      throw new Error('unexpected');
    });
    const out = await runLayer4GenerateSoap(L4_INPUT);
    const { system } = mocks.modelCompleteText.mock.calls[0][0];
    expect(system).toContain('EVIDENCE ANCHORS');
    expect(out).toContain('No prior diagnosis of migraines.');
    // AUDIT-ONLY (was: `expect(out).not.toContain('bursitis')`).
    //
    // The unanchored line is exactly what the old lane quarantined out of the
    // note. It now stays in the draft the physician reviews and signs — that
    // IS the behaviour change, so this assertion is inverted deliberately
    // rather than deleted. If it ever reverts to "not.toContain", the lane has
    // grown back.
    expect(out).toContain('bursitis');
    expect(out).not.toContain('⟦'); // anchors still stripped
    const data = mocks.prismaUpdate.mock.calls[0][0].data;
    expect(data.soapDraft).toBe(out);
    // No pending-suggestion state, ever. The column is actively CLEARED so a
    // visit cannot keep a lane from an earlier run.
    expect(data.suggestedClaims).toBe(Prisma.DbNull);
  });
});

// ─── Iteration 3 — gate run-3 residual canaries ─────────────────────────────
// The four majority class-(c) claims that survived the single-verdict
// verifier, pinned as the CLASSES that killed them: parenthetical gloss +
// spelled quantification are now DETERMINISTIC (an approving model cannot
// resurrect them); cross-site negation + causal attribution are pinned at
// the k=3 ensemble level (majority ≥2-of-3, errored pass votes no).
describe('iteration 3 — run-3 residual classes + ensemble majority', () => {
  /** Route per-pass verdicts by lens posture in the system prompt. */
  function mockEnsemble(votes: {
    base: boolean | 'error';
    hunter: boolean | 'error';
    skeptic: boolean | 'error';
  }) {
    mocks.modelCompleteText.mockImplementation(
      async (args: { purpose?: string; system?: string; user?: string }) => {
        if (args?.purpose !== 'tm_anchor_entailment')
          throw new Error(`unexpected purpose ${args?.purpose}`);
        const sys = args.system ?? '';
        const v = sys.includes('ELABORATION HUNTER')
          ? votes.hunter
          : sys.includes('CLINICAL SKEPTIC')
            ? votes.skeptic
            : votes.base;
        if (v === 'error') throw new Error('pass down');
        const n = (args.user?.match(/^CLAIM \d+:/gm) ?? []).length;
        return {
          text: JSON.stringify({
            verdicts: Array.from({ length: n }, (_, i) => ({ i, entailed: v })),
          }),
        };
      }
    );
  }

  it('parenthetical gloss ("fundoscopy (examination of the back of the eyes)") demotes DETERMINISTICALLY — approving ensemble cannot overrule', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\nFundoscopy (examination of the back of the eyes) to be arranged. ⟦A:"we will arrange fundoscopy for you"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: we will arrange fundoscopy for you.',
    });
    expect(r.body).not.toContain('Fundoscopy');
    expect(r.suggestions).toHaveLength(1);
    expect(r.suggestions[0].reason).toBe('gloss_unsupported');
  });

  it('span-supported gloss survives (explanation present in the span)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\nFundoscopy (examination of the back of the eyes). ⟦A:"fundoscopy, that is an examination of the back of the eyes"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: fundoscopy, that is an examination of the back of the eyes.',
    });
    expect(r.body).toContain('Fundoscopy');
    expect(r.suggestions).toHaveLength(0);
  });

  it('spelled quantification ("two glasses per week") falls under the digits override — approving ensemble cannot overrule', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\nCut down to two glasses of wine per week initially. ⟦A:"you should try and cut down on the drinking"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: you should try and cut down on the drinking.',
    });
    expect(r.body).not.toContain('two glasses');
    expect(r.suggestions[0].reason).toBe('digits_unsupported');
  });

  it('spelled quantification stated in the span survives ("twice daily" ↔ "twice daily")', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\nTake amoxicillin twice daily. ⟦A:"take the amoxicillin twice daily"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: take the amoxicillin twice daily.',
    });
    expect(r.body).toContain('twice daily');
    expect(r.suggestions).toHaveLength(0);
  });

  it('digit ↔ word equivalence: claim "2 glasses" supported by span "two glasses"', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nDrinks 2 glasses of wine nightly. ⟦A:"I have two glasses of wine most nights"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: I have two glasses of wine most nights.',
    });
    expect(r.body).toContain('2 glasses');
    expect(r.suggestions).toHaveLength(0);
  });

  it('cross-site negation ("ears: no blockage" anchored to a NOSE span) demotes on ensemble majority', async () => {
    mockEnsemble({ base: true, hunter: false, skeptic: false });
    const r = await runAnchorVerify({
      ...IDS,
      // The run-3 escape shape: negation polarity matches (both sides
      // negate) and the subject prefix ("block…") appears in the span — the
      // deterministic overrides PASS by design; the ensemble must catch it.
      anchoredDraft:
        '## Subjective\nEars feel okay with no pain or blockage. ⟦A:"no, my nose just feels blocked all the time"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: no, my nose just feels blocked all the time.',
    });
    expect(r.body).not.toContain('Ears feel okay');
    expect(r.suggestions[0].reason).toBe('not_entailed');
  });

  it('causal attribution ("screen-related eye strain") with 2-of-3 entailed SURVIVES (majority keeps)', async () => {
    mockEnsemble({ base: true, hunter: true, skeptic: false });
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Assessment\nLikely screen-related eye strain. ⟦A:"my eyes get tired when I work at the computer all day"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: my eyes get tired when I work at the computer all day.',
    });
    expect(r.body).toContain('screen-related eye strain');
    expect(r.suggestions).toHaveLength(0);
  });

  it('causal attribution with 1-of-3 entailed demotes (majority rejects)', async () => {
    mockEnsemble({ base: false, hunter: true, skeptic: false });
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Assessment\nLikely screen-related eye strain. ⟦A:"my eyes get tired when I work at the computer all day"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: my eyes get tired when I work at the computer all day.',
    });
    expect(r.body).not.toContain('eye strain');
    expect(r.suggestions[0].reason).toBe('not_entailed');
  });

  it('one errored pass + both remaining entailed → survives (error votes no, 2 yes ≥ majority)', async () => {
    mockEnsemble({ base: 'error', hunter: true, skeptic: true });
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nReports tiredness. ⟦A:"I have been feeling tired"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: I have been feeling tired.',
    });
    expect(r.body).toContain('Reports tiredness');
    expect(r.suggestions).toHaveLength(0);
    expect(r.stats.entailmentPassErrors).toBe(1);
  });

  it('one errored pass + split remaining → demotes (1 yes < majority)', async () => {
    mockEnsemble({ base: 'error', hunter: true, skeptic: false });
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nReports tiredness. ⟦A:"I have been feeling tired"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: I have been feeling tired.',
    });
    expect(r.body).not.toContain('Reports tiredness');
    expect(r.suggestions[0].reason).toBe('not_entailed');
  });

  it('two errored passes → whole stage fails closed (verifier_failed)', async () => {
    mockEnsemble({ base: 'error', hunter: 'error', skeptic: true });
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nReports tiredness. ⟦A:"I have been feeling tired"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: I have been feeling tired.',
    });
    expect(r.body).not.toContain('Reports tiredness');
    expect(r.suggestions[0].reason).toBe('verifier_failed');
    expect(r.stats.verifierErrored).toBe(true);
  });

  it('ensemble fires exactly 3 entailment calls per verify', async () => {
    entailAll();
    await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nReports tiredness. ⟦A:"I have been feeling tired"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: I have been feeling tired.',
    });
    expect(mocks.modelCompleteText).toHaveBeenCalledTimes(3);
  });
});

// ─── Iteration 4 — decisive-run residual class: clinical-reasoning verbs ────
// The three unanimous class-(c) of run 20260612T153417Z, pinned as the
// deterministic process-verb override (approving ensemble cannot overrule).
describe('iteration 4 — clinical-reasoning verb override', () => {
  it('"if migraine with aura is confirmed" (contingency plan) demotes when the span never speaks the act', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\nMay need to change the pill if migraine with aura is confirmed. ⟦A:"I get a flashing in my eyes before the headache starts"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: I get a flashing in my eyes before the headache starts.',
    });
    expect(r.body).not.toContain('is confirmed');
    expect(r.suggestions[0].reason).toBe('process_assertion_unsupported');
  });

  it('"mother confirmed antihistamines are available at home" demotes against a span that merely mentions them', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\nMother confirmed antihistamines are available at home. ⟦A:"we have antihistamines at home"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: we have antihistamines at home.',
    });
    expect(r.body).not.toContain('confirmed');
    expect(r.suggestions[0].reason).toBe('process_assertion_unsupported');
  });

  it('"PE was considered and partially addressed by history" demotes (process assertion never spoken)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Assessment\nPulmonary embolism was considered and partially addressed by history. ⟦A:"have you been on any long flights recently? No."⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: have you been on any long flights recently? No.',
    });
    expect(r.body).not.toContain('considered');
    expect(r.suggestions[0].reason).toBe('process_assertion_unsupported');
  });

  it('a span that SPEAKS the act legitimately supports it ("can you confirm…? I confirm")', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nPatient confirmed she takes the medication daily. ⟦A:"can you confirm you take it every day? yes, I confirm"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: can you confirm you take it every day? yes, I confirm.',
    });
    expect(r.body).toContain('Patient confirmed');
    expect(r.suggestions).toHaveLength(0);
  });

  it('"ruled out" demotes unless the span uses the verb ("we can rule that out" survives)', async () => {
    entailAll();
    const demoted = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Assessment\nSerious causes ruled out. ⟦A:"your blood tests came back normal"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: your blood tests came back normal.',
    });
    expect(demoted.suggestions[0].reason).toBe('process_assertion_unsupported');
    const kept = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Assessment\nSerious causes ruled out. ⟦A:"the tests were normal so we can rule that out"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: the tests were normal so we can rule that out.',
    });
    expect(kept.body).toContain('ruled out');
    expect(kept.suggestions).toHaveLength(0);
  });
});

describe('iteration 4 — noun homonyms stay exempt; boilerplate verb forms demote', () => {
  it('"screened and denied" boilerplate demotes; noun "screen-related" does not trip the override', async () => {
    entailAll();
    const demoted = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nSuicidal ideation screened and denied. ⟦A:"I have been feeling tired"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: I have been feeling tired.',
    });
    expect(demoted.suggestions[0].reason).toBe('process_assertion_unsupported');
    const kept = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Assessment\nLikely screen-related eye strain. ⟦A:"my eyes get tired when I work at the computer all day"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: my eyes get tired when I work at the computer all day.',
    });
    expect(kept.body).toContain('screen-related');
  });
});

// ─── Iteration 5 — gate re-run #1 residual class: form/route specification ──
describe('iteration 5 — drug form/route/class specification override', () => {
  it('"oral contraceptive pill" demotes against a span that only says "the pill"', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Medications\nOral contraceptive pill, ongoing. ⟦A:"I take the pill every day"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: I take the pill every day.',
    });
    expect(r.body).not.toContain('Oral contraceptive');
    expect(r.suggestions[0].reason).toBe('form_route_unsupported');
  });

  it('"topical steroid cream" demotes against a span that only says "steroid cream"', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Medications\nTopical steroid cream applied last night. ⟦A:"I put some steroid cream on it last night"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: I put some steroid cream on it last night.',
    });
    expect(r.body).not.toContain('Topical');
    expect(r.suggestions[0].reason).toBe('form_route_unsupported');
  });

  it('a span that states the form supports it ("oral antibiotics" ↔ "oral antibiotics")', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Plan\nStart oral antibiotics. ⟦A:"I will start you on some oral antibiotics"⟧',
      roleLabeledTranscript:
        '[Doctor #0, 0:10]: I will start you on some oral antibiotics.',
    });
    expect(r.body).toContain('oral antibiotics');
    expect(r.suggestions).toHaveLength(0);
  });

  it('"contraceptive" alone (class specification) demotes when the span never says it', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Medications\nContraceptive pill, ongoing. ⟦A:"I take the pill every day"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: I take the pill every day.',
    });
    expect(r.body).not.toContain('Contraceptive');
    expect(r.suggestions[0].reason).toBe('form_route_unsupported');
  });
});

// ─── Live-voice prod-smoke defects (2026-06-13) ─────────────────────────────
// Phase 1: an Assessment whose every narrative line demotes must NOT render
// empty — it back-fills with the visible review placeholder + flags the
// section. Phase 2: surviving Plan items renumber contiguously.
import { EMPTY_SECTION_PLACEHOLDER } from '@/lib/soap-format';

describe('empty-section back-fill (Phase 1 blocker) + plan renumber (Phase 2)', () => {
  it('an Assessment with EVERY line demoted renders the placeholder, never blank; the section is flagged', async () => {
    // Both Assessment sentences are unanchored boilerplate → no_anchor demote.
    // Plan keeps anchored items; Subjective keeps one.
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: [
        '## Subjective',
        'Patient reports blood pressure has been high at home. ⟦A:"my blood pressure has been running high at home"⟧',
        '## Assessment',
        'Hypertension, uncontrolled, likely requiring intensification.',
        'Hyperlipidemia, stable on current therapy.',
        '## Plan',
        '1. Continue lisinopril. ⟦A:"keep taking the lisinopril"⟧',
        '2. Start amlodipine. ⟦A:"I am going to start you on amlodipine"⟧',
      ].join('\n'),
      roleLabeledTranscript: [
        '[Patient #1, 0:10]: my blood pressure has been running high at home.',
        '[Doctor #0, 0:20]: keep taking the lisinopril.',
        '[Doctor #0, 0:30]: I am going to start you on amlodipine.',
      ].join('\n'),
    });
    // Assessment is NOT blank — it carries the placeholder.
    const assessmentBlock = r.body.split('## Assessment')[1].split('##')[0];
    expect(assessmentBlock).toContain(EMPTY_SECTION_PLACEHOLDER);
    expect(assessmentBlock.replace(EMPTY_SECTION_PLACEHOLDER, '').trim().length).toBe(0);
    // The demoted assessment content is in the lane, not the body.
    expect(r.body).not.toContain('uncontrolled, likely requiring');
    expect(r.suggestions.some((s) => s.text.includes('Hypertension, uncontrolled'))).toBe(true);
    // Flagged for the review banner.
    expect(r.stats.filledEmptySections).toContain('Assessment');
  });

  it('a section that legitimately holds [not documented] is NOT back-filled', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: ['## Objective', '[not documented]', '## Plan', '1. Continue meds. ⟦A:"keep taking your meds"⟧'].join('\n'),
      roleLabeledTranscript: '[Doctor #0, 0:10]: keep taking your meds.',
    });
    expect(r.body).not.toContain(EMPTY_SECTION_PLACEHOLDER);
    expect(r.stats.filledEmptySections ?? []).toHaveLength(0);
  });

  it('surviving Plan items renumber contiguously when middle items demote', async () => {
    // Items 1 and 3 anchored+kept; item 2 unanchored → demoted → body should
    // renumber the two survivors to 1,2 (not 1,3).
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: [
        '## Plan',
        '1. Continue lisinopril 20 mg daily. ⟦A:"continue the lisinopril twenty milligrams"⟧',
        '2. Refer to bariatric surgery for evaluation.',
        '3. Recheck in four weeks. ⟦A:"come back in four weeks"⟧',
      ].join('\n'),
      roleLabeledTranscript: [
        '[Doctor #0, 0:10]: continue the lisinopril twenty milligrams.',
        '[Doctor #0, 0:20]: come back in four weeks.',
      ].join('\n'),
    });
    expect(r.body).toContain('1. Continue lisinopril 20 mg daily.');
    expect(r.body).toContain('2. Recheck in four weeks.');
    expect(r.body).not.toMatch(/^3\./m);
    expect(r.body).not.toContain('bariatric surgery');
  });
});

// ─── Verifier false-positive recovery (2026-06-16) ──────────────────────────
// Two SAFE mechanical false positives in the deterministic stage demoted
// correctly-dictated content. FIX 1: the ≥3 raw-token anchor floor killed
// genuine SHORT anchors that are verbatim in the transcript. FIX 2: the
// "[not documented]" exemption only fired after a BOLD label, and the
// canonical ultrasound Comparison-negative was treated as an unanchored
// claim. The fabrication-catch guarantees (verbatim substring + every
// deterministic override + entailment) are UNCHANGED — proven by the safety
// canaries below, which still demote a degenerate and a fabricated anchor.
describe('FIX 1 — short content-token anchors are recovered to the body', () => {
  // Transcript carries each short span VERBATIM so the (unchanged) substring
  // check passes; the OLD ≥3-token floor would have demoted all three.
  const SHORT_TRANSCRIPT = [
    '[Doctor #0, 0:10]: blood pressure is fine, lungs clear, no edema today.',
    '[Doctor #0, 0:20]: continue lisinopril and recheck in four weeks.',
  ].join('\n');

  it('"lungs clear" (2 content tokens, verbatim) survives — body, not lane', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Objective\nLungs clear. ⟦A:"lungs clear"⟧',
      roleLabeledTranscript: SHORT_TRANSCRIPT,
    });
    expect(r.body).toContain('Lungs clear.');
    expect(r.body).not.toContain('⟦');
    expect(r.suggestions).toHaveLength(0);
  });

  it('"No edema." anchored to the 2-token "no edema" span survives (one content token is enough)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Objective\nNo edema. ⟦A:"no edema"⟧',
      roleLabeledTranscript: SHORT_TRANSCRIPT,
    });
    expect(r.body).toContain('No edema.');
    expect(r.suggestions).toHaveLength(0);
  });

  it('"Continue lisinopril." anchored to the 2-token span survives', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Plan\n1. Continue lisinopril. ⟦A:"continue lisinopril"⟧',
      roleLabeledTranscript: SHORT_TRANSCRIPT,
    });
    expect(r.body).toContain('Continue lisinopril.');
    expect(r.suggestions).toHaveLength(0);
  });
});

describe('FIX 1 safety — the content-token floor still rejects degenerate + fabricated anchors', () => {
  it('an all-stopword anchor ("of the") anchors nothing → demoted, NOT smuggled to the body', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      // "of the" IS a literal substring of the transcript — the verbatim check
      // alone would let it through; the content-token floor is what blocks it.
      anchoredDraft: '## Assessment\nLikely olecranon bursitis. ⟦A:"of the"⟧',
      roleLabeledTranscript: '[Doctor #0, 0:10]: it is on the side of the elbow.',
    });
    expect(r.body).not.toContain('bursitis');
    expect(r.suggestions[0].reason).toBe('anchor_not_in_transcript');
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('a short FABRICATED anchor (2 content tokens, NOT in transcript) still demotes via the unchanged substring check', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Assessment\nSevere sepsis. ⟦A:"severe sepsis"⟧',
      roleLabeledTranscript: '[Patient #1, 0:10]: my elbow is swollen.',
    });
    expect(r.body).not.toContain('Severe sepsis');
    expect(r.suggestions[0].reason).toBe('anchor_not_in_transcript');
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });
});

describe('FIX 2 — [not documented] after a PLAIN label + the Comparison-negative are exempt scaffolding', () => {
  it('a plain "Label: [not documented]" line (no bold) is exempt — body, no entailment call', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Subjective\nFamily History: [not documented]\n\n## Objective\nComparison: [not documented]',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('Family History: [not documented]');
    expect(r.body).toContain('Comparison: [not documented]');
    expect(r.suggestions).toHaveLength(0);
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('the bold form still works (no regression of the existing exemption)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Subjective\n**Allergies:** [not documented]',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('**Allergies:** [not documented]');
    expect(r.suggestions).toHaveLength(0);
  });

  it('the canonical ultrasound Comparison-negative needs no anchor — body, no entailment call', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Comparison\nNo prior study available for comparison.',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('No prior study available for comparison.');
    expect(r.suggestions).toHaveLength(0);
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('a bracketed "[not documented]" with NO label colon is NOT newly exempted (the plain-label form requires its colon)', async () => {
    // The plain-label alternative only matches a "<label>:" prefix; a
    // sentence-shaped prefix with no trailing colon does not qualify, so this
    // line is not exempt and (unanchored) demotes exactly as before.
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Assessment\nPatient has crushing chest pain [not documented]',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('crushing chest pain');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// feat/structured-templates (2026-07-02) — table/option scaffolding exemptions.
// Pre-registered: docs/eval-runs/verifier-table-option-fix-20260702T165454Z.md.
// The safety invariant these pin: SCAFFOLDING (separators, headers, unfilled
// rows, unchecked options) is exempt; CLAIMS (checked options, filled cells)
// still anchor + verify — a fabricated selection must ALWAYS demote.
// ─────────────────────────────────────────────────────────────────────────────
describe('structure-aware exemptions — tables + option-sets (pre-registered pass)', () => {
  it('(a) an UNCHECKED option line is exempt scaffolding — body, no lane row, no entailment call', async () => {
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Lungs\n- [ ] Clear to auscultation\n- [ ] Wheezes\n- [ ] Crackles',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('- [ ] Clear to auscultation');
    expect(r.body).toContain('- [ ] Crackles');
    expect(r.suggestions).toHaveLength(0);
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('(b1) FABRICATED-OPTION canary: a checked option with NO anchor demotes no_anchor', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Lungs\n- [x] Wheezes present',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('[x] Wheezes');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });

  it('(b2) FABRICATED-OPTION canary: a checked option with a NON-TRANSCRIPT anchor demotes anchor_not_in_transcript', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Lungs\n- [x] Wheezes present ⟦A:"diffuse expiratory wheezes heard"⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('[x] Wheezes');
    expect(r.suggestions[0].reason).toBe('anchor_not_in_transcript');
  });

  it('(c1) an anchored table DATA row with dictated digits survives to the body', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Medications\n| Medication | Dose |\n| --- | --- |\n| The pill | 500 milligrams twice daily | ⟦A:"take 500 milligrams twice daily"⟧',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('| The pill | 500 milligrams twice daily |');
    expect(r.suggestions).toHaveLength(0);
  });

  it('(c2) an UNANCHORED table data row still demotes — table shape is not a free pass', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Medications\n| Medication | Dose |\n| --- | --- |\n| Amoxicillin | 875 mg |',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('Amoxicillin');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });

  it('(d) header + separator rows are exempt scaffolding — no lane rows, no entailment call', async () => {
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Vitals\n| Vital | Value |\n| --- | --- |',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('| Vital | Value |');
    expect(r.body).toContain('| --- | --- |');
    expect(r.suggestions).toHaveLength(0);
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('(e) unfilled fixed-row + empty-cell rows are exempt scaffolding', async () => {
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Vitals\n| Vital | Value |\n| --- | --- |\n| BP | [not documented] |\n| Allergies |  |\n| Comparison | — |',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('| BP | [not documented] |');
    expect(r.body).toContain('| Allergies |  |');
    expect(r.suggestions).toHaveLength(0);
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('(f) "Label: [not addressed]" is exempt like [not documented]', async () => {
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## ROS\nSmoking status: [not addressed]',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).toContain('Smoking status: [not addressed]');
    expect(r.suggestions).toHaveLength(0);
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });

  it('(g) a sentence merely containing "[not addressed]" without the label-colon shape is NOT swept', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Assessment\nPatient has severe sepsis [not addressed]',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('severe sepsis');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });
});

// ============================================================================
// B4 STEP 2 — the stage-level MOCK short-circuit is GONE, and the stage still
// behaves identically.
// ----------------------------------------------------------------------------
// Until 2026-08-10 `entailmentStage` returned all-entailed under
// MOCK_AI_CALLS *before* any model call. That is a mock boundary ABOVE the
// meter — the defect B4 step 1 removed from Deepgram and embed — and it made
// B4's own gate ("one usage event per stage") unsatisfiable for
// `tm_anchor_entailment` by construction.
//
// ⚠️ EVERY OTHER TEST IN THIS FILE DELETES `MOCK_AI_CALLS` IN `beforeEach`,
// WHICH IS EXACTLY WHY NOTHING HERE EVER SAW IT. The short-circuit was live
// only on the path no unit test takes. These two arms are the ones that set
// the flag on purpose.
// ============================================================================
describe('B4 step 2 — under MOCK_AI_CALLS the ensemble RUNS rather than being skipped', () => {
  // The same supported claim the "MUST pass" canary uses: anchored, in the
  // transcript, and entailment-approved — so it REACHES the verifier instead
  // of being demoted deterministically before any model call.
  const ANCHORED =
    '## Subjective\nNo prior diagnosis of migraines. ⟦A:"have I told you you have had migraines in the past? No. No."⟧';

  afterEach(() => {
    delete process.env.MOCK_AI_CALLS;
  });

  it('issues the k=3 ensemble instead of short-circuiting above the meter', async () => {
    process.env.MOCK_AI_CALLS = 'true';
    entailAll();
    await runAnchorVerify({
      ...IDS,
      anchoredDraft: ANCHORED,
      roleLabeledTranscript: TRANSCRIPT,
    });

    // ⚠️ THE MUTATION THAT MAKES THIS RED IS RESTORING THE SHORT-CIRCUIT:
    // it drives this to 0, which is the number the meter used to see.
    expect(mocks.modelCompleteText).toHaveBeenCalledTimes(3);
    expect(
      mocks.modelCompleteText.mock.calls.every(
        (c: unknown[]) => (c[0] as { purpose?: string })?.purpose === 'tm_anchor_entailment'
      )
    ).toBe(true);
  });

  it('and a claim with NO claims still issues nothing — no work is not a suppressed call', async () => {
    process.env.MOCK_AI_CALLS = 'true';
    entailAll();
    // A body the claim extractor finds nothing judgeable in. Production agrees
    // this is the real zero: 73 of 73 visits carrying the stage carry exactly
    // 3 calls, so the distribution is {0, 3} and nothing between.
    await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Vitals\n| BP | [not documented] |',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(mocks.modelCompleteText).not.toHaveBeenCalled();
  });
});
