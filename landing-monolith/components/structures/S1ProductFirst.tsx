'use client';

// S1 — PRODUCT-FIRST. Structural lock: ElevenLabs Studio (app IS the page). No marketing
// hero — the user lands inside the QuillMD recorder: top app bar, left rail, a canvas where
// the SOAP note writes itself, and a bottom waveform + live transcript bar. Copy comes AFTER.
import type { CSSProperties } from 'react';
import { SOAP, TRUST } from '../motion/shared';
import { LIVE_LINE } from './content';

const RAIL = ['Record', 'Transcript', 'Note', 'Codes', 'Sign'];

export function S1ProductFirst() {
  return (
    <section className="s1" aria-label="Concept 1 — product-first: you land in the app">
      <div className="s1-window">
        <header className="s1-bar">
          <div className="s1-brand">Quill<span className="s1-brand-md">MD</span></div>
          <div className="s1-bar-mid font-mono">
            <span className="s1-rec" aria-hidden><i />REC</span> 02:14 · Room 4 · today
          </div>
          <button className="s1-sign" type="button">Sign note</button>
        </header>

        <div className="s1-body">
          <nav className="s1-rail" aria-label="Recorder">
            {RAIL.map((l, i) => (
              <span key={l} className={`s1-rail-item ${i === 2 ? 'active' : ''}`}>
                <i aria-hidden />
                {l}
              </span>
            ))}
          </nav>

          <div className="s1-canvas">
            <div className="s1-canvas-head font-mono">
              <span>Note — draft</span>
              <span className="s1-writing">writing…</span>
            </div>
            <h1 className="s1-title">The note writes itself</h1>
            <ol className="s1-note">
              {SOAP.map((l) => (
                <li key={l.tag} className="s1-note-ln">
                  <span className="s1-note-tag">{l.tag}</span>
                  <span className="s1-note-text">{l.text}</span>
                </li>
              ))}
              <li className="s1-note-cue" aria-hidden>
                <span className="s1-caret" />
              </li>
            </ol>
          </div>
        </div>

        <footer className="s1-foot">
          <span className="s1-play font-mono" aria-hidden>❚❚</span>
          <div className="s1-wave" aria-hidden>
            {Array.from({ length: 56 }).map((_, i) => (
              <i key={i} style={{ '--d': i % 13 } as CSSProperties} />
            ))}
          </div>
          <div className="s1-live font-mono" aria-hidden>{LIVE_LINE}</div>
        </footer>
      </div>

      <aside className="s1-after">
        <p className="s1-after-ey font-mono">You just watched it work</p>
        <p className="s1-after-lead">
          No template picking, no dictation, no after-hours catch-up. QuillMD drafts the note from the
          visit while you’re still in the room — every line anchored to the transcript. You review and sign.
        </p>
        <div className="s1-after-cta">
          <a className="s1-btn s1-btn-primary" href="https://staging.quillmd.com/#start">
            Start free <span aria-hidden>→</span>
          </a>
          <a className="s1-btn s1-btn-ghost" href="https://staging.quillmd.com/#sandbox">See it work</a>
        </div>
        <ul className="s1-trust font-mono" aria-label="What QuillMD guarantees">
          {TRUST.map((t, i) => (
            <li key={t}>
              {i > 0 && <span aria-hidden>·</span>}
              {t}
            </li>
          ))}
        </ul>
      </aside>
    </section>
  );
}
