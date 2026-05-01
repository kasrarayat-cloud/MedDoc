'use client';

// ============================================================================
// SoapEditor — visit-detail SOAP note editor pane.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Renders the SOAP body in a hairline-
// bordered surface-1 card with Inter prose, JetBrains Mono for the
// raw-markdown editing textarea, and sage primary CTAs in the action
// row. The Sign & Send modal trigger lives at the bottom-right when
// the visit isn't yet signed; otherwise an "Export again" button
// occupies the same slot. The `theme` prop is preserved as a no-op.
// ============================================================================

import { useState, useTransition } from 'react';
import { Lock, Loader2, Check, PencilLine, Send } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
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
   *  this is set so a doctor can't re-sign a locked note. */
  signedAt?: string | null;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: SoapEditorTheme;
}

export function SoapEditor({
  visitId,
  doctorEmail,
  emailEnabled,
  initialText,
  readonly = false,
  signedAt = null,
}: SoapEditorProps) {
  const [text, setText] = useState(initialText);
  const [editing, setEditing] = useState(false);
  const [saving, startSaving] = useTransition();
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
          className="min-h-[40vh] w-full resize-y rounded-lg border border-linear-border bg-linear-surface-1 p-4 font-mono text-[13px] leading-relaxed text-linear-text outline-none focus:border-linear-sage focus:ring-2 focus:ring-linear-sage/30"
          aria-label="Edit SOAP note"
        />
      ) : (
        <button
          type="button"
          onClick={() => !readonly && setEditing(true)}
          disabled={readonly}
          className={cn(
            'group block w-full rounded-lg border border-linear-border bg-linear-surface-1 p-6 text-left transition-colors',
            readonly
              ? 'cursor-default'
              : 'cursor-text hover:border-linear-border-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg'
          )}
        >
          <SoapMarkdown text={text} />
          {!readonly && (
            <span className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-linear-text-3 opacity-0 transition-opacity group-hover:opacity-100">
              <PencilLine className="h-3 w-3" aria-hidden />
              Click to edit
            </span>
          )}
        </button>
      )}

      <div className="flex flex-wrap items-center justify-end gap-2">
        {editing && !readonly && (
          <>
            <button
              type="button"
              className="qm-lin-btn"
              onClick={() => {
                setEditing(false);
                setText(initialText);
              }}
              disabled={saving}
            >
              Cancel
            </button>
            <button
              type="button"
              className="qm-lin-btn-primary"
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
            </button>
          </>
        )}

        {/* Batch H — the Sign & Send CTA renders ONLY when the visit
            is unsigned (signedAt == null). Once a note has a sign
            timestamp it's locked: re-signing is not a clinically
            valid action, and previously the doctor could click this
            button on a SIGNED visit if the lifecycle status enum
            momentarily disagreed with signedAt. */}
        {!editing && !readonly && !isSigned && (
          <SignAndSendModal
            visitId={visitId}
            doctorEmail={doctorEmail}
            emailEnabled={emailEnabled}
            signOnSubmit
            triggerLabel="Sign & Send"
            triggerIcon={<Lock className="h-3.5 w-3.5" aria-hidden />}
          />
        )}

        {/* Batch H — Export again stays available on signed visits
            so the doctor can still re-send a copy of the locked note
            via clipboard / DOCX / PDF / email. */}
        {!editing && (readonly || isSigned) && (
          <SignAndSendModal
            visitId={visitId}
            doctorEmail={doctorEmail}
            emailEnabled={emailEnabled}
            signOnSubmit={false}
            triggerLabel="Export again"
            triggerIcon={<Send className="h-3.5 w-3.5" aria-hidden />}
            triggerVariant="secondary"
          />
        )}
      </div>
    </div>
  );
}

/** Very lightweight markdown renderer — bold, headings, bullets, line
 *  breaks. We deliberately avoid a full library: clinicians rarely
 *  need tables/images here and a 30-line shim preserves bundle size.
 *  Linear V1 — Inter for prose, JetBrains Mono for the H2 eyebrow. */
function SoapMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  const flushList = (k: number) => {
    if (listBuffer.length === 0) return;
    out.push(
      <ul
        key={`ul-${k}`}
        className="my-2 list-disc space-y-1 pl-5 text-[14px] text-linear-text-2"
      >
        {listBuffer.map((l, i) => (
          <li key={i}>{renderInline(l)}</li>
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
          className="mt-6 font-mono text-[10.5px] font-medium uppercase tracking-[0.07em] text-linear-sage-bright"
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
          className="mt-6 text-[18px] font-semibold tracking-tight text-linear-text"
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
        className="text-[14px] leading-relaxed text-linear-text-2"
      >
        {renderInline(l)}
      </p>
    );
  });
  flushList(lines.length);
  return (
    <div className="space-y-0.5" style={{ maxWidth: 720 }}>
      {out}
    </div>
  );
}

/** Inline markdown: **bold** only. Everything else stays verbatim. */
function renderInline(s: string): React.ReactNode {
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong key={i} className="font-semibold text-linear-text">
        {p.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}
