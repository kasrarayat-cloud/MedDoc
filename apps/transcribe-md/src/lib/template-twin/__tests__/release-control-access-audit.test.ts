import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ execute: vi.fn() }));

vi.mock("@/lib/template-twin/release-control-db", () => ({
  default: { $executeRaw: mocks.execute },
}));

import { recordTemplateTwinControlAccess } from "../release-control-access-audit";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.execute.mockResolvedValue(1);
});

describe("Template Twin isolated control access audit", () => {
  it("persists a bounded synthetic access receipt through the outbox", async () => {
    await recordTemplateTwinControlAccess({
      actorId: "admin_synthetic",
      actorEmail: "admin@synthetic.invalid",
      practiceId: "practice_synthetic",
      routeKey: "template-twin:releases:inspect",
      request: new Request(
        "https://admin.quillmd.com/api/admin/template-twin/releases",
        {
          method: "GET",
          headers: {
            "x-real-ip": "192.0.2.10",
            "user-agent": "synthetic-control-reviewer",
          },
        },
      ),
    });
    expect(mocks.execute).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["invalid route key", "template twin", "GET", "/api/admin/template-twin/releases"],
    ["invalid method", "template-twin:releases:inspect", "DELETE", "/api/admin/template-twin/releases"],
    ["invalid path", "template-twin:releases:inspect", "GET", "/api/admin/users"],
  ])("rejects %s before database access", async (_label, routeKey, method, path) => {
    await expect(
      recordTemplateTwinControlAccess({
        actorId: "admin_synthetic",
        actorEmail: null,
        practiceId: "practice_synthetic",
        routeKey,
        request: new Request(`https://admin.quillmd.com${path}`, { method }),
      }),
    ).rejects.toThrow(/invalid/u);
    expect(mocks.execute).not.toHaveBeenCalled();
  });
});
