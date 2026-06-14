# QuillMD — SOAP review redesign concepts (`/concepts/soap`)

Staging-only design exploration. Three distinct redesigns of the worst + most-used screen
(`/visits/[id]` in the live app), toward **simple, calm, one-clear-action** clinical review.
**Static mockups** with synthetic no-PHI data — NOT wired to the real visit pipeline, server
actions, auth, or data. The live app, pipeline, production and co-tenants are untouched.

## The problem (from the app inventory)
The current SOAP review is a **6-tab workspace** with **three competing primary buttons** —
green "Bump to 99214 · +$32" (revenue), the rail "Confirm 99213 · sign", and "Sign & Send" —
an always-on billing rail, stacked amber banners, a jargon-heavy AI lane, and the **Rx critical
block-state living on a different tab than the Sign button.** A doctor can't tell what THE
action is.

**The fix all three concepts share:** note primary + readable · **exactly ONE Sign button** ·
AI suggestions + Rx warnings as a calm *secondary* surface (never blocking from a hidden tab) ·
any sign-blocker (Rx critical override, E/M confirm) surfaces **inline next to Sign** ·
billing/coding demoted to a quiet, collapsed detail — never a competing CTA.

Tokens kept faithful to the real app: dark `#08090a`, sage `#7AA68C`, Inter + JetBrains Mono.
This is about **density + information architecture, not palette.**

## C1 — GRAMMARLY MODEL (lead reference: Grammarly)
The SOAP note is the primary document (left, wide, readable). One **calm right rail** holds the
secondary work as accept/edit/dismiss cards: the AI **suggestions** (adopt / dismiss), the **Rx
warnings** (the critical one carries an "override to sign" affordance), and a **collapsed
"Coding · 99213" detail** (quiet, expandable — the 99214 option is a calm review line, not a
green CTA). One obvious **"Sign note"** button (top-right + sticky). Sign-blockers appear inline
beside Sign ("1 item to resolve" / "Code changed — confirm").
- **Kills the 3 buttons:** there is only Sign. The "+$32 bump" becomes a collapsed coding line;
  the rail "confirm · sign" is gone (the E/M confirm is an inline checkbox on the Sign button,
  not a second button).

## C2 — FOCUS / STEPPED
A calm guided sequence — **Review note → Resolve flagged items → Sign** — shown as a slim top
progress bar with **one focused panel at a time**, so there is always exactly ONE thing to do
next and never 6 tabs at once.
- Step 1 *Review*: just the note, full width. Primary: "Looks right — continue."
- Step 2 *Resolve*: the lane items + Rx warnings **together** as one checklist (adopt/dismiss
  each suggestion; acknowledge/override the critical Rx). Primary: "All clear — continue"
  (enabled once handled).
- Step 3 *Sign*: a short summary (code `99213`, the E/M confirm if it changed, export as a quiet
  secondary) + the single big **"Sign note."**
- **Kills the 3 buttons:** each step has exactly one primary; the Rx/lane resolution IS a step
  (so the blocker can never hide on another tab); billing is one quiet line at the sign step.

## C3 — NOTE-ONLY + ON-DEMAND DRAWER (reference: WaPo side-sheet / master-detail)
Maximal note-primacy: the note is **full-width and alone**, with just the **"Sign note"** button
and a single **"2 to review" pill**. All secondary work (suggestions, Rx, coding) lives in a
**dismissible right drawer** opened from that pill; closed by default, so the note is the only
thing on screen until the doctor chooses to review.
- **Kills the 3 buttons:** the note dominates; everything else is one calm drawer behind one
  count pill; Sign is the only button. The pill is informational (a count), not a CTA.

All three keep ALL real functionality represented — note editing, the AI suggestions lane with
adopt/dismiss, Rx warnings + critical override, the E/M confirm-before-sign, and sign + export —
just arranged simply with one clear primary.

## Synthetic sample (no PHI)
The hypertension follow-up: amlodipine 5 mg (new) + lisinopril 20 mg + simvastatin 40 mg; BP
148/92; one grounded lane suggestion (order a BMP) + one held suggestion (DASH counseling — "not
stated in this visit"); one **critical** Rx interaction (amlodipine × simvastatin → 20 mg cap,
blocks signing until overridden) + one info interaction (lisinopril × amlodipine). Patient is
labelled "Sample patient · synthetic" throughout.

## Floor
Real selectable text; `prefers-reduced-motion` static; readable; visible focus; mobile graceful
(the rail/drawer/steps stack on tablet/phone); 60fps. Route-scoped: Inter/JetBrains + soap.css
load only on `/concepts/soap`; root, /motion, /heroes, /structures, /final stay untouched.
