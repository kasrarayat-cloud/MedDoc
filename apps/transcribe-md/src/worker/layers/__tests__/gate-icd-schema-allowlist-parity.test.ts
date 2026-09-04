// ============================================================================
// GATE — 07a's SHAPE SCHEMA and the ICD-10 ALLOWLIST must agree
// ----------------------------------------------------------------------------
// Two independent descriptions of "what an ICD-10-CM code looks like" live in
// this repo: the Zod regex on `IcdCode.code` (07a-icd-coding.ts) and the set of
// codes `isValidIcd10` accepts (@meddoc/ai). Nothing made them agree, and they
// silently disagreed the moment the data changed underneath the schema.
//
// ⚠️ HOW THIS WAS FOUND, AND WHY IT IS A GATE AND NOT A FIX. Against the
// 604-code STARTER set the invariant "every allowlist member satisfies 07a's
// regex" held with ZERO violations. Against the complete CMS FY2026 set it had
// THIRTEEN: FY2026 introduced the QA0 neurodevelopmental chapter (SCN2A-,
// CACNA1A-, SLC6A1-, STXBP1-, DLG4-, FOXG1-related disorders) whose codes carry
// a LETTER in position 2, and the regex required a digit there.
//
// ⚠️ AND THE BLAST RADIUS WAS THE WHOLE RESPONSE, NOT ONE CODE. `IcdResult`
// parses the model's ENTIRE array in one `safeParse`, so a single QA0 code made
// the parse fail and discarded every other code alongside it. A rare code did
// not cost you that code; it cost you the visit's coding.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL: narrowing the 07a regex; ingesting a
// future ICD-10-CM edition (FY2027 lands 2026-10-01) that introduces another
// code shape the regex cannot express. Both are exactly when someone needs to
// be told, and neither is visible in the diff that causes it.
// ============================================================================

import { describe, it, expect, vi } from 'vitest';

// 07a imports prisma and the audit helper at module level, and the audit
// helper pulls in next-auth. Stub ONLY those two: `@meddoc/ai` is left REAL on
// purpose, because the real allowlist is the thing under test here. Mocking it
// (as the fallback suite does, correctly, for its own purpose) would make this
// gate assert a parity between a regex and a stub.
vi.mock('@meddoc/db', () => ({ default: { transcribeVisit: { update: vi.fn() } } }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { IcdCode, IcdResult } from '../07a-icd-coding';
import { ICD10_ALLOWLIST, ICD10_HEADERS, isValidIcd10 } from '@meddoc/ai';

const wrap = (code: string) => ({
  code,
  description: 'x',
  evidence_quote: 'x',
  confidence: 0.9,
  confidenceLevel: 'high' as const,
});

describe('07a schema / allowlist parity', () => {
  it('accepts EVERY code the allowlist certifies as billable', () => {
    const rejected = [...ICD10_ALLOWLIST].filter(
      (c) => !IcdCode.safeParse(wrap(c)).success
    );
    // A code the deterministic floor calls billable but the only production
    // caller cannot even parse is a code the pipeline can never emit.
    expect(
      rejected.slice(0, 25),
      `07a's regex rejects ${rejected.length} billable codes`
    ).toEqual([]);
    expect(rejected).toHaveLength(0);
  });

  it('accepts every HEADER code too', () => {
    // isIcd10Header ships with no caller today, but the filed follow-up wires
    // it into the drop-record reason. A header the schema cannot express would
    // break that on arrival rather than here.
    const rejected = [...ICD10_HEADERS].filter(
      (c) => !IcdCode.safeParse(wrap(c)).success
    );
    expect(rejected.slice(0, 25)).toEqual([]);
    expect(rejected).toHaveLength(0);
  });

  it('parses the QA0 chapter — the 13 codes that broke this invariant', () => {
    const QA0 = [
      'QA0.0101', 'QA0.0102', 'QA0.0109', 'QA0.011', 'QA0.012',
      'QA0.0131', 'QA0.0139', 'QA0.0141', 'QA0.0142', 'QA0.0149',
      'QA0.0151', 'QA0.0159', 'QA0.8',
    ];
    // Non-vacuity: assert the set we are checking is the size we think it is,
    // and that these are genuinely billable rather than strings we invented.
    expect(QA0).toHaveLength(13);
    for (const c of QA0) {
      expect(isValidIcd10(c), `${c} must be billable`).toBe(true);
      expect(IcdCode.safeParse(wrap(c)).success, `${c} must parse`).toBe(true);
    }
  });

  it('does not let one exotic code discard the rest of the response', () => {
    // The real failure mode: IcdResult parses the whole array at once.
    const parsed = IcdResult.safeParse({
      codes: [wrap('F84.0'), wrap('QA0.0151'), wrap('I10')],
    });
    expect(parsed.success).toBe(true);
    expect(parsed.success && parsed.data.codes).toHaveLength(3);
  });

  it('still refuses genuinely malformed shapes — the floor is not gone', () => {
    // Widening position 2 must not have opened the gate generally.
    for (const bad of ['', '1', 'AB', '12.34', 'A!.0', 'A00.123456', 'lowercase']) {
      expect(IcdCode.safeParse(wrap(bad)).success, `${bad} must be refused`).toBe(false);
    }
  });

  it('shape-parsing is NOT validity — the two layers stay distinct', () => {
    // A well-shaped string that is not a real code must pass the SHAPE filter
    // and fail the ALLOWLIST. If this ever inverts, the floor has moved into
    // the regex, which is not where it belongs.
    expect(IcdCode.safeParse(wrap('Z99.999')).success).toBe(true);
    expect(isValidIcd10('Z99.999')).toBe(false);
  });
});

describe('07a prompt does not name codes that cannot exist', () => {
  it('every ICD-10 code named in the L7A system prompt is real', async () => {
    // ⚠️ THE PROMPT IS A CODE CONSUMER AND NOTHING TREATED IT AS ONE. It
    // ORDERED the model to emit `I83.810` for unspecified-laterality varicose
    // pain. That code does not exist in any ICD-10-CM edition (the family runs
    // 811/812/813/819), so once the allowlist became correct, every such visit
    // dropped to ZERO diagnosis codes. The sweep that fixed the data and the
    // tests did not reach the file that MANUFACTURES the input.
    const { L7A_SYSTEM_PROMPT } = await import('../07a-icd-coding');
    const named = [
      ...new Set(L7A_SYSTEM_PROMPT.match(/\b[A-TV-Z][0-9][0-9AB]\.[0-9A-Z]{1,4}\b/g) ?? []),
    ];
    // Non-vacuity: the extraction must actually find codes, or this asserts
    // nothing at all.
    expect(named.length, 'no codes extracted — the regex found nothing').toBeGreaterThan(20);
    const notReal = named.filter((c) => !isValidIcd10(c));
    expect(notReal, `the prompt names codes that are not billable: ${notReal.join(', ')}`).toEqual([]);
  });
});
