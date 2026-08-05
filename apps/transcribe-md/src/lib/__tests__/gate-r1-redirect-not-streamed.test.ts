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
//
// ----------------------------------------------------------------------------
// RE-POINTED 2026-08-05, WHEN `NEXT_PUBLIC_SKIN_ROUNDS` WAS DELETED.
//
// The guard used to locate the forward by finding `isSkinRounds()` and counting
// the awaits above it. F-ret.3 then reduced `dashboard/page.tsx` to an
// unconditional `redirect('/board')` with no flag, no parameters and no awaits
// at all — so the old anchor no longer exists in the file it guards.
//
// The INVARIANT DID NOT GO AWAY WITH THE FLAG. `dashboard/loading.tsx` is still
// there, the segment still suspends, and a redirect that ends up below an await
// is still a streamed 200. Deleting this gate because its anchor moved would
// have retired a live property for a bookkeeping reason.
//
// So the anchor moved to the property itself, and got STRICTER in the process.
// It now asserts, on every forwarding route whose segment suspends:
//
//   1. the body forwards to `/board` at all;
//   2. the route component declares NO PARAMETERS. Reading `params`/
//      `searchParams` is precisely what suspends the segment — a route that
//      cannot name them cannot await them, whatever anyone adds later;
//   3. ZERO `await`s appear above the `redirect(`.
//
// (2) is new, and it is why this is a stronger form of the same check rather
// than a like-for-like translation: the old version tolerated an `await
// searchParams` as long as it sat inside the flag branch, which was true but
// fragile. A signature with empty parens makes the failure impossible to
// reintroduce by editing the body.
// ============================================================================

import { existsSync, readFileSync } from 'node:fs';
import { dirname } from 'node:path';

import { describe, expect, it } from 'vitest';

/** Routes whose whole job is to forward somewhere else. */
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
    // returned '' would make the real assertions below quantify over nothing.
    //
    // ⚠️ This used to assert `body.length > 100`, a threshold calibrated when
    // `/dashboard` was a 753-line page. The correct file is now three lines, so
    // a byte count would redden on exactly the shape this gate wants. It asks
    // for the two things that actually prove a parse instead.
    for (const file of FORWARDING_ROUTES) {
      const body = routeBody(codeOnly(readFileSync(file, 'utf8')));
      expect(body, `${file}: no default async export found`).toMatch(
        /^export default async function \w+\s*\(/,
      );
      expect(body, `${file}: no redirect at all`).toContain('redirect(');
    }
  });

  it('NEGATIVE CONTROL — the detectors fire on routes shaped the wrong way', () => {
    const awaitsFirst = `export default async function P() {
      const s = await auth();
      redirect('/board');
    }`;
    expect(
      awaitsBeforeForward(awaitsFirst),
      'the await detector cannot see the defect',
    ).toBeGreaterThan(0);

    const takesSearchParams = `export default async function P({ searchParams }) {
      redirect('/board');
    }`;
    expect(
      declaredParameters(takesSearchParams),
      'the parameter detector cannot see the defect',
    ).not.toBe('');

    // And the sentinel: a route with no forward at all must not read as "zero
    // awaits above the forward", which is what a plain count would return.
    const noForward = `export default async function P() {
      return null;
    }`;
    expect(awaitsBeforeForward(noForward), 'a missing forward passes vacuously').toBe(-1);

    const good = `export default async function P() {
      redirect('/board');
    }`;
    expect(awaitsBeforeForward(good), 'the await detector fires on a correct route').toBe(0);
    expect(declaredParameters(good), 'the parameter detector fires on a correct route').toBe('');
  });

  it('the suspending set is not empty — this guard has something to guard', () => {
    // If `loading.tsx` were renamed or the detector broke, the assertions below
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

  it('⚠️ `/dashboard` forwards to /board with nothing awaited — and cannot await', () => {
    for (const file of FORWARDING_ROUTES.filter(segmentSuspends)) {
      const body = routeBody(codeOnly(readFileSync(file, 'utf8')));

      expect(body, `${file}: does not forward to /board`).toMatch(
        /redirect\(\s*['"`]\/board['"`]/,
      );

      expect(
        declaredParameters(body),
        `${file}: the route component declares parameters ` +
          `(${declaredParameters(body)}). Reading params/searchParams is what ` +
          'suspends the segment, and this segment has a loading.tsx — so the ' +
          'forward would be delivered as a streamed 200 + skeleton rather than ' +
          'a 307. A pure forward takes no arguments.',
      ).toBe('');

      expect(
        awaitsBeforeForward(body),
        `${file}: the forward sits below ${awaitsBeforeForward(body)} ` +
          'await(s). With a loading.tsx in the segment the response has already ' +
          'started, so Next answers 200 + skeleton and streams the redirect ' +
          'instead of issuing it. Hoist the redirect() above every await.',
      ).toBe(0);
    }
  });
});

/** How many `await`s the route evaluates before reaching its forward.
 *
 *  Returns **-1** when there is no forward at all, deliberately: a plain count
 *  would return 0 there, and 0 is the passing value. A sentinel that cannot be
 *  mistaken for success turns a vanished redirect into a red test. */
function awaitsBeforeForward(body: string): number {
  const at = body.search(/\bredirect\(/);
  if (at === -1) return -1;
  return (body.slice(0, at).match(/\bawait\b/g) ?? []).length;
}

/** The parameter list the route component declares, trimmed — `''` when it
 *  takes none. Returns a sentinel rather than `''` if the signature cannot be
 *  parsed, so an unreadable file fails instead of looking parameterless. */
function declaredParameters(body: string): string {
  const m = body.match(/^export default async function \w+\s*\(([^)]*)\)/);
  return m ? m[1].trim() : '<unparsed signature>';
}
