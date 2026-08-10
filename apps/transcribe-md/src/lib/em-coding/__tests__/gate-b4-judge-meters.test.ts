// @vitest-environment node
// ============================================================================
// B4 STEP 3 GATE — the `judge` stage can be COUNTED, without anyone inventing
// a judgement to make the meter tick.
// ----------------------------------------------------------------------------
// B4's gate is: "one full QA pipeline run produces one event per stage,
// counted against the enumerated stage list." Step 1 made that satisfiable for
// Deepgram and embed (ruling 81); step 2 for `tm_anchor_entailment` (ruling
// 82). `judge` was the last stage that could not be counted, and it failed
// differently from both.
//
// `callClaudeMdm` returned `null` under `MOCK_AI_CALLS` before any meter ran,
// so a mocked QA run emitted ZERO `api_usage_events` rows for the stage.
//
//     ZERO USAGE EVENTS LOOKS EXACTLY LIKE A WORKING METER THAT FOUND
//     NOTHING TO RECORD.
//
// ⚠️ AND THE OBVIOUS FIX WAS THE FORBIDDEN ONE. Every other mocked Anthropic
// path meters because `anthropic.ts` hands back a fixture Message and the real
// pipeline runs over it. Doing that here means producing a parseable
// `MdmJudgement`, which would make `judgeMdm` report `llmJudged: true` for a
// judgement no LLM produced — the provenance lie ruling 82 named when it
// carried this stage forward rather than settling it.
//
// So the two claims are separated: THE CALL IS METERED, THE JUDGEMENT IS NOT
// FABRICATED. `null` still comes back, the deterministic fallback still runs,
// and `llmJudged: false` is still true.
//
// ── WHAT THIS GATE ASSERTS ────────────────────────────────────────────────
//   EMITS       a mocked judgeMdm writes exactly ONE usage event
//   LABELLED    operation='judge', provider='anthropic', the real model name
//   MARKED      unitsSource='mock', NULL requestId, ZERO money
//   QUIET       `ai_calls` gets nothing under mock (ruling 66)
//   HONEST      the judgement is the DETERMINISTIC fallback — llmJudged=false
//   NO-FIXTURE  no parseable MdmJudgement is manufactured anywhere
//   ONE-SOURCE  the fixture token counts are the SHARED constant, so this
//               meter and `buildMockMessage` cannot drift apart
//   CACHED      ⚠️ a cache HIT meters NOTHING — ruling 69's "a real cache hit
//               = no vendor call = no cost = no usage event", pinned so a
//               later "the gate wants one row per visit" cannot break it
//   COUNTS      two calls produce two rows — the meter counts CALLS, and
//               `judge` is 1-to-many per visit (RELAY, measured in prod)
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

/** The Redis judgement cache, under this gate's control. Default: cold. */
let cacheReady = false;
const cacheStore = new Map<string, string>();

vi.mock('@/lib/redis', () => ({
  isRedisReady: () => cacheReady,
  getRedis: () => ({
    get: (k: string) => Promise.resolve(cacheStore.get(k) ?? null),
    set: (k: string, v: string) => {
      cacheStore.set(k, v);
      return Promise.resolve('OK');
    },
  }),
}));

/** logApiUsage defers via setImmediate — drain it before asserting. */
const drain = () => new Promise((r) => setImmediate(r));

const SOAP = [
  'S: 54yo M with two days of productive cough and subjective fever.',
  'O: Temp 38.1, chest with scattered rhonchi.',
  'A: Acute bronchitis.',
  'P: Supportive care, azithromycin, return precautions.',
].join('\n');

const CTX = { practiceId: 'p_gate', userId: 'u_gate', visitId: 'v_gate' };

describe('B4 step 3 — the judge stage meters under mock, and invents nothing', () => {
  beforeEach(() => {
    usageWrites.length = 0;
    aiCallWrites.length = 0;
    cacheReady = false;
    cacheStore.clear();
    vi.resetModules();
    process.env.MOCK_AI_CALLS = 'true';
    // Two-condition doctrine (B0): the flag stops the call, and a dummy
    // credential is what survives a code path that forgets the flag. If the
    // guard under test ever regressed, this key is what stands between the
    // suite and a real vendor.
    process.env.ANTHROPIC_API_KEY = 'test-dummy-never-valid';
  });
  afterEach(async () => {
    await drain();
    delete process.env.MOCK_AI_CALLS;
    delete process.env.ANTHROPIC_API_KEY;
  });

  // ── THE METER ────────────────────────────────────────────────────────────

  it('EMITS + LABELLED + MARKED + QUIET — one mocked judge call, one mock row', async () => {
    const { judgeMdm } = await import('../llm-mdm');
    await judgeMdm({ ...CTX, soap: SOAP });
    await drain();

    expect(
      usageWrites,
      'the judge stage emitted no usage event — B4 cannot count it',
    ).toHaveLength(1);
    const row = usageWrites[0];

    expect(row.operation).toBe('judge');
    expect(row.provider).toBe('anthropic');
    // The model actually named by the call site, not a literal wearing an
    // observation's clothes — ruling 81(a), applied here rather than re-learnt.
    expect(row.modelName).toBe('claude-sonnet-4-6');

    expect(row.unitsSource).toBe('mock');
    // B1-b / ruling 72a — only vendor rows may carry an id. A minted one would
    // violate `api_usage_events_request_id_requires_vendor` and, because
    // `logApiUsage` is fire-and-forget, be dropped in SILENCE — putting the
    // stage back to zero events with every line of code looking correct.
    expect(row.requestId ?? null).toBeNull();
    // B0 — no vendor was called, so no money was spent, and zero is the TRUE
    // cost. A priced fixture would put a number in a column that means "money
    // left the building".
    expect(row.unitCostUsd).toBe(0);
    expect(row.totalCostUsd).toBe(0);

    // Ruling 66 — `ai_calls` is a real-vendor-calls-only table.
    expect(aiCallWrites).toHaveLength(0);
  });

  it('ONE-SOURCE — the fixture tokens ARE the shared constant, so the two mock meters cannot drift', async () => {
    const { judgeMdm } = await import('../llm-mdm');
    const { MOCK_FIXTURE_USAGE } = await import('@meddoc/ai');
    await judgeMdm({ ...CTX, soap: SOAP });
    await drain();

    const row = usageWrites[0];
    expect(row.inputTokens).toBe(MOCK_FIXTURE_USAGE.input_tokens);
    expect(row.outputTokens).toBe(MOCK_FIXTURE_USAGE.output_tokens);

    // ⚠️ THE ANTI-DRIFT ARM. Two mock meters now exist — this one and
    // `buildMockMessage`, which every OTHER mocked Anthropic path goes
    // through. Asserting each against its own literal would let them diverge
    // while both stayed green, so what gets asserted is that they read the
    // SAME constant.
    //
    // `buildMockMessage` is deliberately NOT exported from `@meddoc/ai`'s
    // index — it is an internal seam for `anthropic.ts`, and widening the
    // package's surface just to let a test call it would be the tail wagging
    // the dog. So the shared-source property is asserted structurally.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const mockSrc = readFileSync(
      join(process.cwd(), '../../packages/ai/src/mock.ts'),
      'utf8',
    );
    // Non-vacuity: prove the read landed before believing anything about it.
    expect(mockSrc).toContain('export function buildMockMessage');
    expect(
      mockSrc,
      'buildMockMessage stopped reading MOCK_FIXTURE_USAGE — the two mock ' +
        'meters can now drift apart',
    ).toMatch(/usage:\s*\{\s*\.\.\.MOCK_FIXTURE_USAGE\s*\}/);
  });

  // ── AND IT STILL DOES NOT LIE ────────────────────────────────────────────

  it('HONEST — the judgement is the deterministic fallback, and says so', async () => {
    const { judgeMdm } = await import('../llm-mdm');
    const res = await judgeMdm({ ...CTX, soap: SOAP });

    // The whole reason this stage was carried to its own step. Metering the
    // call must not promote the fallback into "the LLM judged this".
    expect(
      res.llmJudged,
      'llmJudged is true under mock — a judgement was fabricated',
    ).toBe(false);
    expect(res.cacheHit).toBe(false);
    // The fallback is real and content-sensitive (ruling 69), so it still
    // produces a usable tier rather than a sentinel.
    expect(res.judgement.tier).toBeTruthy();
    expect(res.judgement.elements).toBeTruthy();
  });

  it('NO-FIXTURE — the mock path manufactures no parseable MdmJudgement', async () => {
    // ⚠️ ASSERTED ON THE SOURCE, because the property is an ABSENCE and a
    // behavioural test cannot see something that is not there. If a future
    // change adds a `judge` fixture to satisfy a meter, this is what notices.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const mockSrc = readFileSync(
      join(process.cwd(), '../../packages/ai/src/mock.ts'),
      'utf8',
    );

    // Non-vacuity first: prove the file was actually read and is the one we
    // think it is, or every assertion below is trivially true about nothing.
    expect(mockSrc.length).toBeGreaterThan(5000);
    expect(mockSrc).toContain('MOCK_COMPLETE_FIXTURES');

    // The exact key form a fixture would take. Matched as a KEYED ENTRY, not
    // the bare word "judge" — this file's prose says "judge" many times, and a
    // substring match on it is the trap this repo has now hit four times.
    expect(
      mockSrc,
      'a `judge` fixture appeared — a mock that answers the judge is a mock ' +
        'that lies about provenance (ruling 82)',
    ).not.toMatch(/^\s*judge:\s/m);
    expect(mockSrc).not.toMatch(/['"]judge['"]\s*:/);
  });

  // ── THE TWO SHAPES A NAIVE B4 GATE WOULD GET WRONG ───────────────────────

  it('CACHED — a cache HIT meters nothing, and that is correct', async () => {
    const { judgeMdm } = await import('../llm-mdm');

    // Prime the cache with a real judgement, the way a live call would.
    cacheReady = true;
    const { buildCacheKey } = await import('../llm-mdm');
    cacheStore.set(
      buildCacheKey(SOAP),
      JSON.stringify({
        tier: 'moderate',
        elements: {
          problems: { level: 'moderate', summary: 'one acute illness' },
          data: { level: 'moderate', summary: 'no external data' },
          risk: { level: 'moderate', summary: 'prescription drug management' },
        },
        confidence: 0.9,
        rationale: 'cached from a real call',
      }),
    );

    usageWrites.length = 0;
    const res = await judgeMdm({ ...CTX, soap: SOAP });
    await drain();

    expect(res.cacheHit).toBe(true);
    // ⚠️ RULING 69, PINNED. A real cache hit is no vendor call, so no cost, so
    // no usage event. This is stated as an EXPECTATION rather than left
    // implicit because B4's gate text reads "one event per stage per run", and
    // the naive repair for a missing row is to make the cache emit one — which
    // would meter a call that never happened.
    expect(
      usageWrites,
      'a cache hit emitted a usage event — that meters a call nobody made',
    ).toHaveLength(0);
  });

  it('COUNTS — two judge calls produce two rows; the meter counts CALLS, not visits', async () => {
    const { judgeMdm } = await import('../llm-mdm');
    // ⚠️ `judge` is 1-to-many per visit and the tail is long: production shows
    // 58 visits with 1 call, 12 with 2, one with 13 (E/M is re-scored, and
    // `callClaudeMdm` retries once on a parse failure). A B4 gate asserting
    // ONE event per visit would be wrong, and a small sample would not reveal
    // it — so the per-call granularity is asserted here.
    await judgeMdm({ ...CTX, soap: SOAP });
    await judgeMdm({ ...CTX, soap: `${SOAP}\nAddendum: re-scored.` });
    await drain();

    expect(usageWrites).toHaveLength(2);
    expect(usageWrites.every((r) => r.operation === 'judge')).toBe(true);
    expect(usageWrites.every((r) => r.unitsSource === 'mock')).toBe(true);
  });

  // ── NON-VACUITY ──────────────────────────────────────────────────────────

  it('NON-VACUITY — with the flag OFF the mock meter does not fire', async () => {
    // If this gate's rows appeared regardless of the flag, every assertion
    // above would be green about a code path nobody reached.
    //
    // ⚠️ AND THE OBVIOUS WAY TO WRITE THIS ARM WAS A LIVE VENDOR CALL — which
    // is the very defect the item exists to close, reintroduced in its own
    // gate. The first draft left the dummy `ANTHROPIC_API_KEY` in place, so
    // the flag-OFF branch built a real client and issued a real HTTPS request
    // to api.anthropic.com, twice (the retry), against a 30s timeout. It
    // passed in isolation and FAILED INTERMITTENTLY in the full suite, which
    // is how it was caught — a network round-trip wearing a unit test's
    // clothes. Two conditions again: the flag is one, the credential is the
    // other.
    //
    // Removing the key makes `getAnthropicClient()` throw BEFORE any socket is
    // opened, so the flag-OFF path is exercised, deterministically, offline.
    delete process.env.MOCK_AI_CALLS;
    delete process.env.ANTHROPIC_API_KEY;

    const { judgeMdm } = await import('../llm-mdm');
    const res = await judgeMdm({ ...CTX, soap: SOAP }).catch(() => null);
    await drain();

    // No MOCK row — the meter above is attributable to the flag and nothing else.
    expect(usageWrites.filter((r) => r.unitsSource === 'mock')).toHaveLength(0);
    // And the branch really was entered: with no credential the judge cannot
    // produce an LLM judgement, so either it threw or it fell back. What it
    // must NOT have done is return a mocked judgement.
    expect(res === null || res.llmJudged === false).toBe(true);
  });
});
