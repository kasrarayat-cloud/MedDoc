# QuillMD Phase 1 Design Directions — Holistic Comparison

Generated: 2026-04-29
Author: lead agent (after 5 parallel Design Director subagents finished)

This file compares all **6 directions** the user has to choose from:

- **Apothecary** (baseline, kept by user — see `docs/design-directions-v2/`)
- **Atelier** (new) — editorial luxury
- **Prism** (new) — vivid AI-native
- **Chart** (new) — Bloomberg / Linear power-user
- **Clinician** (new) — humane medical
- **Nocturne** (new) — moody dark cinematic

Every direction respects the same protected backend zone (`docs/PROTECTED_CONTRACTS.md`) and builds on the App-redesign-v1 foundation tokens unless the README explicitly notes a parallel palette. No direction touches API routes, server actions, hooks, the worker, the AI pipeline, the Prisma schema, auth, or the Rx warning logic.

---

## 1. The grand comparison table

| Direction | Identity in 6 words | Energy stance | Color family | Patient-name typeface | Recording-moment treatment | AI-processing treatment | Best for |
|---|---|---|---|---|---|---|---|
| **Apothecary** | Two-mood — calm app, magic moments | HIGH for landing/recording/processing/success/empty + CALM for daily-driver | Dark violet base + copper warm + aqua cool tri-tone | Source Serif 4 | Aurora mesh + spotlight + border-beam + gradient orb + magnetic CTA | Animated 7-layer pipeline with pulsing nodes, beams, particle trails + thought-chain text | Solo physicians who want craft + a "magic moment" that justifies the price |
| **Atelier** | Editorial luxury — restraint as wealth | Single-mode CALM (no HIGH zones) | Warm-cream-to-graphite ramp + oxblood `#7B1F2D` | Source Serif 4 | Typographic — serif "Now recording" + 6 px oxblood pulsing dot + thin underline progress | One italic serif line crossfading "Reviewing transcript… identifying speakers… drafting subjective…" 2.4 s | Boutique / concierge practices, clinicians who read The New Yorker, "thinking person's medical software" |
| **Prism** | AI-native — gradients earn every surface | HIGH zones LOUDER than Apothecary; calm zones KEEP gradient accents | Cosmic tri-tone — magenta `#D946EF` → electric violet `#7C3AED` → electric cyan `#22D3EE` | Inter Tight (sans, 14 px) | CSS-only gradient-mesh orb + conic-gradient border-beam + 3 offset pulse rings + magnetic CTA | 5-node animated SVG dasharray beam with particle trails + breathing gradient mesh — same showpiece on landing AND inline above SOAP | Modern solo doctors who want to feel cutting-edge; AI-product-conscious users who pay for "feels like the future" |
| **Chart** | Linear-for-medicine — keyboard-first, dense, fast | CALM-only (no HIGH zones at all) | Dark base + signal-amber `#F5A524` accent | JetBrains Mono (entire body — 12-13 px) | 6 px pulsing amber dot + `REC 00:42` tabular mono + 5-bar VU meter, all in toolbar | One mono line in right rail: `✓L1 ▸ ✓L2 ▸ ✓L3 ▸ L4 (drafting)▌ ▸ L5 ▸ L6 ▸ L7` with blinking cursor | Power-user solo doctors, multi-clinic admins, academic medicine, command-palette devotees |
| **Clinician** | Humane medical — light, sage, kind | Single-mode CALM, **light-mode-first** | Sage `#7AA68C` + teal `#5BA3B4` on cream `#FAF7F2` with warm-charcoal ink | Source Serif 4 at 19 px ("Mrs. Elena Lopez") | Slow halo pulse + warm initials chip + serif "Recording with Mrs. Lopez" + italic-serif aside ("Listening. You can speak as you would in any other visit.") | Single italic-serif sentence crossfading every 1.6 s — "Drafting…" "Polishing…" — no pipeline | Older clinicians, wellness-leaning practices, pediatricians, family medicine, anyone tired of clinical-blue |
| **Nocturne** | Cinematic noir — borders, grain, single-accent | HIGH for recording (cinematic) + CALM for daily-driver (still has grain overlay) | Deep blue-black `#0A0E1A` + electric-blue `#3B82F6` only | Source Serif 4 italic display ("Maria *Lopez*") | Conic-gradient border-beam + spotlight cone + dim-elsewhere mask + 5%-opacity drifting film-grain | Single-line typewriter cursor — types and replaces stages in place, the cursor IS the visualization | Design-conscious solo doctors, late-night chart catch-up, Arc-browser / Logic-Pro users |

---

## 2. Energy-stance map (which directions agree on which moments?)

| Moment | Apothecary | Atelier | Prism | Chart | Clinician | Nocturne |
|---|---|---|---|---|---|---|
| Landing / marketing | HIGH | CALM | **LOUDER** | CALM (no hero — feature table) | CALM | HIGH-cinematic |
| Login / signup | HIGH | CALM | HIGH | CALM | CALM | HIGH-cinematic |
| Recording active | HIGH | CALM-typographic | LOUD | CALM-toolbar | CALM-warm | HIGH-cinematic |
| AI processing | HIGH (showpiece) | CALM (italic line) | LOUD (showpiece) | CALM (mono trace) | CALM (italic line) | CALM-cinematic (typewriter) |
| Success state | HIGH (sweep + check-mark) | CALM (small-caps mono) | LOUD (gradient sweep) | CALM (statusbar update) | CALM (warm card) | CALM-cinematic (typewriter reveal) |
| Empty state | HIGH (gradient mesh + CTA) | CALM (paragraph + CTA) | LOUD (mesh + gradient CTA) | CALM (mono + kbd) | CALM (warm illustration) | CALM (italic + dot + grain) |
| Dashboard | CALM | CALM | calm WITH gradient accents | CALM (3-pane dense) | CALM (warm cards) | CALM (with grain) |
| Visit list | CALM | CALM (editorial table) | calm WITH gradient pills | CALM (sortable mono table) | CALM (76 px-tall list rows) | CALM (1px borders + active accent edge) |
| Visit detail (SOAP edit) | CALM | CALM (article-as-form, 680px max-width) | calm WITH gradient bullets | CALM (mono editor) | CALM (serif body 1.7 lh) | CALM (serif body 1.65 lh + grain) |
| Settings / admin | CALM | CALM | calm WITH gradients | CALM | CALM | CALM |

**Reading the map**: Apothecary and Prism agree that the AI-processing moment should be a showpiece. Atelier, Chart, Clinician, and Nocturne all reject the showpiece — but for very different reasons (Atelier: restraint / Chart: density / Clinician: kindness / Nocturne: cinematic stillness). Prism is the only direction that puts gradient accents into calm zones.

---

## 3. Color-family map

| Direction | Base | Primary accent | Secondary accent | Tertiary accent |
|---|---|---|---|---|
| Apothecary | dark `#07060C` (violet-tinted) | violet `#8B5CFF` | copper warm | aqua cool |
| Atelier | warm cream / warm graphite ramp | oxblood `#7B1F2D` | (none) | (none — monochrome + 1) |
| Prism | dark | magenta `#D946EF` | electric violet `#7C3AED` | electric cyan `#22D3EE` |
| Chart | dark | signal-amber `#F5A524` | (none) | (none — single accent) |
| Clinician | cream `#FAF7F2` (light-mode-first) | sage `#7AA68C` | teal `#5BA3B4` | (warm amber for accents) |
| Nocturne | deep blue-black `#0A0E1A` | electric-blue `#3B82F6` | (none) | (none — single accent) |

Three "single accent" directions (Atelier, Chart, Nocturne) and three "multi-accent" (Apothecary, Prism, Clinician) — different bets on how many colors a clinician should hold in their head.

---

## 4. Typography stance

| Direction | Body face | Display / headlines | Mono use |
|---|---|---|---|
| Apothecary | Inter Tight 14 px | Source Serif 4 italic for hero + qm-warn-headline | JetBrains Mono — meta, kbd, transcript IDs |
| Atelier | **Source Serif 4 17.5 px / 1.7 lh — body itself is serif** | Source Serif 4 large display | Mono small-caps for ALL labels + status pills |
| Prism | Inter Tight 14–15 px | Source Serif 4 italic for hero verbs (gradient-clipped) | Mono for transcript timestamps |
| Chart | **JetBrains Mono 12–13 px — entire body is mono** | Inter Tight only on logo + button labels | base font IS mono |
| Clinician | **Source Serif 4 16 px / 1.7 lh — body itself is serif** | Source Serif 4 19–40 px | JetBrains Mono only for IDs (MRN-77324) |
| Nocturne | Source Serif 4 16 px / 1.65 lh | Source Serif 4 italic display ("Maria *Lopez*") | Mono for meta + the typewriter cursor |

> Notice: **Atelier, Clinician, and Nocturne all commit to serif as the BODY face** (not just the headline). Apothecary, Prism, and Chart treat serif as accent or skip it entirely. This is the single biggest typographic philosophy split.

---

## 5. The "magic moment" map (AI processing — the price-tag justifier)

| Direction | What plays when AI is working | Vocabulary |
|---|---|---|
| **Apothecary** | Pipeline diagram with 7 nodes, beams, particles, breathing mesh; thought-chain text | "Look at the AI." Festive. |
| **Atelier** | Single italic serif line, opacity-only crossfade, no other motion | "We're working." Restrained. |
| **Prism** | 5-node SVG-dasharray beam with particle trails + breathing gradient mesh | "AI is the protagonist." LOUD. |
| **Chart** | One mono line in right rail: `L1 ▸ L2 ▸ L3 (drafting)▌ ▸ L4 ▸ L5 ▸ L6 ▸ L7` | "Status visible, no theater." |
| **Clinician** | One italic serif sentence crossfading every 1.6 s — "Drafting…" "Polishing…" | "A patient assistant." Warm. |
| **Nocturne** | One typewriter cursor types and REPLACES the stage line in place | "Cinematic stillness." |

The AI-moment vocabulary is the cleanest way to differentiate the 6 directions. If you had to pick one, ask: **what should a doctor feel during the 12-second wait for a SOAP draft?**

- Apothecary: amazement
- Atelier: faith
- Prism: thrill
- Chart: nothing — they're already on the next visit
- Clinician: comfort
- Nocturne: contemplation

---

## 6. Per-direction "single most controversial decision" (each subagent flagged one — overridable in 1 line of CSS)

| Direction | The bet | What you can flip if you reject it |
|---|---|---|
| Apothecary | Dashboard table uses **serif** for patient names | `.pname { font-family: var(--sans); }` |
| Atelier | **Status pills are never colored** — `READY` `SIGNED` look identical (1 px border, mono small caps); only critical/in-review get a 4 px oxblood dot | Add per-status accent dots |
| Prism | Dashboard status pills are **gradient, not flat** — Prism collapses to "Apothecary with magenta" if pills go flat | One CSS swap to outline pills (kills the thesis) |
| Chart | Marketing landing is a **dense feature × pricing × kbd-shortcut TABLE** inside the same Chart shell — no hero, no photography | Swap `landing-and-recording.html` for an Apothecary-style hero |
| Clinician | Body copy (including the SOAP note itself) is **Source Serif 4 16 px** — most "professional" SaaS treats serif as marketing-only flourish | Swap `--body-font` to sans for the editor only |
| Nocturne | **Status pills are flat desaturated mono — no green anywhere.** A `READY` chip is `[READY]` in cool gray, no fill | Add saturation back to status colors |

---

## 7. Lead-agent observations

### 7.1 Three of these can stack into one product

The 6 directions aren't mutually exclusive in every dimension. A practical product might pick:
- Apothecary's two-mood philosophy
- Clinician's warm light-mode for the day-time dashboard
- Nocturne's grain + cinematic recording widget for the night-time chart catch-up
- Atelier's status-pill restraint
- Chart's command bar + kbd-first IA for power users
- Prism's animated AI pipeline as a togglable easter egg in the regenerate flow

But that hybrid is not what you should pick at this stage. Pick **one direction's North Star** and let Phase 2 build it. The hybrids can come later.

### 7.2 Three directions reject HIGH zones entirely

Atelier, Chart, and Clinician all run **CALM-only**. Apothecary, Prism, and Nocturne run **two-mood**. This is the highest-level fork:
- "Earn the price tag with a magic moment" (Apothecary / Prism / Nocturne) → user feels the AI working
- "Earn the price tag by getting out of the way" (Atelier / Chart / Clinician) → user trusts the AI is working

Both are valid. Both have shipped million-dollar products.

### 7.3 The dashboard is the test

You'll spend 8 hours/day on `dashboard.html`. Open all 6 in browser tabs, scan them in random order, and notice which one your eye returns to. That's the calm-zone winner. Then check whether the same direction's `landing-and-recording.html` matches the energy you want for new-user first impressions. If the same direction wins both, pick it.

If the calm-zone winner and the energy winner are different directions, you have a real fork — and either (a) the two-mood directions (Apothecary / Prism / Nocturne) are doing the right thing because they SHIP both, or (b) you need a sixth/seventh direction we haven't generated.

### 7.4 The Rx warning card is the constraint

Every direction had to integrate the existing `<RxWarningCard>` (518 LOC, severity-themed, with its own design spec at `docs/design/rx_warning_handoff/`). Apothecary keeps it as-is. Atelier and Nocturne explicitly **tone down the gradient pills** to fit. Chart **rewrites** the card into a flat mono `key: value` table. Prism keeps it gradient. Clinician softens the pills.

If keeping the existing Rx warning visual untouched is important (it has tests, a design spec, and a Vitest assertion suite), Apothecary > Prism > Clinician > Nocturne > Atelier > Chart in order of integration cost.

### 7.5 The "tired pediatrician at 5 PM" test

Clinician explicitly named this test. But you can run it on every direction:

| Direction | Tired-pediatrician verdict |
|---|---|
| Apothecary | "Beautiful, but my eyes hurt by 4 PM" |
| Atelier | "Calming, but feels insufficiently AI for what I'm paying" |
| Prism | "Awesome, but my retinas are buzzing" |
| Chart | "I'm fast, but I miss something pretty" |
| Clinician | "I want to make tea while using this" ← passes |
| Nocturne | "Cinematic. I'm noticing the design instead of doing my job" |

This is the test Clinician was built for; it is the right test. It is not the only test.

---

## 8. What I haven't generated (and could, if you want)

If none of the 6 land cleanly, candidate directions for a v4 round include:
- **MEDICAL-ENTERPRISE** — Epic-styled, blue + grey, conservative, sells to hospital procurement. Was implicitly in old A but with more conviction.
- **PRACTITIONER-FRIEND** — Clinician + Apothecary hybrid. Light dashboard + dark recording widget. Different "modes" by time of day.
- **PHYSICAL-INSTRUMENT** — skeuomorphic medical instrument (a stethoscope, a chart pad). Bold bet that physicality grounds the AI.
- **CONVERSATION-FIRST** — the visit IS a chat thread. Doctor + patient + AI as three-way conversation surface. Reframes the whole IA.

None of these are necessary if one of the 6 above resonates. Listed in case the constraint is the brief, not the execution.

---

## 9. How to evaluate (for the user)

1. Open all **24 HTML files** in browser tabs (6 directions × 3+ files each, plus the 3 from `docs/design-directions/` if you want to compare with the original v1 too — though those were rejected).
2. Look at all 6 dashboards first, in random order — pick the one your eye returns to.
3. Look at all 6 landing/recording pages — pick the one that sells the product to a new doctor.
4. If the same direction wins both, pick it. Phase 2 starts on that direction.
5. If two different directions win — tell us which won which. The two-mood directions (Apothecary / Prism / Nocturne) might be doing the right thing precisely because they ship both. Or you might want a hybrid.
6. Tell us which controversial decisions (table in §6) you'd flip. Each direction has ONE override that doesn't kill the thesis.
7. Confirm scope: still `apps/transcribe-md` only for Phase 2? Marketing + meddoc-pro stay separate?

---

## Appendix — file paths

```
docs/design-directions-v2/                       # Apothecary baseline (untouched)
├── README.md
├── landing-and-recording.html
├── dashboard.html
└── visit-detail-with-magic.html

docs/design-directions-v3/
├── COMPARISON.md                                # this file
├── atelier/
│   ├── README.md
│   ├── landing-and-recording.html               # 768 lines
│   ├── dashboard.html                           # 745 lines
│   └── visit-detail.html                        # 910 lines
├── prism/
│   ├── README.md
│   ├── landing-and-recording.html               # 1,221 lines
│   ├── dashboard.html                           # 1,197 lines
│   └── visit-detail.html                        # 1,150 lines
├── chart/
│   ├── README.md
│   ├── landing-and-recording.html               # 1,730 lines
│   ├── dashboard.html                           # 1,370 lines
│   └── visit-detail.html                        # 1,352 lines
├── clinician/
│   ├── README.md
│   ├── landing-and-recording.html               # 987 lines
│   ├── dashboard.html                           # 939 lines
│   └── visit-detail.html                        # 942 lines
└── nocturne/
    ├── README.md
    ├── landing-and-recording.html               # 1,102 lines
    ├── dashboard.html                           # 1,211 lines
    └── visit-detail.html                        # 1,287 lines
```

Total: 22 deliverable files (6 READMEs + 18 HTML mockups + this comparison + the v2 baseline). Working tree on `main` still untracked-only — no source code modified.
