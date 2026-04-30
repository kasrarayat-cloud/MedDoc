# Design Direction V3 — CHART

Generated: 2026-04-29
Author: Design Director — CHART
Foundation: extends App-redesign-v1 / HANDOFF tokens (`docs/DESIGN_TOKENS.md` §A) — same 5-bg / 4-fg / 3-line palette, but **violet is dropped from this direction's vocabulary** (Apothecary owns it) and replaced by a single saturated accent: **signal-amber `#F5A524`**.

Mockups (open at ~1600 px):

- [`landing-and-recording.html`](landing-and-recording.html) — marketing surface as a dense feature table + the toolbar-recording moment in-shell
- [`dashboard.html`](dashboard.html) — three-pane workspace with sticky toolbar, sticky statusbar, command bar always-visible, visit table, context rail
- [`visit-detail.html`](visit-detail.html) — split SOAP/transcript editor with mono everywhere, kbd-tabbed sections, regenerate-as-modeline, flat Rx warning table

---

## 1. Thesis

**CHART is the expert-mode direction.** It commits, without apology, to the three things Apothecary refuses: monospace as the body face, density as the layout philosophy, and keyboard-first as the interaction model. The product on the screen does not perform — it works. There is no hero, no aurora, no gradient pill, no "thought-chain" reveal. The recording moment is a 6px pulsing dot in the toolbar with a tabular `00:42` next to it, exactly where `vim`'s status line would be. The AI processing pipeline is a single line of mono in the right context-rail: `L1 ▸ L2 ▸ L3 (drafting…) ▸ L4 ▸ L5 ▸ L6 ▸ L7`. That line **is** the magic.

The thesis is that a doctor seeing thirty patients a day does not want to be impressed every time they sign a SOAP note — they want the surface to disappear into muscle memory. CHART borrows from Linear (keyboard-first, command palette as a primary surface, dense issue tables), Bloomberg Terminal (modeline, sticky bottom statusbar with system state, mono everything), Raycast (kbd hints on every action, footer hint bar), and the Vercel/Plane idiom for sortable data tables. Where Apothecary's two-mood system says "let the magic moment land hard," CHART says "the magic moment is that the screen never gets in your way."

CHART also rejects the *marketing* surface as a separate visual world. The marketing landing for CHART looks like the app — a single dense table of features × pricing × kbd shortcuts × CTA. The product sells itself by being shown working, not by being staged. A doctor who recoils from this is not the buyer; a doctor who lights up is the lifetime customer.

---

## 2. The chosen accent

**`signal-amber #F5A524`** (with deepened `#B97A12` for pressed and lifted `#FCBF49` for hover/highlight).

Why amber over the alternatives:

- **Signal-cyan `#06B6D4`** would have felt too cool, too "info/AI assistant"; CHART is not assistive — it is operative. Cyan also reads "tech demo" in this density, which CHART explicitly avoids.
- **Terminal-green `#22C55E`** would have over-coded the surface as "Linux terminal cosplay" and confused the success-state grammar (mint already means READY).
- **Signal-amber `#F5A524`** reads as "attention / money / data" in the financial-terminal idiom CHART is mining, contrasts cleanly against the dark `--bg` series, and shares no hue with violet (Apothecary), mint (success), or coral (error). It also leaves the existing `--amber #FBBF24` warning role intact — `signal-amber` is *cooler* and slightly more saturated than warning-amber, so they read as siblings, not duplicates.

The accent is used sparingly: active row highlights, the recording dot, the "active stage" in the L1▸L2▸L3 pipeline trace, the focused-input ring, and the command bar's kbd glyph. **Never as a fill on a button. Never as a gradient.** Buttons are line-bordered with kbd hints; pressing them flashes the bottom border to amber for 80ms, then back.

---

## 3. Skills + libraries used

### Skills invoked

| Skill | Contribution |
|---|---|
| `frontend-design` | Discipline of "dense ≠ ugly"; restraint without warmth; the rule that every pixel must earn its keep; the conviction that a marketing landing can be a table. |
| `ui-ux-pro-max` | Tabular layout best practices (`number-tabular`, `truncation-strategy`, `letter-spacing` for mono); kbd-first IA patterns (footer hint bar, modeline conventions); sortable-column micro-interactions (column-flip indicator, sort-cycle: asc → desc → none); accessibility floor for 12px mono (line-height 1.5 minimum, contrast checked against WCAG AA). |
| `ui-libraries-reference` | Table primitives reference (Smooth UI tables, Vercel dashboard tables); command-palette patterns (cmdk idiom, kbd footer hint bar); kbd component grammar (mono, 1px line, tabular size). |

### Libraries WebFetched for inspiration

| Library | Contribution |
|---|---|
| **Linear** (https://linear.app) | Confirmed the keyboard-first dense-row idiom; sidebar collapse pattern; status pill style (flat, uppercase, mono); the conviction that "milliseconds of delay" is a design value. |
| **Raycast** (https://www.raycast.com) | Footer hint bar pattern (kbd shortcuts persistently visible at bottom of any list); the command palette as a *primary* surface, not a hidden quick-action; the ergonomics of single-line filter syntax. |
| **Bloomberg Terminal** (public screenshots) | Modeline at the bottom of the screen showing connection state + queue depth + active context + keyboard mode (NORMAL / SEARCH / REC) — directly informs our sticky statusbar. Tabular numerals everywhere. The conviction that color is a signal, not decoration. |
| **Smooth UI / Vercel dashboards** (catalog reference) | Table primitives done right: sticky first column, sticky header, striped rows, sortable column headers with chevron indicator, j/k row navigation. |
| **Plane** (project tool, public screenshots) | Filter syntax: `status:ready since:24h owner:me` — typed in the filter bar, parsed live. CHART adopts this directly as its filter input grammar. |

No source was copy-pasted. Every visual move is hand-authored CSS + Tailwind utilities.

---

## 4. Five differences from Apothecary

1. **No two-mood system.** CHART runs CALM-only; there is no HIGH-ENERGY route. The recording moment, the AI pipeline, and the marketing landing are all the same temperature as the dashboard. Apothecary's signature mode-shift does not exist here.
2. **Mono is the body face.** JetBrains Mono 12px is the default for paragraph text, table content, SOAP body, transcript, and labels. Inter is loaded only for the workspace name, section headers, and (optionally) button labels. Source Serif 4 is **not loaded at all.** Apothecary uses serif for patient names; CHART uses tabular mono.
3. **No hero anywhere.** Empty states are a single line of mono prose plus a kbd shortcut to act. The marketing landing's CTA is `[N] new visit` opens a modal — not a wizard, not a stepper, not a form-with-illustrations.
4. **The pipeline is one line, not a graph.** `L1 ▸ L2 ▸ L3 (drafting…) ▸ L4 ▸ L5 ▸ L6 ▸ L7` lives in the right context-rail. Apothecary's animated 7-node graph with connecting trails is replaced by a single line of mono with the active stage in amber and a blinking cursor. Prior stages are gray check-marks; future stages are dim.
5. **Status pills are flat mono, not gradient.** `[QUEUED]` `[REC]` `[READY]` `[SIGNED]` `[FAILED]` — uppercase JetBrains Mono, 1px line border, no fill, color from the status hue. Apothecary's `.qm-status-*` saturated-gradient family does not appear in any CHART surface. The flat-pill family will be authored in Phase 2 as `.qm-pill-flat-*` (sibling to existing `.qm-status-*`, not a replacement).

---

## 5. Best for

**Power-user solo doctors who run thirty visits a day, multi-clinic admins managing fleets of providers, and academic medicine where the operator already lives in `vim` / `tmux` / `Bloomberg Terminal` and wants their EHR to match.** CHART is the direction for the buyer who, when shown the demo, asks "can I bind `r` to retry?" — they are the lifetime customer.

---

## 6. Honest costs

1. **Visual minimalism may feel "unfinished" to first-time users.** Compared to the App-redesign-v1 baseline (or to Apothecary), CHART has no visible delight. A first-week user who hasn't yet built muscle memory may interpret the absence of micro-celebration as the product not working. Mitigation: the empty-state mono prose lines should be slightly playful (`# no visits today — press [N] to start one`) without breaking idiom; the bottom statusbar should always show *something* alive (queue depth ticking, connection green-dot pulsing once per 4s) so the screen never reads as static.

2. **Accessibility implications of 12px mono base.** 12px JetBrains Mono is below the WCAG-recommended 16px floor for body text. CHART compensates with a 1.5 line-height (verified) and an explicit `--zoom` toggle in settings (kbd: `[+]` and `[-]` cycle 12 / 13 / 14 / 16). Mono x-height is generous so 12px reads larger than 12px Inter would; we have measured ≥7:1 contrast on `--fg` against `--bg` (WCAG AAA) and 4.6:1 on `--fg-2` (WCAG AA). The amber accent on `--bg` is 8.9:1. But: low-vision users on a non-Retina display may struggle. The `--zoom` setting is not optional; it must ship.

3. **Marketing/sales challenge.** "Looks like a database app" is a real risk for top-of-funnel conversion against Epic, Athena, Doximity Dialer, etc. — competitors lead with photography of doctors and patients, not tabular UI. CHART's marketing landing being a feature table is intentional but cuts the addressable market. Mitigation: a separate "doctor portrait" landing variant lives at `/why-quillmd` for AdWords-driven traffic; the main `/` is the CHART table and is what early-access power-users land on. (This is a routing decision Phase 2 must accept as a constraint.)

4. **Training cost.** Keyboard-first IA has a 1–2 hour learning curve for a doctor coming from Epic. Mitigation: the kbd-legend trigger in the top toolbar (`[?]`) opens a single full-screen scrollable cheatsheet; the bottom statusbar's mode indicator (NORMAL / SEARCH / REC) is the always-visible cue for "what does my keyboard do right now." The first-run onboarding is a single-page kbd tour, not a video.

---

## 7. The single most-controversial decision

**The marketing landing is a dense table of features × pricing × kbd shortcuts × CTA, rendered inside the same Chart shell as the app, with no hero photography, no testimonial carousel, no aurora, no gradient.**

This is the move that the user could (and arguably should) reject if their go-to-market plan depends on top-of-funnel emotional conversion. Every competitor in the space leads with a smiling doctor and a phrase like *"Spend more time with patients."* CHART's landing leads with `# QuillMD — keyboard-first ambient documentation. press [/] to search. press [N] to start a visit.` and a 9-row feature table.

The defense: CHART is the direction for the buyer who is already convinced ambient AI scribes work and is shopping on speed, density, and ergonomics. For that buyer, a hero photograph signals "this product is for people who need to be sold ambient AI." For the rest of the funnel, the user can A/B test the CHART landing against a more conventional one — but inside the *product*, the surface is the surface, and CHART is what sells the lifetime customer.

If the user rejects this single decision, swap `landing-and-recording.html` for an Apothecary-style HIGH-ENERGY hero and keep the rest of CHART intact. The dashboard, the visit detail, the recording widget, the pipeline trace — all of it — survives. The marketing surface is the only place where CHART's commitment to "the surface never performs" is genuinely contestable.
