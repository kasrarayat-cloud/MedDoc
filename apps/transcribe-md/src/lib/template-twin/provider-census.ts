import { AsyncLocalStorage } from "node:async_hooks";

export type TemplateTwinProviderCensusDecision =
  | {
      readonly classification: "ORDINARY";
      readonly templateId: string;
      readonly templateVersion: number;
    }
  | {
      readonly classification: "TEMPLATE_TWIN";
      readonly templateId: string;
      readonly templateVersion: number;
    };

interface CensusState {
  readonly decision: TemplateTwinProviderCensusDecision;
  active: boolean;
}

const census = new AsyncLocalStorage<CensusState>();

/**
 * Pins the pre-provider template classification for one worker attempt. The
 * classification is intentionally independent from the later L4 template
 * resolver so an active-template change cannot upgrade an ordinary attempt
 * after L1-L3 have already crossed provider boundaries.
 */
export async function runWithTemplateTwinProviderCensus<T>(
  decision: TemplateTwinProviderCensusDecision,
  operation: () => Promise<T>,
): Promise<T> {
  if (census.getStore()) {
    throw new Error("Template Twin provider census cannot be nested.");
  }
  const state: CensusState = { decision: Object.freeze({ ...decision }), active: true };
  return census.run(state, async () => {
    try {
      return await operation();
    } finally {
      state.active = false;
    }
  });
}

export function templateTwinProviderOwnershipRequiredByCensus(): boolean {
  const state = census.getStore();
  return Boolean(
    state &&
      (!state.active || state.decision.classification === "TEMPLATE_TWIN"),
  );
}

export function getTemplateTwinProviderCensusDecision(): TemplateTwinProviderCensusDecision | null {
  const state = census.getStore();
  return state?.active ? state.decision : null;
}
