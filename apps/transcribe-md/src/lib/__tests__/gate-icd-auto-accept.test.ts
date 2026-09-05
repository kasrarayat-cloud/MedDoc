// ============================================================================
// THE SIGN-TIME AUTO-ACCEPT — THE GATE.
// ----------------------------------------------------------------------------
// This writes a BILLABLE DIAGNOSIS onto a signed clinical record without the
// doctor touching it. Every arm below is about a way that could be wrong in the
// direction that harms: overwriting a decision they DID make, reading a number
// it cannot interpret, or attributing the write to nobody.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  ICD_AUTO_ACCEPT_MIN_CONFIDENCE,
  autoAcceptIcdDecisions,
  readSuggestedConfidence,
} from '../icd-auto-accept';
import { ICD_DECISION_RECORD_KEYS, readIcdDecisions } from '../icd-decisions';

const AT = '2026-09-05T09:00:00.000Z';
const WHO = 'user-1';
const ACTOR = { at: AT, byUserId: WHO };

const blob = (codes: Array<{ code: string; confidence?: unknown }>) => ({
  codes: codes.map((c) => ({
    code: c.code,
    description: `desc ${c.code}`,
    evidence_quote: 'q',
    ...(c.confidence === undefined ? {} : { confidence: c.confidence }),
  })),
});

describe('the threshold is the generator’s own band', () => {
  it('is 0.9 — the ONLY band whose description says the note states the diagnosis', () => {
    // Pinned as a VALUE because changing it is a product decision, and a
    // product decision should show up in a diff as a changed number plus a
    // changed test, never as a silent drift.
    expect(ICD_AUTO_ACCEPT_MIN_CONFIDENCE).toBe(0.9);
  });

  it('accepts AT the threshold and refuses just below it', () => {
    const at = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.9 }]), null, ACTOR);
    expect(at.added).toEqual(['E11.9']);
    // 0.89 is inside the generator's "strongly implied" band — an inference,
    // which is the thing a doctor is for.
    const below = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.89 }]), null, ACTOR);
    expect(below.added).toEqual([]);
    expect(below.decisions).toEqual({});
  });
});

describe('⚠️ it ADDS and it never REPLACES', () => {
  it('⚠️ A REJECTED CODE IS NEVER FLIPPED, however confident the suggester was', () => {
    // The arm that matters most. Overwriting here puts a code the doctor threw
    // out onto the signed record as accepted, by a machine, with no trace.
    const stored = {
      'E11.9': { state: 'rejected', at: '2026-09-01T00:00:00.000Z', byUserId: 'dr', reason: 'not_this_encounter' },
    };
    const r = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 1 }]), stored, ACTOR);
    expect(r.added).toEqual([]);
    expect(r.decisions['E11.9']?.state).toBe('rejected');
    expect(r.decisions['E11.9']?.auto).toBeUndefined();
  });

  it('a code the doctor ACCEPTED keeps their attribution, not the machine’s', () => {
    const stored = { 'E11.9': { state: 'accepted', at: '2026-09-01T00:00:00.000Z', byUserId: 'dr' } };
    const r = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 1 }]), stored, ACTOR);
    expect(r.added).toEqual([]);
    expect(r.decisions['E11.9']?.byUserId).toBe('dr');
    expect(r.decisions['E11.9']?.auto).toBeUndefined();
  });

  it('an ORPHANED record survives untouched — it is not in the suggested set', () => {
    const stored = { 'Z00.00': { state: 'accepted', at: AT, byUserId: 'dr' } };
    const r = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.95 }]), stored, ACTOR);
    expect(r.added).toEqual(['E11.9']);
    expect(r.decisions['Z00.00']).toBeTruthy();
    expect(Object.keys(r.decisions).sort()).toEqual(['E11.9', 'Z00.00']);
  });
});

describe('⚠️ a confidence it cannot interpret is REFUSED, never rescaled', () => {
  // The display path guesses the scale — `c * (c <= 1 ? 100 : 1)` — because
  // guessing wrong there costs a wrong percentage on screen. Here it would cost
  // an auto-accepted diagnosis.
  it.each([
    ['a 0-100 scale value', 90],
    ['a nonsense small integer on the 0-100 reading', 2],
    ['above the schema maximum', 1.5],
    ['negative', -1],
    ['NaN', Number.NaN],
    ['Infinity', Number.POSITIVE_INFINITY],
    ['a string', '0.95'],
    ['absent', undefined],
    ['null', null],
  ])('%s does not auto-accept', (_label, conf) => {
    const r = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: conf }]), null, ACTOR);
    expect(r.added).toEqual([]);
  });

  it('non-vacuity: the SAME fixture with a valid confidence DOES auto-accept', () => {
    // Without this the block above passes just as happily on a function that
    // never accepts anything at all.
    expect(autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.95 }]), null, ACTOR).added)
      .toEqual(['E11.9']);
  });

  it('a duplicated code scores against its FIRST row, matching suggestedIcdCodes', () => {
    // `suggestedIcdCodes` collapses a duplicate into its first row. Reading a
    // later row's number here would score one code against another's.
    const raw = { codes: [
      { code: 'E11.9', confidence: 0.2 },
      { code: 'E11.9', confidence: 0.99 },
    ] };
    expect(readSuggestedConfidence(raw)['E11.9']).toBe(0.2);
    expect(autoAcceptIcdDecisions(raw, null, ACTOR).added).toEqual([]);
  });
});

// ============================================================================
// ⚠️ THE ADVERSARIAL PASS'S FINDINGS, AS ARMS.
// ----------------------------------------------------------------------------
// None of the arms above could see any of these. Each is written so it RED-s
// on the code as it was, and each names the wrong output it produced.
// ============================================================================

describe('⚠️ a stored record the NARROWER cannot read still blocks the auto-accept', () => {
  // The guard used to read `readIcdDecisions(...)` — the NARROWED map — while
  // its own comment claimed it "cannot be defeated by a state this file has not
  // heard of". The narrower DROPS what it cannot interpret, so the code read as
  // undecided and the doctor's rejection was replaced by its opposite.
  it.each([
    ['a reason token this build does not know', { state: 'rejected', at: '2026-09-01T00:00:00.000Z', byUserId: 'dr', reason: 'patient_declined' }],
    ['a state a later slice adds', { state: 'deferred', at: '2026-09-01T00:00:00.000Z', byUserId: 'dr' }],
    ['a rejection written before `reason` existed', { state: 'rejected', at: '2026-09-01T00:00:00.000Z', byUserId: 'dr' }],
    ['an empty actor', { state: 'rejected', at: '2026-09-01T00:00:00.000Z', byUserId: '', reason: 'other' }],
    ['a malformed timestamp', { state: 'rejected', at: 0, byUserId: 'dr', reason: 'other' }],
  ])('%s is NOT overwritten by a machine acceptance', (_label, stored) => {
    const r = autoAcceptIcdDecisions(
      blob([{ code: 'E11.9', confidence: 0.99 }]),
      { 'E11.9': stored },
      ACTOR,
    );
    expect(r.added, 'the narrower dropped it, so the guard read it as undecided').toEqual([]);
    // And the stored bytes survive the write untouched.
    expect(r.decisions['E11.9']).toEqual(stored);
  });

  it('the key is matched with the SAME normaliser the suggested set uses', () => {
    // A raw key of a different case must still block — two matchers on one
    // identifier is a recorded failure class in this repo.
    const r = autoAcceptIcdDecisions(
      blob([{ code: 'E11.9', confidence: 0.99 }]),
      { 'e11.9': { state: 'rejected', at: 'A', byUserId: 'dr', reason: 'other' } },
      ACTOR,
    );
    expect(r.added).toEqual([]);
  });

  it('non-vacuity: with NOTHING stored, the same code IS auto-accepted', () => {
    expect(autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.99 }]), {}, ACTOR).added)
      .toEqual(['E11.9']);
  });
});

describe('⚠️ the write carries every stored byte on records it did not touch', () => {
  it('a field this build does not know SURVIVES on an untouched record', () => {
    // The write replaces the whole column. Narrowing the carrier destroyed any
    // field a concurrently-deployed or later image knows about — on a record
    // the auto-accept had correctly DECLINED to touch.
    const stored = {
      I10: { state: 'rejected', at: 'A', byUserId: 'dr', reason: 'other', supersededBy: 'I10.9' },
    };
    const r = autoAcceptIcdDecisions(
      blob([{ code: 'E11.9', confidence: 0.95 }, { code: 'I10', confidence: 0.95 }]),
      stored,
      ACTOR,
    );
    expect(r.added).toEqual(['E11.9']);
    expect(
      (r.decisions['I10'] as unknown as Record<string, unknown>)?.supersededBy,
      'an untouched record lost a field to a signature that only added a different code',
    ).toBe('I10.9');
  });
});

describe('⚠️ a refused confidence CONSUMES the code’s turn', () => {
  it('a malformed FIRST row does not let a later duplicate win', () => {
    // `if (code in out)` guarded on the OUTPUT, and an invalid confidence
    // `continue`d without writing it — so the code stayed unseen and the next
    // duplicate was read. `[{I10,95},{I10,0.95}]` yielded 0.95 and
    // auto-accepted a code whose first row had just been REFUSED.
    const raw = { codes: [{ code: 'I10', confidence: 95 }, { code: 'I10', confidence: 0.95 }] };
    expect(readSuggestedConfidence(raw)['I10']).toBeUndefined();
    expect(autoAcceptIcdDecisions(raw, null, ACTOR).added).toEqual([]);
  });

  it('and the same for a non-numeric first row', () => {
    const raw = { codes: [{ code: 'I10', confidence: '0.40' }, { code: 'I10', confidence: 0.99 }] };
    expect(readSuggestedConfidence(raw)['I10']).toBeUndefined();
    expect(autoAcceptIcdDecisions(raw, null, ACTOR).added).toEqual([]);
  });

  it('non-vacuity: a VALID first row still wins over a later duplicate', () => {
    const raw = { codes: [{ code: 'I10', confidence: 0.99 }, { code: 'I10', confidence: 0.1 }] };
    expect(readSuggestedConfidence(raw)['I10']).toBe(0.99);
    expect(autoAcceptIcdDecisions(raw, null, ACTOR).added).toEqual(['I10']);
  });
});

describe('the written record', () => {
  it('carries auto:true, the actor, and NO reason', () => {
    const r = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.93 }]), null, ACTOR);
    expect(r.decisions['E11.9']).toEqual({ state: 'accepted', at: AT, byUserId: WHO, auto: true });
  });

  it('⚠️ SURVIVES THE NARROWER — the field is in ICD_DECISION_RECORD_KEYS', () => {
    // A record that round-trips through `readIcdDecisions` LOSING `auto` is
    // the F8-S1 stripping defect: every reader would rewrite it narrowed, and
    // the provenance of a machine-written diagnosis would quietly vanish.
    const r = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.93 }]), null, ACTOR);
    expect(readIcdDecisions(r.decisions)['E11.9']?.auto).toBe(true);
    expect(ICD_DECISION_RECORD_KEYS).toContain('auto');
  });

  it('⚠️ `auto` is read as the LITERAL true, never as truthy', () => {
    // A stray `"yes"` marking a DOCTOR'S decision as machine-made is the
    // reading that invites a later sweep to discard it.
    for (const v of ['yes', 1, {}, 'true']) {
      expect(readIcdDecisions({ 'E11.9': { state: 'accepted', at: AT, byUserId: WHO, auto: v } })['E11.9']?.auto)
        .toBeUndefined();
    }
    expect(readIcdDecisions({ 'E11.9': { state: 'accepted', at: AT, byUserId: WHO, auto: true } })['E11.9']?.auto)
      .toBe(true);
  });

  it('a malformed actor writes NOTHING rather than a record naming nobody', () => {
    for (const bad of [{ at: AT, byUserId: '' }, { at: '', byUserId: WHO }]) {
      const r = autoAcceptIcdDecisions(blob([{ code: 'E11.9', confidence: 0.99 }]), null, bad);
      expect(r.added).toEqual([]);
      expect(r.decisions).toEqual({});
    }
  });

  it('added[] and the map RECONCILE — every added code is in the map as auto', () => {
    const r = autoAcceptIcdDecisions(
      blob([
        { code: 'E11.9', confidence: 0.95 },
        { code: 'K21.00', confidence: 0.5 },
        { code: 'I10', confidence: 0.91 },
      ]),
      null,
      ACTOR,
    );
    expect(r.added).toEqual(['E11.9', 'I10']);
    expect(Object.keys(r.decisions).sort()).toEqual(r.added.slice().sort());
    expect(r.added.every((c) => r.decisions[c]?.auto === true)).toBe(true);
    // Non-vacuity for that `every`: the set it quantifies over is not empty.
    expect(r.added.length).toBeGreaterThan(1);
  });
});
