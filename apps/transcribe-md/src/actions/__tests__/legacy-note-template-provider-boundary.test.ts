import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requireSession: vi.fn(),
  findActor: vi.fn(),
  complete: vi.fn(),
  completeText: vi.fn(),
  getCachedPreview: vi.fn(),
  setCachedPreview: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("@meddoc/db", () => ({
  default: { user: { findFirst: mocks.findActor } },
}));
vi.mock("@meddoc/ai", async () => {
  const actual =
    await vi.importActual<typeof import("@meddoc/ai")>("@meddoc/ai");
  return {
    ...actual,
    modelClient: {
      complete: mocks.complete,
      completeText: mocks.completeText,
    },
  };
});
vi.mock("@/lib/sample-preview-cache", () => ({
  previewCacheKey: vi.fn(() => "notefmt:preview:test-safe-projection"),
  getCachedPreview: mocks.getCachedPreview,
  setCachedPreview: mocks.setCachedPreview,
}));

import { parseNoteTemplateAction } from "../parse-note-template";
import { previewNoteTemplateAction } from "../preview-note-template";

const CURRENT_ACTOR = {
  id: "doctor-current",
  practiceId: "practice-current",
} as const;

const BLANK_OUTLINE = [
  "SUBJECTIVE:",
  "[blank]",
  "OBJECTIVE:",
  "[blank]",
  "ASSESSMENT:",
  "[blank]",
  "PLAN:",
  "[blank]",
].join("\n");

function parsedTemplateOutput() {
  return {
    name: "Synthetic blank outline",
    encounterType: null,
    styleProfile: {
      tense: null,
      tone: "concise",
      abbreviations: null,
    },
    flags: [],
    sections: [
      {
        key: "subjective",
        label: "Subjective",
        order: 1,
        formatHint: "prose" as const,
        styleInstructions: "Write as prose.",
        defaultText: null,
      },
      {
        key: "assessment",
        label: "Assessment",
        order: 2,
        formatHint: "prose" as const,
        styleInstructions: "Write as prose.",
        defaultText: null,
      },
    ],
  };
}

function blankPreviewInput(overrides: Record<string, unknown> = {}) {
  return {
    name: "Sports medicine outline",
    encounterType: null,
    sections: [
      {
        key: "custom_sports",
        label: "Custom Sports Heading",
        order: 1,
        formatHint: "prose",
        styleInstructions: "Use a concise paragraph.",
        defaultText: null,
        structure: null,
      },
    ],
    styleProfile: {
      tense: null,
      tone: "concise",
      abbreviations: null,
      contextDefaults: null,
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: {
      id: CURRENT_ACTOR.id,
      practiceId: "practice-stale-jwt",
      role: "DOCTOR",
      email: "synthetic-doctor@example.test",
      fullName: "Synthetic Doctor",
    },
  });
  mocks.findActor.mockResolvedValue(CURRENT_ACTOR);
  mocks.getCachedPreview.mockResolvedValue(null);
  mocks.setCachedPreview.mockResolvedValue(undefined);
});

describe("legacy blank-outline parse provider boundary", () => {
  it.each([
    [
      "structured PHI",
      "SUBJECTIVE:\nPatient name: Synthetic Person\nDOB: 01/02/2026\nPLAN:\n[blank]",
    ],
    [
      "a completed-like note",
      "SUBJECTIVE:\nPatient reports worsening left knee pain.\nPLAN:\nContinue medication.",
    ],
  ])("keeps %s local and never calls a provider", async (_label, input) => {
    const result = await parseNoteTemplateAction(input);

    expect(result.rejected).toBe(true);
    expect(mocks.complete).not.toHaveBeenCalled();
    expect(mocks.completeText).not.toHaveBeenCalled();
  });

  it("does not call a provider when current actor authority is revoked", async () => {
    mocks.findActor.mockResolvedValueOnce(null);

    const result = await parseNoteTemplateAction(BLANK_OUTLINE);

    expect(result).toMatchObject({ rejected: true, template: null });
    expect(mocks.complete).not.toHaveBeenCalled();
    expect(mocks.findActor).toHaveBeenCalledWith({
      where: {
        id: CURRENT_ACTOR.id,
        role: "DOCTOR",
        isActive: true,
        deactivatedAt: null,
        suspendedAt: null,
        softDeletedAt: null,
        products: { has: "TRANSCRIBE_MD" },
        practice: { is: { isActive: true } },
      },
      select: { id: true, practiceId: true },
    });
  });

  it("discards the parse response when authority is revoked during the call", async () => {
    mocks.findActor
      .mockResolvedValueOnce(CURRENT_ACTOR) // action admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // immediately before provider
      .mockResolvedValueOnce(null); // immediately after provider
    mocks.complete.mockResolvedValueOnce(parsedTemplateOutput());

    const result = await parseNoteTemplateAction(BLANK_OUTLINE);

    expect(result).toMatchObject({ rejected: true, template: null });
    expect(mocks.complete).toHaveBeenCalledTimes(1);
    expect(mocks.complete.mock.calls[0]?.[0]).toMatchObject({
      practiceId: CURRENT_ACTOR.practiceId,
      userId: CURRENT_ACTOR.id,
      purpose: "tm_template_parse",
    });
  });

  it("rechecks authority around every parse schema attempt and stops a retry after revocation", async () => {
    const providerAttempts = vi.fn();
    mocks.findActor
      .mockResolvedValueOnce(CURRENT_ACTOR) // action admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // parse boundary admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // attempt 1 pre
      .mockResolvedValueOnce(CURRENT_ACTOR) // attempt 1 post
      .mockResolvedValueOnce(null); // retry pre: revoked
    mocks.complete.mockImplementationOnce(async (args) => {
      await args.beforeProviderAttempt?.();
      providerAttempts();
      await args.afterProviderAttempt?.();
      await args.beforeProviderAttempt?.();
      providerAttempts();
      return parsedTemplateOutput();
    });

    const result = await parseNoteTemplateAction(BLANK_OUTLINE);

    expect(result).toMatchObject({ rejected: true, template: null });
    expect(providerAttempts).toHaveBeenCalledTimes(1);
    expect(mocks.complete).toHaveBeenCalledTimes(1);
  });

  it("rechecks authority around every PHI-scan schema attempt", async () => {
    const scanProviderAttempts = vi.fn();
    mocks.findActor
      .mockResolvedValueOnce(CURRENT_ACTOR) // action admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // parse boundary admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // parse attempt pre
      .mockResolvedValueOnce(CURRENT_ACTOR) // parse attempt post
      .mockResolvedValueOnce(CURRENT_ACTOR) // parse final fence
      .mockResolvedValueOnce(CURRENT_ACTOR) // scan boundary admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // scan attempt 1 pre
      .mockResolvedValueOnce(CURRENT_ACTOR) // scan attempt 1 post
      .mockResolvedValueOnce(null); // scan retry pre: revoked
    mocks.complete
      .mockImplementationOnce(async (args) => {
        await args.beforeProviderAttempt?.();
        await args.afterProviderAttempt?.();
        return parsedTemplateOutput();
      })
      .mockImplementationOnce(async (args) => {
        await args.beforeProviderAttempt?.();
        scanProviderAttempts();
        await args.afterProviderAttempt?.();
        await args.beforeProviderAttempt?.();
        scanProviderAttempts();
        return { phiFields: [], anyUncertain: false };
      });

    const result = await parseNoteTemplateAction(BLANK_OUTLINE);

    expect(result).toMatchObject({ rejected: true, template: null });
    expect(scanProviderAttempts).toHaveBeenCalledTimes(1);
    expect(mocks.complete).toHaveBeenCalledTimes(2);
  });
});

describe("legacy synthetic preview provider boundary", () => {
  it.each([
    ["structured PHI", blankPreviewInput({ name: "Encounter 2026-01-02" })],
    [
      "an unstructured patient name",
      blankPreviewInput({ name: "Patient Synthetic Person" }),
    ],
    [
      "a populated clinical measurement",
      blankPreviewInput({ name: "Blood pressure 138/88" }),
    ],
    [
      "completed-like default text",
      blankPreviewInput({
        sections: [
          {
            key: "subjective",
            label: "Subjective",
            order: 1,
            formatHint: "prose",
            styleInstructions: null,
            defaultText: "Patient reports worsening pain.",
            structure: null,
          },
        ],
      }),
    ],
  ])("never calls a provider for %s", async (_label, input) => {
    const result = await previewNoteTemplateAction(input);

    expect(result).toMatchObject({ ok: false, privacyRejected: true });
    expect(mocks.completeText).not.toHaveBeenCalled();
  });

  it("does not call a provider when current actor authority is revoked", async () => {
    mocks.findActor.mockResolvedValueOnce(null);

    const result = await previewNoteTemplateAction(blankPreviewInput());

    expect(result.ok).toBe(false);
    expect(mocks.completeText).not.toHaveBeenCalled();
  });

  it("discards and does not cache a response after mid-call revocation", async () => {
    mocks.findActor
      .mockResolvedValueOnce(CURRENT_ACTOR) // action admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // immediately before provider
      .mockResolvedValueOnce(null); // immediately after provider
    mocks.completeText.mockResolvedValueOnce({
      text: "## QMD_SECTION_001\nSynthetic preview output.",
    });

    const result = await previewNoteTemplateAction(blankPreviewInput());

    expect(result.ok).toBe(false);
    expect(mocks.completeText).toHaveBeenCalledTimes(1);
    expect(mocks.setCachedPreview).not.toHaveBeenCalled();
  });

  it("runs a pinned post-attempt fence before accepting preview output", async () => {
    mocks.findActor
      .mockResolvedValueOnce(CURRENT_ACTOR) // action admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // preview boundary admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // provider attempt pre
      .mockResolvedValueOnce(null); // provider attempt post: revoked
    mocks.completeText.mockImplementationOnce(async (args) => {
      await args.beforeProviderAttempt?.();
      const output = {
        text: "## QMD_SECTION_001\nSynthetic preview output.",
      };
      await args.afterProviderAttempt?.();
      return output;
    });

    const result = await previewNoteTemplateAction(blankPreviewInput());

    expect(result.ok).toBe(false);
    expect(mocks.setCachedPreview).not.toHaveBeenCalled();
  });

  it("does not return a cached sample after current authority is lost", async () => {
    mocks.findActor
      .mockResolvedValueOnce(CURRENT_ACTOR)
      .mockResolvedValueOnce(null);
    mocks.getCachedPreview.mockResolvedValueOnce(
      "## QMD_SECTION_001\nCached synthetic preview.",
    );

    const result = await previewNoteTemplateAction(blankPreviewInput());

    expect(result.ok).toBe(false);
    expect(mocks.completeText).not.toHaveBeenCalled();
  });

  it("reasserts authority once more before returning a live sample", async () => {
    mocks.findActor
      .mockResolvedValueOnce(CURRENT_ACTOR) // action admission
      .mockResolvedValueOnce(CURRENT_ACTOR) // immediately before provider
      .mockResolvedValueOnce(CURRENT_ACTOR) // immediately after provider
      .mockResolvedValueOnce(null); // final delivery fence
    mocks.completeText.mockResolvedValueOnce({
      text: "## QMD_SECTION_001\nSynthetic preview output.",
    });

    const result = await previewNoteTemplateAction(blankPreviewInput());

    expect(result.ok).toBe(false);
    expect(mocks.setCachedPreview).not.toHaveBeenCalled();
  });

  it("egresses only structural tokens, then restores labels locally after the fence", async () => {
    mocks.completeText.mockResolvedValueOnce({
      text: "## QMD_SECTION_001\nSynthetic preview output.",
    });

    const result = await previewNoteTemplateAction(blankPreviewInput());

    expect(result).toEqual({
      ok: true,
      markdown: "## Custom Sports Heading\nSynthetic preview output.",
      cached: false,
    });
    const providerRequest = mocks.completeText.mock.calls[0]?.[0];
    expect(providerRequest).toMatchObject({
      practiceId: CURRENT_ACTOR.practiceId,
      userId: CURRENT_ACTOR.id,
    });
    expect(providerRequest.beforeProviderAttempt).toEqual(expect.any(Function));
    expect(providerRequest.afterProviderAttempt).toEqual(expect.any(Function));
    expect(JSON.stringify(providerRequest)).not.toContain(
      "Custom Sports Heading",
    );
    expect(mocks.setCachedPreview).toHaveBeenCalledWith(
      "notefmt:preview:test-safe-projection",
      "## QMD_SECTION_001\nSynthetic preview output.",
    );
  });
});
