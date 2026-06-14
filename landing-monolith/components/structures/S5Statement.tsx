'use client';

// S5 — SINGLE STATEMENT. Structural lock: mymind (one centred statement in empty space).
// Above the fold there is ONLY the statement, dead-centre — no buttons, no badges, no card.
// The subhead, proof (SOAP), CTAs and trust all live BELOW the fold. Emptiness is the
// structure — the explicit opposite of cramming everything above the fold.
import { SOAP, SUBHEAD, TRUST } from '../motion/shared';

export function S5Statement() {
  return (
    <section className="s5" aria-label="Concept 5 — single statement">
      <div className="s5-stage">
        <h1 className="s5-title">
          The note<br />writes itself.
        </h1>
        <a className="s5-scroll font-mono" href="#s5-more" aria-label="Scroll for more">↓</a>
      </div>

      <div className="s5-below" id="s5-more">
        <p className="s5-sub">
          {SUBHEAD} <strong className="s5-sub-em">You sign every note.</strong>
        </p>
        <div className="s5-note">
          <div className="s5-note-head font-mono">
            <span>SOAP draft</span>
            <span className="s5-note-ok">✓ transcript-anchored</span>
          </div>
          <ol className="s5-note-list font-mono">
            {SOAP.map((l) => (
              <li key={l.tag}>
                <span className="s5-note-tag">{l.tag}</span>
                <span>{l.text}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="s5-cta">
          <a className="s5-btn s5-btn-primary" href="https://staging.quillmd.com/#start">
            Start free <span aria-hidden>→</span>
          </a>
          <a className="s5-btn s5-btn-ghost" href="https://staging.quillmd.com/#sandbox">See it work</a>
        </div>
        <ul className="s5-trust font-mono" aria-label="What QuillMD guarantees">
          {TRUST.map((t, i) => (
            <li key={t}>
              {i > 0 && <span aria-hidden>·</span>}
              {t}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
