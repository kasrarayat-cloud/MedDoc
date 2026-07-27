// ============================================================================
// A flag-ON CI image must carry every flag the surface it tests reads.
// ----------------------------------------------------------------------------
// The `doc-preview` project asserts on the note-format CONFIRM CARD. That card
// renders only when `isUxSimplify()` is true — and the image the project built
// did not pass NEXT_PUBLIC_UX_SIMPLIFY. So every test in it waited out its
// 180-second timeout, the project had never passed since the day it was added,
// and it burned ~13 minutes of a 40-minute job budget on every run. The
// workflow was green-by-omission for a while and then simply always red.
//
// Nothing pointed at the cause: the tests failed on a missing element, which
// reads as "the feature is broken", not "the build is missing a flag".
//
// This pins the coupling. It is deliberately a source-grep over the workflow —
// the alternative is discovering the mismatch 18 minutes into CI, which is
// exactly what happened.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const WORKFLOW = readFileSync('../../.github/workflows/e2e.yml', 'utf8');

/** Each flag-ON image build in the E2E workflow, and the flags its project's
 *  surfaces actually read. */
const IMAGES: { tag: string; needs: string[]; why: string }[] = [
  {
    tag: 'meddoc-pro-transcribe-md:doc-preview',
    needs: ['NEXT_PUBLIC_DOC_PREVIEW', 'NEXT_PUBLIC_UX_SIMPLIFY'],
    why: 'the confirm card it asserts on is behind isUxSimplify()',
  },
  {
    tag: 'meddoc-pro-transcribe-md:visit-doc',
    needs: [
      'NEXT_PUBLIC_VISIT_DOC_PAGE',
      'NEXT_PUBLIC_DOC_PREVIEW',
      'NEXT_PUBLIC_REVIEW_DOC_VIEW',
      'NEXT_PUBLIC_UX_SIMPLIFY',
    ],
    why: 'it drives the document page, its suggestions and the signed view',
  },
  {
    tag: 'meddoc-pro-transcribe-md:review-doc',
    needs: ['NEXT_PUBLIC_REVIEW_DOC_VIEW'],
    why: 'the pre-sign document surface',
  },
];

/** The `docker build … -t <tag> .` block for one image. */
function buildBlock(tag: string): string {
  const at = WORKFLOW.indexOf(`-t ${tag} .`);
  if (at === -1) return '';
  // Walk back to the `docker build` that owns this -t.
  const start = WORKFLOW.lastIndexOf('docker build', at);
  return start === -1 ? '' : WORKFLOW.slice(start, at);
}

describe('every flag-ON E2E image carries the flags its surface reads', () => {
  for (const img of IMAGES) {
    it(`${img.tag} — ${img.why}`, () => {
      const block = buildBlock(img.tag);
      expect(block, `no docker build found for ${img.tag}`).not.toBe('');
      const missing = img.needs.filter(
        (f) => !new RegExp(`--build-arg\\s+${f}=true`).test(block),
      );
      expect(
        missing,
        `${img.tag} omits ${missing.join(', ')} — its tests will fail on a ` +
          `missing element, which reads as a broken feature rather than a ` +
          `missing build arg, and each one will burn its full timeout first`,
      ).toEqual([]);
    });
  }
});
