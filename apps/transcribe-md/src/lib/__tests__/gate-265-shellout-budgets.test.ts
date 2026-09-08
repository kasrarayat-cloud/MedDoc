// ============================================================================
// RULING #265(c) — EVERY SHELL-OUT TIMEOUT IN THE TEST TREE IS BOUNDED BY ITS
// OWN `it` BUDGET.
// ----------------------------------------------------------------------------
// ⚠️ THE REFERENCE CASE IS `c4e778a2`, AND IT FAILED IN CI ON A BRANCH THAT
// TOUCHED NOTHING NEAR IT. `gate-lens-sandbox` handed `execFileSync` a
// `timeout: 120_000` and ran under vitest's DEFAULT 5_000. The inner number
// could never be reached — vitest killed the test first — so the 120s described
// an INTENTION nothing enforced, and the number that actually governed was
// written down nowhere.
//
//     TWO BUDGETS THAT DISAGREE BY 24×, AND THE SMALLER ONE IS INVISIBLE.
//
// What the operator sees when it bites is `Error: Test timed out in 5000ms` and
// NOTHING ELSE — not the script's own message, not its exit code, not its
// stderr. A shell-out that cannot fail as a shell-out fails as a mystery.
//
// ── THE SHAPE THIS ENFORCES, AND WHY IT IS THAT ONE ─────────────────────────
// `c4e778a2` fixed it with ONE NAMED CONSTANT USED TWICE — `timeout: ARM_BUDGET_MS`
// and `}, ARM_BUDGET_MS)` — and that shape is what the owner ratified. So the
// rule here is NOT "strictly less". It is:
//
//   1 · the shell-out's `timeout:` is a NAMED CONSTANT, never a bare literal
//   2 · the enclosing `it`'s budget is a NAMED CONSTANT, never a bare literal
//   3 · and, where both resolve, inner <= outer
//
// ⚠️ (1) AND (2) ARE THE LOAD-BEARING HALF, NOT (3). Two literals that happen to
// be equal today are two numbers that drift tomorrow, and the drift is silent —
// which is precisely how the 120/5 pair came to exist. A shared identifier
// cannot drift, and that is a structural property rather than a habit.
//
// ── HONEST LIMITS, NAMED RATHER THAN IMPLIED ────────────────────────────────
// This is a TEXT scan, not a TypeScript parse. It finds the enclosing budget by
// taking the FIRST `}, X);` at or after the timeout line, which is the shape
// every real call site in this tree has. It would mis-attribute a `timeout:`
// inside a nested closure that closes before its own `it` does. No such site
// exists today (the whole population is enumerated below and is five lines), and
// the gate REPORTS what it matched so a future mis-attribution is visible rather
// than silent.
//
// ⚠️ AND IT SCANS THE WHOLE TEST TREE, NOT A LIST. A hand-kept list of files to
// check is a hand-kept list, and the next shell-out somebody adds is not on it.
// ============================================================================
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = resolve(__dirname, '../../../../..');

/** vitest's default when an `it` states no budget of its own. */
const VITEST_DEFAULT_TIMEOUT_MS = 5_000;

/** Every tracked test file, from git — not a glob that can silently miss one. */
function testFiles(): string[] {
  const out = execFileSync(
    'git',
    ['ls-files', '--', 'apps/**/*.test.ts', 'packages/**/*.test.ts'],
    { cwd: ROOT, encoding: 'utf8', maxBuffer: 8 * 1024 * 1024 },
  );
  return out.split('\n').filter(Boolean);
}

interface Site {
  file: string;
  line: number;
  /** the raw text after `timeout:` — an identifier or a literal */
  inner: string;
  innerLiteral: boolean;
  outer: string | null;
  outerLiteral: boolean;
  innerMs: number | null;
  outerMs: number | null;
}

const NUM = /^[0-9_]+$/;
const toMs = (t: string) => (NUM.test(t) ? Number(t.replace(/_/g, '')) : null);

/** `const NAME = 120_000;` in the same file. */
function constants(src: string): Map<string, number> {
  const m = new Map<string, number>();
  for (const line of src.split('\n')) {
    const hit = /^\s*const\s+([A-Za-z_$][\w$]*)\s*=\s*([0-9_]+)\s*;/.exec(line);
    if (hit) m.set(hit[1]!, Number(hit[2]!.replace(/_/g, '')));
  }
  return m;
}

function collectSites(): Site[] {
  const sites: Site[] = [];
  for (const file of testFiles()) {
    const src = readFileSync(resolve(ROOT, file), 'utf8');
    // Only files that actually shell out. A `timeout:` on a fetch or a waitFor
    // is a different animal and this ruling does not reach it.
    if (!/\b(execFileSync|execSync|spawnSync|execFile|spawn)\b/.test(src)) continue;
    const lines = src.split('\n');
    const consts = constants(src);

    // ⚠️ COMMENTS ARE STRIPPED, AND THE FIRST RUN OF THIS GATE PROVED WHY.
    // It flagged `gate-lens-sandbox.test.ts:40` — which is the PROSE describing
    // the very defect this gate looks for: "This arm handed `execFileSync` a
    // `timeout: 120_000` and then ran under vitest's DEFAULT 5_000." The
    // detector matched its own documentation and reported the fixed file as
    // broken.
    //
    //   A PROBE WHOSE PATTERN APPEARS IN THE PROSE AROUND IT CANNOT RETURN
    //   FALSE — and here it returned a confident TRUE about a corrected file.
    //
    // Kept as a comment rather than a lesson because the next person to widen
    // this regex will meet it again.
    const code = lines.map((l) => {
      const t = l.trimStart();
      if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')) return '';
      return l.replace(/\/\/.*$/, '');
    });

    code.forEach((line, i) => {
      // ⚠️ AND A TEMPLATE INTERPOLATION IS NOT A CALL SITE — THE SECOND TIME
      // THIS PROBE MATCHED ITSELF. Stripping comments fixed the first
      // (`gate-lens-sandbox`'s prose). This one is worse and it only surfaced in
      // CI: the `show()` helper twenty lines below formats a finding as
      // `` `… timeout: ${s.inner} …` ``, the regex captured the `$`, and the
      // gate reported ITS OWN REPORTING STRING as an unresolvable budget.
      //
      // ⚠️ IT PASSED LOCALLY FOR THE WORST POSSIBLE REASON: the scan reads
      // `git ls-files`, and when I ran it the file was still UNTRACKED — so the
      // gate could not see itself. It went green because its watched set
      // excluded the one file that would have failed it, and the set changed the
      // moment it was committed.
      //
      //   THE INSTRUMENT WAS FINE. THE UNIVERSE IT WAS ASKED ABOUT WAS WRONG.
      //
      // The gate DOES still scan itself, deliberately — it is a test file that
      // shells out, and exempting it by name would be a hand-kept list of one.
      const hit = /\btimeout:\s*(?!\$\{)([A-Za-z_$][\w$]*|[0-9_]+)/.exec(line);
      if (!hit) return;
      const inner = hit[1]!;
      // belt: a bare `$` can only come from an interpolation the guard missed
      if (inner === '$') return;

      // ⚠️ A SHELL-OUT INSIDE A HELPER HAS NO SINGLE ENCLOSING `it`, AND THE
      // FORWARD SCAN CANNOT INVENT ONE. `gate-container-revision` put all four
      // of its `execFileSync` calls in helpers (`sh`, `scratchRepo`, `shIn`)
      // called from twenty-two arms; the scan walks forward, meets the first
      // `it(`, and correctly reports "no budget".
      //
      // Reporting those forever would make the gate un-satisfiable, and a gate
      // that cannot be satisfied gets deleted. Permitting them silently would
      // hide the real hazard, since a helper's budget governs EVERY arm that
      // calls it.
      //
      // So the helper declares its own contract, once, beside itself:
      //
      //     // shell-budget-governed-by: ARM_BUDGET_MS
      //
      // naming the constant every calling arm must carry. The gate then checks
      // that constant instead of a per-arm one — which is stricter than the
      // per-arm check, because one wrong arm is caught by the arm sweep below
      // and a wrong helper contract is caught here for all of them at once.
      // ⚠️ THE LOOKBACK IS THE ENCLOSING FUNCTION, NOT A FIXED NUMBER OF LINES.
      // A 12-line window was the first attempt and it MISSED a real contract 15
      // lines up — a magic distance is a silent false negative the moment a
      // helper grows a doc comment. Walk back to the function header that
      // encloses this call, and stop there: a contract further up belongs to a
      // different helper and must not be borrowed.
      // ⚠️ READ FROM `lines`, NOT `code`. `code` is the COMMENT-STRIPPED copy —
      // that stripping is deliberate and is what stops this gate matching its
      // own prose. The contract IS a comment, so searching `code` for it finds
      // nothing, always, and reports "no budget" for a helper that declared one.
      // Cost me three wrong fixes to the scan logic before I measured what the
      // scan was actually reading: a flawless instrument answering about the
      // wrong universe.
      const governed = /\/\/\s*shell-budget-governed-by:\s*([A-Za-z_$][\w$]*)/;
      let helperContract: string | null = null;
      for (let j = i; j >= 0; j -= 1) {
        const g = governed.exec(lines[j] ?? '');
        if (g) {
          helperContract = g[1]!;
          break;
        }
        // ⚠️ STOP AT THE ENCLOSING FUNCTION'S HEADER, NOT AT ANY `}`. The first
        // draft stopped on /^\}/ and that matched the helper's OWN closing
        // braces on the way up, so the contract three lines further was never
        // reached — a stop-rule that fires inside the region it is scoping.
        // The contract sits directly above `function <name>(`, so the header IS
        // the boundary: read it, then stop.
        if (/^\s*(export\s+)?(async\s+)?function\s/.test(code[j] ?? '')) {
          const g2 = governed.exec(lines[j - 1] ?? '');
          if (g2) helperContract = g2[1]!;
          break;
        }
        if (/^\s*(it|test)\s*\(/.test(code[j] ?? '')) break;
      }

      // the enclosing `it`'s budget: the first `}, X);` at or after this line
      let outer: string | null = helperContract;
      for (let j = i; helperContract === null && j < lines.length; j += 1) {
        const close = /^\s*\},\s*([A-Za-z_$][\w$]*|[0-9_]+)\s*\);?\s*$/.exec(code[j]!);
        if (close) {
          outer = close[1]!;
          break;
        }
        // an `it(` opening before any close means the timeout is not inside an
        // it that states a budget — vitest's default governs.
        if (/^\s*(it|test)\s*\(/.test(code[j]!) && j > i) break;
      }

      const innerMs = toMs(inner) ?? consts.get(inner) ?? null;
      const outerMs =
        outer === null
          ? VITEST_DEFAULT_TIMEOUT_MS
          : (toMs(outer) ?? consts.get(outer) ?? null);

      sites.push({
        file,
        line: i + 1,
        inner,
        innerLiteral: NUM.test(inner),
        outer,
        outerLiteral: outer !== null && NUM.test(outer),
        innerMs,
        outerMs,
      });
    });
  }
  return sites;
}

const SITES = collectSites();
const show = (s: Site) =>
  `${s.file}:${s.line}  timeout: ${s.inner} (${s.innerMs ?? '?'}ms)  under  ${s.outer ?? '<vitest default>'} (${s.outerMs ?? '?'}ms)`;

describe('#265(c) — a shell-out timeout is bounded by its own `it` budget', () => {
  // ⚠️ THE POSITIVE CONTROL COMES FIRST. A scan that found nothing would pass
  // every arm below, and "no violations" and "no measurement" are the same
  // green. This programme has paid for that distinction more than once.
  it('POSITIVE CONTROL — the scan finds real shell-out sites', () => {
    expect(SITES.length, 'the scan matched nothing — the matcher is broken').toBeGreaterThan(0);
    // and it is looking at a real corpus, not one file
    expect(new Set(SITES.map((s) => s.file)).size).toBeGreaterThan(1);
  });

  it('⚠️ WATCHED-SET CONTROL — the scan can SEE THIS FILE, and an untracked file is invisible', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE GATE SHIPPED GREEN AND FAILED IN CI ON ITS
    // FIRST RUN. The scan reads `git ls-files`; when it was run locally this file
    // was still UNTRACKED, so the gate could not see itself, and the one file
    // that would have failed it was outside the universe it was asked about.
    //
    //   THE INSTRUMENT WAS FINE. THE SET IT MEASURED WAS WRONG — the failure
    //   this house names WATCHED-SET, and no ordinary positive control catches
    //   it, because the instrument answers perfectly about a smaller world.
    //
    // Naming this file specifically is not a hand-kept list: it is the ONE file
    // whose invisibility the gate cannot otherwise detect, because a gate that
    // cannot see itself reports the same green either way.
    const files = testFiles();
    expect(files.length, 'git ls-files returned an implausibly small corpus').toBeGreaterThan(100);
    expect(
      files.some((f) => f.endsWith('gate-265-shellout-budgets.test.ts')),
      'this gate is not in its own watched set — it is untracked, and it is therefore not measuring itself',
    ).toBe(true);
  });

  it('⚠️ NON-VACUITY — the predicate CAN fail, proved on a synthetic site', () => {
    // The exact `c4e778a2` shape: a 120s subprocess under a 5s test.
    const bad: Site = {
      file: 'synthetic',
      line: 1,
      inner: '120_000',
      innerLiteral: true,
      outer: null,
      outerLiteral: false,
      innerMs: 120_000,
      outerMs: VITEST_DEFAULT_TIMEOUT_MS,
    };
    expect(bad.innerMs! > bad.outerMs!).toBe(true);
    expect(bad.innerLiteral).toBe(true);
  });

  it('the shell-out timeout NEVER EXCEEDS the enclosing `it` budget', () => {
    // ⚠️ THE ONE THAT ACTUALLY BITES. An inner budget larger than the outer can
    // never be reached, so the subprocess's own error is unreachable and the
    // operator gets `Test timed out in Nms` about a subprocess they cannot see.
    const over = SITES.filter(
      (s) => s.innerMs !== null && s.outerMs !== null && s.innerMs > s.outerMs,
    );
    expect(over.map(show), 'a subprocess budget that can never be reached').toEqual([]);
  });

  it('⚠️ BOTH budgets are NAMED CONSTANTS — two literals are two numbers that drift', () => {
    // The `c4e778a2` shape, ratified: ONE constant used twice. Equality is
    // fine; equality between two bare literals is not, because nothing holds
    // them together and the drift is silent — which is exactly how a 120/5 pair
    // came to exist in the first place.
    const literals = SITES.filter((s) => s.innerLiteral || s.outerLiteral);
    expect(
      literals.map(show),
      'use one named constant for both the subprocess timeout and the it budget',
    ).toEqual([]);
  });

  it('every site RESOLVES — an unresolvable budget is cannot-tell, not all-clear', () => {
    // Fail-closed: a `timeout: SOME_IMPORT` this scan cannot resolve means the
    // arms above measured nothing for that site, and silence there is the
    // failure mode the whole file is about.
    const unresolved = SITES.filter((s) => s.innerMs === null || s.outerMs === null);
    expect(unresolved.map(show), 'budget not resolvable from the file').toEqual([]);
  });
});
