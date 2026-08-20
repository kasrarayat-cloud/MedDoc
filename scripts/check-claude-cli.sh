#!/usr/bin/env bash
# ============================================================================
# THE LOOP'S OWN INTERPRETER — is it installed, and is it a COMPLETE pair?
# ----------------------------------------------------------------------------
# READ-ONLY. 0 = usable · 1 = BROKEN/mismatched · 2 = cannot tell
#
# ⚠️ WHY THIS EXISTS. On 2026-08-20T01:36Z the `claude` CLI auto-updated itself
# to 2.1.237. That version's linux native package was never published — the
# registry's newest `@anthropic-ai/claude-code-linux-x64` was 2.1.236 — so every
# invocation died with "claude native binary not installed" and the FOUNDATION
# loop went dark mid-run. Nothing said so: the loop's own liveness signals were
# all about tmux and the tree, and the interpreter it shells out to is not
# something any of them look at.
#
# Running the documented postinstall did NOT help; there was nothing to download.
# The repair was to pin back to the newest COMPLETE pair.
#
# ⚠️ THE FAILURE IS A PAIR MISMATCH, NOT A MISSING BINARY, AND THE CHECK MUST SAY
# WHICH. "not installed" sends you to a reinstall that cannot work. "the wrapper
# is 2.1.237 and no native package exists for it" sends you to a pin.
# ============================================================================
set -uo pipefail

# The binary under test is injectable so the RED path can be proved without
# shadowing the real CLI on PATH — writing an executable called `claude` onto
# PATH to test a check that looks for `claude` is its own hazard.
CLI="${CLAUDE_CLI_BIN:-claude}"

say(){ echo "$1"; }

if ! command -v "$CLI" >/dev/null 2>&1; then
  say "🟡 CANNOT TELL — no \`$CLI\` on PATH; this host may not run the loop."
  exit 2
fi

ver_out="$("$CLI" --version 2>&1)"
rc=$?

if [ $rc -eq 0 ] && printf '%s' "$ver_out" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+'; then
  ver="$(printf '%s' "$ver_out" | awk '{print $1}')"
  say "🟢 claude CLI answers — ${ver}"
  exit 0
fi

# It did not answer. Distinguish the pair-mismatch case by name, because that is
# the one whose obvious repair is wrong.
if printf '%s' "$ver_out" | grep -q 'native binary not installed'; then
  wrapper=""
  pkg="$(command -v "$CLI")"
  pkg="$(dirname "$(readlink -f "$pkg")")/.."
  if [ -f "$pkg/package.json" ]; then
    wrapper="$(node -p "require('$pkg/package.json').version" 2>/dev/null || true)"
  fi
  say "🔴 claude CLI is BROKEN — native binary missing${wrapper:+ (wrapper ${wrapper})}."
  say "   ⚠️ Do NOT just re-run the postinstall: if the wrapper auto-updated to a"
  say "   version whose native package was never published, there is nothing to"
  say "   download. Compare against the registry and PIN to the newest complete"
  say "   pair, e.g.:"
  say "     npm view @anthropic-ai/claude-code-linux-x64 versions --json | tail"
  say "     npm install -g @anthropic-ai/claude-code@<that version>"
  say "   Reference: 2026-08-20, wrapper 2.1.237 vs native 2.1.236 — loop dark."
  exit 1
fi

say "🔴 claude CLI did not answer \`--version\` (rc=$rc): ${ver_out%%$'\n'*}"
exit 1
