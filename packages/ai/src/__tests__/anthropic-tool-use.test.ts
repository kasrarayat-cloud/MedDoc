// ============================================================================
// anthropicComplete — tool_use structured-output path (2026-05-13).
// ----------------------------------------------------------------------------
// Cross-input-mode audit Finding 1 hardening: PED1 text_notes hit a
// JSON_PARSE_FAIL at position 790 (trailing-garbage shape) that
// exhausted the 2-retry budget. Switching to Anthropic's native
// tool_use eliminates the free-form JSON.parse failure class entirely —
// the model is FORCED to call a tool whose `input_schema` matches the
// Zod schema, and the response is a structured object, not free text.
//
// These tests pin the tool_use code path: SDK is invoked with `tools` +
// `tool_choice`; the tool's `input` is read directly off the response;
// Zod safeParse still runs on the tool input; missing tool_use block
// throws the same error shape downstream callers expect.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';

// The Anthropic client lazy-init checks process.env.ANTHROPIC_API_KEY
// before constructing. Tests stub a placeholder so getClient() succeeds.
process.env.ANTHROPIC_API_KEY = 'sk-test-fixture';

// Anthropic SDK mock — captures the create() call args so we can assert
// the tool_use payload shape.
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

import { anthropicComplete } from '../anthropic';

const Schema = z.object({
  codes: z.array(z.object({ code: z.string(), description: z.string() })),
});

const baseArgs = {
  practiceId: 'p1',
  visitId: 'v1',
  userId: 'u1',
  purpose: 'tm_icd_coding' as const,
  model: 'claude-sonnet-4-6',
  system: 'You are a coder.',
  user: 'Code this visit.',
  schema: Schema,
  useToolUse: {
    name: 'submit_icd_codes',
    description: 'Submit ICDs.',
  },
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

describe('anthropicComplete with useToolUse — SDK call shape', () => {
  it('passes `tools` + `tool_choice` to the SDK when useToolUse is set', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'tool_use',
          id: 'tu_1',
          name: 'submit_icd_codes',
          input: { codes: [{ code: 'Z39.2', description: 'Postpartum' }] },
        },
      ],
      usage: mockUsage(),
    });

    await anthropicComplete(baseArgs);

    expect(mocks.createCall).toHaveBeenCalledTimes(1);
    const call = mocks.createCall.mock.calls[0][0];
    expect(call.tools).toBeDefined();
    expect(call.tools).toHaveLength(1);
    expect(call.tools[0].name).toBe('submit_icd_codes');
    expect(call.tools[0].description).toBe('Submit ICDs.');
    expect(call.tools[0].input_schema).toBeDefined();
    expect(call.tools[0].input_schema.type).toBe('object');
    expect(call.tool_choice).toEqual({ type: 'tool', name: 'submit_icd_codes' });
  });

  it('does NOT pass `tools` to the SDK when useToolUse is omitted (backwards-compat)', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'text',
          text: '{"codes":[{"code":"Z39.2","description":"Postpartum"}]}',
        },
      ],
      usage: mockUsage(),
    });

    const { useToolUse: _omit, ...freeFormArgs } = baseArgs;
    await anthropicComplete(freeFormArgs);

    const call = mocks.createCall.mock.calls[0][0];
    expect(call.tools).toBeUndefined();
    expect(call.tool_choice).toBeUndefined();
  });

  it('input_schema reflects the Zod schema (codes array with code+description)', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'tool_use',
          id: 'tu_1',
          name: 'submit_icd_codes',
          input: { codes: [] },
        },
      ],
      usage: mockUsage(),
    });

    await anthropicComplete(baseArgs);

    const call = mocks.createCall.mock.calls[0][0];
    const schema = call.tools[0].input_schema;
    expect(schema.properties).toBeDefined();
    expect(schema.properties.codes).toBeDefined();
    expect(schema.properties.codes.type).toBe('array');
    expect(schema.required).toContain('codes');
  });
});

describe('anthropicComplete with useToolUse — response handling', () => {
  it('returns the tool_use input directly (no JSON.parse needed)', async () => {
    const expected = {
      codes: [
        { code: 'Z39.2', description: 'Postpartum follow-up' },
        { code: 'Z30.430', description: 'IUD insertion' },
      ],
    };
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'tool_use',
          id: 'tu_1',
          name: 'submit_icd_codes',
          input: expected,
        },
      ],
      usage: mockUsage(),
    });

    const result = await anthropicComplete(baseArgs);
    expect(result).toEqual(expected);
  });

  it('happy path — full IcdCode shape (5 fields) survives Zod validation end-to-end', async () => {
    // Strengthens coverage: prior tests only mocked { code, description };
    // this test exercises the full IcdCode schema used by L7a in
    // production, including the regex-validated `code` field, the
    // `confidence` numeric range, and the `confidenceLevel` enum.
    const FullSchema = z.object({
      codes: z.array(z.object({
        code: z.string().regex(/^[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$/i),
        description: z.string().min(1),
        evidence_quote: z.string().min(1),
        confidence: z.number().min(0).max(1),
        confidenceLevel: z.enum(['high', 'medium', 'low']),
      })),
    });
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'tool_use',
          id: 'tu_1',
          name: 'submit_icd_codes',
          input: {
            codes: [
              {
                code: 'Z39.2',
                description: 'Encounter for routine postpartum follow-up',
                evidence_quote: '6 weeks postpartum, routine visit',
                confidence: 0.95,
                confidenceLevel: 'high',
              },
            ],
          },
        },
      ],
      usage: mockUsage(),
    });

    const result = await anthropicComplete({
      ...baseArgs,
      schema: FullSchema,
    });
    expect(result.codes).toHaveLength(1);
    expect(result.codes[0].code).toBe('Z39.2');
    expect(result.codes[0].confidenceLevel).toBe('high');
  });

  it('still validates the tool_use input via Zod (defense-in-depth)', async () => {
    // Tool input has a bad shape — codes is a string, not an array.
    // Anthropic's tool_use is best-effort on schema adherence; we
    // still safeParse to catch model drift.
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'tool_use',
          id: 'tu_1',
          name: 'submit_icd_codes',
          input: { codes: 'not-an-array' },
        },
      ],
      usage: mockUsage(),
    });

    await expect(anthropicComplete(baseArgs)).rejects.toThrow(/SCHEMA_FAIL/);
  });

  it('throws JSON_PARSE_FAIL-shape error when no tool_use block in the response', async () => {
    // Defensive: even with `tool_choice: { type: 'tool' }` forced,
    // a malformed response could in theory return no tool_use block.
    mocks.createCall.mockResolvedValueOnce({
      content: [{ type: 'text', text: 'I refuse.' }],
      usage: mockUsage(),
    });

    await expect(anthropicComplete(baseArgs)).rejects.toThrow(
      /Anthropic response was not valid JSON/,
    );
  });
});

describe('anthropicComplete free-form path — backwards-compat regression guard', () => {
  it('parses JSON from text content blocks when useToolUse is omitted', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'text',
          text: '{"codes":[{"code":"K80.20","description":"Gallstones"}]}',
        },
      ],
      usage: mockUsage(),
    });

    const { useToolUse: _omit, ...freeFormArgs } = baseArgs;
    const result = await anthropicComplete(freeFormArgs);
    expect(result.codes).toHaveLength(1);
    expect(result.codes[0].code).toBe('K80.20');
  });

  it('strips ```json fences (legacy free-form behavior)', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'text',
          text: '```json\n{"codes":[{"code":"K80.20","description":"Gallstones"}]}\n```',
        },
      ],
      usage: mockUsage(),
    });

    const { useToolUse: _omit, ...freeFormArgs } = baseArgs;
    const result = await anthropicComplete(freeFormArgs);
    expect(result.codes[0].code).toBe('K80.20');
  });

  it('throws JSON_PARSE_FAIL on free-form garbage (regression — proves the failure mode tool_use eliminates)', async () => {
    mocks.createCall.mockResolvedValueOnce({
      content: [
        {
          type: 'text',
          text: '{"codes":[]}\n\nLet me know if you need anything else!',
        },
      ],
      usage: mockUsage(),
    });

    const { useToolUse: _omit, ...freeFormArgs } = baseArgs;
    // This is the PED1 trailing-garbage shape — would land at
    // "position N: Unexpected non-whitespace character after JSON."
    await expect(anthropicComplete(freeFormArgs)).rejects.toThrow(
      /Anthropic response was not valid JSON/,
    );
  });
});
