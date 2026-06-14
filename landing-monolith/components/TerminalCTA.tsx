'use client';

import { useState } from 'react';

export function TerminalCTA() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const value = email.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setError('Enter a valid email address.');
      return;
    }
    setError(null);
    // Staging: no backend wired. The real onboarding handoff lands here.
    setSubmitted(true);
  }

  return (
    <section id="start" className="section cta" aria-label="Get started">
      <div className="glass glass-edge terminal reveal">
        <div className="terminal-bar font-mono" aria-hidden>
          <span className="dotrow"><i /><i /><i /></span>
          <span className="terminal-title">onboarding — quillmd — zsh</span>
          <span className="terminal-flat">$49 / mo · flat</span>
        </div>

        <div className="terminal-body font-mono">
          <p className="term-line">
            <span className="term-prompt">~</span>
            <span className="term-cmd">quillmd --initiate-onboarding</span>
          </p>
          <p className="term-out">
            <span className="text-turq">✓</span> evidence-anchored notes ·
            <span className="text-turq"> ✓</span> machine-verified ·
            <span className="text-turq"> ✓</span> you sign every note
          </p>
          <p className="term-out term-dim">
            audio retained 90 days after signing · HIPAA-ready · BAA included · US-hosted
          </p>

          {submitted ? (
            <p className="term-success" role="status">
              <span className="text-gold">→</span> Thanks. We’ll reach out at{' '}
              <span className="text-turq">{email}</span> to get you set up.
            </p>
          ) : (
            <form className="term-form" onSubmit={onSubmit} noValidate>
              <label htmlFor="cta-email" className="term-input-line">
                <span className="term-prompt" aria-hidden>❯</span>
                <span className="sr-only">Your work email to start onboarding</span>
                <input
                  id="cta-email"
                  name="email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  placeholder="you@clinic.com"
                  className="term-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  aria-invalid={!!error}
                  aria-describedby={error ? 'cta-error' : undefined}
                />
                <span className="term-caret" aria-hidden />
              </label>
              <button type="submit" className="btn btn-primary term-submit">
                Start free <span aria-hidden>↵</span>
              </button>
            </form>
          )}

          {error && (
            <p id="cta-error" className="term-error" role="alert">
              <span aria-hidden>✗ </span>{error}
            </p>
          )}
        </div>
      </div>

      <footer className="site-foot font-mono">
        <span>© {new Date().getFullYear()} QuillMD</span>
        <span className="foot-mid">The note writes itself. You sign it.</span>
        <span className="text-ink-3">staging</span>
      </footer>
    </section>
  );
}
