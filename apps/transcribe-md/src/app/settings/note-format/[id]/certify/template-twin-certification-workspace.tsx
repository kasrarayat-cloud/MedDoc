"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import type { SemanticMapping } from "@/lib/template-twin/ir";
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

function fieldStatus(item: TemplateTwinWorkspaceField): {
  label: string;
  tone: "safe" | "review" | "block";
} {
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

function StatusPill({ item }: { item: TemplateTwinWorkspaceField }) {
  const status = fieldStatus(item);
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
  const [selectedId, setSelectedId] = useState(
    initial.fields.find((item) => item.mapping.status !== "certified")?.field
      .fieldId ??
      initial.fields[0]?.field.fieldId ??
      "",
  );
  const [filter, setFilter] = useState<FieldFilter>("all");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<"save" | "test" | "certify" | null>(null);
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
        : fields.filter((item) => fieldStatus(item).tone !== "safe"),
    [fields, filter],
  );
  const confirmedCount = fields.filter(
    (item) => item.mapping.status === "certified",
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
  const canCertify =
    workspace.canEdit &&
    !dirty &&
    allConfirmed &&
    testMatches &&
    !hasBlockingUnsupported &&
    unexercisedBlockingFields.length === 0 &&
    waiversReady &&
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
            mappings: fields.map((item) => item.mapping),
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
                <StatusPill item={item} />
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
                onChange={(patch) =>
                  updateMapping(selected.field.fieldId, patch)
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
  onChange,
}: {
  item: TemplateTwinWorkspaceField;
  canEdit: boolean;
  busy: boolean;
  onChange: (patch: Partial<SemanticMapping>) => void;
}) {
  const { field, mapping } = item;
  const disabled = !canEdit || busy;
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
          <StatusPill item={item} />
        </div>
      </div>

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
              disabled={disabled}
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
              disabled={disabled}
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
              disabled={disabled}
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
              disabled={disabled}
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
              disabled={disabled}
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
              disabled={disabled}
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
              disabled={disabled}
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
              disabled={disabled}
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
              disabled={disabled}
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
              onClick={() => onChange({ status: "certified" })}
              disabled={busy || mapping.status === "certified"}
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

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className={styles.monoLabel}>{label}</div>
      <div className={styles.definitionValue}>{value}</div>
    </div>
  );
}
