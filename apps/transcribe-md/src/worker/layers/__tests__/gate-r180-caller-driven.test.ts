// ============================================================================
// GATE — #180's CALLER IS DRIVEN, not merely name-checked
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THE ADVERSARIAL PASS BROKE THE PREVIOUS ANSWER.
//
// The first mutation proof found that collapsing the split in `07a` redded
// nothing, because the gate REPRODUCED the classification in a local helper —
// a copy witnessing itself. The fix was to export `classifyAllowlistRefusals`
// and have the gate drive the shipped function. **The pass then showed that fix
// moved the problem up one level rather than closing it:** the gate drove the
// exported FUNCTION, and nothing drove or asserted the CALLER. Demonstrated —
//
//   · replace the `classifyAllowlistRefusals(...)` call with an inline
//     `rejectedNotCodes = rejected.map(r => r.code)` and no classification
//     -> every category-header refusal ships as `not_in_verified_allowlist`
//        with no children, #180's entire product silently reverted
//   · or keep the call and pass `children: []`
//     -> the doctor gets the ACTIONABLE "bill one of these" card with an
//        EMPTY list, which is worse than the pre-#180 status quo
//
// Both were GREEN on all 54 assertions, on every ICD suite (377), and on
// `tsc`. The only guard was a source regex over variable NAMES.
//
// So this drives `runLayer7aIcdCoding` end to end with the REAL allowlist and
// asserts what actually reaches the stored blob. A source assertion cannot
// substitute for executing the path.
// ============================================================================

import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelComplete: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

// ⚠️ `isValidIcd10` / `isIcd10Header` / `billableDescendantsOf` are LEFT REAL.
// The sibling fallback suite mocks `isValidIcd10` for its own purpose; doing so
// here would make this gate assert a classification against a stub, which is
// the defect it exists to catch one layer down.
vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: mocks.modelComplete } };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runLayer7aIcdCoding } from '../07a-icd-coding';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({});
  mocks.logAudit.mockResolvedValue(undefined);
});
afterEach(() => vi.restoreAllMocks());

const baseInput = {
  visitId: 'cmp_r180',
  practiceId: 'prac_r180',
  userId: 'user_r180',
  specialty: 'family-medicine',
  soapFinal: '## Assessment\nLow back pain. Also an unparseable code.',
  entitiesJson: '{}',
};

const code = (c: string) => ({
  code: c,
  description: 'd',
  evidence_quote: 'low back pain',
  confidence: 0.9,
  confidenceLevel: 'high' as const,
});

/** The blob the layer actually persisted. */
function storedBlob() {
  const call = mocks.prismaUpdate.mock.calls.find(([a]) => a?.data?.icdCodes);
  expect(call, 'the layer must persist an icdCodes blob').toBeTruthy();
  return call![0].data.icdCodes as {
    codes: unknown[];
    dropped: Array<{ code: string; reason: string; children?: string[] }>;
  };
}

describe('#180 — the split reaches the STORED BLOB, driven through the real layer', () => {
  it('a header and a fabrication are persisted with DIFFERENT tokens', async () => {
    // M54.5 is a real FY2026 header (not submittable). K58.3 is not a code at
    // all — "Other IBS" is K58.8. I10 is billable and must survive.
    mocks.modelComplete.mockResolvedValueOnce({
      codes: [code('I10'), code('M54.5'), code('K58.3')],
    });

    await runLayer7aIcdCoding(baseInput);
    const blob = storedBlob();
    const byCode = new Map(blob.dropped.map((d) => [d.code, d]));

    expect(byCode.get('M54.5')?.reason).toBe('header_use_billable_child');
    expect(byCode.get('K58.3')?.reason).toBe('not_in_verified_allowlist');
    // the actionable case carries its substitutes, all the way to storage
    expect(byCode.get('M54.5')?.children).toEqual(['M54.50', 'M54.51', 'M54.59']);
    // the fabrication carries none — there is nothing to offer
    expect(byCode.get('K58.3')?.children).toBeUndefined();
    // and the valid code is NOT dropped
    expect(byCode.has('I10')).toBe(false);
  });

  it('⚠️ a header NEVER reaches storage with an empty substitute list', async () => {
    // The second mutation the pass found green: the token says "bill one of
    // these" and the list is empty. Worse than the pre-#180 status quo, because
    // it promises an answer and shows none.
    mocks.modelComplete.mockResolvedValueOnce({
      codes: [code('M54.5'), code('K21.0'), code('Z83.71')],
    });

    await runLayer7aIcdCoding(baseInput);
    const headers = storedBlob().dropped.filter(
      (d) => d.reason === 'header_use_billable_child',
    );
    expect(headers.length, 'all three are headers').toBe(3);
    for (const h of headers) {
      expect(h.children, `${h.code} must carry substitutes`).toBeDefined();
      expect(h.children!.length, `${h.code} must not be empty`).toBeGreaterThan(0);
    }
  });

  it('the classifier is REACHED — a header is never stored as a fabrication', async () => {
    // The first mutation: drop the call, everything ships as the old token.
    mocks.modelComplete.mockResolvedValueOnce({ codes: [code('M54.5')] });
    await runLayer7aIcdCoding(baseInput);
    const dropped = storedBlob().dropped;
    expect(dropped).toHaveLength(1);
    expect(dropped[0].reason).not.toBe('not_in_verified_allowlist');
    expect(dropped[0].reason).toBe('header_use_billable_child');
  });
});
