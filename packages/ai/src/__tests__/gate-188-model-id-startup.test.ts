/**
 * RULING #188 — THE CONFIGURED MODEL ID IS VALIDATED AT STARTUP.
 *
 * ⚠️ WHAT THIS FIXES IS TIMING, NOT POLICY. The per-request refusal in
 * `shouldOmitTemperature` is right and is untouched: a wrong guess is a 400 on
 * the clinical path or an undeclared change to sampling. What was wrong is
 * WHERE it landed. Every clinical layer passes a temperature — L2 `0`, L4
 * `0.2`, L6 `0.1`, L7a `0`, L7b `0`, L7e `0.3`, 04b `0`, 06b `0` — and
 * `TRANSCRIBE_MD_CLINICAL_MODEL` is read by production code, so a
 * one-character typo threw uncaught on the first clinical request, wearing the
 * costume of a generation failure.
 *
 * A configuration error must not masquerade as a clinical one; the two are
 * diagnosed by different people, in different places, at different hours.
 */
import { describe, it, expect } from 'vitest';
import {
  assertClinicalModelEnv,
  temperaturePolicyFor,
  UnknownTemperaturePolicyError,
} from '../anthropic';

describe('#188 — temperaturePolicyFor is the single table, asked without throwing', () => {
  it('NON-VACUITY: it classifies both real families', () => {
    // Without this every `null` below is consistent with a predicate that
    // always returns null, which would refuse every boot.
    expect(temperaturePolicyFor('claude-opus-5')).toBe('strip');
    expect(temperaturePolicyFor('claude-fable-5')).toBe('strip');
    expect(temperaturePolicyFor('claude-sonnet-5')).toBe('accept');
    expect(temperaturePolicyFor('claude-haiku-4-5-20251001')).toBe('accept');
  });

  it('returns null — never throws — for an unlisted family', () => {
    // The whole point of splitting it out: a startup check cannot be built on
    // a function whose only way of saying "no policy" is to throw.
    expect(() => temperaturePolicyFor('claude-sonnet5')).not.toThrow();
    expect(temperaturePolicyFor('claude-sonnet5')).toBeNull();
  });
});

describe('#188 — assertClinicalModelEnv refuses a typo, by name', () => {
  it('⚠️ the exact reported typo is refused: claude-sonnet5', () => {
    // One character off the real `claude-sonnet-5`.
    expect(() =>
      assertClinicalModelEnv({ TRANSCRIBE_MD_CLINICAL_MODEL: 'claude-sonnet5' }),
    ).toThrow(UnknownTemperaturePolicyError);
  });

  it('the refusal NAMES the id, so the operator can see what they typed', () => {
    // A refusal that does not quote the offending value makes the operator
    // diff their own config against their memory.
    let msg = '';
    try {
      assertClinicalModelEnv({ TRANSCRIBE_MD_CLINICAL_MODEL: 'claude-sonnet5' });
    } catch (e) {
      msg = (e as Error).message;
    }
    expect(msg).toContain('claude-sonnet5');
  });

  it('⚠️ a LEGACY-FORM id is refused too — the anchors are at the start', () => {
    // `^claude-sonnet-` does not match `claude-3-5-sonnet-20241022`, and that
    // is the shape most likely to be pasted from older documentation.
    expect(() =>
      assertClinicalModelEnv({ TRANSCRIBE_MD_CLINICAL_MODEL: 'claude-3-5-sonnet-20241022' }),
    ).toThrow(UnknownTemperaturePolicyError);
  });

  it('every real family is ACCEPTED — this must not refuse a working boot', () => {
    for (const m of [
      'claude-opus-5',
      'claude-opus-4-8',
      'claude-fable-5',
      'claude-sonnet-5',
      'claude-sonnet-4-6',
      'claude-haiku-4-5-20251001',
    ]) {
      expect(
        () => assertClinicalModelEnv({ TRANSCRIBE_MD_CLINICAL_MODEL: m }),
        m,
      ).not.toThrow();
    }
  });

  it('⚠️ an UNSET or EMPTY variable is NOT an error', () => {
    // The default is a literal in the code and is covered by the same table.
    // Refusing on absence would refuse every normal boot — which is how a
    // fail-closed check gets deleted by whoever is on call at 03:00.
    expect(() => assertClinicalModelEnv({})).not.toThrow();
    expect(() => assertClinicalModelEnv({ TRANSCRIBE_MD_CLINICAL_MODEL: '' })).not.toThrow();
  });

  it('it reads ONLY that variable — an unrelated env value cannot trip it', () => {
    expect(() =>
      assertClinicalModelEnv({ SOME_OTHER_MODEL: 'claude-sonnet5' }),
    ).not.toThrow();
  });
});
