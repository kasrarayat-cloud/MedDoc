import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isEmailDeliveryEnabled,
  isEmailVerificationRequired,
} from "./email-enabled";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("email delivery and authentication policy", () => {
  it("keeps delivery disabled unless both provider requirements are present", () => {
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("RESEND_FROM_VERIFIED", "true");
    expect(isEmailDeliveryEnabled()).toBe(false);

    vi.stubEnv("RESEND_API_KEY", "synthetic-provider-key");
    vi.stubEnv("RESEND_FROM_VERIFIED", "false");
    expect(isEmailDeliveryEnabled()).toBe(false);

    vi.stubEnv("RESEND_FROM_VERIFIED", "true");
    expect(isEmailDeliveryEnabled()).toBe(true);
  });

  it("requires verification in production when the delivery provider is absent", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("RESEND_FROM_VERIFIED", "false");
    vi.stubEnv("EMAIL_VERIFICATION_REQUIRED", "false");

    expect(isEmailDeliveryEnabled()).toBe(false);
    expect(isEmailVerificationRequired()).toBe(true);
  });

  it("retains provider-free local tests unless strict policy is explicitly enabled", () => {
    vi.stubEnv("NODE_ENV", "test");
    vi.stubEnv("RESEND_API_KEY", "");
    vi.stubEnv("RESEND_FROM_VERIFIED", "false");
    vi.stubEnv("EMAIL_VERIFICATION_REQUIRED", "false");
    expect(isEmailVerificationRequired()).toBe(false);

    vi.stubEnv("EMAIL_VERIFICATION_REQUIRED", "true");
    expect(isEmailVerificationRequired()).toBe(true);
  });
});
