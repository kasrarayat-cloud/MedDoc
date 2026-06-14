'use client';

// SCREEN 3 (final 3) — AUTH / SIGN-IN, in the dark family. A quiet single card. The states are
// EXPLICIT (the old form silently morphed between sign-in / verify / MFA / recovery) — here Sign in,
// Sign up, and MFA are distinct, clearly-titled steps, switchable via the mockup control so all are
// visible. Live password feedback on sign-up; errors are persistent + inline (role=alert), never a
// transient toast. Static mockup — nothing authenticates.
import { useId, useState, type FormEvent } from 'react';
import { SAMPLE_BANNER } from './data';

type Mode = 'signin' | 'signup' | 'mfa';

function AuthField({
  label, type, value, onChange, placeholder, autoComplete, invalid, describedBy, inputMode,
}: {
  label: string; type: string; value: string; onChange: (v: string) => void;
  placeholder?: string; autoComplete?: string; invalid?: boolean; describedBy?: string; inputMode?: 'numeric';
}) {
  const id = useId();
  return (
    <div className="ax-si-field">
      <label className="ax-si-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        className="ax-si-input"
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        inputMode={inputMode}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
      />
    </div>
  );
}

export function SigninScreen() {
  const [mode, setMode] = useState<Mode>('signin');
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const errId = useId();

  const switchMode = (m: Mode) => { setMode(m); setError(''); setPw(''); setCode(''); };

  const checks = [
    { label: 'At least 8 characters', ok: pw.length >= 8 },
    { label: 'A number', ok: /\d/.test(pw) },
    { label: 'A letter', ok: /[a-zA-Z]/.test(pw) },
  ];
  const pwValid = checks.every((c) => c.ok);

  const signinSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !pw) {
      setError('Enter your email and password.');
      return;
    }
    setError('That email or password isn’t right. Please try again.');
  };

  return (
    <div className="ax-root ax-si">
      <main className="ax-si-card">
        <div className="ax-si-brand"><span className="ax-brand-mark" aria-hidden>◆</span> QuillMD</div>

        {mode === 'signin' && (
          <form className="ax-si-form" onSubmit={signinSubmit} noValidate>
            <h1 className="ax-si-h">Sign in</h1>
            <p className="ax-si-sub">Welcome back.</p>
            <AuthField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" placeholder="you@clinic.com" invalid={!!error} describedBy={error ? errId : undefined} />
            <AuthField label="Password" type="password" value={pw} onChange={setPw} autoComplete="current-password" invalid={!!error} describedBy={error ? errId : undefined} />
            {error && <p className="ax-si-error" id={errId} role="alert">{error}</p>}
            <button className="ax-si-go" type="submit">Sign in</button>
            <div className="ax-si-links">
              <button className="ax-link" type="button">Forgot password?</button>
              <button className="ax-link" type="button" onClick={() => switchMode('signup')}>Create account</button>
            </div>
          </form>
        )}

        {mode === 'signup' && (
          <form className="ax-si-form" onSubmit={(e) => e.preventDefault()} noValidate>
            <h1 className="ax-si-h">Create your account</h1>
            <p className="ax-si-sub">Start documenting in minutes.</p>
            <AuthField label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" placeholder="you@clinic.com" />
            <AuthField label="Password" type="password" value={pw} onChange={setPw} autoComplete="new-password" />
            <ul className="ax-si-checks" aria-label="Password requirements" aria-live="polite">
              {checks.map((c) => (
                <li key={c.label} className={c.ok ? 'ok' : ''}>
                  <span className="ax-si-check-mark" aria-hidden>{c.ok ? '✓' : '○'}</span> {c.label}
                </li>
              ))}
            </ul>
            <button className="ax-si-go" type="submit" disabled={!pwValid || !email.trim()}>Create account</button>
            <div className="ax-si-links">
              <span className="ax-si-muted">Already have an account?</span>
              <button className="ax-link" type="button" onClick={() => switchMode('signin')}>Sign in</button>
            </div>
          </form>
        )}

        {mode === 'mfa' && (
          <form className="ax-si-form" onSubmit={(e) => e.preventDefault()} noValidate>
            <h1 className="ax-si-h">Two-factor authentication</h1>
            <p className="ax-si-sub">Enter the 6-digit code from your authenticator app.</p>
            <AuthField label="Authentication code" type="text" inputMode="numeric" value={code} onChange={(v) => setCode(v.replace(/\D/g, '').slice(0, 6))} placeholder="000000" autoComplete="one-time-code" />
            <button className="ax-si-go" type="submit" disabled={code.length !== 6}>Verify</button>
            <div className="ax-si-links">
              <button className="ax-link" type="button">Use a recovery code</button>
              <button className="ax-link" type="button" onClick={() => switchMode('signin')}>Back to sign in</button>
            </div>
          </form>
        )}

        <p className="ax-si-sample">● {SAMPLE_BANNER}</p>
      </main>

      {/* mockup control — preview the explicit auth states (clearly a demo affordance) */}
      <nav className="ax-si-mock" aria-label="Mockup state controls">
        <span className="ax-si-mock-tag" aria-hidden>◆ MOCKUP</span>
        <div className="ax-si-mock-grp" role="group" aria-label="Auth state">
          <button type="button" className={mode === 'signin' ? 'on' : ''} aria-pressed={mode === 'signin'} onClick={() => switchMode('signin')}>Sign in</button>
          <button type="button" className={mode === 'signup' ? 'on' : ''} aria-pressed={mode === 'signup'} onClick={() => switchMode('signup')}>Sign up</button>
          <button type="button" className={mode === 'mfa' ? 'on' : ''} aria-pressed={mode === 'mfa'} onClick={() => switchMode('mfa')}>MFA</button>
        </div>
      </nav>
    </div>
  );
}
