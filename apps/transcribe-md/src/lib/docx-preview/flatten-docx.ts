// ============================================================================
// FLATTEN A WHOLE .docx PACKAGE FOR CONVERSION.
// ----------------------------------------------------------------------------
// Unzips, unwraps every content control in every part that can carry one, and
// re-zips. See `flatten-sdt.ts` for WHY this exists and what it costs; this file
// is only the packaging.
// ============================================================================
import JSZip from 'jszip';

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
   * ⚠️ HOW MANY WRAPPERS CAME OUT — so the caller can tell `applied` from
   * `not_needed`. A flattener that silently matched nothing returns 0 here and
   * is therefore distinguishable from one that had nothing to match; without
   * this number those two are the same green.
   */
  controlsRemoved: number;
}

export async function flattenDocxForConversion(
  docx: Uint8Array,
): Promise<FlattenedPackage> {
  const zip = await JSZip.loadAsync(docx);
  const names = Object.keys(zip.files).filter((n) => FLATTENABLE.test(n));
  // ⚠️ NON-VACUITY, AND IT IS A REAL GUARD RATHER THAN A COMMENT. A package
  // whose body part is missing or renamed would flatten NOTHING and return
  // silently — indistinguishable from a document that simply had no controls,
  // and the PDF would be empty again with nothing to say why.
  if (!names.includes('word/document.xml')) {
    throw new Error('flattenDocxForConversion: word/document.xml not found');
  }
  let controlsRemoved = 0;
  for (const name of names) {
    const file = zip.file(name);
    if (!file) continue;
    const xml = await file.async('string');
    if (!xml.includes('<w:sdt')) continue;
    controlsRemoved += (xml.match(/<w:sdt[ >]/g) ?? []).length;
    zip.file(name, flattenContentControls(xml));
  }
  return { docx: await zip.generateAsync({ type: 'uint8array' }), controlsRemoved };
}
