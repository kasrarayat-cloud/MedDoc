// ============================================================================
// llm-mdm.ts unit tests (Phase 5.2)
// ----------------------------------------------------------------------------
// Tests cache key derivation, drift detection, and the JSON
// validation path. Does NOT exercise a live model — llm-mdm calls the
// raw @anthropic-ai/sdk directly (to attach cache_control), so the
// warm/drift/fallback paths mock '@anthropic-ai/sdk' (messages.create)
// and stub a dummy ANTHROPIC_API_KEY so getAnthropicClient() resolves.
// ============================================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// File-level mock (hoisted; survives vi.resetModules): keep @meddoc/ai REAL
// except the two fire-and-forget telemetry sinks. With them real, every
// judgeMdm test fires `void prisma.aiCall.create().catch(console.error)`
// against a non-existent DB — the rejection can settle AFTER afterEach
// restores the console, landing in vitest worker teardown as
// "EnvironmentTeardownError: Closing rpc while onUserConsoleLog was
// pending" (the PR #304 CI flake; all tests green, exit 1). No-op the
// sinks so the async chain never exists.
vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    logAiCall: () => undefined,
    logApiUsage: () => undefined,
  };
});

import {
  buildCacheKey,
  charDistanceRatio,
  normalizeSoap,
  validateMdmJudgement,
  judgeMdm,
} from '../llm-mdm';
import type { MdmJudgement } from '../types';

describe('normalizeSoap', () => {
  it('collapses whitespace, lowercases, strips line numbers', () => {
    const a = '## Subjective\n1.  Patient reports COUGH';
    const b = 'Patient reports cough';
    expect(normalizeSoap(a).includes('patient reports cough')).toBe(true);
  });

  it('produces the same key for cosmetically-different bodies', () => {
    const a = 'Patient reports COUGH × 3 days.';
    const b = 'patient reports cough × 3 days.';
    expect(normalizeSoap(a)).toBe(normalizeSoap(b));
  });
});

describe('buildCacheKey', () => {
  it('returns a stable em_mdm_cache:<sha256> key', () => {
    const k1 = buildCacheKey('Patient reports cough.');
    const k2 = buildCacheKey('patient reports COUGH.');
    expect(k1).toBe(k2);
    expect(k1.startsWith('em_mdm_cache:')).toBe(true);
    expect(k1.length).toBe('em_mdm_cache:'.length + 64);
  });
});

describe('charDistanceRatio', () => {
  it('returns 0 for identical normalized bodies', () => {
    expect(charDistanceRatio('hello', 'hello')).toBe(0);
  });
  it('returns >0.20 for substantially different bodies (>20% drift)', () => {
    const a = 'Patient reports cough × 3 days. No fever.';
    const b = 'Patient reports SEVERE cough with fever, dyspnea, pneumonia symptoms over a long period of time spanning 2 weeks now';
    expect(charDistanceRatio(a, b)).toBeGreaterThan(0.20);
  });
  it('returns small value for minor edits', () => {
    const a = 'Patient reports cough × 3 days.';
    const b = 'Patient reports cough × 4 days.';
    expect(charDistanceRatio(a, b)).toBeLessThan(0.10);
  });
});

describe('validateMdmJudgement', () => {
  const valid: MdmJudgement = {
    tier: 'low',
    elements: {
      problems: { level: 'low', summary: 'one acute uncomplicated' },
      data: { level: 'low', summary: 'UA in office' },
      risk: { level: 'moderate', summary: 'Rx mgmt' },
    },
    confidence: 0.91,
    rationale: '2-of-3 → low.',
  };

  it('accepts a well-shaped judgement', () => {
    expect(validateMdmJudgement(valid)).not.toBeNull();
  });

  it('rejects missing tier', () => {
    const bad: any = { ...valid };
    delete bad.tier;
    expect(validateMdmJudgement(bad)).toBeNull();
  });

  it('rejects out-of-range confidence', () => {
    const bad = { ...valid, confidence: 1.5 };
    expect(validateMdmJudgement(bad)).toBeNull();
  });

  it('rejects unknown tier value', () => {
    const bad = { ...valid, tier: 'nuclear' };
    expect(validateMdmJudgement(bad)).toBeNull();
  });

  it('rejects element with non-string summary', () => {
    const bad: any = { ...valid };
    bad.elements = { ...valid.elements, problems: { level: 'low', summary: 42 } };
    expect(validateMdmJudgement(bad)).toBeNull();
  });
});

// Silence the expected console noise these tests produce (the fallback
// path's "llm call failed" warn + fire-and-forget logAiCall/logApiUsage
// prisma errors with no DB). Beyond tidiness this is load-bearing on CI:
// pending onUserConsoleLog RPCs at worker teardown intermittently raise
// "EnvironmentTeardownError: Closing rpc while onUserConsoleLog was
// pending" → vitest exits 1 with all tests green (seen on PR #304).
// Same pattern as edit-tracking.test.ts.
function silenceExpectedConsole() {
  vi.spyOn(console, 'info').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'log').mockImplementation(() => {});
}

describe('judgeMdm — cache warm path', () => {
  beforeEach(() => {
    vi.resetModules();
    silenceExpectedConsole();
    process.env.ANTHROPIC_API_KEY = 'test-key-not-used-network-mocked';
  });
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.ANTHROPIC_API_KEY;
  });

  it('cold call → LLM hit → store cached; warm call → cache hit, no LLM', async () => {
    const store = new Map<string, string>();
    let llmCallCount = 0;
    const fakeJudgement: MdmJudgement = {
      tier: 'low',
      elements: {
        problems: { level: 'low', summary: 'x' },
        data: { level: 'low', summary: 'x' },
        risk: { level: 'minimal', summary: 'x' },
      },
      confidence: 0.85,
      rationale: 'unit-test',
    };
    vi.doMock('@anthropic-ai/sdk', () => ({
      default: class {
        messages = {
          create: async () => {
            llmCallCount++;
            return {
              content: [{ type: 'text', text: JSON.stringify(fakeJudgement) }],
              usage: {
                input_tokens: 10,
                output_tokens: 20,
                cache_read_input_tokens: 0,
                cache_creation_input_tokens: 0,
              },
            };
          },
        };
      },
    }));
    vi.doMock('@/lib/redis', () => ({
      getRedis: () => ({
        get: async (k: string) => store.get(k) ?? null,
        set: async (k: string, v: string) => { store.set(k, v); return 'OK'; },
      }),
      isRedisReady: () => true,
    }));
    const mod = await import('../llm-mdm');

    const args = {
      soap: '## Subjective\n34F with stable HTN.\n## Plan\nContinue lisinopril.',
      practiceId: 'p1',
      visitId: 'v1',
      icdCodes: [{ code: 'I10' }],
      rxDrafts: [],
    };

    // Cold.
    const r1 = await mod.judgeMdm(args);
    expect(r1.cacheHit).toBe(false);
    expect(r1.llmJudged).toBe(true);
    expect(llmCallCount).toBe(1);

    // Warm — same SOAP body, should hit cache.
    const r2 = await mod.judgeMdm(args);
    expect(r2.cacheHit).toBe(true);
    expect(r2.llmJudged).toBe(true);
    expect(llmCallCount).toBe(1); // no second LLM call
  });

  it('drift >20% bypasses cache and forces re-judge', async () => {
    const store = new Map<string, string>();
    let llmCallCount = 0;
    const fakeJudgement: MdmJudgement = {
      tier: 'moderate',
      elements: {
        problems: { level: 'moderate', summary: 'x' },
        data: { level: 'moderate', summary: 'x' },
        risk: { level: 'moderate', summary: 'x' },
      },
      confidence: 0.85,
      rationale: 'unit-test',
    };
    vi.doMock('@anthropic-ai/sdk', () => ({
      default: class {
        messages = {
          create: async () => {
            llmCallCount++;
            return {
              content: [{ type: 'text', text: JSON.stringify(fakeJudgement) }],
              usage: {
                input_tokens: 10,
                output_tokens: 20,
                cache_read_input_tokens: 0,
                cache_creation_input_tokens: 0,
              },
            };
          },
        };
      },
    }));
    vi.doMock('@/lib/redis', () => ({
      getRedis: () => ({
        get: async (k: string) => store.get(k) ?? null,
        set: async (k: string, v: string) => { store.set(k, v); return 'OK'; },
      }),
      isRedisReady: () => true,
    }));
    const mod = await import('../llm-mdm');

    const oldSoap = '## Subjective\n34F with stable HTN.\n## Plan\nContinue lisinopril.';
    const newSoap = '## Subjective\n34F with NEW chest pain, dyspnea, palpitations, exacerbation, decompensated CHF, multiple problems requiring intensive workup, ekg, troponin, BNP, CXR, ASA, hospitalization decision pending. \n## Plan\nUrgent stress test, started ASA, decision-not-to-hospitalize.';

    // Cold call with old soap.
    await mod.judgeMdm({ soap: oldSoap, practiceId: 'p1', icdCodes: [{ code: 'I10' }] });
    expect(llmCallCount).toBe(1);
    // Warm call with NEW soap and priorSoap=oldSoap → drift >20% → re-judge.
    const r2 = await mod.judgeMdm({
      soap: newSoap,
      practiceId: 'p1',
      icdCodes: [{ code: 'I10' }],
      priorSoap: oldSoap,
    });
    expect(r2.cacheHit).toBe(false);
    expect(llmCallCount).toBe(2); // re-judged on drift
  });
});

describe('judgeMdm — fallback path', () => {
  beforeEach(() => {
    vi.resetModules();
    silenceExpectedConsole();
    process.env.ANTHROPIC_API_KEY = 'test-key-not-used-network-mocked';
  });
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.ANTHROPIC_API_KEY;
  });

  it('falls back to deterministicMdm with llmJudged:false on LLM error', async () => {
    // Mock the raw SDK to throw a 5xx-like error on every attempt.
    vi.doMock('@anthropic-ai/sdk', () => ({
      default: class {
        messages = {
          create: () => Promise.reject(new Error('Anthropic 503')),
        };
      },
    }));
    // Mock redis to skip cache (so we go straight to the LLM call).
    vi.doMock('@/lib/redis', () => ({
      getRedis: () => ({ get: () => Promise.resolve(null), set: () => Promise.resolve('OK') }),
      isRedisReady: () => false,
    }));
    const mod = await import('../llm-mdm');
    const result = await mod.judgeMdm({
      soap: '## Subjective\n34F with cough × 3d.\n## Plan\nOTC tx.',
      practiceId: 'test-prac',
      visitId: 'test-vid',
      icdCodes: [{ code: 'J06.9' }],
      rxDrafts: [],
    });
    expect(result.llmJudged).toBe(false);
    expect(result.cacheHit).toBe(false);
    // Fallback judgement should still be a well-shaped MdmJudgement.
    expect(['straightforward', 'low', 'moderate', 'high']).toContain(
      result.judgement.tier,
    );
    expect(result.judgement.rationale).toMatch(/Deterministic fallback/);
  });
});
