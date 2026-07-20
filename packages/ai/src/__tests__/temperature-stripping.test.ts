// ============================================================================
// Q2 follow-up — Opus 4.x temperature-deprecation handling.
// ----------------------------------------------------------------------------
// Anthropic's Opus 4.7 returns 400 invalid_request_error if the request
// body includes a `temperature` parameter (the model uses adaptive
// internal sampling and stopped accepting the param). Sonnet + Haiku
// still accept it. anthropic.ts strips silently for the Opus 4.x family
// and passes through for everything else. This guard test asserts the
// wire shape so a future SDK refactor can't quietly re-introduce the
// param for Opus models.
//
// Strategy: mock the @anthropic-ai/sdk client at the SDK boundary and
// capture every `messages.create` payload. Drive both layer-equivalent
// paths (anthropicComplete with a Zod schema; anthropicCompleteText
// for free-text markdown).
// ============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { z } from 'zod';

const captured: Array<{
  model: string;
  payload: Record<string, unknown>;
  options?: Record<string, unknown>;
}> = [];

// Reset between tests so each case sees its own captured list.
beforeEach(() => {
  captured.length = 0;
});

// Mock the SDK before importing anthropic.ts so the import binds to the
// mock. The mock returns a minimal valid response payload (one text
// block + usage counts) — enough for the JSON / text path to complete
// successfully.
vi.mock('@anthropic-ai/sdk', () => {
  class MockAnthropic {
    public messages = {
      create: vi.fn(
        async (
          payload: Record<string, unknown>,
          options?: Record<string, unknown>,
        ) => {
          captured.push({ model: payload.model as string, payload, options });
          // Return a minimal response. JSON path: include valid JSON.
          // Text path: any non-empty text is fine.
          return {
            content: [{ type: 'text', text: '{"ok": true}' }],
            usage: { input_tokens: 1, output_tokens: 1 },
          };
        },
      ),
    };
  }
  return { default: MockAnthropic };
});

// Stub the AiCall + ApiUsage writes so we don't hit Prisma in tests.
vi.mock('../log', () => ({
  logAiCall: vi.fn(),
  redactPhi: (s: unknown) => String(s),
}));
vi.mock('../api-usage', () => ({
  logApiUsage: vi.fn(),
  buildAnthropicUsage: vi.fn(() => ({})),
}));

// Set the API key so getClient() doesn't throw.
process.env.ANTHROPIC_API_KEY = 'test-key';

// Import AFTER mocks are set up.
const { anthropicComplete, anthropicCompleteText } = await import('../anthropic');

const trivialSchema = z.object({ ok: z.boolean() });
const baseArgs = {
  practiceId: 'p1',
  visitId: 'v1',
  userId: null,
  purpose: 'tm_soap_draft' as const,
  system: 'sys',
  user: 'usr',
};

describe('anthropicComplete — Opus 4.x temperature stripping', () => {
  it('strips temperature when model is claude-opus-4-7', async () => {
    await anthropicComplete({
      ...baseArgs,
      model: 'claude-opus-4-7',
      schema: trivialSchema,
      temperature: 0.2,
    });
    expect(captured).toHaveLength(1);
    const payload = captured[0]!.payload;
    expect(payload.model).toBe('claude-opus-4-7');
    expect(payload).not.toHaveProperty('temperature');
  });

  it('strips temperature for forward-compat Opus 4.x (claude-opus-4-6)', async () => {
    await anthropicComplete({
      ...baseArgs,
      model: 'claude-opus-4-6',
      schema: trivialSchema,
      temperature: 0.5,
    });
    expect(captured[0]!.payload).not.toHaveProperty('temperature');
  });

  it('passes temperature through for claude-sonnet-4-6', async () => {
    await anthropicComplete({
      ...baseArgs,
      model: 'claude-sonnet-4-6',
      schema: trivialSchema,
      temperature: 0.2,
    });
    expect(captured[0]!.payload.temperature).toBe(0.2);
  });

  it('passes temperature through for claude-haiku-4-5 (forward compat)', async () => {
    await anthropicComplete({
      ...baseArgs,
      model: 'claude-haiku-4-5',
      schema: trivialSchema,
      temperature: 0.0,
    });
    expect(captured[0]!.payload.temperature).toBe(0.0);
  });

  it('omits temperature key when args.temperature is undefined regardless of model', async () => {
    await anthropicComplete({
      ...baseArgs,
      model: 'claude-sonnet-4-6',
      schema: trivialSchema,
    });
    expect(captured[0]!.payload).not.toHaveProperty('temperature');
  });
});

describe('anthropicCompleteText — Opus 4.x temperature stripping', () => {
  it('strips temperature when model is claude-opus-4-7', async () => {
    await anthropicCompleteText({
      ...baseArgs,
      model: 'claude-opus-4-7',
      temperature: 0.2,
    });
    expect(captured[0]!.payload).not.toHaveProperty('temperature');
  });

  it('passes temperature through for claude-sonnet-4-6', async () => {
    await anthropicCompleteText({
      ...baseArgs,
      model: 'claude-sonnet-4-6',
      temperature: 0.2,
    });
    expect(captured[0]!.payload.temperature).toBe(0.2);
  });

  it('forwards the durable text-completion idempotency key at the provider boundary', async () => {
    await anthropicCompleteText({
      ...baseArgs,
      model: 'claude-sonnet-4-6',
      idempotencyKey: 'b'.repeat(64),
    });
    expect(captured[0]!.options).toEqual({
      headers: { 'Idempotency-Key': 'b'.repeat(64) },
      maxRetries: 0,
    });
  });

  it('keeps ordinary unowned text calls on the SDK default retry policy', async () => {
    await anthropicCompleteText({
      ...baseArgs,
      model: 'claude-sonnet-4-6',
    });
    expect(captured[0]!.options).toBeUndefined();
  });
});
