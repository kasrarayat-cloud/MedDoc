// ============================================================================
// FLATTEN A WHOLE .docx PACKAGE FOR CONVERSION.
// ----------------------------------------------------------------------------
// Unzips, unwraps every content control in every part that can carry one, and
// re-zips. See `flatten-sdt.ts` for WHY this exists and what it costs; this file
// is only the packaging.
// ============================================================================
import JSZip from 'jszip';

import { readVerifiedZipPackage } from '../note-template-docx/zip-directory';
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
export interface FlattenedPackage {
  docx: Uint8Array;
  /**
   * Parts left UNFLATTENED because they could not be flattened safely. Their
   * content controls may render empty. ⚠️ Returned rather than only logged, so
   * the export path can name the degradation in its audit row instead of
   * shipping a quietly-partial PDF.
   */
  skipped: string[];
}

export async function flattenDocxForConversion(docx: Uint8Array): Promise<FlattenedPackage> {
  const zip = await JSZip.loadAsync(docx);
  const names = Object.keys(zip.files).filter((n) => FLATTENABLE.test(n));
  // ⚠️ NON-VACUITY, AND IT IS A REAL GUARD RATHER THAN A COMMENT. A package
  // whose body part is missing or renamed would flatten NOTHING and return
  // silently — indistinguishable from a document that simply had no controls,
  // and the PDF would be empty again with nothing to say why.
  if (!names.includes('word/document.xml')) {
    throw new Error('flattenDocxForConversion: word/document.xml not found');
  }
  // ⚠️ THE CEILING IS TAKEN FROM THE CENTRAL DIRECTORY, BEFORE ANY BYTE IS
  // DECOMPRESSED — AND THAT ORDERING IS THE WHOLE FINDING. The first version
  // measured `Buffer.byteLength` AFTER `file.async('string')` had already
  // materialised the part: a 261 KB upload declaring 268 MB drove heap from
  // 5 MB to 518 MB, thirty-two times the ceiling, and only THEN threw. It also
  // watched five filenames while `generateAsync` re-inflates all twenty-five,
  // so a bomb parked in a NON-flattenable part sailed through and produced a
  // 268 MB package that convert.ts would POST to the sidecar.
  //
  // `readVerifiedZipPackage` is this repo's hardened reader: it reads each
  // entry's declared uncompressed size and compression ratio from the central
  // directory and refuses ZIP_ENTRY_TOO_LARGE / ZIP_COMPRESSION_RATIO_EXCEEDED
  // / ZIP_TOTAL_TOO_LARGE for EVERY entry, before decompression. Reusing it
  // rather than re-implementing means the two cannot drift.
  readVerifiedZipPackage(docx);

  const skipped: string[] = [];
  for (const name of names) {
    const file = zip.file(name);
    if (!file) continue;
    const xml = await file.async('string');

    // ⚠️ EVERY PER-PART DECISION LIVES INSIDE THIS TRY, AND THAT PLACEMENT IS
    // THE POINT. The refusals below were first written ABOVE it, so a CDATA
    // section in one part threw straight out of the function and
    // `convertDocxToPdf` discarded the whole flatten — reintroducing, in the
    // same commit that fixed it, the "one odd header costs the body its 28
    // filled values" defect. A refusal that is not caught is not per-part.
    try {
      // ⚠️ SHAPES THIS FLATTENER CANNOT REASON ABOUT ARE REFUSED, NOT GUESSED
      // AT. A `w:sdt` inside a comment or a CDATA section is TEXT, not a tag,
      // and the tag-removal patterns cannot tell the difference — round three
      // demonstrated character data inside CDATA being discarded. Word emits
      // neither in a document part, so refusing costs nothing real.
      if (xml.includes('<![CDATA[')) {
        throw new Error('CDATA section');
      }
      if (/<!--[\s\S]*?<w:sdt[\s\S]*?-->/.test(xml)) {
        throw new Error('a comment mentions a control');
      }
      if (!xml.includes('<w:sdt')) {
        // ⚠️ AND A DIFFERENTLY-PREFIXED CONTROL IS NAMED RATHER THAN IGNORED.
        // The wordprocessingml namespace may legally bind to a prefix other
        // than `w`; the patterns would then match nothing and this function
        // would report a clean success over a document it never touched — a
        // SILENT no-op. The bytes are unflattened either way; the difference is
        // that somebody can now see why.
        if (/<[A-Za-z][\w.-]*:sdt[ />]/.test(xml)) {
          throw new Error('content controls use a non-`w` namespace prefix');
        }
        continue;
      }
      zip.file(name, flattenContentControls(xml));
    } catch (err) {
      // A part we cannot flatten safely keeps its ORIGINAL bytes; its own
      // controls render empty — the pre-existing defect confined to the one
      // part that earned it — and every other part is still fixed.
      skipped.push(name);
      console.warn(
        `[docx-preview] ${name} left unflattened; its content controls may render EMPTY:`,
        err instanceof Error ? err.message : err,
      );
    }
  }

  // ⚠️ DEFLATE, NOT JSZip's DEFAULT. `generateAsync` re-emits every entry STORED
  // unless told otherwise: the real customer form went 52,884 -> 378,054 bytes,
  // 7.15x, and every one of those bytes crosses to the sidecar on every export.
  return {
    docx: await zip.generateAsync({ type: 'uint8array', compression: 'DEFLATE' }),
    skipped,
  };
}
