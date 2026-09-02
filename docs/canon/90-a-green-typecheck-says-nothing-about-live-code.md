# A GREEN TYPECHECK SAYS NOTHING ABOUT WHETHER CODE IS LIVE

**Recorded 2026-09-02.** `tsc --noEmit` proves types are consistent. It does not
prove a line ever executes, and the two get conflated because "tsc clean" is
cited the way a test result is.

## The specimen

A refactor moved a `return` above a block that had to run:

    const numbered = …
    const selection = …
    return { patches: out, blankEligible: !numbered && !selection };

    // the placeholder-flag removal, now unreachable
    for (const flag of descendantXmlElements(control, 'showingPlcHdr')) {
      out.push(removeXmlElementPatch(flag, fieldId));
    }

**`tsc --noEmit` exited 0.** The dead block is type-correct; nothing about it is
a type error. `noUnusedLocals` does not fire — the symbols are used, in code
that never runs. Three test arms caught it, all asserting the OUTPUT rather than
the shape of the source.

## Why the confusion is structural rather than careless

A typechecker's job is to reject programs whose types disagree. Reachability is
a different property, and TypeScript deliberately does not enforce it: it reports
unreachable code only under `allowUnreachableCode: false`, which most
configurations leave at its permissive default, and never across the kind of
control flow a real refactor produces.

> **`tsc` answers "would this run correctly IF it ran". Only a test answers
> "does it run".**

## ⚠️ AND THE SAME PASS FOUND THE SHARPER VERSION OF THIS

An adversarial lens made a function `throw` unconditionally and **zero of 36
arms redded** — the function was never called from that file at all. A green
suite around dead code looks exactly like a green suite around working code.

That is why an arm's worth is measured by MUTATION and not by reading it:
deleting the thing it claims to guard is the only question that distinguishes
"this passes" from "this measures something".

## The practice

- Never cite "tsc clean" as evidence a behaviour exists. It is evidence about
  types, and saying so costs one word.
- When a refactor moves control flow, the arm that catches a mistake asserts the
  OUTPUT, not the source. All three arms that caught the specimen above were
  checking rendered bytes.
- If a check has no arm, prove it is load-bearing by disabling it and watching
  something red — and if nothing does, that is the finding.
