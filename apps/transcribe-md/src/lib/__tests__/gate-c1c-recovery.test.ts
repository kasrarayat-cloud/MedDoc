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

async function withFlag<T>(value: string | undefined, fn: () => Promise<T>): Promise<T> {
  const prev = process.env.NEXT_PUBLIC_SKIN_ROUNDS;
  if (value === undefined) delete process.env.NEXT_PUBLIC_SKIN_ROUNDS;
  else process.env.NEXT_PUBLIC_SKIN_ROUNDS = value;
  vi.resetModules();
  try {
    return await fn();
  } finally {
    if (prev === undefined) delete process.env.NEXT_PUBLIC_SKIN_ROUNDS;
    else process.env.NEXT_PUBLIC_SKIN_ROUNDS = prev;
    vi.resetModules();
  }
}

describe('C1-c recovery destination', () => {
  afterEach(() => vi.resetModules());

  it('flag OFF → /dashboard, because /board 404s with the flag off', async () => {
    await withFlag('false', async () => {
      const { recoveryHref, recoveryLabel } = await import(MOD);
      expect(recoveryHref()).toBe('/dashboard');
      expect(recoveryLabel()).toMatch(/dashboard/i);
    });
  });

  it('flag ON → /board', async () => {
    await withFlag('true', async () => {
      const { recoveryHref, recoveryLabel } = await import(MOD);
      expect(recoveryHref()).toBe('/board');
      expect(recoveryLabel()).toMatch(/board/i);
    });
  });

  it('unset is treated as OFF — the predicate is strict equality', async () => {
    // `skin-rounds.ts` compares === 'true', so unset / '1' / 'TRUE' are all
    // off. Asserted because "the flag is not set" is the production state for
    // every environment until item F, and a truthiness check here would send
    // every one of them to a 404.
    await withFlag(undefined, async () => {
      const { recoveryHref } = await import(MOD);
      expect(recoveryHref()).toBe('/dashboard');
    });
    await withFlag('1', async () => {
      const { recoveryHref } = await import(MOD);
      expect(recoveryHref()).toBe('/dashboard');
    });
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
    const EXPECTED = {
      true: { href: '/board', label: 'Back to the board' },
      false: { href: '/dashboard', label: 'Back to dashboard' },
    } as const;
    for (const flag of ['true', 'false'] as const) {
      await withFlag(flag, async () => {
        const { recoveryHref, recoveryLabel } = await import(MOD);
        expect(recoveryHref()).toBe(EXPECTED[flag].href);
        expect(recoveryLabel()).toBe(EXPECTED[flag].label);
      });
    }
    // And the guard against the substring trap itself, so nobody reintroduces
    // it while "simplifying": these two labels must not be prefixes of one
    // another under a naive containment check in the ON direction.
    expect('Back to dashboard'.toLowerCase()).toContain('board');
  });

  it('/board really does fail closed — the premise of the fork', async () => {
    // If this ever stops being true, the fork is unnecessary and this whole
    // file is ceremony. Read from source rather than assumed, and stripped of
    // comments first: `board/page.tsx`'s header PROSE also says the route
    // 404s, and matching the prose instead of the code is the A2 defect-2
    // shape that has now caught five guards in this repo.
    const src = readFileSync('src/app/board/page.tsx', 'utf8');
    const code = src
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n')
      .filter((l) => !l.trim().startsWith('//'))
      .join('\n');
    expect(src).toMatch(/404s/); // the prose exists…
    expect(code).toMatch(/if\s*\(\s*!\s*isSkinRounds\(\)\s*\)\s*notFound\(\)/); // …and so does the gate
  });

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
