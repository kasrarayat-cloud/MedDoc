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

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

describe('embedText — MOCK_AI_CALLS fixture', () => {
  const prior = process.env.MOCK_AI_CALLS;
  beforeEach(() => {
    process.env.MOCK_AI_CALLS = 'true';
  });
  afterEach(() => {
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
