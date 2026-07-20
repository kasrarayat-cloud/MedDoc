import { describe, expect, it } from "vitest";

import {
  ADMIN_PRODUCTION_ORIGIN,
  PHYSICIAN_PRODUCTION_ORIGIN,
  SYNTHETIC_QA_PHYSICIAN_ORIGIN,
  assertAuthOriginRuntimeConfiguration,
  authOriginConfigurationError,
} from "../auth-origin";
import { ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION } from "../admin-host";

const physician = {
  NODE_ENV: "production",
  QUILLMD_SERVICE_ROLE: "physician-app",
  AUTH_URL: PHYSICIAN_PRODUCTION_ORIGIN,
  NEXTAUTH_URL: PHYSICIAN_PRODUCTION_ORIGIN,
} as const;

const admin = {
  NODE_ENV: "production",
  QUILLMD_SERVICE_ROLE: "template-twin-admin-app",
  AUTH_URL: ADMIN_PRODUCTION_ORIGIN,
  NEXTAUTH_URL: ADMIN_PRODUCTION_ORIGIN,
} as const;

describe("production authentication origin startup gate", () => {
  it("admits only the exact reviewed physician origin", () => {
    expect(
      authOriginConfigurationError(physician, PHYSICIAN_PRODUCTION_ORIGIN),
    ).toBeNull();
  });

  it.each([
    "http://app.quillmd.com",
    "https://app.quillmd.com:443",
    "https://user:pass@app.quillmd.com",
    "https://app.quillmd.com/",
    "https://app.quillmd.com/callback",
    "https://app.quillmd.com?next=admin",
    "https://app.quillmd.com#fragment",
    "https://APP.quillmd.com",
  ])("rejects non-exact physician AUTH_URL %s", (AUTH_URL) => {
    expect(
      authOriginConfigurationError(
        { ...physician, AUTH_URL },
        PHYSICIAN_PRODUCTION_ORIGIN,
      ),
    ).toBe("AUTH_URL_NOT_REVIEWED");
  });

  it("pins both admin processes to the admin origin and public links to the physician origin", () => {
    expect(
      authOriginConfigurationError(admin, PHYSICIAN_PRODUCTION_ORIGIN),
    ).toBeNull();
    expect(
      authOriginConfigurationError(
        {
          ...admin,
          QUILLMD_SERVICE_ROLE: "template-twin-admin-control",
        },
        PHYSICIAN_PRODUCTION_ORIGIN,
      ),
    ).toBeNull();
    expect(
      authOriginConfigurationError(
        { ...admin, AUTH_URL: PHYSICIAN_PRODUCTION_ORIGIN },
        PHYSICIAN_PRODUCTION_ORIGIN,
      ),
    ).toBe("AUTH_URL_NOT_REVIEWED");
    expect(authOriginConfigurationError(admin, ADMIN_PRODUCTION_ORIGIN)).toBe(
      "PHYSICIAN_APP_URL_NOT_REVIEWED",
    );
  });

  it("rejects a missing or unreviewed production service identity", () => {
    expect(
      authOriginConfigurationError(
        { ...physician, QUILLMD_SERVICE_ROLE: "worker" },
        PHYSICIAN_PRODUCTION_ORIGIN,
      ),
    ).toBe("AUTH_SERVICE_ROLE_NOT_REVIEWED");
  });

  it("permits only the exact, attested isolated synthetic-QA localhost profile", () => {
    const qa = {
      NODE_ENV: "production" as const,
      QUILLMD_SERVICE_ROLE: "physician-app",
      AUTH_URL: SYNTHETIC_QA_PHYSICIAN_ORIGIN,
      NEXTAUTH_URL: SYNTHETIC_QA_PHYSICIAN_ORIGIN,
      ADMIN_PUBLIC_HOST: "localhost",
      PHYSICIAN_PUBLIC_HOST: "localhost",
      TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
      ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION:
        ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION,
    };
    expect(
      authOriginConfigurationError(qa, SYNTHETIC_QA_PHYSICIAN_ORIGIN),
    ).toBeNull();
    expect(
      authOriginConfigurationError(
        { ...qa, ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION: "unreviewed" },
        SYNTHETIC_QA_PHYSICIAN_ORIGIN,
      ),
    ).toBe("AUTH_URL_NOT_REVIEWED");
  });

  it("does not constrain local development", () => {
    expect(
      authOriginConfigurationError(
        {
          NODE_ENV: "development",
          QUILLMD_SERVICE_ROLE: "local",
          AUTH_URL: "http://localhost:3011",
          NEXTAUTH_URL: "http://localhost:3011",
        },
        "http://localhost:3011",
      ),
    ).toBeNull();
  });

  it("throws only a fixed error code without reflecting configured URLs", () => {
    expect(() =>
      assertAuthOriginRuntimeConfiguration(
        { ...physician, NEXTAUTH_URL: "https://sensitive.invalid/path" },
        PHYSICIAN_PRODUCTION_ORIGIN,
      ),
    ).toThrow(
      "Unsafe authentication origin configuration: NEXTAUTH_URL_NOT_REVIEWED",
    );
  });
});
