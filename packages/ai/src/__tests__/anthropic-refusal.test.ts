// ============================================================================
// Anthropic content-policy refusal — Q1 #09.1
// ----------------------------------------------------------------------------
// When Anthropic returns `stop_reason: 'refusal'`, the model declined to
// generate. A refusal is deterministic for the same input, so anthropic.ts
// throws a typed `AnthropicRefusalError` (categorized PERMANENT by the worker
// → no retry burn) and logs the token-spending call as `AI_REFUSAL`.
//
// Pins the typed throw on all three call paths (completeText, complete
// text-mode, complete tool-mode) + the AI_REFUSAL telemetry, and that a
// normal stop_reason is unaffected.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';

process.env.ANTHROPIC_API_KEY = 'sk-test-fixture';

const mocks = vi.hoisted(() => ({
  createCall: vi.fn(),
  logAiCall: vi.fn(),
  logApiUsage: vi.fn(),
}));

vi.mock('@anthropic-ai/sdk', () => ({
  default: class {
    messages = { create: mocks.createCall };
  },
}));
vi.mock('../log', () => ({ logAiCall: mocks.logAiCall }));
vi.mock('../api-usage', () => ({
  logApiUsage: mocks.logApiUsage,
  buildAnthropicUsage: () => ({}),
}));

import { anthropicComplete, anthropicCompleteText } from '../anthropic';
import { AnthropicRefusalError } from '../errors';

const Schema = z.object({ codes: z.array(z.object({ code: z.string() })) });

function mockUsage() {
  return {
    input_tokens: 100,
    output_tokens: 5,
    cache_read_input_tokens: 0,
    cache_creation_input_tokens: 0,
  };
}

const textArgs = {
  practiceId: 'p1',
  visitId: 'v1',
  userId: 'u1',
  purpose: 'tm_soap_draft' as const,
  model: 'claude-opus-4-8',
  system: 'You are a clinical scribe.',
  user: 'Draft the SOAP.',
};

const completeArgs = {
  ...textArgs,
  purpose: 'tm_icd_coding' as const,
  schema: Schema,
};

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

describe('anthropic refusal (Q1 #09.1)', () => {
  it('anthropicCompleteText: stop_reason=refusal → throws AnthropicRefusalError', async () => {
    mocks.createCall.mockResolvedValueOnce({
      stop_reason: 'refusal',
      content: [],
      usage: mockUsage(),
    });
    await expect(anthropicCompleteText(textArgs)).rejects.toBeInstanceOf(
      AnthropicRefusalError
    );
  });

  it('logs the token-spending call as AI_REFUSAL (success:false) + carries model/purpose', async () => {
    mocks.createCall.mockResolvedValueOnce({
      stop_reason: 'refusal',
      content: [],
      usage: mockUsage(),
    });
    try {
      await anthropicCompleteText(textArgs);
      throw new Error('expected throw');
    } catch (err) {
      expect(err).toBeInstanceOf(AnthropicRefusalError);
      const typed = err as AnthropicRefusalError;
      expect(typed.code).toBe('AI_REFUSAL');
      expect(typed.model).toBe('claude-opus-4-8');
      expect(typed.purpose).toBe('tm_soap_draft');
    }
    expect(mocks.logAiCall).toHaveBeenCalledWith(
      expect.objectContaining({ success: false, errorCode: 'AI_REFUSAL' })
    );
  });

  it('anthropicComplete (text-mode): refusal throws BEFORE the JSON parse', async () => {
    mocks.createCall.mockResolvedValueOnce({
      stop_reason: 'refusal',
      content: [],
      usage: mockUsage(),
    });
    await expect(anthropicComplete(completeArgs)).rejects.toBeInstanceOf(
      AnthropicRefusalError
    );
  });

  it('anthropicComplete (tool-mode): refusal throws before reading the tool block', async () => {
    mocks.createCall.mockResolvedValueOnce({
      stop_reason: 'refusal',
      content: [],
      usage: mockUsage(),
    });
    await expect(
      anthropicComplete({
        ...completeArgs,
        useToolUse: { name: 'emit_codes', description: 'emit ICD codes' },
      })
    ).rejects.toBeInstanceOf(AnthropicRefusalError);
  });

  it('normal stop_reason (end_turn) is unaffected — returns text, no refusal error', async () => {
    mocks.createCall.mockResolvedValueOnce({
      stop_reason: 'end_turn',
      content: [{ type: 'text', text: '## Subjective\nclean output' }],
      usage: mockUsage(),
    });
    const res = await anthropicCompleteText(textArgs);
    expect(res.text).toContain('Subjective');
    expect(mocks.logAiCall).not.toHaveBeenCalledWith(
      expect.objectContaining({ errorCode: 'AI_REFUSAL' })
    );
  });
});
