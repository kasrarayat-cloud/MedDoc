// ============================================================================
// The /dashboard forward: fires under Rounds, inert without it, ordered right.
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
    expect(roundsRedirects('true').length).toBe(2);
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

  it('nothing else is forwarded — the blast radius is one route', () => {
    expect(roundsRedirects('true').map((r) => r.source)).toEqual(['/dashboard', '/dashboard']);
  });
});
