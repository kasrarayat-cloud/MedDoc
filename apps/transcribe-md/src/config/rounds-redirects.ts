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
// ============================================================================

export interface RoundsRedirect {
  source: string;
  has?: { type: 'query'; key: string; value: string }[];
  destination: string;
  permanent: boolean;
}

/**
 * Evaluated at BUILD time — the same moment `NEXT_PUBLIC_SKIN_ROUNDS` is
 * inlined — so the fork is baked into the image like every other consumer of
 * the flag. Takes the flag as an argument rather than reading `process.env`
 * directly so the off case is testable without mutating global state.
 */
export function roundsRedirects(flag: string | undefined): RoundsRedirect[] {
  // ⚠️ INERT WITH THE FLAG OFF, and that is load-bearing: the default
  // `chromium` E2E pack builds flag-OFF and 24 of its specs live on
  // `/dashboard`. A redirect that fired there would delete the page they test.
  if (flag !== 'true') return [];
  return [
    // FIRST — the specific rule. See the ordering note above.
    {
      source: '/dashboard',
      has: [{ type: 'query', key: 'tab', value: 'all' }],
      destination: '/board?filter=active',
      // 307, not 308: a product decision that rolls back with the flag, and a
      // permanent redirect is cached by the browser effectively forever.
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
    // 307, matching `/dashboard` above: a product decision that rolls back with
    // the flag. A `permanent: true` would be cached by the browser effectively
    // forever, which is not a thing to do to a URL on a hunch about the IA.
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
