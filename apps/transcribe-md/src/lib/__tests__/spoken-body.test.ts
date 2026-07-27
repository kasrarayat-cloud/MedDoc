// ============================================================================
// What a blind doctor HEARS is a clinical surface too.
// ----------------------------------------------------------------------------
// The document is drawn to a canvas, so the DOM copy of the note IS the reading
// order a screen reader uses. Every artifact the sighted surface kills has to
// die here as well, or the accessible path becomes the one that still shows
// markup — the worse failure, because nobody looks at it to notice.
//
// The header row is the specific trap, and it survived the first pass:
// claimProse rewrites a table row by reading that table's header, and a header
// has no header of its own, so it came back verbatim.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { spokenBody } from '@/lib/spoken-body';

const TABLE = [
  'DIAMETER AND REFLUX TIME — Right Leg',
  '| Segment | DIAMETER (mm) | REFLUX TIME (seconds) |',
  '| --- | --- | --- |',
  '| GSV at the SFJ | 6.2 | 3.4 |',
  '| SSV at the Proximal Calf | [not documented] | [not documented] |',
].join('\n');

const NOTE = ['## FINDINGS', TABLE].join('\n');

describe('spokenBody', () => {
  it('leaves NO pipe markup for a listener', () => {
    expect(spokenBody(TABLE, NOTE)).not.toMatch(/\|/);
  });

  it('drops the header row, not the data', () => {
    const out = spokenBody(TABLE, NOTE);
    expect(out).not.toContain('Segment');
    // The column names survive INSIDE each row, which is why dropping the
    // header loses nothing.
    expect(out).toContain('GSV at the SFJ: diameter 6.2 mm, reflux time 3.4 seconds');
  });

  it('says a row that documents nothing, rather than staying silent', () => {
    expect(spokenBody(TABLE, NOTE)).toContain('SSV at the Proximal Calf: nothing documented');
  });

  it('keeps the caption — it carries the laterality', () => {
    expect(spokenBody(TABLE, NOTE)).toContain('Right Leg');
  });

  it('substitutes the set-aside marker instead of dropping it', () => {
    const marker =
      '_[All AI-drafted content for this section was set aside for your review — see the suggestions below and adopt before signing.]_';
    const out = spokenBody(marker, marker);
    expect(out).not.toContain('All AI-drafted content');
    expect(out).toContain('Set aside for your review');
  });

  it('an empty section reads the way the drawn page does', () => {
    expect(spokenBody('   ', '')).toBe('Not documented.');
  });

  it('leaves ordinary prose completely alone', () => {
    const prose = 'Right great saphenous vein is reflux positive.';
    expect(spokenBody(prose, prose)).toBe(prose);
  });

  it('a pipe row with NO alignment rule under it is not treated as a header', () => {
    // Defensive: a header is only dropped when it actually heads a table.
    const orphan = '| not really a table |';
    expect(spokenBody(orphan, orphan)).toContain('not really a table');
  });
});
