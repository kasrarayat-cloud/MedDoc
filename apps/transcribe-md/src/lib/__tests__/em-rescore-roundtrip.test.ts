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

import { readFileSync } from 'node:fs';

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
    for (const cause of [
      'suggestion_adopted',
      'suggestion_dismissed',
      'note_edited',
      // The doctor set the level themselves, from the gate stack. Same trap:
      // an override recorded under an unlisted cause would confront them with
      // a confirm card reading "unknown → unknown" for a code they had just
      // chosen, and the acknowledgement they gave would not match.
      'doctor_override',
    ]) {
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

describe('A DOCTOR-SET LEVEL IS GATED EXACTLY LIKE A MODEL-SET ONE', () => {
  // Requirement A, at the seam where it is actually decided. The sign route
  // compares only from/to, so this is the whole question: does an override's
  // record reach that comparison intact and unacknowledged?
  const override = {
    cause: 'doctor_override',
    at: new Date('2026-07-28T06:00:00Z').toISOString(),
    from: '99213',
    to: '99215',
  };

  it('the record the override route writes arrives unacknowledged', () => {
    const seen = unacknowledgedEmChange(override);
    expect(seen).not.toBeNull();
    expect(seen?.from).toBe('99213');
    expect(seen?.to).toBe('99215');
    expect(seen?.cause).toBe('doctor_override');
  });

  it('the acknowledgement the client sends MATCHES it — from/to, cause-blind', () => {
    // The gate is `ack.from !== pendingEm.from || ack.to !== pendingEm.to`. If
    // the cause ever entered that comparison, an override could be impossible
    // to acknowledge; if the codes ever drifted, it would be acknowledgeable
    // without being read.
    const seen = unacknowledgedEmChange(override)!;
    const ack = { from: '99213', to: '99215' };
    expect(ack.from === seen.from && ack.to === seen.to).toBe(true);

    for (const wrong of [
      { from: '99213', to: '99214' },
      { from: '99214', to: '99215' },
    ]) {
      expect(
        wrong.from === seen.from && wrong.to === seen.to,
        'a mismatched acknowledgement must not clear the gate',
      ).toBe(false);
    }
  });

  it('once acknowledged it stops blocking — and only then', () => {
    expect(unacknowledgedEmChange({ ...override })).not.toBeNull();
    expect(
      unacknowledgedEmChange({ ...override, acknowledgedAt: new Date().toISOString() }),
    ).toBeNull();
  });

  it('the sign refusal names the DOCTOR as the cause, not the model', () => {
    // The message was built from a two-arm ternary whose else-branch was "by an
    // AI-suggestion action", so the moment a doctor could set the level it told
    // them their own choice was the model's. Pinned as an exhaustive map, which
    // is also what makes a future cause a type error rather than a wrong string.
    const src = readFileSync('src/app/api/visits/[id]/sign/route.ts', 'utf8');
    const map = src.slice(
      src.indexOf('const EM_CAUSE_PHRASE'),
      src.indexOf('};', src.indexOf('const EM_CAUSE_PHRASE')),
    );
    expect(map).toContain('Record<EmChangeCause, string>');
    for (const cause of EM_CHANGE_CAUSES) {
      expect(map, `no phrase for ${cause}`).toContain(`${cause}:`);
    }
    expect(map).toMatch(/doctor_override:\s*'because you set it'/);
    // And the message is built from the map, not from a ternary.
    expect(src).toContain('EM_CAUSE_PHRASE[pendingEm.cause]');
  });
});
