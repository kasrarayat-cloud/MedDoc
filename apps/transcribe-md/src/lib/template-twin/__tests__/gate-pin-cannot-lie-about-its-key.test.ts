import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * ⚠️ THE PIN MUST NOT LIE ABOUT WHAT IT HOLDS.
 *
 * Measured in production on 2026-08-20, on the owner's real template:
 *
 *   pinnedNoteEncounterSha256 : a3b63b2dda4f   ← the NEW encounter
 *   pinnedNoteGeneratedAt     : 2026-08-18T23:19:50Z
 *   note contains any diameter dictation : FALSE
 *   note contains the OLD encounter's marker ("Heaviness") : TRUE
 *
 * A note generated two days before the encounter it was keyed to existed. The
 * certification proof ran against it, filled 5 of the required 10, and refused —
 * and the refusal read as "your form does not fill" when the truth was "the
 * model never saw this encounter".
 *
 * TWO defects composed, and neither is sufficient alone:
 *
 *   :376  `pinValid = !!pinned`   — the invalidation block correctly identifies
 *         a mismatched note, fails to find a sibling, and then falls through
 *         USING IT. Presence was treated as validity.
 *
 *   :408  the EXTRACTION pin wrote `pinnedNoteEncounterSha256` — the NOTE's key.
 *         One column keys both pins, so pinning a fresh extraction under a new
 *         encounter RE-KEYED the old note to it. A write-on-read. Thereafter the
 *         shas compare equal and invalidation never runs again.
 *
 * This gate is a SOURCE gate on purpose. The lie is a persistence effect across
 * two updates and a reload; reproducing it in-process would need the whole
 * Prisma+model stack, and a mock of that stack is exactly the thing that could
 * not see the defect in the first place.
 */
const SRC = readFileSync(
  join(__dirname, '..', 'synthetic-test.ts'),
  'utf8',
);

// Comments discuss both defects at length; a prose-matching scan would pass on
// its own documentation. This is the recorded substring trap.
const CODE = SRC.split('\n')
  .filter((l) => {
    const t = l.trim();
    return !t.startsWith('//') && !t.startsWith('*') && !t.startsWith('/*');
  })
  .join('\n');

describe('the pin cannot hold old content under a new key', () => {
  it('the scan is non-vacuous — it found the pin machinery', () => {
    expect(CODE).toMatch(/pinnedNoteEncounterSha256/);
    expect(CODE).toMatch(/const pinValid/);
  });

  it('⚠️ presence is NOT validity — pinValid consults the KEY', () => {
    const line = CODE.split('\n').find((l) => l.includes('const pinValid'))!;
    expect(line, 'pinValid must not be a bare truthiness test on the note').not.toMatch(
      /const pinValid = !!pinned;\s*$/,
    );
    expect(line).toMatch(/noteKeyMatches|adoptedFromSibling/);
  });

  it('⚠️ noteKeyMatches compares BOTH shas, not just the encounter', () => {
    const i = CODE.indexOf('const noteKeyMatches');
    expect(i).toBeGreaterThan(-1);
    const block = CODE.slice(i, i + 260);
    expect(block).toMatch(/pinnedNoteEncounterSha256 === encounterSha256/);
    expect(block).toMatch(/pinnedNoteTemplateSha256 === templateSha256/);
  });

  it('⚠️ THE WRITE-ON-READ: any update that re-keys the note must also DROP it', () => {
    // Every statement that writes the note's key while the note itself is not
    // being (re)generated must null the note in the same statement.
    const updates = CODE.split('prisma.templateTwinCompiledVersion.update(')
      .slice(1)
      .map((chunk) => chunk.slice(0, 700))
      .filter((chunk) => chunk.includes('pinnedNoteEncounterSha256'));

    expect(updates.length, 'no key-writing update found — scan is broken').toBeGreaterThan(0);

    for (const u of updates) {
      const writesNote =
        /pinnedSyntheticNote:\s*(?!null)/.test(u) || u.includes('pinnedSyntheticNote: pinned');
      const dropsNote = u.includes('pinnedSyntheticNote: null');
      expect(
        writesNote || dropsNote,
        'an update re-keys the note without writing or dropping it — ' +
          'that is the 2026-08-20 write-on-read:\n' + u.slice(0, 300),
      ).toBe(true);
    }
  });

  it('the extraction pin drops the note it cannot vouch for', () => {
    const i = CODE.indexOf('pinnedSyntheticEntities: asJson(');
    expect(i).toBeGreaterThan(-1);
    const block = CODE.slice(i, i + 600);
    expect(block).toMatch(/pinValid/);
    expect(block).toMatch(/pinnedSyntheticNote: null/);
    expect(block).toMatch(/pinnedNoteGeneratedAt: null/);
  });

  it('⚠️ a generated note stamps its OWN encounter, and that write keeps the note', () => {
    // The one legitimate place the key is stamped: alongside the note it was
    // generated from.
    const gen = CODE.split('prisma.templateTwinCompiledVersion.update(')
      .slice(1)
      .find((c) => c.includes('pinnedSyntheticNote:') && !c.includes('pinnedSyntheticNote: null'));
    expect(gen, 'no update writes a note at all').toBeDefined();
    expect(gen!).toMatch(/pinnedNoteEncounterSha256: encounterSha256/);
  });
});
