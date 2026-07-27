// ============================================================================
// A field you read must be a field you selected.
// ----------------------------------------------------------------------------
// `packages/db` exports the Prisma client as `any`, so a select result is
// untyped: reading a column you forgot to select gives `undefined`, tsc says
// nothing, and the failure surfaces far away as a wrong branch.
//
// It has bitten four times in this repo:
//   • `practiceId` read off the compiled version, which has no such column
//   • `cptCodes`/`specialty` missing, so a doctor's E/M override was invisible
//     and the baseline could never match a later score
//   • `status` missing, so a guard rejected every visit and the document view
//     silently declined for everyone
//   • `emScoredCode` read before it was added to a select
//
// This checks the actions where a missing field changes a CLINICAL decision:
// every `visit.<field>` read has a matching `<field>: true` in the select.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

/** Actions whose branches turn on visit columns. */
const FILES = [
  'src/actions/preview-visit-document.ts',
  'src/actions/rescore-em.ts',
  'src/actions/chat-edit-visit.ts',
  'src/actions/save-note-section.ts',
];

/** Relations and locals that are not columns. */
const NOT_COLUMNS = new Set(['user', 'id']);

function selectedFields(src: string): Set<string> {
  const out = new Set<string>();
  // Anywhere, not just on its own line: a compact select puts several on one.
  for (const m of src.matchAll(/(\w+):\s*true\b/g)) out.add(m[1]);
  // Nested relation selects, e.g. `user: { select: { practiceId: true } }`.
  for (const m of src.matchAll(/(\w+):\s*\{\s*select:/g)) out.add(m[1]);
  return out;
}

function readFields(src: string): Set<string> {
  // Comments FIRST. An apostrophe in prose ("the doctor's own") would otherwise
  // open a string literal that runs to the next quote, desynchronising the pair
  // matching and leaving real literals unstripped.
  const code = src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '')
    // Then string literals: `convertDocxToPdf(docx, 'visit.docx')` is passing a
    // filename, not reading a column.
    .replace(/'(?:[^'\\]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""')
    .replace(/`(?:[^`\\]|\\.)*`/g, '``');
  const out = new Set<string>();
  for (const m of code.matchAll(/\bvisit[?]?\.(\w+)/g)) out.add(m[1]);
  return out;
}

describe('every visit column a branch reads is selected', () => {
  for (const file of FILES) {
    it(file, () => {
      const src = readFileSync(file, 'utf8');
      const selected = selectedFields(src);
      const missing = [...readFields(src)].filter(
        (f) => !selected.has(f) && !NOT_COLUMNS.has(f),
      );
      expect(
        missing,
        `${file} reads visit.${missing.join(', visit.')} without selecting it — ` +
          `prisma is untyped here, so it reads as undefined and the branch is wrong`,
      ).toEqual([]);
    });
  }
});
