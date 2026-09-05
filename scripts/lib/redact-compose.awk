# ============================================================================
# Redact credential-shaped values out of `docker compose config` output.
# ----------------------------------------------------------------------------
# ⚠️ IT LIVES IN ITS OWN FILE ON PURPOSE. The first version was an inline awk
# program inside a bash function inside dc.sh, and the nested quoting broke it
# so badly that it emitted NOTHING — which passed a "no secret appears in the
# output" check perfectly. Only the negative control (does a NON-secret line
# survive?) exposed it. A redactor that eats everything is not a redactor.
#
# ⚠️ MASKING IS BY KEY SHAPE, AND IT FAILS TOWARD MASKING. A list of known
# secret NAMES would leak the day somebody adds a name nobody listed, silently.
# Over-masking costs one deliberate second command; under-masking costs a
# credential rotation.
{
  line = $0

  # `KEY: value` (compose YAML) and `- KEY=value` (environment list form)
  if (match(line, /[A-Za-z0-9_]*(PASSWORD|PASSWD|SECRET|KEY|TOKEN|CREDENTIAL|PRIVATE|SALT|SEED)[A-Za-z0-9_]*[ \t]*[:=]/)) {
    print substr(line, 1, RSTART + RLENGTH - 1) " ***REDACTED by dc.sh***"
    next
  }

  # any URL carrying inline credentials: scheme://user:pass@host
  if (match(line, /:\/\/[^:/ \t]+:[^@ \t]+@/)) {
    pre  = substr(line, 1, RSTART - 1)
    post = substr(line, RSTART + RLENGTH)
    print pre "://***REDACTED***@" post
    next
  }

  print line
}
