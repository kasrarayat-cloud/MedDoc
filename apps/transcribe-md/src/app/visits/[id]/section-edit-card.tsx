'use client';

// ============================================================================
// Tap a section, change its words.
// ----------------------------------------------------------------------------
// Phase 2 made the visit page the doctor's own document — and took inline
// editing with it, because the pages are canvases and the note editor was no
// longer mounted. "Fix a typo before signing" had no path at all.
//
// This puts one back, at the only place the document view can honestly offer
// it: under the page the section appears on. Tapping opens that section's text
// — verbatim, not a re-typeset copy — and saving splices it back into the note
// and re-fills the document, through the same save the note editor has always
// used.
//
// It edits ONE section. The rest of the note is not in this textarea and cannot
// be touched by it, which is the whole reason the splice refuses ambiguous
// headings rather than guessing.
// ============================================================================

import { useEffect, useRef, useState } from 'react';

export interface SectionEditCardProps {
  label: string;
  /** The section's current body, verbatim. Null when the note has no such
   *  section any more — the control is not offered at all in that case. */
  body: string | null;
  disabled: boolean;
  /** The note version this card is showing. Sent with the save so a change
   *  that landed while the editor was open is refused, not overwritten. */
  soapVersion: number;
  /** Saves and returns the outcome. The caller re-fills the document. */
  onSave: (
    label: string,
    body: string,
    expectedVersion: number,
  ) => Promise<{ ok: boolean; error?: string }>;
}

/** An id may not contain whitespace. "Chief Complaint" produced
 *  id="edit-Chief Complaint", which is invalid HTML and unaddressable by
 *  `#id` — the selector parses as a descendant combinator and matches
 *  nothing. The visible label keeps its real text. */
function domId(label: string): string {
  return `edit-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}`;
}

export function SectionEditCard(props: SectionEditCardProps) {
  const { label, body, disabled } = props;
  const fieldId = domId(label);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(body ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Keep the draft in step with the note when we are NOT editing — an adopt
  // elsewhere on the page changes this section under us, and reopening the
  // editor on stale text would let a doctor overwrite it without seeing it.
  //
  // Derived-state-DURING-RENDER, the same pattern review-document-view uses for
  // its claims and E/M state: an effect that setStates synchronously cascades
  // an extra render, and this one runs on every adopt.
  const [prevBody, setPrevBody] = useState(body);
  if (prevBody !== body) {
    setPrevBody(body);
    if (!editing) setDraft(body ?? '');
  }

  useEffect(() => {
    if (editing && taRef.current) {
      taRef.current.focus();
      const len = taRef.current.value.length;
      taRef.current.setSelectionRange(len, len);
    }
  }, [editing]);

  // The note has no section we can address by this heading — it is missing,
  // duplicated, or the display label differs from the raw heading (classic
  // SOAP notes are shown as "Subjective" whatever their heading actually
  // says). Offering nothing AND saying nothing is the silent case; say it.
  if (body === null) {
    return (
      <p className="qm-vdoc-edit-na" data-testid={`section-uneditable-${label}`}>
        {label} can&rsquo;t be edited here — open the full note to change it.
      </p>
    );
  }

  if (!editing) {
    return (
      <button
        type="button"
        className="qm-vdoc-edit-open qm-tap-44"
        onClick={() => {
          setError(null);
          setEditing(true);
        }}
        disabled={disabled}
        data-testid={`section-edit-${label}`}
        aria-label={`Edit ${label}`}
      >
        Edit {label}
      </button>
    );
  }

  return (
    <div className="qm-vdoc-edit" data-testid={`section-editor-${label}`}>
      <label className="qm-vdoc-edit-label" htmlFor={fieldId}>
        {label}
      </label>
      <textarea
        id={fieldId}
        data-testid={`section-textarea-${label}`}
        ref={taRef}
        className="qm-vdoc-edit-ta"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        rows={Math.min(18, Math.max(4, draft.split('\n').length + 1))}
        disabled={saving}
      />
      {error && (
        <p className="qm-vdoc-edit-err" role="alert" data-testid="section-edit-error">
          {error}
        </p>
      )}
      <div className="qm-vdoc-edit-actions">
        <button
          type="button"
          className="qm-ux-primary qm-tap-44"
          disabled={saving}
          data-testid={`section-save-${label}`}
          onClick={async () => {
            setSaving(true);
            setError(null);
            const r = await props.onSave(label, draft, props.soapVersion);
            setSaving(false);
            if (r.ok) setEditing(false);
            // A failure keeps the editor OPEN with the doctor's text still in
            // it. Closing on error would discard what they wrote and show them
            // the old words as though nothing had happened.
            else setError(r.error ?? "We couldn't save that just now.");
          }}
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          className="qm-ux-quiet qm-tap-44"
          disabled={saving}
          onClick={() => {
            setDraft(body);
            setEditing(false);
            setError(null);
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
