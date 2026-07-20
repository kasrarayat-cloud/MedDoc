"use server";

// ============================================================================
// Note-format customization — Phase 2b: upload → note text (server action)
// ----------------------------------------------------------------------------
// Accepts ONE plain-text blank outline from the entry screen and returns its
// text to the client (which then calls parseNoteTemplateAction). Office/PDF
// packages fail closed before their bytes are read; those formats require the
// quarantined Template Twin intake. The accepted text bytes are held in memory
// only — NOTHING is written to disk, DB, or object storage.
// ============================================================================

import { requireSession } from "@/lib/auth";
import {
  extractNoteTextFromUpload,
  type ExtractResult,
} from "@/lib/note-template-parse/extract-note-text";

/** Hard ceiling on upload size — a single note is tiny; anything large is
 *  almost certainly the wrong file and risks runaway memory/token cost. */
const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MB
const LEGACY_TEXT_MIME_TYPES = new Set([
  "",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
]);

function isLegacyPlainTextOutline(file: File): boolean {
  const name = file.name.toLowerCase();
  const hasSafeExtension = name.endsWith(".txt") || name.endsWith(".md");
  return (
    hasSafeExtension && LEGACY_TEXT_MIME_TYPES.has(file.type.toLowerCase())
  );
}

export async function extractNoteFileAction(
  formData: FormData,
): Promise<ExtractResult> {
  await requireSession(); // authenticated doctors only; result isn't doctor-scoped data
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    return {
      ok: false,
      fallbackToPaste: true,
      error: "No file received. Paste the note instead.",
    };
  }
  // This check intentionally precedes size checks and arrayBuffer(): DOCX/PDF
  // bytes must never enter a convenience extractor without quarantine,
  // malware attestation, and package-security admission.
  if (!isLegacyPlainTextOutline(file)) {
    return {
      ok: false,
      fallbackToPaste: true,
      error:
        "Only blank .txt or .md outlines are accepted here. Use the quarantined Template Twin workflow for an original blank DOCX; PDF and completed documents are not accepted.",
    };
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      fallbackToPaste: true,
      error:
        "That text outline is larger than 5 MB. Paste one short blank outline instead.",
    };
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  return extractNoteTextFromUpload(bytes, file.name, file.type);
}
