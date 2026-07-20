// ============================================================================
// L4b — template-scaffold / anchored-option-carrier exemption canaries.
// Pre-registered: docs/eval-runs/verifier-scaffold-exemption-20260706T202636Z.md
// Pins the HARD INVARIANTS: fixed scaffold exempt (only WITH scaffold + only
// exact), filled carriers judged on their PICKS, and every fabrication path
// (fabricated option / contradicting pick / laterality swap / frozen override)
// STILL demotes. Entailment is mocked (deterministic CI).
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ modelCompleteText: vi.fn() }));
vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText } };
});
vi.mock('@meddoc/db', () => ({
  default: {
    $queryRaw: vi.fn().mockResolvedValue([
      { id: 'u', practiceId: 'p', email: 'synthetic@example.test' },
    ]),
    transcribeVisit: { update: vi.fn() },
  },
}));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { runAnchorVerify } from '../04b-anchor-verify';
import { buildTemplateScaffold } from '../../note-templates/template-scaffold';
import type { NoteTemplateSection } from '../../note-templates/system-default-template';

const IDS = { visitId: 'v', practiceId: 'p', userId: 'u' };

/** Capture the CLAIM lines sent to the judge; respond entailed unless the
 *  claim matches a `reject` predicate (models a real judge rejecting an
 *  unsupported pick). */
let judgeClaims: string[] = [];
function mockJudge(reject: (claim: string) => boolean = () => false) {
  judgeClaims = [];
  mocks.modelCompleteText.mockImplementation(async (args: { purpose?: string; user?: string }) => {
    if (args?.purpose !== 'tm_anchor_entailment') throw new Error(`unexpected ${args?.purpose}`);
    const claims = [...(args.user ?? '').matchAll(/^CLAIM (\d+): (.*)$/gm)];
    judgeClaims.push(...claims.map((m) => m[2]));
    const verdicts = claims.map((m) => ({ i: Number(m[1]), entailed: !reject(m[2]) }));
    return { text: JSON.stringify({ verdicts }) };
  });
}

function section(key: string, defaultText: string): NoteTemplateSection {
  return {
    key, label: key, order: 1, formatHint: 'prose', styleInstructions: null,
    defaultText, defaultTextMode: 'scaffold_confirm', structure: null,
  };
}

// Realistic WM_IOV-style scaffold.
const SCAFFOLD = buildTemplateScaffold([
  section('technique', 'A duplex Doppler color flow ultrasound study was performed documenting the venous systems.'),
  section('findings',
    'Right Leg:\n' +
    'The {{one of: great saphenous vein | small saphenous vein}} from the {{one of: saphenofemoral junction | mid thigh}} to the {{one of: mid thigh | distal calf}} was found to have had previous treatment {{one of: and is absent. | , however, there has been a recurrence.}}\n' +
    'Clinical correlation with the above findings is required.'),
  section('impression',
    'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive. | is absent.}}\n' +
    'Left {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive. | is absent.}}'),
  section('deep',
    'Right deep venous system {{one of: without evidence of obstruction or insufficiency. | with evidence of an acute DVT of CFV, FV, POP V, PTV.}}'),
]);

const TRANSCRIPT =
  'On the right side the great saphenous vein had previous ablation and there has been a recurrence, ' +
  'with reflux from the saphenofemoral junction to the mid thigh. ' +
  'The right great saphenous vein is reflux positive. ' +
  'The right deep venous system shows no evidence of deep vein thrombosis. ' +
  'The left leg is normal with no reflux.';

beforeEach(() => { vi.clearAllMocks(); delete process.env.MOCK_AI_CALLS; });

describe('Bucket A — fixed template boilerplate', () => {
  it('a fixed-scaffold line is EXEMPT (into body) with scaffold, even with no anchor', async () => {
    mockJudge();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Technique\nA duplex Doppler color flow ultrasound study was performed documenting the venous systems.',
      roleLabeledTranscript: TRANSCRIPT,
      templateScaffold: SCAFFOLD,
    });
    expect(r.body).toContain('duplex Doppler color flow');
    expect(r.suggestions).toHaveLength(0);
  });

  it('WITHOUT scaffold the same boilerplate demotes (no_anchor) — byte-identical to today', async () => {
    mockJudge();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Technique\nA duplex Doppler color flow ultrasound study was performed documenting the venous systems.',
      roleLabeledTranscript: TRANSCRIPT,
    });
    expect(r.body).not.toContain('duplex Doppler');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });

  it('a real claim that merely CONTAINS a scaffold label is NOT exempt', async () => {
    mockJudge();
    const r = await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Findings\nRight Leg: there is a large tender mass.',
      roleLabeledTranscript: TRANSCRIPT,
      templateScaffold: SCAFFOLD,
    });
    expect(r.suggestions[0].reason).toBe('no_anchor'); // unanchored real claim still demotes
  });
});

describe('Bucket B — filled carriers judged on their picks', () => {
  it('a supported filled carrier SURVIVES, and the judge is given the REDUCED claim (picks, not boilerplate)', async () => {
    mockJudge();
    const line = 'The great saphenous vein from the saphenofemoral junction to the mid thigh was found to have had previous treatment, however, there has been a recurrence. ⟦A:"the great saphenous vein had previous ablation and there has been a recurrence, with reflux from the saphenofemoral junction to the mid thigh"⟧';
    const r = await runAnchorVerify({
      ...IDS, anchoredDraft: `## Findings\n${line}`, roleLabeledTranscript: TRANSCRIPT, templateScaffold: SCAFFOLD,
    });
    expect(r.body).toContain('great saphenous vein from the saphenofemoral junction to the mid thigh');
    // judge saw the reduced claim (picks), NOT the connective boilerplate
    expect(judgeClaims.some((c) => c.includes('great saphenous vein') && !c.includes('was found to have had previous treatment'))).toBe(true);
  });

  it('INVARIANT: a filled slot whose pick the dictation does NOT support still demotes (judge rejects the reduced claim)', async () => {
    // dictation says GREAT saphenous vein; model picks SMALL saphenous vein
    // (a valid template option) — no polarity/digit conflict, so ONLY the
    // judge can catch it: it must reject the reduced pick.
    mockJudge((claim) => /small saphenous vein/.test(claim));
    const line = 'Right small saphenous vein is reflux positive. ⟦A:"The right great saphenous vein is reflux positive."⟧';
    const r = await runAnchorVerify({
      ...IDS, anchoredDraft: `## Impression\n${line}`, roleLabeledTranscript: TRANSCRIPT, templateScaffold: SCAFFOLD,
    });
    expect(r.body).not.toContain('small saphenous vein');
    expect(r.suggestions.some((s) => s.reason === 'not_entailed')).toBe(true);
    // the judge received the reduced pick, so it could reject it
    expect(judgeClaims.some((c) => c.includes('small saphenous vein'))).toBe(true);
  });

  it('an UNANCHORED carrier whose picks are grounded in the transcript survives (scaffold the model reproduced without a quote)', async () => {
    mockJudge();
    // no ⟦A:…⟧ anchor; every pick is in the transcript
    const line = 'The great saphenous vein from the saphenofemoral junction to the mid thigh was found to have had previous treatment, however, there has been a recurrence.';
    const r = await runAnchorVerify({
      ...IDS, anchoredDraft: `## Findings\n${line}`, roleLabeledTranscript: TRANSCRIPT, templateScaffold: SCAFFOLD,
    });
    expect(r.body).toContain('great saphenous vein from the saphenofemoral junction to the mid thigh');
    expect(r.suggestions).toHaveLength(0);
  });

  it('INVARIANT: an UNANCHORED carrier whose pick carries a short abbreviation the dictation lacks still demotes (grounding hole closed)', async () => {
    mockJudge();
    // transcript says "no evidence of deep vein thrombosis"; this pick asserts
    // an acute DVT of CFV/FV/POP/PTV — short abbreviations NOT in the dictation.
    const line = 'Right deep venous system with evidence of an acute DVT of CFV, FV, POP V, PTV.';
    const r = await runAnchorVerify({
      ...IDS, anchoredDraft: `## Impression\n${line}`, roleLabeledTranscript: TRANSCRIPT, templateScaffold: SCAFFOLD,
    });
    expect(r.body).not.toContain('acute DVT');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });

  it('INVARIANT: an UNANCHORED carrier whose pick is NOT in the transcript still demotes (undictated pick)', async () => {
    mockJudge();
    // "distal calf" is a valid template option but the transcript says "mid thigh"
    const line = 'The great saphenous vein from the saphenofemoral junction to the distal calf was found to have had previous treatment, however, there has been a recurrence.';
    const r = await runAnchorVerify({
      ...IDS, anchoredDraft: `## Findings\n${line}`, roleLabeledTranscript: TRANSCRIPT, templateScaffold: SCAFFOLD,
    });
    expect(r.body).not.toContain('distal calf');
    expect(r.suggestions[0].reason).toBe('no_anchor');
  });

  it('INVARIANT: a laterality/polarity contradiction on a carrier still demotes via the FROZEN negation override (before the judge)', async () => {
    mockJudge(); // judge would approve — but the deterministic override fires first
    // left leg is normal ("no reflux"); claiming it reflux-positive is a
    // polarity mismatch the frozen negation check catches on the FULL line.
    const line = 'Left great saphenous vein is reflux positive. ⟦A:"The left leg is normal with no reflux."⟧';
    const r = await runAnchorVerify({
      ...IDS, anchoredDraft: `## Impression\n${line}`, roleLabeledTranscript: TRANSCRIPT, templateScaffold: SCAFFOLD,
    });
    expect(r.body).not.toContain('Left great saphenous vein is reflux positive');
    expect(r.suggestions[0].reason).toBe('negation_mismatch');
  });

  it('INVARIANT: a FABRICATED option not in the template never takes the carrier path (judge sees the full line) and demotes', async () => {
    mockJudge((claim) => /thrombosed/.test(claim));
    const line = 'Right great saphenous vein is thrombosed with acute clot. ⟦A:"The right great saphenous vein is reflux positive."⟧';
    const r = await runAnchorVerify({
      ...IDS, anchoredDraft: `## Impression\n${line}`, roleLabeledTranscript: TRANSCRIPT, templateScaffold: SCAFFOLD,
    });
    expect(r.body).not.toContain('thrombosed');
    // full line reached the judge (no reduction), boilerplate intact
    expect(judgeClaims.some((c) => c.includes('thrombosed with acute clot'))).toBe(true);
  });

});

describe('byte-identity — no scaffold supplied', () => {
  it('a free-text claim is judged on its FULL text (entailText absent)', async () => {
    mockJudge();
    await runAnchorVerify({
      ...IDS,
      anchoredDraft: '## Impression\nRight great saphenous vein is reflux positive. ⟦A:"The right great saphenous vein is reflux positive."⟧',
      roleLabeledTranscript: TRANSCRIPT,
      // no templateScaffold
    });
    expect(judgeClaims[0]).toBe('Right great saphenous vein is reflux positive.');
  });
});
