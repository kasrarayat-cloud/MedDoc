// ============================================================================
// Note-format customization — Phase 2b: .docx → text (webpack-bundled helper)
// ----------------------------------------------------------------------------
// mammoth is imported STATICALLY here so Next/webpack BUNDLES it into the
// server chunk (the same way `docx` is bundled for exports). A bare dynamic
// `import('mammoth')` of the package was NOT traced into the standalone output,
// so the .docx path silently fell back to paste in production. extract-note-
// text.ts dynamically imports THIS local module, so mammoth still loads lazily
// (only when a .docx is actually processed) — the pure-function path + its unit
// tests never pull mammoth in.
// ============================================================================

import mammoth from 'mammoth';

import { docxToTextWithControls } from './docx-content-controls';

/** Extract raw text from a .docx file's bytes. Server-only. Never persists.
 *
 *  A template built with native Word DROPDOWN content controls loses every
 *  option through `mammoth.extractRawText` (it keeps only the placeholder
 *  "Choose an item."). So we FIRST walk the document for dropdowns and, when
 *  any exist, return the content-control reconstruction (fixed text + each
 *  dropdown inlined as a `{{one of: A | B | C}}` choice marker). A docx with
 *  no dropdowns falls back to mammoth — byte-identical to the prior behavior,
 *  so the existing extract-note-text tests and every non-dropdown template are
 *  unaffected. */
export async function docxToText(bytes: Uint8Array): Promise<string> {
  try {
    const { text, dropdownCount } = await docxToTextWithControls(bytes);
    if (dropdownCount > 0) return text;
  } catch {
    // Malformed/unexpected docx internals → fall through to mammoth, which is
    // the proven, more permissive extractor.
  }
  const result = await mammoth.extractRawText({ buffer: Buffer.from(bytes) });
  return result.value;
}
