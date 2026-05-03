'use client';

import { useRef } from 'react';
import { useCounter } from '@/hooks/useCounter';

/**
 * Problem stage — Phase 7 v6 (Apple Product).
 *
 * Centred full-viewport stage. Massive 2.0 number (clamp 180-460px) with
 * gradient text-fill, sub copy, source citation, then the 4-bar comparison
 * chart at the bottom (sage on the QuillMD bar).
 *
 * The 2.0 number animates from 0.0 once it scrolls into view via useCounter.
 */
const BARS = [
  { label: 'Paper (1990)', value: '0.4h', heightPct: 30 },
  { label: 'EHR (2010)', value: '1.2h', heightPct: 60 },
  { label: 'Today', value: '2.0h', heightPct: 100 },
  { label: 'With QuillMD', value: '~0.15h', heightPct: 8, us: true },
];

export function Problem() {
  const statRef = useRef<HTMLDivElement>(null);
  useCounter(statRef, 2.0, 1600);

  return (
    <section className="stage" id="problem">
      <div className="container stage-inner">
        <div className="reveal">
          <span className="eyebrow-tiny">The real cost of charting</span>
        </div>

        <div className="reveal delay-1">
          <div className="problem-num" ref={statRef}>
            0.0
          </div>
          <span className="problem-unit">hours of charting · per hour of patient care</span>
        </div>

        <p className="stage-sub reveal delay-2" style={{ marginTop: 48 }}>
          Hours of charting for every hour of patient care.{' '}
          <span className="sage">Half your day spent on paperwork.</span>
        </p>

        <div className="problem-source reveal delay-3">
          JAMA Intern Med · Sinsky et al. · Ann Int Med 2017
        </div>

        <div className="problem-bars reveal delay-4">
          {BARS.map((b) => (
            <div key={b.label} className={b.us ? 'pbar us' : 'pbar'}>
              <div className="pbar-num">{b.value}</div>
              <div
                className={b.us ? 'pbar-bar us' : 'pbar-bar'}
                style={{ height: `${b.heightPct}%` }}
              />
              <div className="pbar-label">{b.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
