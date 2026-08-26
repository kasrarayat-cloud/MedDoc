> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **83 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## A FIX IS PRICED BY THE ASSET BEHIND THE SYMPTOM, NOT BY THE SYMPTOM'S VOLUME

**Standing rule for every backlog row, follow-up and "🟢 nice to have".** When
you set a severity, name the thing that breaks if the item is never done — then
price *that*. A symptom's loudness is a fact about the symptom, and it is
routinely inverse to the value of what sits behind it: the quietest failures are
the ones where nothing is in an error state.

> **Ask "what is this a symptom OF?" before "how annoying is this?"**

⚠️ **REFERENCE CASE — THE 65-DAY 🟢, 2026-08-07.**
`docs/qa-reports/site-down-20260603.md` §9.5, follow-up 5 of 6, priority 🟢:

> **🟢 Caddy ACME noise** — Caddy still retries LE every ~10 min and now never
> needs to. Add `tls internal` to the quillmd Caddy blocks.

Every word of that is true. The severity is wrong by the width of the system.
The item was titled by its symptom — **log spam** — and priced accordingly. The
asset behind the symptom was **the certificate on the only path from the
internet to the application**. Sixty-five days later that certificate expired,
its storage was cleaned, a reboot dropped the in-memory copy, and every public
hostname served `502` for six hours and fifteen minutes. `/login` was 0 of 30.

The same report had already written the deadline down and nobody carried it
forward: §6.2 recorded *"Certs aren't expired (~46 days left), so this is latent,
not the outage."* **Forty-six days is a due date wearing a reassurance's
clothes.**

Three things generalise:

1. **A "noise" item that touches an expiring credential, a certificate, a token
   or a lease is not a noise item.** Rename it after the asset. `tls internal on
   the ingress hop` gets triaged; `Caddy ACME noise` gets skipped forever.
2. **"Latent, not the outage" needs a DATE and an owner, or it decays.** An
   unanswered question becomes "probably fine" through nothing but repetition —
   the same decay that left the May audit PDF tracked and unlisted for eleven
   weeks.
3. **Priority set from the symptom is unfalsifiable later.** Nobody re-reads a
   🟢 to ask whether it was priced right; the colour *is* the reason it is not
   re-read. So the pricing has to be right when written, which means it has to
   be written against the asset.

⚠️ **AND THE DOCUMENT THAT DESCRIBED THE INTENDED STATE MADE IT WORSE.**
`DEPLOYMENT_RUNBOOK.md` §5.6 had asserted since 2026-07-28 that Caddy *"sits
behind it on `127.0.0.1:8443` with its own internal certs and is not involved."*
That sentence was **false for two months**. It described what the topology was
*supposed* to be, in the present tense, and every reader took it as a statement
about the running system — so the gap between intent and reality was invisible
to anyone consulting either document.

> **A stated invariant is a WISH until something asserts it. Write the check, or
> write the sentence in the future tense.**

That is why the fix shipped with `scripts/check-ingress-tls.sh` rather than with
a corrected paragraph.

