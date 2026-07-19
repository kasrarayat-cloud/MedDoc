import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    logAiCall: () => undefined,
    logApiUsage: () => undefined,
  };
});

describe('judgeMdm — explicit synthetic provider boundary', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    delete process.env.MOCK_AI_CALLS;
    delete process.env.ANTHROPIC_API_KEY;
  });

  it('uses deterministic MDM without constructing an Anthropic client', async () => {
    process.env.MOCK_AI_CALLS = 'true';
    process.env.ANTHROPIC_API_KEY = 'synthetic-key-must-not-be-used';
    const constructor = vi.fn();
    vi.doMock('@anthropic-ai/sdk', () => ({
      default: class {
        constructor() {
          constructor();
          throw new Error('synthetic QA must not construct a live provider');
        }
      },
    }));

    const mod = await import('../llm-mdm');
    const result = await mod.judgeMdm({
      soap: 'Synthetic follow-up with no patient data.',
      practiceId: 'practice-synthetic-qa',
      visitId: 'visit-synthetic-qa',
      icdCodes: [{ code: 'Z00.00' }],
      rxDrafts: [],
    });

    expect(result.llmJudged).toBe(false);
    expect(result.cacheHit).toBe(false);
    expect(constructor).not.toHaveBeenCalled();
  });
});
