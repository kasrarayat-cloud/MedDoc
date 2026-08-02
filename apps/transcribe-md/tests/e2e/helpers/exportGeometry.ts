// ============================================================================
// Read the PAGE and the TYPE out of a downloaded export.
// ----------------------------------------------------------------------------
// ⚠️ THE PARITY CHECK THIS SITS BESIDE COULD NOT SEE EITHER.
//
// `exportText.ts` strips every XML tag to compare section headings, which
// discards `w:pgSz`, `w:pgMar`, `w:rFonts` and `w:sz`; and it reads the PDF
// through `unpdf`'s text extractor, which returns bare strings. Both are the
// right tools for "are the words there" and structurally blind to "is it the
// same page, in the same face".
//
// That blindness had a live cost: the PDF was US Letter and the Word file was
// A4 — the `docx` library's default, which nobody chose — and because the
// on-screen preview is Gotenberg's render of the DOCX, the doctor read one page
// size and downloaded another. The text check passed the whole time.
//
// So these helpers read the bytes: the zip entry for Word, the page viewport
// and font dictionary for PDF.
// ============================================================================

import { readFile } from 'node:fs/promises';

import JSZip from 'jszip';
import { getDocumentProxy } from 'unpdf';

export interface ExportGeometry {
  /** Page box in POINTS, whatever unit the container stored it in. */
  widthPt: number;
  heightPt: number;
  /** Font family names the artifact actually carries. For PDF these are the
   *  EMBEDDED faces (`/BaseFont`); for DOCX the ones the runs NAME (`w:rFonts`),
   *  which is all a Word file can do — the difference is why the converter has
   *  to have them installed. */
  fonts: string[];
}

const TWIPS_PER_PT = 20;

export async function docxGeometry(path: string): Promise<ExportGeometry> {
  const zip = await JSZip.loadAsync(await readFile(path));
  const entry = zip.file('word/document.xml');
  if (!entry) throw new Error(`${path}: no word/document.xml — not a .docx?`);
  const xml = await entry.async('string');

  const sz = xml.match(/<w:pgSz\b[^>]*\/>/)?.[0];
  if (!sz) throw new Error(`${path}: no <w:pgSz> — the section declares no page`);
  const num = (attr: string) => Number(sz.match(new RegExp(`w:${attr}="(\\d+)"`))?.[1] ?? NaN);

  // ⚠️ FONTS LIVE IN TWO PARTS, AND READING ONE REPORTS A FALSE ABSENCE.
  // The first draft of this helper scanned `word/document.xml` only and
  // concluded the export "does not name Charter". It does: Charter is the
  // DOCUMENT-LEVEL DEFAULT run style, which Word stores in `word/styles.xml`
  // (`docx-generator.ts` sets it via `styles.default.document.run`), and
  // `document.xml` then carries only the per-run OVERRIDES — Inter Tight on
  // labels. Scanning the part where the exceptions live and calling it the
  // font list is an answer about a set whose boundary was never established.
  const parts = ['word/styles.xml', 'word/document.xml'];
  const fonts: string[] = [];
  for (const part of parts) {
    const f = zip.file(part);
    if (!f) continue;
    const partXml = await f.async('string');
    for (const m of partXml.matchAll(/w:ascii="([^"]+)"/g)) fonts.push(m[1]);
  }

  return {
    widthPt: num('w') / TWIPS_PER_PT,
    heightPt: num('h') / TWIPS_PER_PT,
    fonts: [...new Set(fonts)].sort(),
  };
}

export async function pdfGeometry(path: string): Promise<ExportGeometry> {
  const bytes = await readFile(path);
  const doc = await getDocumentProxy(new Uint8Array(bytes));
  const page = await doc.getPage(1);
  const vp = page.getViewport({ scale: 1 });

  // `/BaseFont` names the EMBEDDED faces. Subset prefixes (`ABCDEF+`) are
  // stripped so a comparison is about the family, not the subset id.
  const fonts = [
    ...new Set(
      [...bytes.toString('latin1').matchAll(/\/BaseFont\s*\/([A-Za-z0-9+\-,_]+)/g)].map((m) =>
        m[1].replace(/^[A-Z]{6}\+/, ''),
      ),
    ),
  ].sort();

  return { widthPt: Math.round(vp.width), heightPt: Math.round(vp.height), fonts };
}

/** True when `fonts` contains a face from `family`, ignoring weight/style
 *  suffixes and the space in "Inter Tight" vs "InterTight". */
export const hasFamily = (fonts: string[], family: string): boolean => {
  const norm = (s: string) => s.toLowerCase().replace(/[^a-z]/g, '');
  return fonts.some((f) => norm(f).includes(norm(family)));
};
