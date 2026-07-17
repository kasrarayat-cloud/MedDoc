import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/lib/auth", () => ({
  requireSession: vi.fn(),
  requireDoctorSession: vi.fn(),
}));

vi.mock("@/actions/parse-note-template", () => ({
  parseNoteTemplateAction: vi.fn(),
}));

vi.mock("@/actions/extract-note-file", () => ({
  extractNoteFileAction: vi.fn(),
}));

vi.mock("@/actions/note-template-lifecycle", () => ({
  activateNoteTemplateAction: vi.fn(),
  duplicateNoteTemplateAction: vi.fn(),
  deleteNoteTemplateAction: vi.fn(),
  getNoteTemplateForEditAction: vi.fn(),
}));

vi.mock("@/actions/template-twin-management", () => ({
  activateTemplateTwinVersionAction: vi.fn(),
  createTemplateTwinVersionAction: vi.fn(),
  deactivateTemplateTwinVersionAction: vi.fn(),
  inspectTemplateTwinLineageAction: vi.fn(),
  retireTemplateTwinVersionAction: vi.fn(),
  rollbackTemplateTwinVersionAction: vi.fn(),
}));

vi.mock("./template-review-editor", () => ({
  TemplateReviewEditor: () => null,
}));

import { NoteFormatManager } from "./note-format-manager";

function renderManager(
  state: "enabled" | "unavailable" | "hidden" = "enabled",
) {
  render(
    <NoteFormatManager
      templates={[]}
      uploadCaps={{ pdf: true, docx: true }}
      templateTwinSyntheticQaState={state}
    />,
  );
}

describe("Template Twin synthetic upload dialog", () => {
  it("preserves the existing generic Template Twin upload when staging is hidden", async () => {
    renderManager("hidden");

    expect(
      screen.queryByRole("button", { name: "Upload synthetic DOCX" }),
    ).not.toBeInTheDocument();
    const genericUpload = screen.getByRole("button", {
      name: "Upload original DOCX",
    });
    fireEvent.click(genericUpload);
    expect(
      await screen.findByRole("dialog", {
        name: "Add a Word template for certification",
      }),
    ).toBeInTheDocument();
  });

  it("traps modal focus and restores it to the staging trigger on Escape", async () => {
    renderManager();
    const trigger = screen.getByRole("button", {
      name: "Upload synthetic DOCX",
    });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = await screen.findByRole("dialog", {
      name: "Add the synthetic Word fixture for certification",
    });
    const firstField = screen.getByLabelText("Template name");
    await waitFor(() => expect(firstField).toHaveFocus());

    // Radix's modal FocusScope prevents focus from escaping to the inert
    // settings surface even when an outside control is focused directly.
    trigger.focus();
    await waitFor(() =>
      expect(dialog.contains(document.activeElement)).toBe(true),
    );

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("closes with the keyboard-focusable Cancel control and returns focus", async () => {
    renderManager();
    const trigger = screen.getByRole("button", {
      name: "Upload synthetic DOCX",
    });
    trigger.focus();
    fireEvent.click(trigger);
    const cancel = await screen.findByRole("button", { name: "Cancel" });
    cancel.focus();
    fireEvent.click(cancel);

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(trigger).toHaveFocus());
  });
});
