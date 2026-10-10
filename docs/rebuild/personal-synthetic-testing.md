# Personal synthetic clinician testing

The existing account `kasra.rayat@gmail.com` is enrolled for prospective sponsored
testing in X-ray, Synthetic North Clinic. Sign in at `https://app.quillmd.com/login/`
with that individual account. Its clinician role, administrator flags, MFA,
documents and department access are unchanged by enrollment. No shared test-account
credentials or new testing budget are required.

Upload a new blank Word form for preparation, or choose an approved department form
and create your own new synthetic document. Typed-note generation and transcription
of reviewed synthetic voice notes on those documents use the existing standing
authority with a $0 account charge. Shared approved forms remain reusable. Existing
documents created by colleagues stay readable in the department; this enrollment
does not sponsor new generation or transcription on a colleague's document. Create
your own document from the same approved form instead.

This applies to ordinary app usage as well as automated testing. Admission binds
the exact account UUID `e1a20625-455d-4603-a874-794327b19d10` and department UUID
`46a5abdd-36f1-41f0-968f-8c09c39d9daa`, an active verified account and an active
owner, clinician or manager membership. New immutable request configurations carry
`testing_actor_enrollment=quillmd-actual-clinician-20261010-v1`. Older configurations
are never relabelled. The synthetic-only restriction, configured provider/model,
purpose, recording limits, independent Word checking, explicit doctor approval,
provider serialization and no-automatic-retry rules remain in force.

Application checks are in `core/testing_authority.py`; ordinary enqueue and sponsor
labels use the same personal-document ownership check. Migration
`0025_personal_synthetic_testing_actor` adds the standing-only database helper and
qualifies the existing standing guards. The historical finite-campaign helper,
allowlists, limits, reservations and unknown outcomes remain intact. Runtime
admission verifies complete function bodies and enabled trigger definitions; backup
qualification requires the same enrollment and ownership. Rollback is refused once
an enrolled request is retained.

Enrollment itself creates no accounts, clinical records, wallet credits or model
requests. Provider costs remain separately recorded under the existing standing
authority. Native Word pagination and microphone behavior still require the owner's
normal device checks.
