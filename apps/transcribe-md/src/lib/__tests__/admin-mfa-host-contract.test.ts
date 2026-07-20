import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const REPO = path.resolve(__dirname, "../../../../..");
const read = (relative: string) =>
  readFileSync(path.join(REPO, relative), "utf8");

describe("admin-host MFA recovery contract", () => {
  it("allows only enrollment APIs at the admin edge", () => {
    const caddy = read("Caddyfile");
    const matcher = caddy.match(/@mfaApi path ([^\n]+)/u)?.[1] ?? "";
    expect(matcher).toContain("/api/mfa/enroll");
    expect(matcher).toContain("/api/mfa/verify-enrollment");
    expect(matcher).toContain("/api/mfa/recovery-codes/rotate");
    expect(matcher).not.toContain("/api/mfa/disable");
  });

  it("isolates the admin-host page from clinician AppFrame navigation", () => {
    const page = read(
      "apps/transcribe-md/src/app/settings/security/mfa/page.tsx",
    );
    const isolatedReturn = page.indexOf("if (isAdminHost)");
    const clinicianFrameReturn = page.lastIndexOf("<AppFrame>");
    expect(isolatedReturn).toBeGreaterThan(-1);
    expect(clinicianFrameReturn).toBeGreaterThan(isolatedReturn);
    expect(page).toContain('href="/admin/template-twin-release"');
    expect(page).toMatch(
      /isAdminHost \? ["']\/admin\/template-twin-release["'] : ["']\/settings["']/u,
    );
    expect(page).not.toContain('href="/admin"');
    expect(page).not.toMatch(/isAdminHost\s*\?\s*["']\/admin["']/u);
    const enrollmentPanel = read(
      "apps/transcribe-md/src/app/settings/security/mfa/mfa-enrollment-panel.tsx",
    );
    expect(enrollmentPanel).toContain(
      'completionHref?: "/admin/template-twin-release" | "/settings"',
    );
    expect(enrollmentPanel).toContain("router.push(completionHref)");
    expect(page).toContain("isAdminHost || user.products.includes");
    expect(page).toContain("mfaSecret: true");
    expect(page).toContain("hasInconsistentMfaEnrollment");
    expect(page).toContain("MFA configuration requires controlled repair");
  });

  it("uses the strict host validator for both post-login paths", () => {
    for (const relative of [
      "apps/transcribe-md/src/app/login/page.tsx",
      "apps/transcribe-md/src/actions/auth.ts",
    ]) {
      const source = read(relative);
      expect(source).toContain("isAdminRequestHost(");
      expect(source).not.toContain("h.get('x-forwarded-host')");
      expect(source).not.toContain("startsWith('admin.')");
    }
  });
});
