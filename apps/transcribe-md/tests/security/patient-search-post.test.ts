// ============================================================================
// Patient search moved off URL (Security Audit P1-C, 2026-05-13)
// ----------------------------------------------------------------------------
// `GET /api/patients?search=<name>` put patient names in URLs (Caddy
// access logs, browser history, Referer headers, Sentry request URL).
// The picker now POSTs the search term to `/api/patients/search` and
// the new endpoint mirrors the GET handler's auth + scoping + audit
// posture.
//
// Tests verify the new endpoint's shape AND the picker's call-site.
// ============================================================================

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const REPO_ROOT = resolve(__dirname, "..", "..", "..", "..");
function readSrc(rel: string): string {
  return readFileSync(resolve(REPO_ROOT, rel), "utf-8");
}

describe("POST /api/patients/search — new endpoint (P1-C)", () => {
  const SRC = readSrc(
    "apps/transcribe-md/src/app/api/patients/search/route.ts",
  );

  it("exports POST handler", () => {
    expect(SRC).toMatch(/export\s+const\s+POST\s*=/);
  });

  it("requires a session before doing any work", () => {
    expect(SRC).toMatch(/getSession\(\)/);
    expect(SRC).toMatch(/apiError\(['"]unauthorized['"],\s*401\)/);
  });

  it("applies the PATIENT_READ rate limit", () => {
    expect(SRC).toMatch(/rateLimitOr429\(\s*RATE_LIMITS\.PATIENT_READ/);
  });

  it("binds the PHI query to the exact current actor and practice", () => {
    expect(SRC).toContain("currentClinicalPatientReadAuthoritySql");
    expect(SRC).toContain("userId: session.user.id");
    expect(SRC).toContain("practiceId: session.user.practiceId");
    expect(SRC).toContain("WHERE ${patientAuthority}");
  });

  it("uses Prisma parameterized $queryRaw (not unsafe raw)", () => {
    expect(SRC).toMatch(/\$queryRaw</);
    expect(SRC).not.toMatch(/\$queryRawUnsafe/);
    expect(SRC).not.toMatch(/\$executeRawUnsafe/);
  });

  it("emits VIEWED_PATIENT_LIST audit with metadata.source identifying the POST surface", () => {
    expect(SRC).toMatch(
      /logAudit\([\s\S]{0,300}?action:\s*['"]VIEWED_PATIENT_LIST['"][\s\S]{0,400}?source:\s*['"]api:POST\s*\/api\/patients\/search['"]/,
    );
  });

  it("audit metadata never includes the search term itself", () => {
    // Defensive: the metadata field should NOT contain `search`.
    // Catches a future "add searchTerm to audit row" edit that would
    // re-introduce the PHI leak.
    const auditBlock = SRC.match(/logAudit\(\s*\{[\s\S]+?\}\s*\)/)?.[0] ?? "";
    expect(auditBlock).not.toMatch(/searchTerm|search:\s*search\b/);
  });
});

describe("Patient picker — uses POST search endpoint (P1-C client side)", () => {
  const SRC = readSrc(
    "apps/transcribe-md/src/app/visits/new/patient-picker.tsx",
  );

  it("fetches /api/patients/search via POST with JSON body", () => {
    expect(SRC).toMatch(/fetch\(['"]\/api\/patients\/search['"]/);
    expect(SRC).toMatch(
      /\/api\/patients\/search[\s\S]{0,200}?method:\s*['"]POST['"][\s\S]{0,400}?JSON\.stringify\(\s*\{\s*search:\s*term\s*\}\s*\)/,
    );
  });

  it("no longer constructs a `/api/patients?search=` URL", () => {
    expect(SRC).not.toMatch(/\/api\/patients\?search=/);
  });
});
