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
