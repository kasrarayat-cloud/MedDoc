import { AsyncLocalStorage } from "node:async_hooks";

import type { Prisma } from "@prisma/client";

import type { AuditAction } from "@/lib/audit";
import type { TemplateTwinAuditMetadata } from "@/lib/template-twin/audit-outbox";
import type { VisitAutomationLayerId } from "@/worker/automation-policy";

export interface CapturedWorkerAudit {
  eventKey: string;
  practiceId: string;
  actorId: string;
  action: AuditAction;
  targetId: string;
  targetType: string | null;
  metadata?: TemplateTwinAuditMetadata;
}

export interface CapturedVisitMutation {
  data: Record<string, unknown>;
}

export interface CapturedAutomationLayerEffects {
  visitMutations: CapturedVisitMutation[];
  audits: CapturedWorkerAudit[];
}

interface CaptureState extends CapturedAutomationLayerEffects {
  layerId: VisitAutomationLayerId;
  visitId: string;
  userId: string;
  practiceId: string;
}

const captureStorage = new AsyncLocalStorage<CaptureState>();

const ALLOWED_VISIT_FIELDS: Record<
  VisitAutomationLayerId,
  ReadonlySet<string>
> = {
  icd_coding: new Set(["icdCodes", "needsReview", "reviewReason"]),
  cpt_coding: new Set(["cptCodes", "needsReview", "reviewReason"]),
  rx_drafting: new Set(["rxDrafts", "needsReview", "reviewReason"]),
  referrals: new Set(["referrals", "needsReview", "reviewReason"]),
  patient_summary: new Set(["patientSummary", "needsReview", "reviewReason"]),
  em_mdm_prewarm: new Set(),
};

function cloneBoundedJson(value: unknown): Record<string, unknown> {
  const serialized = JSON.stringify(value);
  if (!serialized || Buffer.byteLength(serialized, "utf8") > 512 * 1024) {
    throw new AutomationLayerEffectCaptureError(
      "AUTOMATION_LAYER_EFFECT_INVALID",
    );
  }
  const cloned = JSON.parse(serialized) as unknown;
  if (!cloned || Array.isArray(cloned) || typeof cloned !== "object") {
    throw new AutomationLayerEffectCaptureError(
      "AUTOMATION_LAYER_EFFECT_INVALID",
    );
  }
  return cloned as Record<string, unknown>;
}

export class AutomationLayerEffectCaptureError extends Error {
  constructor(
    readonly code:
      | "AUTOMATION_LAYER_EFFECT_IDENTITY_MISMATCH"
      | "AUTOMATION_LAYER_EFFECT_FIELD_FORBIDDEN"
      | "AUTOMATION_LAYER_EFFECT_INVALID",
  ) {
    super("The automation layer attempted an unsupported database effect.");
    this.name = "AutomationLayerEffectCaptureError";
  }
}

export async function runWithAutomationLayerEffectCapture<T>(input: {
  layerId: VisitAutomationLayerId;
  visitId: string;
  userId: string;
  practiceId: string;
  callback: () => Promise<T>;
}): Promise<{ output: T; effects: CapturedAutomationLayerEffects }> {
  const state: CaptureState = {
    layerId: input.layerId,
    visitId: input.visitId,
    userId: input.userId,
    practiceId: input.practiceId,
    visitMutations: [],
    audits: [],
  };
  const output = await captureStorage.run(state, input.callback);
  return {
    output,
    effects: {
      visitMutations: state.visitMutations,
      audits: state.audits,
    },
  };
}

export function captureAutomationLayerVisitMutation(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  data:
    | Prisma.TranscribeVisitUpdateInput
    | Prisma.TranscribeVisitUncheckedUpdateInput;
}): boolean {
  const state = captureStorage.getStore();
  if (!state) return false;
  if (
    state.visitId !== input.visitId ||
    state.userId !== input.userId ||
    state.practiceId !== input.practiceId
  ) {
    throw new AutomationLayerEffectCaptureError(
      "AUTOMATION_LAYER_EFFECT_IDENTITY_MISMATCH",
    );
  }
  const data = cloneBoundedJson(input.data);
  const allowed = ALLOWED_VISIT_FIELDS[state.layerId];
  if (Object.keys(data).some((field) => !allowed.has(field))) {
    throw new AutomationLayerEffectCaptureError(
      "AUTOMATION_LAYER_EFFECT_FIELD_FORBIDDEN",
    );
  }
  state.visitMutations.push({ data });
  return true;
}

export function captureAutomationLayerAudit(
  audit: CapturedWorkerAudit,
): boolean {
  const state = captureStorage.getStore();
  if (!state) return false;
  if (
    state.visitId !== audit.targetId ||
    state.userId !== audit.actorId ||
    state.practiceId !== audit.practiceId
  ) {
    throw new AutomationLayerEffectCaptureError(
      "AUTOMATION_LAYER_EFFECT_IDENTITY_MISMATCH",
    );
  }
  state.audits.push(audit);
  return true;
}
