'use client';

import { useState, useTransition } from 'react';
import { Lock, Loader2, Check, PencilLine, Send } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { SpecularButton } from '@/components/specular-button';
import { saveSoapDraftAction } from '@/actions/soap';
import { SignAndSendModal } from './sign-and-send-modal';

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
  needsReview: boolean;
  reviewReason: string | null;
  overallQuality?: 'high' | 'medium' | 'low' | null;
}

export function SoapEditor({
  visitId,
  doctorEmail,
  emailEnabled,
  initialText,
  readonly = false,
  needsReview,
  reviewReason,
  overallQuality,
}: SoapEditorProps) {
  const [text, setText] = useState(initialText);
  const [editing, setEditing] = useState(false);
  const [saving, startSaving] = useTransition();

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
      {needsReview && !readonly && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/5 px-4 py-3 text-[13px] text-text-secondary"
        >
          <span className="mt-0.5 inline-block h-1.5 w-1.5 flex-none rounded-full bg-warning" />
          <div>
            <div className="font-medium text-text-primary">Needs review</div>
            <div className="mt-1 text-text-tertiary">
              {reviewReason ??
                'Our auditor flagged issues worth a quick review before signing.'}
            </div>
          </div>
        </div>
      )}

      {overallQuality && !readonly && (
        <QualityStrip quality={overallQuality} />
      )}

      {editing && !readonly ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-h-[40vh] w-full resize-y rounded-xl border border-border-default bg-bg-surface-1/60 p-4 font-mono text-[13px] leading-relaxed text-text-primary outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/30"
          aria-label="Edit SOAP note"
        />
      ) : (
        <button
          type="button"
          onClick={() => !readonly && setEditing(true)}
          disabled={readonly}
          className={cn(
            'group block w-full rounded-xl border border-border-default bg-bg-surface-1/60 p-6 text-left',
            readonly
              ? 'cursor-default'
              : 'cursor-text hover:border-border-emphasis focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base'
          )}
        >
          <SoapMarkdown text={text} />
          {!readonly && (
            <span className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-text-muted opacity-0 transition-opacity group-hover:opacity-100">
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

        {!editing && !readonly && (
          <SignAndSendModal
            visitId={visitId}
            doctorEmail={doctorEmail}
            emailEnabled={emailEnabled}
            signOnSubmit
            triggerLabel="Sign & Send"
            triggerIcon={<Lock className="h-3.5 w-3.5" aria-hidden />}
          />
        )}

        {!editing && readonly && (
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

        {readonly && (
          <div className="inline-flex items-center gap-2 rounded-full border border-success/40 bg-success/10 px-3 py-1 text-[12px] font-medium text-success">
            <Lock className="h-3 w-3" aria-hidden />
            Signed and locked
          </div>
        )}
      </div>
    </div>
  );
}

function QualityStrip({ quality }: { quality: 'high' | 'medium' | 'low' }) {
  const meta =
    quality === 'high'
      ? {
          label: 'High confidence',
          color: 'text-success',
          dot: 'bg-success',
        }
      : quality === 'medium'
        ? {
            label: 'Medium confidence — skim before signing',
            color: 'text-warning',
            dot: 'bg-warning',
          }
        : {
            label: 'Low confidence — read carefully before signing',
            color: 'text-danger',
            dot: 'bg-danger',
          };
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full border border-border-subtle bg-bg-surface-2/60 px-3 py-1',
        'text-[11px] font-medium',
        meta.color
      )}
    >
      <span className={cn('inline-block h-1.5 w-1.5 rounded-full', meta.dot)} />
      {meta.label}
    </div>
  );
}

/** Very lightweight markdown renderer — bold, headings, bullets, line
 *  breaks. We deliberately avoid a full library: clinicians rarely
 *  need tables/images here and a 30-line shim preserves bundle size. */
function SoapMarkdown({ text }: { text: string }) {
  const lines = text.split('\n');
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  const flushList = (k: number) => {
    if (listBuffer.length === 0) return;
    out.push(
      <ul
        key={`ul-${k}`}
        className="my-2 list-disc space-y-1 pl-5 text-[14px] text-text-secondary"
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
          className="mt-6 text-[15px] font-semibold uppercase tracking-wider text-violet-300"
        >
          {l.slice(3)}
        </h2>
      );
      return;
    }
    if (l.startsWith('# ')) {
      flushList(k);
      out.push(
        <h1 key={k} className="mt-6 text-[18px] font-semibold text-text-primary">
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
      <p key={k} className="text-[14px] leading-relaxed text-text-secondary">
        {renderInline(l)}
      </p>
    );
  });
  flushList(lines.length);
  return <div className="space-y-0.5">{out}</div>;
}

/** Inline markdown: **bold** only. Everything else stays verbatim. */
function renderInline(s: string): React.ReactNode {
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong key={i} className="font-semibold text-text-primary">
        {p.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}
