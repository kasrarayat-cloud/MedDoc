'use client';

import { useEffect, useRef } from 'react';
import { Headline, HeroCopy, SOAP, useReducedMotion } from '../shared';

// v1 — the existing quill hero, ported: the quill writes the headline on load,
// then keeps writing a SOAP note as you scroll.
export function V1Quill() {
  const reduce = useReducedMotion();
  const stageRef = useRef<HTMLDivElement>(null);
  const quillRef = useRef<HTMLDivElement>(null);
  const lineRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const soapRef = useRef<HTMLOListElement>(null);
  const soapLineRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    if (reduce) return;
    const stage = stageRef.current;
    const quill = quillRef.current;
    const lines = lineRefs.current.filter(Boolean) as HTMLSpanElement[];
    if (!stage || lines.length === 0) return;
    stage.classList.add('is-writing');

    let raf = 0, start = 0;
    let geom: { left: number; top: number; width: number; height: number }[] | null = null;
    const PER = 600, GAP = 130, total = lines.length * (PER + GAP);
    const frame = (now: number) => {
      if (!start) start = now;
      if (!geom) {
        const sr = stage.getBoundingClientRect();
        geom = lines.map((ln) => {
          const r = ln.getBoundingClientRect();
          return { left: r.left - sr.left, top: r.top - sr.top, width: r.width, height: r.height };
        });
      }
      const t = now - start;
      lines.forEach((ln, i) => {
        const g = geom![i];
        const e = -(Math.cos(Math.PI * Math.min(Math.max((t - i * (PER + GAP)) / PER, 0), 1)) - 1) / 2;
        ln.style.setProperty('--p', `${e}`);
        if (quill && t >= i * (PER + GAP) && t < (i + 1) * (PER + GAP)) {
          quill.style.setProperty('--qx', `${g.left + g.width * e}px`);
          quill.style.setProperty('--qy', `${g.top + g.height * 0.82}px`);
        }
      });
      if (t < total) raf = requestAnimationFrame(frame);
      else {
        lines.forEach((l) => l.style.setProperty('--p', '1'));
        const last = geom[geom.length - 1];
        if (quill) {
          quill.style.setProperty('--qx', `${last.left + last.width + 14}px`);
          quill.style.setProperty('--qy', `${last.top + last.height * 0.5}px`);
          quill.classList.add('quill-rest');
        }
      }
    };
    const timer = window.setTimeout(() => { raf = requestAnimationFrame(frame); }, 320);

    const soap = soapRef.current;
    const sl = soapLineRefs.current.filter(Boolean) as HTMLLIElement[];
    let sraf = 0;
    const onScroll = () => {
      if (sraf) return;
      sraf = requestAnimationFrame(() => {
        sraf = 0;
        if (!soap) return;
        const r = soap.getBoundingClientRect();
        const prog = Math.min(Math.max((window.innerHeight - r.top) / (window.innerHeight * 0.6), 0), 1);
        sl.forEach((li, i) => li.style.setProperty('--p', `${Math.min(Math.max(prog * sl.length - i, 0), 1)}`));
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => { cancelAnimationFrame(raf); cancelAnimationFrame(sraf); window.removeEventListener('scroll', onScroll); window.clearTimeout(timer); };
  }, [reduce]);

  return (
    <section className={`ml-hero v1 ${reduce ? 'reduce' : ''}`} aria-label="Concept 1 — the quill">
      <div className="v1-glow" aria-hidden />
      <div className="ml-stage v1-stage" ref={stageRef}>
        <div className="v1-quill" ref={quillRef} aria-hidden>
          <svg viewBox="0 0 120 160" width="110" height="146" fill="none" aria-hidden>
            <defs>
              <linearGradient id="v1f" x1="0.2" y1="0" x2="0.8" y2="1"><stop offset="0" stopColor="#f4d28a" /><stop offset="0.5" stopColor="#e8b85c" /><stop offset="1" stopColor="#9c6f2e" /></linearGradient>
              <linearGradient id="v1n" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#e8b85c" /><stop offset="1" stopColor="#3fd8c8" /></linearGradient>
            </defs>
            <path d="M86 8 C40 30 22 70 14 120 C44 104 70 70 96 26 C94 20 90 12 86 8 Z" fill="url(#v1f)" />
            <path d="M14 120 L40 148" stroke="url(#v1n)" strokeWidth="3.4" strokeLinecap="round" />
            <circle cx="41" cy="149" r="3.2" fill="#3fd8c8" /><circle cx="41" cy="149" r="7" fill="#3fd8c8" opacity="0.25" />
          </svg>
        </div>
        <div className="ml-copy">
          <p className="ml-eyebrow">Ambient clinical documentation</p>
          <Headline lineRef={(el, i) => { lineRefs.current[i] = el; }} lineClass="v1-line" />
          <HeroCopy />
        </div>
        <ol className="v1-soap font-mono" ref={soapRef} aria-hidden>
          {SOAP.map((l, i) => (
            <li key={l.tag} ref={(el) => { soapLineRefs.current[i] = el; }} className="v1-soap-ln">
              <span className={`v1-soap-tag v1-${l.tag}`}>{l.tag}</span>
              <span className="v1-soap-text">{l.text}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
