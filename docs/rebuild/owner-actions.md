# Owner actions

Updated 2026-09-19 (application release `6d73c5e9026d974053365468101c2f7921544c6c`, verified from `/health/` on both surfaces; repository/harness
revision is separate and ahead — see `CHECKPOINT.md`). **Private engineering is complete. Everything below is an owner action; nothing on this
list can be done for you.** The two items that gate the most are **1 (native Word review)** and **5 (one controlled email recipient)**.

This is the single list of what only the owner can do. Engineering does everything else
without asking. The private service stays synthetic-only, and the public routes stay in maintenance, until the release evidence supports a
change. Never paste a secret into chat, a shell command line, Git, a ticket or a screenshot. Every secret location below is a file readable only
by its owner account.

Your access is SSH as `root` to `147.189.172.8`; the `claude` account has no SSH key. On first connection, check that the host key matches one
of these fingerprints before you accept it:

- ED25519 `SHA256:e0eCC1AeF1xUQ8conZqXbXjTVa9YhGwzQzz0GSctqIY`
- ECDSA `SHA256:ie7lReVrF69+Zt1C7W5ow0HPLTFozvyb4sROMff/6YY`

The commands below are for Windows PowerShell, which includes OpenSSH.

## 1. Review the Word documents in native Microsoft Word

**STATUS: PENDING. It has not been performed, and nothing in the record claims otherwise.**

This blocks native Word appearance acceptance. No renderer on the VPS can establish it, and none is substituted for it. **Nothing about
native Word appearance is accepted until you have actually done this.**

**USE THE 2026-09-19 PACKAGE. The 2026-09-18 one is superseded** — your inspection found three things and all three reproduced, two of them
about that package's own labels. The new archive ships each real export TWICE, before and after the table-pagination repair, because the repair
changes no visible character and only Word can show the difference. It also renames the two SDK fixtures to what they actually are and corrects
three checklist claims, including the font one: **there is no font defect and none should be raised.**

⚠️ The layout repair is merged and tested but **NOT YET DEPLOYED**, so files 03 and 05 are what the exporter *will* emit, not what the running
service would hand a doctor today. And a genuine missing-answer document and a genuine long-mapped-answer document are **not in this package** —
see `CHECKPOINT.md`; six attempts hit the clinical review model rather than the exporter, and none finalized.

Run the four lines below in Windows PowerShell exactly as written. The first creates the destination, the second retrieves the archive, the
third decides whether it arrived intact, and the fourth unpacks it only if it did.

    $dest = "$env:USERPROFILE\Downloads\quillmd-word-review"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    scp root@147.189.172.8:/opt/meddoc-pro/rebuild/.runtime/word-review-package/quillmd-word-review-20260919.zip "$dest\quillmd-word-review-20260919.zip"

    $expected = 'D88B397D8468453C5B3C406635A2538ABA0A0819EEC60C6909CF0AA798CFC66C'
    $actual = (Get-FileHash "$dest\quillmd-word-review-20260919.zip" -Algorithm SHA256).Hash
    $size = (Get-Item "$dest\quillmd-word-review-20260919.zip").Length
    if ($actual -eq $expected -and $size -eq 315232) {
        Expand-Archive "$dest\quillmd-word-review-20260919.zip" -DestinationPath "$dest\quillmd-word-review-20260919"
        "ARCHIVE VERIFIED AND UNPACKED"
    } else { "MISMATCH - do not open; tell engineering. actual=$actual size=$size" }

Expected: `ARCHIVE VERIFIED AND UNPACKED`, from **315,232 bytes** hashing to that value. Open `01` beside the BEFORE/AFTER pairs
(`02`/`03` and `04`/`05`) and complete the checklist, section **F2** included. ⚠️ The unpack is **inside** the check on purpose — an earlier draft left it outside, so a mismatched archive printed the warning and then unpacked anyway. The checksum was re-verified on the host on 2026-09-18
(`sha256sum` on `rebuild/.runtime/word-review-package/quillmd-word-review-20260918.zip`). If the comparison fails, the file was altered or
truncated in transit — do not open it.

Then open each `.docx` in desktop Microsoft Word and work through `word-acceptance-checklist.md` inside the archive. Mark each row ACCEPT or
REJECT and report your Word version and build (File > Account > About Word). `SHA256SUMS.txt` inside lists every review file with its own hash.

The archive holds the blank WM IOV original, the fresh and previous live exports, two fixture exports, the checklist and the hash list. All
content is synthetic. It holds no credentials and no runtime files.

## 2. Take custody of the storage and backup encryption keys

The fresh database and private files are on a LUKS2 volume (`storage-encryption.md`). Both of its keys are on the host, root-only, and no vault
is connected to this service — so independent custody waits for you.

**How this procedure protects the values.** Each secret goes from the host to your clipboard and into your vault without ever being displayed,
written to a file, or entering a shell history. You then confirm the copy is correct by hashing what is on the clipboard and comparing it to a
checksum published here. A SHA-256 checksum does not reveal the value it summarises, which is why it can be written down in a document that is
not itself secret.

**Verified before publication.** The whole procedure — `cat` over ssh, `.Trim()`, SHA-256 — was exercised on dummy values on 2026-09-18,
including a value with a trailing newline, one without, and one padded with spaces. In all three the transport preserved the bytes exactly and
trimming reproduced the intended value. The two checksums below were then computed from the real files without printing them.

### 2a. The volume recovery passphrase (LUKS slot 1)

    ssh root@147.189.172.8 "cat /etc/quillmd/quillmd-fresh-luks.recovery-passphrase" | Set-Clipboard

    $v = (Get-Clipboard -Raw).Trim()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $h = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($v)) | ForEach-Object { $_.ToString('x2') })
    if ($h -eq '46cee981df24625792ac99c542aa53f0a9853eaf5cecb9c0075e4d1e1c041400') {
        Set-Clipboard -Value $v
        "PASSPHRASE VERIFIED - $($v.Length) characters - clipboard now holds exactly the checked value"
    } else { Set-Clipboard -Value ' '; "MISMATCH - do not store; tell engineering" }

Expected: `PASSPHRASE VERIFIED - 48 characters - clipboard now holds exactly the checked value`. Paste into a new vault item,
then clear the clipboard with `Set-Clipboard -Value ' '`.

⚠️ **The re-set is the point.** The checksum is computed over the TRIMMED value, so the clipboard must be put back to that
same trimmed value before you paste — otherwise you verify one string and store another.

### 2b. The backup encryption key

    ssh root@147.189.172.8 "cat /opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-current-20260917.key" | Set-Clipboard

    $v = (Get-Clipboard -Raw).Trim()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $h = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($v)) | ForEach-Object { $_.ToString('x2') })
    if ($h -eq 'cf69c55e4c288499e6c54c010b726bb9c7241be823bc8c15694a73740f53cff6') {
        Set-Clipboard -Value $v
        "BACKUP KEY VERIFIED - $($v.Length) characters - clipboard now holds exactly the checked value"
    } else { Set-Clipboard -Value ' '; "MISMATCH - do not store; tell engineering" }

Expected: `BACKUP KEY VERIFIED - 44 characters - clipboard now holds exactly the checked value`. Store it as a **separate**
vault item, then clear the clipboard the same way.

⚠️ **There are TWO keys in that directory.** `fresh-backup-current-20260917.key` is the live one and the command above names
it. `fresh-backup-20260917T165751Z-eccb5538.key` is its superseded predecessor, still present because the backups it opens
are still on disk; take custody of it as a third vault item if you want those older backups to remain restorable.

⚠️ **The trim is not cosmetic.** The key file on disk is 45 bytes: a 44-character Fernet key followed by a newline, which the backup tool
strips when it loads it. A value stored with that newline attached will not open a backup. The published checksum is of the trimmed
44-character value, which is exactly what the tool uses.

### 2c. Afterwards

1. Tell engineering the custodian's name and the two vault item names — **never the values, and never a screenshot of the vault**.
2. The host copies stay in place for now. Slot 0 (`/etc/quillmd/quillmd-fresh-luks.key`) is what lets the service come back unattended after a
   restart; deleting it would mean every boot waits for someone to type the passphrase.
3. **Decide whether disk-level protection is needed before real patient data.** Today, anyone with root on this host, or a copy of the whole
   disk, can open the volume — the unlock key is a file on the same unencrypted disk, and so is the backup key beside the backups it opens.
   `storage-encryption.md`, "What the configuration protects against", states scenario by scenario what is and is not covered. Closing those
   rows takes one maintenance window: remove slot 0, re-encrypt the volume, remove the key file — after which every boot needs
   `bash scripts/ops/unlock-fresh-volume.sh` and your passphrase.

### 2d. What engineering does NOT do

Nothing in this programme reads `/opt/meddoc-pro/rebuild/.env`, and reading it indirectly — `grep`, a script that prints a value, a diff that
includes it — is the same act with an extra step. To answer *is this credential configured*, run the application's own report, which is built
so that no branch of it can emit a value:

    cd /opt/meddoc-pro/rebuild && .venv/bin/python manage.py configuration_status

**Live since release `5f8050df` (2026-09-18).** Verified on the running system that day: it reports the two release
gates, the email and AI modes, and `absent` for every private credential that is not set.

It prints, per setting, `absent`, `present`, `present, recognised shape` or `present, UNRECOGNISED shape`, plus the release gates. Its tests
assert that a configured secret never appears in the output (`core/tests/test_configuration_status.py`).

## 3. Approve a maintenance window to prove recovery after a host reboot

Closing and reopening the volume is proven: the services stop, nothing can write plaintext, and they recover with the same rows and files.
Recovery after a full host reboot has not been tested, because the host is shared with other tenants. If you want it proven, name a window in
which the other tenants may restart, and engineering will reboot and verify.

## 4. Pair the Stripe CLI with the QuillMD sandbox and supply the application key

This blocks hosted checkout, signed event delivery, refund and retry verification.

1. Pair the CLI already on the VPS (`/home/claude/.local/bin/stripe`, v1.51.0). In this Claude Code session type:

       ! /home/claude/.local/bin/stripe login

   Open the printed URL, sign in, select the dedicated QuillMD **sandbox**, check the pairing code and approve. The CLI stores its own test-mode
   keys in `/home/claude/.config/stripe/config.toml` (0600). No key passes through chat.
2. In the same sandbox, create a restricted key named `QuillMD private beta checkout` with **Checkout Sessions: Write** and nothing else. Add it
   as `STRIPE_SECRET_KEY=rk_test_…` to `/opt/meddoc-pro/rebuild/.env`, keeping owner `claude` and mode 0600.
3. Tell engineering it is done. Engineering then runs `stripe listen` against the private service, stores that listener's own signing secret as
   `STRIPE_WEBHOOK_SECRET` in the same file, and runs the prepared sandbox verification over the signed delivery path.

## 5. Name one controlled email recipient

⚠️ **THIS IS NOW THE ONLY THING STANDING BETWEEN THE ACCOUNT FLOWS AND REAL DELIVERY.** As of 2026-09-19 the
private invitation, welcome-credit, cross-department, password-recovery and administrator-MFA checks all pass
(8 of 8) against the deployed release — but they read the application's **private file outbox**, which
demonstrates that the application composed and handed off each message. **It demonstrates nothing about
delivery.** No transport is exercised, and no message has ever reached a real mailbox. Naming one controlled
recipient is what converts that from an untested claim into evidence.

This blocks real invitation and password-recovery delivery evidence. Reply with one inbox address you control and will check. The sender, DNS
and provider credential already exist.

## 6. Approve the Backblaze B2 destination and supply a scoped key

This blocks the offsite backup round trip and restore proof. Bucket creation and any spending are yours.

1. Use a private bucket dedicated to the new system, with prefix `quillmd-fresh/synthetic/`.
2. Create a standard application key restricted to that bucket and prefix, with `listFiles`, `readFiles` and `writeFiles` only. Do not grant
   `deleteFiles` or any administration capability.
3. Write `/opt/meddoc-pro/rebuild/.runtime/backup-secrets/b2-offsite.json` (owner `claude`, mode 0600) in the shape given in
   `external-verification-runbook.md` §3: key id, application key, bucket, prefix, region and endpoint.

## 7. Supply provider cost evidence

This blocks provider-cost reconciliation. Supply Anthropic and Deepgram usage or cost exports for the synthetic jobs, with the account rates,
discounts and credits that apply. Copy them over SFTP into a new directory, `/opt/meddoc-pro/rebuild/.runtime/provider-evidence/` (mode 0700).
The console's "Cost reconciliation" section records each reconciliation as ledger entries. Rows stay labelled "configured estimate" until then.

⚠️ **UNTIL THAT ARRIVES, EVERY COST FIGURE ANYWHERE IN THIS PROJECT IS A *CONFIGURED-RATE* COST** — provider-reported units priced at the rates
recorded with the row — and it is **not** an invoice-reconciled actual amount. The documents that had drifted into calling it "actual cost" were
corrected on 2026-09-19, and the three evidence GENERATORS now emit a `cost_basis` field so the next run cannot quietly reintroduce the claim.
The database column is still named `actual_cost`; that is a schema name, not an assertion about a bill.

## 8. CPT content rights

CPT stays built and disabled. To enable it, supply the licensed dataset or terminology API access, and the contract that covers QuillMD's use,
display, distribution and user scope. Nothing is purchased automatically.

## 9. Independent test and patient-data release evidence

- **Independent tester.** Supply the tester's name, SSH public key, UTC window and emergency contact. The tunnel-only access grant is prepared
  (`pentest-scope.md`).
- **Patient-data agreements.** Supply signed agreements (BAAs), and approved processing regions and retention, for every provider and storage
  location. Real patient data stays disabled until these and the gates in `patient-data-release-requirements.md` are closed.

## Decided and implemented (no action)

- **Recordings above the displayed maximum** (owner policy 2026-09-18): the displayed maximum is a binding limit. A longer recording is
  explained before anything is sent, with a shorter segment or a clearly priced higher limit. An estimate that proves short is absorbed. See
  `cost-definition.md`, "Recording charge limit".
- **Plaintext copies of the new application's data**: removed on 2026-09-18 at 11:13Z after they were accounted for and encrypted recovery was proven.
  The record is at `rebuild/.runtime/plaintext-recovery-reap-20260918.json`.
