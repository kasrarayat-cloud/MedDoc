'use client';

// Verification — the differentiator, carried as the second SPLIT moment. LEFT (dark) the raw
// transcript with the anchored utterances highlighted ｜ RIGHT (light) the verified note (every
// line tagged "anchored") plus the review lane holding a plausible-but-unstated suggestion.
// This shows the real mechanism: anchored → into the note; ungrounded → held for the doctor.
import { SOAP } from '../motion/shared';
import { TRANSCRIPT, REVIEW_SUGGESTION } from './content';

export function VerificationSplit() {
  return (
    <section className="fx-verify" id="verification" aria-label="How QuillMD verifies the note">
      <div className="fx-verify-head">
        <p className="fx-kicker fx-kicker-on-dark font-mono">The difference</p>
        <h2 className="fx-section-h fx-on-dark">It only writes<br />what was said.</h2>
        <p className="fx-section-lede fx-lede-on-dark">
          Every line is anchored to the transcript. When something can’t be grounded in the visit, it
          goes to a review lane — not into your note.
        </p>
      </div>

      <div className="fx-verify-split fx-reveal">
        <div className="fx-verify-half fx-verify-raw">
          <p className="fx-kicker font-mono">The raw transcript</p>
          <div className="fx-vt">
            {TRANSCRIPT.map((u, i) => (
              <p key={`${u.who}-${i}`} className={`fx-vt-line fx-vt-${u.who}`}>
                <span className="fx-vt-who font-mono">{u.who === 'dr' ? 'Dr.' : 'Pt.'}</span>
                <span className={u.soap ? 'fx-vt-anchored' : undefined}>{u.text}</span>
              </p>
            ))}
          </div>
        </div>

        <div className="fx-verify-half fx-verify-note">
          <p className="fx-kicker fx-kicker-after font-mono">The verified note</p>
          <ol className="fx-note-list fx-vn font-mono">
            {SOAP.map((l, i) => (
              <li key={`${l.tag}-${i}`}>
                <span className="fx-note-tag">{l.tag}</span>
                <span className="fx-vn-text">{l.text}</span>
                <span className="fx-vn-anchor font-mono" aria-hidden>anchored</span>
              </li>
            ))}
          </ol>
          <div className="fx-review">
            <p className="fx-review-head font-mono">Review lane</p>
            <div className="fx-review-item">
              <span className="fx-review-q">{REVIEW_SUGGESTION.text}</span>
              <span className="fx-review-reason font-mono">{REVIEW_SUGGESTION.reason}</span>
              <span className="fx-review-actions font-mono" aria-hidden>Keep · Discard</span>
            </div>
          </div>
        </div>

        <div className="fx-seam fx-seam-v" aria-hidden />
      </div>
    </section>
  );
}
