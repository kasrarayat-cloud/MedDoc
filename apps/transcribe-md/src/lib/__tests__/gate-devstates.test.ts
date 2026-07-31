// ============================================================================
// /dev/states — reachable where the sweep runs, absent from production, and
// silent about errors it invents.
// ----------------------------------------------------------------------------
// Three ways this route can be silently wrong, none of them a build error:
//
//  1. GATED ON THE WRONG THING. `NODE_ENV === 'production'` is the obvious
//     gate and it is wrong for anything a test must reach, because the QA
//     stack RUNS a production build. Measured: `/dev/rx-warnings` returns 404
//     on QA against a `/login` control at 200. A NODE_ENV-gated preview route
//     is a door onto nothing.
//
//  2. REACHABLE IN PRODUCTION. The inverse failure, and the worse one: a route
//     that renders synthetic failure states on a production host is
//     indistinguishable from a real outage to whoever lands on it.
//
//  3. FILING REAL BUG REPORTS. `ErrorFallback` POSTs scope/message/stack/
//     digest/url to `/api/client-errors` on mount. A preview that renders it
//     without `preview` puts fabricated errors into the stream ops reads.
//     ⚠️ And the fix has its own failure mode — a suppression switch that
//     silently disabled REAL reporting would be far worse than the bug it
//     fixes. So the beacon is asserted to still fire when `preview` is falsy,
//     not merely to be skippable.
// ============================================================================

import { readFileSync } from 'node:fs';

import { afterEach, describe, expect, it, vi } from 'vitest';

const DOCKERFILE = readFileSync('Dockerfile', 'utf8');
const WORKFLOW = readFileSync('../../.github/workflows/e2e.yml', 'utf8');
const COMPOSE = readFileSync('../../docker-compose.yml', 'utf8');
const PAGE = readFileSync('src/app/dev/states/page.tsx', 'utf8');
const FALLBACK = readFileSync('src/components/error-fallback.tsx', 'utf8');

/** Executable lines only. The files below DISCUSS the wrong gate at length, and
 *  matching prose instead of code is the A2 defect-2 shape that has now caught
 *  six guards in this repo. */
function code(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*') && !l.trim().startsWith('#'))
    .join('\n');
}

describe('/dev/states — the Gate C door', () => {
  afterEach(() => vi.resetModules());

  it('the comment-stripper works — negative control', () => {
    expect(PAGE).toContain('NODE_ENV'); // discussed at length…
    expect(code(PAGE)).not.toContain('NODE_ENV'); // …and never executed.
  });

  it('is gated on the BUILD FLAG, not on NODE_ENV', () => {
    const c = code(PAGE);
    expect(c).toMatch(/if\s*\(\s*!\s*isDevStates\(\)\s*\)\s*notFound\(\)/);
    expect(c).not.toMatch(/NODE_ENV/);
  });

  it('the flag is DECLARED in the Dockerfile — an undeclared build-arg is discarded silently', () => {
    // This is how the first flag-ON build shipped the old skin.
    expect(code(DOCKERFILE)).toMatch(/^ARG NEXT_PUBLIC_DEV_STATES=false$/m);
    expect(code(DOCKERFILE)).toMatch(
      /^ENV NEXT_PUBLIC_DEV_STATES=\$\{NEXT_PUBLIC_DEV_STATES\}$/m,
    );
  });

  it('the :rounds CI image passes it', () => {
    const build = WORKFLOW.slice(
      WORKFLOW.indexOf('Build Rounds flag-ON image'),
      WORKFLOW.indexOf('-t meddoc-pro-transcribe-md:rounds'),
    );
    expect(build).toContain('--build-arg NEXT_PUBLIC_DEV_STATES=true');
  });

  it('PRODUCTION never passes it — asserted against compose, not a default', () => {
    // A Dockerfile default is only as good as everyone's memory of it. The
    // binding fact is that prod's `args:` block does not mention this flag.
    const appService = COMPOSE.slice(COMPOSE.indexOf('  transcribe-md:'));
    const argsBlock = appService.slice(0, appService.indexOf('\n    environment:'));
    expect(argsBlock).not.toContain('NEXT_PUBLIC_DEV_STATES');
    // Positive control: the matcher CAN see flags in that block, so the
    // absence above is a real absence and not a broken slice.
    expect(argsBlock).toContain('NEXT_PUBLIC_SKIN_ROUNDS');
  });

  it('the flag predicate is strict equality — unset and "1" are OFF', async () => {
    for (const [value, expected] of [
      ['true', true],
      ['false', false],
      ['1', false],
      ['TRUE', false],
      [undefined, false],
    ] as const) {
      const prev = process.env.NEXT_PUBLIC_DEV_STATES;
      if (value === undefined) delete process.env.NEXT_PUBLIC_DEV_STATES;
      else process.env.NEXT_PUBLIC_DEV_STATES = value;
      vi.resetModules();
      const { isDevStates } = await import('../../config/dev-states');
      expect(isDevStates(), `value ${String(value)}`).toBe(expected);
      if (prev === undefined) delete process.env.NEXT_PUBLIC_DEV_STATES;
      else process.env.NEXT_PUBLIC_DEV_STATES = prev;
    }
  });

  it('the preview renders the fallback WITH preview, so it files no bug report', () => {
    const client = code(readFileSync('src/app/dev/states/client.tsx', 'utf8'));
    expect(client).toMatch(/<ErrorFallback[\s\S]*?preview[\s\S]*?\/>/);
  });

  it('⚠️ the beacon STILL FIRES when preview is falsy', () => {
    // The suppression's own failure mode. If `preview` ever became the default,
    // or the early return lost its condition, real client errors would stop
    // being reported and nothing else in the suite would notice.
    const c = code(FALLBACK);
    // The guard is a CONDITIONAL early return, not an unconditional one.
    expect(c).toMatch(/if\s*\(\s*preview\s*\)\s*return;/);
    expect(c).not.toMatch(/^\s*return;\s*$[\s\S]*sendBeacon/m);
    // And the default is OFF, so every real boundary keeps reporting.
    expect(c).toMatch(/preview\s*=\s*false/);
    // The beacon itself is still there.
    expect(c).toContain("sendBeacon('/api/client-errors'");
  });

  it('the stale fixture really is classified stale — and the plain one is not', async () => {
    const { isStaleDeploymentError } = await import('../stale-deployment');
    const { DEV_PLAIN_ERROR, DEV_STALE_ERROR } = await import(
      '../../app/dev/states/client'
    );
    expect(isStaleDeploymentError(DEV_STALE_ERROR)).toBe(true);
    expect(isStaleDeploymentError(DEV_PLAIN_ERROR)).toBe(false);
  });

  it('the preview imports the REAL loading components, not copies', () => {
    const c = code(PAGE);
    expect(c).toContain("from '@/app/board/loading'");
    expect(c).toContain("from '@/app/visits/[id]/loading'");
  });
});
