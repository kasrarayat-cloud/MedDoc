'use client';

import { useRef } from 'react';
import { useCounter } from '@/hooks/useCounter';

const BARS = [
  { label: 'Paper (1990)', value: '0.4h', heightPct: 30 },
  { label: 'EHR (2010)', value: '1.2h', heightPct: 60 },
  { label: 'Today', value: '2.0h', heightPct: 100 },
  { label: 'With QuillMD', value: '~0.15h', heightPct: 8, us: true },
];

export function Problem() {
  const statRef = useRef<HTMLDivElement>(null);
  useCounter(statRef, 2.0, 1400);

  return (
    <section className="problem reveal">
      <div className="container">
        <span className="stat-unit">§ The real cost of charting</span>
        <div ref={statRef} className="stat-big" id="statBig">
          0.0
        </div>
        <div className="stat-caption">
          Hours of charting for every hour of patient care. <br />
          That&apos;s{' '}
          <em style={{ color: 'var(--accent-bright)', fontStyle: 'italic' }}>half your day</em>{' '}
          spent on paperwork.
        </div>
        <div className="stat-source">JAMA Intern Med · Sinsky et al. · Ann Int Med 2017</div>
        <div className="bars">
          {BARS.map((b) => (
            <div
              key={b.label}
              className={b.us ? 'bar us' : 'bar'}
              style={{ height: `${b.heightPct}%` }}
            >
              <span className="lbl">{b.label}</span>
              <span className="val">{b.value}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
