'use client';

// ============================================================================
// SoapEditor — visit-detail SOAP note editor pane.
// ----------------------------------------------------------------------------
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the dark .qm-card + violet
// focus ring rendering verbatim. Migrated surfaces (visit-detail)
// pass `theme="clinician"`, which swaps the editor surface to the
// soft cream-card with sage focus ring and renders the markdown
// preview through `.qm-cl-prose` (Source Serif 4 16px / 1.7lh) for
// the "letter from your doctor" SOAP body the visit-detail mockup
// commits to.
// ============================================================================

import { useState, useTransition } from 'react';
import { Lock, Loader2, Check, PencilLine, Send } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { SpecularButton } from '@/components/specular-button';
import { saveSoapDraftAction } from '@/actions/soap';
import { SignAndSendModal } from './sign-and-send-modal';

type SoapEditorTheme = 'legacy' | 'clinician';

interface SoapEditorProps {
  visitId: string;
  /** Doctor's email — pre-filled in the Sign & Send modal. */
  doctorEmail: string;
  /** T-M9 — whether Email delivery is configured. Hides the checkbox
   *  from Sign & Send when false so users can't request an
   *  un-shippable destination. */
  emailEnabled: boolean;
  initialText: string;
  /** Readonly when the visit is SIGNED. The signed copy lives in
   *  signedSoap; the client passes that value as initialText. */
  readonly?: boolean;
  /** Batch H — ISO 8601 UTC moment the doctor signed the note, or
   *  null while still drafting. The Sign & Send CTA is hidden when
   *  this is set so a doctor can't re-sign a locked note. The
   *  visual replacement (a calm "Signed at … by …" card) lives in
   *  visit-ready-view above this editor. Optional so the legacy
   *  callsite signature stays backwards-compatible. */
  signedAt?: string | null;
  theme?: SoapEditorTheme;
}

export function SoapEditor({
  visitId,
  doctorEmail,
  emailEnabled,
  initialText,
  readonly = false,
  signedAt = null,
  theme = 'legacy',
}: SoapEditorProps) {
  const [text, setText] = useState(initialText);
  const [editing, setEditing] = useState(false);
  const [saving, startSaving] = useTransition();
  const isClinician = theme === 'clinician';
  // Batch H — the signed-state visual gate. Used directly (over the
  // existing `readonly` flag) per the brief: signedAt is the canonical
  // signal that the note is locked, regardless of how the lifecycle
  // status enum was set. A signed visit MUST NOT show the Sign & Send
  // CTA — that's the clinical-safety bug Batch H exists to fix.
  const isSigned = signedAt !== null;

  const onSave = () => {
    startSaving(async () => {
      const res = await saveSoapDraftAction(visitId, text);
      if (!res.ok) {
        toast.error('Could not save', { description: res.error });
        return;
      }
      toast.success('Saved');
      setEditing(false);
    });
  };

  return (
    <div className="space-y-4">
      {editing && !readonly ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className={cn(
            'min-h-[40vh] w-full resize-y rounded-xl p-4 leading-relaxed outline-none',
            isClinician
              ? // Clinician: cream-card with sage focus ring + sage tint
                // glow. Mono is intentionally retained because the
                // editor exposes raw markdown — readability for editing
                // wants the structural grid mono provides, even on
                // cream. Body view (read mode) renders via .qm-cl-prose
                // serif below.
                'border border-clinician-line bg-clinician-cream-card font-mono text-[13px] text-clinician-ink focus:border-clinician-sage focus:ring-2 focus:ring-clinician-sage/30'
              : 'border border-border-default bg-bg-surface-1/60 font-mono text-[13px] text-text-primary focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30'
          )}
          aria-label="Edit SOAP note"
        />
      ) : (
        <button
          type="button"
          onClick={() => !readonly && setEditing(true)}
          disabled={readonly}
          className={cn(
            'group block w-full text-left',
            isClinician
              ? 'qm-cl-card p-6'
              : 'rounded-xl border border-border-default bg-bg-surface-1/60 p-6',
            readonly
              ? 'cursor-default'
              : isClinician
                ? 'cursor-text hover:border-clinician-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream'
                : 'cursor-text hover:border-border-emphasis focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base'
          )}
        >
          <SoapMarkdown text={text} theme={theme} />
          {!readonly && (
            <span
              className={cn(
                'mt-4 inline-flex items-center gap-1.5 text-[11px] opacity-0 transition-opacity group-hover:opacity-100',
                isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
              )}
            >
              <PencilLine className="h-3 w-3" aria-hidden />
              Click to edit
            </span>
          )}
        </button>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        {editing && !readonly && (
          <>
            <SpecularButton
              theme={theme}
              variant="secondary"
              size="md"
              sweep={false}
              onClick={() => {
                setEditing(false);
                setText(initialText);
              }}
              disabled={saving}
            >
              Cancel
            </SpecularButton>
            <SpecularButton
              theme={theme}
              variant="primary"
              size="md"
              onClick={onSave}
              disabled={saving}
            >
              {saving ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                  Saving…
                </>
              ) : (
                <>
                  <Check className="h-3.5 w-3.5" aria-hidden />
                  Save edits
                </>
              )}
            </SpecularButton>
          </>
        )}

        {/* Batch H — the Sign & Send CTA renders ONLY when the visit
            is unsigned (signedAt == null). Once a note has a sign
            timestamp it's locked: re-signing is not a clinically
            valid action, and previously the doctor could click this
            button on a SIGNED visit if the lifecycle status enum
            momentarily disagreed with signedAt. The calm
            "Signed at … by …" replacement card lives in
            visit-ready-view above this editor. */}
        {!editing && !readonly && !isSigned && (
          <SignAndSendModal
            visitId={visitId}
            doctorEmail={doctorEmail}
            emailEnabled={emailEnabled}
            signOnSubmit
            triggerLabel="Sign & Send"
            triggerIcon={<Lock className="h-3.5 w-3.5" aria-hidden />}
            theme={theme}
          />
        )}

        {/* Batch H — Export again stays available on signed visits
            so the doctor can still re-send a copy of the locked note
            via clipboard / DOCX / PDF / email. We key off isSigned
            here too so the gate composes from a single signal. */}
        {!editing && (readonly || isSigned) && (
          <SignAndSendModal
            visitId={visitId}
            doctorEmail={doctorEmail}
            emailEnabled={emailEnabled}
            signOnSubmit={false}
            triggerLabel="Export again"
            triggerIcon={<Send className="h-3.5 w-3.5" aria-hidden />}
            triggerVariant="secondary"
            theme={theme}
          />
        )}
      </div>
    </div>
  );
}

/** Very lightweight markdown renderer — bold, headings, bullets, line
 *  breaks. We deliberately avoid a full library: clinicians rarely
 *  need tables/images here and a 30-line shim preserves bundle size.
 *
 *  Clinician variant wraps the rendered output in `.qm-cl-prose` so
 *  paragraphs / bullets / strong / em all resolve against the Source
 *  Serif 4 16px/1.7lh body the mockup commits to. The same shim
 *  produces both branches — only the wrapper class + per-block colour
 *  tokens change. */
function SoapMarkdown({
  text,
  theme,
}: {
  text: string;
  theme: SoapEditorTheme;
}) {
  const isClinician = theme === 'clinician';
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  const flushList = (k: number) => {
    if (listBuffer.length === 0) return;
    out.push(
      <ul
        key={`ul-${k}`}
        className={cn(
          'my-2 list-disc space-y-1 pl-5 text-[14px]',
          isClinician ? 'text-clinician-ink-2' : 'text-text-secondary'
        )}
      >
        {listBuffer.map((l, i) => (
          <li key={i}>{renderInline(l, theme)}</li>
        ))}
      </ul>
    );
    listBuffer = [];
  };
  lines.forEach((raw, k) => {
    const l = raw.trimEnd();
    if (l.startsWith('## ')) {
      flushList(k);
      out.push(
        <h2
          key={k}
          className={cn(
            'mt-6 text-[15px] font-semibold uppercase tracking-wider',
            isClinician
              ? 'qm-cl-eyebrow text-clinician-sage-deep'
              : 'text-violet-300'
          )}
        >
          {l.slice(3)}
        </h2>
      );
      return;
    }
    if (l.startsWith('# ')) {
      flushList(k);
      out.push(
        <h1
          key={k}
          className={cn(
            'mt-6 text-[18px] font-semibold',
            isClinician
              ? 'qm-cl-serif text-clinician-ink'
              : 'text-text-primary'
          )}
        >
          {l.slice(2)}
        </h1>
      );
      return;
    }
    if (/^\s*[-*]\s+/.test(l)) {
      listBuffer.push(l.replace(/^\s*[-*]\s+/, ''));
      return;
    }
    flushList(k);
    if (l.trim() === '') {
      out.push(<div key={k} className="h-2" />);
      return;
    }
    out.push(
      <p
        key={k}
        className={cn(
          'leading-relaxed',
          isClinician
            ? 'qm-cl-serif text-[16px] text-clinician-ink-2'
            : 'text-[14px] text-text-secondary'
        )}
        style={isClinician ? { lineHeight: 1.7 } : undefined}
      >
        {renderInline(l, theme)}
      </p>
    );
  });
  flushList(lines.length);
  return (
    <div
      className={cn(
        'space-y-0.5',
        isClinician && 'qm-cl-prose'
      )}
      style={isClinician ? { maxWidth: 720 } : undefined}
    >
      {out}
    </div>
  );
}

/** Inline markdown: **bold** only. Everything else stays verbatim. */
function renderInline(s: string, theme: SoapEditorTheme): React.ReactNode {
  const isClinician = theme === 'clinician';
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong
        key={i}
        className={cn(
          'font-semibold',
          isClinician ? 'text-clinician-ink' : 'text-text-primary'
        )}
      >
        {p.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}
