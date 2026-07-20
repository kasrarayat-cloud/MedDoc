// ============================================================================
// Suggestions-lane server actions (hybrid anchored generation, 2026-06-11).
// prisma + auth + audit mocked; the append/filter logic is REAL. Pins the
// load-bearing invariants:
//   - adopt APPENDS the claim text VERBATIM under its section heading (else
//     at the end of the note), filters the claim out of suggestedClaims, and
//     bumps soapVersion in ONE version-gated update (optimistic concurrency)
//   - the audit metadata is PHI-SAFE: key-set EXACTLY {reason, remaining,
//     section} — never the claim text
//   - dismiss filters + audits but NEVER touches soapFinal / soapVersion
//   - emptying the lane writes SQL NULL (Prisma.DbNull), not []
//   - bad index / malformed jsonb / SIGNED / not-owned / version conflict
//     → { ok:false } with NO write (and, where applicable, NO audit row)
//
// E/M visible-confirm (2026-06-12, prod smoke #311) — computeEmScore is
// MOCKED (no Redis, no LLM); the delta/merge/audit logic is REAL. Pins:
//   - adopt that changes the computed level records {from, to, cause, at}
//     in the SAME atomic update + audits EM_LEVEL_CHANGED with metadata
//     key-set EXACTLY {cause, from, to}
//   - adopt that does NOT change the level touches neither the column nor
//     the EM_LEVEL_CHANGED audit
//   - merge keeps the doctor's baseline `from`; a change back to baseline
//     cancels to SQL NULL
//   - dismiss never changes the note → never scores, never records
// ============================================================================

import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findUnique: vi.fn(),
  update: vi.fn(),
  updateMany: vi.fn(),
  fillUpdateMany: vi.fn(),
  transaction: vi.fn(),
  requireSession: vi.fn(),
  logAudit: vi.fn(),
  computeEmScore: vi.fn(),
  pinStagingMutation: vi.fn(),
  lockOrdinary: vi.fn(),
}));

vi.mock("@meddoc/db", () => {
  const transcribeVisit = {
    findUnique: mocks.findUnique,
    update: mocks.update,
    updateMany: mocks.updateMany,
  };
  const prisma = {
    transcribeVisit,
    $transaction: mocks.transaction,
  };
  return { default: prisma, prisma };
});
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("@/lib/audit", () => ({ logAudit: mocks.logAudit }));
vi.mock("@/lib/template-twin/staging-qa-mutation", () => ({
  pinTemplateTwinStagingQaMutation: mocks.pinStagingMutation,
}));
vi.mock(
  "@/lib/template-twin/visit-mutation-authority",
  async (importOriginal) => ({
    ...(await importOriginal<
      typeof import("@/lib/template-twin/visit-mutation-authority")
    >()),
    lockAndAssertOrdinaryClinicalMutation: mocks.lockOrdinary,
  }),
);
vi.mock("next/cache", () => ({ revalidatePath: vi.fn() }));
// E/M visible-confirm — mock the scoring engine (the real one would pull
// the Redis client + Anthropic SDK into the test graph and make network
// calls). Tests steer the computed code per-SOAP-body via
// mockImplementation; the default (same code for any text) means "no
// level change".
vi.mock("@/lib/em-coding/score", () => ({
  computeEmScore: mocks.computeEmScore,
}));

import { Prisma, TranscribeVisitStatus } from "@prisma/client";
import { currentClinicalVisitActorWhere } from "@/lib/clinical-visit-authority";
import { TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE } from "@/lib/template-twin/durable-visit-exclusion";
import { TemplateTwinClinicalMutationAuthorizationError } from "@/lib/template-twin/visit-mutation-authority";

import {
  adoptSuggestionAction,
  dismissSuggestionAction,
} from "../suggestion-actions";

const DOCTOR = "doc1";
const VISIT = "visit-1";

const SOAP = [
  "## Subjective",
  "Reports right elbow pain for two weeks.",
  "",
  "## Objective",
  "Swelling over the olecranon.",
  "",
  "## Plan",
  "Rest and NSAIDs.",
].join("\n");

const CLAIMS = [
  {
    text: "No prior diagnosis of migraines.",
    reason: "not_entailed",
    section: "Subjective",
    anchor: "had migraines in the past? No.",
  },
  {
    text: "Ice packs recommended twice daily.",
    reason: "no_anchor",
    section: "Plan",
    anchor: "no anchor",
  },
];

/** Text of CLAIMS[i] — the content-identity check both actions now require. */
const claimsAt = (i: number) => CLAIMS[i].text;

function visitRow(over: Record<string, unknown> = {}) {
  return {
    id: VISIT,
    userId: DOCTOR,
    patientId: "patient-1",
    noteTemplateId: "ordinary-template-1",
    noteTemplateVersion: 1,
    status: TranscribeVisitStatus.READY,
    signedAt: null,
    deletedAt: null,
    archivedAt: null,
    updatedAt: new Date("2026-07-20T00:00:00.000Z"),
    soapFinal: SOAP,
    soapVersion: 3,
    suggestedClaims: CLAIMS,
    patient: { id: "patient-1", practiceId: "p1", externalId: null },
    templateTwinSyntheticQaRun: null,
    noteTemplate: {
      id: "ordinary-template-1",
      doctorId: DOCTOR,
      version: 1,
      templateKind: "structured",
      templateTwinCompiledVersion: null,
    },
    templateTwinFill: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: DOCTOR, practiceId: "p1", email: "doc@test.dev" },
  });
  mocks.findUnique.mockResolvedValue(visitRow());
  mocks.updateMany.mockResolvedValue({ count: 1 });
  mocks.fillUpdateMany.mockResolvedValue({ count: 1 });
  mocks.transaction.mockImplementation(
    async (callback: (tx: unknown) => Promise<unknown>) =>
      callback({
        transcribeVisit: {
          findUnique: mocks.findUnique,
          update: mocks.update,
          updateMany: mocks.updateMany,
        },
        templateTwinFillManifest: { updateMany: mocks.fillUpdateMany },
      }),
  );
  mocks.update.mockResolvedValue({ id: VISIT });
  mocks.pinStagingMutation.mockResolvedValue(null);
  mocks.lockOrdinary.mockResolvedValue(undefined);
  // Default: every SOAP body scores the same code → no E/M level change.
  mocks.computeEmScore.mockResolvedValue({ code: "99213" });
});

/** Steer the mocked engine: any SOAP containing `marker` scores `withCode`,
 *  everything else scores `baseCode`. The adopted claim's text is the
 *  natural marker — only the AFTER body contains it. */
function scoreByMarker(marker: string, baseCode: string, withCode: string) {
  mocks.computeEmScore.mockImplementation(async (soap: string) => ({
    code: soap.includes(marker) ? withCode : baseCode,
  }));
}

describe("adoptSuggestionAction — append + filter + version bump", () => {
  it("returns no suggestion/clinical snapshot when durable lineage appears after admission", async () => {
    mocks.findUnique
      .mockResolvedValueOnce(visitRow())
      .mockResolvedValueOnce(null);

    await expect(
      adoptSuggestionAction(VISIT, 0, claimsAt(0)),
    ).resolves.toMatchObject({ ok: false });
    expect(mocks.findUnique.mock.calls[1]?.[0].where).toEqual(
      expect.objectContaining({
        ...currentClinicalVisitActorWhere(DOCTOR),
        ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
      }),
    );
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("appends the claim text verbatim INSIDE its section heading block", async () => {
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(r.soapVersion).toBe(4);

    const args = mocks.updateMany.mock.calls[0][0];
    // ONE atomic update, gated on the soapVersion read in this request.
    // status:READY in the WHERE (auditor WARN-1): an adopt whose LLM-scoring
    // window straddles the READY→SIGNED transition must MISS (count=0),
    // never mutate a signed row or deposit an unacknowledgeable record.
    expect(args.where).toEqual({
      id: VISIT,
      userId: DOCTOR,
      soapVersion: 3,
      status: TranscribeVisitStatus.READY,
      deletedAt: null,
      archivedAt: null,
      signedAt: null,
      updatedAt: new Date("2026-07-20T00:00:00.000Z"),
      soapFinal: SOAP,
      suggestedClaims: { equals: CLAIMS },
      ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
    });
    expect(args.data.soapVersion).toEqual({ increment: 1 });

    const newSoap: string = args.data.soapFinal;
    expect(r.soapFinal).toBe(newSoap);
    // Verbatim — and NO trailing "[adopted from AI suggestion]" label;
    // the audit row is the record.
    expect(newSoap).toContain("No prior diagnosis of migraines.");
    expect(newSoap).not.toMatch(/adopted from/i);
    // Inserted under ## Subjective, before ## Objective.
    const claimAt = newSoap.indexOf("No prior diagnosis of migraines.");
    expect(claimAt).toBeGreaterThan(newSoap.indexOf("## Subjective"));
    expect(claimAt).toBeLessThan(newSoap.indexOf("## Objective"));

    // The adopted claim is filtered OUT of the persisted array.
    expect(args.data.suggestedClaims).toEqual([CLAIMS[1]]);
    expect(r.suggestedClaims).toEqual([CLAIMS[1]]);
  });

  it("appends at the END of the note when the section heading is absent", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        suggestedClaims: [
          {
            text: "Entire-note fallback claim.",
            reason: "verifier_failed",
            section: "(entire note)",
            anchor: "no anchor",
          },
        ],
      }),
    );
    const r = await adoptSuggestionAction(
      VISIT,
      0,
      "Entire-note fallback claim.",
    );
    expect(r.ok).toBe(true);
    const newSoap: string = mocks.updateMany.mock.calls[0][0].data.soapFinal;
    expect(newSoap.trimEnd().endsWith("Entire-note fallback claim.")).toBe(
      true,
    );
  });

  it("adopting the LAST claim writes SQL NULL (Prisma.DbNull), not []", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ suggestedClaims: [CLAIMS[0]] }),
    );
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(mocks.updateMany.mock.calls[0][0].data.suggestedClaims).toBe(
      Prisma.DbNull,
    );
    expect(r.suggestedClaims).toBeNull();
  });

  it("audits SUGGESTION_ADOPTED with PHI-safe metadata — key-set EXACTLY {reason, remaining, section}", async () => {
    await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    const call = mocks.logAudit.mock.calls[0][0];
    expect(call.action).toBe("SUGGESTION_ADOPTED");
    expect(call.targetId).toBe(VISIT);
    expect(Object.keys(call.metadata).sort()).toEqual([
      "reason",
      "remaining",
      "section",
    ]);
    expect(call.metadata).toEqual({
      section: "Subjective",
      reason: "not_entailed",
      remaining: 1,
    });
    // Belt: the claim text must never reach the audit row in any field.
    expect(JSON.stringify(call)).not.toContain(
      "No prior diagnosis of migraines",
    );
  });

  it("bad index → { ok:false }, no write, no audit", async () => {
    for (const idx of [99, -1, 1.5]) {
      const r = await adoptSuggestionAction(VISIT, idx, "whatever");
      expect(r.ok).toBe(false);
    }
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("malformed suggestedClaims jsonb (strict parse) → { ok:false }, no write", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        suggestedClaims: [
          { reason: "no_anchor", section: "Plan", anchor: "no anchor" },
        ],
      }),
    );
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("SIGNED visit → { ok:false }, no write (read-only after signing)", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ status: TranscribeVisitStatus.SIGNED }),
    );
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("not-owned visit → { ok:false }, no write", async () => {
    mocks.findUnique.mockResolvedValue(visitRow({ userId: "someone-else" }));
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });

  it("version conflict (updateMany count=0) → { ok:false }, no audit", async () => {
    mocks.updateMany.mockResolvedValue({ count: 0 });
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe("dismissSuggestionAction — filter only, never the note", () => {
  it("filters the claim, audits SUGGESTION_DISMISSED, and NEVER touches soapFinal/soapVersion", async () => {
    const r = await dismissSuggestionAction(VISIT, 1, claimsAt(1));
    expect(r.ok).toBe(true);
    expect(r.suggestedClaims).toEqual([CLAIMS[0]]);

    const args = mocks.updateMany.mock.calls[0][0];
    expect(args.where).toEqual({
      id: VISIT,
      userId: DOCTOR,
      status: TranscribeVisitStatus.READY,
      deletedAt: null,
      archivedAt: null,
      signedAt: null,
      updatedAt: new Date("2026-07-20T00:00:00.000Z"),
      soapFinal: SOAP,
      soapVersion: 3,
      suggestedClaims: { equals: CLAIMS },
      ...TEMPLATE_TWIN_DURABLE_VISIT_EXCLUSION_WHERE,
    });
    expect(args.data.suggestedClaims).toEqual([CLAIMS[0]]);
    expect("soapFinal" in args.data).toBe(false);
    expect("soapVersion" in args.data).toBe(false);

    const call = mocks.logAudit.mock.calls[0][0];
    expect(call.action).toBe("SUGGESTION_DISMISSED");
    expect(Object.keys(call.metadata).sort()).toEqual([
      "reason",
      "remaining",
      "section",
    ]);
    expect(call.metadata).toEqual({
      section: "Plan",
      reason: "no_anchor",
      remaining: 1,
    });
    expect(JSON.stringify(call)).not.toContain("Ice packs recommended");
  });

  it("dismissing the LAST claim writes SQL NULL (Prisma.DbNull)", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ suggestedClaims: [CLAIMS[1]] }),
    );
    const r = await dismissSuggestionAction(VISIT, 0, claimsAt(1));
    expect(r.ok).toBe(true);
    expect(mocks.updateMany.mock.calls[0][0].data.suggestedClaims).toBe(
      Prisma.DbNull,
    );
    expect(r.suggestedClaims).toBeNull();
  });

  it("bad index → { ok:false }, no write, no audit", async () => {
    const r = await dismissSuggestionAction(VISIT, 7, "whatever");
    expect(r.ok).toBe(false);
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("SIGNED visit → { ok:false }, no write", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ status: TranscribeVisitStatus.SIGNED }),
    );
    const r = await dismissSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.update).not.toHaveBeenCalled();
  });
});

describe("Template Twin staging provider-isolation gate", () => {
  const stagingRun = {
    id: "synthetic-run-1",
    practiceId: "p1",
    doctorId: DOCTOR,
    fixtureVersion: "template-twin-staging-safe-docx/1.0.0",
    attempt: 2,
    pinnedGlobalRolloutGeneration: BigInt(4),
    pinnedPracticeRolloutGeneration: BigInt(7),
  };
  const stagingClaim = {
    runId: stagingRun.id,
    attempt: stagingRun.attempt,
    visitId: VISIT,
    userId: DOCTOR,
    practiceId: "p1",
    rolloutToken: {
      practiceId: "p1",
      globalGeneration: BigInt(4),
      practiceGeneration: BigInt(7),
    },
  };

  beforeEach(() => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ templateTwinSyntheticQaRun: stagingRun }),
    );
    mocks.pinStagingMutation.mockResolvedValue(stagingClaim);
  });

  it.each(["adopt", "dismiss"] as const)(
    "blocks marked staging %s before scoring, clinical writes, or audit writes",
    async (operation) => {
      const result =
        operation === "adopt"
          ? await adoptSuggestionAction(VISIT, 0, claimsAt(0))
          : await dismissSuggestionAction(VISIT, 0, claimsAt(0));

      expect(result).toEqual({ ok: false, error: "Visit not found." });
      expect(mocks.pinStagingMutation).not.toHaveBeenCalled();
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
      expect(mocks.updateMany).not.toHaveBeenCalled();
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.logAudit).not.toHaveBeenCalled();
    },
  );

  it.each([
    "TEMPLATE_TWIN_ROLLOUT_DISABLED",
    "TEMPLATE_TWIN_STAGING_QA_ROLLOUT_STALE",
    "TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE",
  ])(
    "a rejected %s admission cannot reach a provider or mutate",
    async (reasonCode) => {
      mocks.pinStagingMutation.mockRejectedValueOnce(new Error(reasonCode));

      const result = await adoptSuggestionAction(VISIT, 0, claimsAt(0));

      expect(result).toEqual({ ok: false, error: "Visit not found." });
      expect(mocks.computeEmScore).not.toHaveBeenCalled();
      expect(mocks.updateMany).not.toHaveBeenCalled();
      expect(mocks.transaction).not.toHaveBeenCalled();
      expect(mocks.logAudit).not.toHaveBeenCalled();
    },
  );
});

describe("durable Template Twin suggestion-action boundary", () => {
  it.each([
    [
      "live Twin kind",
      { noteTemplate: { templateKind: "template_twin_docx" } },
    ],
    [
      "fill after template mutation",
      {
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: { id: "fill-1" },
      },
    ],
    [
      "fill after template detach",
      { noteTemplate: null, templateTwinFill: { id: "fill-1" } },
    ],
    [
      "pre-cert voice admission",
      { templateTwinSyntheticQaAdmission: { id: "admission-1" } },
    ],
    [
      "detached provider execution",
      { templateTwinProviderExecutions: [{ id: "execution-1" }] },
    ],
    [
      "orphaned reserved synthetic patient",
      { patient: { externalId: "SYNTHETIC-QA-ONLY" } },
    ],
  ] as const)(
    "blocks adopt and dismiss for %s before model/cache or mutation",
    async (_label, provenance) => {
      for (const operation of ["adopt", "dismiss"] as const) {
        vi.clearAllMocks();
        mocks.requireSession.mockResolvedValue({
          user: { id: DOCTOR, practiceId: "p1", email: "doc@test.dev" },
        });
        mocks.findUnique.mockResolvedValue(visitRow(provenance));
        mocks.pinStagingMutation.mockResolvedValue(null);

        const result =
          operation === "adopt"
            ? await adoptSuggestionAction(VISIT, 0, claimsAt(0))
            : await dismissSuggestionAction(VISIT, 0, claimsAt(0));

        expect(result).toEqual({ ok: false, error: "Visit not found." });
        expect(mocks.computeEmScore).not.toHaveBeenCalled();
        expect(mocks.updateMany).not.toHaveBeenCalled();
        expect(mocks.update).not.toHaveBeenCalled();
        expect(mocks.transaction).not.toHaveBeenCalled();
        expect(mocks.fillUpdateMany).not.toHaveBeenCalled();
        expect(mocks.logAudit).not.toHaveBeenCalled();
      }
    },
  );
});

describe("ordinary suggestion final-write race fence", () => {
  it("blocks adopt before provider egress when ordinary provenance changes", async () => {
    mocks.lockOrdinary.mockRejectedValueOnce(
      new TemplateTwinClinicalMutationAuthorizationError(
        "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
      ),
    );

    const result = await adoptSuggestionAction(VISIT, 0, claimsAt(0));

    expect(result.ok).toBe(false);
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("discards an adopt provider result when provenance changes before final commit", async () => {
    mocks.lockOrdinary
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(
        new TemplateTwinClinicalMutationAuthorizationError(
          "TEMPLATE_TWIN_MUTATION_TARGET_CHANGED",
        ),
      );

    const result = await adoptSuggestionAction(VISIT, 0, claimsAt(0));

    expect(result.ok).toBe(false);
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(2);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it.each([
    "durable relation or Twin template appeared",
    "owner changed",
    "visit was archived or deleted",
    "visit was signed",
    "SOAP or version changed",
    "suggestion lane changed",
  ])("adopt discards its provider result when %s", async () => {
    mocks.updateMany.mockResolvedValueOnce({ count: 0 });

    const result = await adoptSuggestionAction(VISIT, 0, claimsAt(0));

    expect(result.ok).toBe(false);
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(2);
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it.each([
    "durable relation or Twin template appeared",
    "owner changed",
    "visit was archived or deleted",
    "visit was signed",
    "SOAP or version changed",
    "suggestion lane changed",
  ])("dismiss fails closed when %s", async () => {
    mocks.updateMany.mockResolvedValueOnce({ count: 0 });

    const result = await dismissSuggestionAction(VISIT, 0, claimsAt(0));

    expect(result.ok).toBe(false);
    expect(mocks.computeEmScore).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });
});

describe("cross-tab index drift — content-identity check", () => {
  // The DB lane was re-indexed by another tab (e.g. its claim 0 was
  // dismissed); this tab still renders the OLD array and acts on "index 0"
  // expecting the old claim's text. Both actions must refuse — adopting or
  // dismissing the WRONG claim is the failure mode (auditor WARN-1).
  it("adopt with stale text at the index → { ok:false }, no write, no audit", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ suggestedClaims: [CLAIMS[1]] }),
    );
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/another tab/i);
    expect(mocks.updateMany).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("dismiss with stale text at the index → { ok:false }, no write, no audit", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({ suggestedClaims: [CLAIMS[1]] }),
    );
    const r = await dismissSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/another tab/i);
    expect(mocks.update).not.toHaveBeenCalled();
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("empty expectedText fails input validation", async () => {
    const r = await adoptSuggestionAction(VISIT, 0, "");
    expect(r.ok).toBe(false);
    expect(mocks.updateMany).not.toHaveBeenCalled();
  });
});

// ─── E/M visible-confirm (prod smoke #311) ──────────────────────────────────

describe("adopt — E/M level delta recording (visible-confirm, never silent)", () => {
  it("adopt that CHANGES the level records {from, to, cause, at} in the SAME atomic update + audits EM_LEVEL_CHANGED with key-set EXACTLY {cause, from, to}", async () => {
    scoreByMarker(CLAIMS[0].text, "99213", "99214");

    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(r.emPendingChange).toEqual({ from: "99213", to: "99214" });

    // Scored BEFORE vs AFTER with the same engine inputs as /em-score.
    expect(mocks.computeEmScore).toHaveBeenCalledTimes(2);
    const [beforeCall, afterCall] = mocks.computeEmScore.mock.calls;
    expect(beforeCall[0]).toBe(SOAP);
    expect(afterCall[0]).toContain(CLAIMS[0].text);
    expect(beforeCall[1]).toMatchObject({
      practiceId: "p1",
      visitId: VISIT,
      userId: DOCTOR,
    });

    // ONE update carries note + lane + pending-change together — no
    // window where the note changed but the change isn't recorded.
    expect(mocks.updateMany).toHaveBeenCalledTimes(1);
    const args = mocks.updateMany.mock.calls[0][0];
    expect(args.data.emPendingChange).toEqual({
      from: "99213",
      to: "99214",
      cause: "suggestion_adopted",
      at: expect.any(String),
    });

    const emAudit = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === "EM_LEVEL_CHANGED");
    expect(emAudit).toBeDefined();
    expect(emAudit.targetId).toBe(VISIT);
    // Metadata key-set EXACTLY {cause, from, to} — PHI-free by shape.
    expect(Object.keys(emAudit.metadata).sort()).toEqual([
      "cause",
      "from",
      "to",
    ]);
    expect(emAudit.metadata).toEqual({
      from: "99213",
      to: "99214",
      cause: "suggestion_adopted",
    });
    // Belt: the claim text never reaches the audit row in any field.
    expect(JSON.stringify(emAudit)).not.toContain(CLAIMS[0].text);
  });

  it("adopt that does NOT change the level records NOTHING (column untouched, no EM_LEVEL_CHANGED audit)", async () => {
    // Default mock: same code for any body.
    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(r.emPendingChange).toBeNull();

    const args = mocks.updateMany.mock.calls[0][0];
    expect("emPendingChange" in args.data).toBe(false);

    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit.mock.calls[0][0].action).toBe("SUGGESTION_ADOPTED");
  });

  it("second change MERGES against the doctor's baseline: persisted `from` stays the original, audit row carries this leg's own delta", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        emPendingChange: {
          from: "99212",
          to: "99213",
          cause: "suggestion_adopted",
          at: "2026-06-12T00:00:00.000Z",
        },
      }),
    );
    scoreByMarker(CLAIMS[0].text, "99213", "99214");

    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(r.emPendingChange).toEqual({ from: "99212", to: "99214" });

    const args = mocks.updateMany.mock.calls[0][0];
    expect(args.data.emPendingChange).toMatchObject({
      from: "99212",
      to: "99214",
      cause: "suggestion_adopted",
    });

    const emAudit = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === "EM_LEVEL_CHANGED");
    expect(emAudit.metadata).toEqual({
      from: "99213",
      to: "99214",
      cause: "suggestion_adopted",
    });
  });

  it("change BACK to the baseline cancels the record (SQL NULL — nothing left to confirm)", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        emPendingChange: {
          from: "99214",
          to: "99213",
          cause: "suggestion_adopted",
          at: "2026-06-12T00:00:00.000Z",
        },
      }),
    );
    scoreByMarker(CLAIMS[0].text, "99213", "99214");

    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(r.emPendingChange).toBeNull();
    expect(mocks.updateMany.mock.calls[0][0].data.emPendingChange).toBe(
      Prisma.DbNull,
    );
    // The leg itself is still audited — the trail shows both moves.
    const emAudit = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === "EM_LEVEL_CHANGED");
    expect(emAudit.metadata).toEqual({
      from: "99213",
      to: "99214",
      cause: "suggestion_adopted",
    });
  });

  it("an already-ACKNOWLEDGED record is not a baseline — a fresh change starts a fresh record", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        emPendingChange: {
          from: "99211",
          to: "99213",
          cause: "suggestion_adopted",
          at: "2026-06-11T00:00:00.000Z",
          acknowledgedAt: "2026-06-11T01:00:00.000Z",
        },
      }),
    );
    scoreByMarker(CLAIMS[0].text, "99213", "99214");

    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(true);
    expect(
      mocks.updateMany.mock.calls[0][0].data.emPendingChange,
    ).toMatchObject({ from: "99213", to: "99214" });
  });

  it("version conflict (count=0) after a level-changing score → { ok:false }, NO audit rows at all", async () => {
    scoreByMarker(CLAIMS[0].text, "99213", "99214");
    mocks.updateMany.mockResolvedValue({ count: 0 });

    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    expect(r.ok).toBe(false);
    expect(mocks.logAudit).not.toHaveBeenCalled();
  });

  it("scoring engine failure → FAIL TOWARD CONFIRM: the note write lands AND an indeterminate pending change forces sign-time confirmation (never a silent flip)", async () => {
    mocks.computeEmScore.mockRejectedValue(new Error("redis down"));

    const r = await adoptSuggestionAction(VISIT, 0, claimsAt(0));
    // The adoption succeeds (the note change must not be lost) ...
    expect(r.ok).toBe(true);
    expect(mocks.updateMany).toHaveBeenCalled();
    // ... but an indeterminate delta is recorded so the sign gate fires.
    expect(r.emPendingChange).toEqual({ from: "unknown", to: "review" });
    const written = mocks.updateMany.mock.calls[0][0].data.emPendingChange;
    expect(written.from).toBe("unknown");
    expect(written.to).toBe("review");
    // EM_LEVEL_CHANGED still audits the (indeterminate) change, PHI-free.
    const emRow = mocks.logAudit.mock.calls
      .map((c) => c[0])
      .find((c) => c.action === "EM_LEVEL_CHANGED");
    expect(emRow).toBeTruthy();
    expect(Object.keys(emRow.metadata).sort()).toEqual(["cause", "from", "to"]);
  });
});

describe("dismiss — E/M level delta (never changes the note → never records)", () => {
  it("dismiss never scores, never touches emPendingChange, never audits EM_LEVEL_CHANGED", async () => {
    const r = await dismissSuggestionAction(VISIT, 1, claimsAt(1));
    expect(r.ok).toBe(true);
    expect(r.emPendingChange).toBeNull();

    // Identical before/after note short-circuits ahead of the engine.
    expect(mocks.computeEmScore).not.toHaveBeenCalled();

    const args = mocks.updateMany.mock.calls[0][0];
    expect("emPendingChange" in args.data).toBe(false);

    expect(mocks.logAudit).toHaveBeenCalledTimes(1);
    expect(mocks.logAudit.mock.calls[0][0].action).toBe("SUGGESTION_DISMISSED");
  });

  it("dismiss surfaces (but does not alter) an existing unacknowledged change in its result", async () => {
    mocks.findUnique.mockResolvedValue(
      visitRow({
        suggestedClaims: CLAIMS,
        emPendingChange: {
          from: "99213",
          to: "99214",
          cause: "suggestion_adopted",
          at: "2026-06-12T00:00:00.000Z",
        },
      }),
    );

    const r = await dismissSuggestionAction(VISIT, 1, claimsAt(1));
    expect(r.ok).toBe(true);
    expect(r.emPendingChange).toEqual({ from: "99213", to: "99214" });
    expect("emPendingChange" in mocks.updateMany.mock.calls[0][0].data).toBe(
      false,
    );
  });
});
