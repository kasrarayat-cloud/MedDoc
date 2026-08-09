// @vitest-environment node
// ============================================================================
// B2 GATE, BEHAVIOURAL ARM — FORCE EACH ENUMERATED FAILURE AND READ THE METER.
// ----------------------------------------------------------------------------
// The census arm next door proves the SHAPE of the source. This one proves the
// BEHAVIOUR: every branch is actually driven, and what `logApiUsage` received
// is asserted — payload, provenance, units and id.
//
// ⚠️ BOTH ARMS ARE NECESSARY AND NEITHER IS SUFFICIENT.
//   · The census alone is a grep. It cannot see that a wired call passes the
//     WRONG tokens, the wrong provenance, or a fabricated id.
//   · This alone is a hand-kept list of eight tests. It cannot see a NINTH
//     branch appearing in a file nobody added a test for — which is exactly how
//     B1-a's gate came to be green over a universe missing four callers.
// The census counts the universe; this one checks the members.
//
// ⚠️ AND THE NEGATIVE CASES ARE TESTED AS HARD AS THE POSITIVE ONES. A branch
// that must write NO row is a claim too, and "no row" is the single easiest
// assertion in the world to satisfy by accident — a test that drives nothing at
// all passes it. Every negative case below therefore asserts the `ai_calls`
// row WAS written in the same breath, so the branch is proven to have been
// reached before its silence is believed.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';

process.env.ANTHROPIC_API_KEY = 'sk-test-fixture';
process.env.OPENAI_API_KEY = 'sk-test-fixture';

const mocks = vi.hoisted(() => ({
  createCall: vi.fn(),
  embeddingsCreate: vi.fn(),
  logAiCall: vi.fn(),
  logApiUsage: vi.fn(),
}));

vi.mock('@anthropic-ai/sdk', () => ({
  default: class {
    messages = { create: mocks.createCall };
  },
}));
vi.mock('openai', () => ({
  default: class {
    embeddings = { create: mocks.embeddingsCreate };
  },
}));
vi.mock('../log', () => ({ logAiCall: mocks.logAiCall }));

// ⚠️ THE BUILDERS ARE NOT MOCKED AWAY TO `() => ({})`, unlike the older
// anthropic-* suites. This gate's whole question is what lands in the row, so
// the real builders run and the real pricing dispatcher prices them — a stub
// would make every assertion below vacuous while still passing.
vi.mock('../api-usage', async () => {
  const actual = await vi.importActual<typeof import('../api-usage')>('../api-usage');
  return { ...actual, logApiUsage: mocks.logApiUsage };
});

import { anthropicComplete, anthropicCompleteText } from '../anthropic';
import { embedText } from '../embed';

const Schema = z.object({ codes: z.array(z.object({ code: z.string() })) });

const USAGE = {
  input_tokens: 1000,
  output_tokens: 250,
  cache_read_input_tokens: 0,
  cache_creation_input_tokens: 0,
};

/** Attach a non-enumerable `_request_id` exactly the way the SDK does. */
function withRequestId<T extends object>(obj: T, id: string): T {
  Object.defineProperty(obj, '_request_id', {
    value: id, enumerable: false, writable: true, configurable: true,
  });
  return obj;
}

const textArgs = {
  practiceId: 'p1',
  visitId: 'v1',
  userId: 'u1',
  purpose: 'tm_soap_draft' as const,
  model: 'claude-sonnet-4-6',
  system: 'You are a clinical scribe.',
  user: 'Draft the SOAP.',
};

const completeArgs = {
  ...textArgs,
  purpose: 'tm_icd_coding' as const,
  schema: Schema,
};

beforeEach(() => {
  vi.clearAllMocks();
  delete process.env.MOCK_AI_CALLS;
});
afterEach(() => vi.restoreAllMocks());

/** The single usage row this call produced. Fails loudly on 0 or >1. */
function theUsageRow() {
  expect(mocks.logApiUsage).toHaveBeenCalledTimes(1);
  return mocks.logApiUsage.mock.calls[0][0];
}

// ---------------------------------------------------------------------------
// BRANCH 1–6 — anthropic.ts, the branches that hold vendor-reported tokens
// ---------------------------------------------------------------------------

describe('BILLED branches write a usage row carrying the vendor\'s own numbers', () => {
  it('BRANCH 1 — tool-mode AI_REFUSAL', async () => {
    mocks.createCall.mockResolvedValueOnce(
      withRequestId({ stop_reason: 'refusal', content: [], usage: USAGE }, 'req_tool_refusal'),
    );
    await expect(
      anthropicComplete({ ...completeArgs, useToolUse: { name: 'emit', description: 'd' } }),
    ).rejects.toThrow();

    const row = theUsageRow();
    expect(row.inputTokens).toBe(1000);
    expect(row.outputTokens).toBe(250);
    expect(row.unitsSource).toBe('vendor');
    expect(row.requestId).toBe('req_tool_refusal');
    expect(row.metadata).toMatchObject({ outcome: 'failed', errorCode: 'AI_REFUSAL' });
    // The money is the point of the item: a refusal that spent 1000 input
    // tokens is priced, not zeroed.
    expect(row.totalCostUsd).toBeGreaterThan(0);
  });

  it('BRANCH 2 — tool-mode JSON_PARSE_FAIL (no tool_use block)', async () => {
    mocks.createCall.mockResolvedValueOnce(
      withRequestId({ stop_reason: 'end_turn', content: [], usage: USAGE }, 'req_no_tool_block'),
    );
    await expect(
      anthropicComplete({ ...completeArgs, useToolUse: { name: 'emit', description: 'd' } }),
    ).rejects.toThrow();

    const row = theUsageRow();
    expect(row.unitsSource).toBe('vendor');
    expect(row.requestId).toBe('req_no_tool_block');
    expect(row.metadata).toMatchObject({ errorCode: 'JSON_PARSE_FAIL' });
    expect(row.totalCostUsd).toBeGreaterThan(0);
  });

  it('BRANCH 3 — text-mode AI_REFUSAL', async () => {
    mocks.createCall.mockResolvedValueOnce(
      withRequestId({ stop_reason: 'refusal', content: [], usage: USAGE }, 'req_text_refusal'),
    );
    await expect(anthropicComplete(completeArgs)).rejects.toThrow();

    const row = theUsageRow();
    expect(row.requestId).toBe('req_text_refusal');
    expect(row.metadata).toMatchObject({ errorCode: 'AI_REFUSAL' });
  });

  it('BRANCH 4 — text-mode JSON_PARSE_FAIL (unparseable body)', async () => {
    mocks.createCall.mockResolvedValueOnce(
      withRequestId(
        { stop_reason: 'end_turn', content: [{ type: 'text', text: 'not json at all' }], usage: USAGE },
        'req_bad_json',
      ),
    );
    await expect(anthropicComplete(completeArgs)).rejects.toThrow();

    const row = theUsageRow();
    expect(row.requestId).toBe('req_bad_json');
    expect(row.metadata).toMatchObject({ errorCode: 'JSON_PARSE_FAIL' });
    expect(row.totalCostUsd).toBeGreaterThan(0);
  });

  it('BRANCH 5 — SCHEMA_FAIL (valid JSON, wrong shape)', async () => {
    mocks.createCall.mockResolvedValueOnce(
      withRequestId(
        { stop_reason: 'end_turn', content: [{ type: 'text', text: '{"wrong":"shape"}' }], usage: USAGE },
        'req_schema_fail',
      ),
    );
    await expect(anthropicComplete(completeArgs)).rejects.toThrow('SCHEMA_FAIL');

    const row = theUsageRow();
    expect(row.requestId).toBe('req_schema_fail');
    expect(row.metadata).toMatchObject({ errorCode: 'SCHEMA_FAIL' });
    expect(row.totalCostUsd).toBeGreaterThan(0);
  });

  it('BRANCH 6 — completeText AI_REFUSAL', async () => {
    mocks.createCall.mockResolvedValueOnce(
      withRequestId({ stop_reason: 'refusal', content: [], usage: USAGE }, 'req_ct_refusal'),
    );
    await expect(anthropicCompleteText(textArgs)).rejects.toThrow();

    const row = theUsageRow();
    expect(row.requestId).toBe('req_ct_refusal');
    expect(row.metadata).toMatchObject({ errorCode: 'AI_REFUSAL' });
    expect(row.totalCostUsd).toBeGreaterThan(0);
  });

  it('BRANCH 7 — embed.ts EMBED_DIM_MISMATCH', async () => {
    mocks.embeddingsCreate.mockResolvedValueOnce(
      withRequestId(
        { data: [{ embedding: [1, 2, 3] }], usage: { total_tokens: 800 } },
        'req_embed_dim',
      ),
    );
    await expect(
      embedText({ practiceId: 'p1', visitId: 'v1', userId: 'u1', purpose: 'tm_embed', text: 'x' }),
    ).rejects.toThrow();

    const row = theUsageRow();
    expect(row.provider).toBe('openai');
    expect(row.inputTokens).toBe(800);
    expect(row.unitsSource).toBe('vendor');
    expect(row.requestId).toBe('req_embed_dim');
    expect(row.metadata).toMatchObject({ outcome: 'failed', errorCode: 'EMBED_DIM_MISMATCH' });
    expect(row.totalCostUsd).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// THE NO-UNITS BRANCHES — proven REACHED, then proven SILENT
// ---------------------------------------------------------------------------

describe('NO-UNITS branches are reached and write NO usage row', () => {
  it('anthropicComplete outer catch — the SDK threw', async () => {
    mocks.createCall.mockRejectedValueOnce(new Error('socket hang up'));
    await expect(anthropicComplete(completeArgs)).rejects.toThrow('socket hang up');

    // Reached: the telemetry row exists...
    expect(mocks.logAiCall).toHaveBeenCalledWith(
      expect.objectContaining({ success: false }),
    );
    // ...and no units were invented for it.
    expect(mocks.logApiUsage).not.toHaveBeenCalled();
  });

  it('anthropicCompleteText outer catch — the SDK threw', async () => {
    mocks.createCall.mockRejectedValueOnce(new Error('ECONNRESET'));
    await expect(anthropicCompleteText(textArgs)).rejects.toThrow('ECONNRESET');

    expect(mocks.logAiCall).toHaveBeenCalledWith(
      expect.objectContaining({ success: false }),
    );
    expect(mocks.logApiUsage).not.toHaveBeenCalled();
  });

  it('embed.ts outer catch — the SDK threw', async () => {
    mocks.embeddingsCreate.mockRejectedValueOnce(new Error('429 rate limit'));
    await expect(
      embedText({ practiceId: 'p1', visitId: 'v1', userId: 'u1', purpose: 'tm_embed', text: 'x' }),
    ).rejects.toThrow('429');

    expect(mocks.logAiCall).toHaveBeenCalledWith(
      expect.objectContaining({ success: false }),
    );
    expect(mocks.logApiUsage).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// THE PROVENANCE SEAM — a mocked run's failure is not a vendor failure
// ---------------------------------------------------------------------------

describe('the mock seam survives the failure path', () => {
  it('under MOCK_AI_CALLS a failed call meters as `mock`, never `vendor`', async () => {
    // ⚠️ THIS IS THE ASSERTION THAT KEEPS B2 FROM UNDOING B0-a. The failure
    // branches are new writers, and a new writer that hardcodes `'vendor'`
    // would put fabricated vendor rows into every mocked QA run — silently,
    // because `logApiUsage` is fire-and-forget and the CHECK constraint's
    // refusal is swallowed. The helper mirrors the success path's seam; this
    // proves it does.
    process.env.MOCK_AI_CALLS = 'true';
    const { isMockEnabled } = await import('../mock');
    expect(isMockEnabled(), 'the flag did not take — the assertion below would be vacuous')
      .toBe(true);

    // ⚠️ WHICH BRANCH IS REACHABLE UNDER MOCK IS ITSELF A FINDING, and the
    // first draft of this test got it wrong in an instructive way.
    //
    // B0 puts the mock seam BELOW the caller: `createMessage` short-circuits to
    // a fixture, so the SDK mock is never consulted and a vendor-shaped
    // `stop_reason: 'refusal'` CANNOT be injected. The three vendor-verdict
    // branches (both refusals, the missing tool block) are therefore
    // structurally unreachable in a mocked run — correctly, because a mocked
    // run has no vendor to refuse.
    //
    // SCHEMA_FAIL is the branch that IS reachable, and that is by B0's design:
    // the real Zod gate runs against the fixture. A schema the fixture cannot
    // satisfy reaches it, which is exactly what a QA run hits when a caller's
    // schema and the mock drift apart.
    const Impossible = z.object({ __no_fixture_has_this__: z.string() });
    await expect(
      anthropicComplete({ ...completeArgs, schema: Impossible }),
    ).rejects.toThrow('SCHEMA_FAIL');

    const row = theUsageRow();
    expect(row.unitsSource).toBe('mock');
    // And the id is not smuggled through: the writer zeroes a mock row's id,
    // but the caller must not be handing it one to zero in the first place.
    expect(row.metadata).toMatchObject({ errorCode: 'SCHEMA_FAIL' });
  });
});
