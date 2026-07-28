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

function fieldStatus(
  item: TemplateTwinWorkspaceField,
  intentDraft?: FieldIntentDraft,
): {
  label: string;
  tone: "safe" | "review" | "block";
} {
  if (
    item.field.rendererBinding.bindingType === "ordinary_placeholder" &&
    (!intentDraft || intentDraft.intentKind === "unresolved")
  ) {
    return { label: "Needs intent", tone: "review" };
  }
  if (item.mapping.status === "certified") {
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
}: {
  initial: TemplateTwinWorkspace;
}) {
  const router = useRouter();
  const [workspace, setWorkspace] = useState(initial);
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
    "save" | "test" | "custom-examples" | "ack-custom-examples" | "certify" | null
  >(null);
  const [announcement, setAnnouncement] = useState("");
  const [syntheticText, setSyntheticText] = useState(SYNTHETIC_STARTER);
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
  const confirmedCount = fields.filter(
    (item) =>
      item.mapping.status === "certified" &&
      (item.field.rendererBinding.bindingType !== "ordinary_placeholder" ||
        intentDrafts[item.field.fieldId]?.intentKind !== "unresolved"),
  ).length;
  const allConfirmed = fields.length > 0 && confirmedCount === fields.length;
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

  function updateMapping(fieldId: string, patch: Partial<SemanticMapping>) {
    setFields((current) =>
      current.map((item) =>
        item.field.fieldId === fieldId
          ? { ...item, mapping: { ...item.mapping, ...patch } }
          : item,
      ),
    );
    setDirty(true);
    setAckStructure(false);
    setAckTest(false);
    setWaiverReasons({});
    setAnnouncement("Mapping changed. Save the draft before running a test.");
  }

  function updateIntent(fieldId: string, intent: FieldIntentDraft) {
    setIntentDrafts((current) => ({ ...current, [fieldId]: intent }));
    setDirty(true);
    setAckStructure(false);
    setAckTest(false);
    setWaiverReasons({});
    setAnnouncement(
      "Field intent changed. Save this version before running a test.",
    );
  }

  async function saveMappings(): Promise<boolean> {
    if (!workspace.canEdit) return true;
    setBusy("save");
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
            mappings: fields.map((item) => item.mapping),
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
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("Mappings were not saved", {
          description:
            payload && !payload.ok
              ? payload.error
              : "Reload the workspace and try again.",
        });
        return false;
      }
      setWorkspace(payload.workspace);
      setFields(payload.workspace.fields);
      setIntentDrafts(intentDraftsFor(payload.workspace.fields));
      setDirty(false);
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
      form.append(
        "expectedFieldIntentsSha256",
        workspace.fieldIntentsSha256,
      );
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
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ action: "run" }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; coverage: NonNullable<TemplateTwinWorkspace["customExampleCoverage"]> }
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
        description: "No example review was recorded. Check your connection and try again.",
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
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify({ action: "acknowledge", batchId }),
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; coverage: NonNullable<TemplateTwinWorkspace["customExampleCoverage"]> }
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
      setAnnouncement("Every current custom-field example is passed and physician-reviewed.");
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

  return (
    <div className={styles.shell}>
      <div className="sr-only" role="status" aria-live="polite">
        {announcement}
      </div>

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

      <section
        className={styles.summary}
        aria-label="Detected structure summary"
      >
        <Metric label="Fields" value={workspace.stats.totalFields} />
        <Metric
          label="Dropdowns"
          value={workspace.stats.dropdowns + workspace.stats.comboBoxes}
        />
        <Metric label="Checkboxes" value={workspace.stats.checkboxes} />
        <Metric label="Tables" value={workspace.stats.tables} />
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
          <div
            className={styles.fieldList}
            role="listbox"
            aria-label="Detected fields"
          >
            {visibleFields.map((item) => (
              <button
                key={item.field.fieldId}
                type="button"
                role="option"
                aria-selected={item.field.fieldId === selected?.field.fieldId}
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
          </div>
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
                <h2 className={styles.sectionTitle}>Custom-field safety examples</h2>
                <div className={styles.callout}>
                  QuillMD runs every positive, negative, and unclear synthetic
                  example you approved through the same extractor used for
                  typed and voice visits. Activation stays blocked until every
                  current example passes and you review the results.
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
                      {busy === "custom-examples" ? "Running…" : "Run all examples"}
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
                      <strong>{example.physicianName} · {titleCase(example.exampleKind)}</strong>
                      <div style={{ marginTop: 5 }}>
                        <span className={styles.monoLabel}>Synthetic evidence</span>
                        <div>“{example.syntheticEvidence}”</div>
                      </div>
                      <div className={styles.fieldMeta} style={{ marginTop: 6 }}>
                        Expected: {expected}
                      </div>
                      <div className={styles.fieldMeta} style={{ marginTop: 3 }}>
                        Actual: {example.actualStatus ? titleCase(example.actualStatus) : "Not run"}
                        {example.actualValue !== null
                          ? ` · ${String(example.actualValue)}${example.actualUnit ? ` ${example.actualUnit}` : ""}`
                          : ""}
                        {` · ${example.actualEvidenceAnchorCount} evidence anchor${example.actualEvidenceAnchorCount === 1 ? "" : "s"} · ${example.actualSourceFactCount} source fact${example.actualSourceFactCount === 1 ? "" : "s"}`}
                      </div>
                      <div className={styles.fieldMeta} style={{ marginTop: 3 }}>
                        {example.passed ? "Passed" : `Needs attention${example.failureCode ? ` · ${example.failureCode}` : ""}`} · {example.acknowledged ? "Reviewed" : "Not yet reviewed"}
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
                disabled={!dirty || busy !== null}
              >
                {busy === "save" ? "Saving…" : "Save draft"}
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
  intentDraft,
  onChange,
  onIntentChange,
}: {
  item: TemplateTwinWorkspaceField;
  canEdit: boolean;
  busy: boolean;
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

  function changeIntent(next: FieldIntentDraft) {
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
        expectedDataType: expectedTypeForCustom(intentDraft.customSpec.dataType),
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
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              marginTop: 14,
            }}
          >
            <button
              type="button"
              className={styles.primaryButton}
              onClick={confirmField}
              disabled={
                busy ||
                mapping.status === "certified" ||
                (requiresIntent && intentDraft.intentKind === "unresolved")
              }
            >
              {mapping.status === "certified"
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
  onChange,
}: {
  item: TemplateTwinWorkspaceField;
  draft: FieldIntentDraft;
  disabled: boolean;
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
                onChange({ intentKind: "supported_concept", supportedConcept: "" });
              } else if (value === "static") {
                onChange({ intentKind: "static", reason: "" });
              } else if (value === "custom_concept" && defaultSpec) {
                onChange({ intentKind: "custom_concept", customSpec: defaultSpec });
              } else {
                onChange({ intentKind: "unresolved" });
              }
            }}
          >
            <option value="unresolved">Leave unresolved — blocks certification</option>
            <option value="supported_concept">Use an existing clinical detail</option>
            <option value="static">Keep this text static; never fill it</option>
            <option value="custom_concept">Define a template-specific scalar detail</option>
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

        {draft.intentKind === "static" && (
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
        )}

        {draft.intentKind === "custom_concept" && (
          <>
            <label className={styles.field}>
              <span className={styles.monoLabel}>Physician-facing name</span>
              <input
                className={styles.input}
                value={draft.customSpec.physicianName}
                maxLength={160}
                disabled={disabled}
                onChange={(event) => updateSpec({ physicianName: event.target.value })}
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
                  const expectedUnit =
                    dataType === "measurement" ? "mm" : null;
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
                <option value="single_select">Exact single-select option</option>
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
                A value is accepted only when one of these exact phrases and
                the value appear together in the same evidence clause.
              </span>
            </label>
            {draft.customSpec.dataType === "single_select" && (
              <label className={`${styles.field} ${styles.fieldWide}`}>
                <span className={styles.monoLabel}>Allowed values · comma separated</span>
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
                <span className={styles.monoLabel}>Allowed units · comma separated</span>
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
                  <span className={styles.monoLabel}>Minimum value · optional</span>
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
                  <span className={styles.monoLabel}>Maximum value · optional</span>
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
                      event.target.value as "current" | "historical" | "planned",
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
                value={draft.customSpec.allowedLateralities[0] ?? "not_applicable"}
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
                onChange={(event) => updateSpec({ required: event.target.checked })}
              />
              Required before signing
            </label>
            <label className={styles.checkLabel}>
              <input
                type="checkbox"
                checked={draft.customSpec.polarityPolicy.allowExplicitDenial}
                disabled={disabled || draft.customSpec.dataType === "measurement"}
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
                    <span className={styles.monoLabel}>Expected exact output</span>
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
              <span className={styles.monoLabel}>Negative synthetic evidence</span>
              <textarea
                className={styles.textarea}
                rows={2}
                value={
                  draft.customSpec.negativeSyntheticExamples[0]
                    ?.syntheticEvidence ?? ""
                }
                disabled={disabled}
                onChange={(event) => {
                  const first =
                    draft.customSpec.negativeSyntheticExamples[0]!;
                  updateSpec({
                    negativeSyntheticExamples: [
                      { ...first, syntheticEvidence: event.target.value },
                    ],
                  });
                }}
              />
            </label>
            <label className={`${styles.field} ${styles.fieldWide}`}>
              <span className={styles.monoLabel}>Ambiguity synthetic evidence</span>
              <textarea
                className={styles.textarea}
                rows={2}
                value={
                  draft.customSpec.ambiguitySyntheticExamples[0]
                    ?.syntheticEvidence ?? ""
                }
                disabled={disabled}
                onChange={(event) => {
                  const first =
                    draft.customSpec.ambiguitySyntheticExamples[0]!;
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
                  draft.customSpec.ambiguitySyntheticExamples[0]
                    ?.possibleValues.map(String)
                    .join(", ") ?? ""
                }
                disabled={disabled}
                onChange={(event) => {
                  const first =
                    draft.customSpec.ambiguitySyntheticExamples[0]!;
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
