# Personal synthetic clinician testing enrollment — 2026-10-10

Direct owner instruction received in this session:

> Explain this restriction concretely. Show the authorized test doctor’s email and department name, the account and department currently being used, and where the restriction is enforced. Do not reveal passwords or keys.
>
> Clarify whether this affects only the automated test runner or ordinary app usage.
>
> If the newly created synthetic doctor account needs to be linked to testing, reconcile that through the supported procedure within my existing authorization. Preserve tenant isolation and historical records. Do not ask for another testing budget or require ordinary users to share the automated test account.

The account was recovered, not newly created. The served active, verified nonstaff
clinician is `e1a20625-455d-4603-a874-794327b19d10`, `kasra.rayat@gmail.com`, in
existing X-ray department `46a5abdd-36f1-41f0-968f-8c09c39d9daa` of Synthetic
North Clinic. The served standing test owner is `2247e403-a830-4807-9a34-6903b95a0f50`,
`doctor@synthetic.quillmd.invalid`, in the same department. The older QA UUID pair
remains in the source allowlist but its account is absent from this served database.

This instruction authorizes reconciling the recovered clinician's own exact
account/department pair under the existing prospective standing testing authority
`quillmd-standing-testing-20261009-v1`; no new budget, wallet credits, shared test
credentials, new tenant, administrator role or provider purchase. Existing standing
authority and synthetic-only/provider/purpose/tenant/active-membership controls
remain effective. Old finite campaign actors and histories remain unchanged.

There is no existing account-link setting, enrollment command or supported UI.
Use the repository's supported reviewed forward-migration/native installation
procedure to make this one exact standing-only enrollment, then verify both
application and database admission without provider calls or account login.
No password reset, credential read, user/session/MFA/membership mutation, clinical
write, model call, token read or unrelated project change is authorized or needed.
