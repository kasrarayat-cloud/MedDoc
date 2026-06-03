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

/** Extract raw text from a .docx file's bytes. Server-only. Never persists. */
export async function docxToText(bytes: Uint8Array): Promise<string> {
  const result = await mammoth.extractRawText({ buffer: Buffer.from(bytes) });
  return result.value;
}
