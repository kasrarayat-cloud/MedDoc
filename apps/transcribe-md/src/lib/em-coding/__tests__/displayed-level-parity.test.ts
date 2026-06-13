// ============================================================================
// E/M trigger-parity (2026-06-13, #313 smoke follow-up).
// ----------------------------------------------------------------------------
// The rail (POST /em-score) and the sign gate (suggestion actions →
// emPendingChange) must compute the SAME displayed E/M level, or a
// rail-visible billing-level change can reach a signed note without the
// confirm dialog (silent upcoding). These tests pin the two failure modes
// the #313 smoke exposed — the rxDrafts field-name mismatch and the
// override projection — AND the by-construction property: both surfaces call
// the SAME extractors + the SAME projection, so they cannot diverge.
//
// computeEmScore (the LLM/deterministic engine) is mocked: these tests are
// about which INPUTS each surface feeds it, not the scoring itself.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ computeEmScore: vi.fn() }));
vi.mock('../score', () => ({ computeEmScore: mocks.computeEmScore }));

import {
  extractIcdRows,
  extractRxRows,
  extractEmOverride,
  computeDisplayedEmCode,
} from '../displayed-level';

const CTX = { practiceId: 'p1', visitId: 'v1', userId: 'u1' };

beforeEach(() => {
  vi.clearAllMocks();
  // Engine returns moderate-tier 99214 only when it was handed a non-empty
  // rxDrafts signal — modeling "prescription drug management ⇒ moderate".
  mocks.computeEmScore.mockImplementation(
    async (
      _soap: string,
      opts: { rxDrafts?: Array<unknown>; icdCodes?: Array<unknown> }
    ) => ({
      code:
        (opts.rxDrafts?.length ?? 0) > 0 || (opts.icdCodes?.length ?? 1) >= 2
          ? '99214'
          : '99213',
    })
  );
});

describe('unified rx extractor — the #313 divergence root cause', () => {
  it('reads the worker shape { prescriptions: [...] } (the route used to read only { drafts } → empty)', () => {
    const rows = extractRxRows({
      prescriptions: [{ drug: 'lisinopril', action: 'new' }],
    });
    expect(rows).toEqual([
      { drug: 'lisinopril', drug_name: undefined, action: 'new' },
    ]);
  });

  it('still reads the legacy shape { drafts: [...] }', () => {
    const rows = extractRxRows({ drafts: [{ drug_name: 'metformin' }] });
    expect(rows[0].drug).toBe('metformin');
  });

  it('a visit with prescriptions now scores 99214 on BOTH surfaces (they share this extractor) — no rail/gate split', async () => {
    const signals = {
      icdCodes: null,
      rxDrafts: { prescriptions: [{ drug: 'lisinopril', action: 'new' }] },
      cptCodes: null,
    };
    // Same note text, same signals → the rail and the gate both get the
    // rx signal and both compute 99214. Before the fix the rail read
    // { drafts } (empty → 99213 from note text) while the gate read
    // { prescriptions } (99214) — a silent divergence.
    const code = await computeDisplayedEmCode('any note', signals, CTX);
    expect(code).toBe('99214');
    expect(mocks.computeEmScore.mock.calls[0][1].rxDrafts).toHaveLength(1);
  });
});

describe('unified icd extractor — legacy bare array', () => {
  it('reads a bare array (gate copy used to read only { codes } → empty)', () => {
    expect(extractIcdRows([{ code: 'I10' }, { code: 'E78.5' }])).toEqual([
      { code: 'I10', description: undefined },
      { code: 'E78.5', description: undefined },
    ]);
  });
  it('reads { codes: [...] }', () => {
    expect(extractIcdRows({ codes: [{ code: 'I10' }] })).toEqual([
      { code: 'I10', description: undefined },
    ]);
  });
});

describe('override projection — the displayed code, not the raw engine code', () => {
  it('a doctor override pins the displayed code regardless of the engine tier', async () => {
    const signals = {
      icdCodes: { codes: [{ code: 'I10' }, { code: 'E78.5' }] }, // engine→99214
      rxDrafts: null,
      cptCodes: { em: { override: { code: '99212', overriddenAt: 'x' } } },
    };
    // Engine would say 99214; the doctor overrode to 99212. The rail shows
    // 99212; the gate must too (else it false-prompts).
    expect(await computeDisplayedEmCode('note', signals, CTX)).toBe('99212');
  });

  it('extractEmOverride returns the code, or undefined when absent/malformed', () => {
    expect(extractEmOverride({ em: { override: { code: '99215' } } })?.code).toBe(
      '99215'
    );
    expect(extractEmOverride(null)).toBeUndefined();
    expect(extractEmOverride({ em: {} })).toBeUndefined();
    expect(extractEmOverride({ em: { override: { reason: 'x' } } })).toBeUndefined();
  });
});

describe('by construction — the gate computes from the same function the rail displays', () => {
  it('computeDisplayedEmCode is the single projection; identical inputs → identical code (a divergence is impossible)', async () => {
    const signals = {
      icdCodes: null,
      rxDrafts: { prescriptions: [{ drug: 'amlodipine', action: 'increase' }] },
      cptCodes: null,
    };
    const a = await computeDisplayedEmCode('note v1', signals, CTX);
    const b = await computeDisplayedEmCode('note v1', signals, CTX);
    expect(a).toBe(b);
    // Both calls fed the engine the SAME extracted rx rows.
    const [c1, c2] = mocks.computeEmScore.mock.calls;
    expect(c1[1].rxDrafts).toEqual(c2[1].rxDrafts);
  });
});
