'use client';

// ============================================================================
// Talk to the note.
// ----------------------------------------------------------------------------
// A conversational surface beside the document. The doctor asks; the server
// dispatches into the same audited actions the buttons call; the document
// re-fills.
//
// EVERY ACTION IS NAMED ON SCREEN. The model is told to say what it did, and
// this renders the server's own list of outcomes underneath the reply — so what
// the doctor is told matches what actually ran, even if the two ever disagree.
// A chat that says "done" while something failed would be worse than no chat.
//
// The transcript lives HERE, in component state, for the life of the page. It
// is not persisted, and nothing in it survives a reload.
// ============================================================================

import { useCallback, useRef, useState } from 'react';

import {
  chatEditVisitAction,
  type ChatActionOutcome,
  type ChatTurn,
} from '@/actions/chat-edit-visit';

/** Doctor-facing labels for what the server did. `detail` is PHI-free by
 *  construction — a section name, an index, a column heading, a scroll target.
 *  The VALUES live on `a.changed`, which is why they are read from there and
 *  not spliced into detail upstream. */
function describe(a: ChatActionOutcome): string {
  const moved = a.changed ? ` — ${a.changed.from} → ${a.changed.to}` : '';
  switch (a.kind) {
    case 'adopt_suggestion':
    case 'adopt_suggestions':
      return a.ok ? `Adopted a suggestion in ${a.detail}` : `Could not adopt: ${a.error}`;
    case 'edit_section':
      return a.ok ? `Changed ${a.detail}` : `Could not change ${a.detail}: ${a.error}`;
    // The structural echo of the edit, drawn by the client rather than trusted
    // from the model's prose: the doctor sees the cell and both values whether
    // or not the reply remembered to mention them.
    case 'edit_table_cell':
      return a.ok
        ? `Changed ${a.detail}${moved}`
        : `Could not change ${a.detail}: ${a.error}`;
    case 'edit_header':
      return a.ok ? `Changed ${a.detail}${moved}` : `Could not change ${a.detail}: ${a.error}`;
    case 'scroll_to':
      return `Took you to ${a.detail.replace(/_/g, ' ')}`;
    case 'refuse':
      return a.detail;
    // The reply IS the sentence — repeating it under the bubble would say the
    // same thing twice.
    case 'cannot':
    case 'answer':
      return '';
    default:
      return '';
  }
}

export interface ChatEditorPanelProps {
  visitId: string;
  disabled: boolean;
  /** Called when the note changed, so the page re-fills the document through
   *  the same path adopting and editing already use. */
  onNoteChanged: (r: { soapFinal: string; soapVersion?: number }) => void;
  /** The header changed but the note did not — redraw the document anyway. */
  onHeaderChanged?: () => void;
  /** Where the chat asked to take the doctor. */
  onScrollTo: (target: string) => void;
}

interface Entry extends ChatTurn {
  actions?: ChatActionOutcome[];
}

export function ChatEditorPanel(props: ChatEditorPanelProps) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft('');
    setError(null);
    setBusy(true);
    const asked: Entry = { role: 'doctor', text };
    setEntries((prev) => [...prev, asked]);

    // The history the server sees is the transcript as rendered — the same
    // turns the doctor can scroll back to. That matters: bulk adoption is
    // gated on the suggestions having been READ OUT in a previous reply.
    const history: ChatTurn[] = [...entries, asked].map((e) => ({
      role: e.role,
      text: e.text,
    }));

    try {
      const r = await chatEditVisitAction(props.visitId, text, history);
      if (!r.ok) {
        setError(r.error ?? 'Something went wrong.');
      } else {
        setEntries((prev) => [
          ...prev,
          { role: 'assistant', text: r.reply, actions: r.actions },
        ]);
        if (r.soapFinal) {
          props.onNoteChanged({ soapFinal: r.soapFinal, soapVersion: r.soapVersion });
        } else if (r.headerChanged) {
          // A header edit changes the DRAWN page without touching the note, so
          // there is no soapFinal to hand back and the document would sit there
          // showing the old name — the change landing everywhere except the one
          // place the doctor is looking.
          props.onHeaderChanged?.();
        }
        if (r.scrollTo) props.onScrollTo(r.scrollTo);
      }
    } catch {
      setError("I couldn't reach the assistant. Nothing was changed.");
    } finally {
      setBusy(false);
      requestAnimationFrame(() => {
        logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
      });
    }
  }, [draft, busy, entries, props]);

  return (
    <section className="qm-chat" data-testid="chat-editor">
      <header className="qm-chat-head">
        <span className="qm-chat-title">Ask about this note</span>
        <span className="qm-chat-sub">This visit only. It can&rsquo;t sign for you.</span>
      </header>

      <div className="qm-chat-log" ref={logRef} data-testid="chat-log">
        {entries.length === 0 && (
          <p className="qm-chat-empty">
            Try &ldquo;what still needs my attention?&rdquo; or &ldquo;change the technique
            line to say bilateral&rdquo;.
          </p>
        )}
        {entries.map((e, i) => (
          <div
            key={i}
            className={e.role === 'doctor' ? 'qm-chat-turn qm-chat-me' : 'qm-chat-turn'}
            data-testid={e.role === 'doctor' ? 'chat-turn-doctor' : 'chat-turn-assistant'}
          >
            <p className="qm-chat-text">{e.text}</p>
            {/* What the SERVER did — rendered from its outcomes, not from the
                model's account of itself, and rendered ALWAYS. Hiding this
                block when the list was empty is what let a reply claiming
                "I've adopted the allergy suggestion and tidied the plan" sit
                on screen with nothing to contradict it. */}
            {e.role === 'assistant' && (
              <ul className="qm-chat-actions" data-testid="chat-actions">
                {e.actions && e.actions.length > 0 ? (
                  e.actions.map((a, j) => (
                    <li key={j} className={a.ok ? undefined : 'qm-chat-action-fail'}>
                      {describe(a)}
                    </li>
                  ))
                ) : (
                  <li className="qm-chat-action-none">No changes were made.</li>
                )}
              </ul>
            )}
          </div>
        ))}
        {busy && (
          <p className="qm-chat-busy" role="status">
            Working…
          </p>
        )}
      </div>

      {error && (
        <p className="qm-chat-err" role="alert" data-testid="chat-error">
          {error}
        </p>
      )}

      <div className="qm-chat-compose">
        <textarea
          className="qm-chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Ask about this note…"
          rows={2}
          disabled={props.disabled || busy}
          aria-label="Ask about this note"
          data-testid="chat-input"
        />
        <button
          type="button"
          className="qm-ux-primary qm-tap-44"
          onClick={() => void send()}
          disabled={props.disabled || busy || !draft.trim()}
          data-testid="chat-send"
        >
          Send
        </button>
      </div>
    </section>
  );
}
