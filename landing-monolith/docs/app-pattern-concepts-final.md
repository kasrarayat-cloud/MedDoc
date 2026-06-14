# QuillMD — final 3 concept screens (`/concepts/patient`, `/concepts/settings`, `/concepts/signin`)

Staging-only design exploration. Completes the C3 calm-one-action family — **every** doctor-facing
screen is now designed as a static mockup before the real build. Synthetic no-PHI data, NOT wired to
the real pipeline/auth. The live app, production and co-tenants are untouched. Reuses the merged
`AppShell` + `StatusPill` + `--ax-*` tokens, so these belong to the same family as the dashboard,
record, and C3 review.

## Screen 1 — Patient detail (`/concepts/patient`)
A calm patient header (identity + the few facts a doctor wants at a glance: **problems, medications,
allergies**) + a quiet **visit timeline that reuses the dashboard inbox row + status pill** — the top
visit is "Ready to sign," the rest "Signed," each opening the C3 review. **One** primary
("+ New visit"); **"Open last note"** one click away. Gone: the 4 stat tiles, the dense 6-col table,
the "Coming soon" tabs, the duplicate "New visit" CTAs. (Refs: TravelPerk/Cohere profile + record list.)

## Screen 2 — Settings (`/concepts/settings`)
The old endless 7-section scroll collapses to a calm **section rail + one panel** (Profile · Security ·
Note format · Billing · Danger zone). The **note-format power-editor is hidden behind an explicit
opt-in** — by default a doctor sees a one-line explainer + a toggle ("Use my own note format," off);
only when on does the advanced "Open the format editor →" appear. **One** clearly-labelled (coral)
**danger zone** with a single "Delete account." Placeholder/non-functional features removed.
(Refs: Raycast dark settings, Fernand calm two-pane, Mercury billing, Cohere danger-zone.)

## Screen 3 — Auth / sign-in (`/concepts/signin`)
A quiet single dark card. The states are **EXPLICIT** (the old form silently morphed): **Sign in**,
**Sign up**, and **MFA** are distinct, clearly-titled steps (switchable via the mockup control to
preview all). **Live password feedback** on sign-up (a criteria checklist that updates per keystroke,
`aria-live`); errors are **persistent + inline** (`role="alert"`, fields `aria-invalid`) — never a
transient toast. MFA is its own step (6-digit code), not a morph. (Refs: Manus/Monarch/Kinhive cards,
Hers inline-error.)

## Build / isolation
Additive — `app/concepts/(app)/{patient,settings,signin}` + `components/concepts/app/{PatientScreen,
SettingsScreen,SigninScreen}`; `app.css` extended **append-only** (new rule blocks; no existing rule
edited). Patient + Settings use the shared `AppShell` (active=patients / settings); Sign-in is
standalone (no nav — pre-auth) on the same `.ax-root` tokens. No other landing route changed; the real
app (`apps/transcribe-md`) is git-clean.

## Floor
Real selectable text; visible focus; `prefers-reduced-motion` gates the switch + checklist transitions
(content stays static text); mobile/tablet graceful — the consistent bottom nav for patient/settings,
the settings rail becomes a horizontal scroll strip, the patient header + facts stack; 60fps.

## All doctor-facing screens are now designed — staged plan for the REAL build (apps/transcribe-md)
Skin-only — the pipeline (transcribe → SOAP → coding → Rx → referral), auth, BAAs and all hardening
stay untouched; each stage staged + smoke-verified before production:
1. **Core flow first** — dashboard → record → review (C3). Highest-traffic, highest-value. Build the
   shared chrome (one nav, mobile nav, unified status words) once, then the three screens against the
   existing server actions/data — no pipeline change.
2. **Patient detail** — reuses the chrome + the inbox row + status pill from stage 1; mostly a
   re-layout of existing patient/visit queries.
3. **Settings** — section rail; fold the existing note-format editor behind the opt-in; one danger zone.
4. **Auth / sign-in** — explicit states over the existing NextAuth flow; lowest churn, do last.
Each stage: feature-flag or route-level, screenshot-diff against the mockup, ship to staging, smoke,
then production.
