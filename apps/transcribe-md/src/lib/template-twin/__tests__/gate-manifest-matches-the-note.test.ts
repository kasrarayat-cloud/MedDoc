import { describe, expect, it } from 'vitest';
import { noteIdentity, manifestMatchesNote } from '../note-identity';

/**
 * F5-f RULING 1 — A MANIFEST IS SERVABLE ONLY WHEN IT PROVABLY CORRESPONDS TO
 * THE VISIT'S CURRENT NOTE.
 *
 * ⚠️ THE DEFECT THIS CLOSES, and it was found by the refutation pass over the
 * commit that exposed it rather than by anything watching the product:
 *
 *   the worker fills the manifest from note v1
 *   the doctor edits the note        -> soapFinal is v2
 *   the doctor downloads             -> the artifact is still v1
 *
 * and after signing, `native-export` refuses to recompute
 * (`visit_not_eligible`), so the stored bytes and `soapFinal` disagree
 * PERMANENTLY. The signed view also serves the stored bytes, so screen and
 * export agree with each other and BOTH disagree with the note — nothing on any
 * surface reveals that a signed PDF is missing the doctor's edits.
 *
 * Word carried this from the start. Routing the PDF onto the same artifact is
 * what made it visible.
 */
describe('note identity', () => {
  it('is stable for the same text and different for an edit', () => {
    const v1 = 'IMPRESSION: right GSV incompetent.';
    const v2 = 'IMPRESSION: LEFT GSV incompetent.';
    expect(noteIdentity(v1)).toBe(noteIdentity(v1));
    expect(noteIdentity(v1)).not.toBe(noteIdentity(v2));
  });

  it('⚠️ a ONE CHARACTER edit changes it — laterality is one character', () => {
    // The edit that matters clinically can be the smallest one there is.
    expect(noteIdentity('side: right')).not.toBe(noteIdentity('side: light'));
  });

  it('an absent note has NO identity — null, never a hash of ""', () => {
    expect(noteIdentity(null)).toBeNull();
    expect(noteIdentity(undefined)).toBeNull();
    expect(noteIdentity('')).toBeNull();
  });
});

describe('the serve gate', () => {
  const NOTE = 'IMPRESSION: right GSV incompetent, 6.2 mm.';
  const SHA = noteIdentity(NOTE)!;

  it('⚠️ SERVES when the manifest matches the current note', () => {
    // The positive control. A gate that refuses everything would pass every
    // refusal arm below and be strictly worse than the defect.
    expect(manifestMatchesNote(SHA, NOTE)).toEqual({ ok: true, reason: 'match' });
  });

  it('⚠️ DECLINES after the note is edited — the defect, pinned', () => {
    const edited = NOTE.replace('right', 'left');
    expect(manifestMatchesNote(SHA, edited)).toEqual({
      ok: false,
      reason: 'note_changed',
    });
  });

  it('⚠️ DECLINES a manifest written before the column existed', () => {
    // Fail-closed on UNPROVABLE, not just on WRONG. A pre-existing artifact
    // cannot say which note it came from, and "probably fine" here is a signed
    // record that silently disagrees with itself.
    expect(manifestMatchesNote(null, NOTE)).toEqual({
      ok: false,
      reason: 'manifest_note_unknown',
    });
    expect(manifestMatchesNote(undefined, NOTE)).toEqual({
      ok: false,
      reason: 'manifest_note_unknown',
    });
  });

  it('DECLINES when the visit has no note to compare against', () => {
    expect(manifestMatchesNote(SHA, null)).toEqual({
      ok: false,
      reason: 'visit_note_absent',
    });
  });

  it('⚠️ the three refusals are DISTINGUISHABLE — one reason each', () => {
    // A single catch-all would make "we cannot tell" and "it changed"
    // indistinguishable in the log, and those need different responses.
    const reasons = new Set([
      manifestMatchesNote(null, NOTE).reason,
      manifestMatchesNote(SHA, null).reason,
      manifestMatchesNote(SHA, 'different').reason,
    ]);
    expect(reasons.size).toBe(3);
  });
});

describe('the serve path and the write path use ONE derivation', () => {
  it('⚠️ native-export declines via manifestMatchesNote, not a local comparison', () => {
    const src = readFileSync(join(__dirname, '..', 'native-export.ts'), 'utf8');
    const code = src.split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
    expect(code).toMatch(/manifestMatchesNote\(/);
    expect(code).toMatch(/freshness\.ok/);
  });

  it('⚠️ fill-engine stamps via noteIdentity — the same function', () => {
    const src = readFileSync(join(__dirname, '..', 'fill-engine.ts'), 'utf8');
    const code = src.split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
    expect(code).toMatch(/noteSha256: noteIdentity\(input\.generatedNote\)/);
  });

  it('⚠️ the manifest lookup is PRACTICE-scoped, not user-scoped — ruling 2', () => {
    const src = readFileSync(join(__dirname, '..', 'native-export.ts'), 'utf8');
    const code = src.split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
    expect(code).toMatch(/visit: \{ practiceId, deletedAt: null \}/);
    // the per-user predicate is the divergence; it must not come back
    expect(code).not.toMatch(/visit: \{ userId, deletedAt: null \}/);
  });
});

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
