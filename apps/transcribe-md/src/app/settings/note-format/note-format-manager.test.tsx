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
import type { ClientTemplateListItem } from "@/lib/note-template-persist/types";

const SYNTHETIC_TEMPLATE: ClientTemplateListItem = {
  id: "template_synthetic_existing",
  name: "Synthetic existing format",
  encounterType: null,
  encounterLabel: "All my visits",
  status: "active",
  version: 1,
  sectionCount: 4,
  defaultCount: 0,
  templateKind: "structured",
  twinCertificationStatus: null,
  twinFieldCount: 0,
  twinBlockingUnsupportedCount: 0,
  updatedAtIso: "2026-07-17T00:00:00.000Z",
};

function renderManager(
  state: "enabled" | "unavailable" | "hidden" = "enabled",
  requested = state === "enabled",
  templates: ClientTemplateListItem[] = [],
) {
  render(
    <NoteFormatManager
      templates={templates}
      uploadCaps={{ pdf: true, docx: true }}
      templateTwinSyntheticQaState={state}
      templateTwinStagingQaRequested={requested}
    />,
  );
}

describe("Template Twin synthetic upload dialog", () => {
  it("preserves the existing generic Template Twin upload when staging is hidden", async () => {
    renderManager("hidden", false);

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

  it("removes the generic DOCX upload from the synthetic-only entry surface", () => {
    renderManager("enabled", true);

    expect(
      screen.getByRole("button", { name: "Upload synthetic DOCX" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Upload original DOCX" }),
    ).not.toBeInTheDocument();
  });

  it("removes the generic DOCX upload from the synthetic-only template list", () => {
    renderManager("enabled", true, [SYNTHETIC_TEMPLATE]);

    expect(
      screen.getByRole("button", { name: "Template Twin — Synthetic QA" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Preserve Word template" }),
    ).not.toBeInTheDocument();
  });

  it("fails closed when staging is requested but the staging gate is unavailable", () => {
    renderManager("unavailable", true);

    expect(
      screen.queryByRole("button", { name: "Upload synthetic DOCX" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Upload original DOCX" }),
    ).not.toBeInTheDocument();
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
