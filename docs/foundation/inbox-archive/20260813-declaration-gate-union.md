# RETIRED UNDELIVERED — superseded by events

**Entry:** `### 2026-08-13T02:40:00Z — main took ruling #102's declaration gate`
**Retired:** 2026-08-13, at the relight, without ever being delivered.

⚠️ **THIS IS A CATEGORY THE README DID NOT NAME, AND IT IS WORTH NAMING.** The
retirement rule is *"retired once a session's log shows them received"*. This one
was never received by anybody: it was written at 02:40Z, and the printer that
delivers entries had itself never run — the loop process parsed
`foundation-loop.sh` at 2026-08-12T19:45:02Z, before the printer existed.

**And by the time delivery became possible the notice had become FALSE.** It told
the next session to expect a `RELAY.md` union. That union had already happened:
loop session 03 met it, resolved it correctly, and labelled it in its own commit
subject (`0b2f8473 … — RELAY.md resolved as a UNION`). Delivering it at the
relight would have made the inbox's **first ever delivery a stale notice**, on a
channel whose entire value is that a session can trust what it says at launch.

**So: an entry is retired when it is delivered OR when it stops being true,
whichever comes first — and an undelivered retirement says so, as this one does.**

---

## The entry, verbatim

    ### 2026-08-13T02:40:00Z — main took ruling #102's declaration gate

    Your next `RELAY.md` merge will UNION. It is mechanical by standing rule: take
    both sides, order them chronologically, and verify by `git diff --numstat`
    showing **0 removed in BOTH directions** — never by reading the merged file.
    **Budget one `e2e` re-run (~42m).** Declared in advance so the union is routine
    rather than archaeology.

**Delivered in:** no log. Searched: `grep -l "2026-08-13T02:40:00Z" docs/foundation/logs/*.log` → no match.
**Superseded by:** `0b2f8473`, loop session 03's union merge.
