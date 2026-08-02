// ============================================================================
// The page the default QuillMD export is drawn on — ONE definition, two units.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE A MISSING UNIT CONVERSION SHIPPED A SPLIT PAGE.
//
// `pdf-generator.ts` draws with pdfkit, which takes POINTS, and had always used
// US Letter. `docx-generator.ts` builds with the `docx` library, which takes
// TWIPS, and declared no page properties at all — so Word used the library's
// own default, **A4**. Nobody chose A4 and nothing recorded it.
//
// That is not a cosmetic split, because of what the preview is:
//
//     preview  = generateVisitDocx() → Gotenberg/LibreOffice → PDF → canvas
//     download = generateVisitPdf()  (pdfkit)
//
// The on-screen paper IS a render of the Word file. So the doctor was reading
// an A4 page and downloading a Letter one, and `SPEC.md:200` — "exports must
// match preview 1:1" — could not hold no matter what either generator drew.
//
// Text extraction could never have caught it: the parity check that existed
// compares section-heading STRINGS, and stripping XML tags throws away
// `w:pgSz`, `w:pgMar`, `w:rFonts` and `w:sz`. `gate-c2b-export-parity` asserts
// on the bytes instead — it packs the DOCX and reads the element.
//
// ⚠️ SCOPE. Both generators also render the `formOnly` / `headerFields`
// branches, which a custom template drives. Those are branches INSIDE the
// default renderer; the doctor's own form BYTES go through `pdf-native` /
// `template-twin`, which short-circuit before this module is reached and are
// untouched. One page geometry for everything the default renderer draws is the
// consistent answer, not a second geometry for forms.
// ============================================================================

/** US Letter, in points — the unit pdfkit takes. 612 x 792 at 1" margins is
 *  what the PDF generator has always drawn; the Word file now follows it. */
export const PAGE_PT = {
  width: 612,
  height: 792,
  margin: 72,
} as const;

/** The type scale, in points, for BOTH generators.
 *
 *  Five of these seven roles already agreed across the two files by
 *  coincidence — they were typed as literals on each side with no conversion
 *  between them, so the agreement was luck rather than structure. `body` did
 *  not agree: the PDF drew 10.5pt and the Word file 10pt, and `body` is the
 *  clinical prose itself, the most-used role in the document. */
export const TYPE_PT = {
  title: 16,
  sectionHead: 12,
  body: 10.5,
  small: 9,
  footer: 8.5,
  /** The chart-header block: label smaller/uppercase/muted, value larger. */
  fieldLabel: 8,
  fieldValue: 11,
} as const;

/** Font families both generators name.
 *
 *  ⚠️ NAMING IS NOT RESOLVING. The PDF EMBEDS these from
 *  `apps/transcribe-md/fonts/`. The Word file only names them, and the preview
 *  is rendered by LibreOffice inside the Gotenberg container — which shipped
 *  with neither face installed (measured: `fc-list` returned 0 for both), so
 *  it substituted and the preview could not match the PDF even at an identical
 *  size. The container now carries the same TTFs the PDF embeds. */
export const EXPORT_FONT = {
  body: 'Charter',
  label: 'Inter Tight',
} as const;

/** points → half-points, the unit `docx` uses for `TextRun.size`. */
export const toHalfPt = (pt: number): number => Math.round(pt * 2);

/** points → twips (twentieths of a point), the unit `docx` uses for page
 *  geometry. 612pt x 20 = 12240, which is US Letter; the library's default is
 *  11906 x 16838, which is A4. The two are close enough to look like a rounding
 *  difference in a diff and are a different sheet of paper in a printer. */
export const toTwip = (pt: number): number => Math.round(pt * 20);
