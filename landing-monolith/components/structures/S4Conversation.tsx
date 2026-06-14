'use client';

// S4 — CONVERSATION-LED. Structural lock: Grammarly doc editor (primary text + margin
// annotations tied to it). The hero is a real doctor↔patient TRANSCRIPT (main column) with
// anchored utterances; the SOAP note assembles in the RIGHT margin, each line pinned to the
// exact quote it came from. The conversation is the hero; the note is the annotation.
import { SOAP, TRUST } from '../motion/shared';
import { TRANSCRIPT } from './content';

export function S4Conversation() {
  return (
    <section className="s4" aria-label="Concept 4 — conversation-led">
      <div className="s4-wrap">
        <header className="s4-head">
          <p className="s4-ey font-mono">From what was actually said</p>
          <h1 className="s4-title">
            The note writes itself —<br />
            <em>from the conversation.</em>
          </h1>
        </header>

        <div className="s4-doc">
          <div className="s4-transcript">
            {TRANSCRIPT.map((u, i) => (
              <p key={`${u.who}-${i}`} className={`s4-line s4-${u.who} ${u.soap ? 's4-anchored' : ''}`}>
                <span className="s4-who font-mono">{u.who === 'dr' ? 'Dr.' : 'Pt.'}</span>
                <span className="s4-utter">
                  {u.text}
                  {u.soap && <span className="s4-pin font-mono" aria-hidden>{u.soap}</span>}
                </span>
              </p>
            ))}
          </div>

          <aside className="s4-margin" aria-label="SOAP note assembling from the conversation">
            <p className="s4-margin-head font-mono">SOAP · assembling from the visit</p>
            {SOAP.map((l) => (
              <div key={l.tag} className="s4-card">
                <span className="s4-card-tag">{l.tag}</span>
                <span className="s4-card-text">{l.text}</span>
              </div>
            ))}
          </aside>
        </div>

        <div className="s4-foot">
          <div className="s4-cta">
            <a className="s4-btn s4-btn-primary" href="https://staging.quillmd.com/#start">
              Start free <span aria-hidden>→</span>
            </a>
            <a className="s4-btn s4-btn-ghost" href="https://staging.quillmd.com/#sandbox">See it work</a>
          </div>
          <ul className="s4-trust font-mono" aria-label="What QuillMD guarantees">
            {TRUST.map((t, i) => (
              <li key={t}>
                {i > 0 && <span aria-hidden>·</span>}
                {t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
