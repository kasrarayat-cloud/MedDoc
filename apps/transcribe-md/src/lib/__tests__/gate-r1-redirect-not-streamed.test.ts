// ============================================================================
// A route that only forwards must forward BEFORE it awaits anything.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE A REDIRECT "WORKED" AND WAS STILL WRONG.
//
// R1 made `/dashboard` forward to `/board`. The first version put the check
// after `await auth()` and `await searchParams`, which reads perfectly and does
// the right thing — the doctor ends up on the board.
//
// But `app/dashboard/loading.tsx` exists, so Next wraps that segment in
// Suspense. A redirect thrown after the route's first `await` cannot be an HTTP
// redirect any more: the response has already begun. Next answers **200 with
// the loading skeleton** and delivers the redirect later in the RSC payload.
// Measured on the QA image: `GET /dashboard` → `200`, no `Location`, and the
// URL was still `/dashboard` when `page.goto()` resolved. After hoisting the
// check above every await: `307`, `Location: /board`.
//
// What it costs, in order of who notices:
//   · the doctor sees a skeleton flash and pays a second round trip
//   · a bookmark, a crawler or a link checker records `200 /dashboard` — a
//     page that no longer exists reporting that it does
//   · a test asserting the URL after navigation fails, and blames the redirect
//
// None of that shows up in a "does it end up on the board" check, which is why
// the E2E now asserts the raw status and why this asserts the SHAPE. Both,
// because they fail differently: this one fails on the PR that introduces the
// regression, without needing an image.
// ============================================================================

import { existsSync, readFileSync } from 'node:fs';
import { dirname } from 'node:path';

import { describe, expect, it } from 'vitest';

/** Routes that forward under Rounds. */
const FORWARDING_ROUTES = [
  'src/app/dashboard/page.tsx',
  'src/app/page.tsx',
] as const;

/** ⚠️ THE RULE ONLY BITES WHERE THE SEGMENT SUSPENDS, AND THE FIRST VERSION OF
 *  THIS GUARD DID NOT SAY SO — it reddened on `src/app/page.tsx`, which is
 *  CORRECT. The root route cannot decide where to send anyone without `auth()`:
 *  signed in → the board, signed out → /login. There is no `loading.tsx` beside
 *  it, so nothing wraps it in Suspense, so the redirect is a real 307 anyway —
 *  measured: `/` → `/board`, no skeleton.
 *
 *  An over-strict probe is a defect in the probe. `/dashboard` is the case that
 *  matters precisely because `dashboard/loading.tsx` exists, and the check now
 *  asks that question instead of assuming the answer. */
function segmentSuspends(routeFile: string): boolean {
  return existsSync(`${dirname(routeFile)}/loading.tsx`);
}

/** Strip comments, so a prose mention of `await` cannot move the verdict. This
 *  project has shipped a source-grep that tripped on its own explanation. */
function codeOnly(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .map((l) => l.replace(/(^|[^:])\/\/.*$/, '$1'))
    .join('\n');
}

/** The body of the default-exported route component. */
function routeBody(src: string): string {
  const at = src.search(/export default async function \w+\s*\(/);
  return at === -1 ? '' : src.slice(at);
}

describe('R1 — a forwarding route forwards before it suspends', () => {
  it('the parser finds a route body — non-vacuity', () => {
    // Checked over ALL the routes, suspending or not: a parse that silently
    // returned '' would make the real assertion below quantify over nothing.
    for (const file of FORWARDING_ROUTES) {
      const body = routeBody(codeOnly(readFileSync(file, 'utf8')));
      expect(body.length, `${file}: no default async export found`).toBeGreaterThan(100);
      expect(body, `${file}: no redirect at all`).toContain('redirect(');
    }
  });

  it('NEGATIVE CONTROL — the detector fires on a route shaped the wrong way', () => {
    const bad = `export default async function P() {
      const s = await auth();
      if (isSkinRounds()) redirect('/board');
      return null;
    }`;
    expect(awaitsBeforeSkinRedirect(bad), 'the detector cannot see the defect').toBeGreaterThan(0);
    const good = `export default async function P() {
      if (isSkinRounds()) redirect('/board');
      const s = await auth();
      return null;
    }`;
    expect(awaitsBeforeSkinRedirect(good), 'the detector fires on a correct route').toBe(0);
  });

  it('the suspending set is not empty — this guard has something to guard', () => {
    // If `loading.tsx` were renamed or the detector broke, the assertion below
    // would loop over zero files and read exactly like a pass.
    const suspending = FORWARDING_ROUTES.filter(segmentSuspends);
    expect(
      suspending,
      'no forwarding route has a loading.tsx, so this gate checks nothing. ' +
        'Either the segment layout changed or `segmentSuspends` is broken',
    ).toContain('src/app/dashboard/page.tsx');
    // …and the control on the other side: `/` genuinely has none.
    expect(segmentSuspends('src/app/page.tsx')).toBe(false);
  });

  it('⚠️ `/dashboard` redirects with NOTHING awaited above it', () => {
    // The exception, and it is deliberate: `await searchParams` INSIDE the
    // `if (isSkinRounds())` block is fine — it only runs on the branch that is
    // about to redirect, and Next resolves it before the segment renders. What
    // must not happen is an await on the path to the decision.
    for (const file of FORWARDING_ROUTES.filter(segmentSuspends)) {
      const body = routeBody(codeOnly(readFileSync(file, 'utf8')));
      expect(
        awaitsBeforeSkinRedirect(body),
        `${file}: the Rounds redirect sits below ${awaitsBeforeSkinRedirect(body)} ` +
          'await(s). With a loading.tsx in the segment the response has already ' +
          'started, so Next answers 200 + skeleton and streams the redirect ' +
          'instead of issuing it. Hoist the isSkinRounds() check to the top.',
      ).toBe(0);
    }
  });
});

/** How many `await`s the route evaluates before reaching its skin redirect. */
function awaitsBeforeSkinRedirect(body: string): number {
  const at = body.indexOf('isSkinRounds()');
  if (at === -1) return 0;
  return (body.slice(0, at).match(/\bawait\b/g) ?? []).length;
}
