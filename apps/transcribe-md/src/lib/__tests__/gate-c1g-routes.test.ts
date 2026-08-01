// ============================================================================
// C1-g — a link is a claim that a route exists, and nothing was checking it.
// ----------------------------------------------------------------------------
// `/settings/note-format` was linked from the Rounds nav (`board-chrome.tsx`)
// and from the certified-template EMAIL (`lib/email.ts`), and it 404'd. The
// email link is the sharp one: it goes to a real doctor's inbox, and
// `template-certified-email.test.ts` pinned it — but that test asserts the
// STRING appears in the payload. A string assertion about a URL says nothing
// about whether the URL resolves, so the guard and the defect coexisted.
//
// The directory made it easy to miss: `src/app/settings/note-format/` has
// existed all along holding this feature's components, so `ls` shows a folder
// while Next, which routes on `page.tsx`, serves nothing.
//
// So this checks the claim rather than the spelling: every in-app `/settings/*`
// path any source file links to must resolve to a real route segment. Derived
// by traversal from the source, never from a list kept here — a maintained list
// of links is exactly what would have missed these two.
// ============================================================================

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = 'src/app';

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === 'node_modules' || e.name === '__tests__') continue;
      out.push(...walk(p));
    } else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

const SOURCES = walk('src').filter((f) => !/\.test\.tsx?$/.test(f));

/** Blank comments so a path discussed in prose is not read as a live link —
 *  the trap that made a guard fabricate its own finding twice in C1-f. */
const blankComments = (s: string) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/\/\/[^\n]*/g, (m) => ' '.repeat(m.length));

/** Every `/settings/...` path this codebase links to, with the file that does
 *  it. Matches both `href="/settings/x"` and a template-literal URL ending in
 *  `/settings/x`, which is the shape `email.ts` uses. */
function linkedSettingsPaths(): Map<string, string[]> {
  const found = new Map<string, string[]>();
  for (const f of SOURCES) {
    const src = blankComments(readFileSync(f, 'utf8'));
    for (const m of src.matchAll(/['"`](?:\$\{[^}]*\})?(\/settings\/[a-z0-9/-]+)['"`]/gi)) {
      const path = m[1].replace(/\/+$/, '');
      found.set(path, [...(found.get(path) ?? []), f]);
    }
  }
  return found;
}

/** Does `path` resolve to a route segment? A segment is a directory under
 *  `src/app` containing `page.tsx`. Dynamic segments (`[id]`) count for a
 *  concrete path only if no literal directory matches. */
function routeExists(path: string): boolean {
  const parts = path.replace(/^\//, '').split('/');
  let dir = APP;
  for (const part of parts) {
    const literal = join(dir, part);
    if (existsSync(literal)) {
      dir = literal;
      continue;
    }
    const dynamic = readdirSync(dir, { withFileTypes: true }).find(
      (e) => e.isDirectory() && /^\[.*\]$/.test(e.name),
    );
    if (!dynamic) return false;
    dir = join(dir, dynamic.name);
  }
  return existsSync(join(dir, 'page.tsx'));
}

describe('C1-g — every linked /settings route exists', () => {
  const linked = linkedSettingsPaths();

  it('the traversal finds the links — positive control', () => {
    // Without this a broken walk returns an empty map and the assertion below
    // passes by checking nothing.
    expect(SOURCES.length, 'the source traversal returned nothing').toBeGreaterThan(100);
    expect(
      [...linked.keys()],
      'the two links this item exists for are not being seen by the matcher',
    ).toContain('/settings/note-format');
    expect([...linked.keys()]).toContain('/settings/security/mfa');
  });

  it('the route resolver can say NO — negative control', () => {
    // A resolver that returns true for everything would make this suite green
    // over a site of 404s.
    expect(routeExists('/settings/definitely-not-a-segment')).toBe(false);
    expect(routeExists('/settings')).toBe(true);
  });

  it('every linked /settings path resolves to a real route segment', () => {
    const broken: string[] = [];
    for (const [path, files] of linked) {
      if (!routeExists(path)) broken.push(`${path}  ← ${[...new Set(files)].join(', ')}`);
    }
    expect(
      broken,
      'these paths are LINKED but no `page.tsx` serves them, so the doctor gets ' +
        'a 404. One of them was reached from an email already in an inbox, which ' +
        'is why the route is the side that gets fixed:\n  ' + broken.join('\n  '),
    ).toEqual([]);
  });
});

describe('C1-g — the surface stops describing shipped work as unbuilt', () => {
  const PAGE = blankComments(readFileSync('src/app/settings/page.tsx', 'utf8'));
  const flat = PAGE.replace(/\s+/g, ' ');

  it('the 2FA card no longer says the feature is coming', () => {
    // It shipped at /settings/security/mfa. The card said otherwise for months,
    // in BOTH branches of this file — and a restyle would have set the lie in
    // new type rather than removing it.
    expect(flat, 'the 2FA roadmap promise is back').not.toContain(
      'lands in the next batch of Settings work',
    );
    expect(flat, 'the billing roadmap promise is back').not.toContain(
      'lands in the next Settings wave',
    );
  });

  it('…and BOTH branches carry a door to it', () => {
    // `isSkinBeta()` forks this file: production renders the C3 rail, and the
    // required chromium E2E gate builds SKIN_BETA=false and renders the legacy
    // stack. Fixing one branch fixes the surface nobody is looking at.
    const doors = flat.split('/settings/security/mfa').length - 1;
    expect(
      doors,
      'the MFA route is reachable only by a typed URL and the admin redirect ' +
        'unless BOTH settings branches link to it',
    ).toBe(2);
  });

  it('the billing button is still disabled — the copy changed, not the capability', () => {
    expect(flat, 'the permanently-disabled billing button lost its `disabled`').toMatch(
      /Billing is handled for you during the pilot/,
    );
    expect(PAGE).toMatch(/disabled/);
  });
});

describe('C1-g — the section preselect cannot land on nothing', () => {
  const RAIL = readFileSync('src/app/settings/settings-sections-c3.tsx', 'utf8');

  it('an unknown section id falls back instead of opening an empty column', () => {
    // The value arrives from a URL path. All seven panels stay mounted with
    // `hidden`, so an id matching no panel renders the rail above nothing and
    // throws nothing — a silent blank page.
    expect(RAIL, 'initialSection is used without being validated').toMatch(
      /sections\.some\(\s*\(s\)\s*=>\s*s\.id === initialSection\s*\)/,
    );
  });

  it('the route segment passes a section that actually exists', () => {
    const seg = readFileSync('src/app/settings/note-format/page.tsx', 'utf8');
    const m = seg.match(/initialSection="([a-z0-9-]+)"/);
    expect(m, 'the segment does not preselect a section').not.toBeNull();
    const page = readFileSync('src/app/settings/page.tsx', 'utf8');
    expect(
      page,
      `the segment preselects "${m?.[1]}" but no section declares that id`,
    ).toContain(`id: '${m![1]}'`);
  });
});
