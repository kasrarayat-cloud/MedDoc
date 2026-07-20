import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

import {
  resolveVisitTemplateProviderCensus,
  mayUseLegacySystemDefaultFallback,
  shouldDropPreCertificationSyntheticVoiceVisit,
  shouldReuseProviderLayerCheckpoint,
} from "../visit-template-provider-census";

const ordinary = {
  id: "ordinary-v1",
  version: 1,
  templateKind: "structured",
  templateTwinCompiledVersion: null,
};
const twin = {
  id: "twin-v2",
  version: 2,
  templateKind: "template_twin_docx",
  templateTwinCompiledVersion: { id: "compiled-v2" },
};
const ordinaryProvenance = {
  patient: { externalId: null },
  noteTemplate: ordinary,
  templateTwinFill: null,
  templateTwinSyntheticQaRun: null,
  templateTwinSyntheticQaAdmission: null,
  templateTwinProviderExecutions: [],
} as const;
const twinProvenance = {
  ...ordinaryProvenance,
  noteTemplate: twin,
} as const;

describe("visit template provider census", () => {
  it("loads and classifies every durable marker before entering the clinical pipeline", () => {
    const worker = readFileSync(
      resolve(process.cwd(), "src/worker.ts"),
      "utf8",
    );
    const start = worker.indexOf("async function processVisitPipeline(");
    const end = worker.indexOf(
      "async function processVisitPipelineCore(",
      start,
    );
    const preflight = worker.slice(start, end);

    expect(preflight).toContain("templateTwinFill:");
    expect(preflight).toContain("patient: { select: { externalId: true } }");
    expect(preflight).toContain("templateTwinSyntheticQaRun:");
    expect(preflight).toContain("templateTwinSyntheticQaAdmission:");
    expect(preflight).toContain("templateTwinProviderExecutions:");
    expect(preflight).toContain("templateTwinCompiledVersion:");
    expect(preflight).toContain("durableProvenance: visit");
    expect(preflight.indexOf("durableProvenance: visit")).toBeLessThan(
      preflight.indexOf("processVisitPipelineCore(job"),
    );
  });

  it("drops a pre-certification synthetic voice reservation before provider census", () => {
    expect(
      shouldDropPreCertificationSyntheticVoiceVisit({
        preCertificationVoiceEvidence: true,
      }),
    ).toBe(true);
    expect(shouldDropPreCertificationSyntheticVoiceVisit(null)).toBe(false);
    expect(
      shouldDropPreCertificationSyntheticVoiceVisit({
        preCertificationVoiceEvidence: false,
      }),
    ).toBe(false);
  });

  it("pins an ordinary preflight result even when the active template becomes a Twin before L4", async () => {
    let active: typeof ordinary | typeof twin = ordinary;
    const resolve = vi.fn(async () => ({
      template: active,
      templateTwinRolloutToken:
        active.templateKind === "template_twin_docx" ? { generation: 2 } : null,
    }));

    const decision = await resolveVisitTemplateProviderCensus({
      runtimeEnabled: true,
      pinnedOrdinary: false,
      syntheticQaContextActive: false,
      durableProvenance: ordinaryProvenance,
      resolve,
    });
    active = twin;

    expect(decision).toEqual({
      kind: "RESOLVED_ORDINARY",
      template: ordinary,
      rolloutToken: null,
    });
    expect(resolve).toHaveBeenCalledTimes(1);
  });

  it("fails an unresolved enabled census without retrying into a newly active Twin", async () => {
    const resolve = vi
      .fn()
      .mockRejectedValueOnce(new Error("database unavailable"))
      .mockResolvedValueOnce({
        template: twin,
        templateTwinRolloutToken: { generation: 3 },
      });

    await expect(
      resolveVisitTemplateProviderCensus({
        runtimeEnabled: true,
        pinnedOrdinary: false,
        syntheticQaContextActive: false,
        durableProvenance: ordinaryProvenance,
        resolve,
      }),
    ).rejects.toThrow("database unavailable");
    expect(resolve).toHaveBeenCalledTimes(1);
  });

  it("keeps the exact preflight version when the active ordinary version changes", async () => {
    const mutable = { ...ordinary };
    const decision = await resolveVisitTemplateProviderCensus({
      runtimeEnabled: true,
      pinnedOrdinary: false,
      syntheticQaContextActive: false,
      durableProvenance: ordinaryProvenance,
      resolve: async () => ({
        template: { ...mutable },
        templateTwinRolloutToken: null,
      }),
    });
    mutable.id = "ordinary-v2";
    mutable.version = 2;

    expect(decision.kind).toBe("RESOLVED_ORDINARY");
    if (decision.kind === "RESOLVED_ORDINARY") {
      expect(decision.template).toMatchObject({
        id: "ordinary-v1",
        version: 1,
      });
    }
  });

  it("preserves the legacy ordinary path when the Twin runtime is definitively disabled", async () => {
    const resolve = vi.fn();
    await expect(
      resolveVisitTemplateProviderCensus({
        runtimeEnabled: false,
        pinnedOrdinary: false,
        syntheticQaContextActive: false,
        durableProvenance: ordinaryProvenance,
        resolve,
      }),
    ).resolves.toEqual({ kind: "LEGACY_DISABLED" });
    expect(resolve).not.toHaveBeenCalled();
  });

  it.each([
    [
      "compiled lineage after mutable kind drift",
      {
        ...ordinaryProvenance,
        noteTemplate: {
          ...ordinary,
          templateTwinCompiledVersion: { id: "compiled-drift" },
        },
      },
    ],
    [
      "missing patient relation",
      {
        ...ordinaryProvenance,
        patient: null,
      },
    ],
    [
      "reserved synthetic patient-only",
      {
        ...ordinaryProvenance,
        patient: { externalId: "SYNTHETIC-QA-ONLY" },
        noteTemplate: null,
      },
    ],
    [
      "provider-execution-only",
      {
        ...ordinaryProvenance,
        noteTemplate: null,
        templateTwinProviderExecutions: [{ id: "execution-1" }],
      },
    ],
    [
      "fill-only",
      {
        ...ordinaryProvenance,
        noteTemplate: null,
        templateTwinFill: { id: "fill-1" },
      },
    ],
    [
      "admission-only",
      {
        ...ordinaryProvenance,
        noteTemplate: null,
        templateTwinSyntheticQaAdmission: { id: "admission-1" },
      },
    ],
    [
      "run-only with an ordinary template",
      {
        ...ordinaryProvenance,
        templateTwinSyntheticQaRun: { id: "run-1" },
      },
    ],
  ])(
    "fails closed on detached %s provenance before resolving an active template",
    async (_label, durableProvenance) => {
      const resolve = vi.fn(async () => ({
        template: ordinary,
        templateTwinRolloutToken: null,
      }));

      await expect(
        resolveVisitTemplateProviderCensus({
          runtimeEnabled: true,
          pinnedOrdinary: false,
          syntheticQaContextActive: false,
          durableProvenance,
          resolve,
        }),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_CENSUS_PROVENANCE_INVALID",
      });
      expect(resolve).not.toHaveBeenCalled();
    },
  );

  it.each([true, false])(
    "blocks an orphaned reserved synthetic patient before resolution when runtimeEnabled=%s",
    async (runtimeEnabled) => {
      const resolve = vi.fn(async () => ({
        template: ordinary,
        templateTwinRolloutToken: null,
      }));

      await expect(
        resolveVisitTemplateProviderCensus({
          runtimeEnabled,
          pinnedOrdinary: false,
          syntheticQaContextActive: false,
          durableProvenance: {
            ...ordinaryProvenance,
            patient: { externalId: "SYNTHETIC-QA-ONLY" },
            noteTemplate: twin,
          },
          resolve,
        }),
      ).rejects.toMatchObject({
        code: "TEMPLATE_TWIN_PROVIDER_CENSUS_PROVENANCE_INVALID",
      });
      expect(resolve).not.toHaveBeenCalled();
    },
  );

  it("admits an exact synthetic context only with reserved patient, run, admission, Twin pin, and rollout", async () => {
    await expect(
      resolveVisitTemplateProviderCensus({
        runtimeEnabled: true,
        pinnedOrdinary: false,
        syntheticQaContextActive: true,
        durableProvenance: {
          ...twinProvenance,
          patient: { externalId: "SYNTHETIC-QA-ONLY" },
          templateTwinSyntheticQaRun: { id: "run-1" },
          templateTwinSyntheticQaAdmission: { id: "admission-1" },
        },
        resolve: async () => ({
          template: twin,
          templateTwinRolloutToken: { generation: 5 },
        }),
      }),
    ).resolves.toEqual({
      kind: "RESOLVED_TEMPLATE_TWIN",
      template: twin,
      rolloutToken: { generation: 5 },
    });
  });

  it("fails a durable Twin closed when the active resolver returns an ordinary or different template", async () => {
    const resolve = vi.fn(async () => ({
      template: ordinary,
      templateTwinRolloutToken: null,
    }));

    await expect(
      resolveVisitTemplateProviderCensus({
        runtimeEnabled: true,
        pinnedOrdinary: false,
        syntheticQaContextActive: false,
        durableProvenance: twinProvenance,
        resolve,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CENSUS_PROVENANCE_INVALID",
    });
    expect(resolve).toHaveBeenCalledTimes(1);
  });

  it("does not let a disabled runtime downgrade durable Twin provenance to legacy", async () => {
    const resolve = vi.fn();

    await expect(
      resolveVisitTemplateProviderCensus({
        runtimeEnabled: false,
        pinnedOrdinary: false,
        syntheticQaContextActive: false,
        durableProvenance: twinProvenance,
        resolve,
      }),
    ).rejects.toMatchObject({
      code: "TEMPLATE_TWIN_PROVIDER_CENSUS_PROVENANCE_INVALID",
    });
    expect(resolve).not.toHaveBeenCalled();
  });

  it("admits exact durable Twin provenance only with the exact resolved pin and rollout", async () => {
    await expect(
      resolveVisitTemplateProviderCensus({
        runtimeEnabled: true,
        pinnedOrdinary: false,
        syntheticQaContextActive: false,
        durableProvenance: {
          ...twinProvenance,
          templateTwinProviderExecutions: [{ id: "execution-1" }],
        },
        resolve: async () => ({
          template: twin,
          templateTwinRolloutToken: { generation: 4 },
        }),
      }),
    ).resolves.toEqual({
      kind: "RESOLVED_TEMPLATE_TWIN",
      template: twin,
      rolloutToken: { generation: 4 },
    });
  });

  it("re-enters every provider wrapper for an owned Twin instead of trusting a pre-ledger checkpoint", () => {
    expect(
      shouldReuseProviderLayerCheckpoint({
        checkpointComplete: true,
        providerOwnedTwin: true,
      }),
    ).toBe(false);
    expect(
      shouldReuseProviderLayerCheckpoint({
        checkpointComplete: true,
        providerOwnedTwin: false,
      }),
    ).toBe(true);
  });

  it("preserves the unpinned ordinary normalization fallback but never applies it to a Twin or persisted pin", () => {
    expect(
      mayUseLegacySystemDefaultFallback({
        preparedClassification: "ORDINARY",
        hasPersistedTemplatePin: false,
        selectedTemplateKind: "structured",
      }),
    ).toBe(true);
    expect(
      mayUseLegacySystemDefaultFallback({
        preparedClassification: "TEMPLATE_TWIN",
        hasPersistedTemplatePin: false,
        selectedTemplateKind: "template_twin_docx",
      }),
    ).toBe(false);
    expect(
      mayUseLegacySystemDefaultFallback({
        preparedClassification: "ORDINARY",
        hasPersistedTemplatePin: true,
        selectedTemplateKind: "structured",
      }),
    ).toBe(false);
  });
});
