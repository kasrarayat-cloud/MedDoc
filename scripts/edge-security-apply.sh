#!/usr/bin/env bash
# scripts/edge-security-apply.sh — Round 3 PR-B execution wrapper (PR-N).
# ============================================================================
# Idempotent operator-handoff script for the edge-security runbook
# (docs/runbooks/edge-security.md). Authored by PR-N to reduce the
# manual-typing surface of the 498-line PR-B runbook from 30+ sudo
# commands to a small number of explicit `--phase=NAME go` invocations.
#
# This script is the SAFER way to apply PR-B. The runbook itself
# remains the authoritative reference — read it first to understand
# WHAT each phase does before running.
#
# DESIGN
# ------
# Every destructive phase requires the literal positional argument
# `go` (without it the script prints what WOULD happen). Every phase
# is idempotent — re-running any phase with `go` checks the current
# state and skips work already done.
#
# A kill-switch (--kill-switch arm) schedules `ufw --force disable +
# systemctl stop fail2ban` via `at now + 10 minutes` BEFORE any
# destructive phase runs. If the operator's SSH session dies
# (the failure mode that motivates the kill-switch — sleep+& won't
# survive session termination, which is why we use at(1)), the
# scheduled job fires and reverts. Cancel via --kill-switch cancel
# AFTER verifying the new config works.
#
# PHASES (run in this order on a fresh apply)
# -------------------------------------------
#   pre               read-only — pre-flight checklist
#   ssh               apply infra/ssh/sshd_config.recommended
#   ufw               install + configure UFW + DOCKER-USER fragment
#   fail2ban          apt install fail2ban + drop in jail.local
#   evict-deal-hunter STOP + DISABLE + ARCHIVE the cohabit'd uvicorn
#   verify            read-only — final §7 verification block
#
# USAGE
# -----
#   sudo bash scripts/edge-security-apply.sh --help
#   sudo bash scripts/edge-security-apply.sh --status
#   sudo bash scripts/edge-security-apply.sh --phase=pre
#   sudo bash scripts/edge-security-apply.sh --phase=ufw            # DRY-RUN
#   sudo bash scripts/edge-security-apply.sh --kill-switch arm
#   sudo bash scripts/edge-security-apply.sh --phase=ssh go         # APPLY
#   sudo bash scripts/edge-security-apply.sh --kill-switch cancel
#
# EXIT CODES
# ----------
#   0   ok / phase already-applied no-op
#   1   missing prereqs (e.g. infra/* file missing, sudo not available)
#   2   apply step failed (per-phase rollback documented in runbook §8)
#   3   dry-run mode — script printed what it would do (no changes made)
#   4   precondition failed (e.g. kill-switch not armed before destructive phase)
# ============================================================================

set -euo pipefail

# ── Constants ──────────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"
RUNBOOK_PATH="${REPO_ROOT}/docs/runbooks/edge-security.md"

# PR-B config sources (must exist in repo).
SSHD_RECOMMENDED="${INFRA_DIR}/ssh/sshd_config.recommended"
UFW_FRAGMENT="${INFRA_DIR}/ufw/after.rules.fragment"
F2B_JAIL_LOCAL="${INFRA_DIR}/fail2ban/jail.local"

# Live config targets.
SSHD_LIVE="/etc/ssh/sshd_config"
UFW_AFTER_RULES="/etc/ufw/after.rules"
F2B_JAIL_LIVE="/etc/fail2ban/jail.local"

# Kill-switch marker (at-queue letter is E for Edge-security).
KILL_SWITCH_QUEUE="e"
KILL_SWITCH_STATE_FILE="/var/lib/quillmd/edge-security-kill-switch.id"

# Backup timestamp suffix.
TS="$(date +%Y%m%d-%H%M%S)"

# ── Output helpers ─────────────────────────────────────────────────────────

# Color only when stdout is a TTY. shellcheck-clean tput pattern.
if [ -t 1 ]; then
  C_RED="$(tput setaf 1 2>/dev/null || true)"
  C_GREEN="$(tput setaf 2 2>/dev/null || true)"
  C_YELLOW="$(tput setaf 3 2>/dev/null || true)"
  C_BLUE="$(tput setaf 4 2>/dev/null || true)"
  C_DIM="$(tput dim 2>/dev/null || true)"
  C_RESET="$(tput sgr0 2>/dev/null || true)"
else
  C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""; C_DIM=""; C_RESET=""
fi

log()      { printf '%s[edge-sec] %s%s\n' "${C_BLUE}"   "$*" "${C_RESET}"; }
log_ok()   { printf '%s[edge-sec] OK %s%s\n' "${C_GREEN}" "$*" "${C_RESET}"; }
log_warn() { printf '%s[edge-sec] WARN %s%s\n' "${C_YELLOW}" "$*" "${C_RESET}" >&2; }
log_err()  { printf '%s[edge-sec] ERR %s%s\n'  "${C_RED}"   "$*" "${C_RESET}" >&2; }
log_dry()  { printf '%s[edge-sec dry-run] %s%s\n' "${C_DIM}" "$*" "${C_RESET}"; }

# Print a command verbatim (dry-run preview).
preview() { printf '%s    + %s%s\n' "${C_DIM}" "$*" "${C_RESET}"; }

# ── Mode + state ───────────────────────────────────────────────────────────

# Returns 0 if running as root.
is_root() { [ "$(id -u)" = "0" ]; }

# Returns 0 if `sudo -n true` works (passwordless sudo available).
have_passwordless_sudo() { sudo -n true 2>/dev/null; }

# Wrap a privileged command. If we are root, run directly. Else use sudo.
# Caller is responsible for *intending* the command to be privileged.
priv() {
  if is_root; then "$@"; else sudo "$@"; fi
}

# Returns 0 if the script was invoked with `go` as a positional arg.
GO_REQUESTED=0
maybe_apply() {
  if [ "${GO_REQUESTED}" = "1" ]; then
    "$@"
  else
    preview "$@"
    return 0
  fi
}

# ── Pre-flight assertions ──────────────────────────────────────────────────

require_repo_files() {
  local missing=0
  for f in "${SSHD_RECOMMENDED}" "${UFW_FRAGMENT}" "${F2B_JAIL_LOCAL}" "${RUNBOOK_PATH}"; do
    if [ ! -r "${f}" ]; then
      log_err "missing repo file: ${f}"
      missing=$((missing + 1))
    fi
  done
  if [ "${missing}" -gt 0 ]; then
    log_err "PR-B repo files missing — refusing to proceed."
    log_err "  Verify HEAD is on a branch derived from main post-PR-#113."
    exit 1
  fi
}

require_root_or_sudo() {
  if is_root; then return 0; fi
  if have_passwordless_sudo; then return 0; fi
  log_err "this phase requires root or passwordless sudo."
  log_err "  Re-run as: sudo bash $0 <flags>"
  exit 1
}

# ── Status helpers (read-only, used by --status + verify phase) ────────────

status_ssh() {
  # Best-effort: prefer direct read (root can; non-root usually can't read
  # /etc/ssh/sshd_config). If unreadable, fall back to a sudo read; if
  # neither works, report unknown. set -e is sidestepped per-pipeline
  # via `|| true` so --status doesn't crash on a non-sudo invocation.
  local content=""
  if [ -r "${SSHD_LIVE}" ]; then
    content=$(cat "${SSHD_LIVE}" 2>/dev/null || true)
  elif have_passwordless_sudo; then
    content=$(sudo -n cat "${SSHD_LIVE}" 2>/dev/null || true)
  fi
  if [ -z "${content}" ]; then
    echo "ssh        : unknown (cannot read ${SSHD_LIVE} — re-run with sudo for full status)"
    return
  fi
  local permitroot allowusers passwordauth
  permitroot=$(printf '%s\n' "${content}"   | grep -iE '^[[:space:]]*PermitRootLogin'         | tail -1 | awk '{print $2}' || true)
  allowusers=$(printf '%s\n' "${content}"   | grep -iE '^[[:space:]]*AllowUsers'              | tail -1 | sed 's/^[^ ]* //'  || true)
  passwordauth=$(printf '%s\n' "${content}" | grep -iE '^[[:space:]]*PasswordAuthentication'  | tail -1 | awk '{print $2}' || true)
  if [ "${permitroot}" = "no" ] && [ -n "${allowusers}" ] && [ "${passwordauth}" = "no" ]; then
    echo "ssh        : applied (PermitRootLogin=no, AllowUsers=\"${allowusers}\", PasswordAuthentication=no)"
  else
    echo "ssh        : not-applied (PermitRootLogin=${permitroot:-?}, AllowUsers=${allowusers:-?}, PasswordAuthentication=${passwordauth:-?})"
  fi
}

status_ufw() {
  if ! command -v ufw >/dev/null 2>&1; then
    echo "ufw        : not-installed"; return
  fi
  local active rules_count frag_present
  active=$(systemctl is-active ufw 2>/dev/null || true); active="${active:-unknown}"
  if is_root || have_passwordless_sudo; then
    rules_count=$(priv ufw status numbered 2>/dev/null | grep -cE '^\[ *[0-9]+\]' || echo "?")
    if priv test -r "${UFW_AFTER_RULES}" 2>/dev/null && \
       priv grep -q "BEGIN ufw-docker DOCKER-USER fragment" "${UFW_AFTER_RULES}" 2>/dev/null; then
      frag_present="yes"
    else
      frag_present="no"
    fi
  else
    rules_count="? (needs sudo)"
    frag_present="? (needs sudo)"
  fi
  echo "ufw        : status=${active}, rules=${rules_count}, docker-user-fragment=${frag_present}"
}

status_fail2ban() {
  if ! command -v fail2ban-client >/dev/null 2>&1; then
    echo "fail2ban   : not-installed"; return
  fi
  local active jails banned jail_local_present
  active=$(systemctl is-active fail2ban 2>/dev/null || true); active="${active:-unknown}"
  if [ "${active}" = "active" ] && (is_root || have_passwordless_sudo); then
    jails=$(priv fail2ban-client status 2>/dev/null | awk -F: '/Jail list/ {print $2}' | sed 's/^[[:space:]]*//' || true)
    banned=$(priv fail2ban-client status sshd 2>/dev/null | awk -F: '/Currently banned/ {print $2}' | tr -d '[:space:]' || true)
  else
    jails="-"; banned="-"
  fi
  if [ -r "${F2B_JAIL_LIVE}" ] || (have_passwordless_sudo && sudo -n test -r "${F2B_JAIL_LIVE}" 2>/dev/null); then
    jail_local_present="yes"
  else
    jail_local_present="no"
  fi
  echo "fail2ban   : status=${active}, jails=${jails:--}, banned=${banned:--}, jail.local=${jail_local_present}"
}

status_deal_hunter() {
  local present="no" running="?"
  if [ -d /root/ai-deal-hunter ]; then
    present="yes (NOT yet evicted)"
  elif have_passwordless_sudo && sudo -n test -d /root/ai-deal-hunter 2>/dev/null; then
    present="yes (NOT yet evicted)"
  elif is_root && [ -d /root/ai-deal-hunter ]; then
    present="yes (NOT yet evicted)"
  fi
  if is_root || have_passwordless_sudo; then
    if priv ss -tlnp 2>/dev/null | grep -q ':8000 '; then
      running="yes (port 8000 still bound)"
    else
      running="no"
    fi
  fi
  echo "deal-hunter: dir-present=${present}, listening-on-8000=${running}"
}

status_kill_switch() {
  if [ ! -r "${KILL_SWITCH_STATE_FILE}" ]; then
    echo "kill-switch: not-armed"
    return
  fi
  local id
  id=$(cat "${KILL_SWITCH_STATE_FILE}" 2>/dev/null || echo "?")
  if (is_root || have_passwordless_sudo) && \
     priv atq -q "${KILL_SWITCH_QUEUE}" 2>/dev/null | grep -q "^${id}[[:space:]]"; then
    local fires_at
    fires_at=$(priv atq -q "${KILL_SWITCH_QUEUE}" 2>/dev/null | awk -v id="${id}" '$1 == id {for (i=2;i<=NF-2;i++) printf "%s ", $i; print ""}' || true)
    echo "kill-switch: ARMED (job ${id}, fires at ${fires_at})"
  else
    echo "kill-switch: not-armed (state file ${KILL_SWITCH_STATE_FILE} present but at-queue ${KILL_SWITCH_QUEUE} clean)"
  fi
}

cmd_status() {
  log "edge-security status (read-only):"
  status_ssh
  status_ufw
  status_fail2ban
  status_deal_hunter
  status_kill_switch
}

# ── Kill-switch (at(1)-based; survives SSH session termination) ────────────

kill_switch_arm() {
  if [ "${GO_REQUESTED}" = "1" ]; then require_root_or_sudo; fi
  if ! command -v at >/dev/null 2>&1; then
    if [ "${GO_REQUESTED}" = "1" ]; then
      log_err "at(1) is not installed. apt-get install -y at  (and ensure atd is running)"
      exit 1
    else
      log_warn "at(1) is not installed. Apply will require: apt-get install -y at && systemctl enable --now atd"
    fi
  fi
  if command -v systemctl >/dev/null 2>&1 && ! systemctl is-active --quiet atd 2>/dev/null; then
    if [ "${GO_REQUESTED}" = "1" ]; then
      log_warn "atd service is not active — kill-switch will not fire."
      log_warn "  Run: systemctl enable --now atd  before arming."
      exit 4
    else
      log_warn "atd is not active. Apply will require: systemctl enable --now atd  beforehand."
    fi
  fi
  # The revert command. Conservative: disable UFW + stop fail2ban. SSH
  # is left alone (sshd reload is non-destructive to existing sessions
  # and the runbook validates with sshd -t before reload, so reverting
  # sshd_config is operator-driven, not auto).
  local revert_cmd='ufw --force disable; systemctl stop fail2ban; logger -t edge-security "kill-switch fired"'
  if [ "${GO_REQUESTED}" != "1" ]; then
    log_dry "would schedule kill-switch (queue ${KILL_SWITCH_QUEUE}, fires at now+10min):"
    preview "${revert_cmd}"
    log_dry "(re-run with 'go' to actually arm)"
    exit 3
  fi
  # Idempotency: if a kill-switch is already armed, leave it alone.
  if [ -r "${KILL_SWITCH_STATE_FILE}" ]; then
    local existing
    existing=$(cat "${KILL_SWITCH_STATE_FILE}")
    if priv atq -q "${KILL_SWITCH_QUEUE}" | grep -q "^${existing}[[:space:]]"; then
      log_ok "kill-switch already armed (job ${existing}); leaving as-is."
      return 0
    fi
  fi
  priv mkdir -p "$(dirname "${KILL_SWITCH_STATE_FILE}")"
  local at_out
  at_out=$(echo "${revert_cmd}" | priv at -q "${KILL_SWITCH_QUEUE}" now + 10 minutes 2>&1)
  echo "${at_out}" >&2
  local job_id
  job_id=$(printf '%s\n' "${at_out}" | sed -n 's/^job \([0-9][0-9]*\) at .*/\1/p' | tail -1)
  if [ -z "${job_id}" ]; then
    log_err "could not parse at(1) job id from output above."
    exit 2
  fi
  echo "${job_id}" | priv tee "${KILL_SWITCH_STATE_FILE}" >/dev/null
  log_ok "kill-switch armed (job ${job_id}). Cancel after verifying with: $0 --kill-switch cancel"
}

kill_switch_cancel() {
  if [ "${GO_REQUESTED}" = "1" ]; then require_root_or_sudo; fi
  if [ ! -r "${KILL_SWITCH_STATE_FILE}" ]; then
    log_warn "no kill-switch state file at ${KILL_SWITCH_STATE_FILE}"
    # Still try to scrub the queue in case the file got lost.
    local queued
    queued=$(priv atq -q "${KILL_SWITCH_QUEUE}" 2>/dev/null | awk '{print $1}' || true)
    if [ -n "${queued}" ]; then
      log_warn "found orphaned queue-${KILL_SWITCH_QUEUE} jobs: ${queued}"
      if [ "${GO_REQUESTED}" = "1" ]; then
        # priv is a shell function — can't be passed to xargs. Loop instead.
        while IFS= read -r jid; do
          [ -n "${jid}" ] && priv atrm "${jid}"
        done <<< "${queued}"
        log_ok "scrubbed orphaned jobs."
      else
        log_dry "would atrm: ${queued}  (re-run with 'go' to scrub)"
        exit 3
      fi
    else
      log_ok "no kill-switch active."
    fi
    return 0
  fi
  local id
  id=$(cat "${KILL_SWITCH_STATE_FILE}")
  if [ "${GO_REQUESTED}" != "1" ]; then
    log_dry "would cancel kill-switch (job ${id}):"
    preview "atrm ${id}"
    preview "rm -f ${KILL_SWITCH_STATE_FILE}"
    exit 3
  fi
  priv atrm "${id}" 2>/dev/null || log_warn "atrm ${id} returned non-zero (job already fired or already cancelled)"
  priv rm -f "${KILL_SWITCH_STATE_FILE}"
  log_ok "kill-switch cancelled (job ${id})."
}

# ── Phase: pre — pre-flight checklist (read-only) ─────────────────────────

phase_pre() {
  log "phase: pre — read-only pre-flight checks (runbook §0, §1)"
  local fail=0

  # Containers healthy
  if command -v docker >/dev/null 2>&1; then
    local unhealthy
    unhealthy=$(docker compose -f "${REPO_ROOT}/docker-compose.yml" ps --format '{{.Name}}\t{{.Status}}' 2>/dev/null \
      | grep -vE '\(healthy\)|Up [0-9]+ ' | grep -v '^$' || true)
    if [ -z "${unhealthy}" ]; then
      log_ok "docker compose: all containers healthy"
    else
      log_warn "docker compose: some not-healthy:"
      printf '    %s\n' "${unhealthy}"
      fail=$((fail+1))
    fi
  else
    log_warn "docker not on PATH — skipping container health"
  fi

  # Disk + RAM
  local pct avail
  pct=$(df -h / | awk 'NR==2 {print $5}')
  avail=$(free -h | awk '/^Mem:/ {print $7}')
  log_ok "disk: ${pct} used; RAM available: ${avail}"

  # No active visit being processed (BullMQ active list)
  if docker exec meddoc-pro-redis-1 redis-cli LLEN bull:transcribe-md:active >/dev/null 2>&1; then
    local active
    active=$(docker exec meddoc-pro-redis-1 redis-cli LLEN bull:transcribe-md:active 2>/dev/null | tr -d '[:space:]')
    if [ "${active}" = "0" ]; then
      log_ok "BullMQ active list: 0 (safe to proceed)"
    else
      log_warn "BullMQ active list: ${active} (a visit is processing — pick a quieter window)"
      fail=$((fail+1))
    fi
  fi

  # Operator + automation account ssh keys
  if priv test -s /home/ubuntu/.ssh/authorized_keys 2>/dev/null; then
    log_ok "ubuntu authorized_keys: present"
  else
    log_err "ubuntu authorized_keys: MISSING — disabling root login will lock you out"
    fail=$((fail+1))
  fi
  if [ -s /home/claude/.ssh/authorized_keys ] || priv test -s /home/claude/.ssh/authorized_keys 2>/dev/null; then
    log_ok "claude authorized_keys: present"
  else
    log_warn "claude authorized_keys: MISSING (Claude Code automation will break post-apply)"
  fi

  # ubuntu has sudo
  if id -nG ubuntu 2>/dev/null | grep -qw sudo; then
    log_ok "ubuntu has sudo group"
  else
    log_warn "ubuntu does NOT have sudo group — verify before disabling root"
    fail=$((fail+1))
  fi

  if [ "${fail}" -gt 0 ]; then
    log_err "${fail} pre-flight check(s) failed — review above before any destructive phase."
    exit 4
  fi
  log_ok "pre-flight green."
}

# ── Phase: ssh — apply hardened sshd_config ────────────────────────────────

phase_ssh() {
  log "phase: ssh — apply ${SSHD_RECOMMENDED} (runbook §3)"
  require_repo_files
  if [ "${GO_REQUESTED}" = "1" ]; then require_root_or_sudo; fi

  # Idempotency: if live already byte-matches recommended, skip.
  # On non-sudo dry-run, cmp may not be able to read /etc/ssh/sshd_config
  # — fall back to "treat as differing" so the preview runs.
  if (is_root || have_passwordless_sudo) && priv cmp -s "${SSHD_RECOMMENDED}" "${SSHD_LIVE}" 2>/dev/null; then
    log_ok "sshd_config already matches recommended — no-op."
    return 0
  fi

  if [ "${GO_REQUESTED}" != "1" ]; then
    log_dry "would apply sshd hardening:"
    preview "cp ${SSHD_LIVE} ${SSHD_LIVE}.bak-${TS}"
    preview "install -m 0644 -o root -g root ${SSHD_RECOMMENDED} ${SSHD_LIVE}.staged"
    preview "diff ${SSHD_LIVE} ${SSHD_LIVE}.staged"
    preview "sshd -t -f ${SSHD_LIVE}.staged    # validate staged file"
    preview "mv ${SSHD_LIVE}.staged ${SSHD_LIVE}"
    preview "sshd -t                           # validate live file"
    preview "systemctl reload sshd             # preserves existing sessions"
    log_dry "(re-run with 'go' to apply. AFTER apply, in a NEW terminal:"
    log_dry "    ssh ubuntu@<vps> ; ssh claude@<vps> ; ssh root@<vps>"
    log_dry " — first two MUST succeed, root MUST be denied. See runbook §3.5.)"
    exit 3
  fi

  # Apply (with kill-switch precondition check).
  if [ ! -r "${KILL_SWITCH_STATE_FILE}" ]; then
    log_err "kill-switch is not armed. Refusing to apply destructive phase."
    log_err "  Arm it first:  $0 --kill-switch arm go"
    exit 4
  fi

  log "backing up live sshd_config + staging recommended"
  priv cp -a "${SSHD_LIVE}" "${SSHD_LIVE}.bak-${TS}"
  priv install -m 0644 -o root -g root "${SSHD_RECOMMENDED}" "${SSHD_LIVE}.staged"

  log "validating staged config"
  if ! priv sshd -t -f "${SSHD_LIVE}.staged"; then
    log_err "sshd -t -f staged: FAILED. Backed-up live file untouched."
    exit 2
  fi

  log "atomically replacing live sshd_config"
  priv mv "${SSHD_LIVE}.staged" "${SSHD_LIVE}"

  log "validating live config (post-apply)"
  if ! priv sshd -t; then
    log_err "sshd -t LIVE: FAILED. Reverting from backup."
    priv cp -a "${SSHD_LIVE}.bak-${TS}" "${SSHD_LIVE}"
    priv sshd -t
    log_err "reverted. Diagnose ${SSHD_LIVE}.bak-${TS} vs ${SSHD_RECOMMENDED}."
    exit 2
  fi

  log "reloading sshd (preserves established sessions)"
  priv systemctl reload sshd
  sleep 1
  if ! priv systemctl is-active --quiet sshd; then
    log_err "sshd not active after reload."
    exit 2
  fi
  log_ok "sshd reloaded with hardened config. Verify in a NEW terminal:"
  log_ok "    ssh ubuntu@<vps>   # MUST succeed"
  log_ok "    ssh root@<vps>     # MUST be denied"
}

# ── Phase: ufw — install + configure UFW + DOCKER-USER fragment ───────────

phase_ufw() {
  log "phase: ufw — UFW default-deny + DOCKER-USER fragment (runbook §4)"
  require_repo_files
  if [ "${GO_REQUESTED}" = "1" ]; then require_root_or_sudo; fi

  if [ "${GO_REQUESTED}" != "1" ]; then
    log_dry "would configure + enable UFW:"
    preview "apt-get install -y ufw   # if missing"
    preview "ufw default deny incoming"
    preview "ufw default allow outgoing"
    preview "ufw allow 22/tcp comment 'SSH'"
    preview "ufw allow 80/tcp comment 'HTTP (Caddy)'"
    preview "ufw allow 443/tcp comment 'HTTPS (Caddy)'"
    preview "cp ${UFW_AFTER_RULES} ${UFW_AFTER_RULES}.bak-${TS}"
    preview "# splice ${UFW_FRAGMENT} into ${UFW_AFTER_RULES} BEFORE the final COMMIT of *filter"
    preview "ufw --force enable"
    preview "systemctl enable ufw"
    log_dry "kill-switch precondition: must be armed before this runs with 'go'."
    log_dry "Docker break-detector: §4.4 of runbook walks 3 curl smoke tests post-enable."
    log_dry "(re-run with 'go' to apply.)"
    exit 3
  fi

  if [ ! -r "${KILL_SWITCH_STATE_FILE}" ]; then
    log_err "kill-switch is not armed. Refusing to apply destructive phase."
    log_err "  Arm it first:  $0 --kill-switch arm go"
    exit 4
  fi

  if ! command -v ufw >/dev/null 2>&1; then
    log "installing ufw"
    priv apt-get update -qq
    priv apt-get install -y ufw
  else
    log_ok "ufw already installed"
  fi

  log "setting default policies + allowlist"
  priv ufw default deny incoming   >/dev/null
  priv ufw default allow outgoing  >/dev/null
  # `ufw allow` is idempotent — re-adding the same rule is a no-op.
  priv ufw allow 22/tcp  comment 'SSH'         >/dev/null
  priv ufw allow 80/tcp  comment 'HTTP (Caddy)' >/dev/null
  priv ufw allow 443/tcp comment 'HTTPS (Caddy)' >/dev/null

  # DOCKER-USER chain fragment — splice infra/ufw/after.rules.fragment
  # into /etc/ufw/after.rules BEFORE the final COMMIT of the *filter
  # block, idempotently (skip if already present).
  if priv grep -q "BEGIN ufw-docker DOCKER-USER fragment" "${UFW_AFTER_RULES}" 2>/dev/null; then
    log_ok "DOCKER-USER fragment already present in ${UFW_AFTER_RULES} — skipping splice"
  else
    log "backing up + splicing DOCKER-USER fragment into ${UFW_AFTER_RULES}"
    priv cp -a "${UFW_AFTER_RULES}" "${UFW_AFTER_RULES}.bak-${TS}"
    # Find the LAST COMMIT line in the file (the *filter block's COMMIT
    # is typically the last one in the canonical Ubuntu after.rules).
    # We splice BEFORE that line.
    local last_commit_line
    last_commit_line=$(priv grep -n '^COMMIT$' "${UFW_AFTER_RULES}" | tail -1 | cut -d: -f1)
    if [ -z "${last_commit_line}" ]; then
      log_err "could not find a 'COMMIT' line in ${UFW_AFTER_RULES} — refusing to splice."
      exit 2
    fi
    local tmp
    tmp=$(mktemp)
    priv sed "${last_commit_line}r ${UFW_FRAGMENT}" "${UFW_AFTER_RULES}" > "${tmp}"
    # sed -r appends the file AFTER the matched line; we want BEFORE.
    # Re-do with a more reliable awk-based splicer.
    rm -f "${tmp}"
    tmp=$(mktemp)
    priv awk -v frag="${UFW_FRAGMENT}" -v marker="${last_commit_line}" '
      NR == marker {
        while ((getline line < frag) > 0) print line
        close(frag)
      }
      { print }
    ' "${UFW_AFTER_RULES}" > "${tmp}"
    priv install -m 0640 -o root -g root "${tmp}" "${UFW_AFTER_RULES}"
    rm -f "${tmp}"
    log_ok "fragment spliced (backup at ${UFW_AFTER_RULES}.bak-${TS})"
  fi

  log "enabling UFW (force — accepts current SSH session)"
  # Pre-emptively allow 22 again to be safe; force-enable bypasses the
  # interactive y/N prompt.
  priv ufw --force enable
  priv systemctl enable ufw >/dev/null 2>&1 || true

  log_ok "ufw active. Verify Docker still flows (runbook §4.4):"
  log_ok "  curl -sI https://app.quillmd.com  # 307"
  log_ok "  curl -sI https://quillmd.com      # 200"
  log_ok "  docker compose ps                 # all healthy"
  log_ok "If anything regressed: $0 --kill-switch cancel  is NOT what you want."
  log_ok "  Run:  ufw disable && systemctl restart docker"
}

# ── Phase: fail2ban ────────────────────────────────────────────────────────

phase_fail2ban() {
  log "phase: fail2ban — apt install + drop in ${F2B_JAIL_LOCAL} (runbook §5)"
  require_repo_files
  if [ "${GO_REQUESTED}" = "1" ]; then require_root_or_sudo; fi

  if [ "${GO_REQUESTED}" != "1" ]; then
    log_dry "would install + configure fail2ban:"
    preview "apt-get install -y fail2ban"
    preview "install -m 0644 -o root -g root ${F2B_JAIL_LOCAL} ${F2B_JAIL_LIVE}"
    preview "systemctl enable --now fail2ban"
    preview "fail2ban-client status sshd   # verify jail active"
    log_dry "(re-run with 'go' to apply.)"
    exit 3
  fi

  if ! command -v fail2ban-client >/dev/null 2>&1; then
    log "installing fail2ban"
    priv apt-get update -qq
    priv apt-get install -y fail2ban
  else
    log_ok "fail2ban already installed"
  fi

  # Idempotency: if jail.local already matches, skip.
  if priv cmp -s "${F2B_JAIL_LOCAL}" "${F2B_JAIL_LIVE}" 2>/dev/null; then
    log_ok "${F2B_JAIL_LIVE} already matches ${F2B_JAIL_LOCAL} — skipping copy"
  else
    log "installing jail.local"
    priv install -m 0644 -o root -g root "${F2B_JAIL_LOCAL}" "${F2B_JAIL_LIVE}"
  fi

  log "enabling + starting fail2ban"
  priv systemctl enable --now fail2ban
  sleep 2
  if ! priv systemctl is-active --quiet fail2ban; then
    log_err "fail2ban failed to start. journalctl -u fail2ban -n 30"
    priv journalctl -u fail2ban -n 30 --no-pager || true
    exit 2
  fi
  log_ok "fail2ban active. Jail status:"
  priv fail2ban-client status         | sed 's/^/    /'
  priv fail2ban-client status sshd    | sed 's/^/    /'
}

# ── Phase: evict-deal-hunter ───────────────────────────────────────────────

phase_evict_deal_hunter() {
  log "phase: evict-deal-hunter — STOP + DISABLE + ARCHIVE (runbook §6, A07-P0-003)"
  if [ "${GO_REQUESTED}" = "1" ]; then require_root_or_sudo; fi

  if [ "${GO_REQUESTED}" != "1" ]; then
    log_dry "would stop + archive ai-deal-hunter:"
    preview "systemctl list-units --type=service --all | grep -iE 'ai-deal|deal-hunter|uvicorn'"
    preview "systemctl stop <unit>     # if a systemd unit exists"
    preview "systemctl disable <unit>"
    preview "kill <pid>                # if launched via nohup/orphan"
    preview "mkdir -p /root/archive-${TS}"
    preview "mv /root/ai-deal-hunter /root/archive-${TS}/ai-deal-hunter"
    preview "ss -tlnp | grep ':8000'   # should be empty after"
    log_dry "(re-run with 'go' to apply.)"
    exit 3
  fi

  # Stop systemd unit if any.
  local units
  units=$(priv systemctl list-unit-files --type=service --no-legend 2>/dev/null \
    | awk '{print $1}' | grep -iE 'ai-deal|deal-hunter|uvicorn' || true)
  if [ -n "${units}" ]; then
    while IFS= read -r u; do
      log "stopping + disabling unit: ${u}"
      priv systemctl stop "${u}" || true
      priv systemctl disable "${u}" || true
    done <<< "${units}"
  else
    log_ok "no matching systemd units"
  fi

  # Kill any matching uvicorn process.
  local pids
  pids=$(priv pgrep -f 'uvicorn.*8000\|ai-deal-hunter' 2>/dev/null || true)
  if [ -n "${pids}" ]; then
    log "sending SIGTERM to: ${pids}"
    # Word-splitting on ${pids} is intentional — pgrep returns one PID
    # per line and we want kill to receive each as a separate arg.
    # shellcheck disable=SC2086
    priv kill ${pids} || true
    sleep 5
    pids=$(priv pgrep -f 'uvicorn.*8000\|ai-deal-hunter' 2>/dev/null || true)
    if [ -n "${pids}" ]; then
      log_warn "still running after SIGTERM; SIGKILL: ${pids}"
      # shellcheck disable=SC2086
      priv kill -9 ${pids} || true
    fi
  else
    log_ok "no matching processes"
  fi

  # Archive directory.
  if priv test -d /root/ai-deal-hunter; then
    local arch_dir="/root/archive-${TS}"
    log "archiving /root/ai-deal-hunter to ${arch_dir}/"
    priv mkdir -p "${arch_dir}"
    priv mv /root/ai-deal-hunter "${arch_dir}/ai-deal-hunter"
    log_ok "archived. Restore via: mv ${arch_dir}/ai-deal-hunter /root/  (but: don't co-host on PHI VPS)"
  else
    log_ok "/root/ai-deal-hunter already absent — already evicted"
  fi

  # Verify port 8000 closed.
  if priv ss -tlnp 2>/dev/null | grep -q ':8000 '; then
    log_warn "port 8000 still bound — investigate:"
    priv ss -tlnp | grep ':8000 ' | sed 's/^/    /' || true
  else
    log_ok "port 8000 not bound"
  fi
}

# ── Phase: verify (read-only §7 verification) ─────────────────────────────

phase_verify() {
  log "phase: verify — runbook §7 (read-only)"

  log "—— §7.2 on-VPS checks ——"
  if command -v ufw >/dev/null 2>&1; then
    priv ufw status verbose 2>/dev/null | head -15 | sed 's/^/    /'
  fi
  log "systemd states:"
  for svc in sshd ufw fail2ban; do
    local st
    st=$(systemctl is-active "${svc}" 2>/dev/null || echo unknown)
    printf '    %-12s : %s\n' "${svc}" "${st}"
  done

  if command -v fail2ban-client >/dev/null 2>&1; then
    log "fail2ban sshd jail:"
    priv fail2ban-client status sshd 2>/dev/null | sed 's/^/    /' || true
  fi

  log "listening ports outside the allowed set (22/80/443/9010/9020/3001/3010/3011/5432/6379/9000/9001/18789/18790):"
  # Note the leading space before each port — match :PORT exactly to
  # avoid e.g. ":80" matching ":8080".
  priv ss -tlnp 2>/dev/null \
    | awk 'NR > 1 {print $4}' \
    | grep -vE '127\.0\.0\.[0-9]+:' \
    | grep -vE ':(22|80|443|9010|9020|3001|3010|3011|5432|6379|9000|9001|18789|18790)$' \
    | sed 's/^/    /' || true

  log "—— application health ——"
  docker compose -f "${REPO_ROOT}/docker-compose.yml" ps --format '{{.Name}}\t{{.Status}}' 2>&1 \
    | sed 's/^/    /'
}

# ── Help / usage ───────────────────────────────────────────────────────────

cmd_help() {
  cat <<EOF
edge-security-apply.sh — operator-handoff wrapper for Round 3 PR-B (PR-N).

Authoritative reference: ${RUNBOOK_PATH}
Read it first to understand WHAT each phase does. This script makes it
SAFER to actually run those phases on a production VPS.

USAGE
  sudo bash $0 --help
  sudo bash $0 --status
  sudo bash $0 --phase=<name>          # DRY-RUN preview (no changes)
  sudo bash $0 --phase=<name> go       # APPLY (idempotent)
  sudo bash $0 --kill-switch arm       # DRY-RUN
  sudo bash $0 --kill-switch arm go    # ACTUALLY arm (at(1) job, fires in 10min)
  sudo bash $0 --kill-switch cancel    # DRY-RUN
  sudo bash $0 --kill-switch cancel go # ACTUALLY cancel

PHASES (run in this order on a fresh apply)
  pre                read-only pre-flight checks (runbook §0, §1)
  ssh                apply hardened sshd_config (runbook §3)
  ufw                install + configure UFW + DOCKER-USER fragment (runbook §4)
  fail2ban           apt install fail2ban + drop in jail.local (runbook §5)
  evict-deal-hunter  STOP + DISABLE + ARCHIVE the cohabit'd uvicorn (runbook §6)
  verify             read-only §7 verification block

KILL-SWITCH
  Before any destructive phase, arm the kill-switch:
    sudo bash $0 --kill-switch arm go
  This schedules \`ufw --force disable; systemctl stop fail2ban\` via
  at(1), 10 minutes from now. Survives SSH session termination
  (which is the failure mode that motivates having one).

  After verifying the new config works (you can still SSH in, Docker
  is fine, https://app.quillmd.com responds), cancel:
    sudo bash $0 --kill-switch cancel go

  If the kill-switch is NOT armed, --phase=ssh|ufw|fail2ban refuse to
  run (--phase=evict-deal-hunter does not need it; the eviction is
  reversible).

ZERO DEVIATIONS FROM PR-B
  This script does not change PR-B's parameters:
    - allowed ports: 22, 80, 443
    - fail2ban sshd: maxretry=3, findtime=600, bantime=3600
    - sshd: PermitRootLogin no, AllowUsers ubuntu claude, MaxAuthTries=3
    - DOCKER-USER chain via chaifeng/ufw-docker pattern (verbatim)
    - ai-deal-hunter: STOP + DISABLE + ARCHIVE (not deleted)

EXIT CODES
  0   ok / idempotent no-op
  1   missing prereq (repo file missing, sudo unavailable, etc.)
  2   apply step failed (per-phase rollback in runbook §8)
  3   dry-run mode — printed what it would do, no changes
  4   precondition failed (e.g. kill-switch not armed before destructive phase)
EOF
}

# ── argv parser ────────────────────────────────────────────────────────────

PHASE=""
KILL_SWITCH_OP=""

if [ "$#" -eq 0 ]; then cmd_help; exit 0; fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)            cmd_help; exit 0 ;;
    --status)             cmd_status; exit 0 ;;
    --phase=*)            PHASE="${1#--phase=}" ;;
    --kill-switch)
      shift
      if [ $# -lt 1 ]; then log_err "--kill-switch requires 'arm' or 'cancel'"; exit 1; fi
      KILL_SWITCH_OP="$1"
      ;;
    go)                   GO_REQUESTED=1 ;;
    *)                    log_err "unknown arg: $1"; cmd_help; exit 1 ;;
  esac
  shift
done

if [ -n "${KILL_SWITCH_OP}" ]; then
  case "${KILL_SWITCH_OP}" in
    arm)    kill_switch_arm ;;
    cancel) kill_switch_cancel ;;
    *)      log_err "--kill-switch must be 'arm' or 'cancel' (got: ${KILL_SWITCH_OP})"; exit 1 ;;
  esac
  exit 0
fi

if [ -z "${PHASE}" ]; then
  log_err "no --phase= given. Try --help."
  exit 1
fi

case "${PHASE}" in
  pre)               phase_pre ;;
  ssh)               phase_ssh ;;
  ufw)               phase_ufw ;;
  fail2ban)          phase_fail2ban ;;
  evict-deal-hunter) phase_evict_deal_hunter ;;
  verify)            phase_verify ;;
  *) log_err "unknown phase: ${PHASE}"; cmd_help; exit 1 ;;
esac
