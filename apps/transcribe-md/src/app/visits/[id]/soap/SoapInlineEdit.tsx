'use client';

// ============================================================================
// SoapInlineEdit — sentence-level inline edit affordance for v6 SOAP body.
// ----------------------------------------------------------------------------
// Phase 5.2 — extracts the click-to-edit textarea flow that was previously
// monolithic in soap-editor.tsx. Click on a section body opens an inline
// textarea (sage outline). Esc / blur saves via the parent's onSave
// callback (which calls saveSoapDraftAction byte-identically). Save error
// → toast.error("Save failed — try again"); a successful save closes the
// textarea and the section re-renders the (markdown) body.
//
// The textarea operates on the WHOLE SOAP markdown blob — not a per-section
// slice — to preserve the existing soapFinal byte-identical contract.
// The SoapSection that hosts this affordance therefore passes in the
// FULL markdown text + a setter; the parent SoapEditor owns the source
// of truth and threads the same `text` to all four sections.
//
// `readonly` (signed visits) hides the affordance entirely; no sage
// outline on hover, no textarea, no pencil hint.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { Loader2, Check, PencilLine } from 'lucide-react';

import { cn } from '@/lib/cn';

export interface SoapInlineEditProps {
  /** Full SOAP markdown — this affordance edits the whole blob (the
   *  per-section split is read-only display; saves write the full text
   *  via saveSoapDraftAction byte-identically). */
  text: string;
  /** Disabled when the visit is signed. */
  readonly: boolean;
  /** Called with the new full-blob text. Parent invokes
   *  saveSoapDraftAction and reports back via `saving` / `error`. */
  onSave: (next: string) => Promise<{ ok: boolean; error?: string }>;
  /** Render-prop: how the *display* mode should look. The inline-edit
   *  shell wraps this in a hover/click target with a sage outline. */
  children: React.ReactNode;
}

export function SoapInlineEdit({ text, readonly, onSave, children }: SoapInlineEditProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(text);
  const [saving, setSaving] = useState(false);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Keep the draft in sync if the parent's text prop changes outside of
  // an active edit (e.g. another tab updates soapFinal then revalidates).
  useEffect(() => {
    if (!editing) setDraft(text);
  }, [text, editing]);

  useEffect(() => {
    if (editing && taRef.current) {
      taRef.current.focus();
      // Place caret at the end so the doctor can append immediately.
      const len = taRef.current.value.length;
      taRef.current.setSelectionRange(len, len);
    }
  }, [editing]);

  const persist = async (next: string) => {
    if (next === text) {
      // Nothing changed — close without writing.
      setEditing(false);
      return;
    }
    setSaving(true);
    const res = await onSave(next);
    setSaving(false);
    if (!res.ok) {
      // Caller already toasts via onSave; we keep the textarea open so
      // the doctor can retry without losing their edit.
      return;
    }
    setEditing(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      void persist(draft);
    }
  };

  const onBlur = () => {
    void persist(draft);
  };

  if (readonly) {
    // Signed-state: read-only, no affordance, no hover effect.
    return <div className="qm-lin-soap-section-body">{children}</div>;
  }

  if (editing) {
    return (
      <div className="qm-lin-soap-inline-edit">
        <textarea
          ref={taRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={onBlur}
          onKeyDown={onKeyDown}
          className="qm-lin-soap-inline-edit-ta"
          aria-label="Edit SOAP note"
          disabled={saving}
        />
        <div className="qm-lin-soap-inline-edit-foot">
          {saving ? (
            <span className="qm-lin-soap-inline-edit-status">
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
              Saving…
            </span>
          ) : (
            <span className="qm-lin-soap-inline-edit-status">
              <Check className="h-3 w-3" aria-hidden />
              Esc / blur saves
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      className={cn('qm-lin-soap-section-body', 'qm-lin-soap-section-body--editable')}
      aria-label="Edit SOAP note"
    >
      {children}
      <span className="qm-lin-soap-section-edit-hint" data-edit-affordance>
        <PencilLine className="h-3 w-3" aria-hidden />
        Click to edit
      </span>
    </button>
  );
}
