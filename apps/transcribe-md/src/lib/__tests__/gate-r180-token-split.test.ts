// ============================================================================
// GATE — RULING #180: the allowlist exit's reason SPLITS in two
// ----------------------------------------------------------------------------
// A header refusal and a fabrication refusal are different things to tell a
// doctor. One is ACTIONABLE — bill a billable child, and one always exists —
// the other has nothing to offer. Before #180 both carried
// `not_in_verified_allowlist` and the surface said the same sentence for each.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · the two sub-reasons collapse back to one    -> the classification block
//   · a header record ships without its children  -> the children block
//   · a fabrication acquires children             -> the children block
//   · #149(b)'s four exits stop being distinct    -> the exits block
//   · a header drop stops being doctor-visible    -> the amber block
//   · prose rides in through `children`           -> the posture block
// ============================================================================

import { describe, it, expect, vi } from 'vitest';

// 07a imports prisma and the audit helper at module level, and the audit helper
// pulls in next-auth. Stub ONLY those two: `@meddoc/ai` is left REAL on purpose,
// because the real allowlist is what the classification is being tested against.
vi.mock('@meddoc/db', () => ({ default: { transcribeVisit: { update: vi.fn() } } }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));
import {
  buildIcdDropRecords,
  readIcdDrops,
  amberIcdDrops,
  icdDropCountsByReason,
  ICD_DROP_REASONS,
  type IcdDropInputs,
} from '../icd-drops';
import { isIcd10Header, isValidIcd10, billableDescendantsOf } from '@meddoc/ai';
// ⚠️ THE REAL CLASSIFIER, IMPORTED — NOT A LOCAL COPY. The first draft of this
// gate reproduced the classification in a helper here, so collapsing the split
// in 07a redded NOTHING: the gate was witnessing its own copy. Driving the
// shipped function is what makes arm 1 of the mutation proof able to fire.
import { classifyAllowlistRefusals } from '../../worker/layers/07a-icd-coding';

const NONE: IcdDropInputs = {
  notInVerifiedAllowlist: [],
  headerUseBillableChild: [],
  incoherentVaricose: [],
  contradictedByDenial: [],
  unsupportedDeficiency: [],
  survivors: [],
};

/** The SHIPPED classifier, under its old local name. */
const classify = classifyAllowlistRefusals;

describe('#180 — the two sub-reasons are distinguishable', () => {
  it('a HEADER and a FABRICATION no longer carry the same token', () => {
    // Both fail isValidIcd10, both leave through the SAME exit. That is what
    // made them one token, and it is exactly what #180 changes.
    expect(isValidIcd10('M54.5')).toBe(false);
    expect(isValidIcd10('K58.3')).toBe(false);
    expect(isIcd10Header('M54.5')).toBe(true);
    expect(isIcd10Header('K58.3')).toBe(false);

    const { headers, notCodes } = classify(['M54.5', 'K58.3']);
    const out = buildIcdDropRecords({
      ...NONE,
      headerUseBillableChild: headers,
      notInVerifiedAllowlist: notCodes,
    });
    const byCode = new Map(out.map((d) => [d.code, d.reason]));
    expect(byCode.get('M54.5')).toBe('header_use_billable_child');
    expect(byCode.get('K58.3')).toBe('not_in_verified_allowlist');
    // the whole point: two inputs, two different tokens
    expect(new Set(byCode.values()).size).toBe(2);
  });

  it('the classification is TOTAL — every refused code lands in exactly one bucket', () => {
    const refused = ['M54.5', 'K58.3', 'Z83.71', 'I83.810', 'K21.0', 'Z99.999', 'S82.62X'];
    const { headers, notCodes } = classify(refused);
    expect(headers.length + notCodes.length).toBe(refused.length);
    const overlap = headers.map((h) => h.code).filter((c) => notCodes.includes(c));
    expect(overlap).toEqual([]);
    // and it partitions the way CMS says, not the way we hope
    expect(headers.map((h) => h.code).sort()).toEqual(['K21.0', 'M54.5', 'Z83.71']);
    expect(notCodes.sort()).toEqual(['I83.810', 'K58.3', 'S82.62X', 'Z99.999']);
  });
});

describe('#180 — the children are carried, and only where they mean something', () => {
  it('a header record carries its enumerated billable children', () => {
    const { headers } = classify(['M54.5']);
    const out = buildIcdDropRecords({ ...NONE, headerUseBillableChild: headers });
    expect(out[0].reason).toBe('header_use_billable_child');
    expect(out[0].children).toEqual(['M54.50', 'M54.51', 'M54.59']);
    // every one is genuinely submittable — the whole product of the token
    for (const c of out[0].children ?? []) expect(isValidIcd10(c)).toBe(true);
  });

  it('a fabrication carries NO children — there is nothing to offer', () => {
    const out = buildIcdDropRecords({ ...NONE, notInVerifiedAllowlist: ['K58.3'] });
    expect(out[0].reason).toBe('not_in_verified_allowlist');
    expect(out[0].children).toBeUndefined();
  });

  it('the children survive the round trip through the stored blob', () => {
    // The narrower rebuilds field by field and is a documented silent stripper;
    // a field added and not carried is invisible to every reader.
    const { headers } = classify(['Z83.71']);
    const dropped = buildIcdDropRecords({ ...NONE, headerUseBillableChild: headers });
    const back = readIcdDrops({ codes: [], dropped });
    expect(back[0].children).toEqual(['Z83.710', 'Z83.711', 'Z83.718', 'Z83.719']);
  });

  it('⚠️ a header ALWAYS has at least one child — the ruling depends on it', () => {
    // "one always exists, now provably". If a future edition breaks this, a
    // header drop would tell a doctor to use a child and offer none.
    for (const h of ['M54.5', 'K21.0', 'Z83.71', 'I83.8', 'I71.4', 'D22.1']) {
      expect(isIcd10Header(h), `${h} must be a header`).toBe(true);
      expect(billableDescendantsOf(h).length, `${h} must have children`).toBeGreaterThan(0);
    }
  });
});

describe('#180 — #149(b) survives: the exits are unchanged', () => {
  it('five tokens, and no two EXITS share one', () => {
    expect(new Set(ICD_DROP_REASONS).size).toBe(ICD_DROP_REASONS.length);
    const { headers, notCodes } = classify(['M54.5', 'K58.3']);
    const counts = icdDropCountsByReason({
      codes: [],
      dropped: buildIcdDropRecords({
        ...NONE,
        headerUseBillableChild: headers,
        notInVerifiedAllowlist: notCodes,
        incoherentVaricose: ['I83.90'],
        contradictedByDenial: ['J45.909'],
        unsupportedDeficiency: ['E63.9'],
      }),
    });
    // every token reachable, and each coherence floor still isolated
    for (const t of ICD_DROP_REASONS) expect(counts[t], t).toBe(1);
  });

  it('the partition reconciles against the record count', () => {
    const { headers, notCodes } = classify(['M54.5', 'K58.3']);
    const dropped = buildIcdDropRecords({
      ...NONE,
      headerUseBillableChild: headers,
      notInVerifiedAllowlist: notCodes,
    });
    const blob = { codes: [], dropped };
    const counts = icdDropCountsByReason(blob);
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    expect(total).toBe(readIcdDrops(blob).length);
  });
});

describe('#180 — the header case stays DOCTOR-VISIBLE', () => {
  it('⚠️ amber carries BOTH allowlist-exit tokens', () => {
    // Omitting the new token here would make the one ACTIONABLE case the one
    // the doctor never sees — a silent regression worse than the status quo.
    const { headers, notCodes } = classify(['M54.5', 'K58.3']);
    const blob = {
      codes: [],
      dropped: buildIcdDropRecords({
        ...NONE,
        headerUseBillableChild: headers,
        notInVerifiedAllowlist: notCodes,
        contradictedByDenial: ['J45.909'],
      }),
    };
    const amber = amberIcdDrops(blob);
    expect(amber.map((d) => d.code).sort()).toEqual(['K58.3', 'M54.5']);
    // and a clinical SUPPRESSION is still not amber — #149(c) unchanged
    expect(amber.map((d) => d.code)).not.toContain('J45.909');
    expect(amber.length).toBeLessThan(readIcdDrops(blob).length);
  });
});

describe('#180 — the new field is not a prose channel', () => {
  it('non-code-shaped children are dropped by the narrower', () => {
    // ⚠️ normalizeIcdCode is trim+uppercase ONLY, so prose survives it. The
    // first draft of the reader used it alone and this is the arm that caught
    // it: "Mrs Patient of 4 Elm Street" became a "child code".
    const back = readIcdDrops({
      codes: [],
      dropped: [
        {
          code: 'M54.5',
          reason: 'header_use_billable_child',
          children: ['M54.50', 'Mrs Patient of 4 Elm Street', 'she reports burning', '', 'M54.50'],
        },
      ],
    });
    expect(back[0].children).toEqual(['M54.50']);
    expect(JSON.stringify(back)).not.toMatch(/Elm Street|burning/);
  });

  it('a non-array children field does not crash or leak', () => {
    for (const bad of ['M54.50', 42, null, { a: 1 }, true]) {
      const back = readIcdDrops({
        codes: [],
        dropped: [{ code: 'M54.5', reason: 'header_use_billable_child', children: bad }],
      });
      expect(back[0].children).toEqual([]);
    }
  });
});
