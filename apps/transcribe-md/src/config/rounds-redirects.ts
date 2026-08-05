// ============================================================================
// /dashboard → /board, as a Next `redirects()` rule set.
// ----------------------------------------------------------------------------
// ⚠️ IT LIVES HERE RATHER THAN INLINE IN `next.config.ts` SO IT CAN BE TESTED.
// The rule that matters is an ORDERING one — Next takes the first match, and
// the bare `/dashboard` rule matches regardless of query string, so reversing
// the two silently drops the `?tab=all` deep link. That is not a thing to
// discover from a bookmark; it is a thing to assert.
//
// Why a config redirect at all, rather than `redirect()` in the route:
// `app/dashboard/loading.tsx` wraps that segment in Suspense, so a redirect
// thrown in the page component after ANY await (including `await searchParams`)
// arrives as a streamed `200` + skeleton instead of a `307`. Measured all three
// ways on the QA image; only this one issues a real redirect. See the block
// comment in `next.config.ts`.
//
// ⚠️ UNCONDITIONAL SINCE 2026-08-05 (F-ret.3). This used to take the skin flag
// and return `[]` when it was not exactly the string 'true'.
//
// THE STATED REASON FOR THAT FAIL-CLOSED BRANCH HAD ALREADY EXPIRED, and it is
// worth recording how: the comment read "INERT WITH THE FLAG OFF, and that is
// load-bearing: the default `chromium` E2E pack builds flag-OFF and 24 of its
// specs live on `/dashboard`. A redirect that fired there would delete the page
// they test." True when written. F-ret.1 then gave that pack production's flag
// set — so it builds flag-ON — and re-pointed those specs to `/board`. The
// branch outlived its justification by two days, with a comment still asserting
// it. Same session, same hand: changing a thing and not its explanation is how
// the next reader is misled by something that looks authoritative.
// ============================================================================

export interface RoundsRedirect {
  source: string;
  has?: { type: 'query'; key: string; value: string }[];
  destination: string;
  permanent: boolean;
}

/**
 * Evaluated at BUILD time. No longer takes the flag — there is one skin, so
 * `/dashboard` always forwards.
 *
 * ⚠️ STILL A FUNCTION RATHER THAN A CONST, deliberately: `next.config.ts` calls
 * it from an async `redirects()`, and the ordering invariant below is asserted
 * by its own test against the returned array. A bare exported const would be
 * equally testable but would invite inlining back into the config, which is the
 * arrangement that made the ordering untestable in the first place.
 */
export function roundsRedirects(): RoundsRedirect[] {
  return [
    // FIRST — the specific rule. See the ordering note above.
    {
      source: '/dashboard',
      has: [{ type: 'query', key: 'tab', value: 'all' }],
      destination: '/board?filter=active',
      // 307, not 308. A permanent redirect is cached by the browser
      // effectively forever, and that is not a thing to do to a URL on the
      // strength of an IA decision — even one we now consider settled.
      permanent: false,
    },
    { source: '/dashboard', destination: '/board', permanent: false },

    // ── R2 — /templates → the note-format section under Settings ───────────
    // Templates left the nav; the deep link must not die with it.
    //
    // ⚠️ THERE HAS NEVER BEEN A `/templates` ROUTE — `src/app/templates` does
    // not exist, so this path 404s on `main` today. That makes this rule a
    // strict improvement in both directions and is worth stating, because the
    // obvious reading ("a redirect that shadows a live page") is wrong here:
    // there is no page to shadow. What it catches is bookmarks, typed URLs and
    // anything that ever linked to the noun the nav used to show.
    //
    // QUERY IS PRESERVED BY NEXT, NOT BY THIS RULE. `redirects()` forwards the
    // query string automatically whenever the destination does not specify its
    // own — which is exactly why the `/dashboard?tab=all` rule above has to
    // come FIRST and name `?filter=active` explicitly. This destination is bare,
    // so `/templates?x=1` arrives as `/settings/note-format?x=1` with nothing
    // added here. Asserted in the test rather than trusted.
    { source: '/templates', destination: '/settings/note-format', permanent: false },
  ];
}
