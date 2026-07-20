import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  isTemplateTwinAdminControlPathAllowed,
  isTemplateTwinAdminAppPathAllowed,
  templateTwinAdminLandingPath,
} from "../admin-app-service";

const REPO = path.resolve(__dirname, "../../../../../..");
const read = (relative: string) =>
  readFileSync(path.join(REPO, relative), "utf8");

const caddy = read("Caddyfile");
const compose = read("docker-compose.yml");
const hostNginx = read("infra/nginx/quillmd.conf");
const proxy = read("apps/transcribe-md/src/proxy.ts");
const nextAuth = read("apps/transcribe-md/src/lib/nextauth.ts");

const SENSITIVE_QUERY_KEYS = [
  "token",
  "code",
  "state",
  "id_token",
  "access_token",
  "refresh_token",
  "secret",
  "password",
  "otp",
] as const;

function block(source: string, start: string, end: string): string {
  const startAt = source.indexOf(start);
  const endAt = source.indexOf(end, startAt + start.length);
  expect(startAt).toBeGreaterThan(-1);
  expect(endAt).toBeGreaterThan(startAt);
  return source.slice(startAt, endAt);
}

describe("Caddy access-log credential redaction", () => {
  const runtimePolicy = block(
    caddy,
    "# ─── Runtime request-error log policy",
    "# ─── Shared access-log policy",
  );
  const accessPolicy = block(
    caddy,
    "(redacted_access_log) {",
    "# ─── Shared header snippet",
  );
  const activeSites = [
    block(caddy, "quillmd.com, www.quillmd.com {", "app.quillmd.com {"),
    block(caddy, "app.quillmd.com {", "admin.quillmd.com {"),
    block(caddy, "admin.quillmd.com {", "pro.quillmd.com {"),
    block(
      caddy,
      "pro.quillmd.com {",
      "# ==========================================================================" +
        "\n# MODE A — rollback reference",
    ),
  ];

  it("uses Caddy's native query filter for every credential-like key", () => {
    for (const policy of [runtimePolicy, accessPolicy]) {
      expect(policy).toContain("format filter {");
      expect(policy).toContain("request>uri query {");
      for (const key of SENSITIVE_QUERY_KEYS) {
        expect(policy).toContain(`replace ${key} REDACTED`);
      }
    }
    expect(runtimePolicy).toContain("wrap json");
    expect(accessPolicy).toContain("wrap console");
  });

  it("applies the policy to every active and rollback-reference logger", () => {
    for (const site of activeSites) {
      expect(site.match(/^\s+import redacted_access_log$/gmu)).toHaveLength(1);
      expect(site).not.toMatch(/^\s+log \{$/gmu);
    }
    expect(caddy.match(/^#\s+import redacted_access_log$/gmu)).toHaveLength(3);
    expect(caddy).not.toMatch(/^#\s+log \{$/gmu);
  });

  it("does not publish host-side design artifacts", () => {
    expect(caddy).not.toContain("/_preview");
    expect(caddy).not.toContain("file_server browse");
    expect(caddy).not.toContain("/srv/_design-references");
    expect(compose).not.toContain("./_design-references:");
  });

  it("keeps bearer query strings and Referer out of host-nginx access logs", () => {
    const format = block(
      hostNginx,
      "log_format quillmd_no_query",
      "server {",
    );
    expect(format).toContain("$request_method $uri $server_protocol");
    expect(format).not.toContain("$request_uri");
    expect(format).not.toContain("$request\"");
    expect(format).not.toContain("$http_referer");
    expect(
      hostNginx.match(
        /^\s+access_log \/var\/log\/nginx\/quillmd_access\.log quillmd_no_query;$/gmu,
      ),
    ).toHaveLength(2);
  });

  it("trusts only the deterministic host-ingress hop, never private peers", () => {
    expect(caddy).toContain("trusted_proxies static 172.31.252.1/32");
    expect(caddy).toContain("trusted_proxies_strict");
    expect(caddy).not.toContain("trusted_proxies static private_ranges");
    expect(compose).toContain("subnet: 172.31.252.0/24");
    expect(compose).toContain("gateway: 172.31.252.1");

    const caddyService = block(
      compose,
      "  caddy:",
      "  # ── TranscribeMD Marketing",
    );
    expect(caddyService).toContain("networks:\n      - quillmd_ingress");
    expect(caddyService).not.toContain("networks:\n      - default");
    for (const upstream of [
      block(compose, "  meddoc-pro:", "  # ── Redis"),
      block(compose, "  marketing:", "  # ── TranscribeMD worker"),
      block(
        compose,
        "  transcribe-md: &transcribe_md_app",
        "  # Isolated cookie/session",
      ),
    ]) {
      expect(upstream).toContain("- quillmd_ingress");
    }
  });
});

describe("Template Twin admin app ingress and credential isolation", () => {
  const adminHost = block(caddy, "admin.quillmd.com {", "pro.quillmd.com {");
  const physicianHost = block(
    caddy,
    "app.quillmd.com {",
    "admin.quillmd.com {",
  );
  const adminApp = block(
    compose,
    "  template-twin-admin-app:",
    "  template-twin-admin-control:",
  );
  const releaseControl = block(
    compose,
    "  template-twin-admin-control:",
    "  # ── DB Migrator",
  );

  it("routes auth and only the exact practice-admin page/API to the admin app", () => {
    expect(adminHost).toMatch(
      /@auth path \/api\/auth\/\*[\s\S]*?reverse_proxy template-twin-admin-app:3011/u,
    );
    expect(adminHost).toMatch(
      /@templateTwinStaticAssetApi path \/api\/note-templates\/template-twin\/static-assets\n[\s\S]*?reverse_proxy template-twin-admin-app:3011/u,
    );
    expect(adminHost).toMatch(
      /@templateTwinRollbackApi path \/api\/admin\/template-twin\/rollback\n[\s\S]*?reverse_proxy template-twin-admin-app:3011/u,
    );
    expect(adminHost).toMatch(
      /@templateTwinStaticAssetPage path \/settings\/note-format\/static-assets\n[\s\S]*?reverse_proxy template-twin-admin-app:3011/u,
    );
    expect(adminHost).not.toContain(
      "@templateTwinStaticAssetApi path /api/note-templates/template-twin/static-assets/*",
    );
    expect(physicianHost).not.toContain(
      "reverse_proxy template-twin-admin-app:3011",
    );
    const staticMatcher =
      adminHost
        .split(/\r?\n/u)
        .find((line) => line.includes("@nextStatic path")) ?? "";
    expect(staticMatcher).toContain("/_next/static/*");
    expect(staticMatcher).not.toContain("/_next/*");
    expect(staticMatcher).not.toContain("/_next/image");
    expect(staticMatcher).not.toContain("/_next/data");
    const staticAssets = block(
      adminHost,
      "@nextStatic path",
      "# Auth-flow pages",
    );
    expect(staticAssets).toContain(
      "reverse_proxy template-twin-admin-app:3011",
    );
    expect(staticAssets).not.toContain("reverse_proxy transcribe-md:3011");
    expect(adminHost).not.toContain(
      "@templateTwinAdminAppHealth path /api/health/template-twin-admin-app",
    );
    expect(adminHost).not.toMatch(
      /path[^\n]*\/api\/health\/template-twin-admin-app/u,
    );
  });

  it("routes exact reviewed controls ahead of explicit legacy-admin denies", () => {
    const controlApi = adminHost.indexOf("@templateTwinControlApi path");
    const staticApi = adminHost.indexOf("@templateTwinStaticAssetApi path");
    const rollbackApi = adminHost.indexOf("@templateTwinRollbackApi path");
    const legacyApiDeny = adminHost.indexOf(
      "@retiredLegacyAdminApi path /api/admin /api/admin/*",
    );
    const controlPage = adminHost.indexOf("@templateTwinControlPage path");
    const staticPage = adminHost.indexOf("@templateTwinStaticAssetPage path");
    const legacyPageDeny = adminHost.indexOf(
      "@retiredLegacyAdminPage path /admin /admin/*",
    );
    expect(controlApi).toBeGreaterThan(-1);
    expect(controlPage).toBeGreaterThan(-1);
    expect(controlApi).toBeLessThan(staticApi);
    expect(staticApi).toBeLessThan(legacyApiDeny);
    expect(rollbackApi).toBeGreaterThan(staticApi);
    expect(rollbackApi).toBeLessThan(legacyApiDeny);
    expect(controlPage).toBeLessThan(staticPage);
    expect(staticPage).toBeLessThan(legacyPageDeny);
    expect(adminHost).toMatch(
      /@templateTwinControlApi path[^\n]+[\s\S]*?reverse_proxy template-twin-admin-control:3011/u,
    );
    expect(adminHost).toMatch(
      /@templateTwinControlPage path[^\n]+[\s\S]*?reverse_proxy template-twin-admin-control:3011/u,
    );
    expect(
      read("apps/transcribe-md/src/lib/template-twin/admin-app-service.ts"),
    ).toContain('"/admin/template-twin-release" as const');
    expect(adminHost).toContain(
      "@templateTwinControlPage path /admin/template-twin-release /admin/template-twin-release/*",
    );
    expect(adminHost).toMatch(
      /@retiredLegacyAdminApi path \/api\/admin \/api\/admin\/\*[\s\S]*?respond "Not Found" 404/u,
    );
    expect(adminHost).toMatch(
      /@retiredLegacyAdminPage path \/admin \/admin\/\*[\s\S]*?respond "Not Found" 404/u,
    );
    expect(adminHost).not.toContain("reverse_proxy transcribe-md:3011");
    expect(
      isTemplateTwinAdminAppPathAllowed("/api/admin/template-twin/rollback"),
    ).toBe(true);
    expect(
      isTemplateTwinAdminControlPathAllowed(
        "/api/admin/template-twin/rollback",
      ),
    ).toBe(false);
    expect(adminHost).not.toContain("rewrite * /admin");
    expect(adminHost).not.toContain("@root path /");
  });

  it("carries a SUPER_ADMIN-only login directly across the isolated release-control boundary", () => {
    const landing = templateTwinAdminLandingPath({
      role: "DOCTOR",
      products: ["SUPER_ADMIN"],
      mfaEnabled: true,
      mfaSecret: "SYNTHETIC-SECRET",
      mfaVerifiedAt: new Date("2020-01-01T00:00:00.000Z"),
    });
    expect(landing).toBe("/admin/template-twin-release");
    expect(isTemplateTwinAdminAppPathAllowed(landing!)).toBe(false);
    expect(adminHost).toMatch(
      /@templateTwinControlPage path \/admin\/template-twin-release[^\n]*[\s\S]*?reverse_proxy template-twin-admin-control:3011/u,
    );
    expect(adminApp).toContain("AUTH_SECRET: ${AUTH_SECRET:-}");
    expect(releaseControl).toContain("AUTH_SECRET: ${AUTH_SECRET:-}");
    expect(
      read("apps/transcribe-md/src/lib/admin-session-freshness.ts"),
    ).toContain("template_twin_verify_release_admin_session");
  });

  it("uses a separate unexposed runtime process with a distinct APP attestation", () => {
    expect(adminApp).toContain("env_file: []");
    expect(adminApp).toContain("ports: []");
    expect(adminApp).toContain("QUILLMD_SERVICE_ROLE: template-twin-admin-app");
    expect(adminApp).toContain("postgresql://meddoc_runtime:");
    expect(adminApp).toContain(
      'TEMPLATE_TWIN_RELEASE_CONTROL_DATABASE_URL: ""',
    );
    expect(adminApp).toContain('DB_RELEASE_CONTROL_PASSWORD: ""');
    expect(adminApp).toContain(
      "TEMPLATE_TWIN_RUNTIME_ATTESTATION: ${TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION:-}",
    );
    expect(adminApp).toContain(
      "TEMPLATE_TWIN_LOCAL_OCR_EXECUTABLE: /usr/bin/tesseract",
    );
    expect(adminApp).toContain(
      "http://127.0.0.1:3011/api/health/template-twin-admin-app",
    );
    expect(
      isTemplateTwinAdminAppPathAllowed("/api/health/template-twin-admin-app"),
    ).toBe(true);
    expect(adminApp).toContain("ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}");
    expect(adminApp).not.toContain("postgresql://meddoc_release_control:");
    expect(adminHost).not.toMatch(
      /path[^\n]*\/api\/health\/template-twin-admin-app/u,
    );
  });

  it("keeps release control free of runtime and provider credentials", () => {
    expect(releaseControl).toContain("postgresql://meddoc_release_control:");
    expect(releaseControl).not.toContain("postgresql://meddoc_runtime:");
    expect(releaseControl).toContain('ANTHROPIC_API_KEY: ""');
    expect(releaseControl).toContain('MINIO_ACCESS_KEY: ""');
    expect(releaseControl).toContain('MINIO_SECRET_KEY: ""');
    expect(releaseControl).not.toContain("${ANTHROPIC_API_KEY");
    expect(releaseControl).toContain('TEMPLATE_TWIN_RUNTIME_ATTESTATION: ""');
    expect(releaseControl).toContain(
      "http://127.0.0.1:3011/api/admin/template-twin/control-health",
    );
    expect(adminHost).not.toMatch(
      /path[^\n]*\/api\/admin\/template-twin\/control-health/u,
    );
  });

  it("denies non-allowlisted same-image routes before auth and leaves physician policy exact", () => {
    expect(proxy).toContain("isTemplateTwinAdminAppPathAllowed(pathname)");
    expect(proxy).toContain("isTemplateTwinAdminControlPathAllowed(pathname)");
    expect(proxy).toContain("if (!allowed)");
    expect(proxy).toContain("status: 404");
    expect(proxy).toMatch(/matcher:\s*\[["']\/:path\*["']\]/u);
    expect(nextAuth).toContain("transcribeMdSessionPolicyForService()");
    expect(
      read("apps/transcribe-md/src/lib/template-twin/admin-app-service.ts"),
    ).toContain('allowedRoles: ["DOCTOR"]');
    expect(
      read("apps/transcribe-md/src/lib/template-twin/admin-app-service.ts"),
    ).toContain('requiredProducts: ["TRANSCRIBE_MD"]');
    expect(isTemplateTwinAdminControlPathAllowed("/dashboard")).toBe(false);
    expect(
      isTemplateTwinAdminControlPathAllowed(
        "/api/admin/template-twin/control-health",
      ),
    ).toBe(true);
  });
});
