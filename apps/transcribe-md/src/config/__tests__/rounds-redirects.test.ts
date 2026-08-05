// ============================================================================
// The Rounds forwards: unconditional, ordered right.
//   R1 — /dashboard → /board  (two rules, the deep link first)
//   R2 — /templates → /settings/note-format
//
// ⚠️ THE "INERT WITH THE FLAG OFF" TESTS WERE RETIRED 2026-08-05 (F-ret.3).
// `roundsRedirects` no longer takes the skin flag — there is one skin, so the
// forwards always apply. Two tests pinned the fail-closed branch and are gone
// with it, and the reason they existed is worth keeping because it expired in a
// way that was invisible: "the default `chromium` E2E pack builds flag-OFF and
// 24 of its specs live on /dashboard. A redirect firing there deletes the page
// they test." F-ret.1 gave that pack production's flag set and re-pointed those
// specs to /board, so the justification was already false for two days before
// the branch was removed.
//
// ⚠️ WHAT REPLACES THE POSITIVE CONTROL. The old one guarded a real hazard — a
// helper returning [] unconditionally would have satisfied every emptiness
// assertion and shipped a forward that never forwards. Emptiness is no longer
// asserted anywhere, so that exact trap is gone; the rule COUNT is still pinned
// at 3 below, so adding or dropping a rule still has to be looked at rather
// than sliding under a `.length > 0`.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { roundsRedirects } from '../rounds-redirects';

describe('R1 — the /dashboard → /board redirect rules', () => {
  it('the rule COUNT is pinned — adding one has to be looked at', () => {
    // Asserted as an exact count rather than `.length > 0`, so a new rule
    // cannot slide in unexamined and a dropped one cannot pass quietly.
    expect(roundsRedirects().length).toBe(3);
  });

  it('⚠️ the SPECIFIC rule comes first, or the deep link is silently dropped', () => {
    const rules = roundsRedirects();
    // Next takes the FIRST match. The bare `/dashboard` rule matches regardless
    // of query string, so if it were first, `?tab=all` would land on the board's
    // default and nobody would ever see an error.
    expect(rules[0].has, 'the first rule has no query condition').toBeDefined();
    expect(rules[0].has![0]).toEqual({ type: 'query', key: 'tab', value: 'all' });
    expect(rules[0].destination).toBe('/board?filter=active');
    expect(rules[1].has, 'the fallback rule must be unconditional').toBeUndefined();
    expect(rules[1].destination).toBe('/board');
  });

  it('both are TEMPORARY — a permanent redirect outlives the flag', () => {
    // 308 is cached by the browser indefinitely. Rolling the flag back would
    // leave doctors bouncing to a board that no longer exists, with no
    // server-side way to take it back.
    for (const r of roundsRedirects()) {
      expect(r.permanent, `${r.source} → ${r.destination} is permanent`).toBe(false);
    }
  });

  it('nothing else is forwarded — the blast radius is the named routes', () => {
    expect(roundsRedirects().map((r) => r.source)).toEqual([
      '/dashboard',
      '/dashboard',
      '/templates',
    ]);
  });
});

describe('R2 — the /templates → /settings/note-format redirect', () => {
  const templates = () => roundsRedirects().filter((r) => r.source === '/templates');

  it('exists exactly once, and lands on the note-format section', () => {
    const rules = templates();
    expect(rules, 'expected exactly one /templates rule').toHaveLength(1);
    // `toBe`, not `toContain`. RELAY rule 7: '/settings/note-format' CONTAINS
    // '/settings', so a rule that forwarded to the Settings index instead of
    // the note-format section would satisfy a substring check while sending
    // the doctor to the wrong screen. The expected value is knowable, so it is
    // stated.
    expect(rules[0].destination).toBe('/settings/note-format');
  });

  it('is UNCONDITIONAL — no query condition, so every deep link is caught', () => {
    // A `has:` clause here would forward only the query shape someone thought
    // of, and 404 the rest — the same silent-drop failure the /dashboard
    // ordering rule exists to prevent, arriving from the other direction.
    expect(templates()[0].has).toBeUndefined();
  });

  it('is TEMPORARY, like every other flag-scoped forward', () => {
    expect(templates()[0].permanent).toBe(false);
  });


  it('does not shadow the destination — no rule forwards /settings/*', () => {
    // A `/settings/note-format` source would make the redirect a loop. Cheap to
    // assert, and the failure mode is a hang rather than an error.
    for (const r of roundsRedirects()) {
      expect(r.source.startsWith('/settings')).toBe(false);
    }
  });
});
