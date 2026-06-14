'use client';

// Shared real content for all four hero concepts. The headline, subhead, CTAs and
// trust row are IDENTICAL across H1–H4 (single source of truth = motion/shared.tsx);
// only the `p` class-prefix changes so each concept styles them to its locked
// reference. The <h1> stays a real, selectable heading.
import { HEADLINE, SUBHEAD, TRUST } from '../motion/shared';

export function HeroHeadline({ p }: { p: string }) {
  return (
    <h1 className={`${p}-title`}>
      {HEADLINE.map((l, i) => (
        <span className={`${p}-line-wrap`} key={i}>
          <span className={`${p}-line${l.accent ? ` ${p}-accent` : ''}`}>{l.text}</span>
        </span>
      ))}
    </h1>
  );
}

export function HeroSub({ p }: { p: string }) {
  return (
    <p className={`${p}-sub`}>
      {SUBHEAD} <strong className={`${p}-sub-em`}>You sign every note.</strong>
    </p>
  );
}

export function HeroCtas({ p }: { p: string }) {
  return (
    <div className={`${p}-cta`}>
      <a className={`${p}-btn ${p}-btn-primary`} href="https://staging.quillmd.com/#start">
        Start free <span aria-hidden>→</span>
      </a>
      <a className={`${p}-btn ${p}-btn-ghost`} href="https://staging.quillmd.com/#sandbox">
        See it work
      </a>
    </div>
  );
}

export function HeroTrust({ p }: { p: string }) {
  return (
    <ul className={`${p}-trust`} aria-label="What QuillMD guarantees">
      {TRUST.map((t, i) => (
        <li key={t}>
          {i > 0 && (
            <span className={`${p}-trust-dot`} aria-hidden>
              ·
            </span>
          )}
          {t}
        </li>
      ))}
    </ul>
  );
}
