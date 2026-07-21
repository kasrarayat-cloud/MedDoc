import { describe, expect, it } from "vitest";

import {
  ADMIN_SYNTHETIC_QA_SHARED_HOST_ATTESTATION,
  adminSurfaceConfigurationError,
  assertAdminSurfaceRuntimeConfiguration,
  configuredAdminHost,
  isAdminRequestHost,
  isPhysicianRequestHost,
} from "../admin-host";

const SYNTHETIC_QA_DATABASE_CREDENTIAL = "s".repeat(43);

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

  it("admits clinical authorization only on the exact physician host", () => {
    const environment = { NODE_ENV: "production" as const };
    expect(
      isPhysicianRequestHost(requestHeaders("app.quillmd.com"), environment),
    ).toBe(true);
    expect(
      isPhysicianRequestHost(
        requestHeaders("admin.quillmd.com", "app.quillmd.com"),
        environment,
      ),
    ).toBe(false);
    expect(
      isPhysicianRequestHost(requestHeaders("other.quillmd.com"), environment),
    ).toBe(false);
    expect(isPhysicianRequestHost(requestHeaders(null), environment)).toBe(
      false,
    );
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
    expect(
      isPhysicianRequestHost(requestHeaders("localhost:3010"), {
        NODE_ENV: "development",
      }),
    ).toBe(true);
    expect(
      isPhysicianRequestHost(requestHeaders("admin.quillmd.com"), {
        NODE_ENV: "development",
        ADMIN_PUBLIC_HOST: "admin.quillmd.com",
      }),
    ).toBe(false);
    expect(
      isPhysicianRequestHost(requestHeaders("app.quillmd.com"), {
        NODE_ENV: "production",
        PHYSICIAN_PUBLIC_HOST: "https://app.quillmd.com",
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

  it("rejects an unreviewed production physician hostname", () => {
    const overridden = {
      NODE_ENV: "production" as const,
      ADMIN_PUBLIC_HOST: "admin.quillmd.com",
      PHYSICIAN_PUBLIC_HOST: "physician.example.test",
    };
    expect(adminSurfaceConfigurationError(overridden)).toBe(
      "PRODUCTION_PHYSICIAN_HOST_NOT_REVIEWED",
    );
    expect(
      isPhysicianRequestHost(
        requestHeaders("physician.example.test"),
        overridden,
      ),
    ).toBe(false);
    expect(() => assertAdminSurfaceRuntimeConfiguration(overridden)).toThrow(
      "PRODUCTION_PHYSICIAN_HOST_NOT_REVIEWED",
    );
  });

  it("permits only the explicit isolated synthetic-QA shared-host exception", () => {
    const qa = {
      NODE_ENV: "production" as const,
      QUILLMD_SERVICE_ROLE: "physician-app",
      QUILLMD_DATABASE_PRINCIPAL_PROFILE: "synthetic-disposable-qa-v1",
      ADMIN_PUBLIC_HOST: "localhost",
      PHYSICIAN_PUBLIC_HOST: "localhost",
      AUTH_URL: "http://localhost:9020",
      NEXTAUTH_URL: "http://localhost:9020",
      TEMPLATE_TWIN_STAGING_QA_ENVIRONMENT: "qa",
      TEMPLATE_TWIN_STAGING_QA_RESOURCE_ATTESTATION:
        "isolated-disposable-qa-v1",
      TEMPLATE_TWIN_STORAGE_PROFILE: "qa",
      DATABASE_URL: `postgresql://meddoc_runtime:${SYNTHETIC_QA_DATABASE_CREDENTIAL}@postgres:5432/meddoc_qa_test?schema=public&options=-c%20search_path%3Dpg_catalog%2Cpublic`,
      REDIS_URL: "redis://redis:6379/15",
      MINIO_ENDPOINT: "minio:9000",
      MINIO_USE_SSL: "false",
      TRANSCRIBE_MD_MINIO_BUCKET: "transcribe-md-audio-qa",
      TRANSCRIBE_MD_TEMPLATE_BUCKET: "transcribe-md-template-artifacts-qa",
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

    expect(
      adminSurfaceConfigurationError({
        ...qa,
        ADMIN_PUBLIC_HOST: "admin.quillmd.com",
      }),
    ).toBe("PRODUCTION_PHYSICIAN_HOST_NOT_REVIEWED");
  });
});
