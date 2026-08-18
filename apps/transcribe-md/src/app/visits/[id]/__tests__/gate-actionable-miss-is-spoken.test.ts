import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * A MISS THE DOCTOR CAN ACT ON MUST NOT BE SILENT.
 *
 * `not_certified` shipped as the empty string while the banner is gated on
 * truthiness, so the one fallback with a cure rendered nothing. The render
 * site's own comment says "Silence is illegal" — this pins that claim to the
 * data instead of the prose.
 *
 * ⚠️ THE SPLIT IS THE POINT, so the gate asserts BOTH directions:
 *   actionable  (not_certified, no_render, fill_failed, sample_unavailable) → MUST speak
 *   inert       (not_template_visit)                                       → MUST stay silent
 * A gate that only demanded "non-empty" would force text onto a miss the
 * doctor can do nothing about, which is noise, not honesty.
 */
const SRC = readFileSync(
  join(__dirname, '..', 'visit-document-surface.tsx'),
  'utf8',
);

/** The literal map as shipped — parsed from source, never re-declared here. */
function missKeys(): Record<string, string> {
  const block = SRC.match(/const MISS_TEXT: Record<string, string> = \{([\s\S]*?)\n\};/);
  if (!block) throw new Error('MISS_TEXT literal not found — the gate cannot see its subject');
  const out: Record<string, string> = {};
  // strip comment lines so prose inside the literal cannot be read as a value
  const body = block[1].split('\n').filter((l) => !l.trim().startsWith('//')).join('\n');
  for (const m of body.matchAll(/(\w+):\s*((?:'[^']*'(?:\s*\+\s*)?)+)/g)) {
    out[m[1]] = m[2].replace(/'\s*\+\s*'/g, '').replace(/^'|'$/g, '');
  }
  return out;
}

const ACTIONABLE = ['not_certified', 'no_render', 'fill_failed', 'sample_unavailable'] as const;
const INERT = ['not_template_visit'] as const;

describe('visit-document-surface MISS_TEXT', () => {
  it('is parsed non-vacuously — the gate can see its own subject', () => {
    const keys = missKeys();
    expect(Object.keys(keys).length).toBeGreaterThanOrEqual(5);
  });

  it.each(ACTIONABLE)('%s speaks — an actionable miss is never silent', (k) => {
    const v = missKeys()[k];
    expect(v, `${k} is missing from MISS_TEXT`).toBeDefined();
    expect(v.trim(), `${k} is EMPTY — the banner is truthiness-gated, so it renders nothing`).not.toBe('');
    expect(v.length).toBeGreaterThan(20);
  });

  it.each(INERT)('%s stays silent — nothing for the doctor to do', (k) => {
    expect(missKeys()[k]).toBe('');
  });

  it('not_certified names the CURE, not just the miss', () => {
    const v = missKeys().not_certified;
    // it must point at the door that exists: Settings › My Note Format › Confirm fields
    expect(v).toMatch(/Settings/);
    expect(v).toMatch(/Confirm fields/i);
  });

  it('does not send a doctor who already uploaded back to upload again', () => {
    expect(SRC).not.toMatch(/upload your own blank form/);
  });
});
