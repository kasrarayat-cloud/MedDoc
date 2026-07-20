// ============================================================================
// parseNoteToTemplate under MOCK_AI_CALLS — fixture validation (full-qa F7).
// ----------------------------------------------------------------------------
// Unlike parse-note-to-template.test.ts (which vi.mocks modelClient to feed
// crafted outputs), this file uses the REAL modelClient.complete() and flips
// MOCK_AI_CALLS=true so the engine resolves through packages/ai/src/mock.ts.
// It proves the committed note-format fixtures (tm_template_parse +
// tm_template_phi_scan) are schema-valid and that the full
// parse→gate flow runs under MOCK — which it could not before (the mock threw
// on an unknown purpose), so upload→parse→review→activate was untestable.
// Also exercises the PHI-gate REJECT path via MOCK_TEMPLATE_PHI_FLAG.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { parseNoteToTemplate } from "../parse-note-to-template";

const ctx = {
  providerAuthority: {
    beforeEgress: async () => ({ actorUserId: "u1", practiceId: "p1" }),
    afterResponse: async () => undefined,
  },
};
// Narrow deterministic blank-outline grammar — no arbitrary prose or values.
const NOTE = [
  "SUBJECTIVE:",
  "[blank]",
  "OBJECTIVE:",
  "[blank]",
  "ASSESSMENT:",
  "[blank]",
  "PLAN:",
  "[blank]",
].join("\n");

const prevMock = process.env.MOCK_AI_CALLS;
const prevFlag = process.env.MOCK_TEMPLATE_PHI_FLAG;

beforeEach(() => {
  process.env.MOCK_AI_CALLS = "true";
  delete process.env.MOCK_TEMPLATE_PHI_FLAG;
});
afterEach(() => {
  if (prevMock === undefined) delete process.env.MOCK_AI_CALLS;
  else process.env.MOCK_AI_CALLS = prevMock;
  if (prevFlag === undefined) delete process.env.MOCK_TEMPLATE_PHI_FLAG;
  else process.env.MOCK_TEMPLATE_PHI_FLAG = prevFlag;
});

describe("parseNoteToTemplate — MOCK_AI_CALLS fixtures (F7)", () => {
  it("parses to a clean, activatable template (clean PHI scan is the default)", async () => {
    const r = await parseNoteToTemplate(NOTE, ctx);

    expect(r.rejected).toBe(false);
    if (!r.rejected) {
      expect(r.template.name).toBe("[MOCK] General Follow-up");
      expect(r.template.sections.map((s) => s.key)).toEqual([
        "subjective",
        "objective",
        "assessment",
        "plan",
      ]);
      // A parsed default is never always_include; the one generic default
      // (objective normal-exam line) survives as scaffold_confirm.
      expect(
        r.template.sections.every(
          (s) => s.defaultTextMode !== "always_include",
        ),
      ).toBe(true);
      const objective = r.template.sections.find((s) => s.key === "objective");
      expect(objective?.defaultText).toContain("well-appearing");
      expect(objective?.defaultTextMode).toBe("scaffold_confirm");
    }
  });

  it("rejects via the PHI gate when MOCK_TEMPLATE_PHI_FLAG=true (reject path testable)", async () => {
    process.env.MOCK_TEMPLATE_PHI_FLAG = "true";
    const r = await parseNoteToTemplate(NOTE, ctx);
    // The flagged scan sets anyUncertain → fail-safe gate rejects.
    expect(r.rejected).toBe(true);
  });
});
