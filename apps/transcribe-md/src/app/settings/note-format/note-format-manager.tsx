'use client';

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

import { useCallback, useRef, useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';

import { parseNoteTemplateAction } from '@/actions/parse-note-template';
import { extractNoteFileAction } from '@/actions/extract-note-file';
import { isStaleDeploymentError } from '@/lib/stale-deployment';
import {
  activateNoteTemplateAction,
  duplicateNoteTemplateAction,
  deleteNoteTemplateAction,
  getNoteTemplateForEditAction,
  saveNoteTemplateAction,
} from '@/actions/note-template-lifecycle';
import {
  previewNativeDocumentAction,
  type NativePreviewResult,
} from '@/actions/preview-native-document';
import { previewNoteTemplateAction } from '@/actions/preview-note-template';
import { previewUploadedFormAction } from '@/actions/preview-uploaded-form';
import { NativeDocumentPreview } from '@/components/native-preview/native-document-preview';
import { SPECIALTY_IDS } from '@meddoc/shared/specialties';
import { certifyPdfTemplateAction } from '@/actions/certify-pdf-template';
import type { TemplateReviewModel, ClientTemplateListItem } from '@/lib/note-template-persist/types';
import { TemplateReviewEditor } from './template-review-editor';
// UX simplification pack (A) — flag-gated. OFF ⇒ every path below behaves
// exactly as before; the review editor stays the destination after a parse.
import { isUxSimplify } from '@/config/ux-simplify';
import { isDocPreview } from '@/config/doc-preview';
import { isSettingsSimpleRow } from '@/config/settings-simple-row';
import { ConfirmCard, ProcessingStages, useStages } from './upload-flow';

const mono = 'var(--font-mono)';
const sans = 'var(--font-sans)';

// Next.js server actions reject bodies over 1 MB BEFORE our action runs
// (no serverActions.bodySizeLimit is configured), so the server-side 5 MB
// check in actions/extract-note-file.ts (MAX_UPLOAD_BYTES) is unreachable
// and an oversized file surfaced only as a generic "Something went wrong"
// (custom-template QA 2026-07-02, finding F-4). Check client-side against
// the REAL limit and say so honestly. Keep in sync with the framework
// default; distinct name from the server constant to avoid drift confusion.
const UPLOAD_ACTION_BODY_LIMIT_BYTES = 1024 * 1024;
const btn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  padding: '6px 12px', borderRadius: 6, fontSize: 12, fontWeight: 500, fontFamily: sans,
  cursor: 'pointer', background: 'transparent', color: 'var(--color-linear-text-2)',
  border: '1px solid var(--color-linear-border)',
};
// C1-f: `color` and the ring were LITERALS. The Rounds host bridge retints
// custom properties and cannot touch a hex, so #0d1611 rode the bridged accent
// down to 3.43:1 on every primary button here. Both are tokens now; the old
// skin's values are unchanged (globals.css declares them as what was typed).
const btnPrimary: React.CSSProperties = {
  ...btn, background: 'var(--color-linear-sage)', color: 'var(--color-linear-on-sage)', border: 'none',
  boxShadow: '0 0 0 1px var(--color-linear-sage-ring)',
};
const subLabel: React.CSSProperties = {
  fontFamily: mono, fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase',
  color: 'var(--color-linear-text-3)',
};

/** Open a base64-encoded PDF (the one-time synthetic preview) in a new tab.
 *  Returns false when the browser blocked the popup (or on any error) so the
 *  caller can offer a fallback. */
function openPdfPreview(base64: string): boolean {
  try {
    const bin = atob(base64);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    const url = URL.createObjectURL(new Blob([buf], { type: 'application/pdf' }));
    const win = window.open(url, '_blank', 'noopener');
    // Revoke after a beat so the new tab has loaded it.
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return win !== null;
  } catch {
    return false;
  }
}

type View = 'home' | 'entry' | 'parsing' | 'review' | 'rejected' | 'confirm';

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
  nativePdfEnabled = false,
}: {
  templates: ClientTemplateListItem[];
  uploadCaps: UploadCaps;
  nativePdfEnabled?: boolean;
}) {
  const router = useRouter();
  const hasTemplates = templates.length > 0;
  const [view, setView] = useState<View>(hasTemplates ? 'home' : 'entry');
  const [pasteText, setPasteText] = useState('');
  const [review, setReview] = useState<{ model: TemplateReviewModel; flags: string[] } | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [pending, startTransition] = useTransition();

  // ── UX simplification pack (A) state. Inert when the flag is OFF. ──
  const uxSimplify = isUxSimplify();
  const docPreview = isDocPreview();
  /** The uploaded file is RETAINED through the flow so confirm can hand the
   *  same bytes to certifyPdfTemplateAction. The old flow extracted text and
   *  dropped the bytes, which is exactly why a second "Set up native export"
   *  upload existed at all. Kept in memory only — never persisted here. */
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  /** RC-2 (#106(b)) — the reference to the doctor's ORIGINAL uploaded .docx,
   *  returned by extractNoteFileAction and carried to the save unchanged.
   *  Cleared wherever `pendingFile` is, so a ref can never outlive the upload
   *  it describes and attach itself to the next one. */
  const [pendingSource, setPendingSource] = useState<
    { objectKey: string; sha256: string } | null
  >(null);

  /**
   * Drop the pending upload — the File AND its source ref, together, always.
   *
   * ⚠️ ONE FUNCTION BECAUSE A HAND-KEPT LIST OF CLEAR-SITES IS WRONG
   * EVENTUALLY. There are six places that abandon an upload (extract failure,
   * parse failure, cancel, a fresh paste, save success, certify success). Pair
   * them by hand and the day somebody adds a seventh, a ref outlives the file
   * it describes and attaches itself to the NEXT upload — pointing a new
   * template at the previous document. Putting the pairing in one place is the
   * same cure as hosting a component: it cannot be forgotten because there is
   * nothing to remember.
   */
  const clearPendingUpload = useCallback(() => {
    setPendingFile(null);
    setPendingSource(null);
  }, []);
  const { stages, step, reset: resetStages } = useStages(true);
  const [sample, setSample] = useState<NativePreviewResult | null>(null);
  const [sampleMarkdown, setSampleMarkdown] = useState<string | null>(null);
  const [sampleFailed, setSampleFailed] = useState(false);
  const [certError, setCertError] = useState<string | null>(null);
  /** Confirm failure shown IN the card. A toast alone auto-dismisses after 4s,
   *  which is exactly how a real failure gets misread as a dead button. */
  const [saveError, setSaveError] = useState<string | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  /** Set once confirm has activated the template, so a cert retry doesn't
   *  re-activate (and re-version) it. */
  const [activatedId, setActivatedId] = useState<string | null>(null);

  const isNativeCandidate =
    !!pendingFile &&
    (pendingFile.type === 'application/pdf' ||
      pendingFile.name.toLowerCase().endsWith('.pdf'));
  const fileRef = useRef<HTMLInputElement>(null);

  function refreshHome() {
    setReview(null);
    setPasteText('');
    router.refresh();
    setView('home');
  }

  // A server action THREW (rejected) rather than returning a typed result —
  // most often Next.js "deployment skew" (this tab loaded before a deploy, so
  // its server-action IDs no longer exist on the server). Never let that crash
  // to the full-page error boundary, which would lose the doctor's input: show
  // a clear message and return to a safe view with their text still visible.
  // Skew → a reload is the only fix (a re-mount keeps the stale bundle).
  function handleActionError(err: unknown, recoverView: View) {
    if (isStaleDeploymentError(err)) {
      toast.error('QuillMD was just updated', {
        description: 'Reload the page to continue — copy any unsaved text first.',
        action: { label: 'Reload', onClick: () => window.location.reload() },
        duration: 12000,
      });
    } else {
      toast.error('Something went wrong', {
        description: 'Please try again. If it keeps happening, reload the page.',
      });
    }
    setView(recoverView);
  }

  function runParse(text: string, sourceFile?: File) {
    setView('parsing');
    startTransition(async () => {
      try {
        const res = await parseNoteTemplateAction(text);
        if (res.rejected) {
          // PHI rejection stays exactly as prominent as before — the simplified
          // flow never softens or swallows it. Same view, same plain language.
          setRejectReason(res.reason);
          setView('rejected');
          return;
        }
        const model: TemplateReviewModel = {
          name: res.template.name,
          encounterType: res.template.encounterType,
          sections: res.template.sections,
          styleProfile: res.template.styleProfile,
        };
        setReview({ model, flags: res.flags });

        if (!uxSimplify) {
          setView('review');
          return;
        }

        // Stage 2 done — the count is READ OFF the result, not estimated.
        const sectionCount = model.sections.length;
        const headerCount = model.styleProfile.headerFields?.length ?? 0;
        step('sections', 'done', `${sectionCount}`);
        // Stage 3 needs no extra round trip: the header fields came back on the
        // same parse result. Mark it done immediately rather than fake latency.
        step('fields', 'done', headerCount > 0 ? `${headerCount}` : 'none');

        // Stage 4 — the filled sample. The staged view stays up until this
        // really resolves, so the last stage is genuinely observable rather
        // than a row that flashes complete. Failure NEVER blocks the confirm
        // card; it degrades to an honest "couldn't render a sample" note.
        setSample(null);
        setSampleFailed(false);
        try {
          // The doctor's OWN page, rendered from the bytes they just uploaded.
          // Filled for a flat PDF; the form itself for a .docx. Nothing is
          // persisted by this call and a failure never blocks the confirm.
          if (!docPreview) {
            // Flag OFF — the previous markdown sample, unchanged.
            const prev = await previewNoteTemplateAction(buildConfirmPayload(model));
            if (prev.ok) {
              setSampleMarkdown(prev.markdown);
              step('sample', 'done');
            } else {
              setSampleMarkdown('');
              setSampleFailed(true);
              step('sample', 'done', 'unavailable');
            }
            setView('confirm');
            return;
          }
          if (!sourceFile) {
            // Pasted text: there is no form. Say so — do not draw a mock.
            setSample({
              ok: false,
              kind: null,
              data: null,
              reason: 'no_form_uploaded',
            });
            step('sample', 'done');
            setView('confirm');
            return;
          }
          const pfd = new FormData();
          pfd.set('file', sourceFile);
          pfd.set('sections', JSON.stringify(model.sections ?? []));
          pfd.set(
            'headerFields',
            JSON.stringify(model.styleProfile?.headerFields ?? []),
          );
          const prev = await previewUploadedFormAction(pfd);
          if (prev.ok) {
            setSample(prev);
            step('sample', 'done', prev.kind === 'docx_fallback' ? 'close preview' : undefined);
          } else {
            setSample(prev);
            setSampleFailed(true);
            step('sample', 'done', 'unavailable');
          }
        } catch {
          // NOT null — the flag-ON card tests `sample === null` FIRST and would
          // sit on "Opening your form…" forever. A failure must look like a
          // failure, which is the whole point of carrying a reason.
          setSample({ ok: false, kind: null, data: null, reason: 'sample_unavailable' });
          setSampleMarkdown('');
          setSampleFailed(true);
          step('sample', 'done', 'unavailable');
        }
        setView('confirm');
      } catch (err) {
        handleActionError(err, 'entry');
      }
    });
  }

  /** The exact payload shape saveNoteTemplateAction + previewNoteTemplateAction
   *  validate (ReviewedTemplateSchema). Built from the parse result with no
   *  doctor edits — the confirm card is the "I didn't need to edit it" path.
   *
   *  formOnlyExport defaults ON for an uploaded form: the doctor brought their
   *  own document precisely because they want THAT document back. The toggle
   *  remains in Settings › My Note Format for opt-out. */
  function buildConfirmPayload(model: TemplateReviewModel) {
    // The parse LLM emits FREE-TEXT encounter types ("Operative Note",
    // "Follow-up progress note") that can never equal a visit.specialty, and
    // ReviewedTemplateSchema rejects anything outside the static catalog
    // (custom-template QA 2026-07-02, finding F-2). The review editor already
    // coerces an off-catalog value to the catch-all; the confirm card has to do
    // the SAME or a one-tap confirm fails on most real uploads.
    const encounterType =
      model.encounterType && (SPECIALTY_IDS as readonly string[]).includes(model.encounterType)
        ? model.encounterType
        : null;
    return {
      name: model.name.trim() || 'My note format',
      encounterType,
      // RC-2 — carried verbatim; the server validates it against the caller's
      // own practice before anything is written. Omitted entirely when absent,
      // because the schema is .strict() and `undefined` is not a value here.
      ...(pendingSource ? { source: pendingSource } : {}),
      sections: model.sections.map((s, i) => ({
        key: s.key,
        label: s.label.trim() || 'Section',
        order: i + 1,
        formatHint: s.formatHint,
        styleInstructions: s.styleInstructions,
        defaultText: s.defaultText,
        structure: s.structure ?? null,
      })),
      styleProfile: {
        tense: model.styleProfile.tense,
        tone: model.styleProfile.tone,
        abbreviations: model.styleProfile.abbreviations,
        contextDefaults: model.styleProfile.contextDefaults ?? null,
        headerFields: model.styleProfile.headerFields ?? null,
        formOnlyExport: true,
      },
    };
  }

  /** Run native-PDF certification for an already-activated template. Split out
   *  so the retry affordance re-runs ONLY this half — never re-activating (and
   *  re-versioning) a template that is already live. */
  async function runCertify(templateId: string, file: File): Promise<string | null> {
    const fd = new FormData();
    fd.append('templateId', templateId);
    fd.append('file', file);
    try {
      const res = await certifyPdfTemplateAction(fd);
      return res.ok ? null : res.error;
    } catch {
      return 'Setup failed — please try again.';
    }
  }

  /** THE one action. Activate + certify for native export + form-only, in a
   *  single confirm. This is what retires the CTA-once ritual: the upload IS
   *  the setup, so there is no separate "Set up native export" step and no
   *  dependence on the active template id staying put.
   *
   *  Failure policy — never silent: if certification fails the template is
   *  STILL activated (styled export works), and the card shows the real reason
   *  plus a retry. The doctor is never left with a dead button and no cause. */
  function onConfirmFormat() {
    if (!review) return;
    setConfirmBusy(true);
    setCertError(null);
    setSaveError(null);
    startTransition(async () => {
      try {
        let templateId = activatedId;

        // 1. Save + activate (skipped when a previous attempt already did it).
        if (!templateId) {
          const saved = await saveNoteTemplateAction(buildConfirmPayload(review.model), true);
          if (!saved.ok) {
            setSaveError(saved.error);
            toast.error('Could not use this format', { description: saved.error });
            setConfirmBusy(false);
            return;
          }
          templateId = saved.id;
          setActivatedId(saved.id);
        }

        // 2. Native-export certification — only for a flat PDF we still hold.
        let certFailure: string | null = null;
        if (pendingFile && isNativeCandidate) {
          certFailure = await runCertify(templateId, pendingFile);
        }

        if (certFailure) {
          setCertError(certFailure);
          setConfirmBusy(false);
          toast.warning('Format activated — native export needs another try', {
            description: certFailure,
            duration: 9000,
          });
          router.refresh();
          return;
        }

        toast.success('Format activated', {
          description: isNativeCandidate
            ? 'New matching visits will be written in this format and exported on your own page.'
            : 'New matching visits will be written in this format.',
        });
        clearPendingUpload();
        setActivatedId(null);
        refreshHome();
      } catch (err) {
        setConfirmBusy(false);
        handleActionError(err, 'confirm');
      }
    });
  }

  function onRetryCert() {
    if (!activatedId || !pendingFile) return;
    setConfirmBusy(true);
    startTransition(async () => {
      const failure = await runCertify(activatedId, pendingFile);
      setCertError(failure);
      setConfirmBusy(false);
      if (!failure) {
        toast.success('Native export is set up', {
          description: 'Exports will use your own page.',
        });
        clearPendingUpload();
        setActivatedId(null);
        refreshHome();
      }
    });
  }

  /** "Something's off" — the Advanced escape hatch. The full review editor is
   *  NOT deleted; it is simply no longer the default destination. */
  function onAdvanced() {
    setView('review');
  }

  function onParseClick() {
    const text = pasteText.trim();
    if (text.length === 0) {
      toast.error('Paste a note first');
      return;
    }
    // Mirror the server's 50k-char cap (parse-note-template.ts MAX_NOTE_CHARS)
    // client-side: a multi-MB paste would otherwise die at the framework's
    // 1 MB action-body limit with a generic error before the friendly
    // server message could run (finding F-4, paste path).
    if (text.length > 50_000) {
      toast.error('Note is too long', {
        description: 'Max 50,000 characters — paste a single representative note.',
      });
      return;
    }
    // Paste path: there is genuinely no file, so the "Reading your form" stage
    // is skipped rather than shown-and-instantly-completed, and there are no
    // PDF bytes to certify against.
    clearPendingUpload();
    setActivatedId(null);
    setCertError(null);
    setSample(null);
    setSampleMarkdown(null);
    setSampleFailed(false);
    resetStages(false);
    runParse(text);
  }

  function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file
    if (!file) return;
    if (file.size > UPLOAD_ACTION_BODY_LIMIT_BYTES) {
      toast.error('Could not read that file', {
        description:
          'That file is larger than 1 MB. Upload a single representative note, or paste the note text instead.',
      });
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    // Retain the bytes so confirm can certify native export from the SAME
    // upload. Also reset any prior attempt's state so a second try starts clean.
    setPendingFile(file);
    setActivatedId(null);
    setCertError(null);
    setSample(null);
    setSampleMarkdown(null);
    setSampleFailed(false);
    resetStages(true);
    setView('parsing');
    startTransition(async () => {
      try {
        const ex = await extractNoteFileAction(fd);
        if (!ex.ok) {
          toast.error('Could not read that file', { description: ex.error });
          clearPendingUpload();
          setView('entry');
          return;
        }
        // Stage 1 done — the file really has been read at this point.
        step('read', 'done');
        // Absent when the bytes could not be kept (storage down, or a
        // non-.docx). Absence means "we do not have the file" — never invented.
        setPendingSource(ex.source ?? null);
        setPasteText(ex.text);
        // runParse opens its own transition + owns its own error recovery (also
        // to 'entry'); this catch only covers the extract action itself.
        runParse(ex.text, file);
      } catch (err) {
        clearPendingUpload();
        handleActionError(err, 'entry');
      }
    });
  }

  function chooseStandard() {
    toast.success('You’re on the standard format', {
      description: 'Notes are written in QuillMD’s default SOAP structure — nothing changes.',
    });
    setView('home');
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
        setView('review');
      } catch (err) {
        handleActionError(err, 'home');
      }
    });
  }
  function onDuplicate(id: string) {
    startTransition(async () => {
      try {
        const res = await duplicateNoteTemplateAction(id);
        if (res.ok) { toast.success('Duplicated as a draft'); router.refresh(); }
        else toast.error(res.error);
      } catch (err) {
        handleActionError(err, 'home');
      }
    });
  }
  function onActivate(id: string) {
    startTransition(async () => {
      try {
        const res = await activateNoteTemplateAction(id);
        if (res.ok) { toast.success('Format activated'); router.refresh(); }
        else toast.error(res.error);
      } catch (err) {
        handleActionError(err, 'home');
      }
    });
  }
  function onDelete(id: string) {
    startTransition(async () => {
      try {
        const res = await deleteNoteTemplateAction(id);
        if (res.ok) { toast.success('Format deleted'); router.refresh(); }
        else toast.error(res.error);
      } catch (err) {
        handleActionError(err, 'home');
      }
    });
  }
  // Finish native-export setup: the doctor re-uploads his blank form once; we
  // certify it (canvas + anchors + derived header fields) and open a one-time
  // synthetic preview so he confirms placement.
  function onFinishNativeSetup(id: string, file: File) {
    // Same client-side pre-check as the bring-a-note upload (F-4): the server
    // action rejects bodies over 1 MB before our size check runs, so say so
    // honestly instead of surfacing a generic "Setup failed".
    if (file.size > UPLOAD_ACTION_BODY_LIMIT_BYTES) {
      toast.error('That PDF is larger than 1 MB — a blank form is usually well under. Try re-saving it.');
      return;
    }
    startTransition(async () => {
      try {
        const fd = new FormData();
        fd.set('templateId', id);
        fd.set('file', file);
        const res = await certifyPdfTemplateAction(fd);
        if (!res.ok) { toast.error(res.error); return; }
        toast.success(
          `Native export ready — ${res.anchors} field${res.anchors === 1 ? '' : 's'} mapped` +
            (res.headerFields ? `, ${res.headerFields} header field${res.headerFields === 1 ? '' : 's'}` : '') +
            (res.missing.length ? ` (${res.missing.length} label not found — check the preview)` : '')
        );
        if (res.previewBase64 && !openPdfPreview(res.previewBase64)) {
          toast.message('Preview blocked by your browser — export any visit to see your filled form.');
        }
        router.refresh();
      } catch (err) {
        handleActionError(err, 'home');
      }
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────
  if (view === 'review' && review) {
    return (
      <TemplateReviewEditor
        initial={review.model}
        parseFlags={review.flags}
        // RC-2 — the SECOND save caller. Threading the ref only through the
        // confirm card would lose the file for every doctor who takes the
        // Advanced route, i.e. the one that offers more control.
        source={pendingSource}
        onCancel={() => setView(hasTemplates ? 'home' : 'entry')}
        onSaved={() => refreshHome()}
      />
    );
  }

  // UX pack (A): the ONE confirm card. Flag-gated; `review` is always present
  // here because runParse only routes to 'confirm' after setting it.
  if (uxSimplify && view === 'confirm' && review) {
    return (
      <ConfirmCard
        name={review.model.name}
        sectionCount={review.model.sections.length}
        headerFieldCount={review.model.styleProfile.headerFields?.length ?? 0}
        sample={sample}
        sampleMarkdown={sampleMarkdown}
        docPreview={docPreview}
        sampleFailed={sampleFailed}
        nativeCandidate={isNativeCandidate}
        busy={confirmBusy || pending}
        certError={certError}
        saveError={saveError}
        onConfirm={onConfirmFormat}
        onRetryCert={onRetryCert}
        onAdvanced={onAdvanced}
        onCancel={() => {
          clearPendingUpload();
          setActivatedId(null);
          setCertError(null);
          setView(hasTemplates ? 'home' : 'entry');
        }}
      />
    );
  }

  if (view === 'parsing') {
    // Flag ON → the honest staged view; OFF → the original spinner, untouched.
    return uxSimplify ? <ProcessingStages stages={stages} /> : <ParsingState />;
  }

  if (view === 'rejected') {
    return (
      <RejectedState
        reason={rejectReason}
        onStandard={chooseStandard}
        onRetry={() => setView('entry')}
      />
    );
  }

  if (view === 'entry') {
    return (
      <EntryState
        pasteText={pasteText}
        setPasteText={setPasteText}
        onParse={onParseClick}
        onUploadClick={() => fileRef.current?.click()}
        onUpload={onUpload}
        onStandard={chooseStandard}
        onBack={hasTemplates ? () => setView('home') : undefined}
        pending={pending}
        fileRef={fileRef}
        uploadCaps={uploadCaps}
      />
    );
  }

  // view === 'home'
  return (
    <div className="qm-rounds-tmpl">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <p style={{ fontSize: 12.5, color: 'var(--color-linear-text-2)', lineHeight: 1.55, margin: 0, maxWidth: '70ch' }}>
          Your formats and which visits use them. QuillMD picks the right one per visit; without a match it uses the
          standard SOAP format. Defaults always follow the confirm-before-sign rule.
        </p>
        <button type="button" style={btnPrimary} onClick={() => setView('entry')} disabled={pending}>
          + Bring a note
        </button>
      </div>

      <div style={{ marginTop: 18, border: '1px solid var(--color-linear-border)', borderRadius: 10, overflow: 'hidden' }}>
        {templates.map((t) => (
          <TemplateRow
            key={t.id}
            t={t}
            pending={pending}
            nativePdfEnabled={nativePdfEnabled}
            onEdit={() => onEdit(t.id)}
            onDuplicate={() => onDuplicate(t.id)}
            onActivate={() => onActivate(t.id)}
            onDelete={() => onDelete(t.id)}
            onFinishNativeSetup={onFinishNativeSetup}
          />
        ))}
        {/* Built-in fallback row (the standard format — not editable) */}
        <div className="qm-rounds-tmpl-row" style={{ ...rowStyle, borderBottom: 'none' }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-linear-text)' }}>Standard format</div>
            <div style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)', marginTop: 2 }}>
              <span style={{ fontFamily: mono, fontSize: 10, letterSpacing: '0.04em' }}>SOAP</span> · QuillMD default · used when no format matches
            </div>
          </div>
          <span style={pill('fallback')}>Fallback</span>
          <div style={{ display: 'flex', gap: 6 }}>
            <button type="button" style={{ ...btn, opacity: 0.55, cursor: 'not-allowed' }} disabled title="The built-in default can’t be edited">Built-in</button>
          </div>
        </div>
      </div>

      <p style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)', marginTop: 12, lineHeight: 1.5 }}>
        A visit uses the format whose specialty matches it; if none match, QuillMD writes in the standard SOAP format.
      </p>
    </div>
  );
}

// ── Templates list row ──────────────────────────────────────────────────────
const rowStyle: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 14, alignItems: 'center',
  padding: '13px 16px', borderBottom: '1px solid var(--color-linear-hairline)',
  background: 'var(--color-linear-surface-2)',
};
function pill(kind: 'active' | 'draft' | 'inactive' | 'fallback'): React.CSSProperties {
  const base: React.CSSProperties = {
    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '2px 8px', borderRadius: 4,
    fontSize: 11, fontWeight: 500, whiteSpace: 'nowrap',
    background: 'var(--color-linear-surface-2)', color: 'var(--color-linear-text-2)',
    border: '1px solid var(--color-linear-border)',
  };
  if (kind === 'active') return { ...base, background: 'var(--color-linear-sage-tint)', color: 'var(--color-linear-sage-bright)', border: '1px solid var(--color-linear-sage-ring)' };
  return base;
}

function TemplateRow({
  t, pending, nativePdfEnabled, onEdit, onDuplicate, onActivate, onDelete, onFinishNativeSetup,
}: {
  t: ClientTemplateListItem;
  pending: boolean;
  nativePdfEnabled: boolean;
  onEdit: () => void;
  onDuplicate: () => void;
  onActivate: () => void;
  onDelete: () => void;
  onFinishNativeSetup: (id: string, file: File) => void;
}) {
  const setupRef = useRef<HTMLInputElement | null>(null);
  const [overflowOpen, setOverflowOpen] = useState(false);
  /** The inline "See your form" panel. `preview === null` means still loading;
   *  a failed load still SETS a result carrying its named reason, so the panel
   *  can never sit on a spinner forever. */
  const docPreviewRow = isDocPreview();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [preview, setPreview] = useState<NativePreviewResult | null>(null);

  async function togglePreview() {
    if (previewOpen) {
      setPreviewOpen(false);
      return;
    }
    setPreviewOpen(true);
    if (preview) return; // already fetched for this row
    try {
      setPreview(await previewNativeDocumentAction(t.id));
    } catch {
      setPreview({ ok: false, kind: null, data: null, reason: 'sample_unavailable' });
    }
  }
  const simpleRow = isSettingsSimpleRow();
  const statusLabel = t.status === 'active'
    ? `Active · ${t.encounterLabel}`
    : t.status === 'draft' ? 'Draft' : 'Superseded';
  // Native-export setup surfaces ONLY on the active format when the flag is on.
  const showNative = nativePdfEnabled && t.status === 'active';

  // ── THE SIMPLE ROW ──────────────────────────────────────────────────────
  // name · Active · Replace · Delete, everything else behind ⋯.
  //
  // The "Set up native export" CTA is gone, and not conditionally: there is
  // nothing for the doctor to decide. Replace already does the whole job —
  // the upload activates, certifies, sets form-only and previews once — so a
  // separate ritual that asks for the same file under a different name is
  // pure ceremony. When we cannot fill their own page, that is a FACT we
  // report on one line, not a task we hand back.
  if (simpleRow) {
    return (
      <div className="qm-rounds-tmpl-row" style={rowStyle}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-linear-text)' }}>
            {t.name}
          </div>
          {showNative && (
            <div
              style={{
                fontSize: 11,
                marginTop: 4,
                color: t.pdfNativeCertified
                  ? 'var(--color-linear-sage-bright)'
                  : 'var(--color-linear-text-3)',
              }}
              data-testid="template-row-status"
            >
              {t.pdfNativeCertified
                ? 'Exports use your own form'
                : 'Exports use a styled copy — Replace with your blank form to use your own'}
            </div>
          )}
          {/* SEE IT. A doctor should not have to export a real visit to find
              out what their exports look like. This opens the artifact
              certification itself verified — their page, filled — inline. */}
          {docPreviewRow && t.nativePreviewAvailable && (
            <button
              type="button"
              onClick={() => void togglePreview()}
              aria-expanded={previewOpen}
              data-testid="template-row-see-form"
              style={{
                marginTop: 6,
                padding: 0,
                background: 'none',
                border: 0,
                font: 'inherit',
                fontSize: 11,
                color: 'var(--color-linear-text-3)',
                textDecoration: 'underline',
                textUnderlineOffset: 3,
                cursor: 'pointer',
              }}
            >
              {previewOpen ? 'Hide your form' : 'See your form'}
            </button>
          )}
        </div>
        <span style={pill(t.status === 'active' ? 'active' : 'draft')}>{statusLabel}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {t.status !== 'active' && (
            <button type="button" style={btnPrimary} onClick={onActivate} disabled={pending}>
              Activate
            </button>
          )}
          <input
            ref={setupRef}
            type="file"
            accept=".pdf,application/pdf,.docx"
            style={{ display: 'none' }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFinishNativeSetup(t.id, f);
              e.target.value = '';
            }}
          />
          <button
            type="button"
            style={btn}
            onClick={() => setupRef.current?.click()}
            disabled={pending}
            data-testid="template-row-replace"
          >
            Replace
          </button>
          <button
            type="button"
            style={{ ...btn, color: 'var(--color-linear-text-3)' }}
            onClick={onDelete}
            disabled={pending}
            aria-label={`Delete ${t.name}`}
          >
            Delete
          </button>
          <div style={{ position: 'relative' }}>
            <button
              type="button"
              style={{ ...btn, padding: '6px 9px', color: 'var(--color-linear-text-3)' }}
              onClick={() => setOverflowOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={overflowOpen}
              aria-label={`More actions for ${t.name}`}
              data-testid="template-row-overflow"
              disabled={pending}
            >
              ⋯
            </button>
            {overflowOpen && (
              <div role="menu" className="qm-tmpl-overflow" data-testid="template-row-overflow-menu">
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => { setOverflowOpen(false); onEdit(); }}
                >
                  Advanced editor
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => { setOverflowOpen(false); onDuplicate(); }}
                >
                  Duplicate
                </button>
              </div>
            )}
          </div>
        </div>
        {previewOpen && (
          <div style={{ gridColumn: '1 / -1', marginTop: 12 }} data-testid="template-row-preview">
            {preview === null ? (
              <p style={{ fontSize: 12, color: 'var(--color-linear-text-3)', margin: 0 }}>
                Opening your form…
              </p>
            ) : (
              <NativeDocumentPreview
                kind={preview.kind}
                data={preview.data}
                reason={preview.reason}
                label={`${t.name} — your form, filled`}
                caption="Filled with the synthetic visit your template was certified against — no patient data."
              />
            )}
          </div>
        )}
      </div>
    );
  }

  // (statusLabel / showNative are declared above, shared by both branches.)
  return (
    <div style={rowStyle}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--color-linear-text)' }}>{t.name}</div>
        <div style={{ fontSize: 11.5, color: 'var(--color-linear-text-3)', marginTop: 2 }}>
          <span style={{ fontFamily: mono, fontSize: 10, letterSpacing: '0.04em', textTransform: 'uppercase' }}>{t.sectionCount} section{t.sectionCount === 1 ? '' : 's'}</span>
          {' · '}{t.defaultCount} default{t.defaultCount === 1 ? '' : 's'}
          {t.version > 1 ? ` · v${t.version}` : ''}
        </div>
        {showNative && t.pdfNativeCertified && (
          <div style={{ fontSize: 11, color: 'var(--color-linear-sage-bright)', marginTop: 4, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span aria-hidden>✓</span> Native export ready — your form is filled in for exports
          </div>
        )}
        {showNative && !t.pdfNativeCertified && (
          <div style={{ fontSize: 11, color: 'var(--color-linear-amber)', marginTop: 4 }}>
            {t.pdfNativePendingPreview
              ? "Native export needs the original flat PDF form — re-upload to finish."
              : 'Exports use a styled re-creation. Finish setup to fill your own form instead.'}
          </div>
        )}
      </div>
      <span style={pill(t.status === 'active' ? 'active' : 'draft')}>{statusLabel}</span>
      <div style={{ display: 'flex', gap: 6 }}>
        {showNative && !t.pdfNativeCertified && (
          <>
            <input
              ref={setupRef}
              type="file"
              accept=".pdf,application/pdf"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFinishNativeSetup(t.id, f);
                e.target.value = '';
              }}
            />
            <button
              type="button"
              style={btnPrimary}
              onClick={() => setupRef.current?.click()}
              disabled={pending}
              title="Upload your blank form to fill your own page on export"
            >
              Set up native export
            </button>
          </>
        )}
        <button type="button" style={btn} onClick={onEdit} disabled={pending}>Edit</button>
        {t.status !== 'active' && (
          <button type="button" style={btnPrimary} onClick={onActivate} disabled={pending}>Activate</button>
        )}
        <button type="button" style={btn} onClick={onDuplicate} disabled={pending} aria-label={`Duplicate ${t.name}`}>Duplicate</button>
        <button type="button" style={{ ...btn, color: 'var(--color-linear-text-3)' }} onClick={onDelete} disabled={pending} aria-label={`Delete ${t.name}`}>Delete</button>
      </div>
    </div>
  );
}

// ── Entry ───────────────────────────────────────────────────────────────────
function EntryState({
  pasteText, setPasteText, onParse, onUploadClick, onUpload, onStandard, onBack, pending, fileRef, uploadCaps,
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
}) {
  // Only offer a format whose extractor actually loads in this image (incident
  // 2026-06-04). .txt/.md always available; .pdf/.docx gated on uploadCaps so we
  // never advertise-then-fail. Drives both the label and the <input accept>.
  const uploadKinds = [
    uploadCaps.pdf && { label: '.pdf', accept: '.pdf,application/pdf' },
    uploadCaps.docx && {
      label: '.docx',
      accept:
        '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    },
    { label: '.txt', accept: '.txt,text/plain' },
    { label: '.md', accept: '.md,.markdown,text/markdown' },
  ].filter(Boolean) as { label: string; accept: string }[];
  const uploadSubLabel = ['Paste', ...uploadKinds.map((k) => k.label)].join(' · ');
  const uploadAccept = uploadKinds.map((k) => k.accept).join(',');
  return (
    <div className="qm-rounds-tmpl">
      {onBack && (
        <button type="button" style={{ ...btn, marginBottom: 14 }} onClick={onBack}>← Back to my formats</button>
      )}
      <p style={{ fontSize: 12.5, color: 'var(--color-linear-text-2)', lineHeight: 1.55, margin: '0 0 16px', maxWidth: '70ch' }}>
        Bring a note you’ve already written and QuillMD will draft your future notes in that format — your sections,
        your order, your wording. Or stay on the standard format; you can change this anytime.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div className="qm-rounds-tmpl-card" style={{ padding: 18, border: '1px solid var(--color-linear-sage-edge)', borderRadius: 10, background: 'linear-gradient(180deg, var(--color-linear-sage-tint), var(--color-linear-surface-2))' }}>
          <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--color-linear-text)' }}>Bring your own note</div>
          <div style={{ fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.5, marginTop: 8 }}>
            Paste one of your notes, or upload a file. QuillMD reads the format and shows you what it understood — you
            edit and confirm.
          </div>
          <div style={{ ...subLabel, marginTop: 12 }}>{uploadSubLabel}</div>
        </div>
        <button
          type="button"
          onClick={onStandard}
          className="qm-rounds-tmpl-card"
          style={{ textAlign: 'left', padding: 18, border: '1px solid var(--color-linear-border)', borderRadius: 10, background: 'var(--color-linear-surface-2)', cursor: 'pointer', display: 'block' }}
        >
          <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--color-linear-text)' }}>Start from the standard format</div>
          <div style={{ fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.5, marginTop: 8 }}>
            Use QuillMD’s default SOAP structure. The right choice if you don’t want to customize — nothing changes
            about how notes are written today.
          </div>
          <div style={{ ...subLabel, marginTop: 12 }}>Subjective · Objective · Assessment · Plan</div>
        </button>
      </div>

      <div style={{ marginTop: 16 }}>
        <label style={{ ...subLabel }} htmlFor="nf-paste">Paste a note</label>
        <textarea
          id="nf-paste"
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          rows={5}
          placeholder="Paste one representative note here — e.g. a recent follow-up you wrote. Patient details are fine; they’re removed automatically and never saved."
          style={{
            width: '100%', marginTop: 6, padding: '8px 10px', minHeight: 96, lineHeight: 1.5, resize: 'vertical',
            background: 'var(--color-linear-surface-2)', border: '1px solid var(--color-linear-border)', borderRadius: 6,
            color: 'var(--color-linear-text)', fontFamily: sans, fontSize: 13, outline: 'none',
          }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 10 }}>
          <button type="button" style={btnPrimary} onClick={onParse} disabled={pending}>Read my format</button>
          <span style={{ color: 'var(--color-linear-text-3)', fontSize: 11.5 }}>or</span>
          <button type="button" style={btn} onClick={onUploadClick} disabled={pending}>Upload a file</button>
          <input ref={fileRef} type="file" accept={uploadAccept} onChange={onUpload} style={{ display: 'none' }} aria-hidden tabIndex={-1} />
        </div>
      </div>

      <div role="note" style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '12px 14px', border: '1px solid var(--color-linear-hairline-strong)', borderRadius: 8, background: 'var(--color-linear-surface-2)', marginTop: 14 }}>
        <span aria-hidden style={{ color: 'var(--color-linear-sage-bright)' }}>🛡</span>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.55 }}>
          Your note is read <b style={{ color: 'var(--color-linear-text)', fontWeight: 500 }}>for format only</b>. Patient details — names, dates, findings — are removed automatically before anything is shown, and <b style={{ color: 'var(--color-linear-text)', fontWeight: 500 }}>the note itself is never saved</b>. QuillMD keeps your structure, not your patients.
        </p>
      </div>
    </div>
  );
}

// ── Parsing ─────────────────────────────────────────────────────────────────
function ParsingState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '56px 24px', textAlign: 'center' }}>
      <div style={{ width: 40, height: 40, borderRadius: '50%', border: '2px solid var(--color-linear-hairline-strong)', borderTopColor: 'var(--color-linear-sage)', animation: 'qm-spin 1.1s linear infinite' }} role="status" aria-label="Reading your note format" />
      <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--color-linear-text)' }}>Reading your note format…</div>
      <p style={{ margin: 0, fontSize: 12.5, color: 'var(--color-linear-text-3)', maxWidth: '44ch', lineHeight: 1.55 }}>
        Finding your sections, order, and wording — and stripping any patient details. This stays private and isn’t saved.
      </p>
      <style>{`@keyframes qm-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Rejected ────────────────────────────────────────────────────────────────
export function RejectedState({ reason, onStandard, onRetry }: { reason: string; onStandard: () => void; onRetry: () => void }) {
  return (
    <div className="qm-rounds-tmpl">
      <div style={{ fontSize: 18, fontWeight: 500, letterSpacing: '-0.012em', color: 'var(--color-linear-text)' }}>
        We couldn’t safely read this note
      </div>
      <div role="alert" className="qm-rounds-tmpl-alert" style={{ display: 'flex', gap: 13, alignItems: 'flex-start', padding: 16, border: '1px solid var(--color-linear-amber-edge)', borderRadius: 10, background: 'var(--color-linear-amber-wash)', marginTop: 16 }}>
        <span aria-hidden style={{ color: 'var(--color-linear-amber)', fontSize: 18, lineHeight: 1 }}>⚠</span>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-linear-text)' }}>This note has details we can’t fully separate</div>
          <div style={{ fontSize: 12.5, color: 'var(--color-linear-text-2)', lineHeight: 1.55, margin: '4px 0 12px', maxWidth: '64ch' }}>
            {reason} To keep your patients safe, QuillMD won’t build a format it isn’t sure is clean. Nothing was saved.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" style={btnPrimary} onClick={onStandard}>Start from the standard format</button>
            <button type="button" style={btn} onClick={onRetry}>Remove patient details &amp; try again</button>
          </div>
        </div>
      </div>
      <div role="note" style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '12px 14px', border: '1px solid var(--color-linear-hairline-strong)', borderRadius: 8, background: 'var(--color-linear-surface-2)', marginTop: 16 }}>
        <span aria-hidden style={{ color: 'var(--color-linear-sage-bright)' }}>🛡</span>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.55 }}>
          The note you pasted was <b style={{ color: 'var(--color-linear-text)', fontWeight: 500 }}>not saved</b> — it was discarded the moment we finished reading it.
        </p>
      </div>
    </div>
  );
}
