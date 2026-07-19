import { describe, expect, it } from "vitest";

import {
  TemplateTwinRolloutError,
  assertTemplateTwinRollout,
  evaluateTemplateTwinRollout,
} from "../rollout";

describe("Template Twin safe-alpha rollout gate", () => {
  it("fails closed when the global kill-switch setting is absent", () => {
    expect(
      evaluateTemplateTwinRollout({
        practiceEnabled: true,
        env: {},
      }),
    ).toEqual({
      allowed: false,
      code: "TEMPLATE_TWIN_KILL_SWITCH_ACTIVE",
      reason: "Template Twin is temporarily unavailable.",
    });
  });

  it("fails closed when the practice flag is off", () => {
    expect(
      evaluateTemplateTwinRollout({
        practiceEnabled: false,
        env: { TEMPLATE_TWIN_KILL_SWITCH: "false" },
      }),
    ).toEqual({
      allowed: false,
      code: "TEMPLATE_TWIN_PRACTICE_DISABLED",
      reason: "Template Twin is not enabled for this practice.",
    });
  });

  it.each(["1", "true", "TRUE", "yes", "on"])(
    "honors an explicit global kill switch value %s",
    (value) => {
      const decision = evaluateTemplateTwinRollout({
        practiceEnabled: true,
        env: { TEMPLATE_TWIN_KILL_SWITCH: value },
      });
      expect(decision.allowed).toBe(false);
      if (decision.allowed) throw new Error("Expected rollout to be blocked.");
      expect(decision.code).toBe("TEMPLATE_TWIN_KILL_SWITCH_ACTIVE");
    },
  );

  it("allows only an enabled practice with the global kill switch explicitly off", () => {
    expect(
      evaluateTemplateTwinRollout({
        practiceEnabled: true,
        env: { TEMPLATE_TWIN_KILL_SWITCH: "false" },
      }),
    ).toEqual({ allowed: true });
  });

  it("blocks every Template Twin admission in rollback compatibility mode", () => {
    expect(
      evaluateTemplateTwinRollout({
        practiceEnabled: true,
        env: {
          TEMPLATE_TWIN_KILL_SWITCH: "false",
          TEMPLATE_TWIN_RUNTIME_MODE: "rollback-compat-v2",
        },
      }),
    ).toEqual({
      allowed: false,
      code: "TEMPLATE_TWIN_ROLLBACK_COMPAT_ACTIVE",
      reason:
        "Template Twin is unavailable while rollback compatibility mode is active.",
    });
  });

  it("fails closed when the runtime mode is malformed", () => {
    expect(
      evaluateTemplateTwinRollout({
        practiceEnabled: true,
        env: {
          TEMPLATE_TWIN_KILL_SWITCH: "false",
          TEMPLATE_TWIN_RUNTIME_MODE: "pre-stack-image",
        },
      }),
    ).toMatchObject({
      allowed: false,
      code: "TEMPLATE_TWIN_RUNTIME_MODE_INVALID",
    });
  });

  it("throws a stable physician-readable error at server boundaries", () => {
    expect(() =>
      assertTemplateTwinRollout({
        practiceEnabled: false,
        env: { TEMPLATE_TWIN_KILL_SWITCH: "false" },
      }),
    ).toThrowError(
      new TemplateTwinRolloutError(
        "TEMPLATE_TWIN_PRACTICE_DISABLED",
        "Template Twin is not enabled for this practice.",
      ),
    );
  });
});
