'use client';

// The full-width sections that resolve out of the split spine. They inherit the same palette,
// type and seam-accent (a sage hairline / top-border) so the page reads as one cohesive thing.
import { APP_WAITLIST_URL } from '@/lib/constants';
import { TRUST } from './shared';
import { STEPS, COMPARE, PRICE_INCLUDES, FAQS } from './content';

export function HowItWorks() {
  return (
    <section className="fx-how" id="how" aria-label="How it works">
      <div className="fx-wrap">
        <p className="fx-kicker fx-kicker-mid font-mono">How it works</p>
        <h2 className="fx-section-h">Four steps.<br />You’re in the last one.</h2>
        <ol className="fx-steps">
          {STEPS.map((s) => (
            <li key={s.n} className="fx-step fx-reveal">
              <span className="fx-step-n font-mono">{s.n}</span>
              <h3 className="fx-step-h">{s.label}</h3>
              <p className="fx-step-b">{s.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Comparison() {
  return (
    <section className="fx-compare" id="compare" aria-label="QuillMD compared to enterprise scribes">
      <div className="fx-wrap">
        <p className="fx-kicker fx-kicker-on-dark font-mono">The comparison</p>
        <h2 className="fx-section-h fx-on-dark">Built for the exam room,<br />not the procurement cycle.</h2>
        <div className="fx-table-wrap fx-reveal">
          <table className="fx-table">
            <thead>
              <tr>
                <th scope="col"><span className="fx-sr">Feature</span></th>
                <th scope="col" className="fx-tq">QuillMD</th>
                <th scope="col" className="fx-te">Typical enterprise scribe</th>
              </tr>
            </thead>
            <tbody>
              {COMPARE.map((r) => (
                <tr key={r.f}>
                  <th scope="row" className="fx-tf">{r.f}</th>
                  <td className="fx-tq">{r.q === true ? <span className="fx-check" aria-label="yes">✓</span> : r.q}</td>
                  <td className="fx-te">{r.e === 'varies' ? <span className="fx-varies">varies</span> : r.e}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="fx-compare-note font-mono">“Typical enterprise scribe” describes the general category, not a specific vendor.</p>
      </div>
    </section>
  );
}

export function Pricing() {
  return (
    <section className="fx-pricing" id="pricing" aria-label="Pricing">
      <div className="fx-wrap fx-pricing-wrap">
        <div className="fx-pricing-copy">
          <p className="fx-kicker fx-kicker-mid font-mono">Pricing</p>
          <h2 className="fx-section-h">One price.<br />No procurement.</h2>
          <p className="fx-section-lede">Flat, per provider. No per-visit fees and no enterprise contract to sign.</p>
        </div>
        <div className="fx-plan fx-reveal">
          <div className="fx-plan-price">
            <span className="fx-plan-amt">$49</span>
            <span className="fx-plan-per font-mono">/ provider / month</span>
          </div>
          <p className="fx-plan-flat font-mono">flat — no per-visit fees</p>
          <ul className="fx-plan-list">
            {PRICE_INCLUDES.map((t) => (
              <li key={t}>
                <span className="fx-check" aria-hidden>✓</span>
                {t}
              </li>
            ))}
          </ul>
          <a className="fx-btn fx-btn-primary fx-plan-cta" href={APP_WAITLIST_URL}>
            Get started <span aria-hidden>→</span>
          </a>
        </div>
      </div>
    </section>
  );
}

export function Faq() {
  return (
    <section className="fx-faq" id="faq" aria-label="Frequently asked questions">
      <div className="fx-wrap fx-faq-wrap">
        <div className="fx-faq-head">
          <p className="fx-kicker fx-kicker-mid font-mono">Questions</p>
          <h2 className="fx-section-h">The ones<br />doctors ask.</h2>
        </div>
        <div className="fx-faq-list">
          {FAQS.map((f) => (
            <details key={f.q} className="fx-faq-item">
              <summary className="fx-faq-q">
                <span>{f.q}</span>
                <span className="fx-faq-mark" aria-hidden>+</span>
              </summary>
              <p className="fx-faq-a">{f.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function FinalCta() {
  return (
    <section className="fx-final" id="get-started" aria-label="Get started">
      <div className="fx-wrap fx-final-wrap">
        <p className="fx-kicker fx-kicker-on-dark font-mono">Your notes, done</p>
        <h2 className="fx-final-h">Leave the room with<br />the note already written.</h2>
        <div className="fx-cta fx-final-cta">
          <a className="fx-btn fx-btn-primary" href={APP_WAITLIST_URL}>
            Get started <span aria-hidden>→</span>
          </a>
          <a className="fx-btn fx-btn-ghost fx-btn-ghost-dark" href="#faq">Read the FAQ</a>
        </div>
        <ul className="fx-trust fx-trust-dark font-mono" aria-label="What QuillMD guarantees">
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
