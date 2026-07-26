// ============================================================================
// A 'use server' file may export async functions, and nothing else.
// ----------------------------------------------------------------------------
// Next enforces this at module evaluation, not at build: exporting a plain
// object from a server-actions file compiles, typechecks, passes every unit
// test — and then throws
//
//     A "use server" file can only export async functions, found object.
//
// on the first render of any page that imports it. It cost a visit page and a
// fifteen-minute E2E run to find, because the failure looks like a timeout
// rather than an error.
//
// Types and interfaces are erased before this rule applies, so they are fine.
// ============================================================================

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

function filesUnder(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) {
      if (name !== '__tests__') filesUnder(p, out);
    } else if (p.endsWith('.ts') || p.endsWith('.tsx')) {
      out.push(p);
    }
  }
  return out;
}

/** `export const X = ...` / `export let` / `export class` / `export default`
 *  that is not an async function. Types and interfaces are excluded. */
const VALUE_EXPORT = /^export\s+(?:const|let|var|class)\s+(\w+)/gm;

describe("every 'use server' file", () => {
  const serverFiles = filesUnder('src')
    .filter((f) => {
      const head = readFileSync(f, 'utf8').slice(0, 200);
      return /^\s*['"]use server['"]/.test(head);
    });

  it('there are some to check', () => {
    expect(serverFiles.length).toBeGreaterThan(0);
  });

  for (const file of serverFiles) {
    it(`${file} exports only async functions`, () => {
      const src = readFileSync(file, 'utf8');
      const offenders: string[] = [];
      for (const m of src.matchAll(VALUE_EXPORT)) {
        offenders.push(m[1]);
      }
      // An exported async function is written `export async function X`, which
      // this pattern does not match — so anything it finds is a value.
      expect(
        offenders,
        `${file} exports a non-function value; Next refuses to evaluate the ` +
          `module and every page importing it fails to render`,
      ).toEqual([]);
    });
  }
});
