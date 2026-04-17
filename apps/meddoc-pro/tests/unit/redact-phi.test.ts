// ============================================================================
// redactPhi (@meddoc/ai) — PHI scrubber for log lines
// ----------------------------------------------------------------------------
// M3 ships the minimum per spec §13: email / phone / SSN masking plus a
// word-count ceiling (anything >20 words is assumed transcript content).
// Exercised from scribe-ws error paths where Deepgram events carry raw
// transcript text. M7 hardens with a proper clinical-NER pass.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { redactPhi } from '@meddoc/ai';

describe('redactPhi', () => {
  it('leaves short structured strings untouched so ops can debug', () => {
    expect(redactPhi('visit=abc123 status=RECORDING')).toBe(
      'visit=abc123 status=RECORDING'
    );
    expect(redactPhi('Deepgram connection opened')).toBe(
      'Deepgram connection opened'
    );
  });

  it('masks email addresses', () => {
    expect(redactPhi('contact john.doe+chart@clinic.example.org please')).toBe(
      'contact [EMAIL] please'
    );
  });

  it('masks phone-like digit runs', () => {
    expect(redactPhi('call (415) 555-0142 back')).toBe('call [PHONE] back');
    expect(redactPhi('ph 415-555-0142')).toBe('ph [PHONE]');
    expect(redactPhi('int +1 415 555 0142')).toBe('int [PHONE]');
  });

  it('masks SSN-shaped digit runs', () => {
    expect(redactPhi('SSN 123-45-6789 on file')).toBe('SSN [SSN] on file');
    expect(redactPhi('ssn 123456789')).toBe('ssn [SSN]');
  });

  it('collapses free-text longer than 20 words to a length marker', () => {
    const longText =
      'Patient reports chest pain radiating to left arm for thirty minutes, ' +
      'associated with shortness of breath, nausea, and diaphoresis starting ' +
      'while mowing the lawn this morning after breakfast.';
    const out = redactPhi(longText);
    expect(out).toMatch(/^\[REDACTED:\d+w\]$/);
    // Should not contain any of the original medical content.
    expect(out).not.toContain('chest pain');
    expect(out).not.toContain('Patient');
  });

  it('stringifies non-string inputs before scanning', () => {
    const obj = { err: 'DEEPGRAM_ERROR', visitId: 'cviz1', contact: 'a@b.co' };
    expect(redactPhi(obj)).toContain('[EMAIL]');
    expect(redactPhi(obj)).not.toContain('a@b.co');
  });

  it('renders null / undefined as strings (caller-friendly)', () => {
    expect(redactPhi(null)).toBe('null');
    expect(redactPhi(undefined)).toBe('undefined');
  });

  it('masks pii patterns FIRST, then applies length ceiling', () => {
    // Even inside a long string, PII masking still runs — but the whole
    // thing collapses if over the word ceiling. The ceiling wins, which
    // is the safer default.
    const s = 'call 415-555-0142 ' + 'word '.repeat(30);
    expect(redactPhi(s)).toMatch(/^\[REDACTED:\d+w\]$/);
  });
});
