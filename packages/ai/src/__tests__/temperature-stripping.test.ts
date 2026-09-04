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

const captured: Array<{ model: string; payload: Record<string, unknown> }> = [];

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
      create: vi.fn(async (payload: Record<string, unknown>) => {
        captured.push({ model: payload.model as string, payload });
        // Return a minimal response. JSON path: include valid JSON.
        // Text path: any non-empty text is fine.
        return {
          content: [{ type: 'text', text: '{"ok": true}' }],
          usage: { input_tokens: 1, output_tokens: 1 },
        };
      }),
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
});

// ============================================================================
// ⚠️ #179(7) — THE PER-FAMILY DECISION TABLE, AND THE REFUSAL.
// ----------------------------------------------------------------------------
// The family prefix above is KEPT — it is forward-compat within a family known
// to reject the parameter, and `claude-opus-4-6` arms exactly that. What it
// could not do is cross a family boundary: `claude-opus-5` does not match
// `claude-opus-4`, so a model switch would have changed the WIRE SHAPE and the
// MODEL in one act.
//
// Opus 5 strips NOT because it rejects temperature — that is unmeasured — but
// because production 4.8 already runs stripped and a switch must move ONE
// VARIABLE. And a model in neither family is a NAMED REFUSAL: nobody measured
// it, and guessing either way is a guess about a clinical request.
// ============================================================================
describe('#179(7) — temperature policy is a table, and the unknown refuses', () => {
  it('⚠️ claude-opus-5 STRIPS — the switch must not change the wire shape too', async () => {
    await anthropicComplete({
      ...baseArgs,
      model: 'claude-opus-5',
      schema: trivialSchema,
      temperature: 0.5,
    });
    expect(captured).toHaveLength(1);
    expect(captured[0]!.payload).not.toHaveProperty('temperature');
  });

  it('the whole Opus 4.x family still strips — unchanged behaviour', async () => {
    for (const model of ['claude-opus-4-6', 'claude-opus-4-7', 'claude-opus-4-8']) {
      captured.length = 0;
      await anthropicComplete({ ...baseArgs, model, schema: trivialSchema, temperature: 0.5 });
      expect(captured[0]!.payload, `${model} sent temperature`).not.toHaveProperty('temperature');
    }
  });

  it('sonnet and haiku still RECEIVE temperature — the table is not a blanket strip', async () => {
    for (const model of ['claude-sonnet-4-6', 'claude-haiku-4-5']) {
      captured.length = 0;
      await anthropicComplete({ ...baseArgs, model, schema: trivialSchema, temperature: 0.5 });
      expect(captured[0]!.payload, `${model} lost temperature`).toHaveProperty('temperature', 0.5);
    }
  });

  it('⚠️ an UNLISTED model REFUSES BY NAME rather than passing through silently', async () => {
    await expect(
      anthropicComplete({
        ...baseArgs,
        model: 'claude-zzunmeasured-9',
        schema: trivialSchema,
        temperature: 0.5,
      }),
    ).rejects.toThrow(/no temperature policy for model/);
    // and nothing reached the wire
    expect(captured).toHaveLength(0);
  });
});

