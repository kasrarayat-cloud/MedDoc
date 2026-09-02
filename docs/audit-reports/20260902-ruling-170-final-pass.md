# THE #170 FINAL PASS — the allowlist held; the defects moved to the plumbing

**Four lenses, isolated worktrees created and content-verified before launch
(canon 88).** Every finding below was **re-measured by me, with discriminating
controls**, before being believed.

---

## THE HEADLINE, AND IT IS NOT WHAT THE ESCALATION ANTICIPATED

**#170's instrument change worked.** The inert allowlist itself was attacked and
held: membership is tested on the LOCAL name so no namespace prefix evades it;
the compiler blocks text carriers before the guard is reached; the
content-control clearing path refused every carrier tried; and an absent or
unparseable `styles.xml` fails closed.

> **THE ROUTES THAT WERE FOUND ARE NOT IN THE ALLOWLIST. Every one is in the
> machinery AROUND it — the inherited-default resolution, the watched set for
> one binding, and a predicate that is vacuous on an empty set.**

⚠️ **WHICH IS WHY THE PRE-DECLARED ESCALATION DOES NOT REACH THEM.** Its
permitted fix class is *an element LEAVING the inert list*, and its fallback is
option A (strict no-`pPr`). **Neither closes a single one of these routes:**

| route | fixed by removing an inert element? | fixed by option A? |
|---|---|---|
| default style's `basedOn` chain | no — it is in `defaultParagraphNumbering` | **no** — it applies to paragraphs with NO `pPr`, the shape option A blesses |
| legacy span crossing a paragraph | no — it is in the routing's watched set | no |
| `blankEligibilityOf([])` vacuously eligible | no — it is in the predicate | no |

**That is the finding to rule on**, and it is stated before the individual
defects because it changes what the next decision is about.

---

## CONFIRMED ROUTES — each measured by me with a control that discriminates

### R1 — the DEFAULT style's `w:basedOn` chain is not walked (`renderer.ts` `defaultParagraphNumbering`)

```
CONTROL  numPr directly on Normal      -> filled,  does not count   (correct)
ATTACK   Normal basedOn a numbered sty -> emptied, eligible, COUNTS
```

The code's own security argument — *"no `basedOn` chain to walk"* — is true for
paragraphs naming a style via `w:pStyle`, which #170 made ineligible outright.
**The DEFAULT style's chain is still live**, and it applies to a paragraph with
no `w:pPr` at all, which `paragraphIsInert` calls the cleanest possible answer.

**COST OF THE FAIL-CLOSED FIX, MEASURED:** WM IOV's `Normal` carries **no**
`basedOn` (42 of its 46 styles do; the default is not one of them), and Word's
root `Normal` conventionally has none. Refusing a default style that carries
`basedOn` — a refusal, not a walk, the same move `pStyle` already got — costs
**zero on both real artifacts**.

### R2 — `legacy_form_field`'s watched set is ONE paragraph of a span it cannot bound (`renderer.ts`, the legacy arm)

```
CONTROL  numbering on the BEGIN paragraph -> ineligible, does not count
ATTACK   numbering on the END paragraph   -> eligible,   COUNTS
```

`bound` is the **begin** `w:fldChar`, so `containingParagraph(bound)` judges only
the paragraph holding `begin`. A `FORMTEXT` result legitimately crosses a
paragraph boundary, and the second paragraph lies entirely inside the field.

⚠️ **THIS IS A DEFECT #170 INTRODUCED.** Before it, legacy returned a hardcoded
`true` and was simply unguarded. #170 gave it a guard, and the guard uses a
single-paragraph approximation of a span **this very file says cannot be bounded
by walking** — which is why legacy earns no `emptied` proof at all. The other two
bindings have complete watched sets: content control collects every `w:p` in
every `sdtContent` plus the containing paragraph; table cell takes every
descendant `w:p`.

### R3 — `blankEligibilityOf([])` returns `eligible`, vacuously (`renderer.ts`)

```
a table cell with ZERO w:p -> eligible, COUNTS
```

`paragraphs.every(paragraphIsInert)` is **true on an empty array**. Two reachable
call sites produce one: a `w:tc` with no paragraph, and a `w:fldChar` with no
containing `w:p`.

⚠️ **THIS IS THE SENTINEL'S OWN DEFECT, ONE LAYER INSIDE THE FIX THAT
INTRODUCED IT.** The whole product of three-state eligibility is that
*unexamined* and *examined-and-approved* are distinguishable. Here a guard that
examined **nothing** emits the computed-and-approved value. `'unevaluated'` is
the honest answer for an empty set, and `every()` cannot produce it. The harm
today is bounded — a region with no paragraph cannot print a marker — but the
property being violated is the one #170 exists to establish.

---

## AND A SEPARATE CLASS, NOT A #170 REGRESSION: ELIGIBLE ≠ EMPTY

`table_cell` and `legacy_form_field` clear only `w:t`. A cell holding a printable
carrier and no `w:t` produces **zero patches**, takes the zero-patch `blank`
path, and counts:

| carrier in an otherwise-empty cell | verdict | survives in the rendered output |
|---|---|---|
| `w:sym` (a Wingdings tick) | `blank` · eligible · **COUNTS** | **yes** |
| `w:drawing` | `blank` · eligible · **COUNTS** | **yes** |

**This predates #170** — before it, those bindings were hardcoded eligible and
`blank` counted, so the same harm counted then. It was reported in the previous
pass and surfaced as latent. It is now **confirmed to count**, which is the part
that was previously only argued.

⚠️ **IT IS #164's HARM ON THE OTHER AXIS.** #164 was falsified by a control that
printed a Wingdings tick while proofed blank. The eligibility guard answers
*"can a mark be ADDED by this paragraph's properties?"* It does not answer
*"is this region EMPTY?"* — and for two of the three bindings nothing does.

**POPULATION, WITH ITS RE-ARMING CONDITION:** WM IOV contains zero
`w:sym / w:drawing / w:pict / w:object / w:fldSimple`. It arms on any uploaded
template with a glyph checkbox, a logo, a signature image, or a `PAGE`/`QUOTE`
field in a cell that is otherwise empty — none of which is exotic in a clinical
form.

---

## R4 — a default TABLE style is skipped by the `w:type` filter

`if (type !== null && type.toLowerCase() !== 'paragraph') continue;` skips a
`w:style w:type="table" w:default="1"` carrying `w:pPr/w:numPr`, which applies to
paragraphs in cells of tables naming no style. ⚠️ **The filter is one-sided in
the opposite direction from the ST_OnOff fix immediately above it** — that one
was widened to fail closed, this one still narrows. Two lenses found it.
Whether Word prints the marker for that construct is **UNVERIFIED**; what is
measured is our guard's blind spot.

---

## AND THE ARMS — SIX DEFECTS, ALL DEMONSTRATED BY MUTATION, TWO VERIFIED BY ME

⚠️ **THE MUTATION MATRIX I RAN BEFORE COMMITTING WAS 10 OF 10 GREEN, AND IT WAS
NOT ENOUGH.** A second matrix over the same code found five mutations that red
NOTHING. Mine tested the fixes wholesale; these are the partial and quantifier
shapes — the ones that actually ship.

### A1 — the rewritten `blank-proof` MUTATION arm does not red on the regression it NAMES *(verified by me)*

Applying `if (patches.length === 0) continue;` verbatim: **the arm passes.** Its
filter is `p.kind === 'blank' || p.kind === 'emptied'`, and `emptied` comes from
the PATCHED path which the regression does not touch — so the count falls 6 → 4
and stays `> 0`. Only the neighbour reds, with a bare `expected 0 to be greater
than 0`, so the diagnostic message I wrote never prints.

⚠️ **THIS IS THE ARM I REWROTE *BECAUSE* IT WAS MEASURING THE WRONG THING** —
a canon-72 source-text gate replaced by a behavioural assertion that is laundered
by a neighbouring path. Repair is one edit: drop `|| p.kind === 'emptied'`.

### A2 — ⚠️ THIS DELTA DISARMED A PRE-EXISTING GATE ARM *(verified by me)*

Neutralising `resolvedNull` in `certification-lifecycle.ts` reds **0 of 757** —
including the arm named *"⚠️ `resolvedNull` is pinned THROUGH
`certifyAndActivateTemplateTwin`, not through its helper"*.

**Mechanism, verified in both directions:** that arm's forgery relabels a
genuinely `filled` proof to `blank`. A `filled` proof carries no
`blankEligible`, so #170's new read path refuses it **as an absent sentinel,
before `resolvedNull` is ever consulted**. It was armed before this commit and
is not armed after it.

⚠️ **AND IT IS THE IDENTICAL LAUNDERING I FOUND AND FIXED IN THE SIBLING ARM IN
THE SAME COMMIT** — by adding `blankEligible: 'eligible'` to a forged `emptied`.
I fixed the instance and did not sweep the class, which is the defect canon
already names, committed by the session that had just written it down.

### A3 — "EVERY paragraph in the cell is asked, not merely the first" is unarmed

`descendantXmlElements(bound, 'p')` → `.slice(0, 1)` reds **0 of 757**. The
routing fixture puts exactly ONE paragraph in the answer cell, so no arm can
distinguish *every* from *the first*. Measured on a two-paragraph cell, the
mutation flips a numbered cell from `ineligible` to `eligible`.

### A4 — the ALL-quantifier itself is unarmed, and the empty set is unpinned

`every` → `length === 0 || some` reds **0 of 757**. Instrumented: of **2 174**
calls in the whole suite, **2 171 have exactly one paragraph in scope**. The only
mixed set is produced by an arm that asserts nothing about eligibility. So
`renderer.ts`'s own sentence — *every paragraph in scope must be a shape nothing
can hide in* — has no arm behind it, and R3's empty-set behaviour is pinned in
neither direction.

### A5 — the RENDERER half of the three-state sentinel is unarmed

All **five** `blankEligible: 'unevaluated'` literals flipped to `'eligible'` in
one pass: **0 of 757 red.** Instrumented across all 62 files: **1 160
`eligible`, 20 `ineligible`, 0 `unevaluated`** — no test ever observes the third
state coming out of the renderer. The only arm naming `unevaluated` feeds
hand-built literals to the READ path; it says nothing about the write path ever
producing one.

### A6 — three arms were converted from non-vacuous to vacuous by this delta

Forcing `bodyProofs` to `[]` reds 36 of 79 arms; **41 survive an empty proof
set.** Among them, four assert only via
`expect(bodyProofs.map(p => p.kind)).not.toContain('emptied')` — satisfied by an
empty array. Three were `toContain` before this commit (a form that cannot pass
vacuously) and I reversed them; the fourth is new. **Reversing them was correct
on the merits and it flipped them from a positive existence claim to a negative
one**, and none gained the non-vacuity guard or the `countsAsBlankProof` outcome
check that the sibling `#170` arms all carry.

---

## ⚠️ AND A CLAIM IN MY OWN COMMIT MESSAGE IS OVERSTATED

It lists among the proven behaviours: *"treats an absent or unparseable
`styles.xml` as INELIGIBLE"*. **Only the ABSENT half is proven.** Flipping the
`catch` to return `'clear'` — fail-OPEN on an unparseable style table — reds
**0 of 757**. The limit is disclosed honestly in a comment inside a different
arm, and the commit message still asserted both halves as measured.

## WHAT HELD, recorded so the report is falsifiable

- **The value axis of the sentinel is type-safe at runtime.** 21 values probed —
  absent, `undefined`, `null`, `''`, `0`, `1`, `true`, `false`, `'Eligible'`,
  `'ELIGIBLE'`, `' eligible'`, `'eligible '`, `['eligible']`, `{}`, a
  `toString` object, `new String('eligible')`, `Symbol`, `'ineligible'`,
  `'unevaluated'` — **all refused**, with `'eligible'` controlled to count.
- **The wire is clean.** No Zod strip, no field pick between renderer and the
  stored JSON; a full `JSON.parse(JSON.stringify(…))` round-trip preserves every
  entry and still certifies.
- **Pre-#170 stored proofs are correctly refused.** No grandfathering path
  exists — absence really does mean no.
- **The allowlist resisted direct attack:** local-name membership defeats prefix
  evasion; `docDefaults`, the ST_OnOff spellings and an omitted `w:type` are all
  handled; a missing styles part fails closed.
