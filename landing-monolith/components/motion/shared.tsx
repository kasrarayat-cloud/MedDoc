'use client';

import { useEffect, useState } from 'react';

// The SAME real content rides on every concept. The headline is split into its
// visual lines but stays a real selectable <h1> (animation reveals it).
export const HEADLINE = [
  { text: 'The note', accent: false },
  { text: 'writes', accent: false },
  { text: 'itself', accent: true },
];

export const SUBHEAD =
  'QuillMD listens to the visit and drafts the note from what was actually said — every line anchored to the transcript, machine-verified, with a review lane for anything it can’t ground.';

export const TRUST = ['HIPAA-ready', 'BAA included', 'US-hosted', 'You sign every note'];

// One sample SOAP draft, shared by the concepts that render a note (v1, v3).
export const SOAP = [
  { tag: 'S', text: '54M, 3-mo HTN follow-up, home BP ~150/90.' },
  { tag: 'O', text: 'BP 148/92, HR 78, lungs clear.' },
  { tag: 'A', text: 'Hypertension, uncontrolled.' },
  { tag: 'P', text: 'Add amlodipine 5 mg; f/u 4 wks.' },
];

/** True once on the client when the user asks for reduced motion. SSR-safe
 *  (returns false on the server so content is never gated on JS). */
export function useReducedMotion(): boolean {
  const [reduce, setReduce] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduce(mq.matches);
    const on = () => setReduce(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return reduce;
}

/** The subhead + CTAs + trust row — identical and static across all 5 concepts,
 *  always rendered (real text, visible without JS). The headline is rendered
 *  per-concept so each can animate it its own way. */
export function HeroCopy() {
  return (
    <>
      <p className="ml-sub">
        {SUBHEAD} <strong className="text-gold">You sign every note.</strong>
      </p>
      <div className="ml-cta">
        <a className="btn btn-primary" href="https://staging.quillmd.com/#start">
          Start free <span aria-hidden>→</span>
        </a>
        <a className="btn btn-ghost" href="https://staging.quillmd.com/#sandbox">See it work</a>
      </div>
      <ul className="ml-trust" aria-label="What QuillMD guarantees">
        {TRUST.map((t, i) => (
          <li key={t}>
            {i > 0 && <span className="ml-trust-dot" aria-hidden>·</span>}
            {t}
          </li>
        ))}
      </ul>
    </>
  );
}

/** A real selectable <h1> with per-line spans (for line-by-line reveals).
 *  `lineClass(i)` lets a concept add per-line classes/refs without changing
 *  the accessible heading text. */
export function Headline({
  lineRef,
  lineClass = '',
}: {
  lineRef?: (el: HTMLSpanElement | null, i: number) => void;
  lineClass?: string;
}) {
  return (
    <h1 className="font-display ml-title">
      {HEADLINE.map((l, i) => (
        <span className="ml-line-wrap" key={i}>
          <span
            ref={lineRef ? (el) => lineRef(el, i) : undefined}
            className={`ml-line ${l.accent ? 'text-turq' : ''} ${lineClass}`}
          >
            {l.text}
          </span>
        </span>
      ))}
    </h1>
  );
}
