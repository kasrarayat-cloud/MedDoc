---
id: A07-P3-002
title: h8-post-reboot.sh @reboot cron persists after intended one-shot use
severity: P3
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

The claude user's crontab contains:

```
# Phase 5.2 — 48h cache verification (one-shot, fires 2026-05-04T22:00 UTC, self-removes after)
@reboot /opt/meddoc-pro/scripts/h8-post-reboot.sh 20260503T040001Z > /tmp/h8-post-reboot.log 2>&1
```

The script comment claims it self-removes. Today is 2026-05-04 23:39 UTC.
The intended fire time was 2026-05-04T22:00 UTC. The cron line is still
present. Either the boot did not occur in the intended window, the
self-remove did not work, or this entry is stale.

Self-removing crons are a code-smell pattern in any case: a cron line
that mutates its own definition is hard to reason about and can race with
a manual edit.

## Evidence

```
$ crontab -l | tail -3
# Phase 5.2 — 48h cache verification (one-shot, fires 2026-05-04T22:00 UTC, self-removes after)
@reboot /opt/meddoc-pro/scripts/h8-post-reboot.sh 20260503T040001Z > /tmp/h8-post-reboot.log 2>&1

$ ls -la /tmp/h8-post-reboot.log
(absent — script may not have fired this boot)
```

Inside `scripts/h8-post-reboot.sh` (lines 122-124):
```bash
echo "[4] removing @reboot line from claude user crontab"
( crontab -l 2>/dev/null | grep -v 'h8-post-reboot.sh' ) | crontab -
```

The script also unconditionally pushes commits to git from the post-reboot
hook (`git push origin main`). For a system boot path this is unusually
side-effect-heavy.

## Risk

- If `git push` ever rejects (e.g. force-pushed main, missing creds), the
  script exits non-zero before self-removing the cron line, and the next
  boot tries again forever.
- Pushing to `origin main` from a host-level cron is an unusual pattern
  and means the host has push credentials for the production repo —
  another compromise vector.
- The cron line still being present at this audit's date suggests
  one of: (a) the box did not reboot since 2026-05-03 (it did, see
  `last reboot` showing several reboots), (b) the script's
  `last reboot` invocation hit an exception and never reached step 4,
  or (c) the self-remove pattern raced and re-installed itself.

## Recommended fix

For the immediate cron line (after confirming the test is complete):

```bash
crontab -l | grep -v 'h8-post-reboot.sh' | crontab -
```

For the broader pattern: avoid self-modifying crons. Either:
- Check `[ -f /tmp/h8-already-ran-${PRE_TS} ]` at the top of the script
  and exit early; let a separate manual cleanup remove the line when
  the test is closed.
- Or use a `systemd --user` one-shot unit with `RemainAfterExit=yes` and
  remove the unit file when done.

Remove the `git push origin main` from the boot-path script unless
strictly necessary; commit the report from a follow-up workstation step
instead. The host having push creds to main is a small but non-zero
attack vector.
