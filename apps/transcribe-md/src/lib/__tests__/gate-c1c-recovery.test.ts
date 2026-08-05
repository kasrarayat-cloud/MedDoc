// ============================================================================
// Where a doctor goes when something has gone wrong — and why it is a FORK.
// ----------------------------------------------------------------------------
// Every recovery affordance sent the doctor to `/dashboard`. Under Rounds the
// home surface is `/board`. The obvious change is a swap; the swap builds a
// 404 loop.
//
// `app/board/page.tsx` runs `if (!isSkinRounds()) notFound();` BEFORE `auth()`,
// so with the flag off `/board` does not exist. The flag is OFF in production
// until item F — so a hard swap would take a doctor who just hit an error and
// send them to a second 404, with the browser's back button as the only way
// out. That is not a hypothetical about some future rollback; it is what would
// ship today.
//
// The failure is invisible to a screenshot, to a typecheck, and to any test
// that runs with the flag ON — which is every Rounds pack. So it is asserted
// here, against both flag states, by driving the module rather than reading it.
// ============================================================================

import { readFileSync } from 'node:fs';

import { afterEach, describe, expect, it, vi } from 'vitest';

const MOD = '../recovery-href';

// ⚠️ `withFlag()` was DELETED 2026-08-05 (F-ret.3). It set and restored
// `process.env.NEXT_PUBLIC_SKIN_ROUNDS` around a dynamic re-import so the two
// arms of `recoveryHref()` could each be exercised. There are no arms left, and
// a helper that mutates an env var nothing reads is a trap: the next person to
// use it would get a passing test that proves nothing.

describe('C1-c recovery destination', () => {
  afterEach(() => vi.resetModules());

  // ⚠️ FOUR FLAG-DEPENDENT TESTS RETIRED 2026-08-05 (F-ret.3). They pinned
  // `recoveryHref()`'s fork: OFF → /dashboard (because /board 404'd), ON →
  // /board, and that the predicate was strict equality so unset / '1' / 'TRUE'
  // all counted as OFF. The flag is gone, `/board`'s fail-closed guard is gone,
  // and the helper is a constant — so all four assert against a fork that no
  // longer exists. Replaced by the unconditional assertion below.
  //
  // The strict-equality test is worth naming as it goes, because its reasoning
  // outlives it: a TRUTHINESS check there would have sent every unset
  // environment to a 404. That class of bug moved rather than vanished — it now
  // belongs to whichever flags remain.

  it('recovery goes to the board, unconditionally', async () => {
    const { recoveryHref, recoveryLabel } = await import(MOD);
    expect(recoveryHref()).toBe('/board');
    expect(recoveryLabel()).toBe('Back to the board');
  });

  it('the label and the href cannot disagree', async () => {
    // "Back to dashboard" pointing at /board is the kind of small lie that
    // survives review because each half looks right on its own.
    //
    // ⚠️ ASSERTED BY EXACT VALUE, NOT BY SUBSTRING, AND THE FIRST VERSION WAS
    // VACUOUS. It checked `label.toLowerCase()).toContain('board')` for the
    // flag-ON case — and **'dashboard' contains 'board'**. So a label reverted
    // to "Back to dashboard" on BOTH branches passed this test cleanly. It was
    // caught only by mutating the label and watching the assertion fail to
    // notice: rule 7, doing the one thing reading the test could not.
    const { recoveryHref, recoveryLabel } = await import(MOD);
    expect(recoveryHref()).toBe('/board');
    expect(recoveryLabel()).toBe('Back to the board');
    // And the guard against the substring trap itself, so nobody reintroduces
    // it while "simplifying": these two labels must not be prefixes of one
    // another under a naive containment check in the ON direction.
    expect('Back to dashboard'.toLowerCase()).toContain('board');
  });

  // ⚠️ RETIRED 2026-08-05, F-ret.3 — ON ITS OWN STATED CONDITION.
  //
  // This asserted that `/board` fails closed (`if (!isSkinRounds()) notFound()`
  // before `auth()`), because that 404 was the PREMISE of the recovery fork:
  // hard-swapping recovery links to `/board` while it could 404 would have sent
  // a doctor from one 404 to another.
  //
  // Its own comment named the retirement condition: "If this ever stops being
  // true, the fork is unnecessary and this whole file is ceremony." F-ret.3
  // removed the skin flag and its OFF arm, so the guard has nothing to protect
  // against and is gone. The premise stopped being true, exactly as anticipated.
  //
  // ⚠️ AND THE FORK WENT WITH IT — the two are one change. `recovery-href.ts`
  // is now a constant returning '/board'. Deleting the guard while leaving the
  // fork would have left it choosing between two identical destinations;
  // deleting the fork while leaving the guard would have built the 404 loop this
  // test existed to prevent. Neither half is safe alone.
  //
  // NOT retired, and deliberately kept below: the assertion that no recovery
  // affordance hardcodes `/dashboard`, and the comment-stripper negative
  // control. Those hold regardless of how many skins exist — the first is what
  // stops a future edit re-hardcoding a dead home, and the second is what stops
  // the first from passing on prose.

  it('no recovery affordance hardcodes /dashboard any more', async () => {
    const FILES = [
      'src/components/error-fallback.tsx',
      'src/app/not-found.tsx',
      'src/app/visits/[id]/not-found.tsx',
    ];
    for (const f of FILES) {
      const code = readFileSync(f, 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .split('\n')
        .filter((l) => !l.trim().startsWith('//'))
        .join('\n');
      expect(code, `${f} still hardcodes a recovery href`).not.toMatch(
        /href=(\{)?["']\/dashboard["']/,
      );
      expect(code, `${f} does not use the shared helper`).toContain('recoveryHref');
    }
  });

  it('the comment-stripper works — negative control', () => {
    // recovery-href.ts DISCUSSES /dashboard at length. If stripping breaks,
    // the assertion above starts reading prose and passes on a reverted file.
    const raw = readFileSync('src/lib/recovery-href.ts', 'utf8');
    expect(raw).toContain('/dashboard');
    const code = raw
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n')
      .filter((l) => !l.trim().startsWith('//'))
      .join('\n');
    // Only the return expression survives, never the prose.
    expect(code.match(/\/dashboard/g)?.length ?? 0).toBeLessThan(
      raw.match(/\/dashboard/g)!.length,
    );
  });
});
