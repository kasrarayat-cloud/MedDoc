import { describe, expect, it } from 'vitest';
import {
  normalizeRefluxTimeUnit,
  renderStructureDirective,
  CHOICE_SLOT_DIRECTIVE,
} from '../build-soap-prompt';
import type { SectionStructure } from '../system-default-template';

describe('normalizeRefluxTimeUnit (BUG 1b — ms→seconds reconciliation)', () => {
  it('normalizes a reflux-time column header from ms to seconds', () => {
    expect(normalizeRefluxTimeUnit('REFLUX TIME (ms)')).toBe('REFLUX TIME (seconds)');
    expect(normalizeRefluxTimeUnit('REFLUX TIME (msec)')).toBe('REFLUX TIME (seconds)');
    expect(normalizeRefluxTimeUnit('Reflux (milliseconds)')).toBe('Reflux (seconds)');
    expect(normalizeRefluxTimeUnit('Reverse flow time (ms)')).toBe('Reverse flow time (seconds)');
  });
  it('normalizes a reflux threshold in prose from ms to seconds', () => {
    expect(
      normalizeRefluxTimeUnit('This study documents reflux as lasting more than 500 milliseconds in either vein.')
    ).toBe('This study documents reflux as lasting more than 0.5 seconds in either vein.');
    expect(normalizeRefluxTimeUnit('reflux more than 500 ms')).toBe('reflux more than 0.5 seconds');
  });
  it('does NOT touch non-reflux units or plain prose (narrow scope)', () => {
    expect(normalizeRefluxTimeUnit('DIAMETER (mm)')).toBe('DIAMETER (mm)'); // mm ≠ ms, no reflux
    expect(normalizeRefluxTimeUnit('The patient reports leg pain and swelling.')).toBe(
      'The patient reports leg pain and swelling.'
    );
    expect(normalizeRefluxTimeUnit('Procedure took more than 500 milliseconds.')).toBe(
      'Procedure took more than 500 milliseconds.' // no "reflux" context → untouched
    );
    expect(normalizeRefluxTimeUnit('')).toBe('');
  });
  it('is idempotent and a no-op on already-seconds text', () => {
    const once = normalizeRefluxTimeUnit('REFLUX TIME (ms)');
    expect(normalizeRefluxTimeUnit(once)).toBe(once);
    expect(normalizeRefluxTimeUnit('REFLUX TIME (seconds)')).toBe('REFLUX TIME (seconds)');
  });
});

describe('renderStructureDirective (BUG 1a/1b/1c — bare values, header unit, clean marker)', () => {
  const table: SectionStructure = {
    kind: 'table',
    columns: ['Vein', 'DIAMETER (mm)', 'REFLUX TIME (ms)'],
    rowLabels: ['GSV at the SFJ'],
  };
  it('renders the reflux header in seconds while leaving DIAMETER (mm) intact', () => {
    const out = renderStructureDirective(table);
    expect(out).toContain('REFLUX TIME (seconds)');
    expect(out).not.toContain('REFLUX TIME (ms)');
    expect(out).toContain('DIAMETER (mm)'); // untouched
  });
  it('instructs BARE values under a unit header (no doubled unit)', () => {
    const out = renderStructureDirective(table);
    expect(out).toMatch(/BARE value/);
    expect(out).toMatch(/never repeat the unit word/);
    expect(out).toMatch(/never write a unit the header does not name/);
  });
  it('provides a clean "—" marker for stated-normal segments (not prose in a cell)', () => {
    const out = renderStructureDirective(table);
    expect(out).toContain('"—"');
    expect(out).toMatch(/normal\/absent/);
    expect(out).toMatch(/Never put a phrase or a\s*\n?\s*sentence in a cell|Never put a phrase/);
  });
  it('applies the same discipline to the variable-row table shape', () => {
    const out = renderStructureDirective({ kind: 'table', columns: ['Vein', 'REFLUX TIME (ms)'] });
    expect(out).toContain('REFLUX TIME (seconds)');
    expect(out).toMatch(/BARE value/);
    expect(out).toContain('"—"');
  });
});

describe('CHOICE_SLOT_DIRECTIVE (BUG 2 — impression laterality + normal-omission)', () => {
  it('enforces per-side/subject grounding and forbids cross-leg fills', () => {
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/RIGHT leg must NEVER fill a LEFT carrier/i);
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/laterality is sacred/i);
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/never default to the first-listed option/i);
  });
  it('requires omitting an abnormal-only carrier for a normal side and not contradicting a fixed line', () => {
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/OMIT the entire carrier line/i);
    // (directive wraps across lines, so tolerate whitespace/newlines)
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/No saphenous reflux\s+in <side> lower extremity/i);
  });
  it('is BIDIRECTIONAL: drops the fixed no-reflux line for a REFLUX-POSITIVE side too', () => {
    // The reflux carrier and the fixed "No saphenous reflux…" line are mutually
    // exclusive alternatives — the abnormal side must DROP the fixed line, not
    // just the normal side dropping the carrier. Guards the latent right-leg
    // contradiction (right reflux-positive + fixed "No saphenous reflux in right").
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/MUTUALLY-EXCLUSIVE SIBLING LINES/i);
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/emit EXACTLY ONE per side/i);
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/never states\s+a finding AND its negation/i);
    // both directions present
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/dictates\s+saphenous reflux[\s\S]*DROP the fixed "No saphenous reflux/i);
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/normal \/ competent[\s\S]*KEEP that fixed line/i);
    // each leg resolved independently (bilateral studies commonly differ)
    expect(CHOICE_SLOT_DIRECTIVE).toMatch(/two legs commonly\s+differ/i);
  });
});
