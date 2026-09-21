# Current scoped status — September 21, 2026

The dated September 17 checklist below is retained history. The following entries
supersede its stale technical status; no public launch or patient-data approval is
implied.

- The restricted synthetic B2 destination, encrypted offsite workflow and daily
  timer are installed. The first September 21 05:00 UTC scheduled result remains
  future until actual evidence exists. Account renewal remains owner-assisted;
  current evidence expires September 21 at20:16:35.867379 UTC.
- Windows Credential Manager custody, returned-key receipt and the independent-key
  restore of35 tables/225,615 rows/42 files are complete for their recorded scope.
  This does not cover Windows-account/computer loss, offline/LUKS custody or
  whole-host recovery. The prior plaintext-copy cleanup completed; do not repeat
  broad deletion.
- Nine database integrity triggers and the dedicated service/DB roles are
  installed. The latest [internal operations security proof](privileged-operations-security-20260921.md)
  remains applicable; it does not replace independent penetration testing.
- Three loaded ICD-10-CM releases cover October 1,2025 through September 30,2027;
  service-date release checks remain enforced. CPT stays disabled without rights.
- Original WM IOV native Word acceptance, sandbox payment lifecycle,
  invitation/recovery verification and independent-key restore are completed in
  their documented scopes. Natural human dictation and new SOAP native Word
  appearance remain separate checks.
- Authentic attributable provider billing evidence, a reviewed clean production
  profile and Stripe live setup/acceptance, independent security engagement,
  outside-host monitoring/alert receipt, and patient-data agreements/regions/
  retention/processing controls remain external release gates. Internal tests do
  not certify contracts or regulatory compliance.

The [inactive first-release checklist](production-activation-checklist-20260921.md)
extends these requirements with a separate empty production namespace, exact
payment gating and data-preserving rollback. The private rebuilt system remains
intact and synthetic-only.

---

# Patient-data and public-release requirements — fresh QuillMD application

Prepared 2026-09-17 against release `8f8a6763`. The application is private,
synthetic-only, and public app/admin routes stay in maintenance until every row
marked **OWNER** or **PENDING** below is closed with evidence. This document
lists requirements; it does not claim any of them is satisfied unless the
Status column says so with a pointer.

## 1. Processors that would receive or hold real patient data

| Processor | What it receives in the fresh application | Agreement required before real PHI | Status |
| --- | --- | --- | --- |
| Anthropic (`api.anthropic.com`, `claude-sonnet-4-6`) | Source notes and form labels for answer generation | Business Associate Agreement (BAA) countersigned; confirm zero-data-retention / retention terms and processing region | **OWNER** — request recorded 2026-05-05, no countersign on file |
| Deepgram (`nova-3-medical`, prerecorded) | Raw dictation audio | BAA countersigned; confirm audio retention and region | **OWNER** — none on file |
| Hosting provider (VPS holding the database, originals, exports, receipts, mail outbox, backups) | All PHI at rest | BAA or migration to a BAA-covered host; documented physical/region controls | **OWNER** — none on file |
| Backblaze B2 (offsite encrypted backups, once approved) | Encrypted ciphertext of database and documents | BAA (available from Backblaze) before any real-data backup leaves the host | **OWNER** — destination not yet approved |
| Resend (invitation, verification and recovery email) | Clinician email addresses and links only; no clinical content in the fresh application | No PHI today. A BAA becomes required only if any patient document or name is ever emailed | Not blocking; keep the no-PHI email rule in code review |
| Stripe (wallet top-ups) | Payment data only, no PHI | Not a PHI processor; PCI handled by Stripe Checkout | Not blocking |
| OpenAI (adapter present, key rejected, not configured) | Nothing while unconfigured | BAA before ever enabling | Not blocking; keep disabled |

No real patient record may be created, uploaded, dictated, generated or
exported until the OWNER rows above are closed. The public marketing site
already promises signed BAAs before covered-entity PHI flows; enabling real
data earlier would make that representation false.

## 2. Processing locations, retention and deletion (decisions to record)

| Requirement | What must be written down | Status |
| --- | --- | --- |
| Processing regions | Region for the VPS, Anthropic, Deepgram and the offsite bucket; confirm each is acceptable to the covered entity | **OWNER** |
| Provider retention | Anthropic/Deepgram retention of prompts, audio and outputs under the signed terms | **OWNER** with the BAAs |
| Application retention schedule | How long originals, exports, provider receipts (raw model output), audit rows, mail outbox and backups are kept; a reviewed deletion procedure that does not break the immutable financial ledger | PENDING — draft with counsel; today nothing is deleted |
| Data-subject requests | Procedure for access, correction and deletion requests; who executes them and how the audit trail records them | PENDING |
| Breach notification | Contacts, clock, and evidence collection procedure | PENDING |

## 3. Technical controls (status is evidence-based)

| Control | Status | Evidence / remaining |
| --- | --- | --- |
| Dedicated service OS identity, no capabilities, secrets inaccessible to services | DONE | `.runtime/os-identity-activation.json`; same-PID denial probes |
| Database runtime role without DDL/superuser; immutable financial rows (8 triggers) | DONE | `docs/rebuild/database-role-policy.md`, restore checks |
| Administrator MFA (TOTP) and separate admin listener | DONE | `.runtime/admin-current-release-verification-after-backoff.json` |
| Organization/department isolation on every route, file and export | DONE (internal tests) | Fresh live check 2026-09-17 (`review-report-attempt2.json`, cross-org 404s); independent retest PENDING |
| Encryption at rest for the fresh PostgreSQL volume and `/var/lib/quillmd` | **PARTIAL — encrypted 2026-09-18, key on host** | Declared act (attempt 2, target `3eac783a`) judged 29/29: database, WAL, files, mail, proofs and service temp on a LUKS2 volume (aes-xts-plain64, 512-bit, argon2id); closed-volume drill passed; pre- and post-act encrypted backups restored with no decrypted files written (`storage-encryption.md`). Before real data: vault the recovery passphrase; decide key custody (protection against disk-level access needs slot 0 removed, re-encryption and the key file removed); destroy the plaintext rollback snapshot, pre-cutover `rebuild/.runtime/files`/`mail` and old restore-check copies (`owner-actions.md` §5). Host swap and journald stay host-level |
| Encrypted backups with isolated restore | DONE on the same VPS | `.runtime/restore-checks/backup-restore-*.json` |
| Offsite backup, separately escrowed key, measured RPO/RTO | **OWNER + PENDING** | Destination, scoped key, custodian; then round trip via `rebuild/ops/offsite_backup.py` |
| Public ingress with TLS, security headers, rate limits | PENDING | Public routes are 503 maintenance by design until release |
| Independent penetration test and finding retests | **OWNER + PENDING** | `docs/rebuild/pentest-scope.md`; reviewer identity, key, window |
| Provider cost reconciliation before paid use | **OWNER** | Authentic invoice/usage exports; see `cost-definition.md` |
| CPT terminology | Disabled by design | Remains disabled until a license and usage rights are verified |
| ICD-10-CM refresh | Maintenance gate | Loaded set expires 2026-09-30; import the October release before then |

## 4. Release sequence

1. Close the OWNER rows in sections 1 and 2 and file the executed agreements
   under owner-controlled storage (never in git).
2. Complete independent key custody for the encrypted fresh data paths
   (`owner-actions.md` §2), and decide on disk-level protection. The plaintext
   copies were destroyed on 2026-09-18 (`storage-encryption.md`). Then verify
   the offsite round trip with key escrow.
3. Complete the independent penetration test and retest every finding.
4. Complete native Word acceptance (`word-acceptance-checklist.md`).
5. Only then lift maintenance on public routes and enable real patient data,
   through a declared deploy with the synthetic-only gate removed in the same
   reviewed change.
