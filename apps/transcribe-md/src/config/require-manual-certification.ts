/**
 * `require manual certification` — the escape hatch from auto-certification.
 * Owner ruling: auto-certification is the DEFAULT; this is how a practice opts
 * out. **Default OFF.**
 *
 * ⚠️ IT IS AN ENV FLAG TODAY, NOT A PER-PRACTICE COLUMN, AND THAT IS A RECORDED
 * CHOICE RATHER THAN AN OVERSIGHT.
 *
 * The ruling describes it per-practice. `Practice` has no settings column, so
 * per-practice means a migration on a clinical-adjacent table — with the
 * write-path sweep, the drift declaration and the deploy that implies — for a
 * hatch that **no practice has yet asked for** and whose default is OFF.
 *
 * So: the SEAM is built here and honoured at the only call site that matters.
 * When a practice actually asks, the migration replaces this function's body and
 * nothing else moves. Filed rather than pretended: until then the flag is
 * deployment-wide, and a deployment with one practice cannot tell the
 * difference.
 *
 * ⚠️ FAIL-OPEN TO AUTO-CERTIFY, DELIBERATELY. An unreadable or absent flag means
 * OFF, which means auto-certification proceeds. The opposite default would let a
 * typo silently return every doctor to eighty clicks, and they would have no way
 * to tell that a flag had done it.
 */
export function requireManualCertification(): boolean {
  return process.env.REQUIRE_MANUAL_CERTIFICATION === 'true';
}

export const REQUIRE_MANUAL_CERTIFICATION_FLAG = 'REQUIRE_MANUAL_CERTIFICATION';
