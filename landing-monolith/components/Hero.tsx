'use client';

import { useEffect, useRef } from 'react';

const TRUST = ['HIPAA-ready', 'BAA included', 'US-hosted', 'You sign every note'];

// The headline, split into its visual lines. It stays a real, selectable <h1>
// (the spans only let the quill reveal it line-by-line); screen readers read
// the full heading. The accent class colors the last line.
const HEADLINE: { text: string; accent?: boolean }[] = [
  { text: 'The note' },
  { text: 'writes' },
  { text: 'itself', accent: true },
];

// The quill keeps writing as you scroll — one short SOAP note, scroll-driven.
const SOAP: { tag: string; label: string; text: string; chip?: 'verified' | 'review' }[] = [
  { tag: 'S', label: 'Subjective', text: '54M, 3-mo HTN follow-up, home BP ~150/90.', chip: 'verified' },
  { tag: 'O', label: 'Objective', text: 'BP 148/92, HR 78, lungs clear.', chip: 'verified' },
  { tag: 'A', label: 'Assessment', text: 'Hypertension, uncontrolled.', chip: 'review' },
  { tag: 'P', label: 'Plan', text: 'Add amlodipine 5 mg; f/u 4 wks.', chip: 'verified' },
];

export function Hero() {
  const sectionRef = useRef<HTMLElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const quillRef = useRef<HTMLDivElement>(null);
  const lineRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const soapRef = useRef<HTMLOListElement>(null);
  const soapLineRefs = useRef<(HTMLLIElement | null)[]>([]);

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const section = sectionRef.current;
    const glow = glowRef.current;
    const stage = stageRef.current;
    const quill = quillRef.current;

    // ── Pointer-tracked turquoise glow (kept; off under reduced motion) ──
    let glowRaf = 0;
    const onMove = (e: PointerEvent) => {
      if (!section || !glow) return;
      const r = section.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width) * 100;
      const y = ((e.clientY - r.top) / r.height) * 100;
      cancelAnimationFrame(glowRaf);
      glowRaf = requestAnimationFrame(() => {
        glow.style.setProperty('--gx', `${x}%`);
        glow.style.setProperty('--gy', `${y}%`);
      });
    };
    if (!reduce && section) section.addEventListener('pointermove', onMove);

    // Reduced motion / no measurable layout → everything is already visible
    // (CSS default --p:1). Nothing to animate.
    if (reduce || !stage || !section) {
      return () => {
        if (section) section.removeEventListener('pointermove', onMove);
        cancelAnimationFrame(glowRaf);
      };
    }

    // ── Headline: the quill writes it line-by-line on load ──
    const lines = lineRefs.current.filter(Boolean) as HTMLSpanElement[];
    section.classList.add('is-writing'); // CSS: lines start hidden, quill shown

    let writeRaf = 0;
    let start = 0;
    // Line geometry (relative to the stage) is MEASURED ONCE — the headline is
    // static during the write, so we cache it on the first frame and never call
    // getBoundingClientRect again in the loop (no per-frame reads, no thrash).
    let geom: { left: number; top: number; width: number; height: number }[] | null = null;
    const PER_LINE = 620; // ms to write one line
    const GAP = 130; // ms pen lifts between lines
    const total = lines.length * (PER_LINE + GAP);

    const writeFrame = (now: number) => {
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
        const lineStart = i * (PER_LINE + GAP);
        const local = Math.min(Math.max((t - lineStart) / PER_LINE, 0), 1);
        // easeInOutSine for a hand-drawn cadence
        const e = -(Math.cos(Math.PI * local) - 1) / 2;
        ln.style.setProperty('--p', `${e}`);

        // Park the quill at the pen edge of the line currently being written.
        if (t >= lineStart && t < lineStart + PER_LINE + GAP && quill) {
          quill.style.setProperty('--qx', `${g.left + g.width * e}px`);
          quill.style.setProperty('--qy', `${g.top + g.height * 0.82}px`);
        }
      });

      if (t < total) {
        writeRaf = requestAnimationFrame(writeFrame);
      } else {
        lines.forEach((ln) => ln.style.setProperty('--p', '1'));
        // Settle the quill to an elegant resting float near the last line's end.
        const last = geom[geom.length - 1];
        if (quill) {
          quill.style.setProperty('--qx', `${last.left + last.width + 14}px`);
          quill.style.setProperty('--qy', `${last.top + last.height * 0.5}px`);
          quill.classList.add('quill-rest');
        }
        section.classList.add('write-done');
      }
    };
    // Brief beat before the first stroke.
    const startTimer = window.setTimeout(() => {
      writeRaf = requestAnimationFrame(writeFrame);
    }, 360);

    // ── SOAP: scroll-driven inking ──
    const soap = soapRef.current;
    const soapLines = soapLineRefs.current.filter(Boolean) as HTMLLIElement[];
    let scrollRaf = 0;
    const onScroll = () => {
      if (scrollRaf) return;
      scrollRaf = requestAnimationFrame(() => {
        scrollRaf = 0;
        if (!soap) return;
        const r = soap.getBoundingClientRect();
        const vh = window.innerHeight;
        // 0 when the block's top is near the fold, 1 when it has risen ~62% up
        // the screen — driven by scrolling through the hero.
        const progress = Math.min(Math.max((vh - r.top) / (vh * 0.62), 0), 1);
        const n = soapLines.length;
        soapLines.forEach((li, i) => {
          const local = Math.min(Math.max(progress * n - i, 0), 1);
          li.style.setProperty('--p', `${local}`);
          li.classList.toggle('inked', local >= 0.96);
        });
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    return () => {
      if (section) section.removeEventListener('pointermove', onMove);
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(glowRaf);
      cancelAnimationFrame(writeRaf);
      cancelAnimationFrame(scrollRaf);
      window.clearTimeout(startTimer);
    };
  }, []);

  return (
    <section ref={sectionRef} className="hero hero-quill" aria-label="QuillMD — the note writes itself">
      <div
        ref={glowRef}
        className="hero-glow"
        aria-hidden
        style={{ ['--gx' as string]: '50%', ['--gy' as string]: '34%' }}
      />
      {/* The monolith, kept as a faint atmospheric backdrop — the quill is the star. */}
      <img src="/assets/hero-monolith.webp" alt="" aria-hidden className="hero-backdrop" width={1344} height={768} decoding="async" />

      <nav className="nav" aria-label="Primary">
        <a className="brand font-display" href="#top">
          Quill<span className="text-turq">MD</span>
        </a>
        <div className="nav-links">
          <a href="#sandbox">Sandbox</a>
          <a href="#journey">How it works</a>
          <a href="#security">Security</a>
          <a className="btn btn-ghost nav-cta" href="#start">Start free</a>
        </div>
      </nav>

      <div className="hero-stage" id="top" ref={stageRef}>
        {/* The quill that writes the headline. Decorative; hidden from AT. */}
        <div ref={quillRef} className="quill" aria-hidden>
          <QuillSVG />
        </div>

        <div className="hero-copy">
          <p className="eyebrow reveal is-in">Ambient clinical documentation</p>
          <h1 className="font-display hero-title quill-title">
            {HEADLINE.map((l, i) => (
              <span className="qline-wrap" key={i}>
                <span
                  ref={(el) => { lineRefs.current[i] = el; }}
                  className={`qline ${l.accent ? 'text-turq' : ''}`}
                  style={{ ['--p' as string]: 1 }}
                >
                  {l.text}
                </span>
              </span>
            ))}
          </h1>
          <p className="hero-sub">
            QuillMD listens to the visit and drafts the note from what was
            actually said — every line anchored to the transcript, machine-verified,
            with a review lane for anything it can’t ground.
            <strong className="text-gold"> You sign every note.</strong>
          </p>
          <div className="hero-cta">
            <a className="btn btn-primary" href="#start">
              Start free <span aria-hidden>→</span>
            </a>
            <a className="btn btn-ghost" href="#sandbox">See it work</a>
          </div>
          <ul className="trust-row" aria-label="What QuillMD guarantees">
            {TRUST.map((t, i) => (
              <li key={t}>
                {i > 0 && <span className="trust-dot" aria-hidden>·</span>}
                {t}
              </li>
            ))}
          </ul>
        </div>

        {/* The quill keeps writing as you scroll — the note, on ruled ink lines. */}
        <ol className="hero-soap font-mono" ref={soapRef} aria-label="A SOAP note the quill writes as you scroll">
          {SOAP.map((l, i) => (
            <li
              key={i}
              ref={(el) => { soapLineRefs.current[i] = el; }}
              className="hsoap-ln"
              style={{ ['--p' as string]: 1 }}
            >
              <span className={`hsoap-tag hsoap-${l.tag}`} title={l.label} aria-label={l.label}>{l.tag}</span>
              <span className="hsoap-text">{l.text}</span>
              {l.chip && (
                <span className={`chip chip-${l.chip}`}>
                  {l.chip === 'verified' ? '✓ verified' : '⚑ review'}
                </span>
              )}
            </li>
          ))}
        </ol>
      </div>

      <a className="scroll-hint font-mono" href="#sandbox" aria-label="Scroll to the live sandbox">
        ↓ watch it write
      </a>
    </section>
  );
}

function QuillSVG() {
  return (
    <svg viewBox="0 0 120 160" width="120" height="160" fill="none" aria-hidden>
      <defs>
        <linearGradient id="feather" x1="0.2" y1="0" x2="0.8" y2="1">
          <stop offset="0" stopColor="#f4d28a" />
          <stop offset="0.5" stopColor="#e8b85c" />
          <stop offset="1" stopColor="#9c6f2e" />
        </linearGradient>
        <linearGradient id="qnib" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#e8b85c" />
          <stop offset="1" stopColor="#3fd8c8" />
        </linearGradient>
      </defs>
      {/* feather barbs */}
      <path d="M86 8 C40 30 22 70 14 120 C44 104 70 70 96 26 C94 20 90 12 86 8 Z" fill="url(#feather)" opacity="0.95" />
      <path d="M86 8 C56 28 38 64 22 110" stroke="#7a531f" strokeWidth="1.4" opacity="0.5" />
      <g stroke="#8a5e22" strokeWidth="1" opacity="0.35">
        <path d="M64 36 L80 22" /><path d="M52 56 L72 38" /><path d="M40 78 L64 56" /><path d="M30 98 L54 76" />
      </g>
      {/* shaft → nib */}
      <path d="M14 120 L40 148" stroke="url(#qnib)" strokeWidth="3.4" strokeLinecap="round" />
      {/* nib tip + ink glow */}
      <circle cx="41" cy="149" r="3.2" fill="#3fd8c8" />
      <circle cx="41" cy="149" r="7" fill="#3fd8c8" opacity="0.25" />
    </svg>
  );
}
