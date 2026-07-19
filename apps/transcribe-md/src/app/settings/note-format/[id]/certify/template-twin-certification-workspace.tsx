"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import type { SemanticMapping } from "@/lib/template-twin/ir";
import type {
  CustomScalarDataType,
  TemplateFieldSpecificationContent,
} from "@/lib/template-twin/custom-concepts/specification";
import {
  TEMPLATE_TWIN_CUSTOM_OPTION_LIMIT,
  TEMPLATE_TWIN_CUSTOM_UNIT_LIMIT,
} from "@/lib/template-twin/custom-concepts/specification";
import {
  defaultCustomAmbiguityEvidence,
  synchronizeCustomSyntheticExamples,
} from "@/lib/template-twin/custom-concepts/example-authoring";
import type {
  TemplateTwinWorkspace,
  TemplateTwinWorkspaceField,
} from "@/lib/template-twin/client-types";
import {
  TEMPLATE_TWIN_SUPPORTED_CONCEPTS,
  isSupportedTemplateTwinConcept,
} from "@/lib/template-twin/supported-concepts";
import { validateTemplateTwinClinicalDetail } from "@/lib/template-twin/mapping-validation";
import { TemplateTwinSyntheticQaBanner } from "@/components/template-twin-synthetic-qa-banner";
import {
  TEMPLATE_TWIN_STAGING_QA_STATIC_INTENT_REASON,
  TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER,
} from "@/lib/template-twin/staging-qa-ui-contract";
import type {
  TemplateTwinStagingQaPhysicianReviewSummary,
  TemplateTwinStagingQaReviewedMappingsResponse,
} from "@/lib/template-twin/staging-qa-reviewed-mapping-contract";

import styles from "./template-twin-certification.module.css";

type FieldFilter = "all" | "attention";

type FieldIntentDraft =
  | { intentKind: "unresolved" }
  | { intentKind: "supported_concept"; supportedConcept: string }
  | { intentKind: "static"; reason: string }
  | {
      intentKind: "custom_concept";
      customSpec: TemplateFieldSpecificationContent;
    };

type MappingFieldError = {
  fieldId: string;
  fieldLabel: string;
  setting: string;
  message: string;
};

type MappingErrorPayload = {
  ok: false;
  code?: string;
  error: string;
  recoverable?: boolean;
  latestWorkspace?: TemplateTwinWorkspace;
  latestTemplateId?: string;
  fieldErrors?: MappingFieldError[];
  retryAfterSec?: number;
  limitType?: string;
  resetAtIso?: string;
};

type StoredMappingDraft = {
  version: 1;
  templateLineageId: string;
  sourceSha256: string;
  baseTemplateId: string;
  baseTemplateVersion: number;
  baseMappingsSha256: string;
  baseFieldIntentsSha256: string;
  baseMappings: SemanticMapping[];
  baseFieldIntents: Record<string, FieldIntentDraft>;
  selectedFieldId: string;
  savedAtIso: string;
  mappings: SemanticMapping[];
  fieldIntents: Record<string, FieldIntentDraft>;
};

type DraftMergeConflict = {
  fieldId: string;
  fieldLabel: string;
  localMapping: SemanticMapping;
  localIntent: FieldIntentDraft | null;
};

type VersionRecoveryState = {
  message: string;
  latestWorkspace?: TemplateTwinWorkspace;
  latestTemplateId?: string;
};

const MAPPING_DRAFT_STORAGE_VERSION = 1;

function mappingDraftStorageKey(templateLineageId: string): string {
  return `template-twin:certification-draft:v${MAPPING_DRAFT_STORAGE_VERSION}:${encodeURIComponent(templateLineageId)}`;
}

function mappingDraftFor(input: {
  workspace: TemplateTwinWorkspace;
  fields: TemplateTwinWorkspaceField[];
  intentDrafts: Record<string, FieldIntentDraft>;
  selectedFieldId: string;
}): StoredMappingDraft {
  return {
    version: MAPPING_DRAFT_STORAGE_VERSION,
    templateLineageId: input.workspace.template.lineageId,
    sourceSha256: input.workspace.source.sha256,
    baseTemplateId: input.workspace.template.id,
    baseTemplateVersion: input.workspace.template.version,
    baseMappingsSha256: input.workspace.mappingsSha256,
    baseFieldIntentsSha256: input.workspace.fieldIntentsSha256,
    baseMappings: input.workspace.fields.map((item) => item.mapping),
    baseFieldIntents: intentDraftsFor(input.workspace.fields),
    selectedFieldId: input.selectedFieldId,
    savedAtIso: new Date().toISOString(),
    mappings: input.fields.map((item) => item.mapping),
    fieldIntents: input.intentDrafts,
  };
}

function storeMappingDraft(draft: StoredMappingDraft): void {
  try {
    window.sessionStorage.setItem(
      mappingDraftStorageKey(draft.templateLineageId),
      JSON.stringify(draft),
    );
  } catch {
    // Storage can be unavailable in a hardened/private browser. The live React
    // state remains intact and the save request still behaves safely.
  }
}

function clearStoredMappingDraft(templateLineageId: string): void {
  try {
    window.sessionStorage.removeItem(mappingDraftStorageKey(templateLineageId));
  } catch {
    // See storeMappingDraft. A failed cleanup must not turn a successful save
    // into a user-visible failure.
  }
}

function readStoredMappingDraft(
  workspace: TemplateTwinWorkspace,
): StoredMappingDraft | null {
  try {
    const raw = window.sessionStorage.getItem(
      mappingDraftStorageKey(workspace.template.lineageId),
    );
    if (!raw) return null;
    const candidate = JSON.parse(raw) as Partial<StoredMappingDraft>;
    if (
      candidate.version !== MAPPING_DRAFT_STORAGE_VERSION ||
      candidate.templateLineageId !== workspace.template.lineageId ||
      candidate.sourceSha256 !== workspace.source.sha256 ||
      !Array.isArray(candidate.mappings) ||
      !candidate.fieldIntents ||
      typeof candidate.fieldIntents !== "object" ||
      (candidate.baseMappings !== undefined &&
        !Array.isArray(candidate.baseMappings)) ||
      (candidate.baseFieldIntents !== undefined &&
        (!candidate.baseFieldIntents ||
          typeof candidate.baseFieldIntents !== "object" ||
          Array.isArray(candidate.baseFieldIntents)))
    ) {
      return null;
    }
    const currentFieldIds = new Set(
      workspace.fields.map((item) => item.field.fieldId),
    );
    const storedFieldIds = new Set(
      candidate.mappings
        .filter(
          (mapping): mapping is SemanticMapping =>
            Boolean(mapping) && typeof mapping.fieldId === "string",
        )
        .map((mapping) => mapping.fieldId),
    );
    if (
      storedFieldIds.size !== currentFieldIds.size ||
      [...storedFieldIds].some((fieldId) => !currentFieldIds.has(fieldId)) ||
      (candidate.baseMappings !== undefined &&
        (candidate.baseMappings.length !== currentFieldIds.size ||
          candidate.baseMappings.some(
            (mapping) =>
              !mapping ||
              typeof mapping.fieldId !== "string" ||
              !currentFieldIds.has(mapping.fieldId),
          )))
    ) {
      return null;
    }
    return candidate as StoredMappingDraft;
  } catch {
    return null;
  }
}

function rebaseMappingDraft(
  workspace: TemplateTwinWorkspace,
  draft: Pick<
    StoredMappingDraft,
    | "baseMappingsSha256"
    | "baseFieldIntentsSha256"
    | "baseMappings"
    | "baseFieldIntents"
    | "mappings"
    | "fieldIntents"
  >,
): {
  fields: TemplateTwinWorkspaceField[];
  intentDrafts: Record<string, FieldIntentDraft>;
  conflicts: DraftMergeConflict[];
} {
  const baseMappingByFieldId = new Map(
    (draft.baseMappings ?? []).map((mapping) => [mapping.fieldId, mapping]),
  );
  const localMappingByFieldId = new Map(
    draft.mappings.map((mapping) => [mapping.fieldId, mapping]),
  );
  const intentDrafts = { ...intentDraftsFor(workspace.fields) };
  const conflicts: DraftMergeConflict[] = [];
  const hasBaseSnapshot =
    Array.isArray(draft.baseMappings) &&
    draft.baseMappings.length === workspace.fields.length &&
    draft.baseFieldIntents !== null &&
    typeof draft.baseFieldIntents === "object";
  const legacyDraftMatchesCurrentRevision =
    draft.baseMappingsSha256 === workspace.mappingsSha256 &&
    draft.baseFieldIntentsSha256 === workspace.fieldIntentsSha256;
  const fields = workspace.fields.map((item) => {
    const fieldId = item.field.fieldId;
    const remoteIntent = intentDrafts[fieldId] ?? null;
    const localIntent = draft.fieldIntents[fieldId] ?? null;
    const localMapping = localMappingByFieldId.get(fieldId) ?? item.mapping;
    const baseMapping = baseMappingByFieldId.get(fieldId) ?? item.mapping;
    const baseIntent = draft.baseFieldIntents?.[fieldId] ?? null;
    const localChanged =
      !draftValuesEqual(localMapping, baseMapping) ||
      !draftValuesEqual(localIntent, baseIntent);
    const remoteChanged = hasBaseSnapshot
      ? !draftValuesEqual(item.mapping, baseMapping) ||
        !draftValuesEqual(remoteIntent, baseIntent)
      : !legacyDraftMatchesCurrentRevision;
    const localMatchesRemote =
      draftValuesEqual(localMapping, item.mapping) &&
      draftValuesEqual(localIntent, remoteIntent);

    if (localChanged && remoteChanged && !localMatchesRemote) {
      conflicts.push({
        fieldId,
        fieldLabel: item.field.originalLabel,
        localMapping,
        localIntent,
      });
      return item;
    }

    if (!localChanged) return item;

    let nextIntent = localIntent;
    let nextMapping = localMapping;
    if (
      localIntent?.intentKind === "custom_concept" &&
      item.customConceptScaffold
    ) {
      nextIntent = {
        intentKind: "custom_concept",
        customSpec: {
          ...localIntent.customSpec,
          ...item.customConceptScaffold,
        },
      };
      nextMapping = {
        ...nextMapping,
        clinicalConcept: item.customConceptScaffold.conceptId,
      };
    }
    if (nextIntent) intentDrafts[fieldId] = nextIntent;
    return { ...item, mapping: nextMapping };
  });
  return { fields, intentDrafts, conflicts };
}

function draftValuesEqual(left: unknown, right: unknown): boolean {
  const canonicalize = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(canonicalize);
    if (!value || typeof value !== "object") return value;
    return Object.fromEntries(
      Object.entries(value)
        .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
        .map(([key, nestedValue]) => [key, canonicalize(nestedValue)]),
    );
  };
  return (
    JSON.stringify(canonicalize(left)) === JSON.stringify(canonicalize(right))
  );
}

const EXPECTED_TYPES: SemanticMapping["expectedDataType"][] = [
  "text",
  "single_select",
  "multi_select",
  "boolean",
  "date",
  "number",
  "measurement",
  "table",
];

const SYNTHETIC_STARTER = [
  "Synthetic test encounter. No real patient information.",
  "The patient reports a mild current symptom on the left side for three days.",
  "They explicitly deny medication allergies.",
  "A synthetic measurement is 12 mm. No medication was prescribed.",
].join(" ");

function contentOnlyCustomSpec(
  item: TemplateTwinWorkspaceField,
): TemplateFieldSpecificationContent | null {
  const spec = item.intent.customSpec;
  if (!spec) return null;
  const { certification, ...content } = spec;
  void certification;
  return content;
}

function defaultCustomSpec(
  item: TemplateTwinWorkspaceField,
): TemplateFieldSpecificationContent | null {
  const identity = item.customConceptScaffold;
  if (!identity) return null;
  const dataType: CustomScalarDataType =
    item.field.kind === "single_select"
      ? "single_select"
      : item.field.kind === "checkbox"
        ? "boolean"
        : item.field.kind === "date"
          ? "date"
          : item.field.kind === "number"
            ? "number"
            : item.field.kind === "measurement"
              ? "measurement"
              : "narrative_text";
  const syntheticValue: string | number | boolean =
    dataType === "boolean"
      ? true
      : dataType === "number" || dataType === "measurement"
        ? 1
        : dataType === "single_select"
          ? (item.field.allowedOptions[0]?.value ?? "synthetic")
          : dataType === "date"
            ? "2099-01-15"
            : "Synthetic supported value";
  const syntheticUnit = dataType === "measurement" ? "mm" : null;
  return synchronizeCustomSyntheticExamples({
    specificationVersion: "template-twin-field-specification/1.1.0",
    ...identity,
    physicianName: item.field.originalLabel.slice(0, 160),
    physicianDescription: "",
    approvedEvidenceCues: [item.field.originalLabel.slice(0, 120)],
    dataType,
    allowedOptions:
      dataType === "single_select"
        ? item.field.allowedOptions.map((option) => ({
            ordinal: option.ordinal,
            value: option.value,
            displayText: option.displayText,
          }))
        : [],
    allowedUnits: dataType === "measurement" ? ["mm"] : [],
    permittedUnitConversions: [],
    allowedTemporalities: ["current"],
    allowedLateralities: ["not_applicable"],
    polarityPolicy: {
      allowExplicitDenial: false,
      exactDeniedOutput: null,
    },
    required: item.mapping.required,
    unknownPolicy: item.mapping.unknownPolicy,
    maximumLength: dataType === "narrative_text" ? 500 : null,
    numericRange: null,
    evidenceRequirements: {
      minimumAnchors: 1,
      acceptedEvidenceQualities: ["direct"],
    },
    positiveSyntheticExamples: [
      {
        exampleId: "positive-1",
        syntheticEvidence: `Synthetic example: ${item.field.originalLabel} is ${String(syntheticValue)}${syntheticUnit ? ` ${syntheticUnit}` : ""}.`,
        expectedValue: syntheticValue,
        expectedUnit: syntheticUnit,
      },
    ],
    negativeSyntheticExamples: [
      {
        exampleId: "negative-1",
        syntheticEvidence:
          "Synthetic example: an unrelated encounter detail is documented.",
        prohibitedValue: null,
        reason: "The certified evidence cue is absent.",
      },
    ],
    ambiguitySyntheticExamples: [],
  });
}

function intentDraftFor(item: TemplateTwinWorkspaceField): FieldIntentDraft {
  switch (item.intent.intentKind) {
    case "supported_concept":
      return {
        intentKind: "supported_concept",
        supportedConcept:
          item.intent.supportedConcept ?? item.mapping.clinicalConcept ?? "",
      };
    case "static":
      return { intentKind: "static", reason: item.intent.reason ?? "" };
    case "custom_concept": {
      const customSpec = contentOnlyCustomSpec(item) ?? defaultCustomSpec(item);
      return customSpec
        ? { intentKind: "custom_concept", customSpec }
        : { intentKind: "unresolved" };
    }
    case "unresolved":
      return { intentKind: "unresolved" };
  }
}

function intentDraftsFor(fields: TemplateTwinWorkspaceField[]) {
  return Object.fromEntries(
    fields
      .filter(
        (item) =>
          item.field.rendererBinding.bindingType === "ordinary_placeholder",
      )
      .map((item) => [item.field.fieldId, intentDraftFor(item)]),
  ) as Record<string, FieldIntentDraft>;
}

function expectedTypeForCustom(
  dataType: CustomScalarDataType,
): SemanticMapping["expectedDataType"] {
  return dataType === "narrative_text" ? "text" : dataType;
}

function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function displaySyntheticValue(value: unknown): string {
  if (value === null || value === undefined) return "Blank";
  if (typeof value === "boolean") return value ? "True" : "False";
  if (Array.isArray(value)) {
    if (value.every((item) => typeof item === "string")) {
      return value.join(", ") || "Blank";
    }
    return `${value.length} synthetic table row${value.length === 1 ? "" : "s"}`;
  }
  return String(value);
}

const POLARITY_LABELS: Record<SemanticMapping["polarityBehavior"], string> = {
  affirmative_only: "Fill only when directly stated as present",
  explicit_denial_allowed: "Allow an exact approved negative value",
  value_only: "Use the stated value without positive or negative meaning",
  not_applicable: "Positive or negative meaning does not apply",
};
const TEMPORALITY_LABELS = {
  current: "Current encounter",
  historical: "Past history",
  planned: "Planned care",
  any: "Any time period stated in the encounter",
} as const;
const LATERALITY_LABELS = {
  required: "Left or right must be stated",
  optional: "Use left or right only when stated",
  not_applicable: "Left or right does not apply",
} as const;
const UNIT_LABELS = {
  required: "A unit must be stated",
  optional: "Use a unit only when stated",
  forbidden: "Do not include a unit",
  not_applicable: "Units do not apply",
} as const;
const UNKNOWN_LABELS = {
  blank: "Leave blank",
  not_documented: "Use the approved “not documented” wording",
  requires_input: "Require physician review",
} as const;

function mappingSettingLabel(setting: string): string {
  const labels: Record<string, string> = {
    clinicalDetail: "Clinical detail to fill",
    supportedConcept: "Clinical detail to fill",
    fieldIntent: "Field intent",
    intentKind: "Field intent",
    mappingStatus: "Confirmation status",
    status: "Confirmation status",
    expectedDataType: "Expected data type",
    approvedSynonyms: "Approved synonyms",
    practiceDefault: "Practice default",
    customConcept: "Custom clinical detail",
    staticField: "Why this remains static",
    reason: "Why this remains static",
    fieldSet: "Detected field set",
  };
  return labels[setting] ?? setting;
}

function fieldDraftError(
  item: TemplateTwinWorkspaceField,
  intentDraft?: FieldIntentDraft,
): MappingFieldError | null {
  const fieldId = item.field.fieldId;
  const fieldLabel = item.field.originalLabel;
  const requiresIntent =
    item.field.rendererBinding.bindingType === "ordinary_placeholder";
  const sharedClinicalDetailError = validateTemplateTwinClinicalDetail({
    field: item.field,
    mapping: item.mapping,
    ...(intentDraft ? { intent: { fieldId, ...intentDraft } } : {}),
  });
  if (sharedClinicalDetailError) {
    return {
      fieldId,
      fieldLabel,
      setting: mappingSettingLabel(sharedClinicalDetailError.setting),
      message: sharedClinicalDetailError.message,
    };
  }

  if (requiresIntent) {
    if (!intentDraft || intentDraft.intentKind === "unresolved") {
      return item.mapping.status === "certified"
        ? {
            fieldId,
            fieldLabel,
            setting: "Field intent",
            message: "Choose what belongs in this field before confirming it.",
          }
        : null;
    }
    if (intentDraft.intentKind === "supported_concept") {
      const concept = intentDraft.supportedConcept.trim();
      if (!concept) {
        return {
          fieldId,
          fieldLabel,
          setting: "Clinical detail to fill",
          message:
            "Choose a supported clinical detail before confirming this field.",
        };
      }
      if (!isSupportedTemplateTwinConcept(concept)) {
        return {
          fieldId,
          fieldLabel,
          setting: "Clinical detail to fill",
          message: `“${concept}” is not supported by this Template Twin version.`,
        };
      }
      if (
        item.mapping.status === "certified" &&
        item.mapping.clinicalConcept !== concept
      ) {
        return {
          fieldId,
          fieldLabel,
          setting: "Clinical detail to fill",
          message:
            "The confirmed mapping does not match the selected clinical detail.",
        };
      }
    }
    if (
      intentDraft.intentKind === "static" &&
      intentDraft.reason.trim().length < 10
    ) {
      return {
        fieldId,
        fieldLabel,
        setting: "Why this remains static",
        message: "Give a reason of at least 10 characters.",
      };
    }
  } else if (!item.mapping.clinicalConcept) {
    return {
      fieldId,
      fieldLabel,
      setting: "Clinical detail to fill",
      message:
        "Choose a supported clinical detail before confirming this field.",
    };
  }

  return null;
}

function fieldIsConfirmed(
  item: TemplateTwinWorkspaceField,
  intentDraft?: FieldIntentDraft,
): boolean {
  return (
    item.mapping.status === "certified" && !fieldDraftError(item, intentDraft)
  );
}

function clientMappingErrors(
  fields: TemplateTwinWorkspaceField[],
  intentDrafts: Record<string, FieldIntentDraft>,
): MappingFieldError[] {
  return fields.flatMap((item) => {
    const error = fieldDraftError(item, intentDrafts[item.field.fieldId]);
    if (
      error?.setting === "Clinical detail to fill" &&
      item.field.rendererBinding.bindingType !== "ordinary_placeholder" &&
      item.mapping.status !== "certified"
    ) {
      return [];
    }
    return error ? [error] : [];
  });
}

function formatRetryDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes === 0) return `${remainingSeconds}s`;
  return `${minutes}m ${String(remainingSeconds).padStart(2, "0")}s`;
}

function fieldStatus(
  item: TemplateTwinWorkspaceField,
  intentDraft?: FieldIntentDraft,
): {
  label: string;
  tone: "safe" | "review" | "block";
} {
  const draftError = fieldDraftError(item, intentDraft);
  if (draftError) {
    return {
      label:
        draftError.setting === "Clinical detail to fill"
          ? "Needs clinical detail"
          : draftError.setting === "Field intent"
            ? "Needs intent"
            : "Needs confirmation",
      tone: "review",
    };
  }
  if (
    item.field.rendererBinding.bindingType === "ordinary_placeholder" &&
    (!intentDraft || intentDraft.intentKind === "unresolved")
  ) {
    return { label: "Needs intent", tone: "review" };
  }
  if (fieldIsConfirmed(item, intentDraft)) {
    return { label: "Certified", tone: "safe" };
  }
  if (item.field.detectionStatus === "unsupported") {
    return { label: "Unsupported", tone: "block" };
  }
  if (
    item.field.detectionStatus === "needs_confirmation" ||
    item.mapping.status === "needs_confirmation"
  ) {
    return { label: "Needs confirmation", tone: "review" };
  }
  return { label: "Recognized", tone: "safe" };
}

function StatusPill({
  item,
  intentDraft,
}: {
  item: TemplateTwinWorkspaceField;
  intentDraft?: FieldIntentDraft;
}) {
  const status = fieldStatus(item, intentDraft);
  return (
    <span className={styles.status} data-tone={status.tone}>
      {status.label}
    </span>
  );
}

export function TemplateTwinCertificationWorkspace({
  initial,
  stagingQaGateAllowed,
}: {
  initial: TemplateTwinWorkspace;
  stagingQaGateAllowed: boolean;
}) {
  const router = useRouter();
  const [workspace, setWorkspace] = useState(initial);
  // The global/practice gate alone never confers fixture provenance. This
  // keeps ordinary physician templates out of the staging-only workflow even
  // in a QA deployment where the global gate is enabled.
  const stagingQaEnabled =
    stagingQaGateAllowed && workspace.stagingQaFixtureSource;
  const [fields, setFields] = useState(initial.fields);
  const [intentDrafts, setIntentDrafts] = useState(() =>
    intentDraftsFor(initial.fields),
  );
  const [selectedId, setSelectedId] = useState(
    initial.fields.find((item) => item.mapping.status !== "certified")?.field
      .fieldId ??
      initial.fields[0]?.field.fieldId ??
      "",
  );
  const [filter, setFilter] = useState<FieldFilter>("all");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<
    | "save"
    | "load-reviewed"
    | "test"
    | "custom-examples"
    | "ack-custom-examples"
    | "certify"
    | "staging-run"
    | null
  >(null);
  const [announcement, setAnnouncement] = useState("");
  const [fieldErrors, setFieldErrors] = useState<MappingFieldError[]>([]);
  const [draftMergeConflicts, setDraftMergeConflicts] = useState<
    DraftMergeConflict[]
  >([]);
  const [versionRecovery, setVersionRecovery] =
    useState<VersionRecoveryState | null>(null);
  const [draftRecoveryNotice, setDraftRecoveryNotice] = useState<string | null>(
    null,
  );
  const [retryState, setRetryState] = useState<{
    resetAtMs: number;
    limitType: string;
    serverResetAtIso?: string;
  } | null>(null);
  const [retryNowMs, setRetryNowMs] = useState(0);
  const [reviewedMappingSummary, setReviewedMappingSummary] =
    useState<TemplateTwinStagingQaPhysicianReviewSummary | null>(null);
  const [syntheticText, setSyntheticText] = useState(() =>
    initial.stagingQaFixtureSource
      ? TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER
      : SYNTHETIC_STARTER,
  );
  const [ackStructure, setAckStructure] = useState(false);
  const [ackTest, setAckTest] = useState(false);
  const [waiverReasons, setWaiverReasons] = useState<Record<string, string>>(
    {},
  );
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);
  const [recording, setRecording] = useState(false);
  const [syntheticVoice, setSyntheticVoice] = useState<Blob | null>(null);
  const [stagingEncounterText, setStagingEncounterText] = useState(() =>
    initial.stagingQaFixtureSource
      ? TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER
      : "",
  );
  const stagingRunKeyRef = useRef<string | null>(null);
  const storageReadyRef = useRef(false);
  const mountedWorkspaceRef = useRef(initial);
  const initialRevisionRef = useRef(
    `${initial.template.id}:${initial.mappingsSha256}:${initial.fieldIntentsSha256}`,
  );

  useEffect(() => {
    const mountedWorkspace = mountedWorkspaceRef.current;
    const stored = readStoredMappingDraft(mountedWorkspace);
    storageReadyRef.current = true;
    if (!stored) return;
    const rebased = rebaseMappingDraft(mountedWorkspace, stored);
    setFields(rebased.fields);
    setIntentDrafts(rebased.intentDrafts);
    setDraftMergeConflicts(rebased.conflicts);
    if (
      mountedWorkspace.fields.some(
        (item) => item.field.fieldId === stored.selectedFieldId,
      )
    ) {
      setSelectedId(stored.selectedFieldId);
    }
    setDirty(true);
    setDraftRecoveryNotice(
      rebased.conflicts.length > 0
        ? "Recovered your unsaved mapping draft, but a newer edit changed the same field. Resolve the listed field before saving."
        : "Recovered unsaved mapping changes from this browser tab. Review and save when ready.",
    );
    setAnnouncement("Unsaved mapping changes were recovered.");
  }, []);

  useEffect(() => {
    const revision = `${initial.template.id}:${initial.mappingsSha256}:${initial.fieldIntentsSha256}`;
    if (revision === initialRevisionRef.current) return;
    initialRevisionRef.current = revision;
    if (dirty) {
      const localDraft = mappingDraftFor({
        workspace,
        fields,
        intentDrafts,
        selectedFieldId: selectedId,
      });
      storeMappingDraft(localDraft);
      const rebased = rebaseMappingDraft(initial, localDraft);
      const timeout = window.setTimeout(() => {
        setWorkspace(initial);
        setFields(rebased.fields);
        setIntentDrafts(rebased.intentDrafts);
        setDraftMergeConflicts(rebased.conflicts);
        setDraftRecoveryNotice(
          rebased.conflicts.length > 0
            ? `Version ${initial.template.version} changed the same field as your draft. The current version is shown until you choose which value to keep.`
            : `Rebased your unsaved changes onto version ${initial.template.version}.`,
        );
        setVersionRecovery(null);
        setAnnouncement(
          rebased.conflicts.length > 0
            ? `${rebased.conflicts[0]!.fieldLabel} changed in both versions and needs an explicit choice.`
            : `Unsaved mapping changes were rebased onto version ${initial.template.version}.`,
        );
      }, 0);
      return () => window.clearTimeout(timeout);
    }
    const timeout = window.setTimeout(() => {
      setWorkspace(initial);
      setFields(initial.fields);
      setIntentDrafts(intentDraftsFor(initial.fields));
      setDraftMergeConflicts([]);
      setSelectedId((current) =>
        initial.fields.some((item) => item.field.fieldId === current)
          ? current
          : (initial.fields[0]?.field.fieldId ?? ""),
      );
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [dirty, fields, initial, intentDrafts, selectedId, workspace]);

  useEffect(() => {
    if (!dirty || !storageReadyRef.current || draftMergeConflicts.length > 0)
      return;
    storeMappingDraft(
      mappingDraftFor({
        workspace,
        fields,
        intentDrafts,
        selectedFieldId: selectedId,
      }),
    );
  }, [
    dirty,
    draftMergeConflicts.length,
    fields,
    intentDrafts,
    selectedId,
    workspace,
  ]);

  useEffect(() => {
    if (!retryState) return;
    const update = () => {
      const now = Date.now();
      setRetryNowMs(now);
      if (now >= retryState.resetAtMs) setRetryState(null);
    };
    update();
    const interval = window.setInterval(update, 1_000);
    return () => window.clearInterval(interval);
  }, [retryState]);

  useEffect(
    () => () => {
      if (recorderRef.current?.state === "recording")
        recorderRef.current.stop();
      recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
    },
    [],
  );

  const selected =
    fields.find((item) => item.field.fieldId === selectedId) ??
    fields[0] ??
    null;
  const visibleFields = useMemo(
    () =>
      filter === "all"
        ? fields
        : fields.filter(
            (item) =>
              fieldStatus(item, intentDrafts[item.field.fieldId]).tone !==
              "safe",
          ),
    [fields, filter, intentDrafts],
  );
  const confirmedCount = fields.filter((item) =>
    fieldIsConfirmed(item, intentDrafts[item.field.fieldId]),
  ).length;
  const allConfirmed = fields.length > 0 && confirmedCount === fields.length;
  const retrySecondsRemaining = retryState
    ? Math.max(0, Math.ceil((retryState.resetAtMs - retryNowMs) / 1_000))
    : 0;
  const testMatches = Boolean(
    workspace.latestSyntheticTest?.roundTripVerified &&
    workspace.latestSyntheticTest.mappingsSha256 === workspace.mappingsSha256,
  );
  const hasBlockingUnsupported = workspace.stats.blockingUnsupported > 0;
  const coverageByFieldId = new Map(
    workspace.latestSyntheticTest?.fieldCoverage.map((coverage) => [
      coverage.fieldId,
      coverage,
    ]) ?? [],
  );
  const unexercisedFields = testMatches
    ? fields.filter(
        (item) => !coverageByFieldId.get(item.field.fieldId)?.exercised,
      )
    : fields;
  const unexercisedBlockingFields = unexercisedFields.filter(
    (item) =>
      item.field.required ||
      item.field.clinicallyMaterial ||
      item.mapping.required,
  );
  const waivableFields = unexercisedFields.filter(
    (item) =>
      !item.field.required &&
      !item.field.clinicallyMaterial &&
      !item.mapping.required,
  );
  const waiversReady = waivableFields.every(
    (item) => (waiverReasons[item.field.fieldId] ?? "").trim().length >= 10,
  );
  const hasCustomConcepts = fields.some(
    (item) => item.intent.intentKind === "custom_concept",
  );
  const customExamplesReady =
    !hasCustomConcepts || workspace.customExampleCoverage?.ready === true;
  const canCertify =
    workspace.canEdit &&
    !dirty &&
    allConfirmed &&
    testMatches &&
    !hasBlockingUnsupported &&
    unexercisedBlockingFields.length === 0 &&
    waiversReady &&
    customExamplesReady &&
    ackStructure &&
    ackTest &&
    !busy;
  const inventory = useMemo(
    () => ({
      textControls: fields.filter(
        (item) =>
          ["narrative_text", "number", "measurement"].includes(
            item.field.kind,
          ) &&
          ["content_control", "legacy_form_field"].includes(
            item.field.rendererBinding.bindingType,
          ),
      ).length,
      tabOnlyCells: fields.filter(
        (item) =>
          item.field.rendererBinding.bindingProfile ===
          "TAB_ONLY_BLANK_TABLE_CELL_V1",
      ).length,
      placeholders: fields.filter(
        (item) =>
          item.field.rendererBinding.bindingProfile ===
          "ORDINARY_PLACEHOLDER_TOKEN_V1",
      ).length,
    }),
    [fields],
  );

  function updateMapping(fieldId: string, patch: Partial<SemanticMapping>) {
    setFields((current) =>
      current.map((item) =>
        item.field.fieldId === fieldId
          ? {
              ...item,
              mapping: {
                ...item.mapping,
                ...patch,
                ...(stagingQaEnabled
                  ? { approvedSynonyms: [], practiceDefault: null }
                  : {}),
              },
            }
          : item,
      ),
    );
    setDirty(true);
    setFieldErrors((current) =>
      current.filter((error) => error.fieldId !== fieldId),
    );
    setDraftMergeConflicts((current) =>
      current.filter((conflict) => conflict.fieldId !== fieldId),
    );
    setAckStructure(false);
    setAckTest(false);
    setWaiverReasons({});
    setAnnouncement("Mapping changed. Save the draft before running a test.");
  }

  function updateIntent(fieldId: string, intent: FieldIntentDraft) {
    setIntentDrafts((current) => ({ ...current, [fieldId]: intent }));
    setDirty(true);
    setFieldErrors((current) =>
      current.filter((error) => error.fieldId !== fieldId),
    );
    setDraftMergeConflicts((current) =>
      current.filter((conflict) => conflict.fieldId !== fieldId),
    );
    setAckStructure(false);
    setAckTest(false);
    setWaiverReasons({});
    setAnnouncement(
      "Field intent changed. Save this version before running a test.",
    );
  }

  async function saveMappings(): Promise<boolean> {
    if (!workspace.canEdit) return true;
    const currentDraft = mappingDraftFor({
      workspace,
      fields,
      intentDrafts,
      selectedFieldId: selectedId,
    });
    if (draftMergeConflicts.length > 0) {
      setFilter("all");
      setSelectedId(draftMergeConflicts[0]!.fieldId);
      setAnnouncement(
        `${draftMergeConflicts[0]!.fieldLabel} changed in both versions and needs an explicit choice.`,
      );
      toast.error("Resolve the concurrent field change", {
        description: `${draftMergeConflicts[0]!.fieldLabel} changed in both your draft and the current version. Choose which value to keep before saving.`,
      });
      return false;
    }
    storeMappingDraft(currentDraft);
    const localErrors = clientMappingErrors(fields, intentDrafts);
    if (localErrors.length > 0) {
      setFieldErrors(localErrors);
      setFilter("all");
      setSelectedId(localErrors[0]!.fieldId);
      setAnnouncement(
        `${localErrors[0]!.fieldLabel}: ${localErrors[0]!.setting} needs attention.`,
      );
      toast.error("Mapping draft needs attention", {
        description: `${localErrors[0]!.fieldLabel} — ${localErrors[0]!.setting}: ${localErrors[0]!.message}`,
      });
      return false;
    }
    if (retrySecondsRemaining > 0) {
      toast.error("Mapping save is temporarily paused", {
        description: `Retry in ${formatRetryDuration(retrySecondsRemaining)}. Your unsaved draft is safe in this browser tab.`,
      });
      return false;
    }
    setBusy("save");
    setFieldErrors([]);
    setVersionRecovery(null);
    setAnnouncement("Saving semantic mappings.");
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/mappings`,
        {
          method: "PATCH",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            expectedMappingsSha256: workspace.mappingsSha256,
            expectedFieldIntentsSha256: workspace.fieldIntentsSha256,
            mappings: fields.map((item) =>
              stagingQaEnabled
                ? {
                    ...item.mapping,
                    approvedSynonyms: [],
                    practiceDefault: null,
                  }
                : item.mapping,
            ),
            fieldIntents: fields.flatMap((item) => {
              if (
                item.field.rendererBinding.bindingType !==
                "ordinary_placeholder"
              ) {
                return [];
              }
              const intent = intentDrafts[item.field.fieldId] ?? {
                intentKind: "unresolved" as const,
              };
              return [{ fieldId: item.field.fieldId, ...intent }];
            }),
          }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; workspace: TemplateTwinWorkspace }
        | MappingErrorPayload
        | null;
      if (!response.ok || !payload?.ok) {
        const errorPayload = payload && !payload.ok ? payload : null;
        const responseFieldErrors = (errorPayload?.fieldErrors ?? []).map(
          (error) => ({
            ...error,
            fieldLabel:
              fields.find((item) => item.field.fieldId === error.fieldId)?.field
                .originalLabel ?? error.fieldLabel,
            setting: mappingSettingLabel(error.setting),
          }),
        );
        if (responseFieldErrors.length > 0) {
          setFieldErrors(responseFieldErrors);
          setFilter("all");
          setSelectedId(responseFieldErrors[0]!.fieldId);
          setAnnouncement(
            `${responseFieldErrors[0]!.fieldLabel}: ${responseFieldErrors[0]!.setting} needs attention.`,
          );
        }
        if (
          response.status === 429 ||
          errorPayload?.code === "RATE_LIMITED" ||
          (response.status === 503 &&
            errorPayload?.code === "RATE_LIMIT_UNAVAILABLE")
        ) {
          const retryAfterHeader = Number(
            response.headers?.get("Retry-After") ?? Number.NaN,
          );
          const retryAfterSec =
            errorPayload?.retryAfterSec ??
            (Number.isFinite(retryAfterHeader) ? retryAfterHeader : 60);
          const now = Date.now();
          // Retry-After is a server-derived duration from Redis TIME. Anchor
          // the countdown to receipt time instead of comparing the server's
          // wall-clock timestamp with a potentially skewed workstation clock.
          const resetAtMs = now + Math.max(1, retryAfterSec) * 1_000;
          setRetryNowMs(now);
          setRetryState({
            resetAtMs,
            limitType:
              errorPayload?.limitType ??
              (errorPayload?.code === "RATE_LIMIT_UNAVAILABLE"
                ? "safety_check"
                : "mapping-save"),
            ...(errorPayload?.resetAtIso
              ? { serverResetAtIso: errorPayload.resetAtIso }
              : {}),
          });
          const retryIn = Math.max(1, Math.ceil((resetAtMs - now) / 1_000));
          setAnnouncement(
            `Mapping save is available again in ${formatRetryDuration(retryIn)}.`,
          );
          toast.error(
            errorPayload?.code === "RATE_LIMIT_UNAVAILABLE"
              ? "Mapping safety check is temporarily unavailable"
              : "Mappings were not saved",
            {
              description: `Retry in ${formatRetryDuration(retryIn)}. Your unsaved draft is safe in this browser tab.`,
            },
          );
          return false;
        }
        const recoverableVersionFailure =
          errorPayload?.recoverable === true ||
          ["VERSION_CONFLICT", "VERSION_IMMUTABLE", "VERSION_STALE"].includes(
            errorPayload?.code ?? "",
          );
        if (recoverableVersionFailure) {
          setVersionRecovery({
            message:
              errorPayload?.error ??
              "A newer immutable template version is available.",
            ...(errorPayload?.latestWorkspace
              ? { latestWorkspace: errorPayload.latestWorkspace }
              : {}),
            ...(errorPayload?.latestTemplateId
              ? { latestTemplateId: errorPayload.latestTemplateId }
              : {}),
          });
          setAnnouncement(
            "A newer version is available. Your unsaved changes are safe and can be rebased.",
          );
          toast.error("A newer template version is available", {
            description:
              "Your unsaved draft is safe. Refresh and rebase it onto the current version.",
          });
          return false;
        }
        toast.error("Mappings were not saved", {
          description: errorPayload
            ? responseFieldErrors.length > 0
              ? `${responseFieldErrors[0]!.fieldLabel} — ${responseFieldErrors[0]!.setting}: ${responseFieldErrors[0]!.message}`
              : errorPayload.error
            : "Reload the workspace and try again.",
        });
        return false;
      }
      clearStoredMappingDraft(workspace.template.lineageId);
      if (payload.workspace.template.id !== workspace.template.id) {
        router.replace(
          `/settings/note-format/${encodeURIComponent(payload.workspace.template.id)}/certify`,
          { scroll: false },
        );
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setIntentDrafts(intentDraftsFor(payload.workspace.fields));
      setDirty(false);
      setDraftRecoveryNotice(null);
      setVersionRecovery(null);
      setFieldErrors([]);
      setRetryState(null);
      setAckStructure(false);
      setAckTest(false);
      setWaiverReasons({});
      setAnnouncement("Mappings saved.");
      toast.success("Mapping draft saved");
      return true;
    } catch {
      toast.error("Mappings were not saved", {
        description: "Check your connection and try again.",
      });
      return false;
    } finally {
      setBusy(null);
    }
  }

  function recoverAndRebaseDraft() {
    const currentDraft = mappingDraftFor({
      workspace,
      fields,
      intentDrafts,
      selectedFieldId: selectedId,
    });
    storeMappingDraft(currentDraft);
    const latest = versionRecovery?.latestWorkspace;
    const latestTemplateId = versionRecovery?.latestTemplateId;
    const latestWorkspaceIsAuthoritative = Boolean(
      latest &&
      latestTemplateId &&
      latest.template.id === latestTemplateId &&
      latest.canEdit,
    );
    if (latest && latestWorkspaceIsAuthoritative) {
      if (
        latest.template.lineageId !== workspace.template.lineageId ||
        latest.source.sha256 !== workspace.source.sha256
      ) {
        toast.error("Draft cannot be rebased automatically", {
          description:
            "The current version has a different source document. Your tab-scoped draft remains preserved.",
        });
        return;
      }
      const rebased = rebaseMappingDraft(latest, currentDraft);
      setWorkspace(latest);
      setFields(rebased.fields);
      setIntentDrafts(rebased.intentDrafts);
      setDraftMergeConflicts(rebased.conflicts);
      setSelectedId((current) =>
        latest.fields.some((item) => item.field.fieldId === current)
          ? current
          : (latest.fields[0]?.field.fieldId ?? ""),
      );
      setDirty(true);
      setVersionRecovery(null);
      setFieldErrors([]);
      setDraftRecoveryNotice(
        rebased.conflicts.length > 0
          ? `Version ${latest.template.version} changed the same field as your draft. The current value is shown until you choose which value to keep.`
          : `Rebased your unsaved changes onto version ${latest.template.version}.`,
      );
      if (rebased.conflicts.length === 0) {
        storeMappingDraft(
          mappingDraftFor({
            workspace: latest,
            fields: rebased.fields,
            intentDrafts: rebased.intentDrafts,
            selectedFieldId: selectedId,
          }),
        );
      }
      if (latest.template.id !== workspace.template.id) {
        router.replace(
          `/settings/note-format/${encodeURIComponent(latest.template.id)}/certify`,
          { scroll: false },
        );
      }
      setAnnouncement(
        rebased.conflicts.length > 0
          ? `${rebased.conflicts[0]!.fieldLabel} changed in both versions and needs an explicit choice.`
          : `Unsaved changes were rebased onto version ${latest.template.version}.`,
      );
      return;
    }

    if (latestTemplateId && latestTemplateId !== workspace.template.id) {
      router.replace(
        `/settings/note-format/${encodeURIComponent(latestTemplateId)}/certify`,
        { scroll: false },
      );
      setAnnouncement(
        "Opening the current immutable version. Your unsaved changes remain preserved for rebase.",
      );
      return;
    }
    router.refresh();
    setAnnouncement(
      "Refreshing the current immutable version. Your unsaved changes remain preserved for rebase.",
    );
  }

  function resolveDraftMergeConflict(
    fieldId: string,
    resolution: "latest" | "local",
  ) {
    const conflict = draftMergeConflicts.find(
      (candidate) => candidate.fieldId === fieldId,
    );
    if (!conflict) return;

    if (resolution === "local") {
      setFields((current) =>
        current.map((item) => {
          if (item.field.fieldId !== fieldId) return item;
          if (
            conflict.localIntent?.intentKind === "custom_concept" &&
            item.customConceptScaffold
          ) {
            return {
              ...item,
              mapping: {
                ...conflict.localMapping,
                clinicalConcept: item.customConceptScaffold.conceptId,
              },
            };
          }
          return { ...item, mapping: conflict.localMapping };
        }),
      );
      const localIntent = conflict.localIntent;
      if (localIntent) {
        setIntentDrafts((current) => ({
          ...current,
          [fieldId]:
            localIntent.intentKind === "custom_concept"
              ? {
                  intentKind: "custom_concept",
                  customSpec: {
                    ...localIntent.customSpec,
                    ...(fields.find((item) => item.field.fieldId === fieldId)
                      ?.customConceptScaffold ?? {}),
                  },
                }
              : localIntent,
        }));
      }
    }

    const remainingConflicts = draftMergeConflicts.filter(
      (candidate) => candidate.fieldId !== fieldId,
    );
    setDraftMergeConflicts(remainingConflicts);
    setFieldErrors((current) =>
      current.filter((error) => error.fieldId !== fieldId),
    );
    setSelectedId(fieldId);
    setFilter("all");

    let remainsDirtyAfterResolution = true;
    if (resolution === "latest") {
      const remoteIntentDrafts = intentDraftsFor(workspace.fields);
      const hasOtherLocalChanges = fields.some((item) => {
        const remote = workspace.fields.find(
          (candidate) => candidate.field.fieldId === item.field.fieldId,
        );
        return (
          !remote ||
          !draftValuesEqual(item.mapping, remote.mapping) ||
          !draftValuesEqual(
            intentDrafts[item.field.fieldId] ?? null,
            remoteIntentDrafts[item.field.fieldId] ?? null,
          )
        );
      });
      const remainsDirty =
        hasOtherLocalChanges || remainingConflicts.length > 0;
      remainsDirtyAfterResolution = remainsDirty;
      setDirty(remainsDirty);
      if (!remainsDirty) {
        clearStoredMappingDraft(workspace.template.lineageId);
      }
    } else {
      setDirty(true);
    }

    setDraftRecoveryNotice(
      remainingConflicts.length > 0
        ? `${remainingConflicts.length} concurrent field change${remainingConflicts.length === 1 ? " remains" : "s remain"} to resolve.`
        : resolution === "local"
          ? "Your unsaved value is now applied on top of the current version. Review and save when ready."
          : remainsDirtyAfterResolution
            ? "The current version's value was kept. Other unsaved changes remain available."
            : "The current version's value was kept. There are no unsaved mapping changes.",
    );
    setAnnouncement(
      `${conflict.fieldLabel}: ${resolution === "local" ? "your unsaved value" : "the current version"} was kept.`,
    );
  }

  async function loadReviewedSyntheticMappings() {
    if (!stagingQaEnabled || !workspace.canEdit) return;
    setBusy("load-reviewed");
    setAnnouncement("Loading the reviewed synthetic mapping contract.");
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/staging-qa/reviewed-mappings`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | TemplateTwinStagingQaReviewedMappingsResponse
        | MappingErrorPayload
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("Reviewed synthetic mappings were not loaded", {
          description:
            payload && !payload.ok
              ? payload.error
              : "The current draft was left unchanged. Reload and try again.",
        });
        return;
      }
      const reviewed = payload.reviewed;
      const expectedFieldIds = new Set(
        fields.map((item) => item.field.fieldId),
      );
      const reviewedFieldIds = new Set(
        reviewed.mappings.map((mapping) => mapping.fieldId),
      );
      if (
        reviewed.fixture.sha256 !== workspace.source.sha256 ||
        reviewed.template.id !== workspace.template.id ||
        reviewed.expectedMappingsSha256 !== workspace.mappingsSha256 ||
        reviewed.expectedFieldIntentsSha256 !== workspace.fieldIntentsSha256 ||
        reviewedFieldIds.size !== expectedFieldIds.size ||
        [...reviewedFieldIds].some((fieldId) => !expectedFieldIds.has(fieldId))
      ) {
        toast.error("Reviewed synthetic mappings do not match this version", {
          description:
            "Nothing was loaded. Refresh the exact allowlisted fixture version and try again.",
        });
        return;
      }
      const mappingByFieldId = new Map(
        reviewed.mappings.map((mapping) => [mapping.fieldId, mapping]),
      );
      const nextFields = fields.map((item) => ({
        ...item,
        mapping: mappingByFieldId.get(item.field.fieldId) ?? item.mapping,
      }));
      const nextIntentDrafts = { ...intentDrafts };
      for (const fieldIntent of reviewed.fieldIntents) {
        const { fieldId, ...intent } = fieldIntent;
        if (!expectedFieldIds.has(fieldId)) {
          toast.error("Reviewed synthetic intent does not match this version", {
            description: "Nothing was loaded. Refresh and try again.",
          });
          return;
        }
        nextIntentDrafts[fieldId] = intent;
      }
      setFields(nextFields);
      setIntentDrafts(nextIntentDrafts);
      setReviewedMappingSummary(reviewed.physicianReviewSummary);
      setDirty(true);
      setFieldErrors([]);
      setVersionRecovery(null);
      setDraftRecoveryNotice(
        "The reviewed synthetic mapping set is loaded as an unsaved draft. Activation has not occurred.",
      );
      setAckStructure(false);
      setAckTest(false);
      setWaiverReasons({});
      storeMappingDraft(
        mappingDraftFor({
          workspace,
          fields: nextFields,
          intentDrafts: nextIntentDrafts,
          selectedFieldId: selectedId,
        }),
      );
      setAnnouncement(
        "Eight reviewed synthetic mappings were loaded as an unsaved draft. Physician review and explicit activation are still required.",
      );
      toast.success("Reviewed synthetic mappings loaded");
    } catch {
      toast.error("Reviewed synthetic mappings were not loaded", {
        description:
          "The current draft was left unchanged. Check your connection and try again.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function runSyntheticTest() {
    if (dirty) {
      toast.error("Save mapping changes first");
      return;
    }
    setBusy("test");
    setAnnouncement(
      "Resolving synthetic evidence and verifying a cloned DOCX.",
    );
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/synthetic-test`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            expectedMappingsSha256: workspace.mappingsSha256,
            expectedFieldIntentsSha256: workspace.fieldIntentsSha256,
            encounterText: syntheticText,
          }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; workspace: TemplateTwinWorkspace }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("Synthetic DOCX did not verify", {
          description:
            payload && !payload.ok
              ? payload.error
              : "No template was activated. Review the mappings and try again.",
        });
        return;
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setIntentDrafts(intentDraftsFor(payload.workspace.fields));
      setAckStructure(false);
      setAckTest(false);
      setWaiverReasons({});
      setAnnouncement(
        "Synthetic DOCX passed package, field, and static-region verification.",
      );
      toast.success("Synthetic DOCX verified");
    } catch {
      toast.error("Synthetic test did not finish", {
        description:
          "No template was activated. Check your connection and try again.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function toggleSyntheticRecording() {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      toast.error("Voice recording is not available in this browser");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const requestedMime = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
      ].find((candidate) => MediaRecorder.isTypeSupported(candidate));
      const recorder = requestedMime
        ? new MediaRecorder(stream, { mimeType: requestedMime })
        : new MediaRecorder(stream);
      const mimeType = recorder.mimeType || requestedMime || "audio/webm";
      recordingStreamRef.current = stream;
      recorderRef.current = recorder;
      recordingChunksRef.current = [];
      setSyntheticVoice(null);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordingChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(recordingChunksRef.current, { type: mimeType });
        setSyntheticVoice(blob.size > 0 ? blob : null);
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        recordingStreamRef.current = null;
        recorderRef.current = null;
      };
      recorder.start(500);
      setRecording(true);
      setAnnouncement(
        "Recording synthetic voice evidence. Do not use real patient information.",
      );
    } catch {
      toast.error("Microphone access was not granted");
    }
  }

  async function runSyntheticVoiceTest() {
    if (dirty) {
      toast.error("Save mapping changes first");
      return;
    }
    if (!syntheticVoice) {
      toast.error("Record synthetic voice evidence first");
      return;
    }
    setBusy("test");
    setAnnouncement(
      "Transcribing synthetic voice evidence and verifying a cloned DOCX.",
    );
    try {
      const form = new FormData();
      form.append(
        "audio",
        new File(
          [syntheticVoice],
          syntheticVoice.type.startsWith("audio/mp4")
            ? "synthetic-template-test.m4a"
            : "synthetic-template-test.webm",
          {
            type: syntheticVoice.type || "audio/webm",
          },
        ),
      );
      form.append("expectedMappingsSha256", workspace.mappingsSha256);
      form.append("expectedFieldIntentsSha256", workspace.fieldIntentsSha256);
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/synthetic-test-voice`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          body: form,
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; workspace: TemplateTwinWorkspace }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("Synthetic voice DOCX did not verify", {
          description:
            payload && !payload.ok
              ? payload.error
              : "No template was activated. Review the recording and mappings.",
        });
        return;
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setIntentDrafts(intentDraftsFor(payload.workspace.fields));
      setAckStructure(false);
      setAckTest(false);
      setWaiverReasons({});
      setAnnouncement(
        "Synthetic voice path passed transcript, field, package, and static-region verification.",
      );
      toast.success("Synthetic voice DOCX verified");
    } catch {
      toast.error("Synthetic voice test did not finish", {
        description:
          "No template was activated. Check your connection and try again.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function runCustomExamples() {
    setBusy("custom-examples");
    setAnnouncement("Running every custom-field certification example.");
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/custom-examples`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ action: "run" }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | {
            ok: true;
            coverage: NonNullable<
              TemplateTwinWorkspace["customExampleCoverage"]
            >;
          }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("Custom-field examples did not pass", {
          description:
            payload && !payload.ok
              ? payload.error
              : "No example review was recorded.",
        });
        return;
      }
      setWorkspace((current) => ({
        ...current,
        customExampleCoverage: payload.coverage,
      }));
      setAckStructure(false);
      setAckTest(false);
      setAnnouncement(
        `${payload.coverage.passedCount} of ${payload.coverage.requiredCount} custom-field examples passed. Review and acknowledge the results.`,
      );
    } catch {
      toast.error("Custom-field examples did not finish", {
        description:
          "No example review was recorded. Check your connection and try again.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function acknowledgeCustomExamples() {
    const batchId = workspace.customExampleCoverage?.latestBatchId;
    if (!batchId) return;
    setBusy("ack-custom-examples");
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/custom-examples`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({ action: "acknowledge", batchId }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | {
            ok: true;
            coverage: NonNullable<
              TemplateTwinWorkspace["customExampleCoverage"]
            >;
          }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("Example review was not recorded", {
          description:
            payload && !payload.ok ? payload.error : "Reload and try again.",
        });
        return;
      }
      setWorkspace((current) => ({
        ...current,
        customExampleCoverage: payload.coverage,
      }));
      setAnnouncement(
        "Every current custom-field example is passed and physician-reviewed.",
      );
      toast.success("Custom-field examples reviewed");
    } catch {
      toast.error("Example review was not recorded", {
        description: "Check your connection and try again.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function certify() {
    if (!canCertify) return;
    setBusy("certify");
    setAnnouncement(
      "Certifying and activating this immutable template version.",
    );
    try {
      const response = await fetch(
        `/api/note-templates/template-twin/${encodeURIComponent(workspace.template.id)}/certify`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            expectedMappingsSha256: workspace.mappingsSha256,
            expectedFieldIntentsSha256: workspace.fieldIntentsSha256,
            expectedSyntheticTestProvenanceSha256:
              workspace.latestSyntheticTest!.provenanceSha256,
            acknowledgeStructure: true,
            acknowledgeSyntheticOutput: true,
            optionalFieldWaivers: waivableFields.map((item) => ({
              fieldId: item.field.fieldId,
              reason: waiverReasons[item.field.fieldId]!.trim(),
            })),
          }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; workspace: TemplateTwinWorkspace }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("Template was not certified", {
          description:
            payload && !payload.ok
              ? payload.error
              : "Nothing was activated. Reload and try again.",
        });
        return;
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setIntentDrafts(intentDraftsFor(payload.workspace.fields));
      setAnnouncement("Template version certified and activated.");
      toast.success("Original Word template activated");
      router.refresh();
    } catch {
      toast.error("Template was not certified", {
        description:
          "Nothing was activated. Check your connection and try again.",
      });
    } finally {
      setBusy(null);
    }
  }

  async function startStagingRun(mode: "typed" | "mock_voice") {
    if (workspace.template.certificationStatus !== "certified") {
      toast.error("Certify this exact template version first");
      return;
    }
    if (mode === "typed" && stagingEncounterText.trim().length < 20) {
      toast.error("Add a clearly synthetic encounter before starting");
      return;
    }
    if (typeof crypto.randomUUID !== "function") {
      toast.error("This browser cannot create a replay-safe staging request");
      return;
    }
    const idempotencyKey = stagingRunKeyRef.current ?? crypto.randomUUID();
    stagingRunKeyRef.current = idempotencyKey;
    setBusy("staging-run");
    setAnnouncement(
      mode === "typed"
        ? "Creating a typed synthetic staging visit."
        : "Creating a mocked-voice synthetic staging visit.",
    );
    try {
      const response = await fetch(
        "/api/note-templates/template-twin/staging-qa/runs",
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            templateId: workspace.template.id,
            mode,
            idempotencyKey,
            expectedTemplateVersion: workspace.template.version,
            ...(mode === "typed"
              ? { encounterText: stagingEncounterText.trim() }
              : {}),
          }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | {
            ok: true;
            run: {
              runId: string;
              visitId: string;
              reused: boolean;
            };
            visitUrl: string;
          }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        throw new Error(
          payload && !payload.ok
            ? payload.error
            : "The synthetic visit could not be created.",
        );
      }
      stagingRunKeyRef.current = null;
      setAnnouncement(
        payload.run.reused
          ? "The existing synthetic run was recovered without creating a duplicate."
          : "Synthetic visit queued through the staging worker.",
      );
      router.push(payload.visitUrl);
    } catch (caught) {
      toast.error("Synthetic staging visit did not start", {
        description:
          caught instanceof Error
            ? caught.message
            : "No duplicate run was created. Try again safely.",
      });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className={styles.shell}>
      <div className="sr-only" role="status" aria-live="polite">
        {announcement}
      </div>

      {stagingQaEnabled && (
        <div className={styles.syntheticBanner}>
          <TemplateTwinSyntheticQaBanner />
        </div>
      )}

      <header className={styles.header}>
        <div className={styles.eyebrow}>
          Settings / Note format / Template Twin
        </div>
        <div className={styles.titleRow}>
          <div>
            <h1 className={styles.title}>{workspace.template.name}</h1>
            <p className={styles.subtitle}>
              Version {workspace.template.version} · Original Word layout ·
              Every clinical fill must retain encounter evidence.
            </p>
          </div>
          <div className={styles.headerActions}>
            <span
              className={styles.status}
              data-tone={
                workspace.template.certificationStatus === "certified"
                  ? "safe"
                  : "review"
              }
            >
              {titleCase(workspace.template.certificationStatus)}
            </span>
            <a
              href="/settings"
              className={styles.button}
              style={{ textDecoration: "none" }}
            >
              Back to settings
            </a>
          </div>
        </div>
      </header>

      {draftRecoveryNotice && (
        <section className={styles.callout} role="status">
          <strong>Unsaved mapping draft preserved</strong>
          <div style={{ marginTop: 4 }}>{draftRecoveryNotice}</div>
        </section>
      )}

      {versionRecovery && (
        <section className={styles.callout} data-tone="block" role="alert">
          <strong>A newer immutable version is available</strong>
          <div style={{ marginTop: 4 }}>{versionRecovery.message}</div>
          <div style={{ marginTop: 4 }}>
            Your unsaved changes are safe in this browser tab. Refresh and
            rebase them onto the current version; no field-by-field work will be
            discarded.
          </div>
          <button
            type="button"
            className={styles.button}
            style={{ marginTop: 10 }}
            onClick={recoverAndRebaseDraft}
            disabled={busy !== null}
          >
            Refresh and rebase unsaved draft
          </button>
        </section>
      )}

      {draftMergeConflicts.length > 0 && (
        <section className={styles.callout} data-tone="block" role="alert">
          <strong>Resolve concurrent field changes</strong>
          <div style={{ marginTop: 4 }}>
            The current version and your unsaved draft changed the same field.
            The current version is shown and neither value will be overwritten
            until you choose explicitly.
          </div>
          <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
            {draftMergeConflicts.map((conflict) => (
              <li key={conflict.fieldId}>
                <strong>{conflict.fieldLabel}</strong>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    flexWrap: "wrap",
                    marginTop: 6,
                  }}
                >
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() =>
                      resolveDraftMergeConflict(conflict.fieldId, "latest")
                    }
                  >
                    Keep current version for {conflict.fieldLabel}
                  </button>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() =>
                      resolveDraftMergeConflict(conflict.fieldId, "local")
                    }
                  >
                    Use my unsaved draft for {conflict.fieldLabel}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {retryState && retrySecondsRemaining > 0 && (
        <section className={styles.callout} role="status">
          <strong>
            Mapping save available in{" "}
            {formatRetryDuration(retrySecondsRemaining)}
          </strong>
          <div style={{ marginTop: 4 }}>
            This {retryState.limitType.replaceAll("_", " ")} retry state resets
            at{" "}
            {new Date(
              retryState.serverResetAtIso ?? retryState.resetAtMs,
            ).toLocaleTimeString()}
            . Your unsaved draft remains safe in this browser tab.
          </div>
        </section>
      )}

      {fieldErrors.length > 0 && (
        <section className={styles.callout} data-tone="block" role="alert">
          <strong>Review these exact mapping settings</strong>
          <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
            {fieldErrors.map((error) => (
              <li key={`${error.fieldId}:${error.setting}`}>
                <button
                  type="button"
                  className={styles.button}
                  style={{ margin: "3px 0" }}
                  onClick={() => {
                    setFilter("all");
                    setSelectedId(error.fieldId);
                  }}
                >
                  {error.fieldLabel} — {error.setting}
                </button>{" "}
                {error.message}
              </li>
            ))}
          </ul>
        </section>
      )}

      {stagingQaEnabled && (
        <section
          className={styles.guidedIntro}
          aria-labelledby="template-twin-guided-workflow"
        >
          <div>
            <h2
              id="template-twin-guided-workflow"
              className={styles.sectionTitle}
            >
              One-time physician setup
            </h2>
            <ol className={styles.stepList}>
              <li>Inspect the uploaded DOCX and every detected field.</li>
              <li>Confirm clinical meaning; no answer is selected for you.</li>
              <li>Test every material field with synthetic evidence.</li>
              <li>Certify this immutable version, then run a staging visit.</li>
            </ol>
          </div>
          <dl
            className={styles.admissionGrid}
            aria-label="Source inspection results"
          >
            {workspace.admissionChecks.map((check) => (
              <div key={check.id} className={styles.admissionItem}>
                <dt>
                  {check.label}
                  <span
                    className={styles.status}
                    data-tone={
                      check.status === "passed"
                        ? "safe"
                        : check.status === "blocked"
                          ? "block"
                          : "review"
                    }
                  >
                    {titleCase(check.status)}
                  </span>
                </dt>
                <dd>{check.detail}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {stagingQaEnabled && workspace.canEdit && (
        <section className={styles.guidedIntro} aria-label="Reviewed mappings">
          <div>
            <h2 className={styles.sectionTitle}>
              Reviewed synthetic mapping set
            </h2>
            <p className={styles.fieldMeta}>
              Available only for this exact byte-allowlisted synthetic fixture.
              Loading creates an unsaved local draft; it never saves, tests,
              certifies, or activates a template.
            </p>
            <button
              type="button"
              className={styles.button}
              onClick={() => void loadReviewedSyntheticMappings()}
              disabled={busy !== null}
            >
              {busy === "load-reviewed"
                ? "Loading reviewed mappings…"
                : "Load reviewed synthetic mappings"}
            </button>
          </div>
          {reviewedMappingSummary ? (
            <div className={styles.callout} role="status">
              <strong>{reviewedMappingSummary.title}</strong>
              <div style={{ marginTop: 4 }}>
                {reviewedMappingSummary.fixtureLabel} ·{" "}
                {reviewedMappingSummary.fieldCount} reviewed fields
              </div>
              <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                {reviewedMappingSummary.fields.map((field) => (
                  <li key={field.fieldId}>
                    {field.fieldLabel} → {field.clinicalDetailLabel} ·{" "}
                    {titleCase(field.settings.expectedDataType)} ·{" "}
                    {field.settings.requiredBeforeSigning
                      ? "required before signing"
                      : "optional"}
                  </li>
                ))}
              </ul>
              <div className={styles.fieldMeta} style={{ marginTop: 8 }}>
                Approved synonyms:{" "}
                {reviewedMappingSummary.settings.approvedSynonyms}
                {" · "}Practice defaults:{" "}
                {reviewedMappingSummary.settings.practiceDefaults}
                {" · "}When missing:{" "}
                {titleCase(
                  reviewedMappingSummary.settings.missingClinicalDetail,
                )}
              </div>
              <p className={styles.warningText} role="alert">
                Activation has not occurred. Save and test this draft, inspect
                the synthetic output, complete both physician acknowledgements,
                and explicitly choose Certify &amp; activate.
              </p>
            </div>
          ) : (
            <div className={styles.callout}>
              No reviewed mappings are loaded. Current field decisions are
              unchanged.
            </div>
          )}
        </section>
      )}

      <section
        className={styles.summary}
        aria-label="Detected structure summary"
      >
        <Metric label="Fields" value={workspace.stats.totalFields} />
        <Metric label="Dropdowns" value={workspace.stats.dropdowns} />
        <Metric label="Combo boxes" value={workspace.stats.comboBoxes} />
        <Metric label="Checkboxes" value={workspace.stats.checkboxes} />
        <Metric label="Dates" value={workspace.stats.dateControls} />
        <Metric label="Text controls" value={inventory.textControls} />
        <Metric label="Tables" value={workspace.stats.tables} />
        <Metric label="Tab-only cells" value={inventory.tabOnlyCells} />
        <Metric label="Placeholders" value={inventory.placeholders} />
        <Metric label="Unsupported" value={workspace.stats.unsupported} />
        <Metric
          label="Confirmed"
          value={`${confirmedCount}/${fields.length}`}
        />
      </section>

      <div className={styles.workspace}>
        <aside className={styles.rail} aria-label="Template fields">
          <div className={styles.railHeader}>
            <div className={styles.filterRow}>
              <button
                type="button"
                className={styles.filterButton}
                data-active={filter === "all"}
                onClick={() => setFilter("all")}
              >
                All fields
              </button>
              <button
                type="button"
                className={styles.filterButton}
                data-active={filter === "attention"}
                onClick={() => setFilter("attention")}
              >
                Needs attention
              </button>
            </div>
          </div>
          <nav className={styles.fieldList} aria-label="Detected fields">
            {visibleFields.map((item) => (
              <button
                key={item.field.fieldId}
                type="button"
                aria-current={
                  item.field.fieldId === selected?.field.fieldId
                    ? "true"
                    : undefined
                }
                className={styles.fieldButton}
                data-selected={item.field.fieldId === selected?.field.fieldId}
                onClick={() => setSelectedId(item.field.fieldId)}
              >
                <span style={{ minWidth: 0 }}>
                  <span className={styles.fieldLabel}>
                    {item.field.originalLabel}
                  </span>
                  <span className={styles.fieldMeta}>
                    {titleCase(item.field.kind)} · Field{" "}
                    {item.field.displayOrder + 1}
                  </span>
                </span>
                <StatusPill
                  item={item}
                  intentDraft={intentDrafts[item.field.fieldId]}
                />
              </button>
            ))}
            {visibleFields.length === 0 && (
              <div className={styles.empty}>
                Every detected field is confirmed.
              </div>
            )}
          </nav>
        </aside>

        <section
          className={styles.inspector}
          aria-label="Selected field inspector"
        >
          <div className={styles.inspectorInner}>
            {selected ? (
              <FieldInspector
                item={selected}
                canEdit={workspace.canEdit}
                busy={busy !== null}
                stagingQaMode={stagingQaEnabled}
                intentDraft={
                  intentDrafts[selected.field.fieldId] ?? {
                    intentKind: "unresolved",
                  }
                }
                onChange={(patch) =>
                  updateMapping(selected.field.fieldId, patch)
                }
                onIntentChange={(intent) =>
                  updateIntent(selected.field.fieldId, intent)
                }
              />
            ) : (
              <div className={styles.empty}>
                No fillable fields were detected.
              </div>
            )}

            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>
                Unsupported and ambiguous structure
              </h2>
              {workspace.unsupported.length === 0 ? (
                <div className={styles.callout}>
                  No structures outside the supported safe-alpha profile were
                  found.
                </div>
              ) : (
                <div style={{ display: "grid", gap: 8 }}>
                  {workspace.unsupported.map((item, index) => (
                    <div
                      key={`${item.partName}:${item.path}:${index}`}
                      className={styles.callout}
                      data-tone={item.blocksCertification ? "block" : undefined}
                    >
                      <strong
                        style={{
                          color: "var(--color-linear-text)",
                          fontWeight: 600,
                        }}
                      >
                        {item.label || titleCase(item.code)}
                      </strong>
                      <div style={{ marginTop: 3 }}>{item.detail}</div>
                      <div
                        className={styles.fieldMeta}
                        style={{ marginTop: 6 }}
                      >
                        {item.blocksCertification
                          ? "Blocks certification"
                          : "Review warning"}
                      </div>
                      <details
                        className={styles.fieldMeta}
                        style={{ marginTop: 7 }}
                      >
                        <summary style={{ cursor: "pointer" }}>
                          Advanced document details
                        </summary>
                        <div style={{ marginTop: 5, overflowWrap: "anywhere" }}>
                          Code: {item.code} · Part: {item.partName} · Location:{" "}
                          {item.path}
                        </div>
                      </details>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {hasCustomConcepts && (
              <div className={styles.section}>
                <h2 className={styles.sectionTitle}>
                  Custom-field safety examples
                </h2>
                <div className={styles.callout}>
                  QuillMD runs every positive, negative, and unclear synthetic
                  example you approved through the same extractor used for typed
                  and voice visits. Activation stays blocked until every current
                  example passes and you review the results.
                </div>
                <div className={styles.testStatus} style={{ marginTop: 12 }}>
                  <span>
                    {workspace.customExampleCoverage
                      ? `${workspace.customExampleCoverage.passedCount}/${workspace.customExampleCoverage.requiredCount} passed · ${workspace.customExampleCoverage.acknowledgedCount}/${workspace.customExampleCoverage.requiredCount} reviewed`
                      : "Examples have not been run for this version"}
                  </span>
                  <div className={styles.voiceActions}>
                    <button
                      type="button"
                      className={styles.button}
                      onClick={() => void runCustomExamples()}
                      disabled={dirty || busy !== null || !allConfirmed}
                    >
                      {busy === "custom-examples"
                        ? "Running…"
                        : "Run all examples"}
                    </button>
                    <button
                      type="button"
                      className={styles.primaryButton}
                      onClick={() => void acknowledgeCustomExamples()}
                      disabled={
                        busy !== null ||
                        !workspace.customExampleCoverage?.latestBatchId ||
                        workspace.customExampleCoverage.passedCount !==
                          workspace.customExampleCoverage.requiredCount ||
                        workspace.customExampleCoverage.stale ||
                        workspace.customExampleCoverage.ready
                      }
                    >
                      {busy === "ack-custom-examples"
                        ? "Recording review…"
                        : "I reviewed these results"}
                    </button>
                  </div>
                </div>
                {workspace.customExampleCoverage?.examples.map((example) => {
                  const expected =
                    example.exampleKind === "positive"
                      ? `Exact ${example.expectedStatus === "explicitly_denied" ? "denied" : "supported"} result: ${String(example.expectedValue)}${example.expectedUnit ? ` ${example.expectedUnit}` : ""}`
                      : example.exampleKind === "negative"
                        ? example.prohibitedValue === null
                          ? "No renderable value"
                          : `Must not produce: ${String(example.prohibitedValue)}`
                        : `Must return unclear or conflict; possible values: ${example.possibleValues.map(String).join(", ")}`;
                  return (
                    <div
                      key={`${example.fieldId}:${example.exampleKind}:${example.exampleId}`}
                      className={styles.callout}
                      data-tone={example.passed ? undefined : "block"}
                      style={{ marginTop: 9 }}
                    >
                      <strong>
                        {example.physicianName} ·{" "}
                        {titleCase(example.exampleKind)}
                      </strong>
                      <div style={{ marginTop: 5 }}>
                        <span className={styles.monoLabel}>
                          Synthetic evidence
                        </span>
                        <div>“{example.syntheticEvidence}”</div>
                      </div>
                      <div
                        className={styles.fieldMeta}
                        style={{ marginTop: 6 }}
                      >
                        Expected: {expected}
                      </div>
                      <div
                        className={styles.fieldMeta}
                        style={{ marginTop: 3 }}
                      >
                        Actual:{" "}
                        {example.actualStatus
                          ? titleCase(example.actualStatus)
                          : "Not run"}
                        {example.actualValue !== null
                          ? ` · ${String(example.actualValue)}${example.actualUnit ? ` ${example.actualUnit}` : ""}`
                          : ""}
                        {` · ${example.actualEvidenceAnchorCount} evidence anchor${example.actualEvidenceAnchorCount === 1 ? "" : "s"} · ${example.actualSourceFactCount} source fact${example.actualSourceFactCount === 1 ? "" : "s"}`}
                      </div>
                      <div
                        className={styles.fieldMeta}
                        style={{ marginTop: 3 }}
                      >
                        {example.passed
                          ? "Passed"
                          : `Needs attention${example.failureCode ? ` · ${example.failureCode}` : ""}`}{" "}
                        ·{" "}
                        {example.acknowledged ? "Reviewed" : "Not yet reviewed"}
                      </div>
                    </div>
                  );
                })}
                {workspace.customExampleCoverage?.stale && (
                  <p className={styles.warningText} role="alert">
                    The saved results do not match the current field meaning or
                    mapping. Run every example again.
                  </p>
                )}
              </div>
            )}

            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>Synthetic evidence test</h2>
              <div className={styles.callout}>
                Use synthetic details only. This test runs the same fact
                resolver and exact renderer used by voice and typed visits, then
                reopens the DOCX and verifies fields and untouched regions.
              </div>
              {stagingQaEnabled && (
                <div className={styles.voiceTest}>
                  <div>
                    <strong>Reviewed synthetic evidence fixture</strong>
                    <p>
                      This visible starter is the only typed evidence accepted
                      by the bounded staging provider. It supplies synthetic
                      encounter facts only and does not confirm any field
                      meaning or physician mapping.
                    </p>
                  </div>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() =>
                      setSyntheticText(TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER)
                    }
                    disabled={!workspace.canEdit || busy !== null}
                  >
                    Restore reviewed certification evidence
                  </button>
                </div>
              )}
              <label
                className={`${styles.field} ${styles.fieldWide}`}
                style={{ marginTop: 12 }}
              >
                <span className={styles.monoLabel}>
                  Synthetic encounter text
                </span>
                <textarea
                  className={styles.textarea}
                  value={syntheticText}
                  onChange={(event) => setSyntheticText(event.target.value)}
                  disabled={!workspace.canEdit || busy !== null}
                />
              </label>
              <div className={styles.voiceTest}>
                <div>
                  <strong>Or test the voice path</strong>
                  <p>
                    Record a short synthetic dictation and explicitly say that
                    it is a synthetic test. Audio is sent through the existing
                    transcription provider and is not stored by QuillMD;
                    transcripts containing identifiers or unclear test data are
                    rejected before persistence.
                  </p>
                </div>
                <div className={styles.voiceActions}>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() => void toggleSyntheticRecording()}
                    disabled={!workspace.canEdit || busy !== null}
                  >
                    {recording
                      ? "Stop recording"
                      : syntheticVoice
                        ? "Record again"
                        : "Record synthetic voice"}
                  </button>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() => void runSyntheticVoiceTest()}
                    disabled={
                      !syntheticVoice ||
                      recording ||
                      dirty ||
                      busy !== null ||
                      !allConfirmed ||
                      hasBlockingUnsupported
                    }
                  >
                    Verify voice test
                  </button>
                  {syntheticVoice && !recording && (
                    <span className={styles.fieldMeta}>
                      Synthetic recording ready
                    </span>
                  )}
                </div>
              </div>
              {workspace.latestSyntheticTest && (
                <div>
                  <div className={styles.testStatus}>
                    <span>
                      {testMatches
                        ? "Verified against current mappings"
                        : "Re-run required after mapping changes"}
                    </span>
                    <a
                      className={styles.button}
                      href={workspace.latestSyntheticTest.downloadUrl}
                      style={{ textDecoration: "none" }}
                    >
                      Inspect filled DOCX
                    </a>
                  </div>
                  <div className={styles.evidenceGrid}>
                    <div>
                      <h3 className={styles.monoLabel}>
                        Extracted synthetic facts
                      </h3>
                      {workspace.latestSyntheticTest.facts.length === 0 ? (
                        <p className={styles.fieldMeta}>
                          No source facts were extracted.
                        </p>
                      ) : (
                        <ul className={styles.evidenceList}>
                          {workspace.latestSyntheticTest.facts.map((fact) => (
                            <li key={fact.factId}>
                              <strong>{titleCase(fact.concept)}</strong>
                              <span>
                                {displaySyntheticValue(fact.value)} ·{" "}
                                {titleCase(fact.polarity)}
                              </span>
                              <blockquote>“{fact.evidenceQuote}”</blockquote>
                              <small>
                                {fact.evidenceAnchorIds.length} evidence anchor
                                {fact.evidenceAnchorIds.length === 1 ? "" : "s"}
                                {fact.audioTimestampSeconds !== null
                                  ? ` · audio ${Math.floor(fact.audioTimestampSeconds / 60)}:${String(Math.floor(fact.audioTimestampSeconds % 60)).padStart(2, "0")}`
                                  : ""}
                                {` · ${titleCase(fact.quality.evidence)}`}
                              </small>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div>
                      <h3 className={styles.monoLabel}>
                        Field resolution preview
                      </h3>
                      <ul className={styles.resolutionList}>
                        {workspace.latestSyntheticTest.fieldResults.map(
                          (result) => {
                            const field = fields.find(
                              (item) => item.field.fieldId === result.fieldId,
                            );
                            return (
                              <li key={result.fieldId}>
                                <span>
                                  {field?.field.originalLabel ?? result.fieldId}
                                </span>
                                <span
                                  className={styles.status}
                                  data-tone={
                                    result.status === "supported" ||
                                    result.status === "explicitly_denied" ||
                                    result.status ===
                                      "approved_practice_default"
                                      ? "safe"
                                      : result.status === "conflict"
                                        ? "block"
                                        : "review"
                                  }
                                >
                                  {titleCase(result.status)}
                                </span>
                                <small>
                                  {displaySyntheticValue(result.value)} ·{" "}
                                  {result.sourceFactIds.length} source fact
                                  {result.sourceFactIds.length === 1 ? "" : "s"}
                                </small>
                              </li>
                            );
                          },
                        )}
                      </ul>
                    </div>
                  </div>
                  {workspace.latestSyntheticTest.layoutWarningCodes.length >
                    0 && (
                    <p className={styles.warningText} role="alert">
                      Word layout review required: the test contains unusually
                      long populated text or repeated table rows. Inspect
                      pagination, row styles, and spacing in Word before
                      certification.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>Physician certification</h2>
              {unexercisedBlockingFields.length > 0 && (
                <div className={styles.warningText} role="alert">
                  <strong>More synthetic evidence is required.</strong>{" "}
                  {unexercisedBlockingFields.length} required or clinically
                  meaningful field
                  {unexercisedBlockingFields.length === 1 ? "" : "s"} did not
                  receive a verified test value. Re-run the synthetic test with
                  direct evidence for each field; these fields cannot be waived.
                </div>
              )}
              {waivableFields.length > 0 && (
                <div className={styles.formGrid}>
                  <div className={`${styles.field} ${styles.fieldWide}`}>
                    <strong>Optional fields not exercised</strong>
                    <p className={styles.fieldMeta}>
                      Explain why each optional field is intentionally outside
                      this test. The waiver is recorded with your identity and
                      this exact mapping version.
                    </p>
                  </div>
                  {waivableFields.map((item) => (
                    <label
                      key={item.field.fieldId}
                      className={`${styles.field} ${styles.fieldWide}`}
                    >
                      <span className={styles.monoLabel}>
                        {item.field.originalLabel}
                      </span>
                      <textarea
                        className={styles.textarea}
                        value={waiverReasons[item.field.fieldId] ?? ""}
                        onChange={(event) => {
                          setWaiverReasons((current) => ({
                            ...current,
                            [item.field.fieldId]: event.target.value,
                          }));
                          setAckStructure(false);
                          setAckTest(false);
                        }}
                        minLength={10}
                        maxLength={500}
                        rows={2}
                        disabled={!workspace.canEdit || busy !== null}
                        placeholder="Why is this optional field not part of the certified workflow?"
                      />
                    </label>
                  ))}
                </div>
              )}
              <div className={styles.checkList}>
                <label className={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={ackStructure}
                    onChange={(event) => setAckStructure(event.target.checked)}
                    disabled={!workspace.canEdit}
                  />
                  I reviewed every detected field and every unsupported item in
                  this exact template version.
                </label>
                <label className={styles.checkLabel}>
                  <input
                    type="checkbox"
                    checked={ackTest}
                    onChange={(event) => setAckTest(event.target.checked)}
                    disabled={!workspace.canEdit}
                  />
                  I inspected the synthetic filled copy and approve its
                  mappings, blank policies, and structure.
                </label>
              </div>
            </div>

            {stagingQaEnabled && (
              <>
                <div className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    Run a synthetic staging visit
                  </h2>
                  <div className={styles.callout}>
                    This step uses the authenticated visit route, tenant-scoped
                    database, queue, worker, object storage, exact DOCX
                    renderer, and strict verification contract. It does not call
                    a live voice or clinical model provider.
                  </div>
                  <div className={styles.voiceTest}>
                    <div>
                      <strong>Reviewed typed visit fixture</strong>
                      <p>
                        Load the exact bounded synthetic evidence used by the
                        mocked-voice path. This action never selects clinical
                        field meanings or certifies mappings.
                      </p>
                    </div>
                    <button
                      type="button"
                      className={styles.button}
                      onClick={() =>
                        setStagingEncounterText(
                          TEMPLATE_TWIN_STAGING_QA_TYPED_STARTER,
                        )
                      }
                      disabled={
                        workspace.template.certificationStatus !==
                          "certified" || busy !== null
                      }
                    >
                      Restore reviewed visit evidence
                    </button>
                  </div>
                  <label
                    className={`${styles.field} ${styles.fieldWide}`}
                    style={{ marginTop: 12 }}
                  >
                    <span className={styles.monoLabel}>
                      Typed synthetic encounter
                    </span>
                    <textarea
                      className={styles.textarea}
                      value={stagingEncounterText}
                      onChange={(event) =>
                        setStagingEncounterText(event.target.value)
                      }
                      placeholder="Example format only: Synthetic encounter. State each synthetic symptom, denial, date, side, number, and unit needed by this template."
                      minLength={20}
                      maxLength={5_000}
                      disabled={
                        workspace.template.certificationStatus !==
                          "certified" || busy !== null
                      }
                    />
                  </label>
                  <p className={styles.fieldMeta} style={{ marginTop: 7 }}>
                    No clinical answer is preselected. Use synthetic details
                    only.
                  </p>
                  <div
                    className={styles.voiceActions}
                    style={{ marginTop: 12 }}
                  >
                    <button
                      type="button"
                      className={styles.primaryButton}
                      disabled={
                        workspace.template.certificationStatus !==
                          "certified" ||
                        stagingEncounterText.trim().length < 20 ||
                        busy !== null
                      }
                      onClick={() => void startStagingRun("typed")}
                    >
                      {busy === "staging-run"
                        ? "Starting synthetic visit…"
                        : "Start typed synthetic visit"}
                    </button>
                    <button
                      type="button"
                      className={styles.button}
                      disabled={
                        workspace.template.certificationStatus !==
                          "certified" || busy !== null
                      }
                      onClick={() => void startStagingRun("mock_voice")}
                    >
                      Start mocked-voice visit
                    </button>
                  </div>
                  <p className={styles.fieldMeta} style={{ marginTop: 7 }}>
                    Mocked voice uses a deterministic synthetic recording and
                    transcription. Repeated submissions recover the same run
                    rather than creating duplicate visits or objects.
                  </p>
                </div>

                <div
                  className={styles.wordPending}
                  aria-labelledby="word-qa-status"
                >
                  <div>
                    <span className={styles.monoLabel}>
                      Final manual release gate
                    </span>
                    <h2 id="word-qa-status">
                      Microsoft Word compatibility: Pending
                    </h2>
                    <p>
                      After a synthetic visit is signed, download its generated
                      Original Template DOCX and open it manually in desktop
                      Microsoft Word. Pending never means approved or ready for
                      patient care; LibreOffice evidence is not a substitute.
                    </p>
                  </div>
                  <ol>
                    <li>
                      Finish the synthetic visit review and signing gates.
                    </li>
                    <li>Download the generated Original Template DOCX.</li>
                    <li>Open and inspect it in desktop Microsoft Word.</li>
                  </ol>
                </div>
              </>
            )}
          </div>
        </section>
      </div>

      <footer className={styles.footer}>
        <div
          style={{
            fontSize: 11.5,
            color: "var(--color-linear-text-3)",
            lineHeight: 1.4,
          }}
        >
          {workspace.canEdit
            ? dirty
              ? "Unsaved mapping changes"
              : `${confirmedCount} of ${fields.length} fields confirmed`
            : "This activated version is immutable. Create a new version to change a mapping."}
        </div>
        <div className={styles.footerActions}>
          {workspace.canEdit && (
            <>
              <button
                type="button"
                className={styles.button}
                onClick={() => void saveMappings()}
                disabled={
                  !dirty ||
                  busy !== null ||
                  retrySecondsRemaining > 0 ||
                  draftMergeConflicts.length > 0
                }
              >
                {busy === "save"
                  ? "Saving…"
                  : retrySecondsRemaining > 0
                    ? `Retry save in ${formatRetryDuration(retrySecondsRemaining)}`
                    : "Save draft"}
              </button>
              <button
                type="button"
                className={styles.button}
                onClick={() => void runSyntheticTest()}
                disabled={
                  dirty ||
                  busy !== null ||
                  !allConfirmed ||
                  hasBlockingUnsupported
                }
              >
                {busy === "test" ? "Verifying…" : "Run synthetic test"}
              </button>
              <button
                type="button"
                className={styles.primaryButton}
                onClick={() => void certify()}
                disabled={!canCertify}
                title={
                  canCertify
                    ? undefined
                    : "Confirm every field, clear blocking items, verify the current mappings, and acknowledge both statements."
                }
              >
                {busy === "certify" ? "Certifying…" : "Certify & activate"}
              </button>
            </>
          )}
        </div>
      </footer>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className={styles.metric}>
      <span className={styles.monoLabel}>{label}</span>
      <span className={styles.metricValue}>{value}</span>
    </div>
  );
}

function FieldInspector({
  item,
  canEdit,
  busy,
  stagingQaMode,
  intentDraft,
  onChange,
  onIntentChange,
}: {
  item: TemplateTwinWorkspaceField;
  canEdit: boolean;
  busy: boolean;
  stagingQaMode: boolean;
  intentDraft: FieldIntentDraft;
  onChange: (patch: Partial<SemanticMapping>) => void;
  onIntentChange: (intent: FieldIntentDraft) => void;
}) {
  const { field, mapping } = item;
  const disabled = !canEdit || busy;
  const requiresIntent =
    field.rendererBinding.bindingType === "ordinary_placeholder";
  const intentLocked = item.intent.lockedInVersion;
  const mappingDisabled =
    disabled ||
    (requiresIntent &&
      (intentDraft.intentKind === "custom_concept" ||
        intentDraft.intentKind === "static"));
  const confirmationError = fieldDraftError(item, intentDraft);

  function changeIntent(next: FieldIntentDraft) {
    if (stagingQaMode && next.intentKind === "custom_concept") return;
    onIntentChange(next);
    if (next.intentKind === "supported_concept") {
      onChange({
        clinicalConcept: next.supportedConcept || null,
        status: "needs_confirmation",
      });
    } else if (next.intentKind === "custom_concept") {
      onChange({
        clinicalConcept: next.customSpec.conceptId,
        expectedDataType: expectedTypeForCustom(next.customSpec.dataType),
        required: next.customSpec.required,
        unknownPolicy: next.customSpec.unknownPolicy,
        blankPolicy: next.customSpec.unknownPolicy,
        approvedSynonyms: [],
        temporality: "any",
        laterality: "optional",
        unitPolicy:
          next.customSpec.dataType === "measurement"
            ? "required"
            : next.customSpec.dataType === "number"
              ? "forbidden"
              : "not_applicable",
        practiceDefault: null,
        polarityBehavior: next.customSpec.polarityPolicy.allowExplicitDenial
          ? "explicit_denial_allowed"
          : next.customSpec.dataType === "boolean"
            ? "affirmative_only"
            : "value_only",
        status: "needs_confirmation",
      });
    } else {
      onChange({ clinicalConcept: null, status: "needs_confirmation" });
    }
  }

  function confirmField() {
    if (confirmationError) return;
    if (requiresIntent) {
      if (intentDraft.intentKind === "unresolved") return;
      if (intentDraft.intentKind === "static") {
        onChange({
          clinicalConcept: null,
          required: false,
          practiceDefault: null,
          status: "certified",
        });
        return;
      }
      if (intentDraft.intentKind === "supported_concept") {
        onChange({
          clinicalConcept: intentDraft.supportedConcept,
          status: "certified",
        });
        return;
      }
      onChange({
        clinicalConcept: intentDraft.customSpec.conceptId,
        expectedDataType: expectedTypeForCustom(
          intentDraft.customSpec.dataType,
        ),
        required: intentDraft.customSpec.required,
        unknownPolicy: intentDraft.customSpec.unknownPolicy,
        blankPolicy: intentDraft.customSpec.unknownPolicy,
        approvedSynonyms: [],
        temporality: "any",
        laterality: "optional",
        unitPolicy:
          intentDraft.customSpec.dataType === "measurement"
            ? "required"
            : intentDraft.customSpec.dataType === "number"
              ? "forbidden"
              : "not_applicable",
        practiceDefault: null,
        polarityBehavior: intentDraft.customSpec.polarityPolicy
          .allowExplicitDenial
          ? "explicit_denial_allowed"
          : intentDraft.customSpec.dataType === "boolean"
            ? "affirmative_only"
            : "value_only",
        status: "certified",
      });
      return;
    }
    onChange({ status: "certified" });
  }
  return (
    <>
      <div className={styles.section}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 12,
          }}
        >
          <div>
            <div className={styles.eyebrow}>Selected field</div>
            <h2 style={{ margin: "5px 0 0", fontSize: 18, fontWeight: 500 }}>
              {field.originalLabel}
            </h2>
          </div>
          <StatusPill item={item} intentDraft={intentDraft} />
        </div>
      </div>

      {requiresIntent && (
        <FieldIntentEditor
          item={item}
          draft={intentDraft}
          disabled={disabled || intentLocked}
          stagingQaMode={stagingQaMode}
          onChange={changeIntent}
        />
      )}

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>What this Word field does</h3>
        <div className={styles.definitionGrid}>
          <Definition label="Field type" value={titleCase(field.kind)} />
          <Definition
            label="Detection"
            value={titleCase(field.detectionStatus)}
          />
          <Definition
            label="Clinical priority"
            value={titleCase(field.criticality)}
          />
        </div>
        {field.allowedOptions.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div className={styles.monoLabel} style={{ marginBottom: 6 }}>
              Allowed options · exact order
            </div>
            <ol className={styles.optionList}>
              {field.allowedOptions.map((option) => (
                <li
                  key={`${option.ordinal}:${option.value}`}
                  className={styles.optionRow}
                >
                  <span className={styles.optionOrdinal}>
                    {option.ordinal + 1}
                  </span>
                  <span>{option.displayText}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
        <details className={styles.fieldMeta} style={{ marginTop: 12 }}>
          <summary style={{ cursor: "pointer" }}>
            Advanced Word binding details
          </summary>
          <div style={{ marginTop: 6, overflowWrap: "anywhere" }}>
            Field ID: {field.fieldId} · Label source:{" "}
            {titleCase(field.labelSource)} · Part:{" "}
            {field.rendererBinding.partName}
          </div>
        </details>
      </div>

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>How QuillMD fills this field</h3>
        <div className={styles.formGrid}>
          {!requiresIntent && (
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>Clinical detail to fill</span>
              <select
                className={styles.select}
                value={mapping.clinicalConcept ?? ""}
                onChange={(event) =>
                  onChange({
                    clinicalConcept: event.target.value || null,
                    status: "needs_confirmation",
                  })
                }
                disabled={mappingDisabled}
              >
                <option value="">Choose a supported clinical detail</option>
                {mapping.clinicalConcept &&
                  !isSupportedTemplateTwinConcept(mapping.clinicalConcept) && (
                    <option value={mapping.clinicalConcept}>
                      Unsupported in this version — {mapping.clinicalConcept}
                    </option>
                  )}
                {TEMPLATE_TWIN_SUPPORTED_CONCEPTS.map((concept) => (
                  <option key={concept.concept} value={concept.concept}>
                    {concept.physicianLabel}
                  </option>
                ))}
              </select>
              {mapping.clinicalConcept &&
                !isSupportedTemplateTwinConcept(mapping.clinicalConcept) && (
                  <span className={styles.warningText} role="alert">
                    QuillMD cannot safely extract and validate this clinical
                    detail in the current alpha, so certification is blocked.
                  </span>
                )}
            </label>
          )}
          <label className={styles.field}>
            <span className={styles.monoLabel}>Expected data type</span>
            <select
              className={styles.select}
              value={mapping.expectedDataType}
              onChange={(event) =>
                onChange({
                  expectedDataType: event.target
                    .value as SemanticMapping["expectedDataType"],
                  status: "needs_confirmation",
                })
              }
              disabled={mappingDisabled}
            >
              {EXPECTED_TYPES.map((value) => (
                <option key={value} value={value}>
                  {titleCase(value)}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>
              How negative statements work
            </span>
            <select
              className={styles.select}
              value={mapping.polarityBehavior}
              onChange={(event) =>
                onChange({
                  polarityBehavior: event.target
                    .value as SemanticMapping["polarityBehavior"],
                  status: "needs_confirmation",
                })
              }
              disabled={mappingDisabled}
            >
              {(
                [
                  "affirmative_only",
                  "explicit_denial_allowed",
                  "value_only",
                  "not_applicable",
                ] as const
              ).map((value) => (
                <option key={value} value={value}>
                  {POLARITY_LABELS[value]}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>When this detail applies</span>
            <select
              className={styles.select}
              value={mapping.temporality ?? ""}
              onChange={(event) =>
                onChange({
                  temporality: (event.target.value ||
                    null) as SemanticMapping["temporality"],
                  status: "needs_confirmation",
                })
              }
              disabled={mappingDisabled}
            >
              <option value="">Not constrained</option>
              {(["current", "historical", "planned", "any"] as const).map(
                (value) => (
                  <option key={value} value={value}>
                    {TEMPORALITY_LABELS[value]}
                  </option>
                ),
              )}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Left or right</span>
            <select
              className={styles.select}
              value={mapping.laterality ?? ""}
              onChange={(event) =>
                onChange({
                  laterality: (event.target.value ||
                    null) as SemanticMapping["laterality"],
                  status: "needs_confirmation",
                })
              }
              disabled={mappingDisabled}
            >
              <option value="">Not set</option>
              {(["required", "optional", "not_applicable"] as const).map(
                (value) => (
                  <option key={value} value={value}>
                    {LATERALITY_LABELS[value]}
                  </option>
                ),
              )}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>Numbers and units</span>
            <select
              className={styles.select}
              value={mapping.unitPolicy ?? ""}
              onChange={(event) =>
                onChange({
                  unitPolicy: (event.target.value ||
                    null) as SemanticMapping["unitPolicy"],
                  status: "needs_confirmation",
                })
              }
              disabled={mappingDisabled}
            >
              <option value="">Not set</option>
              {(
                ["required", "optional", "forbidden", "not_applicable"] as const
              ).map((value) => (
                <option key={value} value={value}>
                  {UNIT_LABELS[value]}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span className={styles.monoLabel}>
              When this detail was not stated
            </span>
            <select
              className={styles.select}
              value={mapping.unknownPolicy}
              onChange={(event) =>
                onChange({
                  unknownPolicy: event.target
                    .value as SemanticMapping["unknownPolicy"],
                  status: "needs_confirmation",
                })
              }
              disabled={mappingDisabled}
            >
              {(["blank", "not_documented", "requires_input"] as const).map(
                (value) => (
                  <option key={value} value={value}>
                    {UNKNOWN_LABELS[value]}
                  </option>
                ),
              )}
            </select>
          </label>
          {stagingQaMode ? (
            <div className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>Approved synonyms</span>
              <p className={styles.fieldMeta}>
                None. This reviewed staging fixture accepts only the exact
                supported clinical detail vocabulary.
              </p>
            </div>
          ) : (
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>
                Approved synonyms · comma separated
              </span>
              <input
                className={styles.input}
                value={mapping.approvedSynonyms.join(", ")}
                onChange={(event) =>
                  onChange({
                    approvedSynonyms: event.target.value
                      .split(",")
                      .map((value) => value.trim())
                      .filter(Boolean)
                      .slice(0, 50),
                    status: "needs_confirmation",
                  })
                }
                disabled={mappingDisabled}
              />
            </label>
          )}
          <label className={styles.checkLabel}>
            <input
              type="checkbox"
              checked={mapping.required}
              onChange={(event) =>
                onChange({
                  required: event.target.checked,
                  status: "needs_confirmation",
                })
              }
              disabled={mappingDisabled}
            />
            Required before signing
          </label>
        </div>
        {canEdit && (
          <div style={{ marginTop: 14 }}>
            {confirmationError && (
              <p className={styles.warningText} role="alert">
                {confirmationError.fieldLabel} — {confirmationError.setting}:{" "}
                {confirmationError.message}
              </p>
            )}
            <button
              type="button"
              className={styles.primaryButton}
              style={{ display: "block", marginLeft: "auto" }}
              onClick={confirmField}
              disabled={
                busy ||
                mapping.status === "certified" ||
                Boolean(confirmationError) ||
                (requiresIntent && intentDraft.intentKind === "unresolved") ||
                (stagingQaMode && intentDraft.intentKind === "custom_concept")
              }
            >
              {fieldIsConfirmed(item, intentDraft)
                ? "Field confirmed"
                : "Confirm this field"}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function FieldIntentEditor({
  item,
  draft,
  disabled,
  stagingQaMode,
  onChange,
}: {
  item: TemplateTwinWorkspaceField;
  draft: FieldIntentDraft;
  disabled: boolean;
  stagingQaMode: boolean;
  onChange: (intent: FieldIntentDraft) => void;
}) {
  const binding = item.field.rendererBinding;
  const defaultSpec = defaultCustomSpec(item);
  const updateSpec = (patch: Partial<TemplateFieldSpecificationContent>) => {
    if (draft.intentKind !== "custom_concept") return;
    onChange({
      intentKind: "custom_concept",
      customSpec: synchronizeCustomSyntheticExamples({
        ...draft.customSpec,
        ...patch,
      }),
    });
  };
  const scalarFromText = (
    dataType: CustomScalarDataType,
    raw: string,
  ): string | number | boolean => {
    if (dataType === "boolean") return raw === "true";
    if (dataType === "number" || dataType === "measurement") {
      const number = Number(raw);
      return Number.isFinite(number) ? number : 0;
    }
    return raw;
  };
  const defaultScalarFor = (
    dataType: CustomScalarDataType,
  ): string | number | boolean => {
    if (dataType === "boolean") return true;
    if (dataType === "number" || dataType === "measurement") return 1;
    if (dataType === "date") return "2099-01-15";
    if (dataType === "single_select") {
      return draft.intentKind === "custom_concept"
        ? (draft.customSpec.allowedOptions[0]?.value ?? "Synthetic option")
        : "Synthetic option";
    }
    return "Synthetic supported value";
  };

  return (
    <div className={styles.section}>
      <h3 className={styles.sectionTitle}>Physician field intent</h3>
      <div className={styles.callout}>
        <strong>What information belongs here?</strong>
        <div style={{ marginTop: 4 }}>
          Confirm this visible placeholder once. QuillMD will bind the decision
          to this exact document location; it will not guess from the label.
        </div>
        <div style={{ marginTop: 4 }}>
          Only a licensed physician should choose the clinical intent. No
          clinical answer is preselected, and leaving it unresolved keeps
          certification blocked.
        </div>
        <div className={styles.fieldMeta} style={{ marginTop: 7 }}>
          {binding.tableIndex === null
            ? `Document paragraph · ${binding.partName}`
            : `Table ${binding.tableIndex + 1} · row ${(binding.rowIndex ?? 0) + 1} · cell ${(binding.cellIndex ?? 0) + 1}`}
        </div>
      </div>
      {item.intent.lockedInVersion && (
        <p className={styles.warningText} role="status">
          This decision is recorded for version {item.intent.version}. Create a
          new draft version to change its clinical meaning.
        </p>
      )}
      <div className={styles.formGrid} style={{ marginTop: 12 }}>
        <label className={`${styles.field} ${styles.fieldWide}`}>
          <span className={styles.monoLabel}>Field intent</span>
          <select
            className={styles.select}
            value={draft.intentKind}
            disabled={disabled}
            onChange={(event) => {
              const value = event.target.value;
              if (value === "supported_concept") {
                onChange({
                  intentKind: "supported_concept",
                  supportedConcept: "",
                });
              } else if (value === "static") {
                onChange({
                  intentKind: "static",
                  reason: stagingQaMode
                    ? TEMPLATE_TWIN_STAGING_QA_STATIC_INTENT_REASON
                    : "",
                });
              } else if (
                !stagingQaMode &&
                value === "custom_concept" &&
                defaultSpec
              ) {
                onChange({
                  intentKind: "custom_concept",
                  customSpec: defaultSpec,
                });
              } else {
                onChange({ intentKind: "unresolved" });
              }
            }}
          >
            <option value="unresolved">
              Leave unresolved — blocks certification
            </option>
            <option value="supported_concept">
              Use an existing clinical detail
            </option>
            <option value="static">Keep this text static; never fill it</option>
            {!stagingQaMode && (
              <option value="custom_concept">
                Define a template-specific scalar detail
              </option>
            )}
          </select>
        </label>

        {draft.intentKind === "supported_concept" && (
          <label className={`${styles.field} ${styles.fieldWide}`}>
            <span className={styles.monoLabel}>Clinical detail to fill</span>
            <select
              className={styles.select}
              value={draft.supportedConcept}
              disabled={disabled}
              onChange={(event) =>
                onChange({
                  intentKind: "supported_concept",
                  supportedConcept: event.target.value,
                })
              }
            >
              <option value="">Choose an existing supported detail</option>
              {TEMPLATE_TWIN_SUPPORTED_CONCEPTS.map((concept) => (
                <option key={concept.concept} value={concept.concept}>
                  {concept.physicianLabel}
                </option>
              ))}
            </select>
          </label>
        )}

        {draft.intentKind === "static" &&
          (stagingQaMode ? (
            <div className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>Why this remains static</span>
              <p className={styles.fieldMeta}>
                {TEMPLATE_TWIN_STAGING_QA_STATIC_INTENT_REASON}
              </p>
            </div>
          ) : (
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>Why this remains static</span>
              <textarea
                className={styles.textarea}
                rows={2}
                minLength={10}
                maxLength={500}
                value={draft.reason}
                disabled={disabled}
                placeholder="Explain why this visible token is intentional fixed text."
                onChange={(event) =>
                  onChange({ intentKind: "static", reason: event.target.value })
                }
              />
            </label>
          ))}

        {draft.intentKind === "custom_concept" && stagingQaMode && (
          <p className={styles.warningText} role="alert">
            Template-specific custom concepts are not admitted by this reviewed
            synthetic staging fixture. Leave the field unresolved or choose an
            existing supported clinical detail.
          </p>
        )}

        {draft.intentKind === "custom_concept" && !stagingQaMode && (
          <>
            <label className={styles.field}>
              <span className={styles.monoLabel}>Physician-facing name</span>
              <input
                className={styles.input}
                value={draft.customSpec.physicianName}
                maxLength={160}
                disabled={disabled}
                onChange={(event) =>
                  updateSpec({ physicianName: event.target.value })
                }
              />
            </label>
            <label className={styles.field}>
              <span className={styles.monoLabel}>Field type</span>
              <select
                className={styles.select}
                value={draft.customSpec.dataType}
                disabled={disabled}
                onChange={(event) => {
                  const dataType = event.target.value as CustomScalarDataType;
                  const next = defaultSpec!;
                  const expectedValue = defaultScalarFor(dataType);
                  const expectedUnit = dataType === "measurement" ? "mm" : null;
                  const evidenceCue =
                    draft.customSpec.approvedEvidenceCues[0] ??
                    draft.customSpec.physicianName;
                  updateSpec({
                    dataType,
                    allowedOptions:
                      dataType === "single_select" ? next.allowedOptions : [],
                    allowedUnits: dataType === "measurement" ? ["mm"] : [],
                    maximumLength: dataType === "narrative_text" ? 500 : null,
                    numericRange: null,
                    polarityPolicy: {
                      allowExplicitDenial: false,
                      exactDeniedOutput: null,
                    },
                    positiveSyntheticExamples: [
                      {
                        exampleId: "positive-1",
                        syntheticEvidence: `Synthetic example: ${evidenceCue} is ${String(expectedValue)}${expectedUnit ? ` ${expectedUnit}` : ""}.`,
                        expectedValue,
                        expectedUnit,
                      },
                    ],
                    negativeSyntheticExamples: [
                      {
                        exampleId: "negative-1",
                        syntheticEvidence:
                          "Synthetic example: an unrelated encounter detail is documented.",
                        prohibitedValue: null,
                        reason: "The certified evidence cue is absent.",
                      },
                    ],
                    ambiguitySyntheticExamples: [],
                  });
                }}
              >
                <option value="narrative_text">Narrative text</option>
                <option value="number">Number</option>
                <option value="measurement">Measurement with unit</option>
                <option value="date">Date</option>
                <option value="boolean">Yes or no</option>
                <option value="single_select">
                  Exact single-select option
                </option>
              </select>
            </label>
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>Clinical description</span>
              <textarea
                className={styles.textarea}
                rows={3}
                maxLength={1000}
                value={draft.customSpec.physicianDescription}
                disabled={disabled}
                placeholder="Describe exactly what encounter evidence supports this field."
                onChange={(event) =>
                  updateSpec({ physicianDescription: event.target.value })
                }
              />
            </label>
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>
                Exact evidence cues · comma separated
              </span>
              <input
                className={styles.input}
                value={draft.customSpec.approvedEvidenceCues.join(", ")}
                disabled={disabled}
                onChange={(event) =>
                  updateSpec({
                    approvedEvidenceCues: event.target.value
                      .split(",")
                      .map((value) => value.trim())
                      .filter(Boolean)
                      .slice(0, 12),
                  })
                }
              />
              <span className={styles.fieldMeta}>
                A value is accepted only when one of these exact phrases and the
                value appear together in the same evidence clause.
              </span>
            </label>
            {draft.customSpec.dataType === "single_select" && (
              <label className={`${styles.field} ${styles.fieldWide}`}>
                <span className={styles.monoLabel}>
                  Allowed values · comma separated
                </span>
                <input
                  className={styles.input}
                  value={draft.customSpec.allowedOptions
                    .map((option) => option.value)
                    .join(", ")}
                  disabled={disabled}
                  onChange={(event) => {
                    const values = event.target.value
                      .split(",")
                      .map((value) => value.trim())
                      .filter(Boolean);
                    if (values.length > TEMPLATE_TWIN_CUSTOM_OPTION_LIMIT) {
                      toast.error(
                        `Safe alpha supports at most ${TEMPLATE_TWIN_CUSTOM_OPTION_LIMIT} exact options. No values were discarded.`,
                      );
                      return;
                    }
                    updateSpec({
                      allowedOptions: values.map((value, ordinal) => ({
                        ordinal,
                        value,
                        displayText: value,
                      })),
                    });
                  }}
                />
              </label>
            )}
            {draft.customSpec.dataType === "measurement" && (
              <label className={`${styles.field} ${styles.fieldWide}`}>
                <span className={styles.monoLabel}>
                  Allowed units · comma separated
                </span>
                <input
                  className={styles.input}
                  value={draft.customSpec.allowedUnits.join(", ")}
                  disabled={disabled}
                  onChange={(event) => {
                    const units = event.target.value
                      .split(",")
                      .map((value) => value.trim())
                      .filter(Boolean);
                    if (units.length > TEMPLATE_TWIN_CUSTOM_UNIT_LIMIT) {
                      toast.error(
                        `Safe alpha supports at most ${TEMPLATE_TWIN_CUSTOM_UNIT_LIMIT} exact units. No units were discarded.`,
                      );
                      return;
                    }
                    updateSpec({
                      allowedUnits: units,
                      permittedUnitConversions: [],
                    });
                  }}
                />
              </label>
            )}
            {draft.customSpec.dataType === "narrative_text" && (
              <label className={styles.field}>
                <span className={styles.monoLabel}>Maximum characters</span>
                <input
                  className={styles.input}
                  type="number"
                  min={1}
                  max={4000}
                  value={draft.customSpec.maximumLength ?? 500}
                  disabled={disabled}
                  onChange={(event) =>
                    updateSpec({ maximumLength: Number(event.target.value) })
                  }
                />
              </label>
            )}
            {(draft.customSpec.dataType === "number" ||
              draft.customSpec.dataType === "measurement") && (
              <>
                <label className={styles.field}>
                  <span className={styles.monoLabel}>
                    Minimum value · optional
                  </span>
                  <input
                    className={styles.input}
                    type="number"
                    value={draft.customSpec.numericRange?.minimum ?? ""}
                    disabled={disabled}
                    onChange={(event) =>
                      updateSpec({
                        numericRange: {
                          minimum:
                            event.target.value === ""
                              ? null
                              : Number(event.target.value),
                          maximum:
                            draft.customSpec.numericRange?.maximum ?? null,
                        },
                      })
                    }
                  />
                </label>
                <label className={styles.field}>
                  <span className={styles.monoLabel}>
                    Maximum value · optional
                  </span>
                  <input
                    className={styles.input}
                    type="number"
                    value={draft.customSpec.numericRange?.maximum ?? ""}
                    disabled={disabled}
                    onChange={(event) =>
                      updateSpec({
                        numericRange: {
                          minimum:
                            draft.customSpec.numericRange?.minimum ?? null,
                          maximum:
                            event.target.value === ""
                              ? null
                              : Number(event.target.value),
                        },
                      })
                    }
                  />
                </label>
              </>
            )}
            <label className={styles.field}>
              <span className={styles.monoLabel}>When it applies</span>
              <select
                className={styles.select}
                value={draft.customSpec.allowedTemporalities[0] ?? "current"}
                disabled={disabled}
                onChange={(event) =>
                  updateSpec({
                    allowedTemporalities: [
                      event.target.value as
                        | "current"
                        | "historical"
                        | "planned",
                    ],
                  })
                }
              >
                <option value="current">Current encounter</option>
                <option value="historical">Past history</option>
                <option value="planned">Planned care</option>
              </select>
            </label>
            <label className={styles.field}>
              <span className={styles.monoLabel}>Laterality</span>
              <select
                className={styles.select}
                value={
                  draft.customSpec.allowedLateralities[0] ?? "not_applicable"
                }
                disabled={disabled}
                onChange={(event) =>
                  updateSpec({
                    allowedLateralities: [
                      event.target.value as
                        | "left"
                        | "right"
                        | "bilateral"
                        | "midline"
                        | "not_applicable",
                    ],
                  })
                }
              >
                <option value="not_applicable">Not applicable</option>
                <option value="left">Left only</option>
                <option value="right">Right only</option>
                <option value="bilateral">Bilateral only</option>
                <option value="midline">Midline only</option>
              </select>
            </label>
            <label className={styles.checkLabel}>
              <input
                type="checkbox"
                checked={draft.customSpec.required}
                disabled={disabled}
                onChange={(event) =>
                  updateSpec({ required: event.target.checked })
                }
              />
              Required before signing
            </label>
            <label className={styles.checkLabel}>
              <input
                type="checkbox"
                checked={draft.customSpec.polarityPolicy.allowExplicitDenial}
                disabled={
                  disabled || draft.customSpec.dataType === "measurement"
                }
                onChange={(event) =>
                  updateSpec({
                    polarityPolicy: {
                      allowExplicitDenial: event.target.checked,
                      exactDeniedOutput: event.target.checked
                        ? draft.customSpec.dataType === "boolean"
                          ? false
                          : draft.customSpec.dataType === "number" ||
                              draft.customSpec.dataType === "measurement"
                            ? 0
                            : draft.customSpec.dataType === "date"
                              ? "2099-01-15"
                              : draft.customSpec.dataType === "single_select"
                                ? (draft.customSpec.allowedOptions[0]?.value ??
                                  "")
                                : "Not present"
                        : null,
                    },
                  })
                }
              />
              Allow an exact evidence-backed negative output
            </label>
            {draft.customSpec.dataType === "measurement" && (
              <div className={styles.fieldMeta}>
                Measurement denial is unavailable in safe alpha because a
                unit-bound negative value cannot yet be proved independently.
              </div>
            )}
            {draft.customSpec.polarityPolicy.allowExplicitDenial && (
              <label className={styles.field}>
                <span className={styles.monoLabel}>Exact negative output</span>
                <input
                  className={styles.input}
                  value={String(
                    draft.customSpec.polarityPolicy.exactDeniedOutput ?? "",
                  )}
                  disabled={disabled}
                  onChange={(event) =>
                    updateSpec({
                      polarityPolicy: {
                        allowExplicitDenial: true,
                        exactDeniedOutput: scalarFromText(
                          draft.customSpec.dataType,
                          event.target.value,
                        ),
                      },
                    })
                  }
                />
              </label>
            )}
            {draft.customSpec.positiveSyntheticExamples.map(
              (example, exampleIndex) => (
                <div
                  className={`${styles.section} ${styles.fieldWide}`}
                  key={example.exampleId}
                >
                  <div className={styles.monoLabel}>
                    {example.expectedStatus === "explicitly_denied"
                      ? "Explicit-denial synthetic test"
                      : `Positive synthetic test ${exampleIndex + 1}`}
                  </div>
                  <label className={`${styles.field} ${styles.fieldWide}`}>
                    <span className={styles.monoLabel}>Synthetic evidence</span>
                    <textarea
                      className={styles.textarea}
                      rows={2}
                      value={example.syntheticEvidence}
                      disabled={disabled}
                      onChange={(event) => {
                        const examples = [
                          ...draft.customSpec.positiveSyntheticExamples,
                        ];
                        examples[exampleIndex] = {
                          ...example,
                          syntheticEvidence: event.target.value,
                        };
                        updateSpec({ positiveSyntheticExamples: examples });
                      }}
                    />
                  </label>
                  <label className={styles.field}>
                    <span className={styles.monoLabel}>
                      Expected exact output
                    </span>
                    <input
                      className={styles.input}
                      value={String(example.expectedValue)}
                      disabled={
                        disabled ||
                        draft.customSpec.dataType === "single_select" ||
                        example.expectedStatus === "explicitly_denied"
                      }
                      onChange={(event) => {
                        const examples = [
                          ...draft.customSpec.positiveSyntheticExamples,
                        ];
                        examples[exampleIndex] = {
                          ...example,
                          expectedValue: scalarFromText(
                            draft.customSpec.dataType,
                            event.target.value,
                          ),
                        };
                        updateSpec({ positiveSyntheticExamples: examples });
                      }}
                    />
                  </label>
                  {draft.customSpec.dataType === "measurement" && (
                    <div className={styles.fieldMeta}>
                      Exact unit: {example.expectedUnit ?? "none"}
                    </div>
                  )}
                </div>
              ),
            )}
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>
                Negative synthetic evidence
              </span>
              <textarea
                className={styles.textarea}
                rows={2}
                value={
                  draft.customSpec.negativeSyntheticExamples[0]
                    ?.syntheticEvidence ?? ""
                }
                disabled={disabled}
                onChange={(event) => {
                  const first = draft.customSpec.negativeSyntheticExamples[0]!;
                  updateSpec({
                    negativeSyntheticExamples: [
                      { ...first, syntheticEvidence: event.target.value },
                    ],
                  });
                }}
              />
            </label>
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>
                Ambiguity synthetic evidence
              </span>
              <textarea
                className={styles.textarea}
                rows={2}
                value={
                  draft.customSpec.ambiguitySyntheticExamples[0]
                    ?.syntheticEvidence ?? ""
                }
                disabled={disabled}
                onChange={(event) => {
                  const first = draft.customSpec.ambiguitySyntheticExamples[0]!;
                  updateSpec({
                    ambiguitySyntheticExamples: [
                      { ...first, syntheticEvidence: event.target.value },
                    ],
                  });
                }}
              />
            </label>
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>
                Ambiguous possible values · comma separated
              </span>
              <input
                className={styles.input}
                value={
                  draft.customSpec.ambiguitySyntheticExamples[0]?.possibleValues
                    .map(String)
                    .join(", ") ?? ""
                }
                disabled={disabled}
                onChange={(event) => {
                  const first = draft.customSpec.ambiguitySyntheticExamples[0]!;
                  const possibleValues = event.target.value
                    .split(",")
                    .map((value) => value.trim())
                    .filter(Boolean)
                    .slice(0, 8)
                    .map((value) =>
                      scalarFromText(draft.customSpec.dataType, value),
                    );
                  updateSpec({
                    ambiguitySyntheticExamples: [
                      {
                        ...first,
                        possibleValues,
                        syntheticEvidence: defaultCustomAmbiguityEvidence(
                          draft.customSpec,
                          possibleValues,
                        ),
                      },
                    ],
                  });
                }}
              />
            </label>
            <label className={styles.field}>
              <span className={styles.monoLabel}>When not stated</span>
              <select
                className={styles.select}
                value={draft.customSpec.unknownPolicy}
                disabled={disabled}
                onChange={(event) =>
                  updateSpec({
                    unknownPolicy: event.target.value as
                      | "blank"
                      | "not_documented"
                      | "requires_input",
                  })
                }
              >
                <option value="blank">Leave blank</option>
                <option value="requires_input">Require physician input</option>
              </select>
            </label>
            <div className={`${styles.callout} ${styles.fieldWide}`}>
              Positive, negative, and ambiguity examples are immutable parts of
              this version. QuillMD requires direct evidence and physician
              review before activation; unclear evidence never fills a value.
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className={styles.monoLabel}>{label}</div>
      <div className={styles.definitionValue}>{value}</div>
    </div>
  );
}
