export const TEMPLATE_TWIN_KILL_SWITCH_ENV =
  'TEMPLATE_TWIN_KILL_SWITCH' as const;

export type TemplateTwinRolloutCode =
  | 'TEMPLATE_TWIN_KILL_SWITCH_ACTIVE'
  | 'TEMPLATE_TWIN_PRACTICE_DISABLED';

export type TemplateTwinRolloutDecision =
  | { allowed: true }
  | {
      allowed: false;
      code: TemplateTwinRolloutCode;
      reason: string;
    };

export interface TemplateTwinRolloutInput {
  practiceEnabled: boolean;
  env?: Readonly<Record<string, string | undefined>>;
}

export class TemplateTwinRolloutError extends Error {
  constructor(
    readonly code: TemplateTwinRolloutCode,
    message: string,
  ) {
    super(message);
    this.name = 'TemplateTwinRolloutError';
  }
}

function killSwitchIsExplicitlyOff(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === 'false';
}

/**
 * Safe-alpha rollout contract. The global switch is fail-closed: an absent,
 * malformed, or truthy value keeps Template Twin disabled. Operators must
 * explicitly set `TEMPLATE_TWIN_KILL_SWITCH=false`, and the owning practice
 * must then opt in separately.
 */
export function evaluateTemplateTwinRollout({
  practiceEnabled,
  env = process.env,
}: TemplateTwinRolloutInput): TemplateTwinRolloutDecision {
  if (!killSwitchIsExplicitlyOff(env[TEMPLATE_TWIN_KILL_SWITCH_ENV])) {
    return {
      allowed: false,
      code: 'TEMPLATE_TWIN_KILL_SWITCH_ACTIVE',
      reason: 'Template Twin is temporarily unavailable.',
    };
  }
  if (!practiceEnabled) {
    return {
      allowed: false,
      code: 'TEMPLATE_TWIN_PRACTICE_DISABLED',
      reason: 'Template Twin is not enabled for this practice.',
    };
  }
  return { allowed: true };
}

export function assertTemplateTwinRollout(
  input: TemplateTwinRolloutInput,
): void {
  const decision = evaluateTemplateTwinRollout(input);
  if (!decision.allowed) {
    throw new TemplateTwinRolloutError(decision.code, decision.reason);
  }
}
