> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **105 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know ▸ PROSE IS NEVER A SHELL ARGUMENT**.
> Why the split: `docs/canon/README.md`.

### And a reassurance check needs a POSITIVE CONTROL like any other

The same incident, second half. Asked whether the accidental `npm ci` had
touched anything, the first check was
`find node_modules -newermt '30 minutes ago'` → **0**, read as an all-clear.
It was wrong. `stat -c '%y'` on the same directory said `06:20:48`, one minute
earlier — the install had rewritten it.

**A check run to prove nothing happened is the one most likely to be believed
without scrutiny, and the least likely to be controlled.** It is the emptiness
test from §"positive-control every zero", arriving at the moment you most want
a clean answer. Before believing an all-clear: run the same matcher against
something you KNOW is present, or answer with a second, independent tool. Two
tools disagreeing is a finding; one tool agreeing with your hope is not
evidence.

