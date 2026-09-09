import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { VISIT_PREVIEW_MISSES } from '@/lib/visit-preview-misses';

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
  // ⚠️ THE TYPE ANNOTATION IS NOT PART OF THE SUBJECT, so the matcher must not
  // depend on its shape. It pinned `Record<string, string>` exactly, and
  // TIGHTENING that annotation — the very fix that makes a missing key a
  // compile error — broke the parser, which then reported "cannot see its
  // subject" for all nine arms. The non-vacuity arm caught it, which is the
  // only reason this is a comment and not a silent zero.
  const block = SRC.match(/const MISS_TEXT[^=]*=\s*\{([\s\S]*?)\n\};/);
  if (!block) throw new Error('MISS_TEXT literal not found — the gate cannot see its subject');
  const out: Record<string, string> = {};
  // strip comment lines so prose inside the literal cannot be read as a value
  const body = block[1]
    .split('\n')
    .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
    .join('\n');
  for (const m of body.matchAll(/(\w+):\s*((?:'[^']*'(?:\s*\+\s*)?)+)/g)) {
    out[m[1]] = m[2].replace(/'\s*\+\s*'/g, '').replace(/^'|'$/g, '');
  }
  return out;
}

// ⚠️ DERIVED FROM THE SHIPPED LIST, NOT RESTATED — AND THIS ARM IS WHY.
// `ACTIONABLE` was a hand-written literal of four. `no_tenant_template` (#287)
// joined the union, was invisible here, and the gate stayed 8 of 8 GREEN while
// the new miss rendered NOTHING to the doctor — deleting an explanation `main`
// had given. A list a test RESTATES goes stale; a list it ITERATES cannot.
//
// INERT is the only hand-kept half, and deliberately: "there is nothing for the
// doctor to do" is a judgement about a specific miss, not something derivable.
// Everything not named inert is actionable BY DEFAULT, so the failure mode of
// forgetting to classify a new miss is a RED, not a silence.
const INERT: readonly string[] = ['not_template_visit'];
const ACTIONABLE = [
  ...VISIT_PREVIEW_MISSES.filter((m) => !INERT.includes(m)),
  // `sample_unavailable` is a NativePreviewError, not a miss — this surface
  // speaks it, so it is asserted here by name.
  'sample_unavailable',
] as const;

describe('visit-document-surface MISS_TEXT', () => {
  it('is parsed non-vacuously — the gate can see its own subject', () => {
    const keys = missKeys();
    expect(Object.keys(keys).length).toBeGreaterThanOrEqual(5);
  });

  it('⚠️ THE WATCHED SET IS THE SHIPPED SET — every miss is classified', () => {
    // The arm that would have caught #287's silent reason. If a new member of
    // `VISIT_PREVIEW_MISSES` is neither inert nor spoken, it reds HERE rather
    // than rendering nothing on a doctor's screen.
    const keys = missKeys();
    const unclassified = VISIT_PREVIEW_MISSES.filter(
      (m) => !INERT.includes(m) && !keys[m]?.trim(),
    );
    expect(
      unclassified,
      'a shipped miss has no MISS_TEXT and is not declared inert — it would ' +
        'render a blank banner, which the render site calls illegal',
    ).toEqual([]);
    // NON-VACUITY: the derived list must be the real one, not an empty import.
    expect(VISIT_PREVIEW_MISSES.length).toBeGreaterThanOrEqual(5);
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
