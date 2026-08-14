// ============================================================================
// A `useCallback` WHOSE BODY CALLS ITSELF IS A STACK OVERFLOW, AND NOTHING
// ELSE IN THIS REPOSITORY SEES IT.
//
// ⚠️ REFERENCE CASE, RC-2, 2026-08-14. A helper was introduced to pair two
// clears that must always happen together:
//
//     const clearPendingUpload = useCallback(() => {
//       clearPendingUpload();          // ← meant to be setPendingFile(null)
//       setPendingSource(null);
//     }, []);
//
// It recursed on every path that abandons an upload, so the note-format screen
// crashed and the parse step never rendered. `tsc` is happy — self-recursion is
// legal. The unit suite never mounted it. It was caught by the E2E pack, and
// only because that pack exists: 24 scenarios failed at "the parse did not
// reach the confirm step", 400 lines away from the cause.
//
// ⚠️ AND THE COMMENT ABOVE IT ARGUED, CORRECTLY, THAT ONE FUNCTION BEATS A
// HAND-KEPT LIST OF CLEAR-SITES. The reasoning was right and the body replaced
// the thing it was extracting with a call to itself — the shape of an edit that
// renamed its own target away. A well-argued helper is not a working one.
// ============================================================================
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = path.resolve(__dirname, '../..');

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = path.join(dir, e);
    if (e === 'node_modules' || e === '__tests__') continue;
    if (statSync(p).isDirectory()) sourceFiles(p, out);
    else if (p.endsWith('.ts') || p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

/** `const NAME = useCallback(() => {` immediately followed by `NAME(` */
const SELF_CALL =
  /const\s+(\w+)\s*=\s*(?:useCallback|useMemo)\(\s*(?:async\s*)?\(\)\s*=>\s*\{\s*\n\s*\1\s*\(/;

describe('no hook callback calls itself as its first statement', () => {
  const files = sourceFiles(SRC);

  it('the matcher DETECTS the shape — a guard proven only green is not proven', () => {
    // POSITIVE CONTROL, and it is the half that matters: this guard's whole
    // job is to go red, and a regex that matches nothing passes forever.
    expect(SELF_CALL.test('const foo = useCallback(() => {\n    foo();\n  }, []);')).toBe(true);
    expect(SELF_CALL.test('const foo = useCallback(async () => {\n    foo();\n  }, []);')).toBe(
      true,
    );
    // …and does NOT flag the correct shape.
    expect(
      SELF_CALL.test('const foo = useCallback(() => {\n    setFoo(null);\n  }, []);'),
    ).toBe(false);
  });

  it('the scan is not vacuous — it walked real files', () => {
    expect(files.length).toBeGreaterThan(50);
    const withHooks = files.filter((f) => readFileSync(f, 'utf8').includes('useCallback('));
    expect(withHooks.length, 'no useCallback found anywhere — the walk is wrong').toBeGreaterThan(
      5,
    );
  });

  it('NO callback recurses into itself', () => {
    const offenders = files
      .filter((f) => SELF_CALL.test(readFileSync(f, 'utf8')))
      .map((f) => path.relative(SRC, f));
    expect(
      offenders,
      'a hook callback calls itself as its first statement — that is unbounded ' +
        'recursion, it type-checks cleanly, and the symptom appears far from the cause',
    ).toEqual([]);
  });
});
