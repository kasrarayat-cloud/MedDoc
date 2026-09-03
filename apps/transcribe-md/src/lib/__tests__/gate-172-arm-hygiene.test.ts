// ============================================================================
// #172(5) — CANON 62's FOURTH INSTANCE GETS A MECHANISM, NOT A FIFTH SWEEP.
// ----------------------------------------------------------------------------
// ⚠️ THE ARGUMENT IS A COUNT. The "unscoped find on a non-unique predicate"
// laundering was found and fixed FOUR times in one arc — twice in the renderer
// suite, twice in the product suite — and the fourth instance was live in the
// very arm that had just been re-armed for the third, in a file whose own
// header states the rule 650 lines above. Writing a rule down is not obeying
// it; that is already canon, and it is why this is a test.
//
// ⚠️ AND YES, THIS IS A SOURCE-TEXT GATE, WHICH CANON 72 WARNS ABOUT. The
// warning is against pinning a SPELLING when the property is behavioural. Here
// the property IS a source shape — "this call selects one of many matches and
// then reasons about it as though it were the only one" — and there is no
// runtime observable for it. A lint is the right instrument for a lint.
// ============================================================================
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = resolve(__dirname, '..', '..', '..');
const REPO = resolve(APP, '..', '..');

/** Test files whose forgeries and selections this rule governs. */
const GATE_DIRS = [
  join(APP, 'src', 'lib', 'note-template-docx', '__tests__'),
  join(APP, 'src', 'lib', 'template-twin', '__tests__'),
];

/**
 * `.find(...)` whose predicate tests `.kind` — a LABEL CLASS, never a key.
 *
 * Unique-key selections (`f.fieldId === id`, `f.originalLabel === label`) are
 * deliberately NOT matched: they select one thing because one thing exists.
 */
const KIND_FIND = /\.find\(\s*\([^)]*\)\s*=>[^;]*?\.kind\s*===/;

describe('#172(5) — no bare find() on a label class in the gate suites', () => {
  it('every gate file is clean', () => {
    const offenders: string[] = [];
    let scanned = 0;
    for (const dir of GATE_DIRS) {
      for (const name of readdirSync(dir)) {
        if (!name.endsWith('.test.ts')) continue;
        scanned += 1;
        const text = readFileSync(join(dir, name), 'utf8');
        text.split('\n').forEach((line, index) => {
          if (KIND_FIND.test(line)) offenders.push(`${name}:${index + 1}  ${line.trim()}`);
        });
      }
    }
    // ⚠️ POSITIVE CONTROL BEFORE ANY ZERO IS BELIEVED. A glob that matched no
    // files would report a perfectly clean suite, and that zero is
    // indistinguishable from health.
    expect(scanned, 'the scan found no gate files — refusing to read that as clean').
      toBeGreaterThan(10);
    // ⚠️ AND THE PATTERN MUST BE ABLE TO FIRE. If this ever stops matching, the
    // gate silently becomes a no-op.
    expect(KIND_FIND.test("const x = list.find((f) => f.kind === 'filled');")).toBe(true);
    expect(KIND_FIND.test('const x = list.find((f) => f.fieldId === id);')).toBe(false);

    expect(
      offenders,
      'a bare find() on `kind` selects one of many matches and then reasons ' +
        'about it as the only one. Scope it (filter + an explicit count) or use ' +
        '`theOnlyMatch`, which refuses ambiguity.',
    ).toEqual([]);
  });
});

describe('#172(5) — every canon BODY has its INDEX ROW', () => {
  it('nothing checks that — now something does', () => {
    // ⚠️ THE RULE HAS EXISTED ALL ALONG AND WAS MISSED IN THIS VERY ARC: canon
    // 94's body landed and its index row did not, caught only by re-reading the
    // commit. An entry whose row is missing is an entry a grep of the index
    // cannot reach — the exact pointer failure the index exists to prevent.
    const agents = readFileSync(join(REPO, 'AGENTS.md'), 'utf8');
    const bodies = readdirSync(join(REPO, 'docs', 'canon'))
      .filter((n) => /^\d+-.*\.md$/.test(n))
      .sort();
    expect(bodies.length, 'no canon bodies found — the scan is broken').toBeGreaterThan(50);
    const missing = bodies.filter((n) => !agents.includes(n));
    expect(
      missing,
      'these canon entries have a body and no index row, so a grep of the ' +
        'index cannot find them',
    ).toEqual([]);
  });
});
