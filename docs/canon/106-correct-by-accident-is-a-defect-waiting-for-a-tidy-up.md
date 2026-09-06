# CORRECT BY ACCIDENT IS A DEFECT WAITING FOR A TIDY-UP

**Ratified 2026-09-04.** Code that does the right thing for a reason nobody
wrote down is not safe code. It is code with a **latent trigger**, and the
trigger is usually somebody improving it.

> **When you find behaviour that is right by accident, NAME THE ACCIDENT in a
> comment and ARM THE TIDY-UP with a test whose mutation IS the tidy-up.**

## THE REFERENCE CASE

Ruling #182 made a session whose validity could not be verified return a token
with the **identity withheld** — `user.id`, `role`, `practiceId` all undefined —
so every consumer's existing `if (!userId) return 401` refuses.

The middleware gate read:

    const isLoggedIn = !!auth?.user;

`auth.user` is an OBJECT. An identity-less user object is still truthy, so an
unverifiable session was **let through** to the page, whose `getSession()`
refuses it 503 with the cookie intact. That is exactly what the ruling requires:
a blip must cost a retry, not a re-login.

**It was also entirely unintentional.** Nothing in that line knew about
unverified sessions; it predates them. And the obvious improvement —

    const isLoggedIn = !!auth?.user?.id;      // surely this is what we meant

— would have flipped an unverifiable session to `false` and **redirected the
doctor to `/login`**, telling them they were signed out when they were not. The
eject-on-a-blip the ruling exists to forbid, reintroduced one layer above the
code that forbids it, by a change that looks like a strict improvement in every
review.

## WHY "IT WORKS, LEAVE IT" IS THE WRONG READ

The behaviour is load-bearing and its cause is invisible. Three things follow:

- **A reviewer cannot see the dependency.** The line mentions no session state,
  no marker, no ruling. There is nothing to notice.
- **The tidy-up is attractive.** Tightening a truthiness check to the field you
  actually care about is a standard, correct-looking refactor.
- **The failure is silent and clinical.** A doctor sent to `/login` mid-shift
  concludes they were signed out; nothing errors, nothing logs, and the next
  request would have worked.

## THE SHAPE

    // ⚠️ THIS IS CORRECT BY ACCIDENT AND HERE IS THE ACCIDENT: <why>.
    // Tightening this to <the obvious improvement> would <the harm>.
    if (unverified) return true;             // the case, NAMED
    const isLoggedIn = !!auth?.user?.id;     // and now the general check is safe

Then arm it, and **make the mutation the tidy-up itself**:

    M · delete the named case → the arm must RED

That is a stronger proof than a generic mutation, because it demonstrates the
gate catches *the specific edit a future reader is most likely to make*.

⚠️ **AND PREFER REMOVING THE ACCIDENT TO DOCUMENTING IT.** In the same ruling,
one `auth()` consumer read `user.name || user.email` and made no identity check
— which would have needed an exemption row. Stripping `name` and `email` from an
unverified session as well removed the exemption instead of explaining it. A
documented exception is a thing somebody must keep believing; a removed one is
not.

**Related:** [canon 72 — pin properties, not
spellings](72-pin-properties-not-spellings.md) is the same hazard pointed the
other way: there a gate DEMANDED a defective spelling and would have red-flagged
the fix. Here the code IS the accident and the gate must protect it. Both come
from the same question — *if somebody improved this, what would happen?*
