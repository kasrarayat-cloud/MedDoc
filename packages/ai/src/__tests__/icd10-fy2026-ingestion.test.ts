// ============================================================================
// GATE — ICD-10-CM FY2026 full-release ingestion (T8)
// ----------------------------------------------------------------------------
// The allowlist stopped being a hand-curated 604-code starter set and became
// the complete CMS valid-for-submission release. This gate exists to make that
// claim falsifiable, and every block below names what would make it fail.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL (stated first, so the assertions can be
// checked against an intent rather than read as self-evidently correct):
//   · ANY content change to the generated payload  -> the digest block
//   · a truncated or partially-written generated file  -> the count blocks
//   · the header set admitted into the billing floor   -> the disjointness +
//                                                          HEADERS_32 blocks
//   · a silent regression on codes that used to work   -> the KEPT_566 block
//   · normalisation quietly widened                    -> the normalisation block
//   · the data and its provenance record drifting      -> the provenance block
// ============================================================================

import { createHash } from 'node:crypto';
import { describe, it, expect } from 'vitest';
import { ICD10CM_FY2026_BILLABLE_RAW } from '../data/icd10cm-fy2026-billable.generated';
import { ICD10CM_FY2026_HEADERS_RAW } from '../data/icd10cm-fy2026-headers.generated';
import {
  ICD10_ALLOWLIST,
  ICD10_ALLOWLIST_SIZE,
  ICD10_HEADERS,
  ICD10_HEADERS_SIZE,
  isValidIcd10,
  isIcd10Header,
} from '../data/icd10-allowlist';
import PROVENANCE from '../data/icd10cm-fy2026-provenance.json';

// CMS's OWN published counts, quoted verbatim from the addenda shipped inside
// the release (icd10cm_order_addenda_2026.txt):
//     "23467 headers in icd10cm_order_2026.txt"
//     "74719 codes in icd10cm_order_2026.txt"
// These are not measurements of our output. They are the external figure our
// output has to match, which is what makes the comparison meaningful.
const CMS_BILLABLE = 74_719;
const CMS_HEADERS = 23_467;
const CMS_TOTAL = 98_186;

// ── The 566 starter-set codes that ARE valid for submission ────────────────
// Every code the old 604-entry allowlist accepted AND that CMS agrees is
// billable. Pinned so the swap cannot silently lose ground that was already
// held. AGENTS.md, "SPLIT-FAMILY COVERAGE PINS BOTH DIRECTIONS".
const KEPT_566: readonly string[] = [
  'A09', 'B07.9', 'B34.9', 'B96.81', 'D12.0', 'D12.1', 'D12.2', 'D12.3',
  'D12.4', 'D12.5', 'D12.6', 'D12.7', 'D12.8', 'D22.0', 'D22.4', 'D22.5',
  'D22.60', 'D22.70', 'D22.9', 'D48.5', 'D50.9', 'D51.0', 'D51.1', 'D51.8',
  'D51.9', 'E03.9', 'E11.22', 'E11.65', 'E11.9', 'E40', 'E41', 'E42',
  'E43', 'E44.0', 'E44.1', 'E45', 'E46', 'E53.8', 'E55.9', 'E56.9',
  'E61.0', 'E61.1', 'E61.2', 'E61.3', 'E61.4', 'E61.5', 'E61.6', 'E61.7',
  'E63.0', 'E63.1', 'E63.9', 'E66.01', 'E66.9', 'E78.00', 'E78.5', 'E86.0',
  'E86.1', 'E86.9', 'F17.200', 'F17.201', 'F17.210', 'F17.211', 'F17.218', 'F17.219',
  'F31.9', 'F32.9', 'F32.A', 'F33.9', 'F41.1', 'F41.9', 'F43.10', 'F43.23',
  'F51.01', 'F84.0', 'F90.0', 'F90.1', 'F90.2', 'F90.9', 'G43.909', 'G44.209',
  'G45.0', 'G45.1', 'G45.2', 'G45.3', 'G45.4', 'G45.8', 'G45.9', 'G47.00',
  'G47.30', 'G47.33', 'G89.29', 'G89.4', 'H66.90', 'H66.91', 'H66.92', 'I10',
  'I20.9', 'I21.9', 'I25.10', 'I25.2', 'I48.91', 'I49.9', 'I50.1', 'I50.20',
  'I50.21', 'I50.22', 'I50.23', 'I50.30', 'I50.31', 'I50.32', 'I50.33', 'I50.40',
  'I50.41', 'I50.42', 'I50.43', 'I50.9', 'I63.00', 'I63.10', 'I63.20', 'I63.30',
  'I63.40', 'I63.50', 'I63.6', 'I63.9', 'I65.1', 'I65.21', 'I65.22', 'I65.23',
  'I65.29', 'I65.8', 'I65.9', 'I66.01', 'I66.02', 'I66.03', 'I70.0', 'I70.1',
  'I70.201', 'I70.202', 'I70.203', 'I70.208', 'I70.209', 'I70.211', 'I70.212', 'I70.213',
  'I70.218', 'I70.219', 'I70.221', 'I70.222', 'I70.223', 'I70.228', 'I70.229', 'I70.231',
  'I70.232', 'I70.233', 'I70.234', 'I70.235', 'I70.241', 'I70.244', 'I70.245', 'I70.25',
  'I70.261', 'I70.262', 'I70.263', 'I70.268', 'I70.269', 'I70.301', 'I70.302', 'I70.311',
  'I70.312', 'I70.8', 'I70.90', 'I70.92', 'I71.00', 'I71.02', 'I71.03', 'I71.8',
  'I71.9', 'I72.0', 'I72.1', 'I72.2', 'I72.3', 'I72.4', 'I72.5', 'I72.6',
  'I72.8', 'I72.9', 'I73.00', 'I73.01', 'I73.1', 'I73.81', 'I73.89', 'I73.9',
  'I74.01', 'I74.09', 'I74.10', 'I74.11', 'I74.19', 'I74.2', 'I74.3', 'I74.4',
  'I74.5', 'I74.8', 'I74.9', 'I77.0', 'I77.1', 'I77.2', 'I77.3', 'I77.4',
  'I77.5', 'I77.6', 'I77.70', 'I77.71', 'I77.72', 'I77.73', 'I77.74', 'I77.75',
  'I77.76', 'I77.77', 'I77.79', 'I77.810', 'I77.811', 'I77.812', 'I77.89', 'I77.9',
  'I80.00', 'I80.01', 'I80.02', 'I80.03', 'I80.10', 'I80.11', 'I80.12', 'I80.13',
  'I80.211', 'I80.212', 'I80.221', 'I80.222', 'I80.231', 'I80.232', 'I80.291', 'I80.292',
  'I80.3', 'I82.401', 'I82.402', 'I82.403', 'I82.4Y1', 'I82.4Z1', 'I82.501', 'I82.502',
  'I82.503', 'I82.621', 'I82.622', 'I82.890', 'I82.91', 'I83.001', 'I83.002', 'I83.003',
  'I83.004', 'I83.008', 'I83.011', 'I83.012', 'I83.013', 'I83.014', 'I83.018', 'I83.10',
  'I83.11', 'I83.12', 'I83.811', 'I83.812', 'I83.813', 'I83.891', 'I83.892', 'I83.893',
  'I83.899', 'I83.90', 'I83.91', 'I83.92', 'I83.93', 'I87.001', 'I87.002', 'I87.003',
  'I87.011', 'I87.012', 'I87.013', 'I87.2', 'I87.8', 'I87.9', 'J02.9', 'J03.90',
  'J06.9', 'J11.1', 'J18.9', 'J20.9', 'J21.9', 'J30.9', 'J44.9', 'J45.40',
  'J45.909', 'K20.0', 'K21.00', 'K21.01', 'K21.9', 'K22.70', 'K22.710', 'K22.711',
  'K22.719', 'K29.70', 'K31.89', 'K50.90', 'K51.90', 'K56.0', 'K56.1', 'K56.2',
  'K56.7', 'K57.30', 'K57.32', 'K58.0', 'K58.1', 'K58.2', 'K58.9', 'K59.00',
  'K62.5', 'K63.5', 'K64.0', 'K64.1', 'K64.8', 'K64.9', 'K74.60', 'K76.0',
  'K76.89', 'K80.20', 'K85.90', 'K85.91', 'K91.1', 'K91.2', 'K91.83', 'K91.86',
  'K91.89', 'K92.1', 'K92.2', 'K94.20', 'K94.21', 'K94.22', 'K94.23', 'L20.9',
  'L23.9', 'L30.9', 'L40.9', 'L50.9', 'L57.0', 'L57.8', 'L70.0', 'L70.1',
  'L70.8', 'L70.9', 'L82.0', 'L82.1', 'M16.9', 'M17.9', 'M19.90', 'M25.50',
  'M25.511', 'M25.512', 'M25.519', 'M25.521', 'M25.522', 'M25.531', 'M25.532', 'M25.551',
  'M25.552', 'M25.561', 'M25.562', 'M25.571', 'M25.572', 'M54.2', 'M54.50', 'M62.830',
  'M75.100', 'M79.601', 'M79.602', 'M79.604', 'M79.605', 'M79.606', 'M79.7', 'N17.0',
  'N17.1', 'N17.2', 'N17.8', 'N17.9', 'N18.1', 'N18.2', 'N18.30', 'N18.31',
  'N18.32', 'N18.4', 'N18.5', 'N18.6', 'N18.9', 'N39.0', 'N91.2', 'N92.0',
  'N94.6', 'N95.1', 'O09.211', 'O09.213', 'O09.90', 'O24.410', 'O24.414', 'O24.415',
  'O24.419', 'O36.0991', 'O80', 'O82', 'P07.30', 'R05.9', 'R06.02', 'R07.9',
  'R10.10', 'R10.11', 'R10.12', 'R10.13', 'R10.30', 'R10.31', 'R10.32', 'R10.819',
  'R10.84', 'R10.9', 'R11.10', 'R11.2', 'R19.7', 'R42', 'R50.9', 'R51.9',
  'R52', 'R53.83', 'R63.4', 'R63.5', 'S39.012A', 'S52.501A', 'S82.001A', 'S83.401A',
  'S83.402A', 'S93.401A', 'S93.402A', 'S93.409A', 'S93.411A', 'S93.412A', 'S93.421A', 'S93.422A',
  'S93.491A', 'S93.492A', 'T78.40XA', 'T81.30XA', 'T81.31XA', 'T81.40XA', 'T81.41XA', 'T81.42XA',
  'T81.43XA', 'T81.49XA', 'T82.41XA', 'T82.42XA', 'T82.43XA', 'T82.49XA', 'T82.510A', 'T82.520A',
  'T82.530A', 'T82.590A', 'T82.7XXA', 'T82.818A', 'T82.828A', 'T82.838A', 'T82.848A', 'T82.858A',
  'T82.868A', 'T82.898A', 'T85.71XA', 'Z00.00', 'Z00.01', 'Z00.110', 'Z00.121', 'Z00.129',
  'Z01.812', 'Z09', 'Z11.59', 'Z12.11', 'Z12.31', 'Z12.83', 'Z23', 'Z30.09',
  'Z30.430', 'Z30.431', 'Z30.432', 'Z30.433', 'Z32.01', 'Z34.00', 'Z34.01', 'Z34.02',
  'Z34.03', 'Z34.80', 'Z34.81', 'Z34.82', 'Z34.83', 'Z34.90', 'Z34.91', 'Z34.92',
  'Z34.93', 'Z39.0', 'Z39.1', 'Z39.2', 'Z45.89', 'Z47.1', 'Z47.2', 'Z47.81',
  'Z47.82', 'Z47.89', 'Z48.00', 'Z48.01', 'Z48.02', 'Z48.03', 'Z48.298', 'Z51.81',
  'Z68.30', 'Z68.31', 'Z68.32', 'Z68.33', 'Z68.34', 'Z68.35', 'Z68.36', 'Z68.37',
  'Z68.38', 'Z68.39', 'Z68.41', 'Z68.42', 'Z68.43', 'Z68.44', 'Z68.45', 'Z71.3',
  'Z71.82', 'Z71.89', 'Z76.89', 'Z79.01', 'Z79.02', 'Z79.4', 'Z79.84', 'Z79.890',
  'Z79.899', 'Z80.0', 'Z80.8', 'Z85.820', 'Z85.828', 'Z86.39', 'Z86.59', 'Z86.711',
  'Z86.718', 'Z86.73', 'Z86.74', 'Z86.79', 'Z87.891', 'Z90.3', 'Z90.49', 'Z95.5',
  'Z95.811', 'Z95.820', 'Z95.828', 'Z95.9', 'Z98.84', 'Z99.2',
];

// ── The 32 starter-set entries that are CATEGORY HEADERS ──────────────────
// Real ICD-10-CM entries, NOT valid for submission. These were accepted by the
// shipped 604-code floor. They must now be refused.
const HEADERS_32: readonly string[] = [
  'D22.1', 'D22.2', 'D22.3', 'F50.81', 'I47.1', 'I63.8', 'I65.0', 'I70.71',
  'I70.79', 'I71.01', 'I71.1', 'I71.2', 'I71.3', 'I71.4', 'I71.5', 'I71.6',
  'I83.20', 'I83.21', 'I83.22', 'I87.30', 'I87.31', 'I87.32', 'I87.33', 'K56.5',
  'K56.60', 'K56.69', 'M54.5', 'Z48.0', 'Z71.4', 'Z71.5', 'Z86.010', 'Z86.71',
];

// ── The 6 starter-set entries that are not ICD-10-CM codes at all ─────────
const ABSENT_6: readonly string[] = [
  'I83.810', 'K58.3', 'S83.20XA', 'T81.32XA', 'T82.510X', 'T82.61XA',
];

describe('ICD-10-CM FY2026 — the set is the complete CMS billable release', () => {
  it('reconciles to the count CMS publishes for its own file', () => {
    expect(ICD10_ALLOWLIST_SIZE).toBe(CMS_BILLABLE);
    expect(ICD10_ALLOWLIST.size).toBe(CMS_BILLABLE);
    expect(ICD10_HEADERS_SIZE).toBe(CMS_HEADERS);
    expect(ICD10_HEADERS.size).toBe(CMS_HEADERS);
    expect(ICD10_ALLOWLIST_SIZE + ICD10_HEADERS_SIZE).toBe(CMS_TOTAL);
  });

  it('is disjoint from the header set — nothing is both billable and a header', () => {
    const both = [...ICD10_HEADERS].filter((c) => ICD10_ALLOWLIST.has(c));
    expect(both).toEqual([]);
  });

  it('carries no empty or malformed member from a bad split', () => {
    // A trailing newline in the generated payload would put '' in the Set and
    // nothing else would notice, because isValidIcd10('') short-circuits on
    // falsiness before it ever reaches the Set.
    expect(ICD10_ALLOWLIST.has('')).toBe(false);
    expect(ICD10_HEADERS.has('')).toBe(false);
    const bad = [...ICD10_ALLOWLIST].filter((c) => !/^[0-9A-Z]{3}(\.[0-9A-Z]{1,4})?$/.test(c));
    expect(bad).toEqual([]);
    const badH = [...ICD10_HEADERS].filter((c) => !/^[0-9A-Z]{3}(\.[0-9A-Z]{1,4})?$/.test(c));
    expect(badH).toEqual([]);
  });

  it('the emitted payload digests to exactly the pinned value', () => {
    // ⚠️ THIS IS THE ONLY ASSERTION THAT CONSTRAINS CONTENT AT SCALE, AND IT
    // WAS ADDED BECAUSE THE ADVERSARIAL PASS PROVED THE REST DO NOT. Every
    // other block here checks CARDINALITY plus ~610 individually-pinned members
    // out of 98,186 — 0.6%. Swapping one real code for a fabricated one keeps
    // both counts, satisfies the shape filter, the disjointness check, the
    // KEPT_566 fixture and the provenance block, and leaves all 212 tests
    // green while `isValidIcd10('A00.7')` returns true. That is the
    // False-Claims-Act direction this module exists to prevent, and nothing
    // could see it.
    //
    // The digest is computed by scripts/data/build-icd10cm.mjs over the same
    // bytes it writes, so CI re-derives it offline on every run — no network,
    // no CMS archive needed. A hand-edit, a bad merge or a partial write moves
    // it. AGENTS.md, "a scripted edit PROVES ITS OWN APPLICATION", one layer out.
    const sha = (s: string) => createHash('sha256').update(s, 'utf8').digest('hex');
    expect(sha(ICD10CM_FY2026_BILLABLE_RAW)).toBe(PROVENANCE.payloadSha256.billable);
    expect(sha(ICD10CM_FY2026_HEADERS_RAW)).toBe(PROVENANCE.payloadSha256.headers);
  });

  it('digests the SAME bytes the runtime Sets are built from', () => {
    // Non-vacuity: a digest over a string nothing else reads would be a
    // decoration. Bind it to the actual membership data.
    expect(ICD10CM_FY2026_BILLABLE_RAW.split('\n')).toHaveLength(CMS_BILLABLE);
    expect(ICD10CM_FY2026_HEADERS_RAW.split('\n')).toHaveLength(CMS_HEADERS);
    expect(ICD10_ALLOWLIST.has(ICD10CM_FY2026_BILLABLE_RAW.split('\n')[0])).toBe(true);
    expect(ICD10_HEADERS.has(ICD10CM_FY2026_HEADERS_RAW.split('\n')[0])).toBe(true);
  });

  it('agrees with its own pinned provenance record', () => {
    expect(PROVENANCE.counts.billable).toBe(CMS_BILLABLE);
    expect(PROVENANCE.counts.headers).toBe(CMS_HEADERS);
    expect(PROVENANCE.counts.total).toBe(CMS_TOTAL);
    // ⚠️ PINNED TO THE ACTUAL DIGESTS, NOT TO A SHAPE. These used to be
    // /^[0-9a-f]{64}$/ matches, which passed happily against 64 zeros — the
    // adversarial pass rewrote all three to garbage plus a 1999 retrieval date
    // and the block stayed green. A shape check on a digest verifies that
    // somebody typed 64 hex characters.
    expect(PROVENANCE.zipSha256).toBe(
      '55a9124a27ca78a4a5c41e1101eda064ec2e08d105ff9e78d1fbd1a83298ef11'
    );
    expect(PROVENANCE.codesSha256).toBe(
      'a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba'
    );
    expect(PROVENANCE.orderSha256).toBe(
      '6dc95c9c7e96c734806e1682f4bf9df76251d60e99199bba0d375ba3dd11026b'
    );
    expect(PROVENANCE.zipBytes).toBe(2_204_985);
    expect(PROVENANCE.retrieved).toBe('2026-09-04');
    expect(PROVENANCE.url).toBe(
      'https://www.cms.gov/files/zip/2026-code-descriptions-tabular-order.zip'
    );
    expect(PROVENANCE.effectiveFrom).toBe('2025-10-01');
    expect(PROVENANCE.effectiveTo).toBe('2026-09-30');
  });
});

describe('ICD-10-CM FY2026 — the day-one amber specimens', () => {
  // These three were named as the specimens the ingestion had to resolve.
  // Two become VERIFIED. The third does not, and the measurement is the point.
  it('R14.0 is now VERIFIED — real, billable, previously refused', () => {
    expect(isValidIcd10('R14.0')).toBe(true);
    expect(isIcd10Header('R14.0')).toBe(false);
  });

  it('Z79.1 is now VERIFIED — real, billable, previously refused', () => {
    expect(isValidIcd10('Z79.1')).toBe(true);
    expect(isIcd10Header('Z79.1')).toBe(false);
  });

  it('Z83.71 stays REFUSED, because CMS says it is a header — and this is correct', () => {
    // ⚠️ THE EXPECTATION THAT ALL THREE WOULD TURN VERIFIED IS FALSIFIED HERE,
    // BY THE OFFICIAL FILE. `Z83.71` ("Family history of colonic polyps") is a
    // category header, flag=0 in icd10cm_order_2026.txt. Admitting it would put
    // a non-submittable code on the accepted side of the billing floor — the
    // exact harm this module's own K21.0 note was written to prevent.
    // What CHANGED is the quality of the refusal: it is no longer "absent from
    // our short list" but "a header, and here are its billable children".
    expect(isValidIcd10('Z83.71')).toBe(false);
    expect(isIcd10Header('Z83.71')).toBe(true);
    for (const child of ['Z83.710', 'Z83.711', 'Z83.718', 'Z83.719']) {
      expect(isValidIcd10(child), `${child} is the billable answer`).toBe(true);
    }
  });
});

describe('ICD-10-CM FY2026 — no regression on ground already held', () => {
  it('accepts all 566 starter-set codes that CMS agrees are billable', () => {
    expect(KEPT_566).toHaveLength(566);
    const lost = KEPT_566.filter((c) => !isValidIcd10(c));
    expect(lost).toEqual([]);
  });

  it('still accepts the specific codes the old suite named', () => {
    for (const c of ['I10', 'E11.9', 'Z00.00', 'K21.00', 'K63.5', 'I83.811', 'Z76.89']) {
      expect(isValidIcd10(c), c).toBe(true);
    }
  });

  it('resolves a sample of the 51 real-but-absent codes #149(e) measured', () => {
    // #149(e) partitioned 65 production-refused codes as 12 + 2 + 51 and found
    // 51 were REAL, SUBMITTABLE codes the starter set simply did not carry.
    // Those refusals were under-coding. A sample of the named ones:
    for (const c of ['Z48.815', 'I87.312', 'Z87.39', 'R59.0', 'F10.20', 'M17.11', 'D62']) {
      expect(isValidIcd10(c), `${c} was refused by the starter set and is real`).toBe(true);
    }
  });

  it('carries the sibling whose absence made billableChildrenOf upcode', () => {
    // #149(f) deleted the "use X instead" chip because E66.0 -> ['E66.01']
    // offered MORBID obesity as the only child of plain obesity. Both siblings
    // are present now, which is the re-arming condition that ruling named.
    expect(isValidIcd10('E66.01')).toBe(true);
    expect(isValidIcd10('E66.09')).toBe(true);
    expect(isValidIcd10('K58.8')).toBe(true); // the real "Other IBS"
  });
});

describe('ICD-10-CM FY2026 — what the starter set wrongly admitted is now refused', () => {
  it('refuses all 32 category headers it used to accept', () => {
    expect(HEADERS_32).toHaveLength(32);
    const stillAccepted = HEADERS_32.filter((c) => isValidIcd10(c));
    expect(stillAccepted).toEqual([]);
  });

  it('recognises each of those 32 as a header rather than as garbage', () => {
    const notRecognised = HEADERS_32.filter((c) => !isIcd10Header(c));
    expect(notRecognised).toEqual([]);
  });

  it('refuses the 6 entries that are not ICD-10-CM codes in any form', () => {
    expect(ABSENT_6).toHaveLength(6);
    for (const c of ABSENT_6) {
      expect(isValidIcd10(c), `${c} is not a code`).toBe(false);
      expect(isIcd10Header(c), `${c} is not a header either`).toBe(false);
    }
  });

  it('names K58.3 specifically, because the real code was left uncovered', () => {
    // The GI block added 'K58.3' commented "Other irritable bowel syndrome".
    // That description belongs to K58.8. So the phantom was admitted and the
    // real code was never carried — a defect that reads as coverage.
    expect(isValidIcd10('K58.3')).toBe(false);
    expect(isIcd10Header('K58.3')).toBe(false);
    expect(isValidIcd10('K58.8')).toBe(true);
  });

  it('keeps refusing the four header codes this codebase had already identified', () => {
    // K21.0 and K22.7 were named by the GI block; I83.89 and I83.9 came from
    // ruling #149(e)'s production audit of refused codes. Different sources,
    // same conclusion, and the official file agrees with all four.
    for (const c of ['K21.0', 'K22.7', 'I83.89', 'I83.9']) {
      expect(isValidIcd10(c), `${c} is a header`).toBe(false);
      expect(isIcd10Header(c), `${c} should be recognised as a header`).toBe(true);
    }
  });
});

describe('ICD-10-CM FY2026 — invalid input is still refused', () => {
  it('refuses fabricated and malformed codes', () => {
    for (const c of ['Z99.999', 'Q9X.XX', '99999', 'XX99.99', '00000', 'ZZZ.99']) {
      expect(isValidIcd10(c), c).toBe(false);
    }
  });

  it('refuses empty and nullish input', () => {
    expect(isValidIcd10('')).toBe(false);
    expect(isValidIcd10(null)).toBe(false);
    expect(isValidIcd10(undefined)).toBe(false);
    expect(isValidIcd10('   ')).toBe(false);
    expect(isIcd10Header('')).toBe(false);
    expect(isIcd10Header(null)).toBe(false);
    expect(isIcd10Header(undefined)).toBe(false);
  });
});

describe('ICD-10-CM FY2026 — normalisation is unchanged, deliberately', () => {
  it('normalises case and surrounding whitespace, as it always did', () => {
    expect(isValidIcd10('i10')).toBe(true);
    expect(isValidIcd10(' I10 ')).toBe(true);
    expect(isValidIcd10('I10\n')).toBe(true);
    expect(isValidIcd10('e11.9')).toBe(true);
  });

  it('STILL refuses undotted codes — a pinned decision, not an oversight', () => {
    // CMS stores codes undotted and this ingestion reads that form, so it would
    // have been easy to start accepting it. Widening what the floor ACCEPTS is a
    // different decision from widening what it KNOWS, and only the second was
    // asked for. If this assertion is ever deliberately flipped, that is a
    // decision someone made — which is the whole reason it is written down.
    // ⚠️ 'I100' WAS HERE AND WAS A DEAD ARM. There is no I10.0 — I10 is a
    // 3-character code — so 'I100' stays false under strip-the-dot
    // normalisation too, and the arm could never fail for the reason the test
    // exists. AGENTS.md, "A CONTROL AIMED WHERE THE ANSWER IS PREDETERMINED IS
    // NOT A CONTROL". Replaced with undotted forms of codes that ARE real, so
    // every arm flips if normalisation widens.
    expect(isValidIcd10('E119')).toBe(false);   // E11.9 is real
    expect(isValidIcd10('K2100')).toBe(false);  // K21.00 is real
    expect(isValidIcd10('M5451')).toBe(false);  // M54.51 is real
    expect(isValidIcd10('I8381')).toBe(false);  // I83.81 is a real header
    // ...and the dotted forms of the same codes ARE accepted, so the arms above
    // are testing normalisation and not merely absence.
    expect(isValidIcd10('E11.9')).toBe(true);
    expect(isValidIcd10('K21.00')).toBe(true);
    expect(isValidIcd10('M54.51')).toBe(true);
  });

  it('does not accept a header just because its billable child exists', () => {
    expect(isValidIcd10('M54.5')).toBe(false);
    expect(isValidIcd10('M54.51')).toBe(true);
  });
});
