// ============================================================================
// EVERY `'use server'` FILE SURVIVES THE COMPILER THAT SHIPS IT.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE 6,564 ARMS WENT GREEN ON A TREE `next build` REFUSES.
//
// A fix landed `export { VISIT_PREVIEW_MISSES } from '@/lib/visit-preview-misses'`
// into `actions/preview-visit-document.ts`, which is `'use server'`. SWC refuses
// that file outright — "Only async functions are allowed to be exported in a
// `use server` file" — and the app does not build. vitest never saw it: it
// transpiles with esbuild, which does not implement the restriction.
//
// ⚠️ AND THE SAME COMMIT REMOVED ITS OWN WITNESS. The one gate that loaded that
// module was deliberately re-pointed at a leaf by that very fix, so nothing in
// the suite imported the file any more. The only thing that would have caught it
// was `next build`, which runs in `a11y-ci`/`e2e` — 40 minutes downstream of the
// commit, on a lane whose author had already read a green suite.
//
// So this drives the REAL compiler binding over the REAL files.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

const APP = join(__dirname, '..', '..', '..');

/** Every tracked `'use server'` file, by first-line directive. */
function useServerFiles(): string[] {
  return execFileSync('git', ['ls-files', 'src'], { cwd: APP, encoding: 'utf8' })
    .split('\n')
    .filter((f) => f.endsWith('.ts') || f.endsWith('.tsx'))
    .filter((f) => {
      const head = readFileSync(join(APP, f), 'utf8').slice(0, 200);
      return /^\s*(['"])use server\1\s*;/m.test(head);
    });
}

type Swc = {
  loadBindings?: () => Promise<unknown>;
  transform: (code: string, opts: unknown) => Promise<unknown>;
};

const OPTS = {
  jsc: { parser: { syntax: 'typescript', tsx: false }, target: 'es2022' },
  serverActions: {
    isReactServerLayer: true,
    isDevelopment: false,
    useCacheEnabled: false,
    hashSalt: 'gate',
    cacheKinds: [] as string[],
  },
};

async function compiles(swc: Swc, filename: string, code: string): Promise<string | null> {
  try {
    await swc.transform(code, { ...OPTS, filename });
    return null;
  } catch (e) {
    return String((e as Error).message ?? e);
  }
}

describe("every 'use server' file compiles under the shipping compiler", () => {
  it('⚠️ SWC ACCEPTS EVERY SERVER-ACTION FILE — the check vitest cannot do for itself', async () => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const swc = require('next/dist/build/swc') as Swc;
    // ⚠️ THE BINDINGS MUST BE LOADED FIRST, and forgetting it is a trap this arm
    // has already met: every call then throws "bindings not loaded yet", so the
    // SUBJECT and every CONTROL fail identically and the run discriminates
    // NOTHING while looking like a red.
    if (swc.loadBindings) await swc.loadBindings();

    const files = useServerFiles();
    // NON-VACUITY: a scan that found no server files would pass forever.
    expect(files.length, "no 'use server' files found — the scan is broken").toBeGreaterThan(3);

    // ⚠️ POSITIVE CONTROL FIRST. If the option shape ever stops enabling the
    // restriction, every real file passes and this gate reports green about
    // nothing. The control is the exact shape that shipped.
    const planted = await compiles(
      swc,
      'planted.ts',
      "'use server';\nexport { A } from './somewhere';\nexport async function f() { return 1; }\n",
    );
    expect(
      planted,
      'the planted value re-export COMPILED — the restriction is not enabled, so a ' +
        'green below means nothing',
    ).toMatch(/use server/i);

    // …and a clean server file must NOT error, or the control above is just noise.
    expect(
      await compiles(swc, 'clean.ts', "'use server';\nexport async function f() { return 1; }\n"),
    ).toBeNull();

    const broken: string[] = [];
    for (const f of files) {
      const err = await compiles(swc, f, readFileSync(join(APP, f), 'utf8'));
      if (err) broken.push(`${f}: ${err.split('\n').find((l) => /use server|async functions/i.test(l))?.trim() ?? err.slice(0, 120)}`);
    }
    expect(
      broken,
      "a 'use server' file does not compile — `next build` will refuse this tree, " +
        'and no other arm in this suite can see it',
    ).toEqual([]);
  }, 120_000);
});
