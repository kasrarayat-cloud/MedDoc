'use client';

import { useRef } from 'react';
import { useCounter } from '@/hooks/useCounter';

/**
 * Problem stat panel — Linear V1 (Faithful).
 *
 * "2.0 hours of charting per hour of patient care" — sage stat, bar chart
 * comparing eras. Built from inline-styled boxes on Linear V1 tokens; no
 * Source Serif italic accent, sage-bright span replaces the old <em>.
 */
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
    <section className="reveal" style={{ padding: '64px 0 96px' }}>
      <div className="container">
        <div className="section-head">
          <div className="section-eyebrow">The real cost of charting</div>
          <h2 className="section-title">
            <span ref={statRef} style={{ fontFamily: 'var(--font-mono)' }} id="statBig">
              0.0
            </span>
            <span
              style={{
                fontSize: 18,
                color: 'var(--color-linear-text-3)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {' '}
              hours
            </span>
          </h2>
          <p className="section-sub">
            Hours of charting for every hour of patient care.{' '}
            <span className="text-linear-sage-bright" style={{ color: 'var(--color-linear-sage-bright)' }}>
              Half your day spent on paperwork.
            </span>
          </p>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10.5,
              color: 'var(--color-linear-text-3)',
              marginTop: 6,
              letterSpacing: '0.04em',
            }}
          >
            JAMA Intern Med · Sinsky et al. · Ann Int Med 2017
          </div>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${BARS.length}, 1fr)`,
            gap: 16,
            maxWidth: 720,
            margin: '0 auto',
            padding: '0 0 0 0',
            alignItems: 'end',
            height: 220,
          }}
        >
          {BARS.map((b) => {
            const sage = b.us;
            return (
              <div
                key={b.label}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                  height: '100%',
                  justifyContent: 'flex-end',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    color: sage
                      ? 'var(--color-linear-sage-bright)'
                      : 'var(--color-linear-text-2)',
                  }}
                >
                  {b.value}
                </span>
                <div
                  style={{
                    width: '100%',
                    height: `${Math.max(b.heightPct, 6)}%`,
                    background: sage
                      ? 'var(--color-linear-sage)'
                      : 'var(--color-linear-surface-2)',
                    border: `1px solid ${
                      sage
                        ? 'rgba(122, 166, 140, 0.4)'
                        : 'var(--color-linear-hairline)'
                    }`,
                    borderRadius: 6,
                    transition: 'background-color 200ms ease-out',
                  }}
                />
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10.5,
                    color: 'var(--color-linear-text-3)',
                    textAlign: 'center',
                    letterSpacing: '0.04em',
                    textTransform: 'uppercase',
                  }}
                >
                  {b.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
