import { describe, expect, it } from "vitest";

import { vi } from "vitest";

import {
  hasTemplateTwinProvenance,
  runProviderBackedEmForOrdinaryVisit,
} from "../template-twin-boundary";

describe("durable Template Twin E/M provenance", () => {
  it.each([
    [
      "current Twin kind",
      { noteTemplate: { templateKind: "template_twin_docx" } },
    ],
    [
      "fill-only with structured template",
      {
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: { id: "fill-1" },
      },
    ],
    [
      "fill-only with detached template",
      { noteTemplate: null, templateTwinFill: { id: "fill-1" } },
    ],
    ["synthetic run-only", { templateTwinSyntheticQaRun: { id: "run-1" } }],
    [
      "pre-cert admission-only",
      { templateTwinSyntheticQaAdmission: { id: "admission-1" } },
    ],
  ])("classifies %s as Template Twin", (_label, visit) => {
    expect(hasTemplateTwinProvenance(visit)).toBe(true);
  });

  it("classifies a wholly ordinary visit as ordinary", () => {
    expect(
      hasTemplateTwinProvenance({
        noteTemplate: { templateKind: "structured" },
        templateTwinFill: null,
        templateTwinSyntheticQaRun: null,
        templateTwinSyntheticQaAdmission: null,
      }),
    ).toBe(false);
  });

  it("never invokes an on-read provider/cache operation for durable Twin provenance", async () => {
    const providerBackedScore = vi.fn(async () => ({ code: "99214" }));

    await expect(
      runProviderBackedEmForOrdinaryVisit(true, providerBackedScore),
    ).resolves.toBeNull();
    expect(providerBackedScore).not.toHaveBeenCalled();
  });

  it("preserves ordinary on-read E/M scoring", async () => {
    const providerBackedScore = vi.fn(async () => ({ code: "99213" }));

    await expect(
      runProviderBackedEmForOrdinaryVisit(false, providerBackedScore),
    ).resolves.toEqual({ code: "99213" });
    expect(providerBackedScore).toHaveBeenCalledTimes(1);
  });
});
