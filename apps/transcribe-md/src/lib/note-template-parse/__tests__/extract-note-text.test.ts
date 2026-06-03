// ============================================================================
// File→text extraction (Phase 2b). Pure normalizer + format classification.
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  normalizeExtractedText,
  classifyUpload,
} from '../extract-note-text';

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
  it('routes by extension and mime', () => {
    expect(classifyUpload('note.txt', '')).toBe('txt');
    expect(classifyUpload('x', 'text/plain')).toBe('txt');
    expect(classifyUpload('note.docx', '')).toBe('docx');
    expect(classifyUpload('x', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')).toBe('docx');
    expect(classifyUpload('note.pdf', '')).toBe('pdf'); // routes to paste fallback
    expect(classifyUpload('scan.jpg', 'image/jpeg')).toBe('unsupported');
  });
});
