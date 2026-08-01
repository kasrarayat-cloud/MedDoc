import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import postcss from 'postcss';

// ============================================================================
// gate-css-parses — the stylesheets must PARSE, and this must be knowable in
// two seconds rather than in a ten-minute image build.
// ----------------------------------------------------------------------------
// ⚠️ WHY THIS EXISTS, and it is not a hypothetical.
//
// C1-e shipped a comment edit into `rounds-tokens.css` that closed a block
// comment in the middle of an existing one, orphaning its remainder:
//
//     * its own note. */          <-- inserted
//     *
//     * WHY IT WINS THE CASCADE…  <-- now parsed as CSS
//
// Every unit test passed. `tsc` passed. 3052 tests passed. The failure surfaced
// only from `docker build`, ~10 minutes in, as
// `Unknown word WHY` behind a turbopack postcss stack trace — a message that
// names neither the file that broke nor the edit that broke it.
//
// Four items before this one each re-parsed the CSS with postcss BY HAND and
// recorded it in the ledger as evidence ("CSS re-parsed with postcss, 133
// rules, against a negative control"). Four sessions performing the same check
// by hand is the definition of something that should be a test. The one session
// that skipped it paid the build.
//
// ⚠️ THE NEGATIVE CONTROL IS THE POINT, not decoration. `postcss.parse` is
// lenient by design, and a check that cannot reject anything reports success on
// every input — the failure mode this repo has now recorded from three
// directions (a dead stack, a depth-limited sweep, an empty-set filter). If the
// control block below ever stops throwing, this file is measuring nothing and
// the assertion at the end says so out loud rather than passing quietly.
// ============================================================================

const APP_DIR = join(__dirname, '..', '..', 'app');

/** Derived by traversal of the app dir, never a maintained array — the
 *  `globstar` miss and the convention-file miss are both this failure. */
function stylesheets(): string[] {
  const { readdirSync, statSync } = require('node:fs') as typeof import('node:fs');
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const e of readdirSync(dir)) {
      const p = join(dir, e);
      if (statSync(p).isDirectory()) walk(p);
      else if (e.endsWith('.css')) out.push(p);
    }
  };
  walk(APP_DIR);
  return out.sort();
}

describe('gate-css-parses — every shipped stylesheet is syntactically valid', () => {
  const files = stylesheets();

  it('the traversal actually found the stylesheets', () => {
    // Non-vacuity. A walk that returns nothing would make every `it.each` below
    // vanish and the file would report green over an empty set.
    expect(files.length, 'no .css found under src/app — the traversal is broken').toBeGreaterThanOrEqual(2);
    const names = files.map((f) => f.split('/').pop());
    expect(names).toContain('globals.css');
    expect(names).toContain('rounds-tokens.css');
  });

  it.each(stylesheets())('%s parses', (file) => {
    const css = readFileSync(file, 'utf8');
    // A parse error throws with `file:line:col: message` — surfaced verbatim,
    // because the build's own version of this error names neither.
    expect(() => postcss.parse(css, { from: file })).not.toThrow();
  });

  it('every stylesheet contains rules — a parse that yields nothing is not a pass', () => {
    for (const file of files) {
      const root = postcss.parse(readFileSync(file, 'utf8'), { from: file });
      let rules = 0;
      root.walkRules(() => {
        rules++;
      });
      expect(rules, `${file} parsed to zero rules`).toBeGreaterThan(0);
    }
  });

  it('THE NEGATIVE CONTROL — the parser rejects malformed input', () => {
    // If this ever passes silently, the assertions above are worthless. Each
    // case is a real shape: the first is EXACTLY the C1-e defect.
    const bad: Array<[string, string]> = [
      ['stray comment close', 'a{color:red} */\n * dangling\n'],
      ['unclosed block comment', 'a{color:red}\n/* never closed\n'],
      ['unclosed brace', '.x{color:red'],
    ];
    const rejected: string[] = [];
    for (const [name, src] of bad) {
      try {
        postcss.parse(src, { from: `control-${name}` });
      } catch {
        rejected.push(name);
      }
    }
    expect(
      rejected,
      'postcss accepted input it should reject — this gate is measuring nothing',
    ).toEqual(bad.map(([n]) => n));
  });
});
