// ============================================================================
// Auth cookie config posture (Security Audit P1-H, 2026-05-13)
// ----------------------------------------------------------------------------
// Pre-fix, the `cookies.sessionToken.options` block was emitted only
// when `AUTH_COOKIE_DOMAIN` was set. With AUTH_COOKIE_DOMAIN unset
// (today's prod), the app silently inherited NextAuth defaults.
// The fix emits the hardening flags unconditionally; `domain` is the
// only field that varies by env.
//
// This is a source-pin guard — the actual cookie shape is exercised
// by NextAuth at runtime, not directly testable in unit scope.
// ============================================================================

import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC = readFileSync(
  resolve(
    __dirname,
    "..",
    "..",
    "..",
    "..",
    "packages",
    "auth",
    "src",
    "index.ts",
  ),
  "utf-8",
);

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("packages/auth — cookie config (P1-H)", () => {
  it("emits the `cookies.sessionToken` block unconditionally (no gating ternary)", () => {
    // Pre-fix pattern: `...(cookieDomain ? { cookies: { ... } } : {})`.
    // The fix removes the ternary wrap; `cookies:` is now a top-level
    // property of the config object.
    expect(SRC).not.toMatch(/\.\.\.\(\s*cookieDomain\s*\?\s*\{\s*cookies:/);
    expect(SRC).toMatch(/\n\s*cookies:\s*\{\s*\n\s*sessionToken:/);
  });

  it("pins httpOnly: true, sameSite: lax, path: /, secure: prod-only", () => {
    // Whitespace-flexible to survive a future reformat. All four
    // flags must be present in the options block.
    expect(SRC).toMatch(/httpOnly:\s*true/);
    expect(SRC).toMatch(/sameSite:\s*['"]lax['"]\s*as\s*const/);
    expect(SRC).toMatch(/path:\s*['"]\/['"]/);
    expect(SRC).toMatch(
      /secure:\s*process\.env\.NODE_ENV\s*===\s*['"]production['"]/,
    );
  });

  it("uses __Secure- cookie-name prefix in production", () => {
    expect(SRC).toMatch(
      /name:[\s\S]{0,80}?['"]__Secure-authjs\.session-token['"]/,
    );
  });

  it("only adds the `domain` field when AUTH_COOKIE_DOMAIN is set (host-only default preserved)", () => {
    // The conditional spread `...(cookieDomain ? { domain: cookieDomain } : {})`
    // means the domain field is omitted when AUTH_COOKIE_DOMAIN is unset.
    expect(SRC).toMatch(
      /\.\.\.\(\s*cookieDomain\s*\?\s*\{\s*domain:\s*cookieDomain\s*\}\s*:\s*\{\s*\}\s*\)/,
    );
  });

  it("fails production startup when a parent-domain cookie is configured", () => {
    expect(SRC).toContain("AUTH_COOKIE_DOMAIN must be unset in production");
    expect(SRC).toMatch(
      /NODE_ENV\s*===\s*['"]production['"][\s\S]*NEXT_PHASE[\s\S]*cookieDomain[\s\S]*throw new Error/u,
    );
  });

  it("rejects a production parent-domain cookie during real module initialization", async () => {
    vi.resetModules();
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PHASE", "phase-production-server");
    vi.stubEnv("AUTH_SECRET", "synthetic-auth-secret-not-for-production");
    vi.stubEnv("AUTH_COOKIE_DOMAIN", ".quillmd.com");

    await expect(import("@meddoc/auth")).rejects.toThrow(
      "AUTH_COOKIE_DOMAIN must be unset in production",
    );
  });

  it("emits a host-only production session cookie when the domain is unset", async () => {
    vi.resetModules();
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PHASE", "phase-production-server");
    vi.stubEnv("AUTH_SECRET", "synthetic-auth-secret-not-for-production");
    vi.stubEnv("AUTH_COOKIE_DOMAIN", "");

    const { authConfig } = await import("@meddoc/auth");
    expect(authConfig.cookies?.sessionToken?.options).toMatchObject({
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure: true,
    });
    expect(authConfig.cookies?.sessionToken?.options?.domain).toBeUndefined();
  });
});
