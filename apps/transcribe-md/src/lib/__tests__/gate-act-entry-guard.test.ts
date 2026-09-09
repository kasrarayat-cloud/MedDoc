// ============================================================================
// A RULED-ACT SCRIPT MUST NOT RUN ON IMPORT — canon 143's lesson, armed.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE IT ALREADY HAPPENED. A bare `void main()` at module
// scope in `regenerate-consult-form.ts` meant that importing its vocabulary
// EXECUTED the regeneration script: the suite reported `Tests 6464 passed` and
// `Errors 1 error`, and the filtered reading in use at the time could not
// display the second line.
//
// That script writes a file when given an output path. THIS one performs an
// IRREVERSIBLE PRODUCTION ACT — it mints a template and copies certified
// clinical dispositions. The same slip here is not noise.
//
// ⚠️ AND THE ARM IS STATIC, DELIBERATELY. Actually importing the module to
// prove it does nothing would be the very experiment whose failure mode is
// "it did something". A test that must not trigger the behaviour it checks
// cannot be the thing that triggers it.
// ============================================================================
import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const SCRIPTS = resolve(__dirname, '../../../scripts');

/** Scripts that perform a ruled, irreversible act and must be guarded. */
const RULED_ACTS = ['re-issue-form.ts', 'regenerate-consult-form.ts'];

describe('a ruled-act script is guarded against running on import', () => {
  it('POSITIVE CONTROL — the files are actually there to be checked', () => {
    // Without this, a rename turns every assertion below into a vacuous pass
    // over an empty list.
    const present = readdirSync(SCRIPTS);
    for (const name of RULED_ACTS) {
      expect(present, `${name} is gone or renamed — this gate is measuring nothing`).toContain(name);
    }
  });

  it.each(RULED_ACTS)('%s does not call main() at module scope', (name) => {
    const src = readFileSync(join(SCRIPTS, name), 'utf8');
    const code = src
      .split('\n')
      .map((l) => (l.trimStart().startsWith('//') || l.trimStart().startsWith('*') ? '' : l))
      .join('\n');

    // ⚠️ COLUMN 0, AND THE `\s*` I FIRST WROTE MADE THIS A FALSE POSITIVE — it
    // matched the INDENTED, correctly-guarded call inside
    // `if (invokedDirectly) { void main(); }`. Module scope means unindented;
    // an arm that flags the fix as the defect is worse than no arm, because the
    // obvious way to make it pass is to delete the guard.
    const bare = /^(void\s+)?main\s*\(\s*\)/m.exec(code);
    expect(
      bare?.[0] ?? null,
      `${name} invokes main() at module scope — importing it RUNS THE ACT`,
    ).toBeNull();
  });

  it.each(RULED_ACTS)('%s guards on being invoked directly', (name) => {
    const src = readFileSync(join(SCRIPTS, name), 'utf8');
    expect(
      /process\.argv\[1\]/.test(src),
      `${name} has no direct-invocation guard keyed on argv[1]`,
    ).toBe(true);
  });

  it('⚠️ the re-issue act names EVERY argument it needs, with no defaults', () => {
    // A default is a value nobody declared, and this act is irreversible. The
    // declaration names each of these; passing them explicitly is what makes
    // the transcript comparable to it.
    const src = readFileSync(join(SCRIPTS, 're-issue-form.ts'), 'utf8');
    for (const required of [
      'artifact-id',
      'transfer-from',
      'practice-id',
      'user-id',
      'user-email',
      'expect-sha256',
      'expect-fields',
      'expect-transfer',
      'transfer-source-types',
    ]) {
      expect(src, `re-issue-form.ts stopped requiring --${required}`).toContain(`'${required}'`);
    }
    // ⚠️ and no `??` fallback on an argument reader, which is how a default
    // sneaks back in without changing the argument list.
    expect(/function arg\([^)]*\)[^}]*\?\?/s.test(src), 'arg() grew a fallback').toBe(false);
  });

  it('⚠️ the tag census INFLATES the package — a raw scan reports a false zero', () => {
    // Measured: a regex over the compressed .docx buffer finds tags=0 sdts=0,
    // where the inflated package has tags=1 sdts=28. A census that scanned the
    // raw bytes would have "settled" the 18-vs-53 premise with a fabricated
    // zero and filed it as fact.
    const src = readFileSync(join(SCRIPTS, 're-issue-form.ts'), 'utf8');
    expect(src, 'the census no longer inflates the package').toContain('readVerifiedZipPackage');
  });
});
