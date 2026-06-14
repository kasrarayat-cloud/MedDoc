'use client';

// SCREEN 2 (final 3) — SETTINGS, in the C3 calm-one-action pattern. The old endless 7-section
// scroll collapses to a calm section rail + one panel at a time. Clean separate sections (Profile,
// Security, Note format, Billing, Danger zone). The note-format power-editor is hidden behind an
// EXPLICIT opt-in (not shown to every doctor). ONE clearly-labelled danger zone. Placeholder
// features removed. Static mockup — fields are display-only, nothing is wired.
import { useId, useState } from 'react';
import { AppShell } from './AppShell';
import { SAMPLE_BANNER, DOCTOR } from './data';

type SectionKey = 'profile' | 'security' | 'notes' | 'billing' | 'danger';
const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: 'profile', label: 'Profile' },
  { key: 'security', label: 'Security' },
  { key: 'notes', label: 'Note format' },
  { key: 'billing', label: 'Billing' },
  { key: 'danger', label: 'Danger zone' },
];

function Field({ label, value, type = 'text' }: { label: string; value: string; type?: string }) {
  const id = useId();
  return (
    <div className="ax-set-field">
      <label className="ax-set-label" htmlFor={id}>{label}</label>
      <input id={id} className="ax-set-input" type={type} defaultValue={value} />
    </div>
  );
}

function Toggle({ label, hint, on, onChange }: { label: string; hint?: string; on: boolean; onChange: (v: boolean) => void }) {
  const lblId = useId();
  return (
    <div className="ax-set-toggle">
      <span className="ax-set-toggle-text">
        <span className="ax-set-toggle-label" id={lblId}>{label}</span>
        {hint && <span className="ax-set-toggle-hint">{hint}</span>}
      </span>
      <button type="button" role="switch" aria-checked={on} aria-labelledby={lblId} className={`ax-switch ${on ? 'on' : ''}`} onClick={() => onChange(!on)}>
        <span className="ax-switch-knob" aria-hidden />
      </button>
    </div>
  );
}

export function SettingsScreen() {
  const [section, setSection] = useState<SectionKey>('profile');
  const [mfaOn, setMfaOn] = useState(true);
  const [customFormat, setCustomFormat] = useState(false);

  return (
    <AppShell active="settings">
      <div className="ax-set">
        <div className="ax-set-top">
          <h1 className="ax-set-title">Settings</h1>
          <span className="ax-sample">● {SAMPLE_BANNER}</span>
        </div>

        <div className="ax-set-body">
          <nav className="ax-set-rail" aria-label="Settings sections">
            {SECTIONS.map((s) => (
              <button
                key={s.key}
                type="button"
                className={`ax-set-tab ${section === s.key ? 'on' : ''} ${s.key === 'danger' ? 'danger' : ''}`}
                aria-pressed={section === s.key}
                onClick={() => setSection(s.key)}
              >
                {s.label}
              </button>
            ))}
          </nav>

          <div className="ax-set-panel">
            {section === 'profile' && (
              <section className="ax-set-sec" aria-label="Profile">
                <h2 className="ax-set-h">Profile</h2>
                <Field label="Full name" value="Dr. Sample" />
                <Field label="Email" value="sample@quillmd-test.local" type="email" />
                <Field label="Specialty" value="Internal medicine" />
                <button className="ax-cta ax-set-save" type="button">Save changes</button>
              </section>
            )}

            {section === 'security' && (
              <section className="ax-set-sec" aria-label="Security">
                <h2 className="ax-set-h">Security</h2>
                <div className="ax-set-row">
                  <div className="ax-set-row-text">
                    <span className="ax-set-row-label">Password</span>
                    <span className="ax-set-row-hint">Last changed 3 months ago</span>
                  </div>
                  <button className="ax-set-2nd" type="button">Change password</button>
                </div>
                <Toggle label="Two-factor authentication" hint={mfaOn ? 'On — required at sign-in' : 'Off'} on={mfaOn} onChange={setMfaOn} />
                <div className="ax-set-row">
                  <div className="ax-set-row-text">
                    <span className="ax-set-row-label">Active sessions</span>
                    <span className="ax-set-row-hint">This device · 2 others</span>
                  </div>
                  <button className="ax-set-2nd" type="button">Sign out others</button>
                </div>
              </section>
            )}

            {section === 'notes' && (
              <section className="ax-set-sec" aria-label="Note format">
                <h2 className="ax-set-h">Note format</h2>
                <p className="ax-set-p">QuillMD writes in a standard SOAP format. Most doctors leave this as-is. If you have your own template, you can teach QuillMD to match it.</p>
                <Toggle
                  label="Use my own note format"
                  hint={customFormat ? 'On — QuillMD will match your format' : 'Off — using the standard SOAP format'}
                  on={customFormat}
                  onChange={setCustomFormat}
                />
                {customFormat && (
                  <div className="ax-set-advanced">
                    <p className="ax-set-p">Upload or paste a sample note and QuillMD will learn its structure. This is an advanced, opt-in workflow.</p>
                    <button className="ax-set-2nd" type="button">Open the format editor →</button>
                  </div>
                )}
              </section>
            )}

            {section === 'billing' && (
              <section className="ax-set-sec" aria-label="Billing">
                <h2 className="ax-set-h">Billing</h2>
                <div className="ax-set-plan">
                  <div>
                    <span className="ax-set-plan-name">Solo</span>
                    <span className="ax-set-plan-price">$49 / month</span>
                  </div>
                  <span className="ax-set-plan-renew">Renews Apr 14</span>
                </div>
                <div className="ax-set-row">
                  <div className="ax-set-row-text">
                    <span className="ax-set-row-label">Payment method</span>
                    <span className="ax-set-row-hint">Visa ···· 4242</span>
                  </div>
                  <button className="ax-set-2nd" type="button">Update</button>
                </div>
                <button className="ax-link" type="button">Manage billing &amp; invoices</button>
              </section>
            )}

            {section === 'danger' && (
              <section className="ax-set-sec" aria-label="Danger zone">
                <h2 className="ax-set-h ax-set-h-danger">Danger zone</h2>
                <div className="ax-set-danger">
                  <div className="ax-set-row-text">
                    <span className="ax-set-row-label">Delete account</span>
                    <span className="ax-set-row-hint">Permanently deletes {DOCTOR.name}’s account and every note. This can’t be undone.</span>
                  </div>
                  <button className="ax-set-danger-btn" type="button">Delete account</button>
                </div>
              </section>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
