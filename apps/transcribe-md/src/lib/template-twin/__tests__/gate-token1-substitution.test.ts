// ============================================================================
// GATE — TOKEN-1: scaffold tokens substitute deterministically from the record,
// an unresolvable token declines (field blank) with a named reason, and no brace
// placeholder ever reaches the rendered bytes.
// ----------------------------------------------------------------------------
// Every arm carries its own POSITIVE CONTROL (the opposite case), because a
// substitution/gate test that only checks the happy path can pass vacuously —
// see "a control can pass vacuously" in the canon.
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  SUBSTITUTABLE_TOKENS,
  hasSubstitutableTokens,
  isFurnitureScaffold,
  isTokenOnlyScaffold,
  residualPlaceholders,
  substitutableTokensIn,
  unregisteredPlaceholders,
} from '../scaffold-text';
import { substituteScaffoldTokens } from '../token-substitution';

const HPI = '{patient} is a pleasant {age}-year-old presenting for consultation.';
// A fixed synthetic record → a stable age, so the assertion is deterministic.
const RECORD = { name: 'Jordan Rivers', dateOfBirth: '1971-03-02' };
const VISIT_DATE = '2026-09-11'; // 55 on this date

describe('TOKEN-1 — the closed token set', () => {
  it('registers exactly {patient} and {age} today', () => {
    expect([...SUBSTITUTABLE_TOKENS].sort()).toEqual(['age', 'patient']);
  });

  it('detects registered tokens and NOT the choice marker or literal prose', () => {
    expect(hasSubstitutableTokens(HPI)).toBe(true);
    // positive control: a non-token brace must not read as substitutable
    expect(hasSubstitutableTokens('{{one of: a, b}}')).toBe(false);
    expect(hasSubstitutableTokens('no braces here')).toBe(false);
    expect(substitutableTokensIn(HPI)).toEqual(['patient', 'age']);
  });
});

describe('TOKEN-1 — deterministic substitution from the record', () => {
  it('substitutes {patient} and {age} with the record values', () => {
    const r = substituteScaffoldTokens(HPI, RECORD, VISIT_DATE);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.text).toBe('Jordan Rivers is a pleasant 55-year-old presenting for consultation.');
    expect(r.text).not.toContain('{'); // no residual brace
    expect(r.substitutions).toEqual([
      { token: 'patient', value: 'Jordan Rivers' },
      { token: 'age', value: '55' },
    ]);
  });

  it('is idempotent in value: same inputs → same output (never a model)', () => {
    const a = substituteScaffoldTokens(HPI, RECORD, VISIT_DATE);
    const b = substituteScaffoldTokens(HPI, RECORD, VISIT_DATE);
    expect(a).toEqual(b);
  });

  it('leaves text with NO registered token unchanged (pre-TOKEN-1 behaviour)', () => {
    const plain = 'The patient consents to the procedure.';
    const r = substituteScaffoldTokens(plain, RECORD, VISIT_DATE);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.text).toBe(plain);
    expect(r.substitutions).toEqual([]);
  });
});

describe('TOKEN-1 — an unresolvable token declines with a named reason', () => {
  it('refuses {patient} when the record has no name', () => {
    const r = substituteScaffoldTokens(HPI, { name: null, dateOfBirth: '1971-03-02' }, VISIT_DATE);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.token).toBe('patient');
    expect(r.reason).toBe('patient_name_absent');
  });

  it('refuses {age} when the record has no DOB — and does NOT emit a half-substituted sentence', () => {
    const r = substituteScaffoldTokens(HPI, { name: 'Jordan Rivers', dateOfBirth: null }, VISIT_DATE);
    expect(r.ok).toBe(false);
    if (r.ok) return;
    // positive control on the DESIGN CHOICE: refusal is whole-insert, so no
    // "Jordan Rivers is a pleasant -year-old" string is ever produced.
    expect(r.token).toBe('age');
    expect(r.reason).toBe('age_input_absent');
  });
});

describe('TOKEN-1 — the export-bytes gate predicate', () => {
  it('flags a surviving {patient}/{age} and any {word}, but NOT {{one of}}', () => {
    expect(residualPlaceholders('… {patient} …').sort()).toEqual(['{patient}']);
    expect(residualPlaceholders('… {foo_bar} …')).toEqual(['{foo_bar}']);
    // positive control: the substituted sentence and a choice marker are clean
    expect(residualPlaceholders('Jordan Rivers is a pleasant 55-year-old.')).toEqual([]);
    expect(residualPlaceholders('Choose {{one of: a, b}} please')).toEqual([]);
  });

  it('catches a token EMBEDDED in a choice marker (the strip no longer eats it)', () => {
    // adversarial finding: a greedy {{…}} strip returned [] here, hiding a residual.
    expect(residualPlaceholders('{{one of: {patient}}}')).toEqual(['{patient}']);
    expect(residualPlaceholders('{{note {age}} tail')).toEqual(['{age}']);
  });

  it('unregisteredPlaceholders separates a defect brace from a registered token', () => {
    expect(unregisteredPlaceholders('{patient} MRN {mrn} age {age}')).toEqual(['{mrn}']);
    // positive control: a scaffold of only registered tokens has no offender
    expect(unregisteredPlaceholders('{patient} is {age}')).toEqual([]);
    expect(unregisteredPlaceholders('plain prose')).toEqual([]);
  });
});

describe('PANEL-1 — furniture and token-only predicates', () => {
  it('classifies furniture (offer withdrawn) vs real wording (offer kept)', () => {
    expect(isFurnitureScaffold('____')).toBe(true);
    expect(isFurnitureScaffold('- ______ -')).toBe(true);
    expect(isFurnitureScaffold('   ')).toBe(false); // empty-after-trim is handled upstream
    // positive control: real wording and a token sentence are NOT furniture
    expect(isFurnitureScaffold(HPI)).toBe(false);
    expect(isFurnitureScaffold('No known drug allergies.')).toBe(false);
  });

  it('drops a TOKEN-ONLY scaffold but keeps a token MIXED with prose', () => {
    expect(isTokenOnlyScaffold('{patient}')).toBe(true);
    expect(isTokenOnlyScaffold('{patient}, {age}')).toBe(true);
    // positive control: the HPI intro mixes a token with prose — it stays offered
    expect(isTokenOnlyScaffold(HPI)).toBe(false);
    expect(isTokenOnlyScaffold('No known drug allergies.')).toBe(false);
  });
});
