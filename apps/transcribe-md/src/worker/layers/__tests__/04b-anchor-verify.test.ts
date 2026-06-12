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

import { beforeEach, describe, expect, it, vi } from 'vitest';

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

  it('flag ON: addendum present; verified body persisted; suggestions stored', async () => {
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
    expect(out).not.toContain('bursitis'); // demoted
    expect(out).not.toContain('⟦'); // stripped
    const data = mocks.prismaUpdate.mock.calls[0][0].data;
    expect(data.soapDraft).toBe(out);
    expect(Array.isArray(data.suggestedClaims)).toBe(true);
    expect(data.suggestedClaims[0].text).toContain('olecranon bursitis');
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

// ─── Polarity-alignment precision fix (2026-06-13, #311 smoke misfire) ──────
// 31/104 negation_mismatch demotions in the final gate run were POSITIVE
// claims killed by an INCIDENTAL span negation ("no missed doses",
// "Do you smoke? No."). The rule now demotes a positive claim only when a
// span negation TARGETS the claim's content; both dangerous directions
// (invented denial; true polarity flip) still demote deterministically.
describe('polarity alignment — incidental span negation no longer misfires', () => {
  it('the lisinopril misfire (verbatim from the prod smoke) now SURVIVES: positive claim, incidental "no missed doses"', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Medications\nLisinopril 20 mg once daily. ⟦A:"On lisinopril 20mg once daily, no missed doses"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: On lisinopril 20mg once daily, no missed doses.',
    });
    expect(r.body).toContain('Lisinopril 20 mg once daily');
    expect(r.suggestions).toHaveLength(0);
  });

  it('the smoking sibling (3 cases in the final run) now reaches the ensemble: "Non-smoker" vs "Do you smoke? No."', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Social History\nSmoking status documented. ⟦A:"And do you smoke? No."⟧',
      roleLabeledTranscript: '[Doctor #0, 0:10]: And do you smoke? No.',
    });
    expect(r.body).toContain('Smoking status documented');
    expect(r.suggestions).toHaveLength(0);
  });

  it('a TRUE polarity flip still demotes: positive claim vs a span negation targeting its content', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Medications\nTaking lisinopril daily. ⟦A:"I am not taking lisinopril anymore"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: I am not taking lisinopril anymore.',
    });
    expect(r.body).not.toContain('Taking lisinopril');
    expect(r.suggestions[0].reason).toBe('negation_mismatch');
  });

  it('an INVENTED DENIAL still demotes: negative claim vs a span with no negation (approving ensemble cannot overrule)', async () => {
    entailAll();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft:
        '## Subjective\nNo chest pain reported. ⟦A:"I have been having some chest pain"⟧',
      roleLabeledTranscript:
        '[Patient #1, 0:10]: I have been having some chest pain.',
    });
    expect(r.body).not.toContain('No chest pain');
    expect(r.suggestions[0].reason).toBe('negation_mismatch');
  });
});
