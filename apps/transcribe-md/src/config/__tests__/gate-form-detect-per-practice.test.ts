import { afterEach, describe, it, expect } from 'vitest';

import { formDetectFillEnabled } from '../form-detect-fill';

// Ruling #326 Slice D — the detect→fill gate is PER-PRACTICE, allowlist-only, with
// NO global "on". This is the safety boundary that keeps the owner-only acceptance
// from routing ~200 other practices' PDF uploads through the new pipeline.

const KEY = 'FORM_DETECT_FILL_PRACTICES';
const OWNER = 'cmo5ye2nf000b01s3q0xlkaxb';

afterEach(() => {
  delete process.env[KEY];
});

describe('formDetectFillEnabled — per-practice gate', () => {
  it('is OFF for EVERY practice when the allowlist is unset (no global on)', () => {
    delete process.env[KEY];
    expect(formDetectFillEnabled(OWNER)).toBe(false);
    expect(formDetectFillEnabled('any-other-practice')).toBe(false);
  });

  it('is OFF for every practice when the allowlist is empty', () => {
    process.env[KEY] = '';
    expect(formDetectFillEnabled(OWNER)).toBe(false);
    process.env[KEY] = '   , ,  ';
    expect(formDetectFillEnabled(OWNER)).toBe(false);
  });

  it('enables ONLY the listed practices, never any other (no cross-practice leak)', () => {
    process.env[KEY] = OWNER;
    expect(formDetectFillEnabled(OWNER)).toBe(true);
    expect(formDetectFillEnabled('cmXXXother')).toBe(false);
    expect(formDetectFillEnabled('cmo5ye2nf000b01s3q0xlkax')).toBe(false); // prefix, not equal
  });

  it('parses a comma-separated list with surrounding whitespace', () => {
    process.env[KEY] = ` pA , ${OWNER} ,pC `;
    expect(formDetectFillEnabled('pA')).toBe(true);
    expect(formDetectFillEnabled(OWNER)).toBe(true);
    expect(formDetectFillEnabled('pC')).toBe(true);
    expect(formDetectFillEnabled('pD')).toBe(false);
  });

  it('FAILS CLOSED on a null / undefined / empty practiceId (never routes by omission)', () => {
    process.env[KEY] = OWNER;
    expect(formDetectFillEnabled(null)).toBe(false);
    expect(formDetectFillEnabled(undefined)).toBe(false);
    expect(formDetectFillEnabled('')).toBe(false);
  });
});
