import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const SRC = path.resolve(__dirname, "../..");
const pageContracts = [
  ["app/admin/page.tsx", "getSystemHealth"],
  ["app/admin/users/page.tsx", "fetchUserListPage"],
  ["app/admin/usage/page.tsx", "fetchUsageSummary"],
  ["app/admin/queues/page.tsx", "readQueueRow"],
  ["app/admin/threats/page.tsx", "getThreatsPageData"],
  ["app/admin/hipaa/page.tsx", "getAllFindings"],
] as const;

describe("admin page fresh-authorization contract", () => {
  it.each(pageContracts)(
    "%s invokes the page gate before its first protected read",
    (relativePath, firstRead) => {
      const source = readFileSync(path.join(SRC, relativePath), "utf8");
      const gate = source.indexOf("requireFreshPlatformAdminPage(");
      const read = source.lastIndexOf(firstRead);
      expect(gate).toBeGreaterThan(-1);
      expect(read).toBeGreaterThan(gate);
      expect(source).not.toContain("from '@/lib/nextauth'");
    },
  );

  it("keeps the layout as routing defense instead of claiming reusable-layout authorization", () => {
    const layout = readFileSync(path.join(SRC, "app/admin/layout.tsx"), "utf8");
    expect(layout).toContain("every page invokes the fresh");
    expect(layout).toContain("if (!verified.mfaComplete)");
    expect(layout).not.toContain(
      "!verified.mfaEnabled || !verified.mfaVerifiedAt",
    );
    expect(layout).not.toContain("void logAudit");
  });
});
