import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(),
  refresh: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mocks.refresh }),
}));
vi.mock("sonner", () => ({
  toast: { success: mocks.toastSuccess },
}));

import { MfaManagementPanel } from "./mfa-management-panel";

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("fetch", mocks.fetch);
});

describe("MFA recovery-code management", () => {
  it("fails closed to urgent replacement when no v2 verifier is confirmed", () => {
    render(
      <MfaManagementPanel
        isPlatformAdmin
        usableRecoveryCodeCount={0}
        verifiedAt="2026-07-20T08:00:00.000Z"
      />,
    );

    expect(
      screen.getByRole("alert", {
        name: /no usable recovery codes—generate replacements now/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Generate new recovery codes" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/use one of your saved recovery codes/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Disable MFA" }),
    ).not.toBeInTheDocument();
  });

  it("rotates for an enrolled platform administrator with password and current TOTP", async () => {
    mocks.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        ok: true,
        recoveryCodes: [
          "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345",
          "BCDE-FGHJ-KLMN-PQRS-TUVW-XYZ2-3456",
        ],
      }),
    });
    render(
      <MfaManagementPanel
        isPlatformAdmin
        usableRecoveryCodeCount={null}
        verifiedAt="2026-07-20T08:00:00.000Z"
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Generate new recovery codes" }),
    );
    const dialog = screen.getByRole("dialog", {
      name: "Generate new recovery codes",
    });
    expect(dialog).toHaveStyle({ padding: "16px", boxSizing: "border-box" });
    const dialogSurface = dialog.firstElementChild as HTMLElement;
    expect(dialogSurface.style.boxSizing).toBe("border-box");
    expect(dialogSurface.style.overflowY).toBe("auto");
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "synthetic-password" },
    });
    fireEvent.change(screen.getByLabelText("Current 6-digit code"), {
      target: { value: "123456" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Replace codes" }));

    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledTimes(1));
    expect(mocks.fetch).toHaveBeenCalledWith("/api/mfa/recovery-codes/rotate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        password: "synthetic-password",
        token: "123456",
      }),
    });
    expect(
      await screen.findByText("Save your new recovery codes"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("ABCD-EFGH-JKLM-NPQR-STUV-WXYZ-2345"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("list", { name: "New recovery codes" }),
    ).toHaveStyle({ display: "grid", overflowX: "auto" });
    expect(screen.getByText(/2 usable recovery codes/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/no usable recovery codes—generate replacements now/i),
    ).not.toBeInTheDocument();
    expect(mocks.toastSuccess).toHaveBeenCalledWith("Recovery codes replaced");
  });

  it("shows only a count for usable v2 codes and preserves physician disable", () => {
    render(
      <MfaManagementPanel
        isPlatformAdmin={false}
        usableRecoveryCodeCount={3}
        verifiedAt={null}
      />,
    );

    expect(screen.getByText(/3 usable recovery codes/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Disable MFA" }),
    ).toBeInTheDocument();
  });

  it("does not offer a guaranteed-fail recovery path when no v2 code is usable", () => {
    render(
      <MfaManagementPanel
        isPlatformAdmin={false}
        usableRecoveryCodeCount={0}
        verifiedAt={null}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Disable MFA" }));
    expect(screen.getByLabelText("6-digit code")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Use a recovery code" }),
    ).not.toBeInTheDocument();
  });
});
