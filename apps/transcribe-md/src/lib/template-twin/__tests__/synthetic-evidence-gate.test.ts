import {
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
  type ModelClient,
} from "@meddoc/ai";
import { describe, expect, it, vi } from "vitest";

vi.mock("../provider-ownership", () => ({
  getTemplateTwinProviderOwnershipContext: vi.fn(() => null),
  requireTemplateTwinProviderOwnershipContext: vi.fn(),
  resolveTemplateTwinProviderLogicalAttempt: vi.fn(async () => 1),
  runWithTemplateTwinProviderOwnershipContext: vi.fn(
    async (_context: unknown, callback: () => Promise<unknown>) => callback(),
  ),
  runTemplateTwinOwnedModelComplete: vi.fn(
    async (input: {
      args: unknown;
      client: { complete(args: unknown): Promise<unknown> };
    }) => input.client.complete(input.args),
  ),
  buildTemplateTwinProviderOwnershipReceipt: vi.fn(() => ({
    evidence: {},
    sha256: "c".repeat(64),
  })),
}));

import {
  assertTemplateTwinSyntheticEvidencePhiFree,
  assertTemplateTwinStagingQaEvidencePhiFree,
  TemplateTwinSyntheticEvidenceRejectedError,
  TemplateTwinSyntheticEvidenceScanUnavailableError,
} from "../synthetic-evidence-gate";

const BASE = {
  practiceId: "practice-synthetic-gate",
  userId: "doctor-synthetic-gate",
  rolloutToken: {
    practiceId: "practice-synthetic-gate",
    globalGeneration: BigInt(1),
    practiceGeneration: BigInt(1),
  },
};

function client(result: unknown) {
  const complete = vi.fn().mockResolvedValue(result);
  return {
    complete,
    value: { complete } as unknown as Pick<ModelClient, "complete">,
  };
}

describe("Template Twin synthetic evidence privacy gate", () => {
  it("admits the exact reviewed staging corpus while masking only its reserved future date from the generic scan", async () => {
    const safe = client({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinStagingQaEvidencePhiFree({
        ...BASE,
        encounterText: TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
        client: safe.value,
      }),
    ).resolves.toBeUndefined();

    const call = safe.complete.mock.calls[0]?.[0] as { user?: string };
    expect(call.user).toContain("[reserved synthetic date]");
    expect(call.user).not.toContain("2099-07-16");
  });

  it.each([
    "Synthetic patient Jordan Smith. Chief concern is synthetic wrist discomfort.",
    `${TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT} Extra synthetic statement.`,
    TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT.replace("2099-07-16", "2026-07-16"),
  ])(
    "rejects non-reviewed staging evidence before provider egress",
    async (encounterText) => {
      const safe = client({
        directIdentifierClasses: [],
        appearsExplicitlySynthetic: true,
        anyUncertain: false,
      });

      await expect(
        assertTemplateTwinStagingQaEvidencePhiFree({
          ...BASE,
          encounterText,
          client: safe.value,
        }),
      ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
      expect(safe.complete).not.toHaveBeenCalled();
    },
  );

  it("accepts explicitly synthetic identifier-free evidence after the independent scan", async () => {
    const safe = client({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          "Synthetic test only. The fictional patient reports mock wrist discomfort.",
        client: safe.value,
      }),
    ).resolves.toBeUndefined();

    expect(safe.complete).toHaveBeenCalledWith(
      expect.objectContaining({
        purpose: "tm_template_synthetic_phi_scan",
        provider: "anthropic",
        visitId: null,
      }),
    );
  });

  it("rejects text that is not explicitly marked as synthetic before model egress", async () => {
    const safe = client({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText: "The patient reports wrist discomfort and uses a brace.",
        client: safe.value,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
    expect(safe.complete).not.toHaveBeenCalled();
  });

  it("rejects structured identifiers deterministically before model egress", async () => {
    const safe = client({
      directIdentifierClasses: [],
      appearsExplicitlySynthetic: true,
      anyUncertain: false,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          "Synthetic test only. Contact example.person@synthetic.test about wrist discomfort.",
        client: safe.value,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
    expect(safe.complete).not.toHaveBeenCalled();
  });

  it("fails closed when the independent scan flags identifiers or uncertainty", async () => {
    const unsafe = client({
      directIdentifierClasses: ["patient-name"],
      appearsExplicitlySynthetic: true,
      anyUncertain: true,
    });

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          "Synthetic example case with wrist discomfort and no contact information.",
        client: unsafe.value,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceRejectedError);
  });

  it("fails closed when the privacy provider is unavailable", async () => {
    const complete = vi.fn().mockRejectedValue(new Error("synthetic outage"));

    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        ...BASE,
        encounterText:
          "Synthetic example case with wrist discomfort and no identifiers.",
        client: {
          complete,
        } as unknown as Pick<ModelClient, "complete">,
      }),
    ).rejects.toBeInstanceOf(TemplateTwinSyntheticEvidenceScanUnavailableError);
  });
});
