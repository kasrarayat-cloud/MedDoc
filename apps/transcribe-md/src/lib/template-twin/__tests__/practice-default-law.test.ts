// ============================================================================
// PRACTICE-DEFAULT LAW — nothing may set APPROVED_PRACTICE_DEFAULT yet.
// ----------------------------------------------------------------------------
// The audit finding this pins: a practice default is injected at visit time as
// an EncounterFact with quality.evidence 'direct', and a VALID one then renders
// as an ordinary populated value. Validation is rigorous about its PROVENANCE
// (PRACTICE_DEFAULT_INVALID checks fact id, anchor, exact value, null transcript
// offsets, null audio timestamps) — but nothing routes it to a flagged /
// set-aside lane. So it can place content the clinician never said into a
// signed note, distinguishable only by `sourceType` deep inside the manifest.
//
// Until that lane exists the capability stays shut, and it must fail LOUDLY.
// Silently coercing to null would leave the caller believing a default was
// stored — the same class of silence this system has spent the week retiring.
//
// Source-level, deliberately: the guard lives inside a Prisma $transaction, so
// a behavioural test would need the whole DB stack to assert one refusal, and
// would still pass on the day someone deletes the guard but leaves the schema
// permissive. What matters is that the refusal EXISTS and stays wired to the
// only write path.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const LIFECYCLE = join(__dirname, '..', 'certification-lifecycle.ts');
const raw = readFileSync(LIFECYCLE, 'utf-8');
const src = raw.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

describe('practice-default law', () => {
  it('refuses any mapping carrying a non-null practiceDefault', () => {
    expect(
      src,
      'the guard that blocks APPROVED_PRACTICE_DEFAULT is gone — a standing ' +
        'default can now assert unsaid clinical content into a signed note'
    ).toMatch(/practiceDefault !== null/);
    expect(src).toMatch(/Practice defaults are not available yet/);
  });

  it('THROWS rather than silently coercing the value away', () => {
    // A silent `practiceDefault: null` coercion would be worse than the
    // capability: the caller would believe a default was saved.
    const guard = src.slice(src.indexOf('practiceDefault !== null'));
    expect(guard.slice(0, 900)).toMatch(/throw new TemplateTwinLifecycleError/);
  });

  it('guards the ONLY path that persists a non-null practiceDefault', () => {
    // Everything else in the twin writes a literal null; the proposal schema
    // pins z.null(). If a second write path appears, this count changes and
    // the guard must be extended to cover it.
    const writes = [...src.matchAll(/practiceDefault:\s*mapping\.practiceDefault/g)];
    expect(
      writes.length,
      'a new persistence path for practiceDefault appeared — extend the guard'
    ).toBe(1);
  });

  it('the guard runs BEFORE the write', () => {
    const guardAt = src.indexOf('practiceDefault !== null');
    const writeAt = src.indexOf('practiceDefault: mapping.practiceDefault');
    expect(guardAt).toBeGreaterThan(-1);
    expect(writeAt).toBeGreaterThan(guardAt);
  });
});

describe('practice-default law — the proposal path cannot introduce one', () => {
  it('semantic-mapping pins practiceDefault to null in the proposal schema', () => {
    const mapping = readFileSync(
      join(__dirname, '..', 'semantic-mapping', 'index.ts'),
      'utf-8'
    );
    expect(mapping).toMatch(/practiceDefault:\s*z\.null\(\)/);
  });
});
