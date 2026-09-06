# A POSITIVE CONTROL IS THE ONLY ARM A BROKEN MOCK CANNOT FOOL

**Ratified 2026-09-04.** When a test replaces a dependency, every result
downstream of that replacement is a fact about **the replacement** until
something independent says otherwise. A mock that is subtly incomplete does not
error — it makes the code under test take its FAILURE path, and the failure path
is usually exactly what the test was written to see.

> **The arm that asserts the HEALTHY case is the only one that can tell "the
> guard fired correctly" from "the mock broke and everything fired".**

## THE REFERENCE CASE

Ruling #182 split a session check into two answers: a DEFINITIVE "revoked"
returns null, and a "the database could not answer" retains the token and marks
it. The arms drove the real callback with `@meddoc/db` mocked, so the real
`validateSession` would run against a controllable prisma.

Three arms asserted the interesting states. A fourth asserted the boring one:

    POSITIVE CONTROL: a live session is returned unmarked  ❌ expected true to be undefined

The mock supplied `findUnique` and `deleteMany`. The real `validateSession` also
calls `update` — it touches `lastSeenAt`. So **every** call threw
`userSession.update is not a function`, every token came back marked
unverifiable, and the two "cannot tell" arms passed **for the wrong reason**.

⚠️ **Read quickly, that output says the fix works.** Two arms green, on exactly
the behaviour being introduced. The only thing that disagreed was the arm that
expected nothing to happen.

## WHY THE OTHER ARMS COULD NOT CATCH IT

Because a broken mock and a working fail-closed guard produce the **same
observable**. Both make the code take the refusal path. An arm that asserts
"the refusal happened" is satisfied by either, and no amount of adding more
refusal arms distinguishes them — they all share the defect.

**The healthy case is the only input whose correct answer DIFFERS between the
two explanations.** That is what makes it a control rather than one more test.

## THE SHAPE

    it('POSITIVE CONTROL: <the boring, healthy case> — the arms below are not vacuous', …)

- Assert it **FIRST**, and say in its name what it is protecting.
- Its failure message should say *the arms below are meaningless*, not
  *this case is broken* — because that is what it actually means.
- ⚠️ **A control aimed where the answer is predetermined is not a control**
  ([canon 31](31-a-detector-can-be-blind-to-the-thing-it-most-exists-to-wat.md)).
  The healthy case qualifies precisely because a broken mock cannot produce it.

## AND THE DEBUGGING MOVE THAT FOLLOWS

When a positive control fails, **do not adjust the assertion.** Print what the
code under test actually saw. Here that meant capturing the swallowed
`console.error` to a file, which named the missing method in one line:

    error: "__vite_ssr_import_0__.default.userSession.update is not a function"

⚠️ **A refusal caused by your own substitution is evidence about your
substitution** ([canon 71](71-a-refusal-caused-by-my-own-substitution.md)) — and
the substitution here was a mock, which is the most common one there is.
