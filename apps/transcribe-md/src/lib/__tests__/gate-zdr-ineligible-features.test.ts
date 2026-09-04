// ============================================================================
// NO ZDR-INELIGIBLE FEATURE MAY TOUCH THE CLINICAL PATH.
// ----------------------------------------------------------------------------
// Anthropic's data-retention arrangements are per-FEATURE as well as per-model.
// Verified 2026-09-04 against the current documentation: the Messages API,
// structured outputs, prompt caching and citations are ZDR-eligible; BATCH
// PROCESSING, the FILES API, CODE EXECUTION and PROGRAMMATIC TOOL CALLING are
// NOT — on either ZDR or HIPAA readiness.
//
// ⚠️ SO A MODEL BEING ELIGIBLE IS NOT THE WHOLE ANSWER. A ZDR-eligible model
// reached through an ineligible feature stores the prompt anyway, and on this
// product the prompt is a patient's dictation. The eligibility we rely on is
// the PAIR, and only one half of it is pinned anywhere.
//
// ⚠️ ENUMERATED BY ENDPOINT, NOT BY VOCABULARY. "We don't use batching" is a
// claim about intent; `/v1/messages/batches` is a claim about a call. The SDK
// surfaces below are the things that actually reach those endpoints.
// ============================================================================
import { existsSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const REPO = resolve(process.cwd(), '../..');

/** A watched directory that does not exist. Surfaces as a failure, not a crash. */
const MISSING_MARKER = '\u0000MISSING:';

/**
 * The clinical/PHI path. A patient's dictation, note text, or template content
 * can reach any of these.
 */
const WATCHED_DIRS = [
  join(REPO, 'packages/ai/src'),
  join(REPO, 'apps/transcribe-md/src/lib'),
  join(REPO, 'apps/transcribe-md/src/actions'),
];

/**
 * ZDR- AND HIPAA-INELIGIBLE SURFACES, each named by what it CALLS.
 *
 * ⚠️ BOTH THE REST PATH AND THE SDK ACCESSOR ARE LISTED. A sweep that watched
 * only the URL would miss `client.messages.batches.create(...)`, which never
 * spells its endpoint anywhere in this repo.
 */
const FORBIDDEN: ReadonlyArray<{ readonly what: string; readonly patterns: readonly RegExp[] }> = [
  {
    what: 'batch processing (/v1/messages/batches)',
    patterns: [/\/v1\/messages\/batches/, /\.messages\s*\.\s*batches\b/],
  },
  {
    what: 'the Files API (/v1/files)',
    // ⚠️ NOT BOUND TO A RECEIVER NAME. The first version matched
    // `client.files.` and a planted `c.beta.files.upload({})` walked straight
    // past it — canon 100, a lint's zero as a fact about an identifier. The
    // METHOD is the thing that reaches the endpoint, whatever the variable is
    // called, so the method is what is matched.
    patterns: [
      /['"`]\/v1\/files/,
      /\.\s*files\s*\.\s*(?:upload|create|list|retrieve|delete|download)\s*\(/,
    ],
  },
  {
    what: 'code execution (container data retained up to 30 days)',
    patterns: [/['"`]code_execution['"`]/, /\bcode_execution_tool\b/],
  },
  {
    what: 'programmatic tool calling (built on code-execution containers)',
    patterns: [/\bprogrammatic_tool_calling\b/, /\ballowed_callers\b/],
  },
];

function sourceFiles(dir: string): string[] {
  // ⚠️ FAIL-CLOSED ON A MISSING DIRECTORY, NOT CRASH. Repointing a watched dir
  // at nothing made the whole FILE error out — vitest reported "no tests",
  // which reads like a config problem rather than a gate that lost its corpus.
  if (!existsSync(dir)) return [MISSING_MARKER + dir];
  const out: string[] = [];
  const walk = (d: string) => {
    for (const name of readdirSync(d)) {
      const p = join(d, name);
      const st = statSync(p);
      if (st.isDirectory()) {
        // fixtures and arms may legitimately NAME these surfaces
        if (name === '__tests__' || name === '__fixtures__' || name === 'node_modules') continue;
        walk(p);
      } else if (/\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name)) {
        out.push(p);
      }
    }
  };
  walk(dir);
  return out;
}

/** ⚠️ COMMENTS STRIPPED, or the gate reports its own documentation. */
function code(path: string): string {
  return readFileSync(path, 'utf8')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');
}

describe('no ZDR-ineligible Anthropic feature is reachable from the clinical path', () => {
  const files = WATCHED_DIRS.flatMap(sourceFiles);

  it('⚠️ NON-VACUITY: the watched set is real and non-trivial', () => {
    // A gate whose corpus is empty passes forever. The floor is tied to the
    // MEASURED corpus rather than to a number somebody remembered.
    const missing = files.filter((f) => f.startsWith(MISSING_MARKER));
    expect(missing, `watched directory does not exist: ${missing.join(', ')}`).toEqual([]);
    expect(files.length, 'the watched directories resolved to nothing').toBeGreaterThan(100);
    // and it must actually contain the AI client, or it is watching the wrong tree
    expect(files.some((f) => f.endsWith('packages/ai/src/anthropic.ts'))).toBe(true);
  });

  it('⚠️ no module CALLS batch processing, Files, code execution, or programmatic tool calling', () => {
    const hits: string[] = [];
    for (const file of files) {
      const src = code(file);
      for (const { what, patterns } of FORBIDDEN) {
        for (const re of patterns) {
          if (re.test(src)) hits.push(`${file.replace(REPO, '')} → ${what} (${re})`);
        }
      }
    }
    expect(hits, `ZDR-ineligible surface on the clinical path:\n${hits.join('\n')}`).toEqual([]);
  });

  it('⚠️ POSITIVE CONTROL: a planted call in a REAL watched file is caught', () => {
    // A control made of string literals in memory proves the regex compiles,
    // not that the scan reaches files. This one is a real path from the real
    // watched set, read the same way the gate reads it.
    const target = files.find((f) => f.endsWith('packages/ai/src/anthropic.ts'));
    expect(target, 'the control needs a real watched file').toBeDefined();
    const planted = `${code(target!)}\nconst x = await client.messages.batches.create({});\n`;
    const caught = FORBIDDEN.some(({ patterns }) => patterns.some((re) => re.test(planted)));
    expect(caught, 'a planted batch call in a real watched file was NOT caught').toBe(true);
  });

  it('⚠️ a forbidden token in a COMMENT is not a call — stripping is armed', () => {
    // ⚠️ THIS ARM DRIVES THE GATE'S OWN `code()` ON A REAL FILE. The first
    // version reimplemented the stripping inline, so mutating `code()` changed
    // nothing and the mutation redded ZERO — a control that never touches a
    // file cannot guard files, and one that reimplements its subject is not a
    // control at all.
    const tmp = join(tmpdir(), `zdr-gate-${process.pid}.ts`);
    writeFileSync(
      tmp,
      [
        '// we deliberately do not use client.messages.batches.create here',
        '/* nor the /v1/files endpoint, nor code_execution */',
        'export const real = 1;',
      ].join('\n'),
    );
    try {
      const stripped = code(tmp);
      expect(
        FORBIDDEN.some(({ patterns }) => patterns.some((re) => re.test(stripped))),
        'a mention in a comment was treated as a call',
      ).toBe(false);
      // NON-VACUITY: the same tokens UNCOMMENTED in a real file must be caught,
      // or this arm would pass on a `code()` that returned the empty string.
      writeFileSync(tmp, 'const x = client.messages.batches.create({});\n');
      expect(
        FORBIDDEN.some(({ patterns }) => patterns.some((re) => re.test(code(tmp)))),
        'the gate stopped seeing a real call',
      ).toBe(true);
    } finally {
      rmSync(tmp, { force: true });
    }
  });

  it('⚠️ POSITIVE CONTROL: each forbidden surface catches its own shape', () => {
    // one control per row, so a row that stops matching anything is visible
    const specimens: ReadonlyArray<readonly [string, string]> = [
      ['batch processing (/v1/messages/batches)', 'await fetch("/v1/messages/batches")'],
      ['the Files API (/v1/files)', 'await client.beta.files.upload({})'],
      ['code execution (container data retained up to 30 days)', 'tools: [{ type: "code_execution" }]'],
      ['programmatic tool calling (built on code-execution containers)', 'allowed_callers: ["x"]'],
    ];
    expect(specimens).toHaveLength(FORBIDDEN.length);
    for (const [what, specimen] of specimens) {
      const row = FORBIDDEN.find((f) => f.what === what);
      expect(row, `no row named ${what}`).toBeDefined();
      expect(
        row!.patterns.some((re) => re.test(specimen)),
        `the row for ${what} no longer matches its own shape`,
      ).toBe(true);
    }
  });
});
