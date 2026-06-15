'use client';

// v2-only presentational pieces. The note, lane cards, Rx cards, sign button and patient meta
// are REUSED verbatim from the v1 lab toolkit (../soap/parts) so the two screens are genuinely
// the same review surface re-arranged. The only new piece is the E/M card: a neutral,
// confirm-before-sign control (no revenue/dollar framing, per the shipped product direction).
import { EM } from '../soap/data';

export function EmCardV2({ confirmed, onConfirm }: { confirmed: boolean; onConfirm: (v: boolean) => void }) {
  return (
    <div className={`v2-em ${confirmed ? 'is-ok' : ''}`}>
      <div className="v2-em-row">
        <span className="v2-em-codes">
          <span className="v2-em-from">{EM.current}</span>
          <span className="v2-em-arrow" aria-hidden>
            →
          </span>
          <span className="v2-em-to">{EM.suggested}</span>
        </span>
        <span className={`v2-em-state ${confirmed ? 'ok' : ''}`}>{confirmed ? 'Confirmed' : 'Confirm to sign'}</span>
      </div>
      <p className="v2-em-basis">{EM.basis}</p>
      {confirmed ? (
        <p className="v2-em-done">✓ Level change confirmed — safe to sign</p>
      ) : (
        <label className="v2-check">
          <input type="checkbox" checked={confirmed} onChange={(e) => onConfirm(e.target.checked)} />
          <span>
            I confirm the documentation supports <strong>{EM.suggested}</strong> (changed from {EM.current}).
          </span>
        </label>
      )}
    </div>
  );
}
