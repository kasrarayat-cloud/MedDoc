'use client';

// ============================================================================
// The documentation level, and the doctor's right to disagree with it.
// ----------------------------------------------------------------------------
// The billing panel is gone from the review page. It held the AMA rubric, a
// "why this level" disclosure and a dropdown — a coding worksheet on a page
// whose job is to show what is being signed. But one control on it was not
// worksheet: the doctor's ability to say the scored level is wrong. That is a
// clinical judgement about their own note, and removing the panel removed the
// only place in the product they could make it.
//
// So it comes back here, in the gate stack, minimal and quiet:
//
//     Documentation level        99213
//     [ Adjust ]
//
// WHAT THIS IS NOT. There is no rubric, no "why this level", no next-level-up
// coaching, no figures, and no suggestion that a different code would be worth
// more. A level is a description of work already done. A surface that nudges
// toward a higher one is asking the doctor to document for the number rather
// than number the documentation, and that is not a thing this product does.
// The wording here is deliberately flat in both directions: up and down read
// exactly the same.
//
// WHAT IT DOES NOT WEAKEN. Setting a level is not attesting to one. The save
// arms the SAME pending-change record the model's own re-scores raise, so the
// existing confirm card appears underneath and the sign route still refuses
// without a matching acknowledgement. Choosing and confirming stay two acts.
//
// The reason is REQUIRED. "Who changed it to what" without "and why" is the
// half of the audit row nobody can reconstruct afterwards.
// ============================================================================

import { useState } from 'react';
import { Check, Pencil } from 'lucide-react';

/** AMA 2021 office E/M surface — mirrors the route's enum. Ordered as the
 *  code sets read, not by "value": two runs of five, new then established. */
export const EM_LEVEL_CODES = [
  '99202',
  '99203',
  '99204',
  '99205',
  '99211',
  '99212',
  '99213',
  '99214',
  '99215',
] as const;

export interface EmLevelCardProps {
  /** The level as displayed today — the doctor's own override if they set one,
   *  otherwise what the note scored at. Null when nothing has scored yet. */
  level: string | null;
  /** Signed, archived, or otherwise not editable. */
  disabled: boolean;
  /** Persists the level and returns the outcome. The caller re-arms the
   *  confirm card from the pending change the server reports. */
  onAdjust: (code: string, reason: string) => Promise<{ ok: boolean; error?: string }>;
}

export function EmLevelCard(props: EmLevelCardProps) {
  const { level, disabled } = props;
  const [editing, setEditing] = useState(false);
  const [code, setCode] = useState(level ?? '99213');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keep the picker in step with the level when it moves underneath us — a
  // re-score or a confirm elsewhere on the page can do that, and opening the
  // picker on a stale value would let a doctor "keep" a level that is no longer
  // the one shown.
  //
  // WHILE THE FORM IS OPEN, SAY SO RATHER THAN SWALLOW IT. Silently leaving the
  // old selection in place meant the doctor could be looking at "changing 99213
  // → 99214" while the level had already become 99215, and save a move away
  // from a level that was never current. Closing the form under them would
  // discard what they typed. So: keep their text, re-point the picker at the
  // new level, and tell them it moved.
  const [prevLevel, setPrevLevel] = useState(level);
  const [movedUnderneath, setMovedUnderneath] = useState<string | null>(null);
  if (prevLevel !== level) {
    setPrevLevel(level);
    setCode(level ?? '99213');
    if (editing) setMovedUnderneath(level);
  }

  if (!level) return null;

  const reasonOk = reason.trim().length >= 3;
  const changed = code !== level;

  return (
    <section className="qm-rdoc-gate qm-rdoc-gate-quiet" data-testid="review-doc-em-level">
      <div className="qm-rdoc-gate-head">
        <span>Documentation level</span>
      </div>
      <div className="qm-rdoc-gate-body">
        {!editing ? (
          <>
            <p className="qm-rdoc-gate-text">
              This visit is documented at{' '}
              <strong className="qm-rdoc-em-code" data-testid="em-level-current">
                {level}
              </strong>
              .
            </p>
            <button
              type="button"
              className="qm-rdoc-gate-btn qm-tap-44"
              onClick={() => {
                setError(null);
                setReason('');
                setCode(level);
                setMovedUnderneath(null);
                setEditing(true);
              }}
              disabled={disabled}
              data-testid="em-level-adjust"
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden />
              Adjust
            </button>
          </>
        ) : (
          <div className="qm-rdoc-emadj">
            <label className="qm-rdoc-emadj-label" htmlFor="em-level-select">
              Level
            </label>
            <select
              id="em-level-select"
              className="qm-rdoc-emadj-select qm-tap-44-input"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              disabled={saving}
              data-testid="em-level-select"
            >
              {EM_LEVEL_CODES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>

            <label className="qm-rdoc-emadj-label" htmlFor="em-level-reason">
              Why you are changing it
            </label>
            <textarea
              id="em-level-reason"
              className="qm-rdoc-emadj-ta"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              maxLength={240}
              disabled={saving}
              placeholder="Recorded with the change."
              data-testid="em-level-reason"
            />

            {movedUnderneath && movedUnderneath === level && (
              <p className="qm-rdoc-emadj-note" role="status" data-testid="em-level-moved">
                The level changed to {level} while this was open. Pick again if you still
                want a different one.
              </p>
            )}

            {error && (
              <p className="qm-rdoc-emadj-err" role="alert" data-testid="em-level-error">
                {error}
              </p>
            )}

            <div className="qm-rdoc-emadj-actions">
              <button
                type="button"
                className="qm-rdoc-gate-btn qm-tap-44"
                // Not a validation message after the fact: the control is
                // simply not armed until the change is real and the reason is
                // there, so there is nothing to be told off about.
                disabled={saving || !reasonOk || !changed}
                data-testid="em-level-save"
                onClick={async () => {
                  setSaving(true);
                  setError(null);
                  const r = await props.onAdjust(code, reason.trim());
                  setSaving(false);
                  if (r.ok) {
                    setEditing(false);
                    setReason('');
                    setMovedUnderneath(null);
                  } else {
                    // Keep the form OPEN with their words in it. Closing on
                    // failure discards what they typed and shows the old level
                    // as though nothing had been attempted.
                    setError(r.error ?? "We couldn't save that just now.");
                  }
                }}
              >
                {saving ? (
                  'Saving…'
                ) : (
                  <>
                    <Check className="h-3.5 w-3.5" aria-hidden />
                    Save level
                  </>
                )}
              </button>
              <button
                type="button"
                className="qm-ux-quiet qm-tap-44"
                disabled={saving}
                data-testid="em-level-cancel"
                onClick={() => {
                  setEditing(false);
                  setCode(level);
                  setReason('');
                  setError(null);
                  setMovedUnderneath(null);
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
