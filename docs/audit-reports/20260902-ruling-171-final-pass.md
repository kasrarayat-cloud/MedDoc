# THE #171 FINAL PASS — the fallback does not reach two of the four

**Three lenses, isolated worktrees content-verified before launch (canon 88),
scoped to the delta: the two refusals, the deletion, the arms.**

---

## 1 · THE DELETION IS CLEAN — VERIFIED, WITH A WORKING POSITIVE CONTROL

The central claim of #171(2) holds. `main`'s renderer and HEAD's were run in one
process over five documents:

| input | `word/document.xml` | proof kind |
|---|---|---|
| plain cell · numbered cell · cell with `w:sym` · legacy field · legacy spanning paragraphs with a numbered `end` | **byte-identical, all five** | `blank` = `blank` |
| **POSITIVE CONTROL** — a content control | **differs (321 B vs 310 B)** | `filled` vs `emptied` |

Credit is preserved, not merely bytes: on the real artifact **main 52 · #170 52 ·
HEAD 52**, and #170→HEAD verdict diffs = **0**. No dead code: every symbol the
deletion touched still has a live caller.

⚠️ **One narrowing "verbatim" does NOT carry, and it is not this commit's:**
HEAD's read path refuses selection kinds and `!resolvedNull` for `blank`, which
`main` did not. A `table_cell` bound to a selection counted on `main` and does
not now. That is #165/#168-era.

---

## 2 · I MIS-IMPLEMENTED R1, AND A REAL THIRD-PARTY DOCUMENT CANNOT CERTIFY

**#171(1)(b) says "a default PARAGRAPH style carrying `w:basedOn`". I applied it
to a default style of ANY type** — and R4 had just deleted the type filter that
used to run first, so the two compose into a document-wide refusal.

**Measured on `pandoc 3.1.3`'s shipped `reference.docx` styles table**, verified
by me:

```
total <w:numPr in the entire file: 0
default: Normal               type=paragraph  basedOn=no   numPr=no
default: DefaultParagraphFont type=character  basedOn=no   numPr=no
default: Table                type=table      basedOn=YES  numPr=no
```

→ `unresolved` → every content control `ineligible` → zero blank proofs →
**`blankVerification=false`, the template can never certify.** Silent: no error,
just `filled` labels. Deleting that one `w:basedOn` flips the same document to
counting.

**Producer census, N small and stated as such:** 1 of 3 independent producers —
Word (both real artifacts) clean, the `docx` npm package (QuillMD's own
generator) emits no `w:default` style at all, **pandoc without `--reference-doc`
refused**.

**The correction is to conform to the ruling as written:** the `basedOn` refusal
applies to a default whose `w:type` is `paragraph` or omitted; the `numPr` check
stays type-blind. That is R1 and R4 doing what each was ruled to do.

---

## 3 · FOUR `content_control` ROUTES — AND THE TERMINAL FALLBACK CLOSES ONLY TWO

#171(4) pre-declares that a `content_control` route collapses eligibility to
option A (no `w:pPr` at all). **Lens A mutated the guard to that blunt rule,
asserted the mutation applied, and re-measured.** Result:

| route | what it is | blunt rule closes it? |
|---|---|---|
| **A1 — the table-style layer is never read** | a control in a cell whose paragraph has **no `w:pPr`**, in a table naming a style that carries `w:numPr` → `emptied` · eligible · **counts** | ⚠️ **NO — measured.** Its shape is a paragraph with no `w:pPr`, which the collapsed rule declares *maximally* eligible |
| **A2 — CDATA survives the clear** | `<![CDATA[WARFARIN 5 MG DAILY]]>` in a sibling gap → `emptied` · eligible · counts, **drug string still in the output**, placeholder cleared | ⚠️ **NO** — not an eligibility route at all |
| A3 — allowlist checked on DIRECT children | a carrier nested inside `w:rPr`/`w:tabs` evades the single `w:r` backstop | yes |
| A4 — only the FIRST `w:pPr` is read | a second `pPr` carrying `numPr` is invisible | yes |

**A1's A/B is one attribute**, verified by me: the same style body marked
`w:default="1"` is correctly refused; named by the table's `w:tblStyle` it is
not. R4's inversion reaches the *default* layer; the **table-style layer of the
OOXML chain is unread**.

⚠️ **A2 IS THE ONE THAT ALREADY HAS A PRECEDENT IN THIS CODEBASE.**
`structureKeepDeletions`' own comment reads *"CHARACTER DATA IS A REFUSAL, NOT A
DELETION"* and cites the measurement that bare text in that position **prints**.
`gapIsInvisible` strips CDATA next to comments and processing instructions,
which genuinely are invisible — CDATA is not; a conformant parser yields the
identical text node. **Verified by me: the same bytes as raw text are refused
and the render throws; as CDATA they buy blank credit.** No arm anywhere
exercises that branch.

A3 and A4 are schema-invalid shapes with UNVERIFIED printing; A1 and A2 are not.

---

## 4 · SIX ARM DEFECTS, AND ONE IS THE SAME CLASS FOR THE FOURTH TIME

| # | defect | mutation redding it |
|---|---|---|
| C1 | R1 and R4 are each armed only on the axis the other is not — re-gating `basedOn` on `w:type="paragraph"` reds **0 of 96** | the exact correction §2 requires is invisible to the suite |
| C2 | the ALL-quantifier arm is ORDER-FIXED — its fixture is (inert, numbered), so pushing only the LAST paragraph reds **0** | catches `some` and first-only, nothing else |
| C3 | that arm has no positive control — `if (paragraphs.length > 1) return 'ineligible'` reds **0**, while every multi-paragraph block control silently loses credit | its R1/R4 siblings both carry one |
| C4 | a bare `find(kind === 'emptied')` matches **2** entries and retargets to the fixture's header control — in the only arm using a non-`w` prefix, whose title is *"no prefix can be wrong"* | reintroducing a `w:` assumption reds 0 |
| **C5** | ⚠️ **the D-5 arm I JUST RE-ARMED is one class-member away from laundering again.** `find(f => f.kind === 'filled')` matches **12** entries, 5 of them selections; take a different member and the refusal comes from `BLANK_INELIGIBLE_KINDS`, a neighbour | `resolvedNull` neutralised → passes |
| C6 | one genuinely vacuous arm in my new `#171` block — a `for` with an `if` and no non-vacuity guard; survives both the empty-proof sweep and the real regression | its two siblings carry `toBeDefined()` |

⚠️ **C5 IS THE FOURTH INSTANCE OF CANON 62 IN THIS ARC, AND THE WORST OF THE
FOUR.** I wrote the class rule — *use `theOnlyMatch` wherever the predicate is a
PROPERTY rather than a unique key* — **650 lines above, in the same file, in the
same commit**, and then did not apply it in the arm I was fixing *for exactly
that reason*. Writing a rule down is not obeying it; that is already canon, and
this is its cleanest specimen.

**What the matrix confirmed does measure:** M1 proves the `unevaluated` value
comes from `blankEligibilityOf` and not from a hardcoded literal; M8/M9 prove
the accepted-limit arms red when the limit closes; M5 proves D-1's arm now reds
with its own diagnostic; M6 proves D-5 reds on the axis it names.

---

## 5 · AND MY OWN DEFERRAL DOC MEASURES THE WRONG LIMIT

`docs/backlog/table-cell-structure-keep.md` and the #171 commit message both
measure the **carrier** limit (`w:sym`, `w:drawing`, …, "population zero") and
name its re-arming condition as a glyph, a logo or a signature image.

**But the guard the deletion removed watched NUMBERING**, and the doc never
names a numbered cell. "The limit predates this arc" is true of `main` and
obscures that the immediately preceding commit had closed the numbering half.

**The missing measurement, supplied by the pass:** of WM IOV's 52 `table_cell`
fields, cell paragraphs carrying `w:numPr` = **0** and `w:pStyle` = **0** —
positive-controlled, since 6 body paragraphs in the same file *do* carry
`w:numPr`. **The population claim is true; it was made about the wrong set.**
