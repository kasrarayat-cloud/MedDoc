'use client';

// S3 — HORIZONTAL SCROLL. Structural lock: NYT TimesMachine (a horizontal filmstrip of
// panels side-by-side). A track of full-height chapter panels — Intro → Listen → Draft →
// Verify → Sign — the user moves SIDEWAYS through them. Native horizontal scroll + snap +
// ←/→ buttons + arrow keys; a desktop wheel→horizontal enhancement (off under reduced-motion
// and on mobile). Mobile fallback: the track becomes a normal vertical stack.
import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from '../motion/shared';
import { CHAPTERS } from './content';

export function S3Horizontal() {
  const reduce = useReducedMotion();
  const trackRef = useRef<HTMLDivElement>(null);
  const [idx, setIdx] = useState(0);
  const idxRef = useRef(0); // mirror of idx so the keyboard handler can bind once (stable deps)
  const total = CHAPTERS.length + 1; // intro + chapters

  // progress indicator follows scroll position
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const onScroll = () => {
      const i = el.clientWidth ? Math.round(el.scrollLeft / el.clientWidth) : 0;
      const c = Math.max(0, Math.min(total - 1, i));
      idxRef.current = c;
      setIdx(c);
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, [total]);

  // desktop wheel → horizontal (progressive enhancement; native scroll/keys/buttons always
  // work without it; disabled under reduced-motion and on the mobile stacked layout)
  useEffect(() => {
    const el = trackRef.current;
    if (!el || reduce) return;
    const onWheel = (e: WheelEvent) => {
      // desktop only — mirrors the CSS breakpoint (max-width:860px = mobile vertical stack)
      if (!window.matchMedia('(min-width: 861px)').matches) return;
      if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
      el.scrollLeft += e.deltaY;
      e.preventDefault();
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [reduce]);

  const go = (n: number) => {
    const el = trackRef.current;
    if (!el) return;
    const t = Math.max(0, Math.min(total - 1, n));
    idxRef.current = t;
    setIdx(t); // jump the progress readout straight to the target (no smooth-scroll flicker)
    el.scrollTo({ left: t * el.clientWidth, behavior: reduce ? 'auto' : 'smooth' });
  };

  // arrow keys page through the track (reads idxRef, so the listener binds once)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      if (e.key === 'ArrowRight') go(idxRef.current + 1);
      else if (e.key === 'ArrowLeft') go(idxRef.current - 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduce]);

  return (
    <section className="s3" aria-label="Concept 3 — horizontal chapters">
      <div className="s3-track" ref={trackRef}>
        <article className="s3-panel s3-intro">
          <p className="s3-ey font-mono">QuillMD, in four moves</p>
          <h1 className="s3-title">
            The note<br />writes itself.
          </h1>
          <p className="s3-cue font-mono" aria-hidden>scroll →</p>
        </article>

        {CHAPTERS.map((c, i) => (
          <article className="s3-panel" key={c.n}>
            <span className="s3-num font-mono" aria-hidden>{String(i + 1).padStart(2, '0')}</span>
            <p className="s3-chapter font-mono">{c.n}</p>
            <h2 className="s3-h">{c.title}</h2>
            <p className="s3-body">{c.body}</p>
            {i === CHAPTERS.length - 1 && (
              <div className="s3-cta">
                <a className="s3-btn s3-btn-primary" href="https://staging.quillmd.com/#start">
                  Start free <span aria-hidden>→</span>
                </a>
                <a className="s3-btn s3-btn-ghost" href="https://staging.quillmd.com/#sandbox">See it work</a>
              </div>
            )}
          </article>
        ))}
      </div>

      <div className="s3-controls">
        <button className="s3-arrow" type="button" aria-label="Previous chapter" onClick={() => go(idx - 1)} disabled={idx === 0}>
          ←
        </button>
        <span className="s3-progress font-mono" aria-live="polite">
          {idx + 1} / {total}
        </span>
        <button className="s3-arrow" type="button" aria-label="Next chapter" onClick={() => go(idx + 1)} disabled={idx === total - 1}>
          →
        </button>
      </div>
    </section>
  );
}
