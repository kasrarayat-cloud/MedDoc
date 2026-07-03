'use client';

// Hero — the signature 50/50 split (promoted from S2). LEFT dark "before" (the 9pm charting
// pile) ｜ RIGHT light "after" (the clean signed SOAP). A hard vertical seam between them.
// On load the seam draws and the after-side note assembles (subtle, .js-gated). The page's
// <h1> is the "after" headline.
import { APP_SIGNUP_URL } from '@/lib/constants';
import { SOAP, TRUST } from './shared';

const PILE = ['“finish notes”', 'BP ~150/90?', 'f/u 4 wks??', '+ amlodipine', 'home readings', '— 11:42 pm'];

export function HeroSplit() {
  return (
    <section className="fx-hero" aria-label="QuillMD — before and after">
      <div className="fx-hero-half fx-before">
        <div className="fx-hero-inner">
          <p className="fx-kicker font-mono">Before QuillMD</p>
          <p className="fx-h fx-h-before">An hour of notes<br />after every clinic.</p>
          <p className="fx-before-p">Charting after hours. Templates that never quite fit. The visit, half-remembered at 9&nbsp;pm.</p>
          <ul className="fx-pile" aria-hidden>
            {PILE.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="fx-hero-half fx-after">
        <div className="fx-hero-inner">
          <p className="fx-kicker fx-kicker-after font-mono">After QuillMD</p>
          <h1 className="fx-h fx-h-after">The note<br />writes itself.</h1>
          <p className="fx-after-p">
            QuillMD listens to the visit and drafts the note from what was actually said — every line
            anchored to the transcript, machine-verified, with a review lane for anything it can’t
            ground. <strong>You sign every note.</strong>
          </p>
          <div className="fx-note">
            <div className="fx-note-head font-mono">
              <span>SOAP · signed</span>
              <span className="fx-note-ok">✓</span>
            </div>
            <ol className="fx-note-list font-mono">
              {SOAP.map((l, i) => (
                <li key={`${l.tag}-${i}`}>
                  <span className="fx-note-tag">{l.tag}</span>
                  <span>{l.text}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="fx-cta">
            <a className="fx-btn fx-btn-primary" href={APP_SIGNUP_URL}>
              Get started <span aria-hidden>→</span>
            </a>
            <a className="fx-btn fx-btn-ghost" href="#how">See how it works</a>
          </div>
          <ul className="fx-trust font-mono" aria-label="What QuillMD guarantees">
            {TRUST.map((t, i) => (
              <li key={t}>
                {i > 0 && <span aria-hidden>·</span>}
                {t}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="fx-seam" aria-hidden />
    </section>
  );
}
