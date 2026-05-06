# Edge security — operator runbook (Round 3 PR-B)

> **Updated 2026-05-06 (PR-N):** The recommended way to apply this
> runbook is now `scripts/edge-security-apply.sh` — an idempotent
> wrapper that turns the 30+ sudo commands below into a small set
> of explicit `--phase=NAME go` invocations, with kill-switch
> arming via `at(1)`, dry-run previews of every destructive step,
> and per-phase rollback on failure.
>
> **This runbook remains authoritative reference.** Read it first
> to understand WHAT each phase does. Then use the script to
> actually apply, e.g.:
>
> ```
> sudo bash scripts/edge-security-apply.sh --help
> sudo bash scripts/edge-security-apply.sh --status
> sudo bash scripts/edge-security-apply.sh --phase=pre
> sudo bash scripts/edge-security-apply.sh --kill-switch arm go
> sudo bash scripts/edge-security-apply.sh --phase=ssh go
> sudo bash scripts/edge-security-apply.sh --phase=ufw go
> sudo bash scripts/edge-security-apply.sh --phase=fail2ban go
> sudo bash scripts/edge-security-apply.sh --phase=evict-deal-hunter go
> sudo bash scripts/edge-security-apply.sh --phase=verify
> sudo bash scripts/edge-security-apply.sh --kill-switch cancel go
> ```
>
> The script wraps the runbook's commands verbatim — zero deviations
> from the parameters below (allowed ports, fail2ban thresholds,
> AllowUsers list, DOCKER-USER fragment, ai-deal-hunter handling).
> If the script ever surprises you, fall back to the manual steps;
> they are still correct.

**Closes audit findings:** A07-P0-001 (sshd `PermitRootLogin yes`), A07-P0-002 (UFW disabled / no nftables), A07-P0-003 (root `ai-deal-hunter` uvicorn cohabits PHI VPS).

**Risk profile:** **HIGH.** SSH lockout and Docker-network break are both real possibilities. Read the whole runbook before starting. Have the Zap Hosting web console open in a separate browser tab. Have a SECOND SSH session open as fallback. Never reload sshd without first validating with `sshd -t`.

**Scope:** host config only. No Docker/compose changes. No application code. Cumulative wall time: ~25-35 min.

---

## §0. Pre-flight checklist (5 min)

Run on the VPS as root (or via `sudo -i`). All commands return non-zero exit on failure → STOP and surface.

- [ ] **Fallback session available.** Open Zap Hosting web console in a browser tab. Verify you can reach a root shell from the console (no SSH involved). This is the "if I lock myself out" recovery path.
- [ ] **Second SSH session open** in a separate terminal as `root@<vps>` from your operator IP. Leave it idle while we work in the primary session — if the primary breaks, this one survives.
- [ ] **All 9 containers healthy.**
  ```
  docker compose -f /opt/meddoc-pro/docker-compose.yml ps --format "{{.Name}}\t{{.Status}}"
  ```
  Expect 9 lines, every one `Up … (healthy)` or `Up …` for the worker.
- [ ] **Disk + RAM headroom.**
  ```
  df -h / | awk 'NR==2 {print $5" used, "$4" free"}'
  free -h | awk 'NR==2 {print $7" available"}'
  ```
  Want < 90% disk, > 1 GiB RAM available.
- [ ] **No active visit being processed.** A SOAP-pipeline retry during sshd reload won't actually break (sshd reload preserves established connections), but the optics are bad if a doctor-facing operation completes mid-runbook.
  ```
  docker exec meddoc-pro-redis-1 redis-cli LLEN bull:transcribe-md:active
  ```
  Expect `(integer) 0`. If non-zero, wait for it to drain or pick a quieter window.

---

## §1. Prerequisites — non-root sudo user with key auth (10 min)

**Audit Q1 decision:** the post-hardening `AllowUsers` line is `ubuntu claude`. Before disabling root login, verify `ubuntu` can already log in via key.

### §1.1 Verify `ubuntu`'s authorized_keys

```
ls -la /home/ubuntu/.ssh/authorized_keys
cat /home/ubuntu/.ssh/authorized_keys
```

Expected: file exists, mode `0600`, owner `ubuntu:ubuntu`, contains your operator public key.

### §1.2 If missing, install your key

From your **laptop**:
```
ssh-copy-id ubuntu@<vps-ip>
```
(this prompts for `ubuntu`'s password if one is set, OR fails if `PasswordAuthentication no` is already enforced — in which case install via root-on-VPS:)

On the VPS as root:
```
mkdir -p /home/ubuntu/.ssh
chmod 700 /home/ubuntu/.ssh
# paste your public key into the next file:
nano /home/ubuntu/.ssh/authorized_keys
chmod 600 /home/ubuntu/.ssh/authorized_keys
chown -R ubuntu:ubuntu /home/ubuntu/.ssh
```

### §1.3 Verify `ubuntu` has sudo

```
groups ubuntu
```
Expected output contains `sudo`. (Audit Phase 0 confirmed this on 2026-05-04.)

### §1.4 **CRITICAL: test `ubuntu` SSH login from your laptop in a NEW terminal**

```
ssh ubuntu@<vps-ip>            # must succeed without password prompt
```

Once logged in:
```
sudo -n true && echo "sudo works"   # must print sudo works
```

If either step fails, **STOP**. The whole point of disabling root SSH is to fall back to `ubuntu`. If `ubuntu` doesn't work, disabling root will lock you out.

### §1.5 Verify `claude`'s authorized_keys (automation account)

```
ls -la /home/claude/.ssh/authorized_keys
```

This should already exist (Claude Code uses it). If it doesn't, install whichever key Claude Code authenticates with. `claude` does NOT need sudo (audit Phase 0 confirmed `claude` is in `docker` group only — that's intentional).

---

## §2. Pre-stage config files (3 min — no live changes)

Pull the recommended configs into place so the apply step is atomic.

```
cd /opt/meddoc-pro

# SSH
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak-$(date +%Y%m%d-%H%M%S)
sudo install -m 0644 -o root -g root infra/ssh/sshd_config.recommended /etc/ssh/sshd_config.staged

# UFW after.rules fragment (will be appended in §4)
# Just verify the file is readable; don't apply yet.
ls -la infra/ufw/after.rules.fragment

# fail2ban jail.local (will be installed in §5)
ls -la infra/fail2ban/jail.local
```

---

## §3. SSH hardening (5 min — high risk; reload not restart)

### §3.1 Diff the staged config vs current

```
sudo diff /etc/ssh/sshd_config /etc/ssh/sshd_config.staged
```

Confirm the changes match expectations (`PermitRootLogin no`, `AllowUsers ubuntu claude`, etc).

### §3.2 Validate staged config syntax

```
sudo sshd -t -f /etc/ssh/sshd_config.staged
echo "exit=$?"
```

Expect `exit=0`. Any non-zero output is a syntax error → fix before continuing.

### §3.3 Apply atomically + validate the live file

```
sudo mv /etc/ssh/sshd_config.staged /etc/ssh/sshd_config
sudo sshd -t                              # validate the LIVE file
echo "exit=$?"
```

Expect `exit=0`. **If non-zero, immediately revert:**

```
sudo cp /etc/ssh/sshd_config.bak-* /etc/ssh/sshd_config
sudo sshd -t                              # must now exit 0
```

### §3.4 Reload sshd (preserves existing sessions)

```
sudo systemctl reload sshd
sudo systemctl status sshd --no-pager | head -5
```

Expect `active (running)`.

### §3.5 **Verify from your laptop, in a NEW terminal**

```
ssh ubuntu@<vps-ip>             # MUST still succeed
ssh claude@<vps-ip>             # MUST still succeed
ssh root@<vps-ip>               # MUST be REJECTED with "Permission denied"
```

If `ubuntu` login fails: your existing `root` session is still alive (reload doesn't kick it). Edit `/etc/ssh/sshd_config` from there to fix, run `sshd -t`, `systemctl reload sshd`, retry.

If `root` login somehow still works: re-grep the file for `PermitRootLogin`, ensure no later override, reload again.

---

## §4. UFW + Docker compatibility (10 min — Docker break risk)

### §4.1 Pre-stage UFW rules WITHOUT enabling

UFW remembers rules even when inactive — we add rules first, then enable.

```
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP (Caddy)'
sudo ufw allow 443/tcp comment 'HTTPS (Caddy)'

# Inspect (still inactive)
sudo ufw show added
```

### §4.2 Append Docker compatibility fragment

```
# Backup current after.rules
sudo cp /etc/ufw/after.rules /etc/ufw/after.rules.bak-$(date +%Y%m%d-%H%M%S)

# Find the line with the final COMMIT in after.rules' filter section
sudo grep -n "^COMMIT" /etc/ufw/after.rules
```

The fragment in `infra/ufw/after.rules.fragment` must be inserted BEFORE the final `COMMIT` of the `*filter` block. Edit manually with `nano`, or use this scripted insertion (works on the canonical Ubuntu `/etc/ufw/after.rules`):

```
sudo bash -c '
TMPFILE=$(mktemp)
awk "/^COMMIT\$/ && !done { while ((getline line < \"/opt/meddoc-pro/infra/ufw/after.rules.fragment\") > 0) print line; close(\"/opt/meddoc-pro/infra/ufw/after.rules.fragment\"); done=1 } { print }" /etc/ufw/after.rules > "$TMPFILE"
mv "$TMPFILE" /etc/ufw/after.rules
chown root:root /etc/ufw/after.rules
chmod 640 /etc/ufw/after.rules
'

# Sanity-diff the change
sudo diff /etc/ufw/after.rules.bak-* /etc/ufw/after.rules | head -40
```

### §4.3 Enable UFW + verify Docker still works

**Watch your second SSH session and the docker ps output the entire time. If anything goes wrong, run `sudo ufw disable` IMMEDIATELY.**

```
sudo ufw --force enable
sudo ufw status verbose
```

Expected output:
```
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), disabled (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere      # SSH
80/tcp                     ALLOW IN    Anywhere      # HTTP (Caddy)
443/tcp                    ALLOW IN    Anywhere      # HTTPS (Caddy)
22/tcp (v6)                ALLOW IN    Anywhere (v6)
80/tcp (v6)                ALLOW IN    Anywhere (v6)
443/tcp (v6)               ALLOW IN    Anywhere (v6)
```

### §4.4 Verify Docker traffic still flows

```
# Container-to-container
docker exec meddoc-pro-transcribe-md-1 wget -qO- http://postgres:5432 2>&1 | head -3
# Expect "no route" or auth-error (postgres rejects HTTP) — what matters is the
# connection establishes (it's NOT a UFW DROP).

# Container-to-internet
docker exec meddoc-pro-transcribe-md-1 wget -qO- https://api.anthropic.com/v1/messages 2>&1 | head -3
# Expect a 401/auth-error JSON response — confirms outbound HTTPS works.

# Host-to-public (the critical one)
curl -sI -m 5 https://app.quillmd.com   | head -1   # 307
curl -sI -m 5 https://pro.quillmd.com   | head -1   # 200
curl -sI -m 5 https://quillmd.com       | head -1   # 200
```

If ANY of these regress vs the pre-UFW baseline:

```
# IMMEDIATE rollback
sudo ufw disable
sudo systemctl restart docker         # forces docker to re-add its iptables rules
docker compose -f /opt/meddoc-pro/docker-compose.yml ps    # all healthy?
```

Then debug. The most common cause is the `after.rules` fragment landing in the wrong section — re-check §4.2.

### §4.5 Persist across reboot

```
sudo systemctl enable ufw
sudo systemctl status ufw --no-pager | head -3
```

---

## §5. fail2ban (3 min — low risk)

### §5.1 Install + configure

```
sudo apt-get update
sudo apt-get install -y fail2ban

# Drop in the QuillMD jail config
sudo install -m 0644 -o root -g root /opt/meddoc-pro/infra/fail2ban/jail.local /etc/fail2ban/jail.local

sudo systemctl enable --now fail2ban
sleep 2
sudo systemctl status fail2ban --no-pager | head -5
```

Expect `active (running)`.

### §5.2 Verify the sshd jail is active

```
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

Expected jails list: `sshd`. Status detail shows `Currently failed: 0`, `Currently banned: 0`, `Filter list: /etc/fail2ban/filter.d/sshd.conf`.

### §5.3 Verify ban behaviour (optional — DO NOT brute-force from operator IP)

If you have a disposable IP / VPN / mobile tether:

```
# from disposable IP, run 3 wrong logins
for i in 1 2 3; do ssh -o PasswordAuthentication=no -o PubkeyAuthentication=yes -o IdentityFile=/dev/null wrong-user@<vps-ip> 2>&1 | head -1; done

# from operator IP / on the box
sudo fail2ban-client banned                  # disposable IP appears
sudo iptables -L f2b-sshd -n                 # IP shows as DROP
```

To unban:
```
sudo fail2ban-client unban <IP>
```

---

## §6. Evict `ai-deal-hunter` (5 min — kill another project's process)

**Audit finding A07-P0-003.** Confirmed in Phase 0: PID 947 = `/root/ai-deal-hunter/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000` running as root, cohabiting the PHI VPS. Audit-Q2 decision: STOP + DISABLE + ARCHIVE (keep the directory; relocate it).

### §6.1 Identify the launch mechanism

```
sudo systemctl list-units --type=service --all | grep -iE "ai-deal|deal-hunter|uvicorn" | head -5
sudo systemctl list-unit-files --type=service | grep -iE "ai-deal|deal-hunter|uvicorn" | head -5

# Cron entries (root)
sudo crontab -l 2>/dev/null | grep -iE "ai-deal|uvicorn"

# Startup hooks in root's shell rc files
sudo grep -iE "ai-deal|uvicorn" /root/.bashrc /root/.profile /root/.bash_profile 2>/dev/null

# tmux/screen sessions still attached?
sudo -u root tmux ls 2>/dev/null
sudo -u root screen -ls 2>/dev/null
```

### §6.2 If a systemd unit exists

```
UNIT=ai-deal-hunter            # adjust to actual unit name from §6.1
sudo systemctl stop "$UNIT"
sudo systemctl disable "$UNIT"
sudo systemctl status "$UNIT" --no-pager | head -3        # should be inactive (dead)

# Optional: remove the unit file too
sudo rm -f /etc/systemd/system/"$UNIT".service /lib/systemd/system/"$UNIT".service
sudo systemctl daemon-reload
```

### §6.3 If launched from shell / nohup / orphan

```
# Find ALL related processes
sudo ps -ef | grep -iE "ai-deal|uvicorn.*8000" | grep -v grep

# Graceful term first
PID=947                         # confirm via ps -ef before running
sudo kill "$PID"
sleep 5

# If still alive, force kill
ps -p "$PID" >/dev/null && sudo kill -9 "$PID"

# Verify gone
sudo ps -ef | grep -iE "ai-deal|uvicorn" | grep -v grep    # should be empty
```

### §6.4 Archive the directory

```
sudo mkdir -p /root/archive-2026-05-04
sudo mv /root/ai-deal-hunter /root/archive-2026-05-04/ai-deal-hunter
ls -la /root/archive-2026-05-04/
```

The directory is preserved (Kasra may relocate it). It's no longer in `/root/ai-deal-hunter/` so any orphan startup hook fails noisily.

### §6.5 Verify port 8000 closed + no orphan process

```
sudo ss -tlnp | grep ":8000"          # should be empty
sudo ps -ef | grep -iE "ai-deal|deal-hunter" | grep -v grep    # should be empty

# UFW also blocks external ingress regardless (only 22/80/443 allowed)
curl -sI -m 3 http://<vps-ip>:8000   # connection refused or timeout
```

---

## §7. Final verification checklist (3 min)

Run all of these. Each must pass.

### §7.1 Externally (from operator's laptop)

```
ssh root@<vps-ip>                # MUST be rejected
ssh ubuntu@<vps-ip>              # MUST succeed (key auth)
ssh claude@<vps-ip>              # MUST succeed (key auth)

curl -sI https://app.quillmd.com   | awk 'NR==1'   # 307
curl -sI https://pro.quillmd.com   | awk 'NR==1'   # 200
curl -sI https://quillmd.com       | awk 'NR==1'   # 200
curl -sI -m 3 http://<vps-ip>:8000                 # connection refused / timeout
```

### §7.2 On the VPS

```
sudo ufw status verbose | head -15                # active, 22/80/443 allow only
sudo systemctl is-active sshd ufw fail2ban        # all active
sudo fail2ban-client status sshd | head -5        # jail running, 0 banned
sudo ss -tlnp | grep -vE ":(22|80|443|9010|9020|3001|3010|3011|5432|6379|9000|9001|18789|18790)"
# ↑ should print only loopback bindings (127.0.0.1:NNNN); no public 0.0.0.0:* outside the allowed set
```

### §7.3 Application health

```
docker compose -f /opt/meddoc-pro/docker-compose.yml ps --format "{{.Name}}\t{{.Status}}"   # 9× healthy
docker exec meddoc-pro-transcribe-md-1 wget -qO- http://localhost:3011/api/health           # JSON ok
```

---

## §8. Recovery procedures

### §8.1 SSH lockout (you cannot connect, even as `ubuntu`)

1. Open the **Zap Hosting web console** browser tab → root shell.
2. `cp /etc/ssh/sshd_config.bak-* /etc/ssh/sshd_config`
3. `sshd -t` (must exit 0)
4. `systemctl reload sshd`
5. Retry ssh from laptop. Diagnose the failed change before re-attempting.

### §8.2 Docker network broken after UFW enable

In the second SSH session (or web console):

1. `sudo ufw disable` — IMMEDIATE
2. `sudo systemctl restart docker` — re-applies Docker's iptables rules
3. `docker compose -f /opt/meddoc-pro/docker-compose.yml ps` — verify all healthy
4. `curl https://app.quillmd.com` (from laptop) — verify production restored
5. Diagnose: most common cause is the `after.rules` fragment in the wrong place — re-check §4.2 paste position.

### §8.3 fail2ban banned your operator IP

In the second SSH session (or web console):

```
sudo fail2ban-client unban <your-IP>
```

If you locked yourself out completely, edit `/etc/fail2ban/jail.local` from web console, set `ignoreip = 127.0.0.1/8 ::1 <your-IP>/32`, restart fail2ban.

### §8.4 ai-deal-hunter wasn't supposed to be evicted

The directory is preserved at `/root/archive-2026-05-04/ai-deal-hunter/`. To restore:

```
sudo mv /root/archive-2026-05-04/ai-deal-hunter /root/ai-deal-hunter
# Restart however it was originally launched (systemd unit, manual nohup, …)
```

(But: don't restart it on the QuillMD VPS. Move it to a separate host. Cohabiting a personal project with PHI infrastructure is the audit finding.)

---

## §9. Sign-off

After completing §1-§7 successfully, mark the boxes in `docs/LAUNCH_CHECKLIST.md` (the "Edge security" subsection added by this PR) and update `docs/POST_MERGE_TODO.md §24` to mark PR-B status from 🚧 OPEN to ✅ MERGED with the merged-PR link.

Tag the merge: `git tag round-3-pr-b-complete && git push origin round-3-pr-b-complete`.

---

## Appendix — full audit trail of files touched

| File | Action | Reverts to |
|---|---|---|
| `/etc/ssh/sshd_config` | replaced | `/etc/ssh/sshd_config.bak-*` |
| `/etc/ufw/after.rules` | appended fragment | `/etc/ufw/after.rules.bak-*` |
| `/etc/fail2ban/jail.local` | created | delete + reinstall fail2ban defaults |
| `/etc/issue.net` | (optional) | delete |
| `/root/ai-deal-hunter/` | moved | mv back from archive |
| `/root/archive-2026-05-04/` | created | rmdir if empty |
