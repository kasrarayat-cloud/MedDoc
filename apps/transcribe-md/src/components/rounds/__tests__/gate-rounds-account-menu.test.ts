// ============================================================================
// The Rounds bar has an account menu, on EVERY mount, with a sign-out in it.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE THE SKIN SHIPPED WITHOUT A WAY TO SIGN OUT, AND
// BECAUSE THE LAST TIME A SHARED COMPONENT WAS GIVEN NEW BEHAVIOUR IT WAS
// GIVEN TO ONE OF ITS THREE MOUNTS.
//
// Two defects, one lesson. R3.4 hosted ONE of `RxTab`'s three mount sites and
// verified it there — correctly, and incompletely; the other two rendered the
// legacy panel on a Rounds route for two rounds. AGENTS.md § "Shared
// components" records the cure: put the behaviour ON the component, and where
// a per-caller list is unavoidable, make the missing case FAIL A TEST rather
// than render quietly.
//
// So this file asserts the two things a class census cannot see:
//   • the menu lives on `RoundsTopBar`, not on its callers — so every present
//     and future mount inherits it
//   • the MOUNT COUNT: every `<RoundsTopBar` in the tree passes `userName`
//
// WHAT WOULD MAKE THIS FAIL (all four proven by mutation before commit):
//   • moving the menu back out to a caller
//   • adding a third `RoundsTopBar` mount without `userName`
//   • removing the sign-out item from the menu
//   • renaming the accessible label the E2E helper searches by
// ============================================================================

import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import { describe, it, expect } from 'vitest';

const ROUNDS_DIR = 'src/components/rounds';
const TOP_BAR = readFileSync(join(ROUNDS_DIR, 'top-bar.tsx'), 'utf8');
const MENU = readFileSync(join(ROUNDS_DIR, 'account-menu.tsx'), 'utf8');

const stripComments = (s: string) =>
  s.replace(/\{\/\*[\s\S]*?\*\/\}/g, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

const TOP_BAR_CODE = stripComments(TOP_BAR);
const MENU_CODE = stripComments(MENU);

/** Every file in the app that mounts `<RoundsTopBar`. */
function mountSites(): { file: string; tag: string }[] {
  const out: { file: string; tag: string }[] = [];
  const walk = (dir: string) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, e.name);
      if (e.isDirectory()) {
        if (e.name === '__tests__' || e.name === 'node_modules') continue;
        walk(p);
        continue;
      }
      if (!e.name.endsWith('.tsx')) continue;
      if (p.endsWith('top-bar.tsx')) continue; // the definition, not a mount
      const src = stripComments(readFileSync(p, 'utf8'));
      for (const m of src.matchAll(/<RoundsTopBar[^>]*>/g)) out.push({ file: p, tag: m[0] });
    }
  };
  walk('src');
  return out;
}

describe('the Rounds account menu is on the COMPONENT', () => {
  it('NON-VACUITY — the sources parsed to something real', () => {
    expect(TOP_BAR_CODE.length).toBeGreaterThan(500);
    expect(MENU_CODE.length).toBeGreaterThan(500);
    expect(TOP_BAR_CODE).toContain('export function RoundsTopBar');
  });

  it('RoundsTopBar renders the menu itself, from a userName PROP', () => {
    expect(TOP_BAR_CODE).toMatch(/import \{ RoundsAccountMenu \} from '\.\/account-menu';/);
    expect(TOP_BAR_CODE).toMatch(/userName\?:\s*string;/);
    expect(TOP_BAR_CODE).toMatch(
      /userName \? <RoundsAccountMenu userName=\{userName\} \/> : null/,
    );
  });

  it('no caller renders its own name span any more', () => {
    // The two duplicated copies this replaced. `.qm-rounds-topbar-who` is kept
    // as a CSS class (other surfaces may want a quiet name label) but nothing
    // in the tree may mount it inside a RoundsTopBar again.
    for (const { file } of mountSites()) {
      const src = stripComments(readFileSync(file, 'utf8'));
      expect(src, `${file} still renders its own name span inside the bar`).not.toContain(
        'qm-rounds-topbar-who',
      );
    }
  });
});

describe('MOUNT COUNT — every mount gets the menu', () => {
  it('there are mounts to check at all', () => {
    // A walker that silently found nothing would make the next test pass over
    // an empty set — the emptiness-test defect, in a new place.
    expect(mountSites().length).toBeGreaterThanOrEqual(2);
  });

  it('EVERY <RoundsTopBar mount passes userName', () => {
    const missing = mountSites()
      .filter((m) => !/\buserName=/.test(m.tag))
      .map((m) => `${m.file} → ${m.tag}`);
    expect(
      missing,
      'these mounts render the Rounds bar with no userName, so they render NO ' +
        'ACCOUNT MENU and NO SIGN-OUT. That is how the skin shipped on ' +
        '2026-08-02 and it went unnoticed for two days.',
    ).toEqual([]);
  });
});

describe('the menu contains the two items, and keeps its accessible name', () => {
  it('Settings and Sign out are both present', () => {
    expect(MENU_CODE).toMatch(/href="\/settings"/);
    expect(MENU_CODE).toContain('Sign out');
    expect(MENU_CODE).toMatch(/signOut\(\{ callbackUrl: '\/login' \}\)/);
  });

  it('the trigger is a real button with the label the E2E helper searches by', () => {
    // `tests/e2e/helpers/auth.ts` finds this with
    // getByRole('button', { name: /account menu/i }). Both halves matter: a
    // <summary> would make role=button an implicit-mapping bet, and a
    // reworded label would break every authed E2E in the repo.
    expect(MENU_CODE).toMatch(/<button[\s\S]{0,400}?aria-label=\{`Account menu for \$\{userName\}`\}/);
    expect(MENU_CODE).not.toMatch(/<summary/);
  });

  it('it is dismissible by keyboard and by outside click', () => {
    // The reason it is not a <details>: neither of these is free there, and
    // "the sign-out menu stayed open behind you" is the wrong default on a
    // shared workstation.
    expect(MENU_CODE).toMatch(/e\.key === 'Escape'/);
    expect(MENU_CODE).toMatch(/addEventListener\('pointerdown'/);
    expect(MENU_CODE).toMatch(/aria-expanded=\{open\}/);
  });

  it('POSITIVE CONTROL — these matchers fire on the pre-fix bar', () => {
    const preFix = `
      export function RoundsTopBar({ children }) {
        return <header>{children}</header>;
      }
    `;
    expect(preFix).not.toMatch(/userName \? <RoundsAccountMenu/);
    expect(preFix).not.toMatch(/userName\?:\s*string;/);
    expect(`<span className="qm-rounds-topbar-who">{userName}</span>`).toContain(
      'qm-rounds-topbar-who',
    );
  });
});
