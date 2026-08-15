// ============================================================================
// The page the default QuillMD export is drawn on — ONE definition, two units.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS BECAUSE A MISSING UNIT CONVERSION SHIPPED A SPLIT PAGE.
//
// `pdf-generator.ts` drew with pdfkit, which takes POINTS, and had always used
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
// ⚠️ THE SECOND BUILDER IS GONE (ruling #113, 2026-08-15). `pdf-generator.ts`
// was retired and the PDF download now takes the SAME route as the preview:
// `generateVisitDocx()` → Gotenberg → PDF (`lib/visit-pdf.ts`). The past tense
// above is deliberate — the split this file exists to prevent can no longer be
// re-created by a divergence between two generators, because there is one.
// This module survives because the DOCX still has to DECLARE the page it draws
// on; nothing else in the repo records that it is US Letter.
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

// ── R1.4 — the shared paper structure ───────────────────────────────────────
// Everything below was a LITERAL on each side, typed twice, and the two sides
// had drifted. The measured divergences this closes:
//
//   role                 PDF (pdfkit)          DOCX (docx lib)     now
//   ------------------   -------------------   -----------------   ----------
//   section head size    12pt (TYPE_PT)        `size: 22` = 11pt   12pt, both
//   section head rule    200pt hairline        none at all         full width
//   section tracking     1.2pt                 `20` = 1.0pt        1.2pt, both
//   accent               COLORS.accent         '7C3AED' literal    one token
//   metadata label       `LABEL_SIZE = 8`      `size: 16` = 8pt    TYPE_PT
//   metadata value       `VALUE_SIZE = 11`     `size: 22` = 11pt   TYPE_PT
//
// The sizes that already agreed agreed by luck — the same defect `TYPE_PT`'s
// own header describes, one layer out. A literal that happens to be right is
// not a shared definition; it is a coincidence waiting for one side to be
// edited.

/** Ink. The PDF's `COLORS` and the DOCX's inline hex strings, unified. */
export const EXPORT_COLOR = {
  textPrimary: '#111111',
  textMuted: '#666666',
  rule: '#dddddd',
  accent: '#7C3AED',
} as const;

/** The width the content actually occupies, in points. The PDF's section rule
 *  was 200pt — a number with no relationship to the page — and the Word file
 *  drew none. A rule that stops in the middle of nowhere reads as an artifact;
 *  one that spans the measure reads as a rule. */
export const CONTENT_WIDTH_PT = PAGE_PT.width - PAGE_PT.margin * 2;

/** Hairline weight, in points, for the section rules in both generators. */
export const RULE_PT = 0.6;

/** Section marker.
 *
 *  ⚠️ VERIFIED AGAINST THE FONT FILES, NOT ASSUMED. This module's siblings
 *  already record a tofu incident (the task-list checkbox is vector-drawn
 *  because U+2610/U+2612 are absent from the bundled faces). Checked with
 *  fontkit's `hasGlyphForCodePoint` across all seven TTFs in
 *  `apps/transcribe-md/fonts/`, with a positive control (U+0041 present) and a
 *  negative one (U+1F600 absent):
 *
 *      §  U+00A7  present in all 7        ← chosen
 *      —  U+2014  present in all 7
 *      ·  U+00B7  present in all 7
 *      ▪  U+25AA  MISSING from all 4 Charter faces
 *      ■  U+25A0  MISSING from all 4 Charter faces
 *      ─  U+2500  MISSING from all 7
 *
 *  The two geometric marks a designer would reach for first are exactly the
 *  ones that would have shipped as tofu in the body face. */
export const SECTION_MARK = '§';

/** Letter-spacing for section headings, in points. pdfkit takes points;
 *  `docx` takes twentieths of a point, so it goes through `toTwip`. */
export const SECTION_TRACKING_PT = 1.2;

/** What an empty metadata value prints as — muted, never blank, never a
 *  bullet. A blank cell is indistinguishable from a cell that failed to
 *  render; an em-dash says "asked, and there is nothing". */
export const EMPTY_VALUE = '—';

/** The metadata grid's label column, in points. Two columns — label, value —
 *  one field per row. The previous layout was N side-by-side columns whose
 *  width was `contentWidth / N`, so adding a fourth field silently narrowed
 *  the other three and a long chief complaint wrapped to three lines while its
 *  neighbours sat on one. */
export const META_LABEL_COL_PT = 118;

/** points → eighths of a point, the unit `docx` uses for border widths. */
export const toEighthPt = (pt: number): number => Math.max(1, Math.round(pt * 8));

/** '#7C3AED' → '7C3AED'. `docx` wants bare hex; pdfkit wants the hash. One
 *  token, two spellings, converted rather than duplicated. */
export const bareHex = (hex: string): string => hex.replace('#', '').toUpperCase();

/** The title lockup's vertical rhythm, in points, for both generators.
 *
 *  Another pair that was never shared: the PDF drove it with pdfkit's
 *  `moveDown(n)`, which is n × the CURRENT LINE HEIGHT — so the gap under the
 *  wordmark depended on the font size in effect when it ran — while the Word
 *  file used absolute twips (6pt and 12pt). And the PDF drew a rule under the
 *  title that the Word file simply did not have, which is the same
 *  rule-vs-nothing split as the section headings, one block higher up. */
export const LOCKUP_PT = {
  /** Wordmark → title. Was ~2.2pt (PDF) vs 6pt (Word). */
  eyebrowToTitle: 3,
  /** Title → its rule. */
  titleToRule: 6,
  /** Rule → the metadata grid. */
  ruleToBody: 12,
} as const;
