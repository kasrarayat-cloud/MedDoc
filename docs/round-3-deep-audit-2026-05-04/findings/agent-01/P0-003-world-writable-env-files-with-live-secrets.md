---
id: A01-P0-003
severity: P0
title: "apps/meddoc-pro/.env and .env.local are mode 0777 (world-writable) holding live keys"
domain: Credential & secret hygiene
files:
  - apps/meddoc-pro/.env
  - apps/meddoc-pro/.env.local
  - .env.backup
  - .env.local
---

## Issue
Five env files containing live API keys have permissions that allow read (and in two cases, write) access by any local user on the VPS:

```
$ stat -c '%a %n' /opt/meddoc-pro/.env*  /opt/meddoc-pro/apps/meddoc-pro/.env*  /opt/meddoc-pro/tests/automated/.env.test
640 /opt/meddoc-pro/.env
755 /opt/meddoc-pro/.env.backup            ← world-readable
755 /opt/meddoc-pro/.env.local             ← world-readable
777 /opt/meddoc-pro/apps/meddoc-pro/.env       ← world-writable + readable
777 /opt/meddoc-pro/apps/meddoc-pro/.env.local ← world-writable + readable
755 /opt/meddoc-pro/apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env
600 /opt/meddoc-pro/tests/automated/.env.test
```

The 0777 files are particularly dangerous: any local user can not only read the live OpenAI/Anthropic/Deepgram keys but also **rewrite** them — pointing the app to attacker-controlled provider endpoints, or burning the key to force fail-open behaviour.

Even the 0755 files (world-readable) are unsafe: trufflehog confirmed all live keys are present in plaintext at the file paths above.

## Evidence
Verified live keys (from `trufflehog filesystem` with `Verified=True`):
- `/opt/meddoc-pro/apps/meddoc-pro/.env` (mode 777): ANTHROPIC_API_KEY=sk-ant-api03-<REDACTED>... [verified live]
- `/opt/meddoc-pro/apps/meddoc-pro/.env.local` (mode 777): ANTHROPIC_API_KEY [verified live]
- `/opt/meddoc-pro/.env.backup` (mode 755): ANTHROPIC_API_KEY [verified live] + OPENAI_API_KEY [verified live] + DEEPGRAM_API_KEY [verified live]
- `/opt/meddoc-pro/.env.local` (mode 755): ANTHROPIC_API_KEY [verified live]

Process listing:
```
$ ls -la /opt/meddoc-pro/apps/meddoc-pro/.env /opt/meddoc-pro/apps/meddoc-pro/.env.local
-rwxrwxrwx 1 claude claude 2301 ... apps/meddoc-pro/.env
-rwxrwxrwx 1 claude claude  ... apps/meddoc-pro/.env.local
```

The .env.example explicitly documents the expected mode:

`/opt/meddoc-pro/.env.example:9-12`:
```
# After populating real values, lock the file down:
#   chmod 600 .env
```

— but the actual on-disk files violate this guidance.

## Risk
1. **Any local user reads live API keys** — bypasses every key-vault, BAA, and rotation discipline.
2. The 0777 files allow **silent substitution** by an attacker (e.g. via a web shell run as `www-data` or a compromised supply-chain package executing post-install hooks). The attacker swaps the OpenAI key for one they control, every visit's transcript metadata is then exfiltrated to attacker via OpenAI request observation, and the attacker doesn't pay a cent (we still pay).
3. HIPAA §164.308(a)(3)(i) requires Workforce Security with role-based access. World-readable PHI-decryption-key-equivalent files are a clear violation.
4. The `apps/meddoc-pro` app is per the AGENT 01 brief DECOMMISSIONED. Yet the env files for it still live, in plaintext, world-writable. There is no operational justification to keep them at all.

## Recommended fix
1. **Immediately**: `chmod 600` on every `.env*` file under `/opt/meddoc-pro` that contains real values. Verify ownership is the runtime service user, not `claude` (or your bastion ops user).
2. Delete the decommissioned `apps/meddoc-pro/.env`, `apps/meddoc-pro/.env.local`, `apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env` — entire `apps/meddoc-pro/.next/` subtree.
3. Delete `.env.backup` (it duplicates `.env` and contains a strict superset of secrets).
4. Add a pre-deploy hook in `scripts/` (called from `Makefile` deploy targets and from container startup) that bails if `find /opt/meddoc-pro -name '.env*' -not -path '*/node_modules/*' -perm /o+rwx` returns any output.
5. `.env.local` (root) appears to be overriding `.env` only for ANTHROPIC_API_KEY — fold this back into `.env` or document why it must exist; either way mode 600.
