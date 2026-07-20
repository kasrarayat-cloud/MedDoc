import {
  hasDurableTemplateTwinVisitProvenance,
  type TemplateTwinDurableVisitProvenance,
} from "@/lib/template-twin/durable-visit-provenance";

export interface VisitTemplateProviderCandidate {
  readonly id: string;
  readonly version: number;
  readonly templateKind: string;
}

export interface VisitTemplateProviderCensusProvenance extends TemplateTwinDurableVisitProvenance {
  readonly noteTemplate: VisitTemplateProviderCandidate | null;
}

export class VisitTemplateProviderCensusProvenanceError extends Error {
  readonly code = "TEMPLATE_TWIN_PROVIDER_CENSUS_PROVENANCE_INVALID" as const;

  constructor() {
    super("Durable Template Twin visit provenance is inconsistent.");
    this.name = "VisitTemplateProviderCensusProvenanceError";
  }
}

export interface PreCertificationSyntheticVoiceMarker {
  readonly preCertificationVoiceEvidence: boolean;
}

/**
 * A pre-certification voice reservation is a provider-evidence capability,
 * never a clinical pipeline admission. A forged or accidentally enqueued job
 * must therefore stop before runtime census, status mutation, or any provider
 * wrapper. The database owns the marker's detailed lineage validation; the
 * worker deliberately needs only the immutable capability bit to isolate it.
 */
export function shouldDropPreCertificationSyntheticVoiceVisit(
  marker: PreCertificationSyntheticVoiceMarker | null | undefined,
): boolean {
  return marker?.preCertificationVoiceEvidence === true;
}

export type VisitTemplateProviderCensus<
  T extends VisitTemplateProviderCandidate,
> =
  | { readonly kind: "LEGACY_DISABLED" }
  | {
      readonly kind: "PINNED_ORDINARY";
    }
  | {
      readonly kind: "RESOLVED_ORDINARY";
      readonly template: T;
      readonly rolloutToken: null;
    }
  | {
      readonly kind: "RESOLVED_TEMPLATE_TWIN";
      readonly template: T;
      readonly rolloutToken: unknown;
    };

/**
 * Performs the only mutable active-template lookup allowed for this attempt.
 * In standard runtime mode an unresolved census is retryable failure, never a
 * license to run L1-L3 and ask the active resolver again at L4.
 */
export async function resolveVisitTemplateProviderCensus<
  T extends VisitTemplateProviderCandidate,
>(input: {
  readonly runtimeEnabled: boolean;
  readonly pinnedOrdinary: boolean;
  readonly durableProvenance: VisitTemplateProviderCensusProvenance;
  readonly resolve: () => Promise<{
    readonly template: T;
    readonly templateTwinRolloutToken: unknown | null;
  }>;
}): Promise<VisitTemplateProviderCensus<T>> {
  const hasDurableTwinProvenance = hasDurableTemplateTwinVisitProvenance(
    input.durableProvenance,
  );
  if (hasDurableTwinProvenance) {
    const pinnedTemplate = input.durableProvenance.noteTemplate;
    if (
      !input.runtimeEnabled ||
      input.pinnedOrdinary ||
      pinnedTemplate?.templateKind !== "template_twin_docx"
    ) {
      throw new VisitTemplateProviderCensusProvenanceError();
    }
  }
  if (!input.runtimeEnabled) return { kind: "LEGACY_DISABLED" };
  if (input.pinnedOrdinary) return { kind: "PINNED_ORDINARY" };

  const resolved = await input.resolve();
  if (
    hasDurableTwinProvenance &&
    (resolved.template.templateKind !== "template_twin_docx" ||
      resolved.template.id !== input.durableProvenance.noteTemplate?.id ||
      resolved.template.version !==
        input.durableProvenance.noteTemplate?.version)
  ) {
    throw new VisitTemplateProviderCensusProvenanceError();
  }
  if (resolved.template.templateKind === "template_twin_docx") {
    if (!resolved.templateTwinRolloutToken) {
      throw new Error(
        "Template Twin provider census resolved without rollout authority.",
      );
    }
    return {
      kind: "RESOLVED_TEMPLATE_TWIN",
      template: resolved.template,
      rolloutToken: resolved.templateTwinRolloutToken,
    };
  }
  return {
    kind: "RESOLVED_ORDINARY",
    template: resolved.template,
    rolloutToken: null,
  };
}

/** Provider-backed checkpoints are reusable only for ordinary attempts. An
 * owned Twin must re-enter the wrapper so the durable execution ledger can
 * prove or safely perform the exact plan slot. */
export function shouldReuseProviderLayerCheckpoint(input: {
  readonly checkpointComplete: boolean;
  readonly providerOwnedTwin: boolean;
}): boolean {
  return input.checkpointComplete && !input.providerOwnedTwin;
}

export function mayUseLegacySystemDefaultFallback(input: {
  readonly preparedClassification: "ORDINARY" | "TEMPLATE_TWIN" | null;
  readonly hasPersistedTemplatePin: boolean;
  readonly selectedTemplateKind: string | null;
}): boolean {
  return (
    !input.hasPersistedTemplatePin &&
    input.selectedTemplateKind !== "template_twin_docx" &&
    input.preparedClassification !== "TEMPLATE_TWIN"
  );
}
