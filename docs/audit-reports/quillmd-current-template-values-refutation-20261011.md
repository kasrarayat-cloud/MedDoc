# QuillMD wrist field values: diagnosis and pre-installation evidence

2026-10-11. This report describes the finished code review and retained evidence;
it is not a claim that the candidate has already been installed or that an
actual-account browser verification has passed.

## Confirmed incident

The exact finalized encounter is `3faf3422-826c-4056-8823-cc7a24b5de9d`, owned by
`kasra.rayat@gmail.com` in Synthetic North Clinic / X-ray. Its original export
SHA-256 is `9ce5b9fcd96b1aabab514a76b41aa1813462a0d86635fb7805d239cdc469b2ab`;
the stored document matches the user's download hash.

Generation job `0fe468eb-d63e-4e20-887e-6462639f7283` was created at
05:35:12.120636 UTC, started at 05:35:13.009174 and finished at
05:35:17.760581. It selected immutable version 1,
`b93fd1ec-3d18-4d22-8bbf-0c1fc8f38083`, without semantic definitions or a
preparation receipt. It retained zero semantic stage receipts and the legacy
`extractive-v7-custom-sentence-evidence` prompt version.

The serving release was `1057061d1fd13d7abd3deb7bdd0848e214f56a1c`. The worker
PID, kernel start time, systemd invocation and reviewed environment-file hash
match that release's installation evidence and remained unchanged across the
job. Old jobs have no direct executing-release field, so this is explicitly
process continuity evidence. New jobs now record queue release in immutable
configuration and executing release in an append-only audit event.

The retained legacy provider response selects source-unit identifiers rather
than assigning semantic answers. Replaying that response through
`generation.validate_tab_selections` reproduces the full-sentence answers:
the validator's selected quote becomes `answer.text`. That is the first wrong
stage. The saved answers and corresponding DOCX cells are identical. Neither a
cached export nor an export-time evidence substitution explains this incident.

QA encounter `f83fa43d-0fb8-4008-af68-6b058abb7a79` instead used semantic
version 3, `b6ad0eb7-5b8c-4d9f-bbff-8c8dd0774d0e`, and three separate roles.
Both accounts were admitted by the existing standing synthetic-testing
authority on the same serving release. Template selection, rather than account
admission, chose different pipelines.

The incident job took 4.751407 seconds and retained $0.009062 of provider cost;
its account charge was $0. The cited semantic QA job took 19.114129 seconds and
retained $0.067878 provider cost, with $0 account charge. These are individual
observations, not a statistical performance or price claim.

## Repair boundaries

New-document forms expose one current usable version per tenant-scoped
template. An existing semantic version takes priority over legacy versions;
incomplete semantic approval metadata withholds the form rather than silently
falling back. A locked POST recheck rejects stale selections and retains typed
notes. Historical encounters, approvals and versions remain unchanged.

The generic label editor cannot silently create a new legacy version from an
approved semantic form. Unchanged labels are a no-op; semantic changes require
the existing separately reviewed definition workflow.

The semantic validator retains exact written-number source spans. Code may
normalize a complete supported unsigned number only for an approved numeric
destination. Approved types, ranges, source scale, evidence references, conflict
handling, destination permissions, checker review and stored-proof validation
remain gates. No patient-specific mapping or manually edited answer is added.

## Independent refutation and verified corrections

A finished-diff refuter demonstrated that updating execution provenance inside
`Job.config` violates the existing PostgreSQL immutable financial-configuration
trigger. The real PostgreSQL test reproduced that refusal. The repair leaves
configuration unchanged after enqueue and appends one `job.running` audit event
inside the atomic claim. Idempotent replay neither relabels nor re-audits a job.
The corrected selection/provenance refutation found no demonstrated additional
failure. Its private receipt SHA-256 is
`343574f850e76bc1c462928e051d80f08f970c0994c9415320441436485a5635`.

The independent numeric refutation demonstrated clipped fractions, ranges,
decimal and Unicode fragments being accepted as complete integer values, and
teen denominators being rejected due to shorter regex alternatives. It also
identified rejection of a valid existing digit proof for a count followed by a
separate duration modifier. These concrete counterexamples are required
regressions before the numeric diff is considered finished.

Protected incident evidence SHA-256:

- Database/retained-response/export diagnosis:
  `c8193ef1f251a943c33e638cc7e43d604698846eee37f2a36490e2f5c1014335`.
- Executing-release continuity proof:
  `3bf678e61c8b29b253a218d96c262abc60bcf41e3d6e71d891f95b550708f2ea`.
- Legacy validator replay and saved-answer/DOCX equality:
  `856faf9358e9373bb07eb22da1dc857a7c4cfa6234d89187b7084db9d7219584`.

Filled synthetic documents and raw provider responses remain in protected
runtime storage; they are not repository fixtures. Installation and subsequent
browser outcomes must be recorded separately against the exact merged release.

## Finished validation before publication

All demonstrated numeric counterexamples were repaired and independently retested. The final pinned refutation found no demonstrated remaining failure across 165 probes, 13 legacy proof/byte comparisons and 84 semantic validator tests. The receipt SHA-256 is `a18c2540372f18b7558ac5f8e9a79f779ed9b88dd04f375a8e5e601f9090258d`.

The lead also ran the 53 selection/provenance/navigation/preparation checks against isolated PostgreSQL, then all 84 final semantic checks. An earlier provenance implementation failed the existing immutable-configuration trigger and was corrected before publication. This is targeted fixture evidence; served actual-account HTTPS and Word verification remain subsequent gates.
