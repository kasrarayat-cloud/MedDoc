import { describe, expect, it } from "vitest";

import {
  TEMPLATE_TWIN_ADMIN_APP_SESSION_POLICY,
  TEMPLATE_TWIN_ADMIN_MFA_PATH,
  TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH,
  TEMPLATE_TWIN_RELEASE_CONTROL_PATH,
  TRANSCRIBE_MD_DENY_SESSION_POLICY,
  TRANSCRIBE_MD_PHYSICIAN_SESSION_POLICY,
  hasTemplateTwinAdminAppAccess,
  isTemplateTwinAdminControlPathAllowed,
  isTemplateTwinAdminControlService,
  isTemplateTwinAdminAppPathAllowed,
  isTemplateTwinAdminAppService,
  isTranscribeMdPhysicianProxyPath,
  templateTwinAdminLandingPath,
  transcribeMdSessionPolicyForService,
} from "../admin-app-service";

describe("isolated Template Twin admin app service", () => {
  it("keeps the ordinary TranscribeMD process on the exact physician policy", () => {
    expect(
      transcribeMdSessionPolicyForService({
        QUILLMD_SERVICE_ROLE: "physician-app",
      }),
    ).toBe(TRANSCRIBE_MD_PHYSICIAN_SESSION_POLICY);
    expect(
      transcribeMdSessionPolicyForService({
        QUILLMD_SERVICE_ROLE: "template-twin-admin-control",
      }),
    ).toBe(TRANSCRIBE_MD_DENY_SESSION_POLICY);
    expect(
      transcribeMdSessionPolicyForService({
        QUILLMD_SERVICE_ROLE: "unreviewed-service",
      }),
    ).toBe(TRANSCRIBE_MD_DENY_SESSION_POLICY);
    expect(transcribeMdSessionPolicyForService({})).toBe(
      TRANSCRIBE_MD_DENY_SESSION_POLICY,
    );
    expect(
      isTemplateTwinAdminAppService({
        QUILLMD_SERVICE_ROLE: "physician-app",
      }),
    ).toBe(false);
  });

  it("selects the disjunctive current-authority policy only for the admin process", () => {
    expect(
      transcribeMdSessionPolicyForService({
        QUILLMD_SERVICE_ROLE: "template-twin-admin-app",
      }),
    ).toBe(TEMPLATE_TWIN_ADMIN_APP_SESSION_POLICY);
  });

  it("recognizes only the exact privileged control service identity", () => {
    expect(
      isTemplateTwinAdminControlService({
        QUILLMD_SERVICE_ROLE: "template-twin-admin-control",
      }),
    ).toBe(true);
    expect(
      isTemplateTwinAdminControlService({
        QUILLMD_SERVICE_ROLE: "template-twin-admin-control-lookalike",
      }),
    ).toBe(false);
  });

  it("admits a TranscribeMD practice admin or product-authorized platform admin, never an ordinary physician", () => {
    expect(
      hasTemplateTwinAdminAppAccess({
        role: "ADMIN",
        products: ["TRANSCRIBE_MD"],
      }),
    ).toBe(true);
    expect(
      hasTemplateTwinAdminAppAccess({
        role: "DOCTOR",
        products: ["SUPER_ADMIN"],
      }),
    ).toBe(true);
    expect(
      hasTemplateTwinAdminAppAccess({
        role: "DOCTOR",
        products: ["TRANSCRIBE_MD"],
      }),
    ).toBe(false);
    expect(hasTemplateTwinAdminAppAccess({ role: "ADMIN", products: [] })).toBe(
      false,
    );
  });

  it("lands practice admins on the only practice-scoped admin page and gates platform MFA", () => {
    expect(
      templateTwinAdminLandingPath({
        role: "ADMIN",
        products: ["TRANSCRIBE_MD"],
      }),
    ).toBe(TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH);
    expect(
      templateTwinAdminLandingPath({
        role: "DOCTOR",
        products: ["SUPER_ADMIN"],
      }),
    ).toBe(TEMPLATE_TWIN_ADMIN_MFA_PATH);
    expect(
      templateTwinAdminLandingPath({
        role: "DOCTOR",
        products: ["SUPER_ADMIN"],
        mfaEnabled: true,
        mfaSecret: "SYNTHETIC-SECRET",
        mfaVerifiedAt: new Date("2020-01-01T00:00:00.000Z"),
      }),
    ).toBe(TEMPLATE_TWIN_RELEASE_CONTROL_PATH);
    expect(
      templateTwinAdminLandingPath({
        role: "DOCTOR",
        products: ["SUPER_ADMIN"],
        mfaEnabled: true,
        mfaSecret: "   ",
        mfaVerifiedAt: new Date("2020-01-01T00:00:00.000Z"),
      }),
    ).toBe(TEMPLATE_TWIN_ADMIN_MFA_PATH);
    expect(
      templateTwinAdminLandingPath({
        role: "DOCTOR",
        products: ["TRANSCRIBE_MD"],
      }),
    ).toBeNull();
  });

  it.each([
    "/login",
    "/api/auth/session",
    "/api/mfa/enroll",
    "/api/mfa/recovery-codes/rotate",
    "/settings/security/mfa",
    "/settings/note-format/static-assets",
    "/api/note-templates/template-twin/static-assets",
    "/api/admin/template-twin/rollback",
    "/api/health/template-twin-admin-app",
    "/_next/static/chunks/synthetic.js",
  ])("allows the exact admin-process route surface: %s", (pathname) => {
    expect(isTemplateTwinAdminAppPathAllowed(pathname)).toBe(true);
  });

  it.each([
    "/",
    "/dashboard",
    "/visits/synthetic",
    "/patients",
    "/settings",
    "/settings/note-format",
    "/api/visits",
    "/api/patients",
    "/api/admin/users",
    "/api/admin/template-twin/releases",
    "/admin/template-twin-release",
    "/api/note-templates/template-twin/static-assets/extra",
    "/api/admin/template-twin/rollback/extra",
    "/api/authentic-looking",
    "/_next/image",
  ])(
    "denies physician, platform-control, or lookalike paths: %s",
    (pathname) => {
      expect(isTemplateTwinAdminAppPathAllowed(pathname)).toBe(false);
    },
  );

  it.each([
    "/admin/template-twin-release",
    "/admin/template-twin-release/synthetic-child",
    "/api/admin/template-twin/releases",
    "/api/admin/template-twin/releases/synthetic-release",
    "/api/admin/template-twin/release-metrics",
    "/api/admin/template-twin/release-metrics/synthetic-snapshot",
    "/api/admin/template-twin/control-health",
    "/_next/static/chunks/synthetic.js",
  ])("allows the exact control-process route surface: %s", (pathname) => {
    expect(isTemplateTwinAdminControlPathAllowed(pathname)).toBe(true);
  });

  it.each([
    "/",
    "/login",
    "/dashboard",
    "/api/auth/session",
    "/api/admin/users",
    "/api/admin/template-twin/rollback",
    "/api/admin/template-twin/control-health/extra",
    "/api/admin/template-twin/releases-lookalike",
    "/api/admin/template-twin/release-metrics-lookalike",
    "/settings/note-format/static-assets",
    "/_next/image",
  ])("denies every unreviewed control-process path: %s", (pathname) => {
    expect(isTemplateTwinAdminControlPathAllowed(pathname)).toBe(false);
  });

  it("preserves the pre-existing physician proxy path census", () => {
    expect(isTranscribeMdPhysicianProxyPath("/dashboard")).toBe(true);
    expect(isTranscribeMdPhysicianProxyPath("/visits/current")).toBe(true);
    expect(isTranscribeMdPhysicianProxyPath("/settings/security")).toBe(true);
    expect(isTranscribeMdPhysicianProxyPath("/api/auth/session")).toBe(false);
    expect(isTranscribeMdPhysicianProxyPath("/dashboard-lookalike")).toBe(
      false,
    );
  });
});
