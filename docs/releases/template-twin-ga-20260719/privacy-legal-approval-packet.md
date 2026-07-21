# Template Twin Privacy/Legal approval packet

Status: **HUMAN PENDING — PHI AND PRODUCTION ROLLOUT BLOCKED**

## Current evidence summary

- The committed 2026-06-10 processor audit records no countersigned Anthropic, Deepgram, OpenAI, Resend, or hosting BAA on file at that time.
- The same audit identifies a potential raw-audio OpenAI fallback after qualifying Deepgram failures and confirms PHI-bearing PDF delivery through Resend.
- This release program has used no real PHI and has not opened PHI-bearing backup contents.
- Template intake is designed to quarantine raw bytes, require malware attestation, minimize metadata, preserve immutable lineage, and reject unsafe/hidden content, but production operational evidence remains incomplete.
- Legal hold, account deletion, patient/document export, data-subject request, breach-response, and provider-retention decisions require authoritative owner confirmation.

## Decisions required

| Topic                   | Evidence required                                                                                     | Current status |
| ----------------------- | ----------------------------------------------------------------------------------------------------- | -------------- |
| HIPAA and BAA status    | Executed agreements and effective dates for every PHI processor and host                              | HUMAN PENDING  |
| Provider data handling  | Current models, regions, training/retention settings, fallback routes, subprocessor list              | HUMAN PENDING  |
| Retention and deletion  | Approved schedules for raw uploads, quarantine, templates, outputs, audit, backups, and provider logs | HUMAN PENDING  |
| De-identification       | Approved standard, responsibilities, validation, and re-identification controls                       | HUMAN PENDING  |
| Legal hold              | Hold initiation, scope, precedence over deletion, release, and audit trail                            | HUMAN PENDING  |
| Account deletion        | Physician/practice/patient effects across primary, object, queue, audit, and backup stores            | HUMAN PENDING  |
| Audit access            | Authorized roles, immutable access history, retention, and disclosure workflow                        | HUMAN PENDING  |
| Breach response         | Named incident owner, counsel/privacy contacts, containment and notification decisions                | HUMAN PENDING  |
| Patient/document export | Authorized requester, identity verification, format, completeness, and audit trail                    | HUMAN PENDING  |
| Data-subject requests   | Intake, identity, search scope, exceptions, response deadlines, and ownership                         | HUMAN PENDING  |

## Mandatory constraints unless explicitly approved otherwise

- No real PHI enters a provider or the release QA environment.
- No provider fallback may expand PHI egress beyond the approved processor inventory.
- No physician/patient document, audio, screenshot, credential, environment file, or secret-bearing evidence enters Git.
- Synthetic provider results do not authorize PHI.
- Unsupported templates and ambiguous completed-document regions fail closed.

## Human decision

- Decision: `APPROVE` / `REJECT` / `REVISE`
- Final exact SHA: **\*\*\*\***\*\***\*\*\*\***\_\_\_\_**\*\*\*\***\*\***\*\*\*\***
- Evidence-manifest SHA-256: **\*\***\*\***\*\***\_**\*\***\*\***\*\***
- Name and role: **\*\*\*\***\*\*\*\***\*\*\*\***\_**\*\*\*\***\*\*\*\***\*\*\*\***
- Date/time and timezone: **\*\***\*\***\*\***\_\_\_\_**\*\***\*\***\*\***
- Approval record: **\*\*\*\***\*\***\*\*\*\***\_\_\_**\*\*\*\***\*\***\*\*\*\***
