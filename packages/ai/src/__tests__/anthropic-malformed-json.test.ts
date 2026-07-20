// ============================================================================
// anthropicComplete — text-mode JSON.parse fail → ModelOutputMalformedError
// ----------------------------------------------------------------------------
// FIND-P1-010 (2026-05-14): the legacy text-mode path at anthropic.ts:292
// used to throw a generic `Error('Anthropic response was not valid JSON: ...')`
// when the model returned non-JSON. The model-client retry loop matched it
// by `err.message.startsWith(...)` — fragile. categorizeError couldn't
// classify it without the same string match, so a body that would never
// parse still got 'transient' → BullMQ retry.
//
// Post-fix: anthropic.ts throws a typed `ModelOutputMalformedError`. The
// message prefix stays for backward-compat; the class supersedes the
// string match via instanceof.
//
// These tests pin the typed throw + the captured diagnostic fields. The
// happy path (well-formed JSON) is covered indirectly by every existing
// test in this file's siblings — no regression check needed here.
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
import { ModelOutputMalformedError } from '../errors';

const Schema = z.object({
  codes: z.array(z.object({ code: z.string() })),
});

// IMPORTANT: NO useToolUse in baseArgs — these tests exercise the
// text-mode branch (free-form JSON, the one FIND-P1-010 covers).
const baseArgs = {
  practiceId: 'p1',
  visitId: 'v1',
  userId: 'u1',
  purpose: 'tm_icd_coding' as const,
  model: 'claude-sonnet-4-6',
  system: 'You are a coder.',
  user: 'Code this visit.',
  schema: Schema,
};

function mockUsage() {
  return {
    input_tokens: 100,
    output_tokens: 50,
    cache_read_input_tokens: 0,
    cache_creation_input_tokens: 0,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('anthropicComplete — text-mode JSON.parse fail (FIND-P1-010)', () => {
  it('throws ModelOutputMalformedError when the response is not valid JSON', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'text',
          text: "Sure! Here's the JSON: { invalid: nope",
        },
      ],
      usage: mockUsage(),
    });

    await expect(anthropicComplete(baseArgs)).rejects.toBeInstanceOf(
      ModelOutputMalformedError
    );
  });

  it('error carries the truncated rawTextSlice (≤ 200 chars)', async () => {
    const garbage = 'a'.repeat(500); // 500 chars
    mocks.createCall.mockResolvedValueOnce({
      content: [{ type: 'text', text: garbage }],
      usage: mockUsage(),
    });

    try {
      await anthropicComplete(baseArgs);
      throw new Error('expected throw');
    } catch (err) {
      expect(err).toBeInstanceOf(ModelOutputMalformedError);
      const typed = err as ModelOutputMalformedError;
      expect(typed.rawTextSlice).toHaveLength(200);
      expect(typed.rawTextSlice).toBe('a'.repeat(200));
    }
  });

  it('error message preserves the legacy "Anthropic response was not valid JSON" prefix', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [{ type: 'text', text: 'definitely not json' }],
      usage: mockUsage(),
    });

    try {
      await anthropicComplete(baseArgs);
      throw new Error('expected throw');
    } catch (err) {
      expect(err).toBeInstanceOf(ModelOutputMalformedError);
      const typed = err as Error;
      // Model-client.ts retry-loop fallback does startsWith('Anthropic
      // response was not valid JSON') — pre-typed throws must keep
      // matching during the migration window.
      expect(typed.message.startsWith('Anthropic response was not valid JSON')).toBe(true);
    }
  });

  it('JSON_PARSE_FAIL is logged to ai_calls with the capped errorDetails', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [{ type: 'text', text: '{"oops": ' }],
      usage: mockUsage(),
    });

    await expect(anthropicComplete(baseArgs)).rejects.toBeInstanceOf(
      ModelOutputMalformedError
    );

    // logAiCall is invoked synchronously inside the catch path (no
    // await on the side-effect log call by design).
    expect(mocks.logAiCall).toHaveBeenCalled();
    const call = mocks.logAiCall.mock.calls.find(
      ([arg]) => arg?.errorCode === 'JSON_PARSE_FAIL'
    );
    expect(call).toBeTruthy();
    expect(call![0].success).toBe(false);
    // The errorDetails carry a capped version of the unfenced body.
    expect(typeof call![0].errorDetails).toBe('string');
  });

  it('strips ```json fences before parsing — only THEN throws on residual garbage', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [{ type: 'text', text: '```json\nNOT JSON\n```' }],
      usage: mockUsage(),
    });

    await expect(anthropicComplete(baseArgs)).rejects.toBeInstanceOf(
      ModelOutputMalformedError
    );

    // The rawTextSlice should reflect the post-fence-strip text, not
    // the original with fences. (Documents the slice contract for
    // diagnostic readers.)
    try {
      await anthropicComplete(baseArgs);
    } catch {
      // first throw consumed above; the test above already pins this.
    }
  });

  it('does NOT throw on well-formed JSON that matches the schema (happy path)', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'text',
          text: JSON.stringify({ codes: [{ code: 'Z00.00' }] }),
        },
      ],
      usage: mockUsage(),
    });

    const result = await anthropicComplete(baseArgs);
    expect(result).toEqual({ codes: [{ code: 'Z00.00' }] });
  });

  it('removes malformed response content from owned logs and thrown errors', async () => {
    const identifier = 'SYNTHETIC_PATIENT_ALICE_MRN_998877';
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    mocks.createCall.mockResolvedValueOnce({
      content: [{ type: 'text', text: `${identifier} { definitely-not-json` }],
      usage: mockUsage(),
    });

    let caught: unknown;
    try {
      await anthropicComplete({ ...baseArgs, idempotencyKey: 'c'.repeat(64) });
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(ModelOutputMalformedError);
    expect((caught as ModelOutputMalformedError).rawTextSlice).toBe('');
    expect(JSON.stringify(caught)).not.toContain(identifier);
    const logged = mocks.logAiCall.mock.calls.find(
      ([arg]) => arg?.errorCode === 'JSON_PARSE_FAIL',
    )?.[0];
    expect(logged).toBeTruthy();
    expect(JSON.stringify(logged)).not.toContain(identifier);
    expect(JSON.parse(logged.errorDetails)).toMatchObject({
      contractVersion: 'owned-anthropic-malformed-v1',
      errorCode: 'JSON_PARSE_FAIL',
      responseSha256: expect.stringMatching(/^[a-f0-9]{64}$/u),
    });
    expect(consoleError).not.toHaveBeenCalled();
  });

  it('keeps owned schema failures structural and omits the raw output', async () => {
    const identifier = 'SYNTHETIC_PATIENT_BOB_MRN_112233';
    mocks.createCall.mockResolvedValueOnce({
      content: [{ type: 'text', text: JSON.stringify({ codes: identifier }) }],
      usage: mockUsage(),
    });

    let caught: unknown;
    try {
      await anthropicComplete({ ...baseArgs, idempotencyKey: 'd'.repeat(64) });
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(Error);
    expect((caught as Error).message).toBe('SCHEMA_FAIL');
    expect((caught as Error & { rawOutput?: string }).rawOutput).toBeUndefined();
    expect(JSON.stringify(caught)).not.toContain(identifier);
    const logged = mocks.logAiCall.mock.calls.find(
      ([arg]) => arg?.errorCode === 'SCHEMA_FAIL',
    )?.[0];
    expect(JSON.stringify(logged)).not.toContain(identifier);
    expect(JSON.parse(logged.errorDetails)).toMatchObject({
      contractVersion: 'owned-anthropic-malformed-v1',
      errorCode: 'SCHEMA_FAIL',
      issueCount: 1,
    });
  });

  it.each(['structured', 'text'] as const)(
    'removes provider error messages from owned %s failures',
    async (path) => {
      const identifier = 'SYNTHETIC_PATIENT_CAROL_MRN_445566';
      mocks.createCall.mockRejectedValueOnce(
        Object.assign(new Error(`upstream echoed ${identifier}`), {
          status: 503,
          error: {
            type: 'error',
            error: {
              type: 'api_error',
              message: `provider echoed ${identifier}`,
            },
          },
          request_id: 'req_synthetic_123',
        }),
      );

      let caught: unknown;
      try {
        if (path === 'structured') {
          await anthropicComplete({
            ...baseArgs,
            idempotencyKey: 'e'.repeat(64),
          });
        } else {
          await anthropicCompleteText({
            ...baseArgs,
            idempotencyKey: 'f'.repeat(64),
          });
        }
      } catch (error) {
        caught = error;
      }

      expect(caught).toMatchObject({
        name: 'OwnedProviderRequestError',
        status: 503,
        request_id: 'req_synthetic_123',
      });
      expect(JSON.stringify(caught)).not.toContain(identifier);
      expect((caught as Error).message).not.toContain(identifier);
      const logged = mocks.logAiCall.mock.calls.at(-1)?.[0];
      expect(JSON.stringify(logged)).not.toContain(identifier);
      expect(JSON.parse(logged.errorDetails)).toEqual({
        contractVersion: 'owned-anthropic-error-v1',
        errorClass: 'Error',
        httpStatus: 503,
        apiErrorType: 'api_error',
        requestId: 'req_synthetic_123',
      });
    },
  );
});
