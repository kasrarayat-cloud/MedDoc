# QuillMD v4 — 10 Radical Directions

Generated: 2026-04-29
Each file is self-contained. Open any one in a browser at ~1600 px wide. Both landing/recording AND dashboard are stacked vertically inside the same HTML page, so one open = full identity.

No comparison table. No recommendation. The directions are themselves the argument.

---

01 · **SPATIAL** — *the room your patients live in*
The dashboard is not a webpage, it's a Three.js scene with depth-of-field, parallax, and a vertex-displaced recording sphere that breathes.
→ [`spatial.html`](spatial.html) (1,597 lines)

02 · **BRUTALIST** — *the grid is the gentleness*
1960s Swiss + neo-brutalist web. Helvetica, hard 12-column grid, construction yellow, 2 px black rules, zero rounded corners, zero gradients, white-on-black inversion blocks.
→ [`brutalist.html`](brutalist.html) (957 lines)

03 · **ANALOG** — *the chart is paper*
Cream paper background with SVG noise grain, Lora serif body, hand-drawn icons with sub-degree jitter, sticky-tab patient files, page-turn 3D animation as the AI magic moment.
→ [`analog.html`](analog.html) (1,607 lines)

04 · **ARCADE** — *the doctor is the player*
Saturated game-UI HUD. XP bars, achievement badges, level system, recording-as-boss-fight with HP bar and ability buttons, SOAP-as-epic-loot-drop, level-up flash toasts.
→ [`arcade.html`](arcade.html) (1,672 lines)

05 · **TERMINAL** — *the doctor is the operator*
Pure black, phosphor green, 100 % monospace, scanlines, chromatic aberration, ASCII dividers, blinking cursors. Dashboard is a vim session. Visit detail is a `man(1)` page. AI pipeline is `[L1] transcribe ... ok`.
→ [`terminal.html`](terminal.html) (1,604 lines)

06 · **EDITORIAL** — *a patient's note is a story*
NYT/Atlantic newsroom — 144 px serif masthead, 88 px headlines, drop caps on every patient name, 3-column newspaper grid, red kicker labels, photographic blocks, recording-as-live-blog.
→ [`editorial.html`](editorial.html) (1,825 lines)

07 · **NEUMORPHIC** — *the surface is sculpted from canvas*
Soft 3D extruded UI, dual-shadow cards, pastel lavender canvas, pressable buttons with three states, glass-blur transcript pane, breathing recording orb with halo, regenerate ripple as the AI moment.
→ [`neumorphic.html`](neumorphic.html) (1,737 lines)

08 · **MAGAZINE** — *the clinic is a feature*
Wallpaper*/Apartamento print aesthetic. Asymmetric 6-column grid, Bodoni Moda + Cormorant marginalia, 11 photographic blocks, masthead chrome (Vol I · Issue 47), classified-ad patient list, burnt-orange single accent.
→ [`magazine.html`](magazine.html) (1,756 lines)

09 · **CYBERPUNK** — *the doctor is a netrunner*
Maximalist neon Tokyo. Pink + cyan + plasma green + amber holographic gradients, glitch text on load, scanlines, screen-flicker, full-stage Blade Runner spinner unit for recording, ICD codes as subject classifications.
→ [`cyberpunk.html`](cyberpunk.html) (2,464 lines)

10 · **MINIMALIST** — *the magic is the absence of magic*
Wabi-sabi MUJI silence. Off-white canvas with warm bias, 11 px chrome / 14 px body / 24-32 px content, ONE single muted-rust hairline accent, opacity-only motion, recording is one 8 px dot.
→ [`minimalist.html`](minimalist.html) (738 lines)

---

## How to view

```bash
# open all 10 in order
for f in spatial brutalist analog arcade terminal editorial neumorphic magazine cyberpunk minimalist; do
  xdg-open /opt/meddoc-pro/docs/design-directions-v4/$f.html
done
```

Or pick the 3 that intrigue you most from the descriptions, open those, and move from there.

## What's around

| Folder | What |
|---|---|
| `docs/design-directions/` | v1 — A/B/C — rejected as too tame |
| `docs/design-directions-v2/` | v2 — Apothecary — kept as baseline |
| `docs/design-directions-v3/` | v3 — Atelier/Prism/Chart/Clinician/Nocturne — rejected as derivative |
| `docs/design-directions-v4/` | **v4 — these 10 — radical, non-medical-SaaS reference universes** |

Each prior round is preserved untouched. Working tree is `?? docs/...` only — no source code modified.

## What happens next

Tell us which one or two land. We'll either:
- pick one and start Phase 2
- pick two and propose a hybrid
- iterate on a specific direction
- launch v5 with a different brief

Implementation does not start until you choose. Boring = fail. Tame = fail. The 10 above are deliberately not the same kind of object — three of them (Brutalist, Terminal, Cyberpunk) are aesthetics that 99 % of medical-SaaS would never ship and that's the point.
