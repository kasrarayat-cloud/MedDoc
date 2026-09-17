# Private account recovery and session continuity

Recovery uses Django5.2's PasswordResetConfirmView and token generator, a30-minute expiry, the established password validators and Argon2 hashing. [Django authentication reference](https://docs.djangoproject.com/en/5.2/topics/auth/default/#django.contrib.auth.views.PasswordResetConfirmView).

- `/recovery/` accepts an email address and returns the same message for eligible, unknown, unverified, inactive and throttled accounts. IP/address request limits apply. Only verified active accounts with usable passwords get links.
- Links use the configured origin, never a request Host header. Django exchanges the raw token in the URL for a session-held token before rendering the password form. POST requires CSRF. Completion locks/rechecks the account, rejects expired/reused tokens and changes the password once. Previous authenticated sessions become invalid; recovery does not sign the user in automatically.
- Staff password recovery also requires the existing confirmed authenticator. A just-used code cannot then be reused at login. Password recovery does not remove or replace MFA.
- `/verification/resend/` lets an unverified doctor account replace expired/lost verification links. Previous unused tokens are invalidated. No welcome credit is granted until verification succeeds; the ledger's one-grant-per-user guard remains authoritative.
- Organization owners/managers can revoke an unused invitation. Expired/revoked invitations cannot be accepted. An invitation's issuer must still have invitation authority when it is accepted. Existing accepted department access is changed through membership controls.
- When an authenticated session expires, sign-in returns to the saved page using a validated local path. It never replays a prior POST. Only explicitly saved drafts are durable; unsaved browser fields are not stored in localStorage or claimed to be recovered.

## Delivery status

Account emails remain in the private file outbox until sender verification and actual controlled recipient delivery pass. The UI labels that state. Existing send-only Resend credentials cannot query sender-domain status. Provider acceptance, inbox delivery, and email ownership confirmation are separate events. Recovery audit records contain purpose/outcome/user identifiers but no passwords, tokens, raw provider errors or clinical material.

## Lost administrator authenticator

There is deliberately no public email-only MFA reset. A verified platform operator must establish the administrator's identity through a previously established independent channel, record approval and the account UUID, revoke existing sessions, and supervise replacement enrollment through a reviewed operational action. Never transmit an enrollment secret or private outbox token in audit logs, PRs or chat. This identity-recovery operating procedure and responsible personnel must be finalized before non-synthetic onboarding; possession of an unverified email request alone is insufficient evidence.

## Evidence

`core.tests.test_recovery` covers token expiry/reuse, two sessions opening one token, old session invalidation, disabled/unverified/unknown users, CSRF, admin MFA and replay, safe return URLs, verification resend/one credit, invitation revocation and cross-department denial. Private browser recovery evidence is recorded in the continuation checkpoint. These are synthetic tests, not proof of external email delivery.
