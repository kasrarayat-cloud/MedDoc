import { describe, expect, it } from "vitest";

import { vi } from "vitest";

import {
  hasTemplateTwinProvenance,
  runProviderBackedEmForOrdinaryVisit,
} from "../template-twin-boundary";

describe("durable Template Twin E/M provenance", () => {
  const ordinaryRelations = {
    patient: { externalId: null },
    templateTwinFill: null,
    templateTwinSyntheticQaRun: null,
    templateTwinSyntheticQaAdmission: null,
    templateTwinProviderExecutions: [],
  } as const;

  it.each([
    [
      "reserved synthetic patient-only",
      {
        ...ordinaryRelations,
        patient: { externalId: "SYNTHETIC-QA-ONLY" },
        noteTemplate: null,
      },
    ],
    [
      "current Twin kind",
      {
        ...ordinaryRelations,
        noteTemplate: {
          templateKind: "template_twin_docx",
          templateTwinCompiledVersion: { id: "compiled-1" },
        },
      },
    ],
    [
      "compiled lineage after mutable kind drift",
      {
        ...ordinaryRelations,
        noteTemplate: {
          templateKind: "structured",
          templateTwinCompiledVersion: { id: "compiled-1" },
        },
      },
    ],
    [
      "fill-only with structured template",
      {
        ...ordinaryRelations,
        noteTemplate: {
          templateKind: "structured",
          templateTwinCompiledVersion: null,
        },
        templateTwinFill: { id: "fill-1" },
      },
    ],
    [
      "fill-only with detached template",
      {
        ...ordinaryRelations,
        noteTemplate: null,
        templateTwinFill: { id: "fill-1" },
      },
    ],
    [
      "provider-execution-only with detached template",
      {
        ...ordinaryRelations,
        noteTemplate: null,
        templateTwinProviderExecutions: [{ id: "execution-1" }],
      },
    ],
    [
      "provider-execution-only with an ordinary template",
      {
        ...ordinaryRelations,
        noteTemplate: {
          templateKind: "structured",
          templateTwinCompiledVersion: null,
        },
        templateTwinProviderExecutions: [{ id: "execution-1" }],
      },
    ],
    [
      "synthetic run-only",
      {
        ...ordinaryRelations,
        noteTemplate: null,
        templateTwinSyntheticQaRun: { id: "run-1" },
      },
    ],
    [
      "pre-cert admission-only",
      {
        ...ordinaryRelations,
        noteTemplate: null,
        templateTwinSyntheticQaAdmission: { id: "admission-1" },
      },
    ],
  ])("classifies %s as Template Twin", (_label, visit) => {
    expect(hasTemplateTwinProvenance(visit)).toBe(true);
  });

  it("classifies a wholly ordinary visit as ordinary", () => {
    expect(
      hasTemplateTwinProvenance({
        noteTemplate: {
          templateKind: "structured",
          templateTwinCompiledVersion: null,
        },
        ...ordinaryRelations,
      }),
    ).toBe(false);
  });

  it("fails closed when a call site omits any durable relation from its select", () => {
    expect(
      hasTemplateTwinProvenance({
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: null,
        templateTwinSyntheticQaRun: null,
        templateTwinSyntheticQaAdmission: null,
      } as never),
    ).toBe(true);
  });

  it.each([
    ["template kind", { templateTwinCompiledVersion: null }],
    ["compiled relation", { templateKind: "structured" }],
    [
      "valid template kind value",
      { templateKind: null, templateTwinCompiledVersion: null },
    ],
  ])("fails closed when noteTemplate omits or malforms %s", (_label, noteTemplate) => {
    expect(
      hasTemplateTwinProvenance({
        ...ordinaryRelations,
        noteTemplate,
      } as never),
    ).toBe(true);
  });

  it.each([
    ["missing patient relation", null],
    ["malformed patient projection", {}],
  ])("fails closed for a %s", (_label, patient) => {
    expect(
      hasTemplateTwinProvenance({
        ...ordinaryRelations,
        patient,
        noteTemplate: { templateKind: "structured" },
      } as never),
    ).toBe(true);
  });

  it("never invokes an on-read provider/cache operation for durable Twin provenance", async () => {
    const fence = vi.fn(async () => undefined);
    const providerBackedScore = vi.fn(async () => ({ code: "99214" }));

    await expect(
      runProviderBackedEmForOrdinaryVisit(true, fence, providerBackedScore),
    ).resolves.toBeNull();
    expect(fence).not.toHaveBeenCalled();
    expect(providerBackedScore).not.toHaveBeenCalled();
  });

  it("fences ordinary E/M immediately before provider egress and after return", async () => {
    const events: string[] = [];
    const fence = vi.fn(async () => {
      events.push("fence");
    });
    const providerBackedScore = vi.fn(async () => {
      events.push("provider");
      return { code: "99213" };
    });

    await expect(
      runProviderBackedEmForOrdinaryVisit(false, fence, providerBackedScore),
    ).resolves.toEqual({ code: "99213" });
    expect(events).toEqual(["fence", "provider", "fence"]);
    expect(fence).toHaveBeenCalledTimes(2);
    expect(providerBackedScore).toHaveBeenCalledTimes(1);
  });

  it("does not call the provider when the pre-egress ordinary fence fails", async () => {
    const fence = vi.fn(async () => {
      throw new Error("provenance changed");
    });
    const providerBackedScore = vi.fn(async () => ({ code: "99213" }));

    await expect(
      runProviderBackedEmForOrdinaryVisit(false, fence, providerBackedScore),
    ).rejects.toThrow("provenance changed");
    expect(providerBackedScore).not.toHaveBeenCalled();
  });

  it("discards the provider result when the post-return fence fails", async () => {
    const fence = vi
      .fn<() => Promise<void>>()
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("provenance appeared"));
    const providerBackedScore = vi.fn(async () => ({ code: "99213" }));

    await expect(
      runProviderBackedEmForOrdinaryVisit(false, fence, providerBackedScore),
    ).rejects.toThrow("provenance appeared");
    expect(providerBackedScore).toHaveBeenCalledTimes(1);
    expect(fence).toHaveBeenCalledTimes(2);
  });
});
