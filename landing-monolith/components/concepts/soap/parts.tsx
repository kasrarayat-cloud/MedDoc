'use client';

// Shared toolkit for the SOAP-review concept mockups. All three concepts compose the SAME
// pieces (note, suggestion cards, Rx cards, coding panel, the ONE Sign button) arranged
// differently. useReview() is the shared review state + the inline sign-blocker computation
// (critical Rx override, E/M confirm) so a blocker can never hide on another tab. Static
// mockup — no real pipeline/server actions.
import { useState, useId } from 'react';
import { SOAP, LANE, RX, EM, VISIT, SAMPLE_BANNER } from './data';
import type { Section, LaneItem, RxWarn } from './data';

export function SampleChip() {
  return <span className="sc-sample" title={SAMPLE_BANNER}>● {SAMPLE_BANNER}</span>;
}

export function PatientMeta() {
  return (
    <div className="sc-pt">
      <span className="sc-pt-name">{VISIT.patient}</span>
      <span className="sc-pt-meta">
        {VISIT.meta} · MRN {VISIT.mrn} · {VISIT.when}
      </span>
      <span className="sc-pt-status">{VISIT.status}</span>
    </div>
  );
}

function EditableSection({ s }: { s: Section }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(s.text);
  return (
    <div className="sc-sec">
      <div className="sc-sec-head">
        <span className={`sc-tag sc-tag-${s.tag}`}>{s.tag}</span>
        <span className="sc-sec-label">{s.label}</span>
        {!editing && (
          <button className="sc-sec-edit" type="button" onClick={() => setEditing(true)} aria-label={`Edit ${s.label}`}>
            Edit
          </button>
        )}
      </div>
      {editing ? (
        <textarea
          className="sc-sec-area"
          value={text}
          autoFocus
          onChange={(e) => setText(e.target.value)}
          onBlur={() => setEditing(false)}
          aria-label={`${s.label} text`}
        />
      ) : (
        <p className="sc-sec-text">{text}</p>
      )}
    </div>
  );
}

export function NoteDoc() {
  return (
    <div className="sc-note">
      {SOAP.map((s) => (
        <EditableSection key={s.tag} s={s} />
      ))}
    </div>
  );
}

export function LaneCard({
  item,
  state,
  onAdopt,
  onDismiss,
}: {
  item: LaneItem;
  state?: 'adopted' | 'dismissed';
  onAdopt: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const held = item.kind === 'held';
  return (
    <div className={`sc-card sc-lane ${state ? 'is-resolved' : ''}`}>
      <div className="sc-card-head">
        <span className={`sc-lane-tag ${held ? 'sc-lane-held' : 'sc-lane-grounded'}`}>{held ? 'Suggested' : 'Grounded'}</span>
        <span className="sc-lane-section">→ {item.section}</span>
      </div>
      <p className="sc-card-text">{item.text}</p>
      <p className={`sc-lane-note ${held ? 'is-held' : ''}`}>{item.note}</p>
      {state === 'adopted' ? (
        <p className="sc-resolved">✓ Added to {item.section}</p>
      ) : state === 'dismissed' ? (
        <p className="sc-resolved sc-dim">Dismissed</p>
      ) : (
        <div className="sc-actions">
          <button className="sc-btn sc-btn-pry-ghost" type="button" onClick={() => onAdopt(item.id)}>
            Adopt
          </button>
          <button className="sc-btn sc-btn-quiet" type="button" onClick={() => onDismiss(item.id)}>
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

export function RxCard({ warn, overridden, onOverride }: { warn: RxWarn; overridden: boolean; onOverride: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState('');
  const crit = warn.severity === 'critical';
  return (
    <div className={`sc-card sc-rx sc-rx-${warn.severity} ${overridden ? 'is-resolved' : ''}`}>
      <div className="sc-card-head">
        <span className={`sc-sev sc-sev-${warn.severity}`}>{crit ? 'Critical' : 'Info'}</span>
        <span className="sc-rx-id">{warn.id}</span>
      </div>
      <p className="sc-rx-pair">{warn.pair}</p>
      <p className="sc-card-text">{warn.text}</p>
      {crit &&
        (overridden ? (
          <p className="sc-resolved">✓ Overridden — safe to sign</p>
        ) : open ? (
          <div className="sc-override">
            <label className="sc-override-label" htmlFor={`why-${warn.id}`}>
              Why sign past this? (required)
            </label>
            <textarea
              id={`why-${warn.id}`}
              className="sc-override-area"
              value={why}
              onChange={(e) => setWhy(e.target.value)}
              placeholder="e.g. simvastatin already reduced to 20 mg"
            />
            <div className="sc-actions">
              <button className="sc-btn sc-btn-quiet" type="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button className="sc-btn sc-btn-danger" type="button" disabled={why.trim().length < 10} onClick={() => onOverride(warn.id)}>
                Override &amp; continue
              </button>
            </div>
          </div>
        ) : (
          <button className="sc-btn sc-btn-danger-ghost" type="button" onClick={() => setOpen(true)}>
            Override to sign
          </button>
        ))}
    </div>
  );
}

export function EmPanel({
  applied,
  onApply,
  confirmed,
  onConfirm,
}: {
  applied: boolean;
  onApply: () => void;
  confirmed: boolean;
  onConfirm: (v: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sc-em">
      <button className="sc-em-head" type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="sc-em-code">Coding · {applied ? EM.suggested : EM.current}</span>
        <span className="sc-em-toggle">{open ? 'Hide' : 'Review'}</span>
      </button>
      {open && (
        <div className="sc-em-body">
          <p className="sc-em-basis">{EM.basis}</p>
          {applied ? (
            <label className="sc-check">
              <input type="checkbox" checked={confirmed} onChange={(e) => onConfirm(e.target.checked)} /> Confirm the {EM.current} → {EM.suggested} level change.
            </label>
          ) : (
            <button className="sc-btn sc-btn-quiet" type="button" onClick={onApply}>
              Documentation supports {EM.suggested} ({EM.delta}) — apply
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function SignButton({
  canSign,
  blockers,
  signed,
  onSign,
  big,
}: {
  canSign: boolean;
  blockers: string[];
  signed: boolean;
  onSign: () => void;
  big?: boolean;
}) {
  const msgId = useId(); // unique per instance — SignButton renders twice (header + mobile bar)
  if (signed) return <div className="sc-signed">✓ Note signed · Sample patient · today 11:24</div>;
  return (
    <div className="sc-signwrap">
      <button
        className={`sc-btn sc-btn-sign ${big ? 'sc-btn-sign-big' : ''}`}
        type="button"
        disabled={!canSign}
        onClick={onSign}
        aria-describedby={!canSign ? msgId : undefined}
      >
        Sign note
      </button>
      {!canSign && (
        <p className="sc-block" id={msgId}>
          {blockers.length} to resolve: {blockers[0]}
        </p>
      )}
    </div>
  );
}

export function useReview() {
  const [adopted, setAdopted] = useState<Set<string>>(new Set());
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [overrides, setOverrides] = useState<Set<string>>(new Set());
  const [bumpApplied, setBumpApplied] = useState(false);
  const [emConfirmed, setEmConfirmed] = useState(false);
  const [signed, setSigned] = useState(false);

  const adopt = (id: string) => {
    setAdopted((s) => new Set(s).add(id));
    setDismissed((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });
  };
  const dismiss = (id: string) => {
    setDismissed((s) => new Set(s).add(id));
    setAdopted((s) => {
      const n = new Set(s);
      n.delete(id);
      return n;
    });
  };
  const override = (id: string) => setOverrides((s) => new Set(s).add(id));
  const laneState = (id: string): 'adopted' | 'dismissed' | undefined =>
    adopted.has(id) ? 'adopted' : dismissed.has(id) ? 'dismissed' : undefined;

  const pendingLane = LANE.filter((l) => !adopted.has(l.id) && !dismissed.has(l.id));
  const blockingRx = RX.filter((r) => r.blocking && !overrides.has(r.id));
  const emNeeded = bumpApplied && !emConfirmed;
  const blockers = [
    ...blockingRx.map((r) => `critical interaction ${r.id} — override to sign`),
    ...(emNeeded ? ['coding changed 99213 → 99214 — confirm'] : []),
  ];
  const canSign = blockers.length === 0;

  return {
    adopted, dismissed, overrides, bumpApplied, setBumpApplied, emConfirmed, setEmConfirmed, signed, setSigned,
    adopt, dismiss, override, laneState, pendingLane, blockingRx, blockers, canSign,
  };
}
