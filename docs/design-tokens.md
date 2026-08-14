# Design tokens — "Rounds"

**This document is the authority.** Where a component and this file disagree,
this file is right and the component is a bug. Where this file and a rendered
screenshot disagree, this file is still right — screenshots go stale.

Rounds is the merge of two directions: **Ward Board** (the dark stage, the
patient-lane × stage-column matrix, position-awareness, blocker language) and
**Focus Flow** (the spotlit sheet, the sequential gates, the deep paper shadow).
Neither shipped alone. Where they conflicted, the resolution is recorded here
rather than left to whoever reads the CSS next.

---

## The one idea

**The stage is dark. The paper is not.**

Everything that is *software* — navigation, queue, gates, chrome — sits on a dark
stage. Everything that is *the clinical document* sits on paper: near-white, warm,
serif, shadowed, and read-only. A doctor should be able to tell at a glance
whether they are looking at the app or at the note, without reading a word.

That split is why there are two colour families below instead of one, and why the
paper family is not simply "the light theme".

---

## Colour

### Stage (the application)

| Token | Value | Use |
|---|---|---|
| `--rounds-stage-bg-1` | `#232B3A` | radial gradient inner |
| `--rounds-stage-bg-2` | `#171D27` | radial gradient mid |
| `--rounds-stage-bg-3` | `#12161E` | radial gradient outer |
| `--rounds-surface-1` | `#161B24` | recessed / lowest |
| `--rounds-surface-2` | `#1E2530` | default card |
| `--rounds-surface-3` | `#252D3A` | raised / hover |
| `--rounds-line-1` | `#2C3442` | hairline, default |
| `--rounds-line-2` | `#3A4353` | emphasised border |
| `--rounds-text-1` | `#E7EBF1` | primary on stage |
| `--rounds-text-2` | `#98A2B1` | secondary |
| `--rounds-text-3` | `#7C8694` | tertiary / kickers |

The stage background is a **radial** gradient, not linear: the lightest point sits
behind the content the clinician is meant to be looking at, which is what makes
the sheet in Screen 2 read as spotlit rather than merely pasted on.

### Paper (the clinical document)

| Token | Value | Use |
|---|---|---|
| `--rounds-paper-1` | `#FCFCFA` | the sheet |
| `--rounds-paper-2` | `#F3F4EF` | inset / alternating |
| `--rounds-paper-3` | `#ECEDE7` | wells, quiet blocks |
| `--rounds-ink` | `#191E26` | clinical prose |
| `--rounds-ink-muted` | `#525A66` | labels, meta on paper |
| `--rounds-paper-line-1` | `#E7E8E3` | hairline rules |
| `--rounds-paper-line-2` | `#D8DAD3` | section dividers |

Warm off-white, never `#FFFFFF`. Pure white next to a dark stage glares, and the
document is the thing a clinician stares at longest.

### Accent

| Token | Value | Use |
|---|---|---|
| `--rounds-accent` | `#5B5BD6` | primary actions, focus rings |
| `--rounds-accent-hover` | `#4A49C4` | hover / active |
| `--rounds-accent-tint-10` | `rgba(91,91,214,.10)` | selected row wash |
| `--rounds-accent-tint-16` | `rgba(91,91,214,.16)` | stronger wash |

### Status

| Token | Value | Meaning |
|---|---|---|
| `--rounds-critical` | `#C93A2E` | critical Rx, failure — borders, glyphs, fills |
| `--rounds-critical-on-dark` | `#FF8D7E` | critical red as **small text on a dark surface** |
| `--rounds-ready` | `#187A4E` | ready to review; completed track runs |
| `--rounds-em` | `#C4841C` | E/M amber |
| `--rounds-em-fill` | `#E29A34` | **E/M action buttons only** |
| `--rounds-processing` | `#3B6FD4` | in pipeline — **fill/line only** |
| `--rounds-processing-text` | `#7AB0F5` | the processing blue as **text on dark** |
| `--rounds-em-text` | `#E8B168` | the E/M amber as **text on dark** |
| `--rounds-ready-text` | `#6EE7A8` | the ready green as **text on dark** |
| `--rounds-accent-text` | `#A5A5F0` | the accent as **text on dark** |
| `--rounds-signed` | `#6B7480` | signed accents — **not small text on dark** |
| `--rounds-signed-text` | `#9AA4B2` | the signed grey as **text on dark** |

⚠️ **`--rounds-signed` is grey on the stage, but a completed track run draws in
`--rounds-ready` green.** Those are not the same thing and the difference is
deliberate: the *card* is finished business and recedes; the *line* is a
successful journey and should read as such at a glance across the board.

⚠️ **Critical has two tokens, for the same reason E/M does.** `#C93A2E` is a
border and fill colour; as small text on `--rounds-surface-2` it fails AA, which
axe caught on the board's REC kicker. Borders and glyphs keep the true red; text
on dark uses `--rounds-critical-on-dark`.

⚠️ **E/M has two tokens.** `--rounds-em` is the status colour; `--rounds-em-fill`
is lighter and exists only so an amber button clears AA against dark text. Do not
fill a button with `--rounds-em`.

### THE RULE THE PAIRS ARE INSTANCES OF

> **If a token names a STATE or a FILL, it needs a `-text` sibling before it is
> used as a foreground.**

This has now been learned **six times** in this palette — `--rounds-em`,
`--rounds-accent`, `--rounds-signed`, `--rounds-ready`, `--rounds-processing`
and the E/M amber again — so it is written here as a rule rather than as six
separate warnings.

Measured against the two backdrops C1 surfaces sit on (`--rounds-surface-1`
`#161B24`, `--rounds-stage-bg-2` `#171D27`), against the 4.5:1 small-text bar:

| Fill token | as text | `-text` sibling | as text |
|---|---|---|---|
| `--rounds-accent` | 3.22 / 3.15 ✗ | `--rounds-accent-text` | 6.10+ ✓ |
| `--rounds-processing` | 3.63 / 3.55 ✗ | `--rounds-processing-text` | 7.69 / 7.54 ✓ |
| `--rounds-critical` | 2.72 ✗ | `--rounds-critical-on-dark` | 6.18+ ✓ |
| `--rounds-ready` | 2.60 ✗ | `--rounds-ready-text` | 9.02+ ✓ |
| `--rounds-signed` | 2.93 ✗ | `--rounds-signed-text` | 5.50+ ✓ |
| `--rounds-em` | 5.48 / 5.37 **✓** | `--rounds-em-text` | 8.98 / 8.80 ✓ |

⚠️ **`--rounds-em` is the interesting row, and the reason this is a table rather
than a sentence.** It *passes* on those two backdrops and on `--rounds-surface-2`
(4.89) — and fails on `--rounds-surface-3` at **4.40**, a tenth under the bar.
A near miss reads exactly like a pass to anyone eyeballing it. A text token has
to be safe wherever it lands, not merely where it is used today.

`gate-rounds-bridge.test.ts` computes these ratios rather than trusting this
table, so the table cannot drift from the values without the suite noticing.

---

## Type

| Family | Token | Use |
|---|---|---|
| Bricolage Grotesque | `--rounds-font-display` | display, page titles, big numerals |
| Figtree | `--rounds-font-ui` | all UI text |
| Source Serif 4 | `--rounds-font-clinical` | **ALL clinical prose** |
| JetBrains Mono | `--rounds-font-mono` | labels, MRNs, codes, drug-pair lines |

**Source Serif 4 covers every piece of clinical prose, including the default
QuillMD paper template.** Not just quotes, not just the note body — if a clinician
would read it as part of the record, it is serif. Clinical prose is read
differently from interface text, and the typeface is the cue.

Clinical body: **15–16.5px / 1.7**. Wide for a UI, correct for prose.

**Mono is for things that are looked up, not read**: an MRN, a CPT code, a drug
pair, a section kicker. If a human scans it character by character, it is mono.

---

## Shape and depth

- Radii **9–18px**. Small controls at the bottom of the range, paper cards at the top.
- Paper cards carry the **deep two-layer Focus Flow shadow** — a tight contact
  shadow plus a wide soft one. One layer looks flat against a radial stage; two
  is what sells the sheet as lifted.

---

## Non-negotiables

These are not style choices and a redesign does not get to overrule them.

- **WCAG AA for all text.** Including amber on dark, which is why
  `--rounds-em-fill` exists.
- **`prefers-reduced-motion` honoured everywhere.** The board's pulsing REC
  kicker and the deck-advance transition both have still fallbacks.
- **Visible keyboard focus on every interactive element.** The accent ring, never
  `outline: none` without a replacement.
- **The paper is read-only.** No edit affordance renders on the document at any
  breakpoint. The chat editor is the only edit path. This is an architecture
  invariant, not a visual one — see AGENTS.md.

---

## The host bridge — how C1 reaches surfaces that have no classes

The C1 surfaces (auth, settings, templates, error/empty/loading) do not use
classes. They style themselves with **434 inline `style={{}}` objects across 43
files**, reading `var(--color-linear-*)` — the old skin's token names.

Forking all of them would be a 400-object diff no review could hold. So instead:

```css
[data-skin='rounds'] .qm-rounds-host {
  --color-linear-text: var(--rounds-text-1);
  /* …22 names in total… */
}
```

Custom properties inherit and resolve at **computed-value time**, so redeclaring
the old names on an ancestor retints every inline object beneath it without
touching a line of TSX. **60% of those objects come to Rounds tokens for free**;
only ~33 carry a colour literal and need a real fork.

**Three rules, each of which has a guard:**

1. **SCOPED to `.qm-rounds-host`, never `:root`.** A root-level redeclaration
   repaints `/visits`, `/patients`, `/admin` and the board — a *replacement* of
   the old skin rather than an addition, while the relay's standing rule is that
   the old skin stays default until item F. Each split applies the host class to
   the surface it restyles.

2. **Every right-hand token must be DECLARED.** An undeclared one is not a build
   error and not a console error: the declaration is invalid-at-computed-value-
   time, the property becomes unset, and the affected CSS property falls to its
   **initial value** — `background-color: transparent`, showing the stage through
   the surface. The C1 plan shipped exactly this on paper by naming
   `--rounds-surface-0`, which does not exist; it was caught by reproducing it in
   headless chromium.

3. **A name used as a FOREGROUND maps to a `-text` token.** See the rule above.
   Where a name is used as *both* (e.g. `--color-linear-sage`: 4 foregrounds, 7
   fills), the bridge follows the majority and the minority sites are forked by
   the split that owns them — tracked as named debt, not as an exemption.

**Why it wins the cascade**, stated because it looks like it should not:
`--color-linear-*` are declared inside Tailwind's `@theme {}`, which compiles to
`@layer theme { :root, :host { … } }`. `rounds-tokens.css` carries no `@layer`
and is imported after `globals.css`, so it lands **unlayered** — and unlayered
rules beat layered ones regardless of specificity.

---

## Controls

**This section did not exist until C1-d, and two records said it did.** The
relay ledger and commit `7d181ae8` both state that C1-b landed "the naming
CONTRACT" here. It did not — C1-b's 87 lines into this file were the contrast
table above and the host-bridge section; the seventeen class names it listed
never appeared anywhere but the plan. Anyone building against the promised
contract would have found nothing and invented their own. This is the contract.

⚠️ **And the sentence that stood here said "The ledger row is corrected" — in
the past tense, in the commit that did not correct it.** `46d7ee6c` touched 24
files and `docs/rounds/RELAY.md` was not among them; the false clause survived
that merge and was still on `RELAY.md:174` a day later. It is corrected now, in
`docs(rounds)` on 2026-08-01, and the fix is checkable rather than asserted:
`grep -c "17 control-primitive" docs/rounds/RELAY.md` finds the row, and the row
names this section by line. **This is rule 2c — an evidence sentence written
before the event it describes — arriving inside the very section whose subject
is a record that said something it had not done.** The cure is the same one the
rule prescribes: write it after, from the artefact, and cite something a reader
can re-run.

⚠️ **THIS TABLE HAS NO GUARD, AND THAT IS HOW IT DRIFTED.** `gate-c1d-auth`
asserts CSS ↔ TSX in both directions — every applied class has a rule, every rule
has a caller — so **the stylesheet and the product cannot disagree.** Nothing
compares either of them to *this table*, which is why `.qm-rounds-authform`
shipped with a rule (`rounds-tokens.css:1275`), a consumer
(`auth-shell.tsx:115`) and a mention in a gate's own comment while appearing in
no row here until 2026-08-01. **A contract that cannot fail is a description, not
a contract.** Deliberately not built yet: C1-e adds roughly seven primitives
(`-select`, `-field`, `-help`, `-btn-danger`, `-btn[disabled]`, `-dialog`,
`-settings`), so a guard written against today's twelve rows gets rewritten by
the split that first needs it — the same reasoning that kept the classes
themselves from landing ahead of their consumers. **It lands with C1-e**, and it
must derive the applied set by traversal (never a maintained array — see the
`globstar` miss and the convention-file miss) and carry a non-vacuity assertion
on the row count, so a parser that matches nothing reddens instead of passing.

**The rule that governs the whole layer:** a class lands **with its consumer**,
never ahead of one. C1-b deliberately shipped none of these for that reason — a
class nothing renders cannot be proven by rule 7, because nothing can be made to
fail — and `gate-c1d-auth` now enforces it in both directions: every applied
class must have a rule, and every rule must have a caller.

| Class | What it is | Notes |
|---|---|---|
| `.qm-rounds-host` | **the bridge.** Redeclares the 22 `--color-linear-*` names on a scoped class | Applied to the ROOT of a restyled surface. Colour only |
| `.qm-rounds-<surface>` | a surface marker — `-auth`, `-notfound`, `-errorstate`, `-loading`, `-tmpl` | Pairs with the host. One per screen |
| `.qm-rounds-authform` | the auth form container — a **second** ownership anchor inside `-auth` | Not decoration. Without it a violation inside the form climbs to `.qm-c3-auth-form`, matches no owned class, and files as *inherited* — reported, never gated. See "What a bridge cannot do" |
| `.qm-rounds-btn` | primary action, accent fill | Text is `--rounds-on-accent` |
| `.qm-rounds-btn-primary` | the same treatment applied **over** an old-skin `.qm-lin-btn-primary` | Fork, not replacement — item F removes the pairing |
| `.qm-rounds-btn-secondary` | outlined action | |
| `.qm-rounds-input` | text input / textarea | Carries its own `:focus-visible` |
| `.qm-rounds-label` | field label, mono smallcaps | `--rounds-text-3` |
| `.qm-rounds-error` | field-level error, `role="alert"` | `--rounds-critical-on-dark`, never `--rounds-critical` |
| `.qm-rounds-check` | native checkbox / radio | `accent-color` is the only property that retints one |
| `.qm-rounds-link` | inline link inside a text block | **Underlined** — see below |
| `.qm-rounds-panel` | a bordered block of prose | Success / submitted / refusal panels |
| `.qm-rounds-skel-*` | skeleton geometry | C1-c |
| `.qm-rounds-settings` | the settings surface marker — **and it paints the ground** | C1-e. The only surface marker that sets a `background`, because `/settings` is the first Rounds surface inside `AppFrame` and `.qm-lin-app` paints an opaque canvas *above* the host. See the note in `rounds-tokens.css` |
| `.qm-rounds-dialog` | a portalled `Dialog.Content` | C1-e. **Must be applied together with `qm-rounds-host`** — a Radix portal mounts on `<body>` and inherits no bridge |
| `.qm-rounds-dialog-overlay` | the modal scrim | C1-e. Deliberately deeper than the old `rgba(0,0,0,.55)`: the Rounds stage is lighter, so the same alpha reads weaker over it |
| `.qm-rounds-select` | native `<select>` | C1-e. Not folded into `-input` — a select draws its own indicator |
| `.qm-rounds-errorid` | the error boundary's Error-ID chip | C2. Repaints its ground to surface-2, so it lifts the faintest text tier for its own subtree — 4.17:1 → 5.97:1 |
| `.qm-rounds-setpanel` | the settings panel — heading + subtitle | C2. **Ownership anchor.** The markup is C3's; under this skin the colours are ours, so a contrast failure inside it must BLOCK rather than file as inherited |
| `.qm-rounds-setbody` | the settings panel's content column | C2. The second shield — `.qm-c3-set-content` owns everything a panel renders inside it, so the panel anchor alone does not reach it |
| `.qm-rounds-tmpl-*` | the templates surfaces — `-row`, `-card`, `-alert`, `-editor`, `-actionbar`, `-proc`, `-confirm` | C1-f. **Ownership anchors first, styling second.** Two of them (`-actionbar`, `-proc`) set no colour at all: a non-Rounds class at that node shields its whole subtree from the axe gate, and what `-actionbar` shielded was the primary CTA. The three that repaint their ground to surface-2 also re-bridge the faintest text tiers upward for their own subtree — `--rounds-text-3` is 4.68:1 on surface-1 and 4.18:1 one step lighter |
| `.qm-rounds-modetile` | the capture-mode tiles on `/visits/new` | R3.7. Applied in `visits/new/mode-tile-with-form.tsx` — a shared surface. Carries hover / pressed only; the focus ring is this file's ONE `:focus-visible` rule, not a second definition. Exists because the two states it replaces were a LITERAL `rgba(122,166,140,.45)` and `ring-linear-sage` — legacy sage written out, which the host bridge structurally cannot retint |
| `.qm-rounds-vstatus` | a visit row's status, as a **treatment rather than a chip** | R3.2. Applied in `components/dashboard/visit-list.tsx`, which renders BOTH the `/patients/[id]` history and the whole of `/visits` — so one rule clears two census surfaces. Replaces `qm-lin-pill*`; `data-status` drives the colour, and every foreground takes the `-text` sibling of its status token, never the fill |
| `.qm-rounds-vlist` | the hosted visit list's surface marker | R3.2. Sets no colour — the bridge does that. It exists so a contrast violation inside the list files as OWNED rather than inherited |
| `.qm-rounds-pdetail-actions` | the patient-detail action row | R3.2. Layout only |
| `.qm-rounds-overflow` | **BACK IN THIS TABLE, and the round trip is the contract working.** | R1 documented them here; R2 removed the rows when the overflow moved into `RoundsStage` and became Rounds-native anatomy; R3.2 mounts the same `<details>` on `/patients/[id]` — a SHARED surface — so it is a control primitive again. The class did not change; its consumers did, and `gate-controls-contract` caught both moves. Destructive `Delete` lives in it here for the same reason `Visit actions` does on the stage: a control that destroys a record is not a peer of "Export" |
| `.qm-rounds-overflow-*` | its parts — `-summary` (the trigger), `-body` (the disclosed content) | R3.2. A PREFIX row, matching how `-skel-*` and `-tmpl-*` are covered: the matcher requires a member longer than the prefix, so a bare `.qm-rounds-overflow-` cannot satisfy it — the substring trap this file already records three sightings of |
| `.qm-rounds-gate-signbar` | the **re-homed signature**, inside Gate 3 | R2. A control primitive because it is applied on a SHARED surface (`review-sign-bar.tsx`), not a Rounds-native directory — the same file renders the legacy `.qm-c3-rev2-signbar` footer with the flag off. It sets no colour: the sign trigger inside it is `SignAndSendModal`'s own button, and repainting it here would fork a control two other surfaces share. Deliberately **not** `position: sticky` — the legacy bar was, and being pinned to the viewport is what made it a permanent second sign control on the stage |

> **RETIRED 2026-08-14 — `.qm-rounds-rx`, owner ruling #109.** It had a row in
> the table above until the prescription-safety surface was deleted. It hosted
> that surface's Rounds treatment — mono kickers and advisory levels on the
> status palette — over the `qm-lin-rx-*` family, and both the class and the
> family are gone. Recorded HERE rather than as a struck-through row because
> the § Controls parser reads any row naming a `.class` as a live contract and
> would keep demanding a CSS rule for it.

**⚠️ R2 — `.qm-rounds-overflow*` LEFT THIS TABLE, AND THE MOVE IS THE REASON.**
R1 documented it here correctly: it was applied in `visits/[id]/page.tsx`, a
shared surface, which made it a control primitive by this section's own
boundary. R2 moved the `<details>` into `RoundsStage` — so it is now applied
only under `src/components/rounds/`, which makes it **Rounds-native anatomy**,
and `gate-controls-contract`'s first direction reds on a documented class that
files as native. Both directions of that guard are load-bearing and neither was
weakened to accommodate this; the row moved because the code did.

The decision it recorded is still the decision, so it is kept here rather than
deleted: `Delete` used to sit in a right-aligned row directly above the note,
level with the patient's name, and destroying a visit is not a peer of "read
this carefully". A native `<details>` is keyboard-operable and
screen-reader-announced with no JavaScript, and it starts closed. R2 moved it
again for the same class of reason — it had been rendering *after the entire
visit body*, below the action rail and past the end of the note.

The same applies to R2's other new classes — `.qm-rounds-newvisit*`,
`.qm-rounds-lane-card`, `.qm-rounds-stage-head`, `.qm-rounds-gateflow-sign`.
All are applied only in `components/rounds/`, so all are native anatomy and
none belongs in this table. They are documented at their rules in
`rounds-tokens.css`. **This paragraph exists because adding them here was the
first thing tried, and the guard refused it** — which is the contract working.

**A class that was declared and then removed, in the change that declared it.**
`.qm-rounds-btn-danger` is not in this table because it does not exist. C1-e
wrote it up front for an obviously destructive button, and the only candidate
kept an inline `background` it needs with the flag off — inline beats a class,
so the primitive's fill could never apply and the rest duplicated the C1-d
`.qm-lin-btn-primary` fork. `gate-c1d-auth`'s orphan assertion caught it. The
rule is *with its consumer, never ahead of one*, and the remedy for breaking it
is to delete the class, not to go looking for a caller.

### Two rules that are not style preferences

**`.qm-rounds-link` is underlined, and that is a recorded axe fix.** A link
distinguished from surrounding prose ONLY by hue fails `link-in-text-block` at
SERIOUS: anyone who cannot separate the two hues sees prose. Both the inline
style and this class carry it, so neither half alone can be tidied away.

**A class is how a node enters Gate C.** Ownership resolves to the nearest
ancestor-or-self carrying ANY class, and tests it for `qm-rounds-`. So on a
densely classed surface the host buys nothing for the nodes beneath it — the
walk stops at the first `qm-c3-*` it meets and reports NOT owned. Every node
whose appearance Rounds changes needs its own `qm-rounds-*`, and an
intermediate container needs one so that its CLASSLESS descendants resolve
somewhere useful. This is not decoration; it is the difference between a gate
and a green tick.

### What a bridge cannot do

Learned on the auth surface, at the cost of three AA failures that shipped
nowhere only because they were computed before the build:

- **A literal.** `.qm-lin-btn-primary` hardcodes `color: #0d1611` over a
  `var(--color-linear-sage)` fill. Bridging sage → `--rounds-accent` retints
  the fill and leaves the label: **6.72:1 → 3.43:1**. Same shape inline on
  /waitlist (**7.27:1 → 3.71:1**) and on the brand mark (**6.82:1 → 3.48:1**,
  and 2.71:1 on the gradient's far stop).
- **A token whose ROLE flips at one site.** `--color-linear-sage-bright` is a
  `color:` at ~13 sites and a `background:` at exactly one —
  `.qm-lin-btn-primary:hover`. One bridge line cannot serve both; the minority
  site gets an explicit rule.
- **A component that paints its own colours.** The root 404's `AnimatedGrid`
  is a fork, not bridge work.
- **A portalled node.** A Radix `<Dialog.Portal>` with no `container` mounts on
  `<body>`, so it is not a descendant of the host and inherits none of the
  bridge. Both settings modals were shipping old-skin interiors on a Rounds
  page. The host goes on `Dialog.Content` itself — and it must, because the
  danger *fill* and its label fork have to arrive through the same selector or
  fixing the fill pushes the label under AA. (C1-e.)

⚠️ **"A Tailwind utility" was in this list until 2026-08-01 and was wrong.**
Tailwind v4's `@theme` emits custom properties, so `bg-linear-surface-2`
compiles to `background-color: var(--color-linear-surface-2)` — verified in the
compiled chunk and at runtime, where a skeleton under the host with no override
in scope computes a Rounds token. It cost nothing yet only because the override
that "needed" it was elective anyway; the direction of the error is the
expensive one, since a split reading it forks files that bridge for free.
**A claim about what a mechanism cannot do is worth measuring before it is
written down beside claims that were.**

`--rounds-on-accent` (#fff — 5.37:1 on the accent, 6.90:1 on its hover) exists
for the first of those.

---

## What Rounds does NOT restyle

- **Custom templates.** A doctor's uploaded form renders exactly as it does
  today. Rounds styles the **default QuillMD layout only**. A practice that
  uploaded its own letterhead did not ask for our typography.
- **Server semantics of any gate.** The gates are UI over server refusals which
  remain the sole source of truth.
- **PDF / Word export parity, and the 820px paper width.**

---

## Flag

Built behind `NEXT_PUBLIC_SKIN_ROUNDS`. Build-time inlined, so flipping it needs a
rebuild — verify with the flag-inlining grep in the prod smoke, not by reading
`.env`.

Rollback tag at flip: `:pre-rounds-<date>`.
