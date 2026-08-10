// ============================================================================
// Smoke test for the MOCK_AI_CALLS path through @meddoc/ai embedText.
// ----------------------------------------------------------------------------
// edit-tracking.test.ts mocks @meddoc/ai wholesale so the business
// logic can be verified with predictable return shapes. This file
// exercises the REAL embedText → mockEmbed → fixture wiring instead,
// so the fixture shape (length 1536, finite numbers) is locked into
// CI. Pre-T-M13 the soap-layer mock had this exact class of bug: a
// misfiled fixture slipped in and every MOCK run silently failed
// until someone read the [MOCK_AI_CALLS] log line.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// ⚠️ B4 — THIS FILE NOW REACHES THE METER, AND THAT IS WHY THE STUB IS HERE.
//
// Until B4, `embed.ts:72` returned `mockEmbed()` ABOVE the two `logApiUsage`
// calls, so this file could not reach a database seam — and it was carried as a
// written EXEMPTION in `packages/ai/src/__tests__/gate-mock-suite-stubs-the-db.
// test.ts` saying exactly that. B4 moved the mock boundary BELOW the meter, so
// the exemption's reason became false and the entry has been removed.
//
// Without this stub the failure is the nasty one documented at
// `parse-note-to-template.mock.test.ts:22` — the `unit` CI job leaves
// DATABASE_URL unset on purpose, so the deferred `apiUsageEvent.create` fails,
// `api-usage.ts` console.warns from a `setImmediate` callback NOTHING awaits,
// and if that warn lands after the file finishes the RPC teardown rejects:
// the run EXITS 1 WITH EVERY TEST GREEN.
//
// The factory matches `gate-b0-mock-boundary.test.ts` exactly — no extra
// surface, so a future module importing a model this stub lacks fails LOUDLY
// rather than reading `undefined`.
vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: { create: (a: unknown) => Promise.resolve(a) },
    aiCall: { create: (a: unknown) => Promise.resolve(a) },
  };
  return { __esModule: true, default: client, prisma: client };
});

describe('embedText — MOCK_AI_CALLS fixture', () => {
  const prior = process.env.MOCK_AI_CALLS;
  beforeEach(() => {
    process.env.MOCK_AI_CALLS = 'true';
  });
  afterEach(async () => {
    // logApiUsage defers via setImmediate — drain it so no metering work
    // outlives this file, whatever the stub does. Defence in depth.
    await new Promise((r) => setImmediate(r));
    if (prior === undefined) delete process.env.MOCK_AI_CALLS;
    else process.env.MOCK_AI_CALLS = prior;
  });

  it('returns a 1536-dim finite vector', async () => {
    const { embedText, EMBED_DIMENSION } = await import('@meddoc/ai');
    expect(EMBED_DIMENSION).toBe(1536);

    const result = await embedText({
      text: '## Assessment\nTension-type headache.\n',
      practiceId: 'p_mock',
      visitId: 'v_mock',
      purpose: 'tm_embed',
    });

    expect(result.embedding).toHaveLength(1536);
    expect(result.embedding.every((n) => Number.isFinite(n))).toBe(true);
    expect(result.inputTokens).toBe(1);
    expect(result.costCents).toBe(0);
  });
});
