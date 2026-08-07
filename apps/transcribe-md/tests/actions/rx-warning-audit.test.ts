// ============================================================================
// recordOverride — warningId + severity correlation guard
// ----------------------------------------------------------------------------
// fix/rx-override-gate-correlation: the override-count-inflation bypass let a
// visit owner mint fabricated 'critical' override rows (bogus warningIds) to
// satisfy the sign-gate's bare count. recordOverride now resolves the submitted
// warningId against the visit's persisted rxDrafts.warnings[] and rejects:
//   - a warningId that matches NO real warning (malformed / out-of-range), and
//   - a severity that doesn't match the warning's server-derived severity.
// Client-supplied warning identity is never trusted verbatim into the audit
// row. This pins that contract; the per-warning sign-gate coverage check is
// proven end-to-end in e2e scenario 25.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  visitFindUnique: vi.fn(),
  overrideCreate: vi.fn(),
  overrideFindUnique: vi.fn(),
  getSession: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    // T5: the read is practice-scoped now, so it uses findFirst (findUnique
    // cannot carry a non-unique predicate). Same mock, same rows.
    transcribeVisit: { findUnique: mocks.visitFindUnique, findFirst: mocks.visitFindUnique },
    rxWarningOverride: {
      create: mocks.overrideCreate,
      findUnique: mocks.overrideFindUnique,
    },
  },
}));
vi.mock('@/lib/auth', () => ({ getSession: mocks.getSession }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
// NB: '@/lib/rx-warnings' is intentionally NOT mocked — the real, pure
// derivation must run so the validation is exercised for real.

import { recordOverride, type RecordOverrideInput } from '@/lib/rx-warning-audit';

const USER = 'doc-1';
const VISIT = 'vis-1';

// rxDrafts.warnings[] fixture: index 0 = critical (id rx-warning-0),
// index 1 = minor → rail 'info' (id rx-warning-1).
const RX_DRAFTS = {
  warnings: [
    { severity: 'critical', rx_drug: 'warfarin', message: 'INR risk' },
    { severity: 'minor', rx_drug: 'ibuprofen', message: 'verify dose' },
  ],
};

const REASON = 'Reviewed with the patient; benefit outweighs the risk, will monitor closely.';

function input(overrides: Partial<RecordOverrideInput>): RecordOverrideInput {
  return {
    visitId: VISIT,
    warningId: 'rx-warning-0',
    rxLineNumber: 1,
    severity: 'critical',
    headline: 'warfarin',
    reason: REASON,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  // getSession() never returns a session without a practice — it fails closed
  // rather than hand back one the accessor refuses. The fixture matches.
  mocks.getSession.mockResolvedValue({ user: { id: USER, practiceId: 'prac_1' } });
  mocks.visitFindUnique.mockResolvedValue({ userId: USER, rxDrafts: RX_DRAFTS });
  mocks.overrideCreate.mockResolvedValue({ id: 'ovr-1' });
  mocks.logAudit.mockResolvedValue(undefined);
});

describe('recordOverride — correlation guard (fix/rx-override-gate-correlation)', () => {
  it('accepts a genuine override of the real critical warning', async () => {
    const result = await recordOverride(input({ warningId: 'rx-warning-0', severity: 'critical' }));
    expect(result.ok).toBe(true);
    expect(mocks.overrideCreate).toHaveBeenCalledTimes(1);
    expect(mocks.overrideCreate.mock.calls[0][0].data.severity).toBe('critical');
    expect(mocks.overrideCreate.mock.calls[0][0].data.warningId).toBe('rx-warning-0');
  });

  it('accepts a non-critical override when the severity matches (minor → info)', async () => {
    const result = await recordOverride(input({ warningId: 'rx-warning-1', severity: 'info' }));
    expect(result.ok).toBe(true);
    expect(mocks.overrideCreate).toHaveBeenCalledTimes(1);
  });

  it('REJECTS a malformed/fabricated warningId (matches no real warning) and writes nothing', async () => {
    const result = await recordOverride(input({ warningId: 'totally-bogus' }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/not on this visit/i);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it('REJECTS an out-of-range positional warningId (no such warning) and writes nothing', async () => {
    const result = await recordOverride(input({ warningId: 'rx-warning-9999' }));
    expect(result.ok).toBe(false);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it('REJECTS a severity that lies about a real warning (minor claimed critical) — kills inflation', async () => {
    // index 1 is a MINOR warning (rail 'info'); claiming 'critical' would mint a
    // gate-counting row for a non-critical warning. Must be rejected.
    const result = await recordOverride(input({ warningId: 'rx-warning-1', severity: 'critical' }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toMatch(/severity/i);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  // ⚠️ REWRITTEN FOR T6 — this asserted OWNERSHIP ("a non-owner is rejected"),
  // which §4.1b retired: a colleague in the same practice may legitimately
  // resolve an Rx warning on a shared chart, because only SIGNING is
  // role-gated. What must still be refused is a visit in ANOTHER PRACTICE, and
  // that is enforced by the query's practice predicate rather than by a branch
  // — so the row simply does not come back.
  it('still refuses when the visit is not in the caller\'s practice', async () => {
    mocks.visitFindUnique.mockResolvedValueOnce(null);
    const result = await recordOverride(input({}));
    expect(result.ok).toBe(false);
    expect(mocks.overrideCreate).not.toHaveBeenCalled();
  });

  it('a COLLEAGUE in the same practice may now resolve the warning', async () => {
    // The positive half — without it the change above is only a deletion, and
    // nothing proves the widening actually happened.
    mocks.visitFindUnique.mockResolvedValueOnce({ userId: 'a-colleague', rxDrafts: RX_DRAFTS });
    const result = await recordOverride(input({}));
    expect(result.ok, 'a same-practice colleague was refused').toBe(true);
    expect(mocks.overrideCreate).toHaveBeenCalled();
  });
});
