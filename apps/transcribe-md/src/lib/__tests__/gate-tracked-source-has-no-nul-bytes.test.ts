// ============================================================================
// A NUL BYTE IN A SOURCE FILE MAKES THAT FILE INVISIBLE TO `grep -r`.
// ----------------------------------------------------------------------------
// Found 2026-08-21 during the F24-CAPTION-VALIDATION recon, by accident, and it
// is the accident that argues for this guard.
//
// `splice-note-section.ts:109` held `spliceNoteSection(markdown, label, <NUL>probe')`
// — a stray NUL inside a string literal. It was FUNCTIONALLY INERT:
// `readNoteSection` throws away the spliced text and returns `previousBody`,
// which is computed from the original lines, so that byte never reached a note.
//
// ⚠️ THE COST WAS NOT RUNTIME. IT WAS EVERY SWEEP THIS PROGRAMME RUNS.
// `file(1)` classified the file as `data`, so GNU grep treated it as binary and
// SUPPRESSED ITS OUTPUT ENTIRELY — no match lines, no "Binary file … matches",
// nothing. Measured on the real tree before the fix:
//
//   grep -rn spliceNoteSection --include=*.ts apps/transcribe-md/src
//     -> note-table-edit.ts, the test file … and NOT THE DEFINITION SITE
//   git grep -c spliceNoteSection
//     -> apps/transcribe-md/src/lib/splice-note-section.ts:2
//
// Two instruments, opposite answers, on a file that is a live dependency of the
// note editor. That is this repository's own "TWO ZEROES WITH OPPOSITE MEANINGS
// IS ONE BROKEN INSTRUMENT" diagnostic, arriving in the tooling rather than in a
// query — and nothing anywhere announced the omission. A census over
// `apps/**/*.ts` written with plain `grep` had a hole in it exactly the size of
// this file, and would have reported a confident zero.
//
// ⚠️ WHY A GUARD AND NOT JUST THE ONE-BYTE DELETION. The deletion is a fact
// about today. Nothing in the toolchain refuses a NUL: `tsc` accepts it, the
// bundler accepts it, every test stayed green, and the ONLY visible symptom is
// a sweep that quietly under-reports. A defect whose sole symptom is a silent
// hole in your instruments is one nobody finds twice by luck.
//
// WHAT WOULD MAKE THIS FAIL: any tracked source file under apps/ or packages/
// acquiring a NUL byte. Proved in the direction that matters — it read 1 before
// the fix and 0 after, so it MOVED when the fix landed rather than merely being
// green (canon: "mutate toward SUCCESS, not just toward failure").
// ============================================================================

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { describe, it, expect } from 'vitest';

/** Repo root, from apps/transcribe-md — the same idiom the other gates use. */
const ROOT = join(process.cwd(), '..', '..');

const ROOTS = ['apps', 'packages'];

/** Directories that hold build output or vendored code, never authored source. */
const SKIP_DIRS = new Set([
  'node_modules',
  '.next',
  '.git',
  'dist',
  'build',
  'coverage',
  'test-results',
  'playwright-report',
  '.turbo',
]);

const SOURCE_EXT = /\.(ts|tsx|js|jsx|mjs|cjs)$/;

/**
 * The file that carried the defect. It is named BY HAND rather than trusted to
 * the walker, because "the sweep found no NULs" and "the sweep never opened
 * this file" produce the identical output — which is the exact failure this
 * whole gate exists to describe.
 */
const MUST_BE_SCANNED = 'apps/transcribe-md/src/lib/splice-note-section.ts';

/**
 * A floor under the scan, so a walker that silently covers nothing cannot pass.
 * Measured 2026-08-21: `git ls-files` reports 1244 matching files; 900 leaves
 * room for ordinary deletion without becoming a second thing to maintain.
 */
const MIN_FILES_SCANNED = 900;

function walk(dir: string, out: string[]): void {
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return;
  }
  for (const entry of entries) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    let isDir: boolean;
    try {
      isDir = statSync(full).isDirectory();
    } catch {
      continue;
    }
    if (isDir) walk(full, out);
    else if (SOURCE_EXT.test(entry)) out.push(full);
  }
}

describe('tracked source carries no NUL bytes', () => {
  const files: string[] = [];
  for (const r of ROOTS) walk(join(ROOT, r), files);
  const scanned = files.map((f) => relative(ROOT, f).split('\\').join('/'));

  it('the walk actually covered the tree (non-vacuity floor)', () => {
    expect(scanned.length).toBeGreaterThanOrEqual(MIN_FILES_SCANNED);
  });

  it('and it covered the file that carried the defect (named control)', () => {
    // A zero over a set that excludes the known case is worth nothing. This arm
    // is what makes the zero below mean something.
    expect(scanned).toContain(MUST_BE_SCANNED);
  });

  it('no source file contains a NUL byte', () => {
    const offenders: string[] = [];
    for (const f of files) {
      let buf: Buffer;
      try {
        buf = readFileSync(f);
      } catch {
        continue;
      }
      if (buf.includes(0)) offenders.push(relative(ROOT, f).split('\\').join('/'));
    }
    // Named, not counted: a bare number tells whoever hits this nothing about
    // which sweep of theirs has just gone blind.
    expect(offenders).toEqual([]);
  });
});
