// ============================================================================
// MFA enrollment revokes sibling sessions (Security Audit P1-J, 2026-05-13)
// ----------------------------------------------------------------------------
// Before this fix, flipping `mfaEnabled = true` left every existing
// session (other tabs / devices) untouched. "MFA-enabled" then no
// longer implied "this session passed an MFA challenge". The fix
// deletes every UserSession EXCEPT the current one inside the same
// transaction that flips the flag. A sessionless/legacy claim cannot
// establish current mutation authority and is rejected before account reads.
// ============================================================================

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const SRC = readFileSync(
  resolve(
    __dirname,
    "..",
    "..",
    "src",
    "app",
    "api",
    "mfa",
    "verify-enrollment",
    "route.ts",
  ),
  "utf-8",
);

describe("verify-enrollment — JWT rotation (P1-J)", () => {
  it("runs the staged-secret CAS + session deleteMany in one interactive transaction", () => {
    expect(SRC).toMatch(
      /prisma\.\$transaction\s*\(\s*async\s*\(tx[^)]*\)[\s\S]*?lockCurrentAccountMutationAuthority\(tx[\s\S]*?current\.user\.mfaSecret\s*!==\s*user\.mfaSecret[\s\S]*?tx\.user\.update[\s\S]*?tx\.userSession\.deleteMany/,
    );
  });

  it("requires the authorization-bound actor session before reading the account", () => {
    expect(SRC).toMatch(
      /resolveMfaRequestActor\(req\.headers\)[\s\S]*?currentSessionId\s*=\s*actor\.sessionId[\s\S]*?if\s*\(!currentSessionId\)[\s\S]*?apiError\("unauthorized",\s*401\)[\s\S]*?prisma\.user\.findUnique/,
    );
  });

  it("deleteMany uses NOT: { sessionToken: currentSessionId } when sessionId present", () => {
    // The KEEP-current branch deletes every session whose
    // sessionToken does NOT match the current — keeps the user
    // logged in on the tab they just enrolled from.
    expect(SRC).toMatch(
      /currentSessionId[\s\S]*?NOT:\s*\{\s*sessionToken:\s*currentSessionId\s*\}/,
    );
  });

  it("never substitutes an unbound or optional session in the authority check", () => {
    expect(SRC).toContain("sessionId: currentSessionId");
    expect(SRC).not.toContain("currentSessionId!");
    expect(SRC).not.toMatch(/sessionId:\s*actor\.sessionId/u);
  });

  it("audit metadata reports keptCurrentSession flag", () => {
    expect(SRC).toMatch(/keptCurrentSession:\s*true/);
  });
});
