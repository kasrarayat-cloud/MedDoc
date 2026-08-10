// @vitest-environment node
// ============================================================================
// B4 STEP 2 GATE — `tm_anchor_entailment` can be COUNTED, and the fixture that
// makes that possible answers the prompt it was actually given.
// ----------------------------------------------------------------------------
// B4's gate is: "one full QA pipeline run produces one event per stage,
// counted against the enumerated stage list." Step 1 made that satisfiable for
// Deepgram and embed by moving their mock boundaries below `logApiUsage`.
//
// This stage failed the same way ONE LAYER HIGHER. `entailmentStage` returned
// all-entailed under `MOCK_AI_CALLS` before `entailmentPass` — so before
// `modelClient`, so before the meter — and a mocked QA run emitted ZERO usage
// events for it. `modelClient.completeText` already carries the note that B0
// deleted exactly this shape from the stage level; 04b kept its own copy.
//
//     ZERO USAGE EVENTS LOOKS EXACTLY LIKE A WORKING METER THAT FOUND
//     NOTHING TO RECORD.
//
// ⚠️ THE REPO ALREADY KNEW, IN WRITING — the fixture's own comment said
// "UNREACHABLE in practice: the verifier short-circuits ... before any model
// call". Step 1 found its defect carried as a written exemption in a gate;
// this one was carried as a written exemption in a fixture. A comment that
// explains why a thing cannot be measured is a finding, not a caveat.
//
// ── WHAT THIS GATE ASSERTS ────────────────────────────────────────────────
//   EMITS        a mocked entailment pass writes a usage event
//   MARKED       it carries unitsSource='mock' and a NULL requestId
//   QUIET        `ai_calls` gets nothing under mock (ruling 66)
//   ANSWERS      the fixture returns one entailed verdict PER CLAIM the
//                prompt names — a constant fixture cannot (ruling 69)
//   ECHOES       it echoes the prompt's OWN claim numbers, and does not
//                assume they are 0..n-1
//   ANCHORED     ⚠️ the word "CLAIM" inside a claim's text does NOT inflate
//                the count — the negative control for the substring trap
//   CLOSED       no user content → empty verdicts → every claim demoted
//   ONE          `mockCompleteText` and the production path agree, because
//                there is exactly one selection function
// ============================================================================

import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

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
  };
  return { __esModule: true, default: client, prisma: client };
});

/** logApiUsage defers via setImmediate — drain it before asserting. */
const drain = () => new Promise((r) => setImmediate(r));

const CTX = { practiceId: 'p_gate', userId: 'u_gate', visitId: 'v_gate' };

/** The real prompt shape, from `04b-anchor-verify.ts`'s claim block. */
const claimBlock = (i: number, text: string) =>
  [`CLAIM ${i}: ${text}`, 'CITED SPAN(S): the span', 'CONTEXT: the line'].join('\n');

const promptOf = (...blocks: string[]) => blocks.join('\n\n');

const verdictsOf = (text: string): { i: number; entailed: boolean }[] =>
  JSON.parse(text).verdicts;

describe('B4 step 2 — tm_anchor_entailment meters, and its fixture answers the prompt', () => {
  beforeEach(() => {
    usageWrites.length = 0;
    aiCallWrites.length = 0;
    vi.resetModules();
    process.env.MOCK_AI_CALLS = 'true';
    // Two-condition doctrine (B0): the flag stops the call, and a dummy
    // credential is what survives a code path that forgets the flag.
    process.env.ANTHROPIC_API_KEY = 'test-dummy-never-valid';
  });
  afterEach(async () => {
    await drain();
    delete process.env.MOCK_AI_CALLS;
    delete process.env.ANTHROPIC_API_KEY;
  });

  // ── THE METER ────────────────────────────────────────────────────────────

  it('EMITS + MARKED + QUIET — a mocked entailment pass writes ONE mock usage row', async () => {
    const { modelClient } = await import('../model-client');
    await modelClient.completeText({
      ...CTX,
      purpose: 'tm_anchor_entailment',
      provider: 'anthropic',
      model: 'claude-sonnet-4-5',
      system: 'ENTAILMENT',
      user: promptOf(claimBlock(0, 'the patient reports headache')),
      maxTokens: 2048,
      temperature: 0,
    });
    await drain();

    expect(usageWrites).toHaveLength(1);
    const row = usageWrites[0];
    expect(row.operation).toBe('tm_anchor_entailment');
    expect(row.provider).toBe('anthropic');
    expect(row.unitsSource).toBe('mock');
    // B1-b / ruling 72a — only vendor rows may carry an id. A minted one here
    // would violate `api_usage_events_request_id_requires_vendor` and, because
    // `logApiUsage` is fire-and-forget, be dropped in SILENCE — putting the
    // stage back to zero events with every line of code looking correct.
    expect(row.requestId ?? null).toBeNull();
    // Ruling 66 — `ai_calls` is a real-vendor-calls-only table.
    expect(aiCallWrites).toHaveLength(0);
  });

  it('EMITS — three passes meter three times, which is what makes the stage COUNTABLE', async () => {
    const { modelClient } = await import('../model-client');
    const user = promptOf(claimBlock(0, 'headache'), claimBlock(1, 'no fever'));
    // The k=3 ensemble: same prompt, three lenses appended to the SYSTEM text.
    for (const lens of ['', 'ELABORATION HUNTER', 'CLINICAL SKEPTIC']) {
      await modelClient.completeText({
        ...CTX,
        purpose: 'tm_anchor_entailment',
        provider: 'anthropic',
        model: 'claude-sonnet-4-5',
        system: `ENTAILMENT${lens}`,
        user,
        maxTokens: 2048,
        temperature: 0,
      });
    }
    await drain();

    // Production's own invariant, measured 2026-08-10: of the 73 visits that
    // carry this stage, ALL 73 carry exactly 3 calls — never 1, 2 or 6. The
    // count is per L4b INVOCATION, not per visit, and L4b runs at most once.
    expect(usageWrites).toHaveLength(3);
    expect(usageWrites.every((r) => r.unitsSource === 'mock')).toBe(true);
  });

  // ── THE FIXTURE ──────────────────────────────────────────────────────────

  it('ANSWERS — one entailed verdict per claim the prompt names', async () => {
    const { mockCompleteText } = await import('../mock');
    const user = promptOf(
      claimBlock(0, 'headache'),
      claimBlock(1, 'no fever'),
      claimBlock(2, 'plan: hydration')
    );

    const verdicts = verdictsOf(
      mockCompleteText({ purpose: 'tm_anchor_entailment', user }).text
    );

    expect(verdicts).toHaveLength(3);
    expect(verdicts.every((v) => v.entailed === true)).toBe(true);
    // ⚠️ This is what a CONSTANT fixture cannot do, and why ruling 69 calls a
    // constant mock a regression. `entailmentPass` counts a missing verdict as
    // NOT entailed, so a fixed 1-verdict answer would silently demote claims
    // 1 and 2 — the mock path would then disagree with the real path about
    // the pipeline's output, which is the one thing a mock must never do.
    const one = verdictsOf(
      mockCompleteText({
        purpose: 'tm_anchor_entailment',
        user: promptOf(claimBlock(0, 'headache')),
      }).text
    );
    expect(one).toHaveLength(1);
  });

  it('ECHOES — the prompt\'s OWN claim numbers, never an assumed 0..n-1', async () => {
    const { mockCompleteText } = await import('../mock');
    // A prompt whose numbering does not start at 0 and is not contiguous.
    // `entailmentPass` matches verdicts by `x.i === k`, so inventing 0,1,2
    // here would leave every real claim without a verdict → all demoted.
    const user = promptOf(claimBlock(4, 'alpha'), claimBlock(7, 'beta'));

    const verdicts = verdictsOf(
      mockCompleteText({ purpose: 'tm_anchor_entailment', user }).text
    );

    expect(verdicts.map((v) => v.i)).toEqual([4, 7]);
  });

  it('ANCHORED — the word CLAIM inside a claim\'s TEXT does not inflate the count', async () => {
    const { mockCompleteText } = await import('../mock');
    // ⚠️ THE NEGATIVE CONTROL FOR THE SUBSTRING TRAP (AGENTS.md, four
    // sightings). A clinician's words are exactly where the token you are
    // grepping for is guaranteed to appear. `CLAIM 9:` occurs here mid-line,
    // inside claim 0's text and inside a CONTEXT line — a `.includes('CLAIM')`
    // or an unanchored regex reports 3 claims and the fixture answers a
    // question nobody asked.
    const user = [
      'CLAIM 0: patient disputes the insurer\'s CLAIM 9: denial of coverage',
      'CITED SPAN(S): the span',
      'CONTEXT: she said they sent a letter saying CLAIM 9: denied',
    ].join('\n');

    const verdicts = verdictsOf(
      mockCompleteText({ purpose: 'tm_anchor_entailment', user }).text
    );

    expect(verdicts.map((v) => v.i)).toEqual([0]);
  });

  it('CLOSED — no user content yields empty verdicts, which demotes everything', async () => {
    const { mockCompleteText } = await import('../mock');
    // There is no production path that omits `user`; if one ever appears, the
    // safe answer for a VERIFIER is to entail nothing.
    expect(verdictsOf(mockCompleteText({ purpose: 'tm_anchor_entailment' }).text))
      .toEqual([]);
  });

  it('ONE — the test-facing helper and the production path select the SAME fixture', async () => {
    const { mockCompleteText, buildMockMessage } = await import('../mock');
    const user = promptOf(claimBlock(0, 'headache'), claimBlock(1, 'no fever'));

    const viaHelper = mockCompleteText({ purpose: 'tm_anchor_entailment', user }).text;
    const viaProduction = buildMockMessage({
      purpose: 'tm_anchor_entailment',
      kind: 'completeText',
      user,
      model: 'claude-sonnet-4-5',
    });
    const text = (viaProduction.content[0] as { text: string }).text;

    // ⚠️ B0's recorded lesson, kept live: a tested helper that production has
    // stopped calling, beside an untested one production DOES call, is worse
    // than no test — the suite stays green while the live path drifts. This
    // arm fails the moment the two stop sharing one selection function.
    expect(text).toBe(viaHelper);
    expect(verdictsOf(text).map((v) => v.i)).toEqual([0, 1]);
  });
});
