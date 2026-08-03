// ============================================================================
// The Rounds forwards: fire under Rounds, inert without it, ordered right.
//   R1 — /dashboard → /board  (two rules, the deep link first)
//   R2 — /templates → /settings/note-format
// ============================================================================

import { describe, expect, it } from 'vitest';

import { roundsRedirects } from '../rounds-redirects';

describe('R1 — the /dashboard → /board redirect rules', () => {
  it('⚠️ INERT with the flag off, absent, or anything but the literal "true"', () => {
    // Load-bearing: the default `chromium` E2E pack builds flag-OFF and 24 of
    // its specs live on /dashboard. A redirect firing there deletes the page
    // they test — and the failure would read as "the dashboard is broken".
    for (const off of ['false', '', 'TRUE', '1', undefined]) {
      expect(roundsRedirects(off), `flag=${String(off)} produced redirects`).toEqual([]);
    }
  });

  it('POSITIVE CONTROL — it does fire on the literal "true"', () => {
    // Without this, a helper that returned [] unconditionally would pass every
    // assertion above and ship a forward that never forwards.
    // R2: 2 → 3. The count is asserted rather than the emptiness, so ADDING a
    // rule has to come here and be looked at, instead of sliding under a
    // `.length > 0`.
    expect(roundsRedirects('true').length).toBe(3);
  });

  it('⚠️ the SPECIFIC rule comes first, or the deep link is silently dropped', () => {
    const rules = roundsRedirects('true');
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
    for (const r of roundsRedirects('true')) {
      expect(r.permanent, `${r.source} → ${r.destination} is permanent`).toBe(false);
    }
  });

  it('nothing else is forwarded — the blast radius is the named routes', () => {
    expect(roundsRedirects('true').map((r) => r.source)).toEqual([
      '/dashboard',
      '/dashboard',
      '/templates',
    ]);
  });
});

describe('R2 — the /templates → /settings/note-format redirect', () => {
  const templates = () => roundsRedirects('true').filter((r) => r.source === '/templates');

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

  it('⚠️ INERT with the flag off — /templates keeps its current behaviour', () => {
    // Flag-OFF the nav still shows Templates and this path is a 404, exactly as
    // on `main`. The default `chromium` pack builds flag-OFF; a redirect firing
    // there would change a route none of R2 touched.
    for (const off of ['false', '', 'TRUE', '1', undefined]) {
      expect(
        roundsRedirects(off).some((r) => r.source === '/templates'),
        `flag=${String(off)} produced a /templates forward`,
      ).toBe(false);
    }
  });

  it('does not shadow the destination — no rule forwards /settings/*', () => {
    // A `/settings/note-format` source would make the redirect a loop. Cheap to
    // assert, and the failure mode is a hang rather than an error.
    for (const r of roundsRedirects('true')) {
      expect(r.source.startsWith('/settings')).toBe(false);
    }
  });
});
