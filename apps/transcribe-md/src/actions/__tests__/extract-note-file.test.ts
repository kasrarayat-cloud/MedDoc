// ============================================================================
// extractNoteFileAction — legacy plain-text upload guard rails. Proves that
// Office/PDF packages fail closed before bytes are read, while a small blank
// text outline still reaches the deterministic text decoder.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ requireSession: vi.fn() }));
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));

import { extractNoteFileAction } from "../extract-note-file";

function fd(file?: File): FormData {
  const f = new FormData();
  if (file) f.append("file", file);
  return f;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: "u1", practiceId: "p1" },
  });
});

describe("extractNoteFileAction — guards", () => {
  it("rejects an oversized file (>5MB) with a clear message", async () => {
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "big.txt", {
      type: "text/plain",
    });
    const r = await extractNoteFileAction(fd(big));
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.fallbackToPaste).toBe(true);
      expect(r.error).toMatch(/larger than 5 ?MB|too large|5 ?MB/i);
    }
  });

  it("falls back when no file is present", async () => {
    const r = await extractNoteFileAction(fd());
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.fallbackToPaste).toBe(true);
  });

  it("extracts a valid blank text outline", async () => {
    const file = new File(
      ["SUBJECTIVE:\n[blank]\nPLAN:\n[blank]"],
      "outline.txt",
      {
        type: "text/plain",
      },
    );
    const r = await extractNoteFileAction(fd(file));
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.kind).toBe("txt");
      expect(r.text).toContain("SUBJECTIVE");
    }
  });

  it.each([
    ["PDF", "note.pdf", "application/pdf"],
    [
      "DOCX",
      "template.docx",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
    ["extension/MIME mismatch", "outline.txt", "application/pdf"],
    ["unlisted Markdown extension", "outline.markdown", "text/markdown"],
  ])("rejects %s before reading bytes", async (_label, name, type) => {
    const file = new File(["not inspected"], name, { type });
    const arrayBuffer = vi.spyOn(file, "arrayBuffer");

    const r = await extractNoteFileAction(fd(file));

    expect(r).toMatchObject({ ok: false, fallbackToPaste: true });
    if (!r.ok) expect(r.error).toMatch(/\.txt|\.md|Template Twin/i);
    expect(arrayBuffer).not.toHaveBeenCalled();
  });
});
