// ============================================================================
// The QA WORKER must DECLARE production's runtime feature-flag universe.
// ----------------------------------------------------------------------------
// ⚠️ WRITTEN BECAUSE EVERY STANDING CHECK WAS GREEN WHILE THE QA WORKER RAN
// WITH ALL ELEVEN PRODUCTION FEATURE FLAGS OFF. Measured 2026-08-24, in the
// live containers, both running `npx tsx src/worker.ts` — identical shape, so
// the env is the only difference and there is no build-time inlining involved:
//
//     prod worker: templateNativeDocxEnabled() = true    | 11 NEXT_PUBLIC_*
//     QA   worker: templateNativeDocxEnabled() = false   |  0 NEXT_PUBLIC_*
//
// CONSEQUENCE: `worker/template-twin-fill-step.ts:76` returned
// `{status:'skipped', reason:'flag_off'}` for EVERY QA visit. The per-visit
// twin fill could not run on QA at all, `template_twin_fill_manifests` sat at
// 0, and ruling #144's acceptance walk — override -> EXPORT-AFTER-OVERRIDE ->
// SIGN-AFTER-OVERRIDE — was UNPERFORMABLE on the one stack reserved for it.
//
// ⚠️ THE MECHANISM IS A SIDE EFFECT OF A CONTROL THAT IS CORRECT, WHICH IS WHY
// NOBODY LOOKED. Production delivers each flag TWICE — `build.args` (Next
// inlines it into the frontend) and `env_file: .env` (the worker's runtime
// env); `docker-compose.yml:561-573` says so in its own comments.
// `docker-compose.qa.yml` declares the same names under `build.args` ONLY and
// has ZERO `env_file` declarations — deliberately, because inheriting the
// shared `.env` is what once put 298 real Anthropic calls through this stack.
// The severance is right. The flags rode `.env` to the worker, so the worker
// silently lost all of them while the APP kept them by inlining.
//
// ⚠️ AND THIS IS THE SAME CLASS THE FILE HAD ALREADY FIXED ONCE, ONE VARIABLE
// AT A TIME. The comment above `TRANSCRIBE_MD_EVIDENCE_ANCHORS` records the
// identical defect on 2026-08-10 — "this stack never set it… L4b has NEVER run
// on QA" — and fixed exactly the one variable that had bitten. The predicate it
// should have been swept by is *every var production's worker carries at
// runtime that this stack does not*. Naming a class is not enumerating it.
//
// ⚠️ HONEST LIMIT, SO THIS GATE IS NOT READ WIDER THAN IT IS. This asserts the
// COMPOSE FILE declares them. It cannot see a running container, so a stack
// that was never recreated after an edit still diverges with this gate green —
// the bind-mount lesson at one remove. `scripts/check-qa-worker-flag-universe.sh`
// is the live-container half, and the two are deliberately separate.
//
// ⚠️ SCOPE IS THE WORKER, DELIBERATELY. The QA APP is a Next BUILD: its
// NEXT_PUBLIC_* are inlined at image-build time and are legitimately ABSENT
// from its runtime env. Demanding a runtime env there would demand something
// harmless. The worker reads at runtime; that is where absence is a defect.
// ============================================================================

import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const COMPOSE = '../../docker-compose.qa.yml';
const WORKER_SERVICE = 'transcribe-md-worker';

/** ⚠️ RESOLVED AT RUNTIME, AND MISSING IS A FAILURE — NEVER A SKIP.
 *  Same doctrine as `gate-workflows-parse`: `js-yaml` reaches this tree
 *  transitively, so a `try { … } catch { return }` would make this guard VANISH
 *  on an unrelated lockfile change — a guard that silently stops running is the
 *  exact defect class this file exists to catch. */
const req = createRequire(__filename);
function loadYaml(): (src: string) => unknown {
  try {
    return (req('js-yaml') as { load: (s: string) => unknown }).load;
  } catch {
    throw new Error(
      'the YAML parser is not installed, so this guard cannot check anything. ' +
        'js-yaml reaches this tree transitively via eslint; if that changed, ' +
        'add it as an explicit devDependency rather than deleting this test.',
    );
  }
}

/**
 * The declared universe: production's MEASURED worker runtime set, with QA's
 * OWN urls.
 *
 * ⚠️ THE TWO URLS ARE NOT PRODUCTION'S, AND THAT IS THE POINT. Copying prod's
 * values verbatim would point the isolated stack at `app.quillmd.com`. They
 * match this file's own `build.args` (:173-174) instead.
 */
const REQUIRED: ReadonlyArray<readonly [string, string]> = [
  ['NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX', 'true'],
  ['NEXT_PUBLIC_TEMPLATE_NATIVE_PDF', 'true'],
  ['NEXT_PUBLIC_ULTRASOUND_SPECIALTY', 'true'],
  ['NEXT_PUBLIC_REVIEW_DOC_VIEW', 'true'],
  ['NEXT_PUBLIC_UX_SIMPLIFY', 'true'],
  ['NEXT_PUBLIC_VISIT_DOC_PAGE', 'true'],
  ['NEXT_PUBLIC_CHAT_EDITOR', 'true'],
  ['NEXT_PUBLIC_DOC_PREVIEW', 'true'],
  ['NEXT_PUBLIC_SETTINGS_SIMPLE_ROW', 'true'],
  ['NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL', 'http://localhost:9020'],
  ['NEXT_PUBLIC_MARKETING_URL', 'http://localhost:9010'],
];

function workerEnvironment(): Record<string, string> {
  const raw = readFileSync(COMPOSE, 'utf8');
  const doc = loadYaml()(raw) as {
    services?: Record<string, { environment?: Record<string, unknown> }>;
  };
  const svc = doc?.services?.[WORKER_SERVICE];
  if (!svc) {
    throw new Error(
      `${COMPOSE} has no service "${WORKER_SERVICE}". The parse is wrong, or the ` +
        'service was renamed — either way this gate is measuring nothing, which ' +
        'is the failure it exists to prevent. Fix the parse, do not delete the test.',
    );
  }
  const env = svc.environment;
  if (!env || typeof env !== 'object') {
    throw new Error(
      `${WORKER_SERVICE} has no \`environment:\` mapping. Note this gate assumes the ` +
        'MAPPING form (`KEY: value`), not the LIST form (`- KEY=value`); if the file ' +
        'switched forms this must be taught to read it rather than silently pass.',
    );
  }
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(env)) out[k] = v === null ? '' : String(v);
  return out;
}

describe('F27 — the QA worker declares production\'s runtime flag universe', () => {
  // ⚠️ NON-VACUITY FIRST. Everything below is a claim about a parsed mapping,
  // and a parse that silently yields `{}` would make every "is it declared"
  // assertion fail LOUDLY (good) while an inverted gate would pass silently.
  // This arm pins that the parse actually found the block, using a key that is
  // NOT one of the ones under test — so it discriminates the instrument rather
  // than the target.
  it('POSITIVE CONTROL — the worker environment parses and carries a known-present key', () => {
    const env = workerEnvironment();
    expect(Object.keys(env).length).toBeGreaterThan(5);
    // MOCK_AI_CALLS is hard-coded in this service unconditionally and is the
    // single most load-bearing line in the file. If it is gone, something far
    // larger than F27 is wrong.
    expect(env.MOCK_AI_CALLS).toBe('true');
    // And the 2026-08-10 precedent for this exact class must still be present.
    expect(env.TRANSCRIBE_MD_EVIDENCE_ANCHORS).toBe('true');
  });

  it.each(REQUIRED)('declares %s = %s', (name, want) => {
    const env = workerEnvironment();
    expect(
      Object.prototype.hasOwnProperty.call(env, name),
      `${name} is NOT declared in ${WORKER_SERVICE}.environment. The QA worker ` +
        'runs `npx tsx src/worker.ts` and reads this at RUNTIME — an absent flag ' +
        'means the feature is OFF on QA while it is ON in production, and every ' +
        'behavioural proof run here is a proof about a system nobody ships.',
    ).toBe(true);
    expect(env[name]).toBe(want);
  });

  // ⚠️ THE TRAP THIS FILE NAMES AT LENGTH ELSEWHERE, ASSERTED RATHER THAN
  // TRUSTED. `${VAR:-default}` applies the default only when the variable is
  // UNSET, and compose interpolation reads the project `.env` WHETHER OR NOT
  // this file declares an `env_file`. Production sets every one of these, so an
  // interpolated form here silently inherits PRODUCTION's value — which is how
  // `${MOCK_AI_CALLS:-true}` and `${ANTHROPIC_API_KEY:-mock-key-qa}` cost 298
  // real Anthropic calls from the stack whose header promised it could reach
  // nothing.
  //
  // ⚠️ SCOPED TO `environment:` (THE RUNTIME HALF) AND NOT TO `build.args`,
  // AND THE NARROWING IS A CORRECTION THAT THIS ARM ITSELF FORCED. Its first
  // version scanned the whole FILE and went red on nine `build.args` lines —
  // reddening against its own author on first execution, which is the strongest
  // evidence a guard can give about itself. Then the callers were diffed, per
  // the standing rule, and the finding inverted:
  //
  //     .github/workflows/e2e.yml:162-169   env: NEXT_PUBLIC_… "true"
  //     .github/workflows/e2e.yml:480-486   --build-arg NEXT_PUBLIC_…=true
  //     .github/workflows/a11y.yml:233-240  env: NEXT_PUBLIC_… 'true'
  //
  // CI does NOT rely on `.env` inheritance for the build args — it supplies
  // every value explicitly, and the `${…}` form is the mechanism that lets it.
  // Hardcoding literals there would silently make those `env:` blocks INERT and
  // remove CI's ability to build QA with a flag OFF to exercise a rollback.
  // e2e.yml:667 records a run where a missing flag did exactly that kind of
  // damage. So the interpolation in `build.args` is load-bearing and stays.
  //
  // ⚠️ RESIDUAL, RECORDED RATHER THAN SILENTLY DROPPED: a LOCAL
  // `docker compose -f docker-compose.qa.yml build` on this host still
  // interpolates those nine build args from `/opt/meddoc-pro/.env`, which holds
  // PRODUCTION's values. Today every one is `true` so the inherited value equals
  // the intended one — a POPULATION fact, not a property. RE-ARMING CONDITION:
  // one flag set to `false` in `.env` for a production rollback, at which point
  // a local QA build silently inherits the rollback. Closing it properly means a
  // QA-specific env file, not a literal; that is a separate item.
  //
  // The runtime half below has no such caller: nothing overrides it, and
  // inheritance there is pure downside.
  it('⚠️ declares the RUNTIME flags as LITERALS — never ${VAR:-default}, which inherits from the shared .env', () => {
    const env = workerEnvironment();
    const offenders = Object.entries(env)
      .filter(([k]) => k.startsWith('NEXT_PUBLIC_'))
      .filter(([, v]) => v.includes('${'))
      .map(([k, v]) => `${k} -> ${v}`);
    expect(
      offenders,
      'these are interpolated and will inherit whatever the shared .env holds:\n  ' +
        offenders.join('\n  '),
    ).toEqual([]);
  });

  // ⚠️ THE SET COMPARISON RUNS BOTH WAYS. An UNDECLARED NEXT_PUBLIC_* in the
  // worker block means somebody added a flag and did not update this list —
  // which is precisely how the original divergence survived a file that had
  // already fixed one member of the same class.
  it('carries no UNDECLARED NEXT_PUBLIC_* — the list cannot go stale silently', () => {
    const env = workerEnvironment();
    const present = Object.keys(env)
      .filter((k) => k.startsWith('NEXT_PUBLIC_'))
      .sort();
    const declared = REQUIRED.map(([n]) => n).sort();
    expect(present).toEqual(declared);
  });
});
