import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  preview: vi.fn(),
  save: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/actions/preview-note-template", () => ({
  previewNoteTemplateAction: mocks.preview,
}));
vi.mock("@/actions/note-template-lifecycle", () => ({
  saveNoteTemplateAction: mocks.save,
}));
vi.mock("sonner", () => ({
  toast: {
    error: mocks.toastError,
    success: vi.fn(),
    message: vi.fn(),
  },
}));

import { TemplateReviewEditor } from "./template-review-editor";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.save.mockResolvedValue({ ok: false, error: "blocked" });
});

describe("TemplateReviewEditor privacy feedback", () => {
  it("surfaces a preview privacy denial without non-blocking save copy", async () => {
    mocks.preview.mockResolvedValue({
      ok: false,
      error:
        "This format contains populated or patient-like text. Remove patient details before saving or activating it.",
      privacyRejected: true,
    });

    render(
      <TemplateReviewEditor
        initial={{
          name: "Blank format",
          encounterType: null,
          sections: [
            {
              key: "subjective",
              label: "Subjective",
              order: 1,
              formatHint: "prose",
              styleInstructions: null,
              defaultText: null,
              defaultTextMode: "omit_unless_supported",
              structure: null,
            },
          ],
          styleProfile: {
            tense: null,
            tone: "concise",
            abbreviations: null,
            contextDefaults: null,
          },
        }}
        onCancel={vi.fn()}
        onSaved={vi.fn()}
      />,
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/privacy check blocked this format/i);
    expect(alert).toHaveTextContent(/before saving or activating/i);
    expect(
      screen.queryByText(/does not affect saving or activating/i),
    ).not.toBeInTheDocument();
  });
});
