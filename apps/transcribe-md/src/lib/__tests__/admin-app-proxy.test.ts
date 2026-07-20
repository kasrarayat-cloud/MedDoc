import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  authenticatedProxy: vi.fn(),
}));

vi.mock("next-auth", () => ({
  default: vi.fn(() => ({
    auth: vi.fn(() => mocks.authenticatedProxy),
  })),
}));

import proxy, { config } from "../../proxy";

function request(pathname: string): NextRequest {
  return new NextRequest(`https://admin.quillmd.com${pathname}`);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.authenticatedProxy.mockResolvedValue(
    new Response(null, { headers: { "x-middleware-next": "1" } }),
  );
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("same-image admin process route-surface gate", () => {
  it("matches every path so internal or Caddy misroutes cannot bypass it", () => {
    expect(config).toEqual({ matcher: ["/:path*"] });
  });

  it.each([
    "/dashboard",
    "/visits/synthetic",
    "/api/visits",
    "/api/admin/users",
    "/api/admin/template-twin/releases",
    "/admin/template-twin-release",
  ])("returns the same closed 404 before auth for %s", async (pathname) => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");

    const response = await proxy(request(pathname), {} as never);

    expect(response).toBeInstanceOf(Response);
    if (!(response instanceof Response)) {
      throw new Error("Synthetic admin route denial returned no response.");
    }
    expect(response.status).toBe(404);
    expect(await response.text()).toBe("Not Found");
    expect(response.headers.get("cache-control")).toContain("no-store");
    expect(mocks.authenticatedProxy).not.toHaveBeenCalled();
  });

  it.each([
    "/login",
    "/api/auth/session",
    "/api/mfa/recovery-codes/rotate",
    "/settings/note-format/static-assets",
    "/api/note-templates/template-twin/static-assets",
    "/api/admin/template-twin/rollback",
    "/api/health/template-twin-admin-app",
  ])(
    "passes an allowlisted path into the cookie-auth proxy: %s",
    async (pathname) => {
      vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-app");

      await proxy(request(pathname), {} as never);

      expect(mocks.authenticatedProxy).toHaveBeenCalledOnce();
    },
  );

  it.each([
    "/",
    "/login",
    "/dashboard",
    "/visits/synthetic",
    "/api/visits",
    "/api/admin/users",
    "/api/admin/template-twin/rollback",
    "/api/note-templates/template-twin/static-assets",
    "/settings/note-format/static-assets",
    "/_next/image",
  ])(
    "closes the privileged control process before auth for %s",
    async (pathname) => {
      vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-control");

      const response = await proxy(request(pathname), {} as never);

      expect(response).toBeInstanceOf(Response);
      if (!(response instanceof Response)) {
        throw new Error("Synthetic control route denial returned no response.");
      }
      expect(response.status).toBe(404);
      expect(await response.text()).toBe("Not Found");
      expect(response.headers.get("cache-control")).toContain("no-store");
      expect(mocks.authenticatedProxy).not.toHaveBeenCalled();
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
  ])("passes only a reviewed control path into auth: %s", async (pathname) => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "template-twin-admin-control");

    await proxy(request(pathname), {} as never);

    expect(mocks.authenticatedProxy).toHaveBeenCalledOnce();
  });

  it("preserves the ordinary physician process matcher behavior", async () => {
    vi.stubEnv("QUILLMD_SERVICE_ROLE", "physician-app");

    await proxy(request("/login"), {} as never);
    expect(mocks.authenticatedProxy).not.toHaveBeenCalled();

    await proxy(request("/dashboard"), {} as never);
    expect(mocks.authenticatedProxy).toHaveBeenCalledOnce();
  });
});
