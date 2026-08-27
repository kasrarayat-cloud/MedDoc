# OVERLAPPING GUARDS MUST NOT LAUNDER AN UNPROVED ARM

**Ratified 2026-08-27.**

> **When a mutation is caught by a DIFFERENT guard than the one you were trying
> to prove, your arm is still unproved — and the run that "went red" is the most
> convincing possible evidence that it works.**
>
> **RE-MUTATE TO THE MINIMAL SHAPE THE ARM CAN SEE.**

⚠️ **REFERENCE CASE.** `rotate-ledger.sh` gained a no-duplication
post-condition: *no archived section may still be present in the head.* To prove
it, the splitter was mutated so the head retained a copy of an archived section.

The run went **red, exit 2**, exactly as a working arm would produce. It was the
wrong guard:

```
FATAL: the new head is 126790 chars, over the 120000 budget
🔴 rotate-ledger: the splitter REFUSED
```

That is the splitter's **P6 budget** arm. The mutation had duplicated **109 KB**,
so the head blew its size budget and the proof aborted *before the
no-duplication check ever ran.* Recorded as evidence, it would have certified an
arm that had never executed once.

**THE CURE IS THE MUTATION, NOT THE ASSERTION.** Re-mutated to duplicate a
heading plus three lines — small enough to pass P6, large enough for the arm to
see — the correct guard fired:

```
🔴 rotate-ledger: CANNOT TELL — content is in BOTH the head and an archive.
     2026-08-27-part1.md: ## ✅ F99 — A SYNTHETIC CLOSED ARC — 2026-08-27
```

## WHY THIS IS ITS OWN ENTRY

This house already requires that **a mutation asserts its own application** — and
that rule was satisfied here. The marker landed, the file changed, the assertion
passed. **Application is not exercise.** A mutation can apply perfectly and still
never reach the code you are testing, because something upstream refuses first.

> **A GREEN THAT NEVER RAN AND A RED THAT RAN SOMEWHERE ELSE ARE THE SAME
> DEFECT WEARING DIFFERENT CLOTHES.** The first is the unapplied mutation; the
> second is this one, and it is harder to catch because *the output looks like
> success.*

**THE CHECK IS ONE QUESTION, ASKED OF THE OUTPUT AND NOT OF THE INTENT:** *does
the failure message name MY arm?* If it names a different guard, the proof has
not happened — **whatever colour the run is.** Read the whole output, not the
exit code: a proof that aborted upstream and a proof that fired are both `exit
2`, and only the text distinguishes them.

⚠️ **AND DO NOT "FIX" IT BY WEAKENING THE UPSTREAM GUARD.** The budget arm was
correct and catching a real problem. Defence in depth is the desired state; the
obligation it creates is that **each layer must be provable independently**, and
that means shaping the mutation to the layer under test rather than removing the
layers above it.
