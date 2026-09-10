# A SUPER_ADMIN's first MFA enrolment is trust-on-first-use

**Status: RECORDED, NOT FIXED. It needs an owner action.** Source: the PR #952
refutation round (ruling #310), finding bypass[0]. It was refuted as a defect
of #952 and kept here as a residual that predates it.

## The residual

Both admin gates admit on `users.mfaEnabled`. For an account that has **never
enrolled**:

- login asks for a TOTP only when `mfaEnabled && mfaSecret`, so the password
  alone mints a session;
- `/api/mfa/enroll` then `/api/mfa/verify-enrollment` need only that session,
  plus a code from the secret enroll just handed back.

So **whoever holds the password of an un-enrolled SUPER_ADMIN can enrol their
own factor and pass both admin gates.** verify-enrollment then revokes every
other session, which signs the real owner out. The owner cannot sign back in
without the new factor.

This is the page gate's **intended** recovery path. `app/admin/layout.tsx`
redirects an un-enrolled SUPER_ADMIN to enrolment "so the operator can
self-recover", and `docs/audit-reports/admin-arc-recon-20260904.md` names it as
the recovery path. PR #952 did not create it. Before #952 the password alone
opened the admin API; after it, the password plus a self-enrolment does. The
PR removes access and adds none.

**What #952's repair does close:** once an account IS enrolled, enroll refuses
(409 `MFA_ALREADY_ENABLED`). Replacing a factor now goes through disable, which
requires the password and the current factor. The window is therefore only
the time before the first enrolment.

## Population: production, read-only counts, 2026-09-10

| population | count |
|---|---|
| users (the positive control) | 198 |
| platform SUPER_ADMIN (`'SUPER_ADMIN' = ANY(products)`), all role DOCTOR | 2 |
| enrolled | 1 |
| **active and NOT enrolled: exposed to this residual** | **1** |
| role `SUPER_ADMIN` (practice RBAC role; neither admin gate admits on it) | 2, both un-enrolled |
| `mfaEnabled` with a null `mfaSecret` (login would skip the TOTP) | 0 |

**Ids are not recorded here.** This repair's production access was limited to
read-only COUNTS, so it did not select the id. The owner can identify the
account (ids only, no emails) with:

```sql
SELECT id FROM users
WHERE 'SUPER_ADMIN' = ANY(products::text[]) AND NOT "mfaEnabled" AND "isActive";
```

## Owner action

1. **Enrol that account now**, from the owner's own authenticator, at
   `https://app.quillmd.com/settings/security/mfa`. Do it on the **app** host:
   `admin.quillmd.com`'s Caddy allowlist 404s `/settings/*` and `/api/mfa/*`,
   and cookies are host-only, so sign in on the app host. After this the
   window is shut: enroll refuses an enrolled account.
2. Until then, that account's password is worth as much as its admin access
   and its MFA combined.
3. **Out-of-band enrolment** would close the residual for every future
   SUPER_ADMIN. That means enrolment gated on something other than the session,
   such as a one-time code issued at provisioning. It is a separate product
   decision (owner class **a**) and is not made here.

Already on the pre-pilot list: `docs/BAA_CHECKLIST.md` (SUPER_ADMIN MFA).
