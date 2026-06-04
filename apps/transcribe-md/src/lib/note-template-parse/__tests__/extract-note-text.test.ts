// ============================================================================
// File→text extraction (Phase 2b). Pure normalizer + format classification.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  normalizeExtractedText,
  classifyUpload,
  extractNoteTextFromUpload,
} from '../extract-note-text';
import { pdfToText, PdfTooLongError } from '../pdf-to-text';

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), '__fixtures__');
const readFix = (name: string) => new Uint8Array(readFileSync(path.join(FIX, name)));

describe('normalizeExtractedText — unicode punctuation', () => {
  it('folds en/em-dash, NBSP, smart quotes, ellipsis, middot', () => {
    const out = normalizeExtractedText('Follow‑up—pt “stable”, mild… · item');
    expect(out).not.toMatch(/[‑— “”…·]/);
    expect(out).toContain('Follow-up-pt');
    expect(out).toContain('"stable"');
    expect(out).toContain('mild...');
  });
});

describe('normalizeExtractedText — wrapped-line rejoin', () => {
  it('rejoins a mid-clause hard wrap but preserves headings + paragraph breaks', () => {
    const raw = 'The patient was\nseen for follow-up.\n\nEXAM\nGeneral: well.';
    const out = normalizeExtractedText(raw);
    expect(out).toContain('The patient was seen for follow-up.');
    // Heading on its own line is NOT glued to the next (uppercase boundary).
    expect(out).toMatch(/EXAM\nGeneral/);
    // Paragraph break preserved.
    expect(out).toMatch(/follow-up\.\n\nEXAM/);
  });

  it('does not join across a sentence end', () => {
    const out = normalizeExtractedText('done today.\nthe plan is rest');
    // prev char '.' is not a join trigger → stays a separate line
    expect(out).toMatch(/done today\.\nthe plan is rest/);
  });
});

describe('normalizeExtractedText — header/footer de-bleed', () => {
  it('drops page-furniture lines', () => {
    const raw = 'Subjective: cc.\nPage 2 of 5\nObjective: exam.\n3 / 5\nAssessment: ok.';
    const out = normalizeExtractedText(raw);
    expect(out).not.toMatch(/Page 2 of 5/);
    expect(out).not.toMatch(/3 \/ 5/);
    expect(out).toContain('Subjective: cc.');
    expect(out).toContain('Assessment: ok.');
  });

  it('removes a short banner repeating 3+ times (multi-page header bleed)', () => {
    const banner = 'Springfield Clinic — Confidential';
    const raw = [banner, 'Subjective: cc.', banner, 'Objective: exam.', banner, 'Plan: rx.'].join('\n');
    const out = normalizeExtractedText(raw);
    expect(out).not.toContain(banner);
    expect(out).toContain('Subjective: cc.');
    expect(out).toContain('Plan: rx.');
  });

  it('keeps a line that repeats only twice (not furniture)', () => {
    const raw = 'Normal exam.\nfoo bar\nNormal exam.';
    const out = normalizeExtractedText(raw);
    expect(out.match(/Normal exam\./g)?.length).toBe(2);
  });
});

describe('classifyUpload', () => {
  it('routes by extension and mime — pdf/docx/txt/md supported, rest unsupported', () => {
    expect(classifyUpload('note.txt', '')).toBe('txt');
    expect(classifyUpload('x', 'text/plain')).toBe('txt');
    expect(classifyUpload('note.md', '')).toBe('md');
    expect(classifyUpload('note.markdown', '')).toBe('md');
    expect(classifyUpload('x', 'text/markdown')).toBe('md');
    expect(classifyUpload('note.docx', '')).toBe('docx');
    expect(classifyUpload('x', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')).toBe('docx');
    expect(classifyUpload('note.pdf', '')).toBe('pdf'); // now a supported extraction path
    expect(classifyUpload('x', 'application/pdf')).toBe('pdf');
    // not reliably extractable → paste fallback
    expect(classifyUpload('note.rtf', '')).toBe('unsupported');
    expect(classifyUpload('scan.jpg', 'image/jpeg')).toBe('unsupported');
  });
});

// ── PDF extraction (unpdf) ───────────────────────────────────────────────────
describe('extractNoteTextFromUpload — .pdf', () => {
  it('extracts a multi-page clinical PDF into text (headers + body intact)', async () => {
    const r = await extractNoteTextFromUpload(readFix('dra-multipage.pdf'), 'note.pdf', 'application/pdf');
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.kind).toBe('pdf');
      // Both pages' content present — section labels the parser keys on.
      expect(r.text).toContain('CHIEF COMPLAINT');
      expect(r.text).toContain('IMPRESSION & PLAN');
      expect(r.text).toContain('PATIENT INSTRUCTIONS');
      // PHI is PRESENT in the extracted text — it's stripped later, at PARSE
      // time, by the unchanged PHI gate (same path as pasted text).
      expect(r.text).toContain('RFM-0098214');
    }
  });

  it('a text-less (scanned/image-only) PDF → graceful paste fallback, no crash', async () => {
    const r = await extractNoteTextFromUpload(readFix('blank.pdf'), 'scan.pdf', 'application/pdf');
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.fallbackToPaste).toBe(true);
      expect(r.error).toMatch(/scan or image|paste/i);
    }
  });

  it('a malformed / non-PDF byte stream → graceful paste fallback, no crash', async () => {
    const garbage = new TextEncoder().encode('this is not a pdf at all %%%% \x00\x01\x02');
    const r = await extractNoteTextFromUpload(garbage, 'broken.pdf', 'application/pdf');
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.fallbackToPaste).toBe(true);
      expect(r.error).toMatch(/encrypted|damaged|paste/i);
    }
  });

  it('an unsupported type → clear paste fallback message', async () => {
    const r = await extractNoteTextFromUpload(new Uint8Array([1, 2, 3]), 'photo.png', 'image/png');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/PDF, Word|paste/i);
  });
});

// ── .md / page-bound DoS guard ───────────────────────────────────────────────
describe('extractNoteTextFromUpload — .md + guards', () => {
  it('reads a Markdown file as text', async () => {
    const md = new TextEncoder().encode('# Note format\n\n**Subjective:** interval history.\n\n**Plan:** numbered.');
    const r = await extractNoteTextFromUpload(md, 'fmt.md', 'text/markdown');
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.kind).toBe('md');
      expect(r.text).toContain('Subjective');
    }
  });

  it('pdfToText enforces the page bound (PdfTooLongError, code PDF_TOO_LONG)', async () => {
    // The fixture is 2 pages; cap at 1 to trip the bound deterministically.
    await expect(pdfToText(readFix('dra-multipage.pdf'), 1)).rejects.toBeInstanceOf(PdfTooLongError);
    try {
      await pdfToText(readFix('dra-multipage.pdf'), 1);
    } catch (e) {
      expect((e as PdfTooLongError).code).toBe('PDF_TOO_LONG');
      expect((e as PdfTooLongError).pages).toBe(2);
    }
  });
});
