// @vitest-environment node
// ============================================================================
// B4's CLOSING GATE, CLOSED — `tm_anchor_entailment` becomes COUNTABLE, and the
// fixture that makes it countable is checked against the transcript it quotes.
// ----------------------------------------------------------------------------
// The closing step (ruling 86) left exactly one enumerated stage UNPROVEN and
// named the closure without attempting it: *"an anchored `tm_soap_draft`
// variant on the same env-selected pattern"*. This is that variant, and this is
// the gate for it.
//
// Two conditions have to hold before this stage can emit anything, and only one
// was ever fixable by a flag:
//
//   1. `TRANSCRIBE_MD_EVIDENCE_ANCHORS=true`, so L4b runs at all — set on the
//      QA stack by the closing step.
//   2. L4's draft must actually CARRY `⟦A:…⟧` anchors. Under mock it did not
//      (`grep -c '⟦A:' mock.ts` → 0), so `deterministicStage` swept every line
//      into the exempt bucket, `toEntail` was empty, and `entailmentStage`
//      returned at `04b-anchor-verify.ts:999` before any model call.
//
// ⚠️ WHY THIS GATE IS NOT OPTIONAL, AND WHY IT ASSERTS THE SPANS DIRECTLY.
// The stage's expectation is `{0, 3}` — zero is PERMITTED, because a visit with
// no anchored claim correctly makes no call. So every way this fixture can
// break degrades to a legal zero:
//
//   · an anchor span stops being a literal substring of the transcript
//     → every claim demotes `anchor_not_in_transcript` → `toEntail` empty → 0
//   · a claim acquires a digit, a gloss or a negation the span cannot support
//     → the hard overrides demote it → 0
//   · the flag stops reaching the fixture → the unanchored default → 0
//
// **None of those is red anywhere.** The coverage run would report the stage
// UNPROVEN again — which is honest, and is a signal nobody is obliged to read —
// and every other suite would stay green. That is the whole reason the spans
// are DERIVED from `MOCK_TRANSCRIPT_UTTERANCES` rather than copied, and the
// reason this gate asserts the derivation instead of trusting it.
//
// ── WHAT THIS GATE ASSERTS ────────────────────────────────────────────────
//   OFF        flag unset → the fixture carries NO anchor, no claim is
//              verified, and ZERO usage rows appear. Today's behaviour,
//              unchanged — this is the negative control for the whole item.
//   DERIVED    every anchor span in the anchored fixture is a literal
//              substring of the normalized mock transcript...
//   CONTROL    ...and a span that is NOT gets demoted, so the assertion above
//              is discriminating rather than vacuous.
//   CLAIMS     flag on → claims actually SURVIVE the deterministic gauntlet
//              and reach the entailment stage.
//   CLEAN      nothing demotes: the anchored note says only what its own
//              transcript says, so the body keeps every drafted line.
//   ENSEMBLE   the usage rows equal ENSEMBLE_LENSES.length — the `{0,3}`
//              expectation's 3, asserted against its mechanism and not as a
//              literal somebody could keep green by hand.
//   MARKED     the rows carry unitsSource='mock' and a NULL requestId
//              (rulings 66, 72(a)).
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const usageWrites: Record<string, unknown>[] = [];
const aiCallWrites: Record<string, unknown>[] = [];

vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: {
      create: (a: { data: Record<string, unknown> }) => {
        usageWrites.push(a.data);
        return Promise.resolve(a.data);
      },
    },
    aiCall: {
      create: (a: { data: Record<string, unknown> }) => {
        aiCallWrites.push(a.data);
        return Promise.resolve(a.data);
      },
    },
    transcribeVisit: { update: vi.fn() },
  };
  return { __esModule: true, default: client, prisma: client };
});
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { modelClient, MOCK_TRANSCRIPT_UTTERANCES } from '@meddoc/ai';
import {
  ANCHOR_BLOCK_RE,
  ENSEMBLE_LENSES,
  anchorSubSpans,
  runAnchorVerify,
  transcriptForMatching,
} from '../04b-anchor-verify';

const IDS = { visitId: 'v_b4_anchored', practiceId: 'p_b4', userId: 'u_b4' };

/** The role-labeled transcript L3 builds from the mock utterances —
 *  `formatRoleLabeledLine`'s `[Role #n, m:ss]: ` shape, which
 *  `transcriptForMatching` strips. Derived from the same constants the
 *  fixture's anchors are, so the two cannot disagree. */
const ROLE_LABELED = [
  `[Doctor #0, 0:00]: ${MOCK_TRANSCRIPT_UTTERANCES.doctor}`,
  `[Patient #1, 0:02]: ${MOCK_TRANSCRIPT_UTTERANCES.patient}`,
].join('\n');

/** `logApiUsage` is fire-and-forget via setImmediate — drain before asserting. */
const drain = () => new Promise((r) => setImmediate(r));

/** The draft exactly as L4 receives it: through the real mock seam, so this
 *  gate reads what production reads rather than a copy of the fixture. */
async function draft(): Promise<string> {
  const { text } = await modelClient.completeText({
    ...IDS,
    purpose: 'tm_soap_draft',
    provider: 'anthropic',
    model: 'claude-sonnet-4-6',
    system: 'system',
    user: 'user',
    maxTokens: 512,
    temperature: 0,
  });
  return text ?? '';
}

/** Only the entailment stage's rows — `draft()` meters a `tm_soap_draft` of
 *  its own, and counting that as an ensemble pass would be the exact
 *  over-count this gate exists to rule out. */
const entailmentRows = () =>
  usageWrites.filter((r) => r.operation === 'tm_anchor_entailment');

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  usageWrites.length = 0;
  aiCallWrites.length = 0;
  process.env.MOCK_AI_CALLS = 'true';
  // `anthropicCompleteText` builds its client BEFORE the mock branch, so a key
  // must exist even though no request is made. A DUMMY, exactly as the QA
  // stack's posture check requires — never a real one.
  process.env.ANTHROPIC_API_KEY = 'mock-key-test';
  process.env.TRANSCRIBE_MD_EVIDENCE_ANCHORS = 'true';
  delete process.env.MOCK_SOAP_ANCHORS;
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe('B4 closing gate — the anchored draft fixture', () => {
  it('OFF — the default fixture carries no anchor, verifies no claim, and meters nothing', async () => {
    const text = await draft();
    expect(text).not.toMatch(ANCHOR_BLOCK_RE);

    const result = await runAnchorVerify({ ...IDS, anchoredDraft: text, roleLabeledTranscript: ROLE_LABELED });
    await drain();

    // This is the state B4's closing step recorded and could not move: a
    // permitted zero that proves nothing. Pinned so the fix cannot be
    // mistaken for something that was always true.
    expect(result.stats.entailmentChecked).toBe(0);
    expect(entailmentRows()).toHaveLength(0);
  });

  it('DERIVED — every anchor span is a literal substring of the normalized transcript', async () => {
    process.env.MOCK_SOAP_ANCHORS = 'true';
    const text = await draft();

    const asrNorm = transcriptForMatching(ROLE_LABELED);
    const spans = [...text.matchAll(ANCHOR_BLOCK_RE)].flatMap((m) => anchorSubSpans(m[1]));

    // Non-vacuity first: a zero-span fixture would satisfy a forEach over
    // nothing, which is the emptiness test AGENTS.md keeps finding.
    expect(spans.length).toBeGreaterThan(0);
    for (const span of spans) {
      const nsub = span.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
      expect(asrNorm).toContain(nsub);
    }
  });

  it('CONTROL — a span the transcript does not contain IS demoted, so the check above discriminates', async () => {
    const fabricated =
      '## Assessment\n[MOCK] Headache. ⟦A:"the patient denies any headache whatsoever"⟧';
    const result = await runAnchorVerify({
      ...IDS,
      anchoredDraft: fabricated,
      roleLabeledTranscript: ROLE_LABELED,
    });
    await drain();

    expect(result.stats.entailmentChecked).toBe(0);
    expect(result.suggestions.map((s) => s.reason)).toContain('anchor_not_in_transcript');
    // And a demoted claim never reaches the ensemble, which is precisely how
    // this stage returns to a legal zero without anything going red.
    expect(entailmentRows()).toHaveLength(0);
  });

  it('CLAIMS + CLEAN — the anchored draft produces claims that survive, and nothing demotes', async () => {
    process.env.MOCK_SOAP_ANCHORS = 'true';
    const text = await draft();

    const result = await runAnchorVerify({ ...IDS, anchoredDraft: text, roleLabeledTranscript: ROLE_LABELED });
    await drain();

    // Three anchored clinical lines — Subjective, Assessment, Plan. The
    // Objective section is `[not documented]`, which is exempt: the mock
    // transcript contains no exam, so an anchored draft cannot assert one.
    expect(result.stats.entailmentChecked).toBe(3);
    // ⚠️ NOT the same 3 as the ensemble's — see the next test. This one is the
    // claim count; that one is the lens count. They are unrelated quantities
    // that happen to coincide, and asserting both separately is what keeps a
    // future edit to either from hiding in the other.
    expect(result.stats.anchored).toBe(3);
    expect(result.suggestions).toHaveLength(0);
    expect(result.body).toContain('Headache');
    expect(result.body).not.toMatch(ANCHOR_BLOCK_RE);
  });

  it('ENSEMBLE + MARKED — one metered call per lens, each marked mock with a null request id', async () => {
    process.env.MOCK_SOAP_ANCHORS = 'true';
    const text = await draft();

    await runAnchorVerify({ ...IDS, anchoredDraft: text, roleLabeledTranscript: ROLE_LABELED });
    await drain();

    const rows = entailmentRows();
    // The `{0,3}` expectation in `pipeline-stages.ts`, asserted against its
    // MECHANISM. A literal 3 here would survive somebody adding a fourth lens
    // while the meter under-counted — the gate would stay green and the
    // production invariant would be wrong.
    expect(rows).toHaveLength(ENSEMBLE_LENSES.length);
    for (const row of rows) {
      expect(row.unitsSource).toBe('mock');
      expect(row.requestId).toBeNull();
    }
    // Ruling 66 — `ai_calls` stays real-vendor-only.
    expect(aiCallWrites).toHaveLength(0);
  });
});
