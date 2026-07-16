import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

import { SignAndSendModal } from "../sign-and-send-modal";

function renderModal(originalTemplateDocxAvailable: boolean) {
  render(
    <SignAndSendModal
      visitId="visit-synthetic-docx-options"
      doctorEmail="clinician@example.test"
      signOnSubmit
      emailEnabled={false}
      originalTemplateDocxAvailable={originalTemplateDocxAvailable}
      triggerLabel="Sign & Send"
      triggerIcon={<span aria-hidden />}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Sign & Send" }));
}

describe("SignAndSendModal DOCX compatibility", () => {
  it("keeps the established Download DOCX destination for non-Twin visits", () => {
    renderModal(false);

    expect(
      screen.getByRole("button", { name: /download docx/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /original template docx/i }),
    ).not.toBeInTheDocument();
  });

  it("makes the verified original primary without removing generic DOCX", () => {
    renderModal(true);

    expect(
      screen.getByRole("button", { name: /original template docx.*primary/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /download docx/i }),
    ).toBeInTheDocument();
  });
});
