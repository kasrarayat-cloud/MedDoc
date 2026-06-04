// ============================================================================
// extractNoteFileAction — upload guard rails. requireSession mocked; extraction
// is real (unpdf). Proves: oversized → clear rejection; no file → fallback; a
// valid PDF round-trips to text. The raw file is never persisted (the action
// holds the buffer in memory only — no DB/MinIO write exists in the path).
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const mocks = vi.hoisted(() => ({ requireSession: vi.fn() }));
vi.mock('@/lib/auth', () => ({ requireSession: mocks.requireSession }));

import { extractNoteFileAction } from '../extract-note-file';

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), '../../lib/note-template-parse/__tests__/__fixtures__');

function fd(file?: File): FormData {
  const f = new FormData();
  if (file) f.append('file', file);
  return f;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({ user: { id: 'u1', practiceId: 'p1' } });
});

describe('extractNoteFileAction — guards', () => {
  it('rejects an oversized file (>5MB) with a clear message', async () => {
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'big.pdf', { type: 'application/pdf' });
    const r = await extractNoteFileAction(fd(big));
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.fallbackToPaste).toBe(true);
      expect(r.error).toMatch(/larger than 5 ?MB|too large|5 ?MB/i);
    }
  });

  it('falls back when no file is present', async () => {
    const r = await extractNoteFileAction(fd());
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.fallbackToPaste).toBe(true);
  });

  it('extracts a valid PDF upload to text', async () => {
    const bytes = readFileSync(path.join(FIX, 'dra-multipage.pdf'));
    const file = new File([bytes], 'note.pdf', { type: 'application/pdf' });
    const r = await extractNoteFileAction(fd(file));
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.text).toContain('CHIEF COMPLAINT');
  });
});
