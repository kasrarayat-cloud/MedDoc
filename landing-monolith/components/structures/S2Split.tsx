'use client';

// S2 — SPLIT-SCREEN. Structural lock: Squarespace 50/50 vertical split. A hard centre seam
// divides the viewport into two halves: LEFT (dark) the "before" — after-hours charting;
// RIGHT (light) the "after" — the note already written and signed. A before/after diptych,
// not a single column. The primary <h1> lives on the "after" half.
import { SOAP, TRUST } from '../motion/shared';

const PILE = ['“finish notes”', 'BP ~150/90?', 'f/u 4 wks??', '+ amlodipine', 'home readings', '— 11:42 pm'];

export function S2Split() {
  return (
    <section className="s2" aria-label="Concept 2 — split screen: before and after">
      <div className="s2-half s2-before">
        <div className="s2-half-inner">
          <p className="s2-kicker font-mono">Before QuillMD</p>
          {/* styled like a heading but kept a <p>: it's subordinate to the page <h1> on the
              "after" half, so this avoids an h2-before-h1 heading-order inversion */}
          <p className="s2-h s2-h-before">An hour of notes<br />after every clinic.</p>
          <p className="s2-p">Charting after hours. Templates that never quite fit. The visit, half-remembered at 9 pm.</p>
          <ul className="s2-pile" aria-hidden>
            {PILE.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="s2-half s2-after">
        <div className="s2-half-inner">
          <p className="s2-kicker s2-kicker-after font-mono">After QuillMD</p>
          <h1 className="s2-h s2-h-after">The note<br />writes itself.</h1>
          <div className="s2-note">
            <div className="s2-note-head font-mono">
              <span>SOAP · signed</span>
              <span className="s2-note-ok">✓</span>
            </div>
            <ol className="s2-note-list font-mono">
              {SOAP.map((l) => (
                <li key={l.tag}>
                  <span className="s2-note-tag">{l.tag}</span>
                  <span>{l.text}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="s2-cta">
            <a className="s2-btn s2-btn-primary" href="https://staging.quillmd.com/#start">
              Start free <span aria-hidden>→</span>
            </a>
            <a className="s2-btn s2-btn-ghost" href="https://staging.quillmd.com/#sandbox">See it work</a>
          </div>
          <ul className="s2-trust font-mono" aria-label="What QuillMD guarantees">
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
