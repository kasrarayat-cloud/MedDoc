# §2.5 BASELINE ADDENDUM — the tree deploy, re-measured by the deploying actor

**Written and committed BEFORE the act**, by FOUNDATION run `20260820-014110-b1`
session **02 of 6** — the session that will run `deploy-prod.sh` and judge the
result.

**It does not replace `docs/foundation/deploys/20260820-b3459390.md` (PR #752).**
That declaration is the gate and it resolves by ancestry. This addendum does two
things the gate cannot do for itself:

1. **Records the deploying actor's OWN measurement of every baseline row**, so
   the judgment is not made against numbers taken on trust. *A count carried
   forward from another session's report and then relied upon is inherited
   evidence.*
2. **Writes the SQL down.** The declaration states its rows but not its queries,
   which is precisely why one of them turned out not to be checkable.

⚠️ **This file is deliberately NOT in `docs/foundation/deploys/`.**
`declaration_resolve` scans that directory and **REFUSES on ambiguity** — two
equidistant ancestor declarations with no runtime diff stop the deploy. A second
file there would have been a self-inflicted refusal.

---

## THE RESULT IN ONE LINE

**Thirteen of the fourteen baseline rows reproduce EXACTLY, independently
measured. One does not**, and it is re-baselined here with its evidence.

## ✅ ROWS CONFIRMED — my own query, my own run, pre-deploy

| row | declared | I measured | |
|---|---|---|---|
| visits | 48 | **48** | ✅ |
| signed visits | 30 | **30** | ✅ |
| patients | 35 | **35** | ✅ |
| active `note_templates` | 7 (10 total) | **7 (10)** | ✅ |
| applied migrations | 104 of 104 | **104 of 104** | ✅ |
| **`###` heading lines in `soapFinal`** | **8** | **8** | ✅ **the row that discriminates** |
| twin compiled versions | 1 | **1** | ✅ |
| twin CERTIFIED versions | 0 | **0** | ✅ |
| mappings CERTIFIED | 80 | **80** | ✅ |
| mappings pending | 0 | **0** (only `CERTIFIED` exists in the table) | ✅ |
| fill manifests | 0 | **0** | ✅ |
| app image | `sha256:c6b0dd3446fb…` | **`c6b0dd3446fb56cf…`** | ✅ |
| worker image | `sha256:c3caed78175e…` | **`c3caed78175e1e11…`** | ✅ |
| deployed commit being replaced | `24b739f9` | **`24b739f9`**, from `docs/deploy-logs/deploy-20260819T050356Z.log` | ✅ |

The queries, so the next actor does not have to invent them:

```sql
select (select count(*) from transcribe_visits)                                   as visits,
       (select count(*) from transcribe_visits where "signedAt" is not null)      as signed,
       (select count(*) from transcribe_md_patients)                              as patients,
       (select count(*) from note_templates where status='active')                as active_tpl,
       (select count(*) from note_templates)                                      as total_tpl;

select (select count(*) from template_twin_compiled_versions)                             as compiled,
       (select count(*) from template_twin_compiled_versions
          where "certificationStatus"='CERTIFIED')                                        as certified,
       (select count(*) from template_twin_fill_manifests)                                as manifests;

select "mappingStatus", count(*) from template_twin_semantic_mappings group by 1;
```

I also re-verified the declaration's two structural claims rather than inheriting
them:

- `git diff --stat 24b739f9 origin/main -- apps packages prisma infra Caddyfile docker-compose.yml`
  → **16 files, 2179 insertions, 14 deletions** — exact, and the split is **8
  test files / 8 runtime files**, matching its table member for member.
- `em-artifact-scan.ts` has **zero** runtime importers — **positive-controlled**,
  because a grep that returns nothing and a grep that is broken produce the same
  output. Control: the same pattern shape against `docx-generator` returns **9**
  non-test importers. The zero is a measurement, not a silence.

---

## ⚠️ THE ONE ROW THAT DOES NOT REPRODUCE — MUST-NOT-CHANGE row 6

**Declared:** *"`##` heading lines in `soapFinal` = **237**"*, with the note that
F6.4's 282 differs because *"the queries differ in scope — mine scans `soapFinal`
only."*

**Measured, scanning `soapFinal` only: 282.** Not 237.

```sql
with lines as (
  select unnest(string_to_array("soapFinal", E'\n')) as ln
  from transcribe_visits where "soapFinal" is not null
)
select count(*) filter (where ln ~ '^##[^#]')  as h2,     -- 282
       count(*) filter (where ln ~ '^###[^#]') as h3,     -- 8
       count(*) filter (where ln ~ '^#[^#]')   as h1,     -- 0
       count(*) filter (where ln ~ '^####')    as h4plus, -- 0
       count(*)                                as total_lines
from lines;
```

**Seven further query shapes were tried and every one returns 282**, so this is
not a near-miss on regex pedantry:

| shape tried | result |
|---|---|
| `^##\s` (whitespace required) | 282 |
| `^## ` (literal space) | 282 |
| `^##\s+\S` (content required) | 282 |
| `^##\s+[A-Z]` | 282 |
| `^##[^#]` excluding bolded lines | 282 |
| non-empty note, trimmed line length > 2 | 282 |
| `coalesce("soapFinal","soapDraft")` | 282 |

And the scopes that DO move the number move it to something other than 237:
`soapDraft` alone → **291**; signed visits only → **177**; distinct heading text
→ **32**; raw `##` pair count over the whole column → **290**; and the per-practice
split reconciles to the total (**193 + 58 + 26 + 5 = 282**), so no practice
exclusion yields 237 either. `282 − 237 = 45`, and nothing in the data has 45.

### ⚠️ AND AN INDEPENDENT INSTRUMENT CORROBORATES 282 — FOUND BY ACCIDENT

This was not sought; it fell out of running the F12-g note-shape watcher as a
standing STEP 0 check, minutes later and for an unrelated reason.

That scan's own **projection control** reports, on this same database:

    · projection control: 290 lines delivered = 290 headings — no body text

It extracts markdown heading lines with `^[ \t]*#{1,6}[ \t]+` — **every** depth,
not just `##`. My measurement, taken separately with different SQL for a
different purpose, is:

    ##   282
    ###    8
    #      0
    ####+  0
    ─────────
    total 290

**290 = 290.** Two instruments written by different sessions, with different
regexes, for different purposes, reconcile exactly — and they reconcile on
**282**, not on 237. There is no residue for a 45-line difference to hide in.

⚠️ **This is corroboration, and its limits are stated rather than glossed.** The
agreement is on the TOTAL heading count; the scan does not publish a per-depth
split, so it confirms `282 + 8 + 0 + 0` as a sum rather than confirming `##`
alone. Since the two non-`##` buckets are measured at zero by the query above,
the sum pins `##` at 282 — but that last step is my arithmetic, not a second
instrument's reading.

### ⚠️ AND THE DECISIVE ONE: F6.4's OWN COMMITTED DECLARATION ALSO SAYS 282

`docs/foundation/deploys/20260820-64c49a45.md`, committed by session 01 before
its own act, on the **same database, the same night**:

    | **`##` heading lines in stored notes** | **282** |
    | **`###` heading lines in stored notes** |   **8** |
    ...
    | 6 | **`##` lines still 282** | the renderer must not touch stored note text |
    | 7 | **`###` lines still 8**  | ⚠️ **THE ONE THAT MATTERS.** ...

**Same quantity. Same wording. Same MUST-NOT-CHANGE row number. 282.**

`RELAY.md:21274` restates it in the hand-off — *"`##` 282 lines · `###` 8
lines"*. So PR #752's framing — *"F6.4's baseline reads 282; the same question
asked by THIS declaration's query reads 237, the queries differ in scope"* — is
a real and honestly-flagged discrepancy whose stated resolution does not hold:
**there is no scope on this database, that I could find, under which the
`soapFinal`-only question answers 237.**

**The tally, and it is three independent sources against one:**

| source | `##` |
|---|---|
| F6.4's committed declaration (session 01, same night) | **282** |
| my own SQL, 7 query shapes, run pre-deploy | **282** |
| F12-g's projection control, total headings, different regex | **290 = 282 + 8** |
| PR #752's declaration row 6 | *237* |

⚠️ **This is stated as a measurement, not an accusation.** The author flagged the
discrepancy rather than hiding it, and every other row they wrote reproduces
exactly — including the two structural claims I re-derived. The most likely
reading is a query that was run, produced 237, and whose scope was described from
memory rather than pasted. **Which is exactly why the fix is to paste the SQL,
not to be more careful.**

### ROW 16's STRUCTURAL PROBE — RE-VERIFIED PRE-DEPLOY, WITH ITS CONTROL

Handed forward by session 01 and **re-run here rather than inherited**:

    docker exec meddoc-pro-transcribe-md-worker-1 grep -c \
      NOTE_HEADING_LINE_RE /app/apps/transcribe-md/src/lib/docx-generator.ts
    → 0       must read >= 1 after the deploy

    … grep -c renderSoapParagraphs …
    → 2       traversal control — the probe reaches the file

**The zero is only meaningful because the control is non-zero.** Without it, "the
new symbol is absent" and "the probe never opened the file" are the same output —
this repository's most expensive recurring defect, and the reason a post-deploy
`1` will actually mean something.

### DISPOSITION — RE-BASELINED, NOT WAIVED, AND NOT A BLOCKER

> **Row 6 is judged against `##` = 282**, measured by me, **committed before the
> deploy**, with the SQL above. The §2.5 product is preserved in full: the number
> was fixed before the evidence existed and it is a number I observed myself.

**Why this does not stop the deploy:**

- Row 6 is the *sanity* row — *"the renderer must not touch stored note text"*.
  The row that **discriminates for the change actually shipping** is row 7,
  `###` = **8**, and it reproduces **exactly**, on the same query, on the same
  three visits F6.4 named (`cms2e4k6w…` 2, `cmsz4fawa…` 2, `cmsz4jsei…` 4).
- Every other row in the declaration reproduces exactly. This is an **isolated
  irreproducible figure, not a declaration measured on the wrong system** — had
  the baseline been taken against the wrong database or the wrong column, the
  clinical counts would have moved too, and they did not.
- The invariant being protected is unchanged either way: **this deploy carries no
  migration and no back-fill, so a heading count in stored text must not move at
  all.** 282 → 282 proves that as well as 237 → 237 would have.

### THE CLASS, NAMED

**A declaration states its ROWS; it must also state its QUERIES.** Row 6 was
unfalsifiable-by-anyone-else not because the number was careless — the actor
explicitly flagged the discrepancy and explained it — but because the
explanation (*"scans `soapFinal` only"*) is the one thing that does not
reproduce, and there was no SQL to check it against.

This is AGENTS.md's *"an unfalsifiable observation is not evidence, whoever made
it"* arriving at the §2.5 gate: a MUST-NOT-CHANGE row that a second actor cannot
recompute cannot be judged by the actor who deploys — and under the standing
split, **the writer of a declaration and the runner of a deploy are routinely
different sessions.**

**Recommendation for the next declaration:** carry the query beside the number
for any row that is not a bare `count(*)` on a table. It costs one fenced block
and it is the difference between a row and a claim.

---

## WHAT THIS ADDENDUM DOES NOT CLAIM

- It does **not** re-open any other row; thirteen reproduce and are accepted as
  written.
- It does **not** assert the declaration's author erred in method — only that
  **the stated scope does not yield the stated number** on this database at this
  time, and I could not find a scope that does.
- It does **not** touch the MUST-CHANGE rows, the MAY-CHANGE backfill section, or
  the finding rule. Those stand exactly as PR #752 wrote them.
