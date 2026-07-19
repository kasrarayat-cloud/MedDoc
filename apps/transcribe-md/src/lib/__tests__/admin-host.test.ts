import { describe, expect, it } from "vitest";

import {
  ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION,
  adminSurfaceConfigurationError,
  assertAdminSurfaceRuntimeConfiguration,
  configuredAdminHost,
  isAdminRequestHost,
} from "../admin-host";

function requestHeaders(
  host: string | null,
  forwardedHost: string | null = null,
): Pick<Headers, "get"> {
  return {
    get(name: string) {
      if (name.toLowerCase() === "host") return host;
      if (name.toLowerCase() === "x-forwarded-host") return forwardedHost;
      return null;
    },
  };
}

describe("platform-admin host boundary", () => {
  it("defaults production to the dedicated admin hostname", () => {
    expect(configuredAdminHost({ NODE_ENV: "production" })).toBe(
      "admin.quillmd.com",
    );
    expect(
      isAdminRequestHost(requestHeaders("admin.quillmd.com"), {
        NODE_ENV: "production",
      }),
    ).toBe(true);
  });

  it("refuses physician-host and forwarded-host spoofing", () => {
    const environment = { NODE_ENV: "production" as const };
    expect(
      isAdminRequestHost(
        requestHeaders("app.quillmd.com", "admin.quillmd.com"),
        environment,
      ),
    ).toBe(false);
    expect(isAdminRequestHost(requestHeaders(null), environment)).toBe(false);
  });

  it("normalizes ports and configured case without accepting malformed hosts", () => {
    const environment = {
      NODE_ENV: "production" as const,
      ADMIN_PUBLIC_HOST: "ADMIN.QuillMD.com:443",
    };
    expect(
      isAdminRequestHost(requestHeaders("admin.quillmd.com:8443"), environment),
    ).toBe(true);
    expect(
      isAdminRequestHost(requestHeaders("admin.quillmd.com.evil"), environment),
    ).toBe(false);
    expect(
      isAdminRequestHost(requestHeaders("admin.quillmd.com@evil"), environment),
    ).toBe(false);
  });

  it("permits unconfigured development but fails closed on invalid production configuration", () => {
    expect(
      isAdminRequestHost(requestHeaders("localhost:3011"), {
        NODE_ENV: "development",
      }),
    ).toBe(true);
    expect(
      isAdminRequestHost(requestHeaders("admin.quillmd.com"), {
        NODE_ENV: "production",
        ADMIN_PUBLIC_HOST: "https://admin.quillmd.com",
      }),
    ).toBe(false);
  });

  it("rejects physician-host collapse and parent-domain session cookies", () => {
    const collapsed = {
      NODE_ENV: "production" as const,
      ADMIN_PUBLIC_HOST: "app.quillmd.com",
      PHYSICIAN_PUBLIC_HOST: "app.quillmd.com",
    };
    expect(adminSurfaceConfigurationError(collapsed)).toBe(
      "PRODUCTION_ADMIN_HOST_NOT_REVIEWED",
    );
    expect(configuredAdminHost(collapsed)).toBeNull();
    expect(
      isAdminRequestHost(requestHeaders("app.quillmd.com"), collapsed),
    ).toBe(false);

    const sharedCookie = {
      NODE_ENV: "production" as const,
      ADMIN_PUBLIC_HOST: "admin.quillmd.com",
      AUTH_COOKIE_DOMAIN: ".quillmd.com",
    };
    expect(adminSurfaceConfigurationError(sharedCookie)).toBe(
      "ADMIN_COOKIE_MUST_BE_HOST_ONLY",
    );
    expect(() => assertAdminSurfaceRuntimeConfiguration(sharedCookie)).toThrow(
      "ADMIN_COOKIE_MUST_BE_HOST_ONLY",
    );
  });

  it("permits only the explicit isolated synthetic-QA shared-host exception", () => {
    const qa = {
      NODE_ENV: "production" as const,
      ADMIN_PUBLIC_HOST: "localhost",
      PHYSICIAN_PUBLIC_HOST: "localhost",
      TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
      ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION:
        ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION,
    };
    expect(adminSurfaceConfigurationError(qa)).toBeNull();
    expect(isAdminRequestHost(requestHeaders("localhost:9020"), qa)).toBe(true);

    expect(
      adminSurfaceConfigurationError({
        ...qa,
        ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION: "unreviewed",
      }),
    ).toBe("PRODUCTION_ADMIN_HOST_NOT_REVIEWED");
  });
});
