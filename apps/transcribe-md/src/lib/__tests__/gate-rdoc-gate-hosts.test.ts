// ============================================================================
// EVERY `.qm-rdoc-gate` ROOT CARRIES THE ROUNDS BRIDGE — a CENSUS, not a list.
//
// `.qm-rdoc-gate` paints its border and background from `--color-linear-amber`
// (globals.css :5546). Only `[data-skin='rounds'] .qm-rounds-host` redeclares
// that token. A gate panel rendered outside a host therefore keeps the LEGACY
// amber and shows as a CREAM CARD on a dark Rounds route.
//
// ⚠️ WHY THIS IS A CENSUS AND NOT FOUR ASSERTIONS. R4b enumerated the family
// and fixed the one member it found. `PrescriptionsCard` was then born during
// R5 — AFTER that enumeration — and shipped unhosted, rendering cream directly
// above the panel R4b had just fixed. The owner found it in a screenshot.
// Nobody was careless: the member did not exist when the list was written.
// That is the failure mode of every hand-kept list, and the only cure is a
// check that DERIVES the set instead of restating it.
//
// So this test does not name the components. It finds them.
// ============================================================================
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '../..');

function tsxFiles(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = path.join(dir, e);
    if (e === 'node_modules' || e === '__tests__') continue;
    if (statSync(p).isDirectory()) tsxFiles(p, out);
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

/** Every `className={...}` / `className="..."` value in a file, as raw text. */
function classNameValues(src: string): string[] {
  const out: string[] = [];
  const re = /className=(?:"([^"]*)"|\{`([^`]*)`\})/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) out.push(m[1] ?? m[2] ?? '');
  return out;
}

/**
 * ⚠️ EXACT TOKEN, NEVER `includes`. `qm-rdoc-gate-head`, `-body`, `-text`,
 * `-btn` and `-quiet` all CONTAIN `qm-rdoc-gate`, and a substring test would
 * class every one of them as a root and demand a bridge on a table cell. This
 * repo has shipped that mistake four times in other shapes; it is a named
 * family in AGENTS.md.
 */
function tokens(value: string): string[] {
  // Drop `${...}` interpolations — a conditional suffix is not a class name.
  return value.replace(/\$\{[^}]*\}/g, ' ').split(/\s+/).filter(Boolean);
}

const GATE = 'qm-rdoc-gate';
const HOST = 'qm-rounds-host';

describe('the .qm-rdoc-gate family — every root carries the Rounds bridge', () => {
  const files = tsxFiles(SRC);

  // Sort EVERY className the scan meets into a named bucket, and reconcile the
  // total. Anything that fits no bucket is the finding — the shape nobody
  // predicted is exactly what this census exists to surface.
  const rootsHosted: string[] = [];
  const rootsUnhosted: string[] = [];
  let descendantOnly = 0;
  let unrelated = 0;

  for (const f of files) {
    for (const value of classNameValues(readFileSync(f, 'utf8'))) {
      const t = tokens(value);
      const isRoot = t.includes(GATE);
      const mentionsFamily = t.some((c) => c.startsWith(GATE));
      const where = `${path.relative(SRC, f)} :: ${value.slice(0, 60)}`;
      if (isRoot) (t.includes(HOST) ? rootsHosted : rootsUnhosted).push(where);
      else if (mentionsFamily) descendantOnly += 1;
      else unrelated += 1;
    }
  }

  it('finds the family at all — the scan is not vacuous', () => {
    // A census that silently matches nothing reports a perfect zero. Both the
    // roots and the descendants must be non-empty, and the file walk must have
    // actually walked.
    expect(files.length, 'the .tsx walk found no files').toBeGreaterThan(50);
    expect(
      rootsHosted.length + rootsUnhosted.length,
      'no .qm-rdoc-gate ROOT found anywhere — the matcher is broken, not the app',
    ).toBeGreaterThanOrEqual(4);
    expect(descendantOnly, 'no -head/-body/-text descendants found').toBeGreaterThan(0);
    expect(unrelated, 'no unrelated classNames — the walk is too narrow').toBeGreaterThan(0);
  });

  it('EVERY root carries qm-rounds-host', () => {
    expect(
      rootsUnhosted,
      'these .qm-rdoc-gate roots render OUTSIDE a Rounds host, so they paint ' +
        'legacy amber and show as cream cards on a dark route. Put ' +
        `\`${HOST}\` on the root element itself — on the COMPONENT, never on ` +
        'its callers, or the next mount is the one nobody remembers.',
    ).toEqual([]);
  });

  it('the matcher can tell a root from a descendant, and would FAIL an unhosted root', () => {
    // POSITIVE CONTROLS. A guard proven only in the green direction is not
    // proven: this asserts the classifier separates the two shapes it depends
    // on, and that a synthetic regression lands in the bucket that fails.
    expect(tokens('qm-rdoc-gate qm-rdoc-gate-quiet').includes(GATE)).toBe(true);
    expect(tokens('qm-rdoc-gate-head').includes(GATE)).toBe(false);
    expect(tokens('qm-rdoc-gate-body').includes(GATE)).toBe(false);
    // A template-literal root with a conditional suffix is still a root.
    expect(tokens('qm-rounds-host qm-rdoc-gate qm-rdoc-gate-em${x}').includes(GATE)).toBe(true);
    // The regression shape: a root without the bridge.
    const synthetic = tokens('qm-rdoc-gate qm-rdoc-gate-em');
    expect(synthetic.includes(GATE) && !synthetic.includes(HOST)).toBe(true);
  });
});
