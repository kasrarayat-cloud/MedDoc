// ============================================================================
// Suggestions-lane server actions (hybrid anchored generation, 2026-06-11).
// prisma + auth + audit mocked; the append/filter logic is REAL. Pins the
// load-bearing invariants:
//   - adopt APPENDS the claim text VERBATIM under its section heading (else
//     at the end of the note), filters the claim out of suggestedClaims, and
//     bumps soapVersion in ONE version-gated update (optimistic concurrency)
//   - the audit metadata is PHI-SAFE: key-set EXACTLY {reason, remaining,
//     section} — never the claim text
//   - dismiss filters + audits but NEVER touches soapFinal / soapVersion
//   - emptying the lane writes SQL NULL (Prisma.DbNull), not []
//   - bad index / malformed jsonb / SIGNED / not-owned / version conflict
//     → { ok:false } with NO write (and, where applicable, NO audit row)
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/db', () => {
  const transcribeVisit = {
    findUnique: mocks.findUnique,
    update: mocks.update,
    updateMany: mocks.updateMany,
  };
  const prisma = { transcribeVisit };
  return { default: prisma, prisma };
});
vi.mock('@/lib/auth', () => ({ requireSession: mocks.requireSession }));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));
vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import { Prisma, TranscribeVisitStatus } from '@prisma/client';

import {
  adoptSuggestionAction,
  dismissSuggestionAction,
} from '../suggestion-actions';

const DOCTOR = 'doc1';
const VISIT = 'visit-1';

const SOAP = [
  '## Subjective',
  'Reports right elbow pain for two weeks.',
  '',
  '## Objective',
  'Swelling over the olecranon.',
  '',
  '## Plan',
  'Rest and NSAIDs.',
].join('\n');

const CLAIMS = [
  {
    text: 'No prior diagnosis of migraines.',
    reason: 'not_entailed',
    section: 'Subjective',
    anchor: 'had migraines in the past? No.',
  },
  {
    text: 'Ice packs recommended twice daily.',
    reason: 'no_anchor',
    section: 'Plan',
    anchor: 'no anchor',
  },
];

/** Text of CLAIMS[i] — the content-identity check both actions now require. */
const claimsAt = (i: number) => CLAIMS[i].text;

function visitRow(over: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    userId: DOCTOR,
    status: TranscribeVisitStatus.READY,
    deletedAt: null,
    archivedAt: null,
    soapFinal: SOAP,
    soapVersion: 3,
    suggestedClaims: CLAIMS,
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: DOCTOR, practiceId: 'p1', email: 'doc@test.dev' },
  });
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.update.mockResolvedValue({ id: VISIT });
});

describe('adoptSuggestionAction — append + filter + version bump', () => {
  it('appends the claim text verbatim INSIDE its section heading block', async () => {
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(r.soapVersion).toBe(4);

    const args = mocks.updateMany.mock.calls[0][0];
    // ONE atomic update, gated on the soapVersion read in this request.
    expect(args.where).toEqual({ id: VISIT, soapVersion: 3 });
    expect(args.data.soapVersion).toEqual({ increment: 1 });

    const newSoap: string = args.data.soapFinal;
    expect(r.soapFinal).toBe(newSoap);
    // Verbatim — and NO trailing "[adopted from AI suggestion]" label;
    // the audit row is the record.
    expect(newSoap).toContain('No prior diagnosis of migraines.');
    expect(newSoap).not.toMatch(/adopted from/i);
    // Inserted under ## Subjective, before ## Objective.
    const claimAt = newSoap.indexOf('No prior diagnosis of migraines.');
    expect(claimAt).toBeGreaterThan(newSoap.indexOf('## Subjective'));
    expect(claimAt).toBeLessThan(newSoap.indexOf('## Objective'));

    // The adopted claim is filtered OUT of the persisted array.
    expect(args.data.suggestedClaims).toEqual([CLAIMS[1]]);
    expect(r.suggestedClaims).toEqual([CLAIMS[1]]);
  });

  it('appends at the END of the note when the section heading is absent', async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        suggestedClaims: [
          { text: 'Entire-note fallback claim.', reason: 'verifier_failed', section: '(entire note)', anchor: 'no anchor' },
        ],
      })
    );
    const r = await adoptSuggestionAction(VISIT, 0, 'Entire-note fallback claim.');
    expect(r.ok).toBe(true);
    const newSoap: string = mocks.updateMany.mock.calls[0][0].data.soapFinal;
    expect(newSoap.trimEnd().endsWith('Entire-note fallback claim.')).toBe(true);
  });

  it('adopting the LAST claim writes SQL NULL (Prisma.DbNull), not []', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ suggestedClaims: [CLAIMS[0]] }));
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(mocks.updateMany.mock.calls[0][0].data.suggestedClaims).toBe(Prisma.DbNull);
    expect(r.suggestedClaims).toBeNull();
  });

  it('audits SUGGESTION_ADOPTED with PHI-safe metadata — key-set EXACTLY {reason, remaining, section}', async () => {
    await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const call = mocks.logAudit.mock.calls[0][0];
    expect(call.action).toBe('SUGGESTION_ADOPTED');
    expect(call.targetId).toBe(VISIT);
    expect(Object.keys(call.metadata).sort()).toEqual(['reason', 'remaining', 'section']);
    expect(call.metadata).toEqual({ section: 'Subjective', reason: 'not_entailed', remaining: 1 });
    // Belt: the claim text must never reach the audit row in any field.
    expect(JSON.stringify(call)).not.toContain('No prior diagnosis of migraines');
  });

  it('bad index → { ok:false }, no write, no audit', async () => {
    for (const idx of [99, -1, 1.5]) {
      const r = await adoptSuggestionAction(VISIT, idx, 'whatever');
      expect(r.ok).toBe(false);
    }
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('malformed suggestedClaims jsonb (strict parse) → { ok:false }, no write', async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ suggestedClaims: [{ reason: 'no_anchor', section: 'Plan', anchor: 'no anchor' }] })
    );
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it('SIGNED visit → { ok:false }, no write (read-only after signing)', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ status: TranscribeVisitStatus.SIGNED }));
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('not-owned visit → { ok:false }, no write', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ userId: 'someone-else' }));
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it('version conflict (updateMany count=0) → { ok:false }, no audit', async () => {
    mocks.updateMany.mockResolvedValue({ count: 0 });
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe('dismissSuggestionAction — filter only, never the note', () => {
  it('filters the claim, audits SUGGESTION_DISMISSED, and NEVER touches soapFinal/soapVersion', async () => {
    const r = await dismissSuggestionAction(VISIT, 1, claimsAt(1));
    expect(r.ok).toBe(true);
    expect(r.suggestedClaims).toEqual([CLAIMS[0]]);

    expect(mocks.updateMany).not.toHaveBeenCalled();
    const args = mocks.update.mock.calls[0][0];
    expect(args.where).toEqual({ id: VISIT });
    expect(args.data.suggestedClaims).toEqual([CLAIMS[0]]);
    expect('soapFinal' in args.data).toBe(false);
    expect('soapVersion' in args.data).toBe(false);

    const call = mocks.logAudit.mock.calls[0][0];
    expect(call.action).toBe('SUGGESTION_DISMISSED');
    expect(Object.keys(call.metadata).sort()).toEqual(['reason', 'remaining', 'section']);
    expect(call.metadata).toEqual({ section: 'Plan', reason: 'no_anchor', remaining: 1 });
    expect(JSON.stringify(call)).not.toContain('Ice packs recommended');
  });

  it('dismissing the LAST claim writes SQL NULL (Prisma.DbNull)', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ suggestedClaims: [CLAIMS[1]] }));
    const r = await dismissSuggestionAction(VISIT, 0, claimsAt(1));
    expect(r.ok).toBe(true);
    expect(mocks.update.mock.calls[0][0].data.suggestedClaims).toBe(Prisma.DbNull);
    expect(r.suggestedClaims).toBeNull();
  });

  it('bad index → { ok:false }, no write, no audit', async () => {
    const r = await dismissSuggestionAction(VISIT, 7, 'whatever');
    expect(r.ok).toBe(false);
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('SIGNED visit → { ok:false }, no write', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ status: TranscribeVisitStatus.SIGNED }));
    const r = await dismissSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.update).not.toHaveBeenCalled();
  });
});

describe('cross-tab index drift — content-identity check', () => {
  // The DB lane was re-indexed by another tab (e.g. its claim 0 was
  // dismissed); this tab still renders the OLD array and acts on "index 0"
  // expecting the old claim's text. Both actions must refuse — adopting or
  // dismissing the WRONG claim is the failure mode (auditor WARN-1).
  it('adopt with stale text at the index → { ok:false }, no write, no audit', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ suggestedClaims: [CLAIMS[1]] }));
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/another tab/i);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('dismiss with stale text at the index → { ok:false }, no write, no audit', async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ suggestedClaims: [CLAIMS[1]] }));
    const r = await dismissSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/another tab/i);
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it('empty expectedText fails input validation', async () => {
    const r = await adoptSuggestionAction(VISIT, 0, '');
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});
