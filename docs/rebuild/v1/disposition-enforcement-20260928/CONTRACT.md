# Authority and journal contract

This candidate implements one adapter, `empty-unreviewed-draft-v1`. It is not an approved retention schedule, production activation procedure, external-copy deletion adapter or restore-release mechanism. The previous preparation rows keep their review-only meaning. The installed application and its data were not changed.

## Trust and policy admission

`QUILLMD_DISPOSITION_ENABLED` defaults to0. Namespace, authority keys, checkpoint keys, journal verification keys, journal writer identity/private key and journal path all default unset. The installation must receive independently verified public keys through its normal configuration authority. The application cannot prove that a key belongs to counsel merely because it is configured. An external owner/counsel process must establish that association; no generated key, schedule or duration ships with the product.

Envelopes have exactly `key_id`, `body`, `signature`. Ed25519 signs the UTF-8 canonical body prefixed with `quillmd.disposition.signed.v1` followed by a zero byte. Canonical JSON sorts keys, uses compact separators, preserves Unicode and rejects nonfinite numbers. Duplicate members, extra fields, unknown key IDs, invalid signatures and oversized envelopes refuse.

The policy body binds contract `disposition-policy-v1`, canonical policy/namespace/department UUIDs, exact adapter, anchor `created_at`, an externally supplied positive `minimum_age_seconds`, timezone-aware `not_before`/`expires_at`, schedule-document SHA-256 reference and purpose `authorize_prospective_empty_draft_disposition`. The fingerprint identifies the signed reference; it does not authorize by itself. Admission must occur before the prospective cohort starts. Execution repeats key, signature, time, scope and exact source checks. The policy's expiry governs new execution; old valid journal entries are verified at their recorded write time and remain suppression instructions.

The verified MFA admin console at `/console/disposition-execution/` derives identity from the session, never from an actor UUID submitted in a form. One custodian prepares the exact eligible target; another approves its digest. Both must remain active verified custodians at execution. Execution checks the entered target ID against the approved instruction. A nonempty or changed target, any job/batch/reservation-bearing graph, prior review/preservation evidence or historical hold refuses before journal append. The exact-row snapshot is PostgreSQL's own JSON representation; its clinical payload is necessarily empty.

## Journal and crash boundary

The configured file must be private, regular, singly linked, and outside both the selected state directory and media directory. No relative path, final symlink, group/world permissions, incomplete final line, invalid signature, duplicate instruction/target, broken chain or oversized file is accepted. Current bound is1000 entries /8MiB. Crossing it refuses; journal rotation/compaction requires a separately reviewed design.

Each signed entry binds namespace, sequence, prior hash, write time and the complete scoped instruction including the signed policy and distinct maker/reviewer metadata. A separately trusted checkpoint signer supplies `disposition-journal-checkpoint-v1`, namespace, exact sequence/head hash and an explicit issuance/expiry window. New execution needs the exact current head checkpoint. The application does not issue that checkpoint or claim that a local file path establishes independent custody.

Execution persists and fsyncs the entry before deleting anything. Its database transaction then imports an immutable tombstone, deletes precisely the approved empty Encounter row and appends completion/audit records. A durable intent followed by DB rollback remains unavailable to clinical reads and processing through the verified journal deny-list. Exact last-instruction retry accepts its immediately preceding checkpoint, verifies the identical instruction, fsyncs again and completes idempotently. No partial journal is automatically truncated or repaired.

Record signatures and chaining detect corruption and a conflicting supplied checkpoint detects a missing prefix/tail. A valid historical prefix by itself does **not** prove latest-head freshness; ordinary deny-list reads do not contact an external checkpoint authority. Independent journal custody, reliable shared filesystem locking/durability, fresh checkpoint issuance, backup selection and protection from operator rollback/unconfiguration are required deployment assumptions and unfinished external integration. This candidate makes no general tamper-proof storage or crash-recovery claim after loss of both the DB completion and independent durable intent.

## Restore and preservation

Replay requires a selected quarantined restore instance, the full signed journal and an exact valid independent head checkpoint. It imports tombstones only. A conflicting restored clinical row remains stored and becomes unavailable; replay never deletes it, marks the restore admitted, releases quarantine, or removes an external copy. The existing preparation record's `journal_freshness_verified=false` is not rewritten into authority.

The additive0030 migration preserves every previous guard/function body. New records are append-only, with truncate guards; reversal refuses any new evidence. Additional Encounter guards deny resurrection and require an exact reviewed empty snapshot for deletion. Job/batch/code inserts lock the source row before checking a tombstone. Existing financial, audit, held/finalized and immutable evidence guards remain in force. SQL checks are an independent structural boundary; PostgreSQL does not authenticate Ed25519 keys or external counsel policy, so DB shape/hash alone never grants application execution authority.

Broader clinical records, recordings, finalized exports, signatures/consent, patient identity, account/financial/audit/history disposal, provider copies, downloaded exports, backup expiry, external journal adapter/custody and safe restore admission remain outside this adapter. B-L6 as a whole remains open.
