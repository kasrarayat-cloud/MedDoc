'use client';

// C6 — LINE-BY-LINE APPROVE. The note is decomposed into atomic claims, each a checklist row with
// its transcript anchor and inline edit. The doctor reviews (or edits) each line; a held AI
// suggestion and the critical Rx interaction are rows too. Sign unlocks only when every line is
// reviewed AND the critical interaction is overridden — nothing can hide on another tab. (≠ C2's
// 3 macro-steps: here review is per-claim, not per-phase.)
import { useState } from 'react';
import { PatientMeta, SampleChip, RxCard, EmPanel, SignButton, useReview } from './parts';
import { CLAIMS, LANE, RX } from './data';
import type { Claim } from './data';

const SEC_LABEL: Record<string, string> = { S: 'Subjective', O: 'Objective', A: 'Assessment', P: 'Plan' };
const held = LANE.find((l) => l.kind === 'held')!;

function ClaimRow({ claim, approved, onApprove }: { claim: Claim; approved: boolean; onApprove: (id: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(claim.text);
  return (
    <li className={`c6-claim ${approved ? 'ok' : ''}`}>
      <button
        className="c6-check"
        type="button"
        role="checkbox"
        aria-checked={approved}
        onClick={() => onApprove(claim.id)}
        aria-label={approved ? `Reviewed: ${claim.text}` : `Mark reviewed: ${claim.text}`}
      >
        {approved ? '✓' : ''}
      </button>
      <div className="c6-claim-main">
        <div className="c6-claim-top">
          <span className={`sc-tag sc-tag-${claim.section}`}>{claim.section}</span>
          <span className="c6-claim-sec">{SEC_LABEL[claim.section]}</span>
          {!editing && (
            <button className="sc-sec-edit" type="button" onClick={() => setEditing(true)} aria-label={`Edit ${SEC_LABEL[claim.section]} line`}>
              Edit
            </button>
          )}
        </div>
        {editing ? (
          <textarea className="sc-sec-area" value={text} autoFocus onChange={(e) => setText(e.target.value)} onBlur={() => setEditing(false)} aria-label="Claim text" />
        ) : (
          <p className="c6-claim-text">{text}</p>
        )}
        {claim.anchor && <p className="c6-anchor">{claim.anchor}</p>}
      </div>
    </li>
  );
}

export function C6Claims() {
  const r = useReview();
  const [approved, setApproved] = useState<Set<string>>(new Set());
  const approve = (id: string) =>
    setApproved((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const heldResolved = r.laneState(held.id) !== undefined;
  const reviewed = approved.size + (heldResolved ? 1 : 0);
  const total = CLAIMS.length + 1; // every claim + the held suggestion must be reviewed
  const left = total - reviewed;
  const blockers = [
    ...(left > 0 ? [`${left} line${left === 1 ? '' : 's'} still to review`] : []),
    ...r.blockers,
  ];
  const canSign = blockers.length === 0;

  return (
    <div className="c6 sc-app">
      <header className="c6-top sc-top">
        <div className="sc-top-l"><PatientMeta /><SampleChip /></div>
      </header>

      <div className="c6-progress">
        <div className="c6-progress-bar"><span style={{ width: `${(reviewed / total) * 100}%` }} /></div>
        <span className="c6-progress-label">{reviewed} of {total} reviewed</span>
      </div>

      <main className="c6-pane sc-pane">
        <div className="sc-pane-head"><span className="sc-pane-title">Approve each line</span></div>
        <ol className="c6-claims">
          {CLAIMS.map((c) => (
            <ClaimRow key={c.id} claim={c} approved={approved.has(c.id)} onApprove={approve} />
          ))}

          {/* the held AI suggestion — must be accepted or rejected, not silently approved */}
          <li className={`c6-claim c6-proposed ${heldResolved ? 'ok' : ''}`}>
            <span className="c6-check c6-check-flag" aria-hidden>+</span>
            <div className="c6-claim-main">
              <div className="c6-claim-top">
                <span className="sc-lane-tag sc-lane-held">Suggested</span>
                <span className="c6-claim-sec">not stated in this visit</span>
              </div>
              <p className="c6-claim-text">{held.text}</p>
              <p className="sc-lane-note is-held">{held.note}</p>
              {heldResolved ? (
                <p className="sc-resolved">{r.laneState(held.id) === 'adopted' ? `✓ Added to ${held.section}` : 'Left out'}</p>
              ) : (
                <div className="sc-actions">
                  <button className="sc-btn sc-btn-pry-ghost" type="button" onClick={() => r.adopt(held.id)}>Add to note</button>
                  <button className="sc-btn sc-btn-quiet" type="button" onClick={() => r.dismiss(held.id)}>Leave out</button>
                </div>
              )}
            </div>
          </li>

          {/* the drug interactions — the critical one is a safety row that must be overridden */}
          <li className="c6-claim c6-safety">
            <span className="c6-check c6-check-warn" aria-hidden>!</span>
            <div className="c6-claim-main">
              {RX.map((w) => (
                <RxCard key={w.id} warn={w} overridden={r.overrides.has(w.id)} onOverride={r.override} />
              ))}
            </div>
          </li>
        </ol>

        <div className="c6-coding">
          <EmPanel applied={r.bumpApplied} onApply={() => r.setBumpApplied(true)} confirmed={r.emConfirmed} onConfirm={r.setEmConfirmed} />
        </div>
      </main>

      <div className="c6-signbar">
        <SignButton canSign={canSign} blockers={blockers} signed={r.signed} onSign={() => r.setSigned(true)} big />
      </div>
    </div>
  );
}
