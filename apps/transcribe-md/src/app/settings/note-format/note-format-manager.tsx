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

import { useRef, useState, useTransition } from 'react';
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
} from '@/actions/note-template-lifecycle';
import { certifyPdfTemplateAction } from '@/actions/certify-pdf-template';
import type { TemplateReviewModel, ClientTemplateListItem } from '@/lib/note-template-persist/types';
import { TemplateReviewEditor } from './template-review-editor';

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
const btnPrimary: React.CSSProperties = {
  ...btn, background: 'var(--color-linear-sage)', color: '#0d1611', border: 'none',
  boxShadow: '0 0 0 1px rgba(122,166,140,0.3)',
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

type View = 'home' | 'entry' | 'parsing' | 'review' | 'rejected';

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

  function runParse(text: string) {
    setView('parsing');
    startTransition(async () => {
      try {
        const res = await parseNoteTemplateAction(text);
        if (res.rejected) {
          setRejectReason(res.reason);
          setView('rejected');
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
          setView('review');
        }
      } catch (err) {
        handleActionError(err, 'entry');
      }
    });
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
    setView('parsing');
    startTransition(async () => {
      try {
        const ex = await extractNoteFileAction(fd);
        if (!ex.ok) {
          toast.error('Could not read that file', { description: ex.error });
          setView('entry');
          return;
        }
        setPasteText(ex.text);
        // runParse opens its own transition + owns its own error recovery (also
        // to 'entry'); this catch only covers the extract action itself.
        runParse(ex.text);
      } catch (err) {
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
        onCancel={() => setView(hasTemplates ? 'home' : 'entry')}
        onSaved={() => refreshHome()}
      />
    );
  }

  if (view === 'parsing') {
    return <ParsingState />;
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
    <div>
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
        <div style={{ ...rowStyle, borderBottom: 'none' }}>
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
  if (kind === 'active') return { ...base, background: 'var(--color-linear-sage-tint)', color: 'var(--color-linear-sage-bright)', border: '1px solid rgba(122,166,140,0.3)' };
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
  const statusLabel = t.status === 'active'
    ? `Active · ${t.encounterLabel}`
    : t.status === 'draft' ? 'Draft' : 'Superseded';
  // Native-export setup surfaces ONLY on the active format when the flag is on.
  // Certified → a calm "Native ✓" chip; otherwise a "Set up native export" CTA
  // the doctor can actually see + act on (re-upload his blank form once).
  const showNative = nativePdfEnabled && t.status === 'active';
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
    <div>
      {onBack && (
        <button type="button" style={{ ...btn, marginBottom: 14 }} onClick={onBack}>← Back to my formats</button>
      )}
      <p style={{ fontSize: 12.5, color: 'var(--color-linear-text-2)', lineHeight: 1.55, margin: '0 0 16px', maxWidth: '70ch' }}>
        Bring a note you’ve already written and QuillMD will draft your future notes in that format — your sections,
        your order, your wording. Or stay on the standard format; you can change this anytime.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div style={{ padding: 18, border: '1px solid rgba(122,166,140,0.32)', borderRadius: 10, background: 'linear-gradient(180deg, var(--color-linear-sage-tint), var(--color-linear-surface-2))' }}>
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
        <span aria-hidden style={{ color: 'var(--color-linear-sage)' }}>🛡</span>
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
function RejectedState({ reason, onStandard, onRetry }: { reason: string; onStandard: () => void; onRetry: () => void }) {
  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 500, letterSpacing: '-0.012em', color: 'var(--color-linear-text)' }}>
        We couldn’t safely read this note
      </div>
      <div role="alert" style={{ display: 'flex', gap: 13, alignItems: 'flex-start', padding: 16, border: '1px solid rgba(212,164,55,0.28)', borderRadius: 10, background: 'rgba(212,164,55,0.05)', marginTop: 16 }}>
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
        <span aria-hidden style={{ color: 'var(--color-linear-sage)' }}>🛡</span>
        <p style={{ margin: 0, fontSize: 12, color: 'var(--color-linear-text-2)', lineHeight: 1.55 }}>
          The note you pasted was <b style={{ color: 'var(--color-linear-text)', fontWeight: 500 }}>not saved</b> — it was discarded the moment we finished reading it.
        </p>
      </div>
    </div>
  );
}
