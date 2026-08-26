> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **46 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A CAPABILITY IS UNREACHABLE UNTIL THE ACTOR THAT INVOKES IT IS TOLD

**Standing 2026-08-23. The no-caller defect one layer up, found by the
independent adversarial pass on F24-S4 (PR #809) after the branch had been
proved 29 ways, gated, and cited 4 of 4.**

Canon already records F4's defect: *a library capability with no caller passes
every test it has.* F24-S4 was written specifically to avoid it and **wired
every layer it could see** — the editor took `rowOrdinal`, the zod intent
carried it, the server action passed it through, and an arm read the caller file
to prove it. All three were correct.

> **The invoking actor here is a MODEL, and a model is wired by its PROMPT.
> `CHAT_EDIT_SYSTEM` never mentioned the field, and the branch never touched
> that file.**

Measured: `grep -c rowOrdinal prompt.ts` → **0**, positive-controlled against
its sibling `tableCaption` → **1**. So the refusal's new promise — *"tell me
which of the rows I listed you mean and I will change it"* — had **no path to
being kept**, and the change replaced a truthful dead end with an untruthful
one.

⚠️ **AND THE SAFETY RULE WAS WRITTEN WHERE NOTHING CAN READ IT — THE HALF THAT
GENERALISES FURTHEST.** The field's own doc-comment said, in capitals, *"THIS
FIELD IS AN ECHO AND NOT A COUNT THE MODEL TAKES OFF THE NOTE"*. That is a
JSDoc comment on a zod field. `anthropic.ts:315` converts the schema with
`z.toJSONSchema()` into the tool's `input_schema`, and **Zod emits `description`
only from `.describe()`/`.meta()`, never from TS comments** — `intent.ts` has
zero of either. The model therefore received `rowOrdinal` as
`{type:"integer",minimum:1,maximum:50}`: an undocumented integer, with the one
rule that makes it safe visible to every human reader and to nobody else.

> **A CONSTRAINT STATED IN A COMMENT ON A SCHEMA FIELD IS DOCUMENTATION FOR
> READERS AND ABSENT FROM THE WIRE.** If the actor bound by the rule is the
> model, the rule lives in the prompt or in a `.describe()` — or it is enforced
> server-side and does not depend on cooperation at all.

**THE DISCIPLINE, and the precedent was already in the same file:** when
`tableCaption` shipped, it got a schema field **and** a prompt paragraph
carrying its safety rule (*"If the doctor did not say which side, ASK — do not
pick one"*). **Enumerate the actors that must invoke a new capability, and check
each one was told** — the caller *code* and the caller *prompt* are two
different wirings, and only one of them has a type checker.

⚠️ **AND EVERY PROOF ON THE BRANCH RAN BELOW THE BROKEN LAYER.** The unit gate,
the census and CI all call `editTableCell` directly with an ordinal already in
hand. That is canon's *WELL-CHOSEN FIXTURE DISGUISES A WRONG UNIVERSE* pointed
at a LAYER rather than a route: the fixture supplies, for free, precisely the
thing production could not produce.

### ⚠️ AND THE ARM THAT NAMED THE INVARIANT WAS BLIND TO THE NEW FIELD

Same diff, and it is the watched-set failure in miniature.
`note-table-edit.test.ts:424` is named **"⚠️ NEVER asks a question it offers no
way to answer"** — exactly the invariant the diff broke. It stayed green
throughout, because it asserts `r.choices ?? []` has length 0 and the new
unanswerable list arrived in **`rowChoices`**, a field that did not exist when
the arm was written.

> **A guard's watched set does not grow when you add a field. Adding a second
> way to say the thing a guard forbids is how a correctly-named guard goes on
> passing.**

When a change introduces a NEW carrier for an existing concept — a second list,
a second id, a second status field — **grep the guards that name the concept and
widen them in the same commit**, or the invariant is protected only on the
carrier nobody uses any more.

