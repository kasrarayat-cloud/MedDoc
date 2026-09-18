# Owner actions

Updated 2026-09-18 (running release `5f673a3b`). This is the single list of what only the owner can do. Engineering does everything else
without asking. The private service stays synthetic-only, and the public routes stay in maintenance, until the release evidence supports a
change. Never paste a secret into chat, a shell command line, Git, a ticket or a screenshot. Every secret location below is a file readable only
by its owner account.

Your access is SSH as `root` to `147.189.172.8`; the `claude` account has no SSH key. On first connection, check that the host key matches one
of these fingerprints before you accept it:

- ED25519 `SHA256:e0eCC1AeF1xUQ8conZqXbXjTVa9YhGwzQzz0GSctqIY`
- ECDSA `SHA256:ie7lReVrF69+Zt1C7W5ow0HPLTFozvyb4sROMff/6YY`

The commands below are for Windows PowerShell, which includes OpenSSH.

## 1. Review the Word documents in native Microsoft Word

This blocks native Word appearance acceptance. No renderer on the VPS can establish it, and none is substituted for it.

1. Copy the archive to your Downloads folder:

       scp root@147.189.172.8:/opt/meddoc-pro/rebuild/.runtime/word-review-package/quillmd-word-review-20260918.zip "$env:USERPROFILE\Downloads\quillmd-word-review-20260918.zip"

2. Check its hash. The expected value is `B270C982864CB42D0BDB13AC64265B29E53F36BD5EFD3CE45D45B7B862F03A72` (227,269 bytes).

       Get-FileHash "$env:USERPROFILE\Downloads\quillmd-word-review-20260918.zip" -Algorithm SHA256

3. Unpack it:

       Expand-Archive "$env:USERPROFILE\Downloads\quillmd-word-review-20260918.zip" -DestinationPath "$env:USERPROFILE\Downloads\quillmd-word-review-20260918"

   `SHA256SUMS.txt` inside lists every review file with its hash.
4. Open each `.docx` in desktop Microsoft Word and work through `word-acceptance-checklist.md`. Mark each row ACCEPT or REJECT, and report
   your Word version and build (File > Account > About Word).

The archive holds the blank WM IOV original, the fresh and previous live exports, two fixture exports, the checklist and the hash list. All
content is synthetic. It holds no credentials and no runtime files.

## 2. Take custody of the storage and backup encryption keys

The fresh database and private files are on a LUKS2 volume (`storage-encryption.md`). Both of its keys are on the host, root-only. No vault is
connected to this service, so independent custody waits for you. Each command below copies one secret straight to your clipboard; nothing is
displayed or stored on your computer.

1. The volume's recovery passphrase (LUKS slot 1):

       ssh root@147.189.172.8 "cat /etc/quillmd/quillmd-fresh-luks.recovery-passphrase" | Set-Clipboard

   Paste it into a new item in your password vault, then clear the clipboard with `Set-Clipboard -Value $null`.
2. The backup encryption key:

       ssh root@147.189.172.8 "cat /opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-current-20260917.key" | Set-Clipboard

   Store it in the same way, as a separate vault item.
3. Tell engineering the custodian's name and the two vault item names, never the values. The host copies stay in place: the key file (slot 0)
   keeps restarts unattended.
4. Decide whether disk-level protection is needed before real patient data. Today, anyone with root on the host, or a copy of the whole disk,
   can open the volume, because the key file is on the same disk. To protect against that, engineering removes slot 0, re-encrypts the volume
   and removes the key file in one maintenance window. Every reboot would then need someone to run `bash scripts/ops/unlock-fresh-volume.sh`
   and type the passphrase.

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
