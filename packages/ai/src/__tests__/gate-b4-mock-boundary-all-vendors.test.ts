// @vitest-environment node
// ============================================================================
// B4 GATE — the mock boundary sits below the meter for EVERY vendor, and the
// Deepgram labels stop lying.
// ----------------------------------------------------------------------------
// B0 proved this for `anthropic.ts` and stated the failure mode it kills:
//
//     ZERO USAGE EVENTS LOOKS EXACTLY LIKE A WORKING METER THAT FOUND
//     NOTHING TO RECORD.
//
// B0 fixed ONE vendor. `deepgram-batch.ts` and `embed.ts` kept their mock
// short-circuits ABOVE `logApiUsage`, so a mocked QA run emitted no usage row
// for the audio stages (L1 / L1b) or for `tm_embed`. That is not a suspicion:
// `gate-mock-suite-stubs-the-db.test.ts` carried it as a WRITTEN EXEMPTION.
//
// It matters because of where each stage can be proven. Every production visit
// is `text_notes`, so the audio path is UNEXERCISED IN PRODUCTION — QA is the
// only place it can be metered at all, and QA was exactly where the meter was
// blind. B4's own gate ("one full QA pipeline run produces one event per
// stage") was unsatisfiable for those stages by construction.
//
// ── WHAT THIS GATE ASSERTS, IN BOTH DIRECTIONS ────────────────────────────
//   EMITS       a mocked Deepgram / embed call writes a usage event
//   MARKED      that event carries unitsSource='mock', never 'vendor'
//   REFUSES     ⚠️ the Deepgram row's requestId is NULL **even though the
//               fixture supplies `metadata.request_id`**
//   LABELLED    operation is the call's PURPOSE and modelName is the model
//               actually requested — neither is a literal any more
//   QUIET       `ai_calls` gets NOTHING under mock (ruling 66)
//   REAL        an UNMOCKED call still writes 'vendor' AND the vendor's real id
//
// The last one is not decoration. A change that made every row 'mock' with a
// null id would satisfy the first five perfectly.
//
// ⚠️ THE `REFUSES` ARM IS THE ONE THAT EARNS THIS FILE. `logApiUsage` is
// fire-and-forget, so a mock row carrying the fixture's id would violate
// `api_usage_events_request_id_requires_vendor` (B1-b, ruling 72a) and be
// SILENTLY DROPPED — leaving the audio stage missing from a QA run while every
// line of code looked correct. The fixture keeps its id on purpose so this arm
// has something to refuse; deleting it from the fixture would make the arm
// vacuous, which is why the fixture and this test name each other.
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

const AUDIO = Buffer.from('not-really-audio');
const CTX = { practiceId: 'p_gate', userId: 'u_gate', visitId: 'v_gate' };

/**
 * A vendor-shaped Deepgram body for the UNMOCKED direction. Deliberately a
 * DIFFERENT id and duration from the fixture's, so an assertion cannot pass by
 * accidentally reading the mock.
 */
const REAL_BODY = {
  metadata: { duration: 12, request_id: 'dg-real-0001' },
  results: {
    channels: [
      { alternatives: [{ transcript: 'real transcript', confidence: 0.9, words: [] }] },
    ],
    utterances: [],
  },
};

describe('B4 — the mock boundary sits BELOW the meter for every vendor', () => {
  beforeEach(() => {
    usageWrites.length = 0;
    aiCallWrites.length = 0;
    vi.resetModules();
    vi.unstubAllGlobals();
    process.env.MOCK_AI_CALLS = 'true';
    // Two-condition doctrine (B0): the FLAG stops the call, and a dummy
    // CREDENTIAL is what survives a code path that forgets the flag.
    process.env.DEEPGRAM_API_KEY = 'test-dummy-never-valid';
    process.env.OPENAI_API_KEY = 'test-dummy-never-valid';
    delete process.env.DEEPGRAM_MODEL;
  });
  afterEach(async () => {
    await drain();
    vi.unstubAllGlobals();
    delete process.env.MOCK_AI_CALLS;
    delete process.env.DEEPGRAM_API_KEY;
    delete process.env.OPENAI_API_KEY;
    delete process.env.DEEPGRAM_MODEL;
  });

  // ── DEEPGRAM ─────────────────────────────────────────────────────────────

  it('EMITS + MARKED + QUIET — a mocked Deepgram call meters, as mock, and writes no ai_call', async () => {
    const { deepgramBatchTranscribe } = await import('../deepgram-batch');
    await deepgramBatchTranscribe({
      ...CTX,
      purpose: 'tm_transcribe',
      audio: AUDIO,
      mimeType: 'audio/mpeg',
    });
    await drain();

    expect(usageWrites).toHaveLength(1);
    const row = usageWrites[0];
    expect(row.provider).toBe('deepgram');
    expect(row.unitsSource).toBe('mock');
    // Vendor-reported seconds still come from the response body, mocked or not.
    expect(row.audioSeconds).toBe(4); // fixture duration 3.5 → Math.round
    // ruling 66 — `ai_calls` is REAL-VENDOR-CALLS-ONLY.
    expect(aiCallWrites).toHaveLength(0);
  });

  // ⚠️ THIS ARM IS TITLED FOR WHAT IT MEASURES, AFTER A MUTATION PROVED THE
  // FIRST TITLE WRONG.
  //
  // It was called "the CALL SITE refuses the fixture's id", and
  // `deepgram-batch.ts` had a `mocked ? null : …` guard to match. Removing that
  // guard left this arm GREEN — because `logApiUsage` already normalises every
  // mock row to `requestId: null` (api-usage.ts:168-171, B1-b step 2). The arm
  // was never watching the call site; it was watching the writer, and its name
  // was the only thing saying otherwise.
  //
  // The redundant guard has been removed and the title now names the real
  // subject: the END-TO-END path. An id IS available upstream, and the row that
  // lands still carries NULL. That is worth a gate — it is what keeps mocked
  // Deepgram rows legal, and therefore what keeps a mocked QA run able to meter
  // the audio stage at all. Its live mutation is on the WRITER's normalisation,
  // not on this file.
  it('NORMALISED END-TO-END — an id is available upstream and the row still lands NULL', async () => {
    // NEGATIVE CONTROL FIRST: prove the fixture really does offer an id, so a
    // future fixture edit that removes it turns this arm RED rather than
    // quietly making it vacuous. Without this, "requestId is null" would also
    // pass on a fixture that never had one — which proves nothing.
    const { mockDeepgramBatch } = await import('../mock');
    expect(mockDeepgramBatch().raw.metadata?.request_id).toBe(
      'mock-deepgram-request'
    );

    const { deepgramBatchTranscribe } = await import('../deepgram-batch');
    await deepgramBatchTranscribe({
      ...CTX,
      purpose: 'tm_transcribe',
      audio: AUDIO,
      mimeType: 'audio/mpeg',
    });
    await drain();

    expect(usageWrites).toHaveLength(1);
    // The whole point: an id was available and was NOT taken.
    expect(usageWrites[0].requestId).toBeNull();
  });

  it('LABELLED — operation is the purpose, not the `transcribe_realtime` literal', async () => {
    const { deepgramBatchTranscribe } = await import('../deepgram-batch');
    await deepgramBatchTranscribe({
      ...CTX,
      purpose: 'tm_transcribe',
      audio: AUDIO,
      mimeType: 'audio/mpeg',
    });
    await drain();

    expect(usageWrites[0].operation).toBe('tm_transcribe');
    expect(usageWrites[0].operation).not.toBe('transcribe_realtime');
  });

  it('LABELLED — modelName follows the model actually requested', async () => {
    const { deepgramBatchTranscribe } = await import('../deepgram-batch');
    // An explicit per-call override. If `modelName` were still the literal,
    // this row would read `nova-3-medical` and the assertion would fail.
    await deepgramBatchTranscribe({
      ...CTX,
      purpose: 'tm_transcribe',
      audio: AUDIO,
      mimeType: 'audio/mpeg',
      model: 'nova-3',
    });
    await drain();

    expect(usageWrites[0].modelName).toBe('nova-3');
    expect(usageWrites[0].modelName).not.toBe('nova-3-medical');
  });

  it('LABELLED — and the DEEPGRAM_MODEL env override reaches the meter too', async () => {
    process.env.DEEPGRAM_MODEL = 'nova-3-from-env';
    const { deepgramBatchTranscribe } = await import('../deepgram-batch');
    await deepgramBatchTranscribe({
      ...CTX,
      purpose: 'tm_transcribe',
      audio: AUDIO,
      mimeType: 'audio/mpeg',
    });
    await drain();

    expect(usageWrites[0].modelName).toBe('nova-3-from-env');
  });

  it('REAL — an UNMOCKED Deepgram call writes `vendor` AND the vendor\'s own id', async () => {
    // The other direction, without a network call: stub `fetch` so the code
    // takes its real branch against a vendor-shaped body.
    delete process.env.MOCK_AI_CALLS;
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify(REAL_BODY), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      )
    );

    const { deepgramBatchTranscribe } = await import('../deepgram-batch');
    await deepgramBatchTranscribe({
      ...CTX,
      purpose: 'tm_transcribe',
      audio: AUDIO,
      mimeType: 'audio/mpeg',
    });
    await drain();

    expect(usageWrites).toHaveLength(1);
    expect(usageWrites[0].unitsSource).toBe('vendor');
    // A real id, read from the real body — not the fixture's.
    expect(usageWrites[0].requestId).toBe('dg-real-0001');
    expect(usageWrites[0].audioSeconds).toBe(12);
    // And off the mock path `ai_calls` DOES get its row.
    expect(aiCallWrites).toHaveLength(1);
  });

  // ── OPENAI EMBEDDINGS ────────────────────────────────────────────────────

  it('EMITS + MARKED + QUIET — a mocked embed call meters, as mock, with a null id', async () => {
    const { embedText } = await import('../embed');
    const result = await embedText({
      ...CTX,
      purpose: 'tm_embed',
      text: '## Assessment\nTension-type headache.\n',
    });
    await drain();

    // The fixture contract the old test guarded is unchanged.
    expect(result.embedding).toHaveLength(1536);
    expect(result.inputTokens).toBe(1);

    expect(usageWrites).toHaveLength(1);
    const row = usageWrites[0];
    expect(row.provider).toBe('openai');
    // ⚠️ WAS `'embed'`, AND THAT ASSERTION WAS PINNING THE DEFECT IN PLACE.
    // `buildOpenAIEmbedUsage` hardcoded the literal while every caller's
    // purpose is `tm_embed`, so the stage metered correctly under a name no
    // stage list could ever match — and this arm, written one step earlier,
    // asserted the wrong label as though it were the contract. B4's closing
    // step threads the caller's purpose through; the operation is now the
    // purpose, here as it already is for Deepgram.
    expect(row.operation).toBe('tm_embed');
    expect(row.unitsSource).toBe('mock');
    expect(row.inputTokens).toBe(1);
    // No `_request_id` on the fixture response, and none invented.
    expect(row.requestId).toBeNull();
    expect(aiCallWrites).toHaveLength(0);
  });

  it('EMITS — a mocked embed needs NO OpenAI credential', async () => {
    // `getClient()` throws without a key and must stay inside the non-mock arm.
    // If it ever escapes, a mocked QA run stops metering embeds the moment the
    // dummy key is removed — a silent regression to the pre-B4 state.
    delete process.env.OPENAI_API_KEY;
    const { embedText } = await import('../embed');
    await embedText({
      ...CTX,
      purpose: 'tm_embed',
      text: 'no key required here',
    });
    await drain();

    expect(usageWrites).toHaveLength(1);
    expect(usageWrites[0].unitsSource).toBe('mock');
  });

  it('REAL — an UNMOCKED embed call writes `vendor` and the vendor\'s own id', async () => {
    delete process.env.MOCK_AI_CALLS;
    const vector = Array.from({ length: 1536 }, () => 0.5);
    // Stub the SDK, not the network — `embed.ts` goes through the OpenAI client.
    vi.doMock('openai', () => ({
      default: class {
        embeddings = {
          create: async () => {
            const response = {
              data: [{ embedding: vector }],
              usage: { total_tokens: 42 },
            };
            // The SDK exposes the id as a NON-ENUMERABLE property; mirror that
            // so `readOpenAIRequestId`'s documented direct access is exercised.
            Object.defineProperty(response, '_request_id', {
              value: 'oai-real-0001',
              enumerable: false,
            });
            return response;
          },
        };
      },
    }));

    const { embedText } = await import('../embed');
    await embedText({
      ...CTX,
      purpose: 'tm_embed',
      text: 'real call',
    });
    await drain();

    expect(usageWrites).toHaveLength(1);
    expect(usageWrites[0].unitsSource).toBe('vendor');
    expect(usageWrites[0].requestId).toBe('oai-real-0001');
    expect(usageWrites[0].inputTokens).toBe(42);
    expect(aiCallWrites).toHaveLength(1);
  });
});
