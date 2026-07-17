"use client";

// ============================================================================
// Note-format customization — Phase 2b: "My Note Format" client manager
// ----------------------------------------------------------------------------
// One client island for the whole settings section. State machine:
//   home  → list of the doctor's formats (or, first-time, the entry directly)
//   entry → bring-your-own (paste / upload) OR stay on standard
//   parsing → while parseNoteTemplateAction runs
//   review  → TemplateReviewEditor (save draft / save & activate)
//   rejected → calm PHI-safe rejection (note was never saved)
// Mirrors the v9 mockups with the live Linear V1 tokens. The templates list is
// rendered from server props; mutations call the doctor-scoped actions then
// router.refresh() to pull fresh data.
// ============================================================================

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import { toast } from "sonner";

import { parseNoteTemplateAction } from "@/actions/parse-note-template";
import { extractNoteFileAction } from "@/actions/extract-note-file";
import { isStaleDeploymentError } from "@/lib/stale-deployment";
import {
  activateNoteTemplateAction,
  duplicateNoteTemplateAction,
  deleteNoteTemplateAction,
  getNoteTemplateForEditAction,
} from "@/actions/note-template-lifecycle";
import {
  activateTemplateTwinVersionAction,
  createTemplateTwinVersionAction,
  deactivateTemplateTwinVersionAction,
  inspectTemplateTwinLineageAction,
  retireTemplateTwinVersionAction,
  rollbackTemplateTwinVersionAction,
  type TemplateTwinLineageVersion,
} from "@/actions/template-twin-management";
import type {
  TemplateReviewModel,
  ClientTemplateListItem,
} from "@/lib/note-template-persist/types";
import { TemplateReviewEditor } from "./template-review-editor";
import { TemplateTwinSyntheticQaBanner } from "@/components/template-twin-synthetic-qa-banner";

const mono = "var(--font-mono)";
const sans = "var(--font-sans)";

function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

// Next.js server actions reject bodies over 1 MB BEFORE our action runs
// (no serverActions.bodySizeLimit is configured), so the server-side 5 MB
// check in actions/extract-note-file.ts (MAX_UPLOAD_BYTES) is unreachable
// and an oversized file surfaced only as a generic "Something went wrong"
// (custom-template QA 2026-07-02, finding F-4). Check client-side against
// the REAL limit and say so honestly. Keep in sync with the framework
// default; distinct name from the server constant to avoid drift confusion.
const UPLOAD_ACTION_BODY_LIMIT_BYTES = 1024 * 1024;
const btn: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 6,
  padding: "6px 12px",
  borderRadius: 6,
  fontSize: 12,
  fontWeight: 500,
  fontFamily: sans,
  cursor: "pointer",
  background: "transparent",
  color: "var(--color-linear-text-2)",
  border: "1px solid var(--color-linear-border)",
};
const btnPrimary: React.CSSProperties = {
  ...btn,
  background: "var(--color-linear-sage)",
  color: "#0d1611",
  border: "none",
  boxShadow: "0 0 0 1px rgba(122,166,140,0.3)",
};
const subLabel: React.CSSProperties = {
  fontFamily: mono,
  fontSize: 10,
  letterSpacing: "0.06em",
  textTransform: "uppercase",
  color: "var(--color-linear-text-3)",
};

type View =
  | "home"
  | "entry"
  | "parsing"
  | "twin-compiling"
  | "review"
  | "rejected";

const TEMPLATE_TWIN_MAX_BYTES = 10 * 1024 * 1024;
const TEMPLATE_TWIN_STAGING_QA_FIXTURE_VERSION =
  "template-twin-staging-safe-docx/1.0.0";
const TEMPLATE_TWIN_STAGING_QA_TEMPLATE_NAME =
  "Template Twin Synthetic QA Fixture";
const TEMPLATE_TWIN_STAGING_QA_ENCOUNTER_SCOPE =
  "Synthetic follow-up encounter";
const TEMPLATE_TWIN_STAGING_QA_VERSION_DESCRIPTION =
  "Reviewed synthetic staging fixture v1";
type TwinUploadMode = "generic" | "synthetic_staging";

/** Which uploadable formats this image can actually extract. Computed server-
 *  side (see SettingsPage.getUploadCaps) so the UI never advertises a format
 *  whose extractor isn't loadable. .txt/.md need no lib and are always on. */
export interface UploadCaps {
  pdf: boolean;
  docx: boolean;
}

export function NoteFormatManager({
  templates,
  uploadCaps,
  templateTwinSyntheticQaState,
}: {
  templates: ClientTemplateListItem[];
  uploadCaps: UploadCaps;
  templateTwinSyntheticQaState: "enabled" | "unavailable" | "hidden";
}) {
  const router = useRouter();
  const hasTemplates = templates.length > 0;
  const [view, setView] = useState<View>(hasTemplates ? "home" : "entry");
  const [pasteText, setPasteText] = useState("");
  const [review, setReview] = useState<{
    model: TemplateReviewModel;
    flags: string[];
  } | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [pending, startTransition] = useTransition();
  const fileRef = useRef<HTMLInputElement>(null);
  const twinFileRef = useRef<HTMLInputElement>(null);
  const twinUploadReturnFocusRef = useRef<HTMLElement | null>(null);
  const [twinUploadOpen, setTwinUploadOpen] = useState(false);
  const [twinUploadMode, setTwinUploadMode] =
    useState<TwinUploadMode>("generic");
  const [twinFile, setTwinFile] = useState<File | null>(null);
  const [twinName, setTwinName] = useState("");
  const [twinScope, setTwinScope] = useState("");
  const [twinVersionDescription, setTwinVersionDescription] = useState("");
  const [twinVersionSource, setTwinVersionSource] =
    useState<ClientTemplateListItem | null>(null);
  const [newTwinName, setNewTwinName] = useState("");
  const [newTwinDescription, setNewTwinDescription] = useState("");
  const [lineageOpen, setLineageOpen] = useState(false);
  const [lineage, setLineage] = useState<{
    activeVersion: number | null;
    versions: TemplateTwinLineageVersion[];
  } | null>(null);

  function refreshHome() {
    setReview(null);
    setPasteText("");
    router.refresh();
    setView("home");
  }

  // A server action THREW (rejected) rather than returning a typed result —
  // most often Next.js "deployment skew" (this tab loaded before a deploy, so
  // its server-action IDs no longer exist on the server). Never let that crash
  // to the full-page error boundary, which would lose the doctor's input: show
  // a clear message and return to a safe view with their text still visible.
  // Skew → a reload is the only fix (a re-mount keeps the stale bundle).
  function handleActionError(err: unknown, recoverView: View) {
    if (isStaleDeploymentError(err)) {
      toast.error("QuillMD was just updated", {
        description:
          "Reload the page to continue — copy any unsaved text first.",
        action: { label: "Reload", onClick: () => window.location.reload() },
        duration: 12000,
      });
    } else {
      toast.error("Something went wrong", {
        description:
          "Please try again. If it keeps happening, reload the page.",
      });
    }
    setView(recoverView);
  }

  function runParse(text: string) {
    setView("parsing");
    startTransition(async () => {
      try {
        const res = await parseNoteTemplateAction(text);
        if (res.rejected) {
          setRejectReason(res.reason);
          setView("rejected");
        } else {
          setReview({
            model: {
              name: res.template.name,
              encounterType: res.template.encounterType,
              sections: res.template.sections,
              styleProfile: res.template.styleProfile,
            },
            flags: res.flags,
          });
          setView("review");
        }
      } catch (err) {
        handleActionError(err, "entry");
      }
    });
  }

  function onParseClick() {
    const text = pasteText.trim();
    if (text.length === 0) {
      toast.error("Paste a note first");
      return;
    }
    // Mirror the server's 50k-char cap (parse-note-template.ts MAX_NOTE_CHARS)
    // client-side: a multi-MB paste would otherwise die at the framework's
    // 1 MB action-body limit with a generic error before the friendly
    // server message could run (finding F-4, paste path).
    if (text.length > 50_000) {
      toast.error("Note is too long", {
        description:
          "Max 50,000 characters — paste a single representative note.",
      });
      return;
    }
    runParse(text);
  }

  function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file) return;
    if (file.size > UPLOAD_ACTION_BODY_LIMIT_BYTES) {
      toast.error("Could not read that file", {
        description:
          "That file is larger than 1 MB. Upload a single representative note, or paste the note text instead.",
      });
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    setView("parsing");
    startTransition(async () => {
      try {
        const ex = await extractNoteFileAction(fd);
        if (!ex.ok) {
          toast.error("Could not read that file", { description: ex.error });
          setView("entry");
          return;
        }
        setPasteText(ex.text);
        // runParse opens its own transition + owns its own error recovery (also
        // to 'entry'); this catch only covers the extract action itself.
        runParse(ex.text);
      } catch (err) {
        handleActionError(err, "entry");
      }
    });
  }

  function openTwinUpload(mode: TwinUploadMode) {
    twinUploadReturnFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setTwinFile(null);
    setTwinName(
      mode === "synthetic_staging"
        ? TEMPLATE_TWIN_STAGING_QA_TEMPLATE_NAME
        : "",
    );
    setTwinScope(
      mode === "synthetic_staging"
        ? TEMPLATE_TWIN_STAGING_QA_ENCOUNTER_SCOPE
        : "",
    );
    setTwinVersionDescription(
      mode === "synthetic_staging"
        ? TEMPLATE_TWIN_STAGING_QA_VERSION_DESCRIPTION
        : "",
    );
    setTwinUploadMode(mode);
    setTwinUploadOpen(true);
  }

  function onTwinFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".docx")) {
      toast.error("Choose an original .docx file", {
        description: "Macro-enabled .docm files are not accepted.",
      });
      return;
    }
    if (file.size === 0 || file.size > TEMPLATE_TWIN_MAX_BYTES) {
      toast.error("That Word template cannot be compiled", {
        description: "Template Twin accepts non-empty DOCX files up to 10 MB.",
      });
      return;
    }
    setTwinFile(file);
  }

  async function submitTwinUpload() {
    const name = twinName.trim();
    const encounterScope = twinScope.trim();
    const versionDescription = twinVersionDescription.trim();
    if (!twinFile || !name || !encounterScope || !versionDescription) {
      toast.error("Complete the template details", {
        description:
          "Choose the DOCX, name it, choose its visit scope, and describe this version.",
      });
      return;
    }

    const recoverView: View = hasTemplates ? "home" : "entry";
    setTwinUploadOpen(false);
    setView("twin-compiling");
    const formData = new FormData();
    formData.append("file", twinFile);
    formData.append("templateName", name);
    formData.append("encounterScope", encounterScope);
    formData.append("versionDescription", versionDescription);
    if (twinUploadMode === "synthetic_staging") {
      formData.append(
        "fixtureVersion",
        TEMPLATE_TWIN_STAGING_QA_FIXTURE_VERSION,
      );
    }

    try {
      const response = await fetch(
        twinUploadMode === "synthetic_staging"
          ? "/api/note-templates/template-twin/staging-qa/upload"
          : "/api/note-templates/template-twin/upload",
        {
          method: "POST",
          body: formData,
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        },
      );
      const payload = (await response.json().catch(() => null)) as
        | { ok: true; certificationUrl: string }
        | { ok: false; error: string }
        | null;
      if (!response.ok || !payload?.ok) {
        toast.error("That Word template could not be compiled", {
          description:
            payload && !payload.ok
              ? payload.error
              : "The file was not saved. Check it in Word and try again.",
        });
        setView(recoverView);
        return;
      }
      router.push(payload.certificationUrl);
    } catch {
      toast.error("Template upload did not finish", {
        description:
          "The file was not activated. Check your connection and try again.",
      });
      setView(recoverView);
    }
  }

  function chooseStandard() {
    toast.success("You’re on the standard format", {
      description:
        "Notes are written in QuillMD’s default SOAP structure — nothing changes.",
    });
    setView("home");
  }

  function onEdit(id: string) {
    startTransition(async () => {
      try {
        const res = await getNoteTemplateForEditAction(id);
        if (!res.ok) {
          toast.error(res.error);
          return;
        }
        setReview({ model: res.template, flags: [] });
        setView("review");
      } catch (err) {
        handleActionError(err, "home");
      }
    });
  }
  function onDuplicate(id: string) {
    startTransition(async () => {
      try {
        const res = await duplicateNoteTemplateAction(id);
        if (res.ok) {
          toast.success("Duplicated as a draft");
          router.refresh();
        } else toast.error(res.error);
      } catch (err) {
        handleActionError(err, "home");
      }
    });
  }
  function onActivate(id: string) {
    startTransition(async () => {
      try {
        const res = await activateNoteTemplateAction(id);
        if (res.ok) {
          toast.success("Format activated");
          router.refresh();
        } else toast.error(res.error);
      } catch (err) {
        handleActionError(err, "home");
      }
    });
  }
  function onDelete(id: string) {
    startTransition(async () => {
      try {
        const res = await deleteNoteTemplateAction(id);
        if (res.ok) {
          toast.success("Format deleted");
          router.refresh();
        } else toast.error(res.error);
      } catch (err) {
        handleActionError(err, "home");
      }
    });
  }

  function openNewTwinVersion(template: ClientTemplateListItem) {
    setTwinVersionSource(template);
    setNewTwinName(template.name);
    setNewTwinDescription("");
  }

  function submitNewTwinVersion() {
    if (!twinVersionSource) return;
    const name = newTwinName.trim();
    const versionDescription = newTwinDescription.trim();
    const encounterType = twinVersionSource.encounterType?.trim() ?? "";
    if (!name || !versionDescription || !encounterType) {
      toast.error("Complete the version details");
      return;
    }
    startTransition(async () => {
      try {
        const result = await createTemplateTwinVersionAction({
          sourceNoteTemplateId: twinVersionSource.id,
          name,
          encounterType,
          versionDescription,
        });
        if (!result.ok) {
          toast.error("New version was not created", {
            description: result.error,
          });
          return;
        }
        setTwinVersionSource(null);
        toast.success(`Version ${result.version} created as a draft`);
        router.push(
          `/settings/note-format/${encodeURIComponent(result.id)}/certify`,
        );
      } catch (error) {
        handleActionError(error, "home");
      }
    });
  }

  function activateTwinVersion(id: string) {
    startTransition(async () => {
      try {
        const result = await activateTemplateTwinVersionAction(id);
        if (!result.ok) {
          toast.error("Version was not activated", {
            description: result.error,
          });
          return;
        }
        toast.success(
          result.changed
            ? "Template Twin activated"
            : "This version is already active",
        );
        router.refresh();
      } catch (error) {
        handleActionError(error, "home");
      }
    });
  }

  function deactivateTwinVersion(id: string) {
    startTransition(async () => {
      try {
        const result = await deactivateTemplateTwinVersionAction(id);
        if (!result.ok) {
          toast.error("Version was not deactivated", {
            description: result.error,
          });
          return;
        }
        toast.success("Template Twin deactivated");
        router.refresh();
      } catch (error) {
        handleActionError(error, "home");
      }
    });
  }

  function retireTwinVersion(id: string, name: string) {
    if (
      !window.confirm(
        `Retire “${name}”? Its history will be kept, but it cannot be activated again.`,
      )
    ) {
      return;
    }
    startTransition(async () => {
      try {
        const result = await retireTemplateTwinVersionAction(id);
        if (!result.ok) {
          toast.error("Version was not retired", { description: result.error });
          return;
        }
        toast.success("Template Twin version retired");
        router.refresh();
      } catch (error) {
        handleActionError(error, "home");
      }
    });
  }

  function inspectTwinLineage(id: string) {
    setLineage(null);
    setLineageOpen(true);
    startTransition(async () => {
      try {
        const result = await inspectTemplateTwinLineageAction(id);
        if (!result.ok) {
          setLineageOpen(false);
          toast.error("Version history is unavailable", {
            description: result.error,
          });
          return;
        }
        setLineage({
          activeVersion: result.lineage.activeVersion,
          versions: result.lineage.versions,
        });
      } catch (error) {
        setLineageOpen(false);
        handleActionError(error, "home");
      }
    });
  }

  function rollbackTwinVersion(id: string) {
    startTransition(async () => {
      try {
        const result = await rollbackTemplateTwinVersionAction(id);
        if (!result.ok) {
          toast.error("Rollback was not completed", {
            description: result.error,
          });
          return;
        }
        toast.success(
          `Restored version ${result.rolledBackToVersion} from version ${result.rolledBackFromVersion}`,
        );
        setLineageOpen(false);
        setLineage(null);
        router.refresh();
      } catch (error) {
        handleActionError(error, "home");
      }
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────
  if (view === "review" && review) {
    return (
      <TemplateReviewEditor
        initial={review.model}
        parseFlags={review.flags}
        onCancel={() => setView(hasTemplates ? "home" : "entry")}
        onSaved={() => refreshHome()}
      />
    );
  }

  if (view === "parsing") {
    return <ParsingState />;
  }

  if (view === "twin-compiling") {
    return <TwinCompilingState />;
  }

  if (view === "rejected") {
    return (
      <RejectedState
        reason={rejectReason}
        onStandard={chooseStandard}
        onRetry={() => setView("entry")}
      />
    );
  }

  if (view === "entry") {
    return (
      <>
        <EntryState
          pasteText={pasteText}
          setPasteText={setPasteText}
          onParse={onParseClick}
          onUploadClick={() => fileRef.current?.click()}
          onUpload={onUpload}
          onStandard={chooseStandard}
          onBack={hasTemplates ? () => setView("home") : undefined}
          pending={pending}
          fileRef={fileRef}
          uploadCaps={uploadCaps}
          onTwinUploadClick={openTwinUpload}
          templateTwinSyntheticQaState={templateTwinSyntheticQaState}
        />
        <TwinUploadDialog
          open={
            twinUploadOpen &&
            (twinUploadMode === "generic" ||
              templateTwinSyntheticQaState === "enabled")
          }
          mode={twinUploadMode}
          file={twinFile}
          name={twinName}
          scope={twinScope}
          versionDescription={twinVersionDescription}
          fileRef={twinFileRef}
          returnFocusRef={twinUploadReturnFocusRef}
          onFileSelected={onTwinFileSelected}
          onNameChange={setTwinName}
          onScopeChange={setTwinScope}
          onVersionDescriptionChange={setTwinVersionDescription}
          onCancel={() => setTwinUploadOpen(false)}
          onSubmit={submitTwinUpload}
        />
      </>
    );
  }

  // view === 'home'
  return (
    <div>
      {templateTwinSyntheticQaState === "enabled" && (
        <div style={{ marginBottom: 14 }}>
          <TemplateTwinSyntheticQaBanner />
        </div>
      )}
      {templateTwinSyntheticQaState === "unavailable" && (
        <p
          role="status"
          style={{
            margin: "0 0 14px",
            padding: "10px 12px",
            border: "1px solid var(--color-linear-border)",
            borderRadius: 8,
            color: "var(--color-linear-text-3)",
            fontSize: 12,
          }}
        >
          Template Twin synthetic QA is unavailable in this practice or
          environment. No patient workflow was enabled.
        </p>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 16,
        }}
      >
        <p
          style={{
            fontSize: 12.5,
            color: "var(--color-linear-text-2)",
            lineHeight: 1.55,
            margin: 0,
            maxWidth: "70ch",
          }}
        >
          Your formats and which visits use them. QuillMD picks the right one
          per visit; without a match it uses the standard SOAP format. Defaults
          always follow the confirm-before-sign rule.
        </p>
        <div
          style={{
            display: "flex",
            gap: 8,
            flexWrap: "wrap",
            justifyContent: "flex-end",
          }}
        >
          <button
            type="button"
            style={btn}
            onClick={() => openTwinUpload("generic")}
            disabled={pending}
          >
            Preserve Word template
          </button>
          {templateTwinSyntheticQaState === "enabled" && (
            <button
              type="button"
              style={btn}
              onClick={() => openTwinUpload("synthetic_staging")}
              disabled={pending}
            >
              Template Twin — Synthetic QA
            </button>
          )}
          <button
            type="button"
            style={btnPrimary}
            onClick={() => setView("entry")}
            disabled={pending}
          >
            + Bring a note
          </button>
        </div>
      </div>

      <div
        style={{
          marginTop: 18,
          border: "1px solid var(--color-linear-border)",
          borderRadius: 10,
          overflow: "hidden",
        }}
      >
        {templates.map((t) => (
          <TemplateRow
            key={t.id}
            t={t}
            pending={pending}
            onEdit={() => onEdit(t.id)}
            onDuplicate={() => onDuplicate(t.id)}
            onActivate={() => onActivate(t.id)}
            onDelete={() => onDelete(t.id)}
            onTwinNewVersion={() => openNewTwinVersion(t)}
            onTwinActivate={() => activateTwinVersion(t.id)}
            onTwinDeactivate={() => deactivateTwinVersion(t.id)}
            onTwinRetire={() => retireTwinVersion(t.id, t.name)}
            onTwinLineage={() => inspectTwinLineage(t.id)}
          />
        ))}
        {/* Built-in fallback row (the standard format — not editable) */}
        <div style={{ ...rowStyle, borderBottom: "none" }}>
          <div>
            <div
              style={{
                fontSize: 13.5,
                fontWeight: 500,
                color: "var(--color-linear-text)",
              }}
            >
              Standard format
            </div>
            <div
              style={{
                fontSize: 11.5,
                color: "var(--color-linear-text-3)",
                marginTop: 2,
              }}
            >
              <span
                style={{
                  fontFamily: mono,
                  fontSize: 10,
                  letterSpacing: "0.04em",
                }}
              >
                SOAP
              </span>{" "}
              · QuillMD default · used when no format matches
            </div>
          </div>
          <span style={pill("fallback")}>Fallback</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              type="button"
              style={{ ...btn, opacity: 0.55, cursor: "not-allowed" }}
              disabled
              title="The built-in default can’t be edited"
            >
              Built-in
            </button>
          </div>
        </div>
      </div>

      <p
        style={{
          fontSize: 11.5,
          color: "var(--color-linear-text-3)",
          marginTop: 12,
          lineHeight: 1.5,
        }}
      >
        A visit uses the format whose specialty matches it; if none match,
        QuillMD writes in the standard SOAP format.
      </p>
      <TwinUploadDialog
        open={
          twinUploadOpen &&
          (twinUploadMode === "generic" ||
            templateTwinSyntheticQaState === "enabled")
        }
        mode={twinUploadMode}
        file={twinFile}
        name={twinName}
        scope={twinScope}
        versionDescription={twinVersionDescription}
        fileRef={twinFileRef}
        returnFocusRef={twinUploadReturnFocusRef}
        onFileSelected={onTwinFileSelected}
        onNameChange={setTwinName}
        onScopeChange={setTwinScope}
        onVersionDescriptionChange={setTwinVersionDescription}
        onCancel={() => setTwinUploadOpen(false)}
        onSubmit={submitTwinUpload}
      />
      <TwinNewVersionDialog
        source={twinVersionSource}
        name={newTwinName}
        versionDescription={newTwinDescription}
        pending={pending}
        onNameChange={setNewTwinName}
        onVersionDescriptionChange={setNewTwinDescription}
        onCancel={() => setTwinVersionSource(null)}
        onSubmit={submitNewTwinVersion}
      />
      <TwinLineageDialog
        open={lineageOpen}
        lineage={lineage}
        pending={pending}
        onClose={() => setLineageOpen(false)}
        onRollback={rollbackTwinVersion}
      />
    </div>
  );
}

function TwinUploadDialog({
  open,
  mode,
  file,
  name,
  scope,
  versionDescription,
  fileRef,
  returnFocusRef,
  onFileSelected,
  onNameChange,
  onScopeChange,
  onVersionDescriptionChange,
  onCancel,
  onSubmit,
}: {
  open: boolean;
  mode: TwinUploadMode;
  file: File | null;
  name: string;
  scope: string;
  versionDescription: string;
  fileRef: React.RefObject<HTMLInputElement | null>;
  returnFocusRef: React.RefObject<HTMLElement | null>;
  onFileSelected: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onNameChange: (value: string) => void;
  onScopeChange: (value: string) => void;
  onVersionDescriptionChange: (value: string) => void;
  onCancel: () => void;
  onSubmit: () => Promise<void>;
}) {
  const inputStyle: React.CSSProperties = {
    width: "100%",
    marginTop: 6,
    padding: "8px 10px",
    borderRadius: 6,
    border: "1px solid var(--color-linear-border)",
    background: "var(--color-linear-surface)",
    color: "var(--color-linear-text)",
    font: `13px ${sans}`,
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onCancel();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay
          data-testid="template-twin-upload-overlay"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 80,
            background: "rgba(5, 9, 7, 0.68)",
          }}
        />
        <Dialog.Content
          onInteractOutside={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            returnFocusRef.current?.focus();
          }}
          style={{
            position: "fixed",
            left: "50%",
            top: "50%",
            zIndex: 81,
            transform: "translate(-50%, -50%)",
            width: "min(560px, 100%)",
            maxHeight: "min(760px, calc(100vh - 40px))",
            overflowY: "auto",
            overscrollBehavior: "contain",
            borderRadius: 12,
            border: "1px solid var(--color-linear-border)",
            background: "var(--color-linear-surface-2)",
            boxShadow: "0 24px 70px rgba(0,0,0,0.38)",
            padding: 22,
            outline: "none",
          }}
        >
          {mode === "synthetic_staging" && <TemplateTwinSyntheticQaBanner />}
          <div
            style={{ ...subLabel, color: "var(--color-linear-sage-bright)" }}
          >
            Original Template DOCX
          </div>
          <Dialog.Title asChild>
            <h2
              style={{
                margin: "6px 0 0",
                fontSize: 18,
                fontWeight: 600,
                color: "var(--color-linear-text)",
              }}
            >
              {mode === "synthetic_staging"
                ? "Add the synthetic Word fixture for certification"
                : "Add a Word template for certification"}
            </h2>
          </Dialog.Title>
          <Dialog.Description asChild>
            <p
              style={{
                margin: "7px 0 18px",
                fontSize: 12.5,
                lineHeight: 1.55,
                color: "var(--color-linear-text-2)",
              }}
            >
              {mode === "synthetic_staging"
                ? "Use only the downloaded QuillMD synthetic fixture. Its bytes and fixture version are verified before storage, then every supported and blocked item is shown before activation."
                : "Name the template and say which visits use it. QuillMD will inspect the original structure, then show every supported and blocked item before anything can be activated."}
            </p>
          </Dialog.Description>

          <div style={{ display: "grid", gap: 14 }}>
            <div>
              <label htmlFor="twin-template-name" style={subLabel}>
                Template name
              </label>
              <input
                id="twin-template-name"
                required
                autoComplete="off"
                maxLength={120}
                value={name}
                readOnly={mode === "synthetic_staging"}
                onChange={(event) => onNameChange(event.target.value)}
                placeholder="e.g. Sports medicine initial visit"
                style={inputStyle}
              />
            </div>
            <div>
              <label htmlFor="twin-template-scope" style={subLabel}>
                Visit or specialty scope
              </label>
              <input
                id="twin-template-scope"
                required
                autoComplete="off"
                maxLength={120}
                value={scope}
                readOnly={mode === "synthetic_staging"}
                onChange={(event) => onScopeChange(event.target.value)}
                placeholder="e.g. New musculoskeletal consultation"
                style={inputStyle}
              />
              <div
                style={{
                  marginTop: 5,
                  fontSize: 11.5,
                  color: "var(--color-linear-text-3)",
                }}
              >
                This prevents a specialized template from becoming a catch-all
                format.
              </div>
            </div>
            <div>
              <label htmlFor="twin-version-description" style={subLabel}>
                What is this version?
              </label>
              <textarea
                id="twin-version-description"
                required
                maxLength={500}
                rows={3}
                value={versionDescription}
                readOnly={mode === "synthetic_staging"}
                onChange={(event) =>
                  onVersionDescriptionChange(event.target.value)
                }
                placeholder="e.g. Initial version supplied by the practice"
                style={{ ...inputStyle, resize: "vertical", lineHeight: 1.45 }}
              />
            </div>
            <div>
              <div style={subLabel}>Original DOCX</div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  marginTop: 6,
                  flexWrap: "wrap",
                }}
              >
                <button
                  type="button"
                  style={btn}
                  onClick={() => fileRef.current?.click()}
                >
                  {file ? "Choose a different file" : "Choose DOCX"}
                </button>
                <span
                  style={{
                    fontSize: 12,
                    color: file
                      ? "var(--color-linear-text)"
                      : "var(--color-linear-text-3)",
                  }}
                >
                  {file?.name ?? "No file selected"}
                </span>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={onFileSelected}
                style={{ display: "none" }}
                tabIndex={-1}
              />
            </div>
          </div>

          <details
            style={{
              marginTop: 16,
              fontSize: 11.5,
              color: "var(--color-linear-text-3)",
            }}
          >
            <summary style={{ cursor: "pointer" }}>
              Advanced artifact details
            </summary>
            <p style={{ margin: "7px 0 0", lineHeight: 1.5 }}>
              The uploaded source is stored as an immutable, tenant-scoped
              artifact. A changed template always creates a new version; the
              activated source is never overwritten.
              {mode === "synthetic_staging"
                ? ` Fixture contract: ${TEMPLATE_TWIN_STAGING_QA_FIXTURE_VERSION}.`
                : ""}
            </p>
          </details>

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
              marginTop: 20,
            }}
          >
            <Dialog.Close asChild>
              <button type="button" style={btn}>
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              style={btnPrimary}
              onClick={() => void onSubmit()}
              disabled={
                !file ||
                !name.trim() ||
                !scope.trim() ||
                !versionDescription.trim()
              }
            >
              Inspect and compile
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function TwinNewVersionDialog({
  source,
  name,
  versionDescription,
  pending,
  onNameChange,
  onVersionDescriptionChange,
  onCancel,
  onSubmit,
}: {
  source: ClientTemplateListItem | null;
  name: string;
  versionDescription: string;
  pending: boolean;
  onNameChange: (value: string) => void;
  onVersionDescriptionChange: (value: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  if (!source) return null;
  const inputStyle: React.CSSProperties = {
    width: "100%",
    marginTop: 6,
    padding: "8px 10px",
    borderRadius: 6,
    border: "1px solid var(--color-linear-border)",
    background: "var(--color-linear-surface)",
    color: "var(--color-linear-text)",
    font: `13px ${sans}`,
  };
  return (
    <div
      onKeyDown={(event) => {
        if (event.key === "Escape") onCancel();
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 80,
        display: "grid",
        placeItems: "center",
        padding: 20,
        background: "rgba(5, 9, 7, 0.68)",
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="template-twin-version-title"
        style={{
          width: "min(520px, 100%)",
          borderRadius: 12,
          border: "1px solid var(--color-linear-border)",
          background: "var(--color-linear-surface-2)",
          boxShadow: "0 24px 70px rgba(0,0,0,0.38)",
          padding: 22,
        }}
      >
        <div style={{ ...subLabel, color: "var(--color-linear-sage-bright)" }}>
          Immutable version history
        </div>
        <h2
          id="template-twin-version-title"
          style={{ margin: "6px 0 0", fontSize: 18, fontWeight: 600 }}
        >
          Create a new Template Twin version
        </h2>
        <p
          style={{
            margin: "7px 0 18px",
            fontSize: 12.5,
            lineHeight: 1.55,
            color: "var(--color-linear-text-2)",
          }}
        >
          The original Word file and detected structure stay unchanged. Field
          mappings, test evidence, waivers, and physician approval reset for
          this draft.
        </p>
        <div style={{ display: "grid", gap: 14 }}>
          <div>
            <label htmlFor="new-twin-name" style={subLabel}>
              Template name
            </label>
            <input
              id="new-twin-name"
              autoFocus
              maxLength={120}
              value={name}
              onChange={(event) => onNameChange(event.target.value)}
              style={inputStyle}
            />
          </div>
          <div>
            <div style={subLabel}>Visit scope</div>
            <div
              style={{
                marginTop: 6,
                fontSize: 13,
                color: "var(--color-linear-text)",
              }}
            >
              {source.encounterLabel}
            </div>
            <div
              style={{
                marginTop: 4,
                fontSize: 11.5,
                color: "var(--color-linear-text-3)",
              }}
            >
              A version keeps the same visit scope. Upload a separate template
              for a different scope.
            </div>
          </div>
          <div>
            <label htmlFor="new-twin-description" style={subLabel}>
              What changed in this version?
            </label>
            <textarea
              id="new-twin-description"
              rows={3}
              maxLength={500}
              value={versionDescription}
              onChange={(event) =>
                onVersionDescriptionChange(event.target.value)
              }
              placeholder="Describe the mapping or workflow change"
              style={{ ...inputStyle, resize: "vertical", lineHeight: 1.45 }}
            />
          </div>
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
            marginTop: 20,
          }}
        >
          <button
            type="button"
            style={btn}
            onClick={onCancel}
            disabled={pending}
          >
            Cancel
          </button>
          <button
            type="button"
            style={btnPrimary}
            onClick={onSubmit}
            disabled={pending || !name.trim() || !versionDescription.trim()}
          >
            Create draft version
          </button>
        </div>
      </section>
    </div>
  );
}

function TwinLineageDialog({
  open,
  lineage,
  pending,
  onClose,
  onRollback,
}: {
  open: boolean;
  lineage: {
    activeVersion: number | null;
    versions: TemplateTwinLineageVersion[];
  } | null;
  pending: boolean;
  onClose: () => void;
  onRollback: (id: string) => void;
}) {
  if (!open) return null;
  return (
    <div
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 80,
        display: "grid",
        placeItems: "center",
        padding: 20,
        background: "rgba(5, 9, 7, 0.68)",
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="template-twin-lineage-title"
        style={{
          width: "min(680px, 100%)",
          maxHeight: "min(760px, calc(100vh - 40px))",
          overflowY: "auto",
          borderRadius: 12,
          border: "1px solid var(--color-linear-border)",
          background: "var(--color-linear-surface-2)",
          boxShadow: "0 24px 70px rgba(0,0,0,0.38)",
          padding: 22,
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <div>
            <div
              style={{ ...subLabel, color: "var(--color-linear-sage-bright)" }}
            >
              Preserved history
            </div>
            <h2
              id="template-twin-lineage-title"
              style={{ margin: "6px 0 0", fontSize: 18, fontWeight: 600 }}
            >
              Template Twin versions
            </h2>
          </div>
          <button type="button" style={btn} onClick={onClose}>
            Close
          </button>
        </div>
        {!lineage ? (
          <p
            aria-live="polite"
            style={{
              marginTop: 18,
              color: "var(--color-linear-text-2)",
              fontSize: 13,
            }}
          >
            Loading version history…
          </p>
        ) : (
          <div style={{ display: "grid", gap: 10, marginTop: 18 }}>
            {lineage.versions.map((version) => (
              <div
                key={version.id}
                style={{
                  padding: "13px 14px",
                  border: "1px solid var(--color-linear-border)",
                  borderRadius: 8,
                  background: "var(--color-linear-surface)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 14,
                    alignItems: "flex-start",
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: 13.5,
                        fontWeight: 600,
                        color: "var(--color-linear-text)",
                      }}
                    >
                      Version {version.version} · {version.name}
                    </div>
                    <div
                      style={{
                        marginTop: 3,
                        fontSize: 11.5,
                        color: "var(--color-linear-text-3)",
                      }}
                    >
                      {version.status === "active"
                        ? "Active"
                        : titleCase(version.status)}{" "}
                      · {titleCase(version.certificationStatus)}
                    </div>
                  </div>
                  {version.rollbackEligible && (
                    <button
                      type="button"
                      style={btnPrimary}
                      onClick={() => onRollback(version.id)}
                      disabled={pending}
                    >
                      Restore this version
                    </button>
                  )}
                </div>
                <p
                  style={{
                    margin: "8px 0 0",
                    fontSize: 12,
                    lineHeight: 1.5,
                    color: "var(--color-linear-text-2)",
                  }}
                >
                  {version.versionDescription ||
                    "No version description was recorded."}
                </p>
                <details
                  style={{
                    marginTop: 8,
                    fontSize: 11,
                    color: "var(--color-linear-text-3)",
                  }}
                >
                  <summary style={{ cursor: "pointer" }}>
                    Advanced verification details
                  </summary>
                  <div
                    style={{
                      marginTop: 6,
                      fontFamily: mono,
                      overflowWrap: "anywhere",
                    }}
                  >
                    Compiler {version.compilerVersion} · source{" "}
                    {version.sourceSha256.slice(0, 12)}… ·{" "}
                    {version.sourceSizeBytes} bytes
                  </div>
                </details>
              </div>
            ))}
            {lineage.activeVersion === null && (
              <p
                style={{
                  margin: "4px 0 0",
                  fontSize: 12,
                  color: "var(--color-linear-text-3)",
                }}
              >
                No version in this lineage is currently active.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

// ── Templates list row ──────────────────────────────────────────────────────
const rowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr auto auto",
  gap: 14,
  alignItems: "center",
  padding: "13px 16px",
  borderBottom: "1px solid var(--color-linear-hairline)",
  background: "var(--color-linear-surface-2)",
};
function pill(
  kind: "active" | "draft" | "inactive" | "fallback",
): React.CSSProperties {
  const base: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 500,
    whiteSpace: "nowrap",
    background: "var(--color-linear-surface-2)",
    color: "var(--color-linear-text-2)",
    border: "1px solid var(--color-linear-border)",
  };
  if (kind === "active")
    return {
      ...base,
      background: "var(--color-linear-sage-tint)",
      color: "var(--color-linear-sage-bright)",
      border: "1px solid rgba(122,166,140,0.3)",
    };
  return base;
}

function TemplateRow({
  t,
  pending,
  onEdit,
  onDuplicate,
  onActivate,
  onDelete,
  onTwinNewVersion,
  onTwinActivate,
  onTwinDeactivate,
  onTwinRetire,
  onTwinLineage,
}: {
  t: ClientTemplateListItem;
  pending: boolean;
  onEdit: () => void;
  onDuplicate: () => void;
  onActivate: () => void;
  onDelete: () => void;
  onTwinNewVersion: () => void;
  onTwinActivate: () => void;
  onTwinDeactivate: () => void;
  onTwinRetire: () => void;
  onTwinLineage: () => void;
}) {
  if (t.templateKind === "template_twin_docx") {
    const certificationLabel =
      t.status === "retired"
        ? "Retired"
        : t.twinCertificationStatus === "certified"
          ? t.status === "active"
            ? `Active · ${t.encounterLabel}`
            : "Certified"
          : t.twinCertificationStatus === "unsupported"
            ? "Unsupported"
            : "Needs confirmation";
    return (
      <div style={rowStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontSize: 13.5,
                fontWeight: 500,
                color: "var(--color-linear-text)",
              }}
            >
              {t.name}
            </span>
            <span style={{ ...subLabel, fontSize: 9 }}>Original DOCX</span>
          </div>
          <div
            style={{
              fontSize: 11.5,
              color: "var(--color-linear-text-3)",
              marginTop: 2,
            }}
          >
            <span
              style={{
                fontFamily: mono,
                fontSize: 10,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {t.twinFieldCount} field{t.twinFieldCount === 1 ? "" : "s"}
            </span>
            {` · v${t.version}`}
            {t.twinBlockingUnsupportedCount > 0
              ? ` · ${t.twinBlockingUnsupportedCount} blocking item${t.twinBlockingUnsupportedCount === 1 ? "" : "s"}`
              : ""}
          </div>
        </div>
        <span style={pill(t.status === "active" ? "active" : "draft")}>
          {certificationLabel}
        </span>
        <div
          style={{
            display: "flex",
            gap: 6,
            flexWrap: "wrap",
            justifyContent: "flex-end",
          }}
        >
          <a
            href={`/settings/note-format/${encodeURIComponent(t.id)}/certify`}
            style={{ ...btn, textDecoration: "none" }}
          >
            {t.twinCertificationStatus === "certified" ? "Inspect" : "Continue"}
          </a>
          {t.twinCertificationStatus === "certified" &&
            t.status !== "retired" && (
              <button
                type="button"
                style={btn}
                onClick={onTwinNewVersion}
                disabled={pending}
              >
                New version
              </button>
            )}
          {t.twinCertificationStatus === "certified" &&
            t.status !== "active" &&
            t.status !== "retired" && (
              <button
                type="button"
                style={btnPrimary}
                onClick={onTwinActivate}
                disabled={pending}
              >
                Activate
              </button>
            )}
          {t.status === "active" && (
            <button
              type="button"
              style={btn}
              onClick={onTwinDeactivate}
              disabled={pending}
            >
              Deactivate
            </button>
          )}
          <button
            type="button"
            style={btn}
            onClick={onTwinLineage}
            disabled={pending}
          >
            Version history
          </button>
          {t.status !== "retired" && (
            <button
              type="button"
              style={{ ...btn, color: "var(--color-linear-text-3)" }}
              onClick={onTwinRetire}
              disabled={pending}
            >
              Retire
            </button>
          )}
        </div>
      </div>
    );
  }
  const statusLabel =
    t.status === "active"
      ? `Active · ${t.encounterLabel}`
      : t.status === "draft"
        ? "Draft"
        : t.status === "retired"
          ? "Retired"
          : "Superseded";
  return (
    <div style={rowStyle}>
      <div style={{ minWidth: 0 }}>
        <div
          style={{
            fontSize: 13.5,
            fontWeight: 500,
            color: "var(--color-linear-text)",
          }}
        >
          {t.name}
        </div>
        <div
          style={{
            fontSize: 11.5,
            color: "var(--color-linear-text-3)",
            marginTop: 2,
          }}
        >
          <span
            style={{
              fontFamily: mono,
              fontSize: 10,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
            }}
          >
            {t.sectionCount} section{t.sectionCount === 1 ? "" : "s"}
          </span>
          {" · "}
          {t.defaultCount} default{t.defaultCount === 1 ? "" : "s"}
          {t.version > 1 ? ` · v${t.version}` : ""}
        </div>
      </div>
      <span style={pill(t.status === "active" ? "active" : "draft")}>
        {statusLabel}
      </span>
      <div style={{ display: "flex", gap: 6 }}>
        <button type="button" style={btn} onClick={onEdit} disabled={pending}>
          Edit
        </button>
        {t.status !== "active" && (
          <button
            type="button"
            style={btnPrimary}
            onClick={onActivate}
            disabled={pending}
          >
            Activate
          </button>
        )}
        <button
          type="button"
          style={btn}
          onClick={onDuplicate}
          disabled={pending}
          aria-label={`Duplicate ${t.name}`}
        >
          Duplicate
        </button>
        <button
          type="button"
          style={{ ...btn, color: "var(--color-linear-text-3)" }}
          onClick={onDelete}
          disabled={pending}
          aria-label={`Delete ${t.name}`}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

// ── Entry ───────────────────────────────────────────────────────────────────
function EntryState({
  pasteText,
  setPasteText,
  onParse,
  onUploadClick,
  onUpload,
  onStandard,
  onBack,
  pending,
  fileRef,
  uploadCaps,
  onTwinUploadClick,
  templateTwinSyntheticQaState,
}: {
  pasteText: string;
  setPasteText: (v: string) => void;
  onParse: () => void;
  onUploadClick: () => void;
  onUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onStandard: () => void;
  onBack?: () => void;
  pending: boolean;
  fileRef: React.RefObject<HTMLInputElement | null>;
  uploadCaps: UploadCaps;
  onTwinUploadClick: (mode: TwinUploadMode) => void;
  templateTwinSyntheticQaState: "enabled" | "unavailable" | "hidden";
}) {
  // Only offer a format whose extractor actually loads in this image (incident
  // 2026-06-04). .txt/.md always available; .pdf/.docx gated on uploadCaps so we
  // never advertise-then-fail. Drives both the label and the <input accept>.
  const uploadKinds = [
    uploadCaps.pdf && { label: ".pdf", accept: ".pdf,application/pdf" },
    uploadCaps.docx && {
      label: ".docx",
      accept:
        ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    { label: ".txt", accept: ".txt,text/plain" },
    { label: ".md", accept: ".md,.markdown,text/markdown" },
  ].filter(Boolean) as { label: string; accept: string }[];
  const uploadSubLabel = ["Paste", ...uploadKinds.map((k) => k.label)].join(
    " · ",
  );
  const uploadAccept = uploadKinds.map((k) => k.accept).join(",");
  return (
    <div>
      {onBack && (
        <button
          type="button"
          style={{ ...btn, marginBottom: 14 }}
          onClick={onBack}
        >
          ← Back to my formats
        </button>
      )}
      <p
        style={{
          fontSize: 12.5,
          color: "var(--color-linear-text-2)",
          lineHeight: 1.55,
          margin: "0 0 16px",
          maxWidth: "70ch",
        }}
      >
        Bring a note you’ve already written and QuillMD will draft your future
        notes in that format — your sections, your order, your wording. Or stay
        on the standard format; you can change this anytime.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div
          style={{
            padding: 18,
            border: "1px solid rgba(122,166,140,0.32)",
            borderRadius: 10,
            background:
              "linear-gradient(180deg, var(--color-linear-sage-tint), var(--color-linear-surface-2))",
          }}
        >
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              letterSpacing: "-0.01em",
              color: "var(--color-linear-text)",
            }}
          >
            Bring your own note
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--color-linear-text-2)",
              lineHeight: 1.5,
              marginTop: 8,
            }}
          >
            Paste one of your notes, or upload a file. QuillMD reads the format
            and shows you what it understood — you edit and confirm.
          </div>
          <div style={{ ...subLabel, marginTop: 12 }}>{uploadSubLabel}</div>
        </div>
        <button
          type="button"
          onClick={onStandard}
          style={{
            textAlign: "left",
            padding: 18,
            border: "1px solid var(--color-linear-border)",
            borderRadius: 10,
            background: "var(--color-linear-surface-2)",
            cursor: "pointer",
            display: "block",
          }}
        >
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              letterSpacing: "-0.01em",
              color: "var(--color-linear-text)",
            }}
          >
            Start from the standard format
          </div>
          <div
            style={{
              fontSize: 12,
              color: "var(--color-linear-text-2)",
              lineHeight: 1.5,
              marginTop: 8,
            }}
          >
            Use QuillMD’s default SOAP structure. The right choice if you don’t
            want to customize — nothing changes about how notes are written
            today.
          </div>
          <div style={{ ...subLabel, marginTop: 12 }}>
            Subjective · Objective · Assessment · Plan
          </div>
        </button>
      </div>

      <section
        aria-labelledby="template-twin-docx-entry"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 18,
          padding: "14px 16px",
          border: "1px solid var(--color-linear-border)",
          borderRadius: 8,
          background: "var(--color-linear-surface-2)",
          marginTop: 14,
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: 1, minWidth: 240 }}>
          <div
            id="template-twin-docx-entry"
            style={{ ...subLabel, color: "var(--color-linear-sage-bright)" }}
          >
            Template Twin · DOCX
          </div>
          <div
            style={{
              fontSize: 13,
              color: "var(--color-linear-text)",
              fontWeight: 500,
              marginTop: 4,
            }}
          >
            Keep the original Word layout and controls
          </div>
          <p
            style={{
              margin: "4px 0 0",
              fontSize: 12,
              lineHeight: 1.5,
              color: "var(--color-linear-text-2)",
            }}
          >
            QuillMD stores an immutable copy, inventories every field, and asks
            you to certify the mapping before it can be used.
          </p>
        </div>
        <button
          type="button"
          style={btn}
          onClick={() => onTwinUploadClick("generic")}
          disabled={pending}
        >
          Upload original DOCX
        </button>
      </section>

      {templateTwinSyntheticQaState === "enabled" && (
        <section
          aria-labelledby="template-twin-synthetic-qa-entry"
          style={{
            marginTop: 14,
            padding: 16,
            border: "1px solid var(--color-linear-border)",
            borderRadius: 10,
            background: "var(--color-linear-surface-2)",
          }}
        >
          <TemplateTwinSyntheticQaBanner />
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 18,
              marginTop: 14,
              flexWrap: "wrap",
            }}
          >
            <div style={{ flex: 1, minWidth: 240 }}>
              <div
                id="template-twin-synthetic-qa-entry"
                style={{
                  ...subLabel,
                  color: "var(--color-linear-sage-bright)",
                }}
              >
                Template Twin — Synthetic QA
              </div>
              <div
                style={{
                  fontSize: 13,
                  color: "var(--color-linear-text)",
                  fontWeight: 500,
                  marginTop: 4,
                }}
              >
                Preserve the original Word layout through the real safety
                pipeline
              </div>
              <p
                style={{
                  margin: "4px 0 0",
                  fontSize: 12,
                  lineHeight: 1.5,
                  color: "var(--color-linear-text-2)",
                }}
              >
                Upload an allowlisted synthetic DOCX, inspect its fields,
                confirm clinical meaning, and run a synthetic visit before
                signing.
              </p>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <a
                href="/api/note-templates/template-twin/staging-qa/fixture"
                style={{ ...btn, textDecoration: "none" }}
                download
              >
                Download synthetic fixture
              </a>
              <button
                type="button"
                style={btnPrimary}
                onClick={() => onTwinUploadClick("synthetic_staging")}
                disabled={pending}
              >
                Upload synthetic DOCX
              </button>
            </div>
          </div>
        </section>
      )}
      {templateTwinSyntheticQaState === "unavailable" && (
        <div
          role="status"
          style={{
            marginTop: 14,
            padding: "12px 14px",
            border: "1px solid var(--color-linear-border)",
            borderRadius: 8,
            background: "var(--color-linear-surface-2)",
            color: "var(--color-linear-text-3)",
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          Template Twin synthetic QA is unavailable in this practice or
          environment. No template or patient workflow was enabled.
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <label style={{ ...subLabel }} htmlFor="nf-paste">
          Paste a note
        </label>
        <textarea
          id="nf-paste"
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          rows={5}
          placeholder="Paste one representative note here — e.g. a recent follow-up you wrote. Patient details are fine; they’re removed automatically and never saved."
          style={{
            width: "100%",
            marginTop: 6,
            padding: "8px 10px",
            minHeight: 96,
            lineHeight: 1.5,
            resize: "vertical",
            background: "var(--color-linear-surface-2)",
            border: "1px solid var(--color-linear-border)",
            borderRadius: 6,
            color: "var(--color-linear-text)",
            fontFamily: sans,
            fontSize: 13,
            outline: "none",
          }}
        />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginTop: 10,
          }}
        >
          <button
            type="button"
            style={btnPrimary}
            onClick={onParse}
            disabled={pending}
          >
            Read my format
          </button>
          <span style={{ color: "var(--color-linear-text-3)", fontSize: 11.5 }}>
            or
          </span>
          <button
            type="button"
            style={btn}
            onClick={onUploadClick}
            disabled={pending}
          >
            Upload a file
          </button>
          <input
            ref={fileRef}
            type="file"
            accept={uploadAccept}
            onChange={onUpload}
            style={{ display: "none" }}
            aria-hidden
            tabIndex={-1}
          />
        </div>
      </div>

      <div
        role="note"
        style={{
          display: "flex",
          gap: 10,
          alignItems: "flex-start",
          padding: "12px 14px",
          border: "1px solid var(--color-linear-hairline-strong)",
          borderRadius: 8,
          background: "var(--color-linear-surface-2)",
          marginTop: 14,
        }}
      >
        <span aria-hidden style={{ color: "var(--color-linear-sage)" }}>
          🛡
        </span>
        <p
          style={{
            margin: 0,
            fontSize: 12,
            color: "var(--color-linear-text-2)",
            lineHeight: 1.55,
          }}
        >
          Your note is read{" "}
          <b style={{ color: "var(--color-linear-text)", fontWeight: 500 }}>
            for format only
          </b>
          . Patient details — names, dates, findings — are removed automatically
          before anything is shown, and{" "}
          <b style={{ color: "var(--color-linear-text)", fontWeight: 500 }}>
            the note itself is never saved
          </b>
          . QuillMD keeps your structure, not your patients.
        </p>
      </div>
    </div>
  );
}

function TwinCompilingState() {
  return (
    <div
      aria-live="polite"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: "56px 24px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          border: "2px solid var(--color-linear-hairline-strong)",
          borderTopColor: "var(--color-linear-sage)",
          animation: "qm-spin 1.1s linear infinite",
        }}
        role="status"
        aria-label="Compiling the original Word template"
      />
      <div
        style={{
          fontSize: 16,
          fontWeight: 500,
          color: "var(--color-linear-text)",
        }}
      >
        Inspecting the original Word structure…
      </div>
      <p
        style={{
          margin: 0,
          fontSize: 12.5,
          color: "var(--color-linear-text-3)",
          maxWidth: "52ch",
          lineHeight: 1.55,
        }}
      >
        Checking the package, controls, tables, headers, and footers. Nothing is
        activated until you review a synthetic filled copy and certify it.
      </p>
      <style>{`@keyframes qm-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Parsing ─────────────────────────────────────────────────────────────────
function ParsingState() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        padding: "56px 24px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          border: "2px solid var(--color-linear-hairline-strong)",
          borderTopColor: "var(--color-linear-sage)",
          animation: "qm-spin 1.1s linear infinite",
        }}
        role="status"
        aria-label="Reading your note format"
      />
      <div
        style={{
          fontSize: 16,
          fontWeight: 500,
          color: "var(--color-linear-text)",
        }}
      >
        Reading your note format…
      </div>
      <p
        style={{
          margin: 0,
          fontSize: 12.5,
          color: "var(--color-linear-text-3)",
          maxWidth: "44ch",
          lineHeight: 1.55,
        }}
      >
        Finding your sections, order, and wording — and stripping any patient
        details. This stays private and isn’t saved.
      </p>
      <style>{`@keyframes qm-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Rejected ────────────────────────────────────────────────────────────────
function RejectedState({
  reason,
  onStandard,
  onRetry,
}: {
  reason: string;
  onStandard: () => void;
  onRetry: () => void;
}) {
  return (
    <div>
      <div
        style={{
          fontSize: 18,
          fontWeight: 500,
          letterSpacing: "-0.012em",
          color: "var(--color-linear-text)",
        }}
      >
        We couldn’t safely read this note
      </div>
      <div
        role="alert"
        style={{
          display: "flex",
          gap: 13,
          alignItems: "flex-start",
          padding: 16,
          border: "1px solid rgba(212,164,55,0.28)",
          borderRadius: 10,
          background: "rgba(212,164,55,0.05)",
          marginTop: 16,
        }}
      >
        <span
          aria-hidden
          style={{
            color: "var(--color-linear-amber)",
            fontSize: 18,
            lineHeight: 1,
          }}
        >
          ⚠
        </span>
        <div>
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: "var(--color-linear-text)",
            }}
          >
            This note has details we can’t fully separate
          </div>
          <div
            style={{
              fontSize: 12.5,
              color: "var(--color-linear-text-2)",
              lineHeight: 1.55,
              margin: "4px 0 12px",
              maxWidth: "64ch",
            }}
          >
            {reason} To keep your patients safe, QuillMD won’t build a format it
            isn’t sure is clean. Nothing was saved.
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" style={btnPrimary} onClick={onStandard}>
              Start from the standard format
            </button>
            <button type="button" style={btn} onClick={onRetry}>
              Remove patient details &amp; try again
            </button>
          </div>
        </div>
      </div>
      <div
        role="note"
        style={{
          display: "flex",
          gap: 10,
          alignItems: "flex-start",
          padding: "12px 14px",
          border: "1px solid var(--color-linear-hairline-strong)",
          borderRadius: 8,
          background: "var(--color-linear-surface-2)",
          marginTop: 16,
        }}
      >
        <span aria-hidden style={{ color: "var(--color-linear-sage)" }}>
          🛡
        </span>
        <p
          style={{
            margin: 0,
            fontSize: 12,
            color: "var(--color-linear-text-2)",
            lineHeight: 1.55,
          }}
        >
          The note you pasted was{" "}
          <b style={{ color: "var(--color-linear-text)", fontWeight: 500 }}>
            not saved
          </b>{" "}
          — it was discarded the moment we finished reading it.
        </p>
      </div>
    </div>
  );
}
