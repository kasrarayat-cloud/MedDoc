import { describe, expect, it } from "vitest";

import {
  COMPLETED_CANDIDATE_SYNTHETIC_MODE,
  completedCandidateSyntheticModeEnabled,
} from "../completed-candidate-access";

describe("completed candidate synthetic runtime selector", () => {
  it("is hidden by default and rejects truthy or near-match widening", () => {
    expect(completedCandidateSyntheticModeEnabled({})).toBe(false);
    expect(
      completedCandidateSyntheticModeEnabled({
        TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE: "true",
      }),
    ).toBe(false);
    expect(
      completedCandidateSyntheticModeEnabled({
        TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE: "synthetic-review-v2",
      }),
    ).toBe(false);
  });

  it("accepts only the documented exact synthetic review mode", () => {
    expect(
      completedCandidateSyntheticModeEnabled({
        TEMPLATE_TWIN_COMPLETED_CANDIDATE_MODE:
          COMPLETED_CANDIDATE_SYNTHETIC_MODE,
      }),
    ).toBe(true);
  });
});
