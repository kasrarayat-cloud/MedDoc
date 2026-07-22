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

import { templateNativeDocxEnabled } from '@/config/template-native-docx';
import { TemplateDocxError } from '@/lib/note-template-docx/errors';

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
 *  unaffected.
 *
 *  NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX (default OFF): when ON, the .docx first
 *  passes the fail-closed OOXML security boundary (macros/OLE/zip attacks are
 *  REJECTED — the TemplateDocxError propagates and is NEVER swallowed by the
 *  permissive mammoth fallback, which would be fail-open). The marker text
 *  returned is identical to the flag-OFF path for a clean dropdown template, so
 *  the downstream parse/reconcile/fill is unaffected. When OFF, this function is
 *  byte-identical to the live pipeline. */
export async function docxToText(bytes: Uint8Array): Promise<string> {
  if (templateNativeDocxEnabled()) {
    return docxToTextNativeGated(bytes);
  }
  try {
    const { text, dropdownCount } = await docxToTextWithControls(bytes);
    if (dropdownCount > 0) return text;
  } catch (err) {
    // Malformed/unexpected docx internals → fall through to mammoth, which is
    // the proven, more permissive extractor. Log the fall-through (non-PHI —
    // this is a template, no patient data) so a silently-degraded extraction
    // is observable rather than invisible.
    console.warn(
      '[docx-to-text] content-control extraction failed; falling back to mammoth:',
      err instanceof Error ? err.message : String(err)
    );
  }
  const result = await mammoth.extractRawText({ buffer: Buffer.from(bytes) });
  return result.value;
}

/** Flag-ON path. The fail-closed security boundary runs first; a security
 *  rejection (TemplateDocxError) MUST propagate — falling back to mammoth on a
 *  macro/OLE/zip attack would silently defeat the boundary (fail-open). Only a
 *  NON-security parse issue falls through to the proven mammoth extractor. The
 *  compiler is imported lazily so the flag-OFF path and the pure-function tests
 *  never pull the OOXML compiler into their graph. */
async function docxToTextNativeGated(bytes: Uint8Array): Promise<string> {
  try {
    const { ingestDocxTemplateSource } = await import(
      '@/lib/template-twin/ingest-docx-source'
    );
    const ingested = await ingestDocxTemplateSource(bytes);
    if (ingested.dropdownCount > 0) return ingested.markerText;
    // Security-passed plain (no-dropdown) template → proven mammoth extraction.
  } catch (err) {
    if (err instanceof TemplateDocxError) throw err; // fail-closed: never swallow
    console.warn(
      '[docx-to-text] native ingestion failed (non-security); falling back to mammoth:',
      err instanceof Error ? err.message : String(err)
    );
  }
  const result = await mammoth.extractRawText({ buffer: Buffer.from(bytes) });
  return result.value;
}
