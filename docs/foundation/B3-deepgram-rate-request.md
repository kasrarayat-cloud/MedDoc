# B3 BLOCKER — the `nova-3-medical` rate needs the vendor. Owner action.

**Status: STAGED, NOT SENT.** Contacting a vendor on the QuillMD account is an
owner action; this file is the request written and ready, plus everything needed
to judge the answer when it comes back. **It must go out in parallel with B3's
other work, not after it** — B3 stalls at 2 of 3 rates without it, and B6
(`charge = cost × 3 / 2`) would inherit a rate the price table refused to certify.

---

## What we need, in one line

> **The effective per-minute rate for `nova-3-medical` PRE-RECORDED transcription
> on the QuillMD account, and the date it took effect** — as an invoice line item
> or a figure shown in the Deepgram console for our account.

## Why the public number will not do

SPEC §4.5 requires PROVENANCE on every rate: one of `published` (URL + read-date),
`invoice`, or `console`. It then disqualifies this one by name — `nova-3-medical`'s
only public figure is an **undated announcement post**, which is not a
`published` provenance because there is no date to pin it to and no guarantee it
still holds.

DISCOVERY §D.5 reaches the same conclusion and says so plainly: confirming it
*"is a question for Deepgram, not for another sweep."* Two sweeps have now agreed;
a third will not change the answer.

## Why we cannot derive it ourselves

Measured on production 2026-08-07:

    api_usage_events  where provider='deepgram'  →  2 rows
    ai_calls          where provider='deepgram'  →  1 row, 1 cent total

There is no billing volume to reverse-engineer a rate from, and quite possibly no
invoice line item at all if the account has been running on trial credits. **This
is worth saying in the request** — it is why we are asking rather than reading it
off a bill.

## What we assume today, and why that is not good enough

`packages/ai/src/pricing.ts:32`

    const DEFAULT_DEEPGRAM_CENTS_PER_MIN = 1.45;    // $0.0145 / min

Unsourced — no URL, no date, no invoice. It is env-overridable via
`DEEPGRAM_COST_PER_MIN_CENTS` (`pricing.ts:156`), and `nova-3-medical` is the
model that actually runs: `deepgram-batch.ts:23` sets it as
`DEFAULT_BATCH_MODEL`. So this constant prices the real path.

⚠️ **AND IT VIOLATES ITS OWN FILE'S STATED INVARIANT.** `pricing.ts:23` says
*"All values are INTEGER CENTS so summation is drift-free"*; `1.45` is not an
integer cent. That is GATE 0.4's argument for integer micro-dollars appearing as
a live inconsistency rather than a principle — and production agrees: **98 of
1085 priced `ai_calls` rows store `costUsdCents = 0`**, real calls that cost money
rounded away because a cent is too coarse.

**The rate is NOT patched now.** SPEC §4.5 is explicit: it feeds only
observability today, nobody is billed from it, and changing it would silently
re-base a year of historical `ai_calls` comparisons. It is corrected **by the
price table, in B3, with provenance** — which is what this request unblocks.

---

## The message — ready to send

> Hello,
>
> We run clinical speech-to-text on Deepgram and are building an internal cost
> ledger that has to reconcile against what you actually charge us. For that we
> need each rate recorded with a verifiable source rather than a figure from a
> blog post.
>
> Could you confirm, for our account:
>
> 1. The **per-minute rate for `nova-3-medical`, pre-recorded** (`/v1/listen`),
>    and the date that rate took effect.
> 2. Whether any of the options we send alter it — we request diarization,
>    punctuation, paragraphs and smart-format on the same call.
> 3. Whether that rate is billed per audio-minute or per **rounded** unit, and if
>    rounded, to what increment.
>
> Our usage to date is negligible (single-digit calls), so we may not have an
> invoice line item to read it from — a console figure or a written confirmation
> is fine, we just need something we can cite with a date.
>
> Thank you.

## What makes an answer ACCEPTABLE

| | |
|---|---|
| provenance | `invoice` or `console` — **not** the announcement post |
| must carry | a **date** the rate took effect |
| must specify | **pre-recorded**, `nova-3-medical` (not streaming, not plain `nova-3`) |
| rounding | per-minute vs per-rounded-unit, and the increment |

⚠️ **Question 3 is not padding.** If Deepgram rounds each request up to a whole
minute or a 15-second block, then a per-second computation of ours will
under-report every short dictation, and the ledger will drift from the invoice in
a way that looks like a bug in our meter. Better to learn the rounding rule now
than to discover it in B9's first reconciliation.

## The other two rates do NOT need this request

`nova-3` pre-recorded and `nova-3` streaming both have dated, published figures
and can be seeded with `published` provenance immediately. **B3 should proceed on
those two and leave `nova-3-medical` open** rather than block the whole item —
that is the split this file exists to make possible.

## When the answer arrives

1. Seed the row with `invoice` or `console` provenance and the effective date.
2. Leave `DEFAULT_DEEPGRAM_CENTS_PER_MIN` alone — the price table supersedes it;
   deleting it is a separate change with its own historical-comparison argument.
3. Record the answer in `DISCOVERY.md` §D beside the other vendor rates, with the
   date it was obtained and who obtained it.
