// ============================================================================
// GATE — THE UPLOADED FILE IS KEPT, AND IT IS KEPT *BEFORE* EXTRACTION.
// RC-2, ruling #106(b).
// ----------------------------------------------------------------------------
// ⚠️ THE ORDERING IS THE ENTIRE RULING, AND IT IS THE ONLY PART A TEST CAN
// ACTUALLY PIN. "The bytes are persisted" is satisfied by persisting anywhere in
// the function. What the ruling asks for is that they survive the step that
// FAILS — a corrupt file, an unsupported shape, a parser throw — because that is
// precisely when the original matters and precisely when a
// persist-after-extract would have kept nothing.
//
// So the load-bearing test makes extraction THROW and asserts the file is
// stored anyway. A version of this code that persisted afterwards passes every
// other assertion in this file and fails that one.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  requireSession: vi.fn(),
  extract: vi.fn(),
  storeUploadArtifact: vi.fn(),
  hasProvider: vi.fn(() => true),
  logWarn: vi.fn(),
  logError: vi.fn(),
}));

vi.mock('@/lib/auth', () => ({ requireSession: mocks.requireSession }));
vi.mock('@/lib/note-template-parse/extract-note-text', () => ({
  extractNoteTextFromUpload: mocks.extract,
}));
vi.mock('@/lib/template-twin/storage', () => ({
  createTemplateTwinArtifactStore: () => ({ storeUploadArtifact: mocks.storeUploadArtifact }),
  hasTemplateTwinStorageProvider: mocks.hasProvider,
}));
vi.mock('@/lib/log', () => ({
  log: { warn: mocks.logWarn, error: mocks.logError, info: vi.fn() },
}));

import { extractNoteFileAction } from '../extract-note-file';

const DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const SHA = 'a'.repeat(64);
const KEY = `practices/prac_1/template-twin/uploads/up_1/up_1/${SHA}.docx`;

function upload(name = 'form.docx', type = DOCX, bytes = new Uint8Array([1, 2, 3])): FormData {
  const fd = new FormData();
  fd.append('file', new File([bytes], name, { type }));
  return fd;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({ user: { id: 'u1', practiceId: 'prac_1' } });
  mocks.extract.mockResolvedValue({ ok: true, text: '## Technique\nx', kind: 'docx' });
  mocks.storeUploadArtifact.mockResolvedValue({ objectKey: KEY, sha256: SHA });
  mocks.hasProvider.mockReturnValue(true);
});

describe('⚠️ THE ORDERING — persist, THEN extract', () => {
  it('⚠️ stores the file even when EXTRACTION THROWS', async () => {
    mocks.extract.mockRejectedValue(new Error('corrupt docx'));
    await expect(extractNoteFileAction(upload())).rejects.toThrow('corrupt docx');
    // The claim: the bytes survived the step that failed.
    expect(mocks.storeUploadArtifact).toHaveBeenCalledTimes(1);
  });

  it('stores the file even when extraction REJECTS the upload', async () => {
    mocks.extract.mockResolvedValue({ ok: false, fallbackToPaste: true, error: 'unsupported' });
    const out = await extractNoteFileAction(upload());
    expect(mocks.storeUploadArtifact).toHaveBeenCalledTimes(1);
    expect(out.ok).toBe(false);
  });

  it('the store is called BEFORE the extractor, by invocation order', async () => {
    const order: string[] = [];
    mocks.storeUploadArtifact.mockImplementation(async () => {
      order.push('store');
      return { objectKey: KEY, sha256: SHA };
    });
    mocks.extract.mockImplementation(async () => {
      order.push('extract');
      return { ok: true, text: 'x', kind: 'docx' };
    });
    await extractNoteFileAction(upload());
    expect(order).toEqual(['store', 'extract']);
  });
});

describe('the happy path returns a ref the caller can carry', () => {
  it('returns objectKey + sha alongside the extracted text', async () => {
    const out = await extractNoteFileAction(upload());
    expect(out.source).toEqual({ objectKey: KEY, sha256: SHA });
    expect(out.ok).toBe(true);
  });

  it('passes the practice from the SESSION, never from the request', async () => {
    await extractNoteFileAction(upload());
    expect(mocks.storeUploadArtifact.mock.calls[0]![0].practiceId).toBe('prac_1');
  });

  it('mints a fresh uploadId per attempt', async () => {
    await extractNoteFileAction(upload());
    await extractNoteFileAction(upload());
    const a = mocks.storeUploadArtifact.mock.calls[0]![0].uploadId;
    const b = mocks.storeUploadArtifact.mock.calls[1]![0].uploadId;
    expect(a).not.toBe(b);
  });
});

describe('⚠️ KEEPING THE FILE NEVER COSTS THE DOCTOR THE UPLOAD', () => {
  it('a storage failure is logged, absent from the result, and does NOT throw', async () => {
    mocks.storeUploadArtifact.mockRejectedValue(new Error('minio down'));
    const out = await extractNoteFileAction(upload());
    expect(out.ok).toBe(true);
    expect(out.source).toBeUndefined();
    expect(mocks.logWarn).toHaveBeenCalledTimes(1);
  });

  it('no storage provider configured → extraction still succeeds, no source', async () => {
    mocks.hasProvider.mockReturnValue(false);
    const out = await extractNoteFileAction(upload());
    expect(out.ok).toBe(true);
    expect(out.source).toBeUndefined();
    expect(mocks.storeUploadArtifact).not.toHaveBeenCalled();
  });
});

describe('what is NOT kept, and why', () => {
  it.each([
    ['note.txt', 'text/plain'],
    ['note.md', 'text/markdown'],
    ['scan.pdf', 'application/pdf'],
  ])('%s is not stored — it is its own text, or has its own path', async (name, type) => {
    await extractNoteFileAction(upload(name, type));
    expect(mocks.storeUploadArtifact).not.toHaveBeenCalled();
  });

  it('a .docx by EXTENSION is kept even when the browser sends a vague mime', async () => {
    await extractNoteFileAction(upload('form.docx', 'application/octet-stream'));
    expect(mocks.storeUploadArtifact).toHaveBeenCalledTimes(1);
  });
});

describe('⚠️ a session without a practice is LOUD, not silently skipped', () => {
  it('logs at ERROR and keeps nothing, rather than quietly not keeping', async () => {
    mocks.requireSession.mockResolvedValue({ user: { id: 'u1', practiceId: '' } });
    const out = await extractNoteFileAction(upload());
    expect(mocks.storeUploadArtifact).not.toHaveBeenCalled();
    expect(mocks.logError).toHaveBeenCalledTimes(1);
    // The upload still works — the doctor is never punished for our bug.
    expect(out.ok).toBe(true);
  });
});
