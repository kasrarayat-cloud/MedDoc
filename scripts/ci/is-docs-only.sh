#!/usr/bin/env bash
# ============================================================================
# IS THIS CHANGE DOCS-ONLY?  exit 0 = YES (heavy CI may skip) · exit 1 = NO/UNKNOWN
# ----------------------------------------------------------------------------
# ⚠️ FAIL-CLOSED BY CONSTRUCTION. Every uncertainty returns 1 (RUN THE SUITE).
# A false "docs-only" merges a CODE change on an untested green — this slice's
# clinical defect — while a false "not docs-only" costs only minutes. The two
# errors are not symmetric, so the predicate is biased hard toward running.
#
# CONSERVATIVE: skip only when the change is NON-EMPTY and EVERY file matches
# the allowlist. One runtime file among a hundred docs files => RUN.
#
# The allowlist is deliberately IDENTICAL to `scripts/lib/declaration.sh`'s
# DECLARATION_NONRUNTIME_RE, so "non-runtime" means ONE thing in this repo.
# If you change one, change both, or a deploy declaration and CI will disagree
# about what a runtime change is.
# ============================================================================
set -uo pipefail

ALLOW='^(docs/|[^/]+\.md$)'
say() { echo "[is-docs-only] $*" >&2; }

BASE="${1:-}"; HEAD_REF="${2:-HEAD}"

if [ -z "$BASE" ]; then say "no base ref given -> RUN"; exit 1; fi
if ! git rev-parse --verify -q "$BASE" >/dev/null 2>&1; then say "base '$BASE' unresolvable -> RUN"; exit 1; fi
if ! git rev-parse --verify -q "$HEAD_REF" >/dev/null 2>&1; then say "head '$HEAD_REF' unresolvable -> RUN"; exit 1; fi

FILES="$(git diff --name-only "$BASE...$HEAD_REF" 2>/dev/null)" || { say "git diff failed -> RUN"; exit 1; }
if [ -z "$FILES" ]; then say "empty file list -> RUN (cannot prove docs-only)"; exit 1; fi

TOTAL=$(printf '%s\n' "$FILES" | wc -l)
OFFENDERS="$(printf '%s\n' "$FILES" | grep -Ev "$ALLOW" || true)"
NOFF=0; [ -n "$OFFENDERS" ] && NOFF=$(printf '%s\n' "$OFFENDERS" | wc -l)

say "files=$TOTAL non-docs=$NOFF"
if [ "$NOFF" -gt 0 ]; then
  say "RUN — non-docs files present:"
  printf '%s\n' "$OFFENDERS" | head -20 | sed 's/^/  [is-docs-only]   /' >&2
  exit 1
fi
say "DOCS-ONLY — all $TOTAL file(s) match $ALLOW"
exit 0
