import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

import { SignAndSendModal } from "../sign-and-send-modal";

function renderModal({
  originalTemplateDocxAvailable,
  originalTemplateOnly = false,
  signOnSubmit = true,
}: {
  originalTemplateDocxAvailable: boolean;
  originalTemplateOnly?: boolean;
  signOnSubmit?: boolean;
}) {
  render(
    <SignAndSendModal
      visitId="visit-synthetic-docx-options"
      doctorEmail="clinician@example.test"
      signOnSubmit={signOnSubmit}
      emailEnabled
      originalTemplateDocxAvailable={originalTemplateDocxAvailable}
      originalTemplateOnly={originalTemplateOnly}
      triggerLabel={signOnSubmit ? "Sign & Send" : "Export again"}
      triggerIcon={<span aria-hidden />}
    />,
  );
  fireEvent.click(
    screen.getByRole("button", {
      name: signOnSubmit ? "Sign & Send" : "Export again",
    }),
  );
}

describe("SignAndSendModal DOCX compatibility", () => {
  it("keeps the established Download DOCX destination for non-Twin visits", () => {
    renderModal({ originalTemplateDocxAvailable: false });

    expect(
      screen.getByRole("button", { name: /download docx/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /original template docx/i }),
    ).not.toBeInTheDocument();
  });

  it("makes the verified original primary without removing generic DOCX", () => {
    renderModal({ originalTemplateDocxAvailable: true });

    expect(
      screen.getByRole("button", { name: /original template docx.*primary/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /download docx/i }),
    ).toBeInTheDocument();
  });

  it("exposes only the verified Original Template DOCX for synthetic signing", () => {
    renderModal({
      originalTemplateDocxAvailable: true,
      originalTemplateOnly: true,
    });

    expect(
      screen.getByRole("heading", {
        name: "Sign synthetic Original Template DOCX",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /original template docx.*primary/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /original template docx.*primary/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.queryByRole("button", { name: /download pdf/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /download docx/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /copy for epic/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /email to me/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Microsoft Word compatibility remains PENDING after signing.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps the synthetic signed-visit export limited to the original DOCX", () => {
    renderModal({
      originalTemplateDocxAvailable: true,
      originalTemplateOnly: true,
      signOnSubmit: false,
    });

    expect(
      screen.getByRole("heading", { name: "Download signed synthetic DOCX" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(4);
    expect(
      screen.getByRole("button", { name: /original template docx.*primary/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Microsoft Word compatibility remains PENDING."),
    ).toBeInTheDocument();
  });

  it("blocks synthetic signing while the strict original-DOCX proof is unavailable", () => {
    renderModal({
      originalTemplateDocxAvailable: false,
      originalTemplateOnly: true,
    });

    expect(
      screen.getByText(
        /complete template twin review and strict verification/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /original template docx/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sign & Deliver" }),
    ).toBeDisabled();
  });
});
