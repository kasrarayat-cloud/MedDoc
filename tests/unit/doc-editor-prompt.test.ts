// ============================================================================
// Doc Editor — two-pass edit architecture (Pass 1 intent parser + Pass 2 executor)
// ----------------------------------------------------------------------------
// Verifies the contract of src/lib/ai-service.ts. OpenAI is mocked.
//
// Structure:
//   - Pass 1 tests: INTENT_PARSER_PROMPT content + model/config
//   - Pass 2 tests: EXECUTOR_PROMPT content + model + how intent is threaded in
//   - End-to-end edit tests: two calls, combined usage, low-confidence short-circuit
//   - Non-edit actions (review / extract / chat): single-pass path intact
// ============================================================================

import { describe, it, expect, beforeEach, vi } from 'vitest';

const { mockCreate } = vi.hoisted(() => ({ mockCreate: vi.fn() }));

vi.mock('openai', () => {
  class OpenAIMock {
    chat = { completions: { create: mockCreate } };
  }
  return { default: OpenAIMock };
});

import { processWithAI, type EditIntent } from '@/lib/ai-service';

beforeEach(() => {
  mockCreate.mockReset();
  process.env.OPENAI_API_KEY = 'test-key';
});

type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string };

function intentResponse(intent: EditIntent) {
  return {
    choices: [{ message: { content: JSON.stringify(intent) } }],
    usage: { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150 },
  };
}

function executorResponse(body = 'x') {
  return {
    choices: [
      {
        message: {
          content: `\`\`\`UPDATED_DOC\n${body}\n\`\`\`\nDone — applied.`,
        },
      },
    ],
    usage: { prompt_tokens: 2000, completion_tokens: 500, total_tokens: 2500 },
  };
}

function highConfidenceIntent(overrides: Partial<EditIntent> = {}): EditIntent {
  return {
    operation: 'replace',
    target_section: 'PROCEDURE DESCRIPTION',
    replacement_text: 'arthur Morgan',
    directive: null,
    partial_edit_description: null,
    fill_fields: [],
    confidence: 'high',
    reasoning: 'stub',
    ...overrides,
  };
}

// ----------------------------------------------------------------------------
// PASS 1 — intent parser
// ----------------------------------------------------------------------------
describe('Pass 1 — intent parser', () => {
  beforeEach(() => {
    mockCreate.mockResolvedValueOnce(intentResponse(highConfidenceIntent()));
    mockCreate.mockResolvedValueOnce(executorResponse());
  });

  it('uses gpt-4o-mini with JSON-schema structured output', async () => {
    await processWithAI({
      action: 'edit',
      documentContent: 'PROCEDURE DESCRIPTION:\nold content',
      userMessage: 'replace the whole procedure description with arthur Morgan',
    });

    const pass1Call = mockCreate.mock.calls[0][0];
    expect(pass1Call.model).toBe('gpt-4o-mini');
    expect(pass1Call.temperature).toBe(0);
    expect(pass1Call.response_format?.type).toBe('json_schema');
    expect(pass1Call.response_format?.json_schema?.name).toBe('edit_intent');
    expect(pass1Call.response_format?.json_schema?.strict).toBe(true);
    // Required fields on the schema must list every EditIntent field so
    // OpenAI strict mode accepts it.
    const required = pass1Call.response_format.json_schema.schema.required;
    expect(required).toEqual(
      expect.arrayContaining([
        'operation',
        'target_section',
        'replacement_text',
        'directive',
        'partial_edit_description',
        'fill_fields',
        'confidence',
        'reasoning',
      ])
    );
  });

  it('INTENT_PARSER_PROMPT enumerates all operations with their triggers', async () => {
    await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'replace procedure description with X',
    });

    const system = (mockCreate.mock.calls[0][0].messages as ChatMessage[])
      .find((m) => m.role === 'system')!.content;

    // Every operation the executor supports must be defined in the parser prompt.
    for (const op of ['"replace"', '"blank"', '"generate"', '"partial_edit"', '"fill_field"', '"unclear"']) {
      expect(system).toContain(op);
    }
    // The trigger-phrase recipes — how the doctor typically says each.
    expect(system).toMatch(/replace X with Y/);
    expect(system).toMatch(/"blank X" \/ "clear X"/);
    expect(system).toMatch(/summarize X/);
    expect(system).toMatch(/fix the typo in X/);
  });

  it('INTENT_PARSER_PROMPT tells the model NOT to filter short / name-like replacements', async () => {
    await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'replace procedure description with arthur Morgan',
    });

    const system = (mockCreate.mock.calls[0][0].messages as ChatMessage[])
      .find((m) => m.role === 'system')!.content;

    expect(system).toMatch(/VERBATIM RULE/);
    expect(system).toMatch(/arthur Morgan/);
    expect(system).toMatch(/Do NOT judge,\s+filter, or reject/i);
    expect(system).toMatch(/It's short/);
    expect(system).toMatch(/It's a name/);
    expect(system).toMatch(/It looks like a placeholder or test input/);
  });

  it('INTENT_PARSER_PROMPT teaches charitable interpretation of voice typos', async () => {
    await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'blan the procedute description',
    });

    const system = (mockCreate.mock.calls[0][0].messages as ChatMessage[])
      .find((m) => m.role === 'system')!.content;

    expect(system).toMatch(/CHARITABLE INTERPRETATION/);
    expect(system).toMatch(/"blan" ≈ "blank"/);
    expect(system).toMatch(/"repalce" ≈ "replace"/);
    expect(system).toMatch(/"procedute" ≈ "procedure"/);
  });

  it('INTENT_PARSER_PROMPT includes worked examples for each major operation', async () => {
    await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'go',
    });

    const system = (mockCreate.mock.calls[0][0].messages as ChatMessage[])
      .find((m) => m.role === 'system')!.content;

    // Replace example with arthur Morgan.
    expect(system).toMatch(/"replace the whole procedure description with arthur Morgan"/);
    // Blank example.
    expect(system).toMatch(/"blank the procedure description"/);
    // Generate example.
    expect(system).toMatch(/"read the procedure description and type me a short small procedure"/);
    // Fill-field example.
    expect(system).toMatch(/"patient name is John Smith, DOB March 5 1980"/);
  });
});

// ----------------------------------------------------------------------------
// PASS 2 — executor
// ----------------------------------------------------------------------------
describe('Pass 2 — executor', () => {
  it('uses gpt-4o and receives the parsed intent in the user message', async () => {
    mockCreate.mockResolvedValueOnce(
      intentResponse(highConfidenceIntent({ replacement_text: 'arthur Morgan' }))
    );
    mockCreate.mockResolvedValueOnce(executorResponse('PROCEDURE DESCRIPTION:\narthur Morgan'));

    await processWithAI({
      action: 'edit',
      documentContent: 'PROCEDURE DESCRIPTION:\nold content',
      userMessage: 'replace procedure description with arthur Morgan',
    });

    const pass2Call = mockCreate.mock.calls[1][0];
    expect(pass2Call.model).toBe('gpt-4o');
    expect(pass2Call.max_tokens).toBe(12000);

    const userMsg = (pass2Call.messages as ChatMessage[])
      .find((m) => m.role === 'user')!.content;
    // Structured intent has to appear in the user message so Pass 2 isn't
    // re-parsing intent from prose.
    expect(userMsg).toMatch(/INTENT \(parsed by Pass 1\)/);
    expect(userMsg).toMatch(/operation: replace/);
    expect(userMsg).toMatch(/target_section: "PROCEDURE DESCRIPTION"/);
    expect(userMsg).toMatch(/replacement_text: "arthur Morgan"/);
    expect(userMsg).toMatch(/confidence: high/);
  });

  it('EXECUTOR_PROMPT enforces label retention and verbatim insertion', async () => {
    mockCreate.mockResolvedValueOnce(intentResponse(highConfidenceIntent()));
    mockCreate.mockResolvedValueOnce(executorResponse());

    await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'replace procedure description with arthur Morgan',
    });

    const system = (mockCreate.mock.calls[1][0].messages as ChatMessage[])
      .find((m) => m.role === 'system')!.content;

    // Label retention — the `PROCEDURE DESCRIPTION:` tab must not be deleted.
    expect(system).toMatch(/KEEP THE LABEL LINE/);
    expect(system).toMatch(/NEVER delete the label itself/);
    // Verbatim insertion — the arthur-Morgan failure mode.
    expect(system).toMatch(/insert replacement_text VERBATIM/);
    expect(system).toMatch(/no validation, no judgment, no filtering/);
    // Scope discipline — follow-up / boilerplate paragraphs are part of the
    // section and must be removed on blank/replace/generate.
    expect(system).toMatch(/SCOPE DISCIPLINE/);
    expect(system).toMatch(/intro boilerplate/);
    expect(system).toMatch(/trailing follow-up paragraphs/);
    // Output format — UPDATED_DOC block.
    expect(system).toMatch(/UPDATED_DOC/);
  });

  it('EXECUTOR_PROMPT defines distinct behavior for each operation', async () => {
    mockCreate.mockResolvedValueOnce(intentResponse(highConfidenceIntent()));
    mockCreate.mockResolvedValueOnce(executorResponse());

    await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'replace procedure description with X',
    });

    const system = (mockCreate.mock.calls[1][0].messages as ChatMessage[])
      .find((m) => m.role === 'system')!.content;

    expect(system).toMatch(/operation = "replace"/);
    expect(system).toMatch(/operation = "blank"/);
    expect(system).toMatch(/operation = "generate"/);
    expect(system).toMatch(/operation = "partial_edit"/);
    expect(system).toMatch(/operation = "fill_field"/);
    // Generate rule must say the output is based on existing content, not
    // boilerplate, and not the directive literally inserted.
    expect(system).toMatch(/NOT generic template boilerplate/);
    expect(system).toMatch(/DO NOT insert the directive literally/);
  });
});

// ----------------------------------------------------------------------------
// End-to-end edit flow
// ----------------------------------------------------------------------------
describe('Edit flow — two-pass coordination', () => {
  it('makes exactly two OpenAI calls for a normal edit', async () => {
    mockCreate.mockResolvedValueOnce(intentResponse(highConfidenceIntent()));
    mockCreate.mockResolvedValueOnce(executorResponse());

    await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'replace procedure description with arthur Morgan',
    });

    expect(mockCreate).toHaveBeenCalledTimes(2);
  });

  it('returns combined usage tokens across both passes', async () => {
    mockCreate.mockResolvedValueOnce(intentResponse(highConfidenceIntent()));
    mockCreate.mockResolvedValueOnce(executorResponse());

    const result = await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'replace procedure description with arthur Morgan',
    });

    // Pass 1: 100 + 50 + 150. Pass 2: 2000 + 500 + 2500.
    expect(result.usage).toEqual({
      promptTokens: 2100,
      completionTokens: 550,
      totalTokens: 2650,
    });
  });

  it('exposes the parsed intent on the response for downstream UI / audit', async () => {
    const stub = highConfidenceIntent({ replacement_text: 'arthur Morgan' });
    mockCreate.mockResolvedValueOnce(intentResponse(stub));
    mockCreate.mockResolvedValueOnce(executorResponse());

    const result = await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'replace procedure description with arthur Morgan',
    });

    expect(result.intent).toBeDefined();
    expect(result.intent?.operation).toBe('replace');
    expect(result.intent?.replacement_text).toBe('arthur Morgan');
  });

  it('short-circuits when intent is unclear — no Pass 2 call, user gets a rephrase prompt', async () => {
    mockCreate.mockResolvedValueOnce(
      intentResponse({
        operation: 'unclear',
        target_section: null,
        replacement_text: null,
        directive: null,
        partial_edit_description: null,
        fill_fields: [],
        confidence: 'low',
        reasoning: 'no discernible target',
      })
    );

    const result = await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'hmm do something',
    });

    // Only Pass 1 ran; gpt-4o (Pass 2) was not called — saves cost + avoids
    // silently applying a misinterpretation.
    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(result.text).toMatch(/I'm not sure what you want me to change/);
    expect(result.text).toMatch(/Could you rephrase/);
    // Parser reasoning is surfaced so the doctor knows why it wasn't applied.
    expect(result.text).toMatch(/no discernible target/);
    expect(result.intent?.operation).toBe('unclear');
  });

  it('short-circuits on low confidence even if operation is not "unclear"', async () => {
    // Parser produced a plausible operation but flagged it low-confidence —
    // we still refuse to execute.
    mockCreate.mockResolvedValueOnce(
      intentResponse(highConfidenceIntent({ confidence: 'low', reasoning: 'guessing' }))
    );

    const result = await processWithAI({
      action: 'edit',
      documentContent: 'foo',
      userMessage: 'maybe replace stuff',
    });

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(result.text).toMatch(/Could you rephrase/);
  });
});

// ----------------------------------------------------------------------------
// Non-edit actions — must stay on the single-pass path
// ----------------------------------------------------------------------------
describe('Non-edit actions', () => {
  beforeEach(() => {
    mockCreate.mockResolvedValue({
      choices: [{ message: { content: 'ok' } }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
    });
  });

  it('review action uses gpt-4o-mini with a single call (no two-pass)', async () => {
    await processWithAI({
      action: 'review',
      documentContent: 'foo',
      userMessage: 'look at this',
    });

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(mockCreate.mock.calls[0][0].model).toBe('gpt-4o-mini');
    // No JSON schema output — free-form review response.
    expect(mockCreate.mock.calls[0][0].response_format).toBeUndefined();
  });

  it('chat action uses gpt-4o-mini with a single call (no two-pass)', async () => {
    await processWithAI({
      action: 'chat',
      documentContent: 'foo',
      userMessage: 'hi',
    });

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(mockCreate.mock.calls[0][0].model).toBe('gpt-4o-mini');
  });

  it('extract action uses gpt-4o-mini with a single call (no two-pass)', async () => {
    await processWithAI({
      action: 'extract',
      documentContent: 'foo',
      userMessage: 'pull the fields',
    });

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(mockCreate.mock.calls[0][0].model).toBe('gpt-4o-mini');
  });

  it('SYSTEM_PROMPT for non-edit actions carries the clinical context (brief history examples etc.)', async () => {
    await processWithAI({
      action: 'chat',
      documentContent: 'foo',
      userMessage: 'hi',
    });

    const system = (mockCreate.mock.calls[0][0].messages as ChatMessage[])
      .find((m) => m.role === 'system')!.content;

    expect(system).toMatch(/You are MedDoc/);
    expect(system).toMatch(/CESI.*LESI|LESI.*CESI/);
    expect(system).toMatch(/BRIEF HISTORY EXAMPLES/);
    expect(system).toMatch(/Dr\. Moussazadeh/);
  });
});
