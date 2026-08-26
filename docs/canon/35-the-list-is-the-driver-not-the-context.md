> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **69 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## THE LIST IS THE DRIVER, NOT THE CONTEXT

**When a sweep produces an enumeration, the fixing pass ITERATES THE LIST.** Each
entry is marked fixed or not-applicable **with its evidence**, and completion
means *the list is exhausted* — never *"the other signals went quiet."*

This is the operational form of **"naming a class is not enumerating it."** That
rule catches the case where the list was never built. This one catches the case
where it was built, printed, read — **and then not used.**

⚠️ **REFERENCE CASE, 2026-08-07 — five enumerated, zero fixed.** A by-table sweep
for `note_templates` printed `noteTemplate — 5 ORM creates`. The fixing pass then
followed two OTHER signals: the raw-SQL grep (4 helpers) and whatever `tsc`
surfaced (2 sites). The five fell between them — invisible to `tsc` because the
shared client is `any`, and not raw SQL either. Both signals went quiet, the work
felt done, and CI failed on a CHECK constraint in the T1 seed.

    A LIST THAT IS PRODUCED AND NOT WORKED FROM IS A COMMENT.

The shape that prevents it:

    for each entry in the enumeration:
        fix it, or record why it is not applicable
    assert: every entry accounted for

**"The errors stopped appearing" is not a completion criterion** — it is a
statement about your detectors, and detectors have coverage. The list is the
contract; the detectors are a convenience.

