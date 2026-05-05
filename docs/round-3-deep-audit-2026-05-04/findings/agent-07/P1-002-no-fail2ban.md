---
id: A07-P1-002
title: fail2ban not installed; SSH brute-force has no rate-limit
severity: P1
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

fail2ban is not installed on this host. SSH (port 22 on 0.0.0.0) is the
primary interactive entry point and accepts root logins (A07-P0-001). With
no host firewall (A07-P0-002) and no fail2ban, the only brute-force
protection is the OpenSSH default `MaxAuthTries 6` per connection — an
attacker can simply reconnect.

## Evidence

```
$ systemctl status fail2ban
Unit fail2ban.service could not be found.
$ which fail2ban-client
(empty)
$ dpkg -l | grep fail2ban
(no output)
```

The active sshd accepts root password attempts (PasswordAuthentication
defaults to `yes` since neither sshd_config nor any readable drop-in
explicitly disables it).

`/var/log/auth.log` is 3.8 MB unrotated; `/var/log/btmp` is 11 MB —
suggests significant unsuccessful-login activity already, though btmp is
unreadable to claude (mode 0600 root:adm) so we can't quantify.

## Risk

- SSH credential brute-force is unmitigated. With root login enabled and
  password auth not explicitly disabled, an attacker only needs one stolen
  / weak password.
- DDoS slow-loris-style SSH attacks against :22 also have nothing in front
  of them.
- For HIPAA §164.308(a)(5)(ii)(D) "Password Management" the absence of
  account-lockout-style controls is hard to defend.

## Recommended fix

Install fail2ban with the SSH jail enabled:

```bash
sudo apt-get install -y fail2ban
sudo bash -c 'cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd

[sshd]
enabled = true
port = 22
EOF'
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

After A07-P0-001 is fixed (key-only SSH, no root, no password auth) the
SSH jail still adds defence-in-depth against connection-flood / discovery
attempts.

Consider adding additional jails:
- `nginx-http-auth` equivalent for Caddy 4xx storms (custom action;
  Caddy's structured logs in stdout via the `log` directive can feed a
  custom filter).
- `recidive` for repeat offenders escalating to 1-week bans.

Document in the launch readiness checklist.
