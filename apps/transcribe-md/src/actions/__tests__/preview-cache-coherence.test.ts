// ============================================================================
// What the doctor READS must be what the doctor SIGNS.
// ----------------------------------------------------------------------------
// The visit page renders a cached document. The cache key is
// (visit, soapVersion) — so anything that changes the DOCUMENT without moving
// soapVersion has to drop the entry itself, or the doctor re-reads a stale
// rendering for the rest of the 30-minute TTL while the file they download
// carries the new value.
//
// This was latent until every visit started caching a STYLED rendering: before
// that the only cached variant was the twin one, and no production visit had a
// certified twin, so nothing was ever served from cache. The E/M override route
// changed the printed billing level and did neither — found by audit, not by a
// test, which is why this file exists.
//
// Source-level on purpose. The alternative is a live Redis + Postgres per case,
// and the invariant being protected is "somebody remembered to call it".
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

/** Columns that are RENDERED INTO the exported document by docx-generator. A
 *  writer of any of these changes what the page shows. */
const EXPORT_VISIBLE = ['icdCodes', 'cptCodes', 'rxDrafts', 'patientSummary', 'soapFinal'];

/** Every module that writes a visit row, from a sweep of `transcribeVisit.update`
 *  / `updateMany` across actions and route handlers. */
const WRITERS = [
  'src/app/api/visits/[id]/em-score/override/route.ts',
  'src/app/api/visits/[id]/em-score/apply-additions/route.ts',
  'src/app/api/visits/[id]/sign/route.ts',
  'src/actions/soap.ts',
  'src/actions/suggestion-actions.ts',
  'src/actions/save-note-section.ts',
];

function body(file: string): string {
  const noComments = readFileSync(file, 'utf8')
    // Comments FIRST — prose is full of apostrophes, and each one looks like
    // the start of a string literal.
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\/\/[^\n]*/g, '');

  // Then string literals, LINE BY LINE.
  //
  // Stripping them across the whole file is what the sibling select-guard test
  // does, and it is a trap: one apostrophe inside a double-quoted string ("the
  // doctor's note") opens a match that runs to the next apostrophe hundreds of
  // lines away and deletes everything between. On sign/route.ts that ate 70% of
  // the file — including its `invalidateVisitFills` call — and this test failed
  // a module that was already correct. Per-line bounds the damage to the line
  // that confused it.
  //
  // Worth stripping at all because `convertDocxToPdf(docx, 'visit.docx')` is
  // passing a FILENAME that reads exactly like a field access on `visit`.
  return noComments
    .split('\n')
    .map((l) =>
      l
        .replace(/'(?:[^'\\]|\\.)*'/g, "''")
        .replace(/"(?:[^"\\]|\\.)*"/g, '""')
        .replace(/`(?:[^`\\]|\\.)*`/g, '``'),
    )
    .join('\n');
}

describe('a writer of the exported document drops the cached rendering of it', () => {
  for (const file of WRITERS) {
    it(file, () => {
      const src = body(file);
      // Does this module write any column the document prints?
      const writes = EXPORT_VISIBLE.filter((c) => new RegExp(`\\b${c}\\s*:`).test(src));
      if (writes.length === 0) return;

      const bumpsVersion = /soapVersion\s*:\s*\{\s*increment/.test(src);
      const invalidates = /invalidateVisitFills\s*\(/.test(src);

      expect(
        bumpsVersion || invalidates,
        `${file} writes ${writes.join(', ')} — which the exported document prints — ` +
          `but neither bumps soapVersion nor calls invalidateVisitFills. The preview ` +
          `cache is keyed on (visit, soapVersion), so the doctor keeps re-reading the ` +
          `pre-change document while the file they download carries the change.`,
      ).toBe(true);
    });
  }
});

describe('the document action guards a missing visit before it dereferences one', () => {
  const FILE = 'src/actions/preview-visit-document.ts';

  it('the null check precedes the first visit.<field> read', () => {
    const src = body(FILE);
    const guard = src.search(/if\s*\(\s*!\s*visit\s*\)/);
    const firstRead = src.search(/\bvisit\.\w/);

    expect(guard, `${FILE} has no bare \`if (!visit)\` guard`).toBeGreaterThan(-1);
    expect(
      guard,
      `${FILE} dereferences visit.<field> before checking it is non-null. findFirst ` +
        `returns null for a visit that is missing, another doctor's, deleted or ` +
        `archived — all ordinary — and prisma is untyped here, so tsc will not ` +
        `catch it and the action throws instead of returning a named miss.`,
    ).toBeLessThan(firstRead);
  });
});
