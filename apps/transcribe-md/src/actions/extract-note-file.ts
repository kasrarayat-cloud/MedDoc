'use server';

// ============================================================================
// Note-format customization — Phase 2b: upload → note text (server action)
// ----------------------------------------------------------------------------
// Accepts ONE uploaded file from the entry screen, extracts text, returns it to
// the client (which then calls parseNoteTemplateAction). The bytes are held in
// memory only — NOTHING is written to disk, DB, or object storage. Paste remains
// the guaranteed path; this is the best-effort upload convenience.
// ============================================================================

import { requireSession } from '@/lib/auth';
import {
  extractNoteTextFromUpload,
  type ExtractResult,
} from '@/lib/note-template-parse/extract-note-text';

/** Hard ceiling on upload size — a single note is tiny; anything large is
 *  almost certainly the wrong file and risks runaway memory/token cost. */
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MB

export async function extractNoteFileAction(formData: FormData): Promise<ExtractResult> {
  await requireSession(); // authenticated doctors only; result isn't doctor-scoped data
  const file = formData.get('file');
  if (!(file instanceof File) || file.size === 0) {
    return { ok: false, fallbackToPaste: true, error: 'No file received. Paste the note instead.' };
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      fallbackToPaste: true,
      error: 'That file is larger than 5 MB. Paste a single representative note instead.',
    };
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  return extractNoteTextFromUpload(bytes, file.name, file.type);
}
