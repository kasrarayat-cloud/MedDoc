# ROUNDS-C1 — a test that says, in its own assertion, that it is a flake

**Filed 2026-09-08 by the custom-file session to Design/Admin (rounds UI), under
ruling #278.**

> **A TEST THAT SAYS SO IN ITS OWN ASSERTION IS A TEST ASKING TO BE FIXED.**

Its author already did the diagnosis and wrote it into the failure message
precisely so the next reader would not re-derive it. This lane is that next
reader, and re-deriving it would have been the waste the message exists to
prevent — so the finding is handed over **quoted**, not summarised.

## WHAT FAILED

`e2e`, PR **#1055** (`feat/transfer-cert-parameterised`) — a branch that touches
nothing in the rounds UI. `CI`, `a11y-ci` and `secrets-scan` were all green on
the same commit; the branch had been **4 of 4** one commit earlier.

```
✘ [rounds-c1] › tests/e2e/scenarios/rounds-c1.spec.ts:313:7
    Rounds C1 — auth to tokens, flag-ON ›
    the login sub-screens render under Rounds, and the fourth is named unreachable
    (20.7s, then retry #1 at 12.4s)

Error: locator.fill: Timeout 15000ms exceeded.
Error: not on the login form — /login redirected us, so the signup session
       survived clearCookies(). This is the flake; it is not a slow render.
Error: element(s) not found
```

## THE ASSERTION, QUOTED — `rounds-c1.spec.ts:353-357`

```ts
    // This turns a 15s silent timeout into an immediate, diagnostic failure.
    await expect(
      page.locator('#email'),
      'not on the login form — /login redirected us, so the signup session ' +
        'survived clearCookies(). This is the flake; it is not a slow render.',
    ).toBeVisible({ timeout: 10_000 });
```

## AND THE DIAGNOSIS ABOVE IT, ALSO THE AUTHOR'S — `:335-350`

> *"`login/page.tsx:20` does `const session = await auth(); if
> (session?.user?.id) redirect(...)` — **`/login` REDIRECTS AN AUTHENTICATED USER
> AWAY**. `signupFreshUser` above leaves this browser signed IN, and
> `clearCookies()` is what is supposed to undo that. When the session survives
> the clear, the navigation lands on the recovery route, where no Email field
> exists — so the locator waits out its full timeout for an element that is not
> merely late, it is on another page."*

⚠️ **AND THE AUTHOR ALSO RULED OUT THE OBVIOUS SUSPECT, WHICH IS THE PART A
FRESH READER WOULD HAVE SPENT THE AFTERNOON ON:**

> *"The label is `htmlFor="email"` → `id="email"`, a SERVER-RENDERED association,
> so hydration was never the cause here — worth stating, because the
> pre-hydration family is the obvious suspect for this file and is the wrong one
> for this line."*

## WHAT IS ACTUALLY BROKEN

**Not the assertion.** The assertion is the good part — it converts a 15-second
silent timeout into an immediate, named failure, and it is the only reason this
filing could be written without a debugging session.

**The defect is the race it names:** `clearCookies()` does not reliably end the
session established by `signupFreshUser`, so a subsequent `/login` navigation is
redirected away by `login/page.tsx:20`.

Two shapes worth considering, and this lane is **not** choosing between them —
that is Design/Admin's call on their own surface:

1. **end the session deterministically** rather than by clearing cookies — sign
   out through the app's own path, so the assertion is about a state the test
   established rather than one it hopes for; or
2. **make the test's precondition explicit** — assert signed-out before
   navigating, so the failure names the setup step rather than the login form.

⚠️ **A THIRD OPTION IS NOT ON THE LIST, DELIBERATELY:** raising the timeout. The
author's own comment forecloses it — *"it is not a slow render"* — and a longer
wait for an element on another page is a longer wait for the same nothing.

## STATUS

**OPEN, and it is not dismissed.** #278 makes the two intermittent reds different
KINDS: `five narrative shapes` is unexplained and gets a reproduction attempt;
this one is self-diagnosed and gets an owner. *"Probably a flake"* is the sentence
that retires a finding without evidence, and neither of them gets it.

**Cost so far:** one `e2e` run and one retry on a PR that could not have caused
it, on a branch whose citation was otherwise complete.
