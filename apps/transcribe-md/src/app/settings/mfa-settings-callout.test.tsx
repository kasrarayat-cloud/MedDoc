import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MfaSettingsCallout } from "./mfa-settings-callout";

describe("settings MFA discoverability", () => {
  it("links an unenrolled physician to the active enrollment workflow", () => {
    render(<MfaSettingsCallout enabled={false} />);

    const link = screen.getByRole("link", { name: "Set up MFA" });
    expect(link).toHaveAttribute("href", "/settings/security/mfa");
    expect(link).toHaveStyle({ height: "36px" });
    expect(screen.getByText("Off")).toBeInTheDocument();
    expect(
      screen.queryByText(/lands in the next batch/i),
    ).not.toBeInTheDocument();
  });

  it("links an enrolled physician to recovery-code management", () => {
    render(<MfaSettingsCallout enabled />);

    expect(screen.getByRole("link", { name: "Manage MFA" })).toHaveAttribute(
      "href",
      "/settings/security/mfa",
    );
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText(/recovery-code readiness/i)).toBeInTheDocument();
  });
});
