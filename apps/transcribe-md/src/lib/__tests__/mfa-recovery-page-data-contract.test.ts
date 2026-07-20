import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = resolve(process.cwd(), "../..");
const page = readFileSync(
  resolve(ROOT, "apps/transcribe-md/src/app/settings/security/mfa/page.tsx"),
  "utf8",
);
const settingsPage = readFileSync(
  resolve(ROOT, "apps/transcribe-md/src/app/settings/page.tsx"),
  "utf8",
);
const managementPanel = readFileSync(
  resolve(
    ROOT,
    "apps/transcribe-md/src/app/settings/security/mfa/mfa-management-panel.tsx",
  ),
  "utf8",
);

describe("MFA recovery page data minimization", () => {
  it("projects only a bounded v2 verifier count and never verifier values", () => {
    const userSelect =
      page.match(
        /const user = await prisma\.user\.findUnique\(\{[\s\S]*?\n  \}\);/u,
      )?.[0] ?? "";
    expect(userSelect).not.toContain("mfaBackupCodes");
    expect(page).toContain("COUNT(*)::integer");
    expect(page).toContain('AS "usableRecoveryCodeCount"');
    expect(page).toContain("count <= 100");
    expect(page).not.toContain("mfaBackupCodes: true");
  });

  it("routes both complete physician and admin states through rotation UI", () => {
    expect(page.match(/<MfaManagementPanel/gmu)).toHaveLength(1);
    expect(page).toContain("isAdminHost ||");
    expect(page).toContain("usableRecoveryCodeCount={usableRecoveryCodeCount}");
  });

  it("makes the active MFA workflow discoverable in both settings layouts", () => {
    expect(settingsPage.match(/<MfaSettingsCallout/gmu)).toHaveLength(2);
    expect(settingsPage).not.toContain("lands in the next batch");
    expect(settingsPage).not.toContain("mfaBackupCodes[]");
  });

  it("bounds narrow recovery dialogs and lets long codes safely reflow", () => {
    expect(managementPanel).toContain('width: "min(420px, 100%)"');
    expect(managementPanel).toContain('boxSizing: "border-box"');
    expect(managementPanel).toContain("padding: 16");
    expect(managementPanel).toContain(
      "repeat(auto-fit, minmax(min(220px, 100%), 1fr))",
    );
    expect(managementPanel).toContain('overflowWrap: "anywhere"');
  });
});
