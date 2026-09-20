# Stripe hosted-choice and exit-status repair — 2026-09-20

## Observed hosted Checkout failure

The primary runner created one authentic sandbox Checkout session, then stopped
before payment because its visible-button selectors did not open Card fields.
The failed attempt remains unchanged. Engineering inspected the same session;
it did not create another checkout for diagnosis. Private evidence is retained
in `.runtime/stripe-payment-20260920/hosted-pointer-inspection2.json` and the
preceding hosted inspection reports.

The visible Card radio was covered by its own accordion overlay button. That
button's own box was hidden, so its locator reported invisible, while its
expanded pointer area intercepted `radio.check()`. A natural pointer click at
the visible radio's center opened the actual card fields. USD also appeared as
a `$5.00` choice; an already-selected choice could be disabled with `is-active`.

The operator helper now selects an offered, unique USD choice or retains the
already-active disabled USD choice. When Card fields are hidden, it inspects
`elementFromPoint` at the visible radio's center and clicks only when the hit is
that radio or the unique identified Card overlay/control descendant. An unrelated
overlay refuses. It waits for actual visible card fields afterwards. It neither
receives card data nor submits payment. The runner calls it after the contact
field appears and before filling card information. Application code, service
configuration, checkout count limits and old evidence are unchanged.

## Observed mutation-wrapper false assurance

The separate primary continuation later returned exit2 after actual sandbox
funding, duplicate receipt, refund and decline checks, because supplemental
acceptance cases remained incomplete. Its report is preserved as
`.runtime/stripe-payment-20260920/primary-continuation.json`. The generic wrapper
incorrectly printed this original warning:

```text
EXIT 2 — the command REFUSED before acting (usage / bad arguments).
Nothing was opened and nothing was written. Fix the invocation and
re-run; there is no partial state to reconcile.
```

Exit2 is a child-defined status; it cannot establish absence of changes. The
wrapper now preserves the status and requires reading the child's semantics and
execution evidence before any rerun. Its declaration gates, execution/watchdog
logic and other status branches are unchanged. The original report and warning
remain historical evidence; payment state must not be reset to match the warning.

## Targeted verification

The local Chromium fixture recreates a button whose own box is hidden but whose
pseudo-element intercepts the radio. It demonstrates the old `check()` timeout,
then proves that the guarded natural pointer opens the fields. Cases also cover
already-active USD, already-visible Card fields, owned descendants, unrelated
overlays, ambiguous USD choices and disabled-but-unselected USD.

The wrapper test copies the actual wrapper and unchanged gate/watchdog libraries
into an isolated temporary Git repository with a committed synthetic declaration.
A real child writes a canary and exits2. Before repair, that test failed against
the false no-effects warning after proving the canary existed. After repair it
passes. Further cases preserve exit0, another failure, timeout-status wording and
the modified-declaration refusal before child execution. The initial test-harness
path-resolution typo was corrected before the meaningful failing reproduction.

```text
node --test rebuild/ops/test_stripe_verification_card_choice.mjs rebuild/ops/test_stripe_verification_navigation.mjs rebuild/ops/test_stripe_verification_outcome.mjs rebuild/ops/test_ruled_mutation_exit.mjs
```

Result: **30 tests passed, zero failed or skipped**. These isolated tests make no
Stripe or other provider calls, access no application accounts and submit no
payments. The temporary repositories, canaries, browsers and local servers are
removed or closed afterwards. Real Stripe acceptance belongs to the separately
recorded primary/supplemental evidence; these tests alone do not establish it.
