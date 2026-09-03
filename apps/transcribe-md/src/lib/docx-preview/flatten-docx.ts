// ============================================================================
// FLATTEN A WHOLE .docx PACKAGE FOR CONVERSION.
// ----------------------------------------------------------------------------
// Unzips, unwraps every content control in every part that can carry one, and
// re-zips. See `flatten-sdt.ts` for WHY this exists and what it costs; this file
// is only the packaging.
// ============================================================================
import JSZip from 'jszip';

import { DEFAULT_TEMPLATE_DOCX_LIMITS } from '../note-template-docx/limits';
import { flattenContentControls } from './flatten-sdt';

/**
 * ⚠️ EVERY PART THAT CAN CARRY A CONTROL, NOT JUST `document.xml`.
 *
 * A content control is legal in headers and footers, and the customer template
 * this defect was found on ships TWO headers. Flattening only the body would fix
 * the visible page and leave a letterhead field empty for exactly the same
 * reason — the defect surviving in the one place a referring physician looks
 * first.
 *
 * Endnotes and footnotes are included for the same reason: cheap to cover,
 * and their absence would be a silent hole.
 */
const FLATTENABLE = /^word\/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$/;

/**
 * Returns a copy of `docx` with every `w:sdt` unwrapped.
 *
 * ⚠️ THE CALLER OWNS FAIL-OPEN. This throws on a package it cannot read, and
 * `convertDocxToPdf` catches it and sends the original bytes — a PDF with empty
 * controls is the defect being fixed, but NO PDF is worse.
 */
export async function flattenDocxForConversion(docx: Uint8Array): Promise<Uint8Array> {
  const zip = await JSZip.loadAsync(docx);
  const names = Object.keys(zip.files).filter((n) => FLATTENABLE.test(n));
  // ⚠️ NON-VACUITY, AND IT IS A REAL GUARD RATHER THAN A COMMENT. A package
  // whose body part is missing or renamed would flatten NOTHING and return
  // silently — indistinguishable from a document that simply had no controls,
  // and the PDF would be empty again with nothing to say why.
  if (!names.includes('word/document.xml')) {
    throw new Error('flattenDocxForConversion: word/document.xml not found');
  }
  // ⚠️ THE SAME CEILINGS THE HARDENED TEMPLATE READER USES — IMPORTED, NOT
  // RETYPED. This function unzips a doctor-supplied package into the app's own
  // heap and rebuilds it, which the previous code did with no ceiling at all.
  // The refutation pass measured a document whose XML deflates **218:1**: a
  // 92 KB upload carrying 20 MB of XML. `note-template-docx`'s reader REFUSES
  // that archive; this path would have inflated it. Reusing the constants
  // rather than inventing new ones means the two cannot drift apart.
  const { maxEntryUncompressedBytes, maxTotalUncompressedBytes } =
    DEFAULT_TEMPLATE_DOCX_LIMITS;

  let total = 0;
  for (const name of names) {
    const file = zip.file(name);
    if (!file) continue;
    const xml = await file.async('string');
    // Byte length, not string length — a multi-byte part is bigger than it
    // looks, and the cap is about memory.
    const bytes = Buffer.byteLength(xml, 'utf8');
    total += bytes;
    if (bytes > maxEntryUncompressedBytes || total > maxTotalUncompressedBytes) {
      throw new Error(
        `flattenDocxForConversion: ${name} exceeds the uncompressed ceiling ` +
          `(${bytes} bytes, ${total} total)`,
      );
    }
    if (!xml.includes('<w:sdt')) continue;
    zip.file(name, flattenContentControls(xml));
  }
  return zip.generateAsync({ type: 'uint8array' });
}
