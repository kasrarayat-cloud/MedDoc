// ============================================================================
// The record the re-score writes must survive the parser that reads it.
// ----------------------------------------------------------------------------
// This exists because a source-text test asserted the presence of a literal
// that its own parser REJECTED. `cause: 'note_edited'` was not a member of
// EM_CHANGE_CAUSES, so every pending record the re-score wrote coerced to the
// unknown→unknown sentinel: the doctor confirmed the correct code and was
// refused, and the confirm card read "now supports unknown, up from unknown" —
// on the exact path the whole change set exists to protect.
//
// Two files that never met. So this one makes them meet: build the record the
// way the writer builds it, feed it to the reader, and assert what comes out.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  EM_CHANGE_CAUSES,
  parseEmPendingChange,
  unacknowledgedEmChange,
} from '../em-pending-change';

/** Exactly the shape rescoreEmAction persists. */
function recordAsWritten(cause: string) {
  return { cause, at: new Date('2026-07-26T20:00:00Z').toISOString(), from: '99213', to: '99214' };
}

describe('the re-score record survives the sign gate', () => {
  it('parses — the cause the writer uses is one the reader accepts', () => {
    const parsed = parseEmPendingChange(recordAsWritten('note_edited'));
    expect(parsed, 'a record the writer produces must not be malformed').not.toBeNull();
    expect(parsed?.from).toBe('99213');
    expect(parsed?.to).toBe('99214');
  });

  it('reaches the sign gate with the REAL codes, not the sentinel', () => {
    const seen = unacknowledgedEmChange(recordAsWritten('note_edited'));
    expect(seen).not.toBeNull();
    expect(seen?.from).toBe('99213');
    expect(seen?.to).toBe('99214');
    // The sentinel is what a malformed record becomes. If we ever see it here,
    // the doctor is being asked to attest to a level nobody can read.
    expect(seen?.from).not.toBe('unknown');
    expect(seen?.to).not.toBe('unknown');
  });

  it('every cause the app writes is a member of the enum', () => {
    // Cheap guard against the same class: the writers' literals, checked
    // against the reader's set rather than against a string in a file.
    for (const cause of ['suggestion_adopted', 'suggestion_dismissed', 'note_edited']) {
      expect(EM_CHANGE_CAUSES as readonly string[], `${cause} must be accepted`).toContain(cause);
      expect(parseEmPendingChange(recordAsWritten(cause))).not.toBeNull();
    }
  });

  it('still fails CLOSED on a genuinely malformed record', () => {
    // The sentinel must survive for the case it was built for.
    const seen = unacknowledgedEmChange(recordAsWritten('not_a_real_cause'));
    expect(seen?.from).toBe('unknown');
    expect(seen?.to).toBe('unknown');
  });
});
