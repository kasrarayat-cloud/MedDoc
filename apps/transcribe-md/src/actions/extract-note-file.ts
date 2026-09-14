'use server';

// ============================================================================
// Note-format customization — upload → KEEP THE BYTES → note text.
// ----------------------------------------------------------------------------
// RC-2, ruling #106(b). This file's header used to say, accurately:
//
//     "The bytes are held in memory only — NOTHING is written to disk, DB, or
//      object storage."
//
// ⚠️ THAT SENTENCE IS THE DEFECT, WRITTEN DOWN AS A FEATURE. Every `.docx` a
// doctor uploaded had its text extracted and its bytes dropped. One customer's
// logo and letterhead stopped existing at upload and are recoverable from
// nothing we hold. The fix cannot bring those back; it stops the next one.
//
// ⚠️ THE ORDER IS THE WHOLE RULING: PERSIST, THEN EXTRACT. Extraction is the
// step that can fail — a corrupt file, an unsupported shape, a parser throw —
// and it is precisely when it fails that the original matters most. Persisting
// afterwards would keep the file exactly when it was not needed.
//
// ⚠️ AND PERSISTENCE MUST NEVER COST THE DOCTOR THE UPLOAD. Paste is the
// guaranteed path and upload is the convenience; a storage outage turning a
// working upload into an error would trade a real capability for a
// nice-to-have. So a failed put is logged, reported in the result as
// `sourceKept: false`, and the extraction proceeds — the doctor still gets
// their template, and the ledger says the file was not kept.
// ============================================================================

import { randomUUID } from 'node:crypto';

import { requireSession } from '@/lib/auth';
import {
  extractNoteTextFromUpload,
  type ExtractResult,
} from '@/lib/note-template-parse/extract-note-text';
import {
  createTemplateTwinArtifactStore,
  hasTemplateTwinStorageProvider,
  type UploadArtifactMedia,
} from '@/lib/template-twin/storage';
import { log } from '@/lib/log';

/** Hard ceiling on upload size — a single note is tiny; anything large is
 *  almost certainly the wrong file and risks runaway memory/token cost. */
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MB

/** What the client carries forward so the saved template can point at the file.
 *  Opaque to the client: it round-trips these and never constructs them. */
export interface KeptSourceRef {
  objectKey: string;
  sha256: string;
}

export type ExtractWithSourceResult = ExtractResult & {
  /** Present only when the original bytes were stored. Absent means the file
   *  was NOT kept — a storage outage, a non-docx upload, or an unauthenticated
   *  practice — and the template will record no source. */
  source?: KeptSourceRef;
};

/**
 * The doctor's FORM is kept — the file whose layout the twin pipeline needs and
 * which cannot be reconstructed from extracted text. That is a `.docx` OR (S2,
 * upload-and-certified) a `.pdf`: the PDF is no longer dropped at upload — it is
 * retained (content-addressed, put-once) and becomes a faithful DOCX twin. A
 * pasted note has no file; a `.txt`/`.md` upload IS its own text, so keeping it
 * would duplicate the row. Returns the allowlisted upload media, or null to skip.
 */
function keepableUploadMedia(filename: string, mime: string): UploadArtifactMedia | null {
  const name = filename.toLowerCase();
  if (
    name.endsWith('.docx') ||
    mime === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ) {
    return 'docx';
  }
  if (name.endsWith('.pdf') || mime === 'application/pdf') {
    return 'pdf';
  }
  return null;
}

export async function extractNoteFileAction(
  formData: FormData
): Promise<ExtractWithSourceResult> {
  const session = await requireSession();
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

  // ── PERSIST FIRST. Everything below this point may fail; the bytes survive.
  //
  // ⚠️ `practiceId` IS READ AS A REQUIRED FIELD, NOT AN OPTIONAL ONE. An earlier
  // draft of this function wrote `session.user?.practiceId ?? null` and skipped
  // storage when it was falsy — defensive-looking, and a silent fail-open: the
  // file would simply not be kept, with no signal, which is the defect this
  // whole item exists to end. `ScopedSession.user.practiceId` is required and
  // branded (`asPracticeId`), and `packages/auth` records the same optional-key
  // shape failing open for tenant predicates. If it is ever absent that is a
  // bug to surface, not a reason to quietly discard a doctor's file.
  const { practiceId } = session.user;
  const uploadMedia = keepableUploadMedia(file.name, file.type);
  let source: KeptSourceRef | undefined;
  if (typeof practiceId !== 'string' || practiceId.length === 0) {
    log.error('note-template:source', 'session carries no practice — file NOT kept', {
      userId: session.user.id,
    });
  } else if (uploadMedia && hasTemplateTwinStorageProvider()) {
    try {
      const stored = await createTemplateTwinArtifactStore().storeUploadArtifact({
        practiceId,
        // Per upload ATTEMPT, not per template — no template exists yet, which
        // is the entire reason this key shape had to be added.
        uploadId: randomUUID(),
        bytes,
        media: uploadMedia,
      });
      source = { objectKey: stored.objectKey, sha256: stored.sha256 };
    } catch (err) {
      // ⚠️ NEVER FAIL THE UPLOAD FOR THIS. See the header: a storage outage must
      // not turn a working upload into an error. The absence of `source` in the
      // result is the honest signal, and it is visible to the caller rather
      // than swallowed.
      log.warn('note-template:source', 'failed to keep the uploaded file', {
        practiceId,
        bytes: bytes.byteLength,
        err: err instanceof Error ? err.message : String(err),
      });
    }
  }

  const extracted = await extractNoteTextFromUpload(bytes, file.name, file.type);
  return source ? { ...extracted, source } : extracted;
}
