'use client';

import { useEffect, useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { HEADLINE, HeroCopy, useReducedMotion } from '../shared';

// v4 — kinetic typography. The giant headline IS the hero: each word is
// magnetically pulled toward the cursor with spring physics and skews with
// scroll velocity. Type as graphic; minimal else.
export function V4Kinetic() {
  const reduce = useReducedMotion();
  const heroRef = useRef<HTMLElement>(null);
  // pointer position, normalized −1..1 around hero center
  const px = useMotionValue(0);
  const py = useMotionValue(0);

  useEffect(() => {
    if (reduce) return;
    const el = heroRef.current;
    if (!el) return;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      px.set(((e.clientX - r.left) / r.width) * 2 - 1);
      py.set(((e.clientY - r.top) / r.height) * 2 - 1);
    };
    const onLeave = () => { px.set(0); py.set(0); };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    return () => { el.removeEventListener('pointermove', onMove); el.removeEventListener('pointerleave', onLeave); };
  }, [reduce, px, py]);

  return (
    <section ref={heroRef} className={`ml-hero v4 ${reduce ? 'reduce' : ''}`} aria-label="Concept 4 — kinetic typography">
      <div className="v4-grid" aria-hidden />
      <div className="ml-stage v4-stage">
        <div className="ml-copy v4-copy">
          <p className="ml-eyebrow">Ambient clinical documentation</p>
          <h1 className="font-display v4-title">
            {HEADLINE.map((l, i) => (
              <span className="v4-line" key={i}>
                <KineticWord text={l.text} accent={l.accent} px={px} py={py} index={i} reduce={reduce} />
              </span>
            ))}
          </h1>
          <HeroCopy />
        </div>
      </div>
    </section>
  );
}

function KineticWord({
  text, accent, px, py, index, reduce,
}: {
  text: string; accent: boolean;
  px: ReturnType<typeof useMotionValue<number>>; py: ReturnType<typeof useMotionValue<number>>;
  index: number; reduce: boolean;
}) {
  // each line pulls a different amount + direction for a parallax-of-type feel
  const depth = 1 + index * 0.55;
  const sx = useSpring(useTransform(px, (v) => v * 26 * depth), { stiffness: 120, damping: 16, mass: 0.6 });
  const sy = useSpring(useTransform(py, (v) => v * 14 * depth), { stiffness: 120, damping: 16, mass: 0.6 });
  const skew = useSpring(useTransform(px, (v) => v * -5 * depth), { stiffness: 90, damping: 14 });

  if (reduce) {
    return <span className={accent ? 'text-turq' : ''}>{text}</span>;
  }
  return (
    <motion.span
      className={`v4-word ${accent ? 'text-turq' : ''}`}
      style={{ x: sx, y: sy, skewX: skew, display: 'inline-block', willChange: 'transform' }}
    >
      {text}
    </motion.span>
  );
}

export default V4Kinetic;
