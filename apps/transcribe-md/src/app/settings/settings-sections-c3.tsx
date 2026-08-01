'use client';

// ============================================================================
// SettingsSectionsC3 — the "section rail + one panel at a time" shell for the
// C3 settings skin (Stage 3, flag-gated).
// ----------------------------------------------------------------------------
// The legacy settings page renders all sections in one long scroll behind a
// sticky jumplink index. The C3 skin keeps a calm left rail and shows exactly
// ONE panel at a time — matching /concepts/settings.
//
// PRESENTATION ONLY. Every panel's content (ProfileForm, NoteFormatManager,
// ChangePasswordForm, SessionPanel, DeleteAccountDialog, …) is rendered by the
// server component and passed in as `content` nodes; this component never
// touches a server action. All panels stay MOUNTED (inactive ones are hidden
// via the `hidden` attribute) so an in-progress edit is never lost when the
// doctor switches sections.
// ============================================================================

import { useState, type ReactNode } from 'react';

export interface SettingsSectionC3 {
  id: string;
  label: string;
  title: string;
  subtitle?: string;
  danger?: boolean;
  content: ReactNode;
}

export function SettingsSectionsC3({
  sections,
  initialSection,
}: {
  sections: SettingsSectionC3[];
  /** Which panel opens first. Used by the `/settings/<section>` route segments,
   *  which exist because a nav item and a customer email both link straight to
   *  one — and until C1-g those links 404'd.
   *
   *  ⚠️ VALIDATED AGAINST THE REAL SECTION LIST, never trusted. The value comes
   *  from a URL path, and an unknown id would leave `active` matching no panel:
   *  all seven stay mounted with `hidden`, so the page would render the rail
   *  above an empty column and throw nothing. Falling back to the first section
   *  is the honest failure — the doctor lands somewhere real. */
  initialSection?: string;
}) {
  const [active, setActive] = useState(
    initialSection && sections.some((s) => s.id === initialSection)
      ? initialSection
      : sections[0]?.id ?? '',
  );

  return (
    <div className="qm-c3-set-body">
      <nav className="qm-c3-set-rail" aria-label="Settings sections">
        {sections.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`qm-c3-set-tab qm-tap-44 ${active === s.id ? 'on' : ''} ${
              s.danger ? 'danger' : ''
            }`}
            aria-pressed={active === s.id}
            onClick={() => setActive(s.id)}
          >
            {s.label}
          </button>
        ))}
      </nav>

      <div className="qm-c3-set-panels">
        {sections.map((s) => (
          <section
            key={s.id}
            id={s.id}
            aria-label={s.title}
            hidden={active !== s.id}
            className={`qm-c3-set-panel ${s.danger ? 'danger' : ''}`}
          >
            <h2
              className={`qm-c3-set-h ${s.danger ? 'danger' : ''}`}
            >
              {s.title}
            </h2>
            {s.subtitle && <p className="qm-c3-set-sub">{s.subtitle}</p>}
            <div className="qm-c3-set-content">{s.content}</div>
          </section>
        ))}
      </div>
    </div>
  );
}
