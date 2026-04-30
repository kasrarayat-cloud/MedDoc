# Transcribe-MD Phase 1, Stage C — Design Directions

Generated: 2026-04-29
Author: Design Director subagent
Foundation: extends App-redesign-v1 / HANDOFF tokens (see `docs/DESIGN_TOKENS.md` §A) — every direction reuses the same 5-bg / 4-fg / 3-line / violet / mint-amber-coral palette and the same Source Serif 4 + Inter Tight + JetBrains Mono trio.

Each direction lives as a single self-contained HTML file. Open in a browser:

- `direction-A.html` — clinical / professional — Linear-meets-Epic
- `direction-B.html` — warm / human — Notion-meets-medical
- `direction-C.html` — dense / power-user — Bloomberg-meets-Raycast

Each file shows two views side-by-side: **Dashboard (left pane)** and **Visit Detail in READY state (right pane)**.

---

## 1. Two-sentence summaries

**A — Clinical / Professional.** A audited, sober, Epic-EHR-meets-Linear surface — high information density, sharp 6&ndash;8 px corners, mono labels everywhere, flat status pills, no orbs, no shader. The data wins; the chrome retreats.

**B — Warm / Human.** B treats the app as a thoughtful instrument rather than a hospital terminal — Source Serif 4 in headlines and prose, generous 16&ndash;28 px radii, soft warm-cream foreground, gradient status pills, and a single quiet ambient pulse-dot in place of the orb. Identity stays dark/violet; we just let it breathe.

**C — Dense / Power-User.** C is built for the doctor who already lives in EHR shortcuts and resents whitespace — 12 px mono base, an always-visible inline command bar, kbd hints on every action, three-column workspaces with sidenav + sticky tables + footer status bar, and 2&ndash;4 px corners. Same paint, applied like a terminal.

---

## 2. Comparison table

| Trait | A — Clinical | B — Warm | C — Dense |
|---|---|---|---|
| **Density** | High — table-of-visits dashboard, 4-up stat strip, 13.5px base | Medium — patient-card grid + visit list, 14.5px base, lots of whitespace | Maximum — sidenav + 12-row sticky table, 12px base, 6-up stat strip |
| **Ornament** | Minimal — flat pills, no gradients on chrome, scrollbars visible | Moderate — keeps gradient pills, soft glass cards, mark has specular highlight, ambient dot | None — flat pills, no glass, sharp dividers, footer status bar |
| **Typography** | Inter Tight 13.5px primary, JetBrains Mono for all meta + labels, Source Serif 4 reserved for visit-name moment | Source Serif 4 leads — page headline, patient names, ICD descriptions, SOAP body all serif. Inter Tight for UI chrome. Mono only for IDs/timestamps. | JetBrains Mono is the **base font**. Source Serif 4 not used. Inter Tight only for the few sans moments (logo, button labels, patient name in detail header). |
| **Motion language** | Conservative — `.12s var(--ease)` linear hovers, no bounce, no springs | Springy — `var(--ease-back)` translateY -2/-3 px on cards, ambient pulse-dot, gradient sweep on primary CTA | Functional only — `step` cursor blink in command bar, no hover lift, no transitions on tables |
| **Fit for clinical trust** | **Highest** — looks audited; the visible audit-log row + pipeline metadata block reinforce traceability | Medium-high — feels safe and considered, but the gradient pills + serif body can read as "consumer app" to a chief-of-staff reviewer | Medium — looks expert but risks looking experimental; non-power-users may misread the density as unfinished |
| **Performance budget** | Light — no Three.js, no WebGL, no glass blur on tables, page-radial only | Moderate — keeps backdrop-blur on cards + buttons, gradient sweeps, ambient-dot animation | Lightest — no blurs, no shadows beyond 1-px borders, no gradients except on the 14×14 logo mark |
| **Accommodates Rx warning card?** | Yes — Rx warning's audited, sectioned, "transcribed | risk | next" structure is right at home next to flat status pills and mono section labels | Acceptable — Rx warning's severity-themed gradient pills harmonize with B's pill styling, but the Rx card's density (518 LOC, transcribed/risk/next blocks) feels heavier than the rest of the surface | Yes — Rx warning's dense risk/outcome list and pill-driven severity reads as one of many sections, not a special case |
| **Day-1 effort to migrate** | Low — most existing `.qm-*` classes already produce flat looks; mostly a radius and pill-flatten pass | Medium — need to add `.qm-card-soft`, larger radii, serif-body utilities, ambient-dot component, soft button hover | High — need a new dense-table primitive, sidenav, command-bar, statusbar, kbd-row component family. ~6 new `.qm-*` blocks. |
| **Effort to keep `<AppFrame>` shipping unchanged** | Easy — same shell, tighter padding | Easy — same shell, more padding | Hard — `<AppFrame>` currently centers content; C wants three-column workspaces, which rewrites the shell |
| **Empty-state feel** | "0 visits / no data yet" — mono and matter-of-fact | "No patients yet — start your first visit, we'll create the record for you" — serif and warm (current handoff matches this exactly) | "rows = 0 · cursor = null" — terminal-style |

---

## 3. Recommendation

**Pick B (Warm / Human).** Three reasons.

First, **the App-redesign-v1 work already in production leans warm.** `dashboard/page.tsx` already opens with `<em style="color:var(--accent-bright)">workspace</em>` in serif-italic, the `EmptyPatients` block uses serif headlines and a violet-tinted illustration cradle, and `<PatientCard>` already mounts the patient name in `qm-serif`. Choosing A would silently revert merged stylistic decisions; choosing C would require rewriting `<AppFrame>` itself. B is the only direction that **continues the trajectory the codebase is already on** rather than bending it.

Second, **the Rx warning card already does the heavy lifting for clinical trust.** The 518-LOC `<RxWarningCard>` (with its severity-themed pill, transcribed-vs-guess block, risk list, next-step strip) is itself an audited, dense, mono-flecked piece — exactly what direction A would commit to across the whole app. But because it's already that intense for the moments that matter (drug interactions, allergy hits), the rest of the surface doesn't have to be. Letting the dashboard and visit-ready view feel calmer makes the Rx warning card's intensity *land harder when it appears* — it stops being one density among many and becomes a signal. B is the right baseline; the Rx card is the right exception.

Third, **this is a clinician's daily-driver tool, not a trading desk.** Doctors are not Bloomberg traders — they have to live with this surface for 8&ndash;12 hours a day, often while talking to a person. C's command-bar-and-kbd-everywhere idiom is exhilarating for the first hour and exhausting by week two. A's audited density reads correct in a code review and tiring in clinic. B's serif-and-soft-radii idiom is the closest match to how a thoughtful doctor wants to feel about their tool.

**A and C are not wrong** — A is the right choice if a future enterprise customer (e.g. a hospital system) requires an Epic-styled aesthetic; C is the right choice if QuillMD ever pivots toward a power-user keyboard-driven Linear-clone positioning. Neither is the next step from where the codebase currently sits.

**Operative consequences if B is chosen:**
- Keep the orb family but **simplify** — replace the Three.js `<VioletOrb>` with the 8 px ambient pulse-dot shown in B's mockup; drop `<ShaderBg>`; keep `<SpecularButton>` only on `.qm-btn-primary` (one shine, not three).
- Add `.qm-card-soft` (larger radius, glass, hover lift) as a sibling to `.qm-glass.hover`.
- Add a `.qm-pill-soft` family that uses gradient-rendered status pills (already exists for `.qm-status-*` — direction B uses that family verbatim).
- Author `.qm-prose` for the SOAP body type — Source Serif 4 15.5 px line-height 1.7.
- Keep all other `.qm-*` classes byte-for-byte; B is additive.

---

## 4. What the user should review

Open all three HTML files in a browser side-by-side (or in three browser tabs) at ~1600 px width and check:

1. **Stat strip emotional read.** Look at the four "12 visits this week / 7 min avg drafted / 3 awaiting review / 94% signed <24h" stats in each direction. Which one would you feel comfortable showing a hospital risk-management committee? Which one would you feel comfortable showing a partner physician at lunch? Different answers are fine — they tell us what we're optimizing for.

2. **The visit-detail header — patient name + status pill.** This is the single most-seen surface element in the app. In A it's 18 px sans + flat outline pill. In B it's 32 px serif + gradient pill. In C it's 14 px sans + flat mono pill. **Which one feels right when the patient name is "John Smith" and which one feels right when it's "Eleanor Nakamura, age 76, awaiting review"?** That's the test.

3. **Information that's still *visible* but not *loud*.** Each direction handles cost ($0.184), layer trace (L1–L7), pipeline metadata, and PHI-redactor status differently. A puts them in a side-rail block with mono key-value rows. B tucks them behind a single line in the eyebrow ("Drafted in 7:12 · ready for your review"). C puts them in the footer status bar plus a sidenav meta block. **Decide how much you want a working doctor to think about the pipeline.**

4. **The Rx-clear chip.** All three show a "Rx → 0 warn / clear / CLEAR" indicator on the Rx tab. Which treatment makes you confident that when the chip flips to amber/coral (Rx warning hit), the doctor will notice without us redesigning anything else? That tells you which direction's status grammar is the strongest.

5. **The "no orbs" decision.** A drops them, B replaces with an 8 px ambient pulse-dot, C drops them entirely. Look at the top-bar in each — the orb's absence (or its replacement) is a quiet decision but a load-bearing one for the brand identity. Decide whether QuillMD still wants the brand to feel "alive" through ornament, or whether the violet is enough.

After picking a direction, the lead agent will hand off to Phase 2 component-builder subagents working route-by-route per the plan in `docs/REMODEL_PHASE1_PLAN.md`.
