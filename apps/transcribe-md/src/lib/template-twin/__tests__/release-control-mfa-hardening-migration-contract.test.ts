import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");
const v2 = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260719163000_template_twin_production_control_plane_hardening_v2/migration.sql",
  ),
  "utf8",
);
const v3 = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260719164000_template_twin_production_control_plane_hardening_v3/migration.sql",
  ),
  "utf8",
);
const v4 = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260720123000_template_twin_production_control_plane_mfa_hardening_v4/migration.sql",
  ),
  "utf8",
);
const POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS =
  "U&'[\\0009-\\000D\\0020\\00A0\\1680\\2000-\\200A\\2028\\2029\\202F\\205F\\3000\\FEFF]'";

function functionDefinition(name: string, nextMarker: string): string {
  const start = v4.indexOf(`CREATE OR REPLACE FUNCTION public.${name}`);
  const end = v4.indexOf(nextMarker, start + 1);
  expect(start, `${name} must be replaced by v4`).toBeGreaterThanOrEqual(0);
  expect(
    end,
    `${name} must have an auditable definition boundary`,
  ).toBeGreaterThan(start);
  return v4.slice(start, end);
}

function expectCanonicalMfa(definition: string, alias: string): void {
  expect(definition).toContain(`${alias}."mfaEnabled" = TRUE`);
  expect(definition).toContain(`${alias}."mfaSecret" IS NOT NULL`);
  expect(definition).toContain("regexp_replace(");
  expect(definition).toContain(`${alias}."mfaSecret",`);
  expect(definition).toContain(POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS);
  expect(definition).toMatch(/\)\s*<> ''/u);
  expect(definition).toContain(`${alias}."mfaVerifiedAt" IS NOT NULL`);
  expect(definition).toContain(`${alias}."mfaVerifiedAt" <= CURRENT_TIMESTAMP`);
  expect(definition).toContain(
    `'SUPER_ADMIN'::public."Product" = ANY(${alias}."products")`,
  );
}

describe("Template Twin production control-plane complete-MFA migration", () => {
  it("replaces the exhaustive final actor predicate census", () => {
    expect(v2.match(/account\."mfaEnabled" = TRUE/g)).toHaveLength(3);
    expect(v2.match(/actor\."mfaEnabled" = TRUE/g)).toHaveLength(1);
    expect(v3).toContain(
      "public.template_twin_verify_release_admin_session(\n  actor_user_id TEXT,",
    );

    const definitions = [
      [
        "template_twin_verify_release_actor(",
        "REVOKE ALL ON FUNCTION public.template_twin_verify_release_actor",
        "account",
      ],
      [
        "template_twin_release_approvals_are_current(",
        "REVOKE ALL ON FUNCTION public.template_twin_release_approvals_are_current",
        "account",
      ],
      [
        "template_twin_guard_release_approval_insert()",
        "REVOKE ALL ON FUNCTION public.template_twin_guard_release_approval_insert",
        "account",
      ],
      [
        "template_twin_guard_checkpoint_pass()",
        "REVOKE ALL ON FUNCTION public.template_twin_guard_checkpoint_pass",
        "actor",
      ],
      [
        "template_twin_verify_release_admin_session(",
        "REVOKE ALL ON FUNCTION public.template_twin_verify_release_admin_session",
        "account",
      ],
    ] as const;

    for (const [name, marker, alias] of definitions) {
      expectCanonicalMfa(functionDefinition(name, marker), alias);
    }
  });

  it("never projects the MFA secret from either bounded session verifier", () => {
    for (const [name, marker] of [
      [
        "template_twin_verify_release_actor(",
        "LANGUAGE sql VOLATILE SECURITY DEFINER",
      ],
      [
        "template_twin_verify_release_admin_session(",
        "LANGUAGE sql VOLATILE SECURITY DEFINER",
      ],
    ] as const) {
      const signature = functionDefinition(name, marker);
      expect(signature).toContain("RETURNS TABLE");
      expect(signature).not.toContain("mfaSecret");
      expect(signature).toContain('"sessionSha256" TEXT');
    }
  });

  it("revokes authority for invalid MFA and for any secret or verification rotation", () => {
    const lifecycle = functionDefinition(
      "template_twin_revoke_authority_on_user_lifecycle()",
      "REVOKE ALL ON FUNCTION public.template_twin_revoke_authority_on_user_lifecycle",
    );
    expect(lifecycle).toContain('NEW."mfaEnabled" IS DISTINCT FROM TRUE');
    expect(lifecycle).toContain('NEW."mfaSecret" IS NULL');
    expect(lifecycle).toContain("NOT (");
    expect(lifecycle).toContain('NEW."mfaSecret",');
    expect(lifecycle).toContain(POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS);
    expect(lifecycle).toContain('NEW."mfaVerifiedAt" IS NULL');
    expect(lifecycle).toContain('NEW."mfaVerifiedAt" > CURRENT_TIMESTAMP');
    expect(lifecycle).toContain(
      'NEW."mfaSecret" IS DISTINCT FROM OLD."mfaSecret"',
    );
    expect(lifecycle).toContain(
      'NEW."mfaVerifiedAt" IS DISTINCT FROM OLD."mfaVerifiedAt"',
    );
    expect(lifecycle).toContain(
      "public.template_twin_revoke_release_authority(",
    );

    const triggerColumns =
      '"mfaEnabled", "mfaSecret", "mfaVerifiedAt", "products", "forceLogoutAt"';
    expect(v4.match(new RegExp(triggerColumns, "g"))).toHaveLength(2);
    expect(v4).toContain(
      "CREATE TRIGGER aaa_template_twin_user_lifecycle_statement_lock",
    );
    expect(v4).toContain(
      "CREATE TRIGGER template_twin_user_lifecycle_authority_revoke",
    );
  });

  it("uses audited install-time revocation and keeps approval/history evidence immutable", () => {
    expect(v4).toContain("DO $reconcile_incomplete_mfa$");
    expect(v4).toContain(
      "PERFORM public.template_twin_revoke_release_authority(",
    );
    expect(v4).toContain("AUTHORITY_MFA_INCOMPLETE_INSTALL");
    expect(v4).toContain("SET CONSTRAINTS ALL IMMEDIATE");
    expect(v4).toContain("left stale live approvals");
    expect(v4.split(POSTGRES_ECMASCRIPT_TRIM_WHITESPACE_CLASS)).toHaveLength(9);
    expect(v4).not.toContain("btrim(");
    expect(v4).not.toContain("[[:space:]]");
    expect(v4).not.toMatch(
      /DELETE\s+FROM\s+public\."template_twin_release_(?:authorities|approval_decisions)"/iu,
    );
    expect(v4).not.toMatch(
      /UPDATE\s+public\."template_twin_release_approval_decisions"/iu,
    );
    expect(v4).not.toMatch(
      /UPDATE\s+public\."(?:practices|template_twin_rollout_controls)"[\s\S]{0,240}(?:"templateTwinEnabled"|"enabled")\s*=\s*TRUE/iu,
    );
  });

  it("preserves definer isolation, trusted paths, and exact release-control grants", () => {
    expect(v4.match(/SECURITY DEFINER/g)).toHaveLength(6);
    expect(
      v4.match(/SET search_path = pg_catalog, public, pg_temp/g),
    ).toHaveLength(6);
    for (const signature of [
      "template_twin_verify_release_actor(TEXT, TEXT)",
      "template_twin_release_approvals_are_current(\n  UUID, CHAR(64)\n)",
      "template_twin_verify_release_admin_session(\n  TEXT, TEXT\n)",
    ]) {
      expect(v4).toContain(`GRANT EXECUTE ON FUNCTION public.${signature}`);
    }
    for (const name of [
      "template_twin_verify_release_actor",
      "template_twin_release_approvals_are_current",
      "template_twin_guard_release_approval_insert",
      "template_twin_guard_checkpoint_pass",
      "template_twin_verify_release_admin_session",
      "template_twin_revoke_authority_on_user_lifecycle",
    ]) {
      expect(v4).toContain(`REVOKE ALL ON FUNCTION public.${name}`);
    }
    expect(v4).toContain("procedure.proname LIKE 'template_twin_%'");
    expect(v4).toContain(
      "ALTER FUNCTION %I.%I(%s) SET search_path TO pg_catalog, public, pg_temp",
    );
    expect(v4).toContain(
      "@> ARRAY['search_path=pg_catalog, public, pg_temp']::TEXT[]",
    );
  });

  it("retains the full checkpoint receipt, monitoring, census, and audit contract", () => {
    const checkpoint = functionDefinition(
      "template_twin_guard_checkpoint_pass()",
      "REVOKE ALL ON FUNCTION public.template_twin_guard_checkpoint_pass",
    );
    for (const fragment of [
      "template_twin_release_approvals_are_current",
      "metric.\"evaluation\" <> 'PASS'",
      'receipt."releaseGeneration" = metric."releaseGeneration"',
      'receipt."globalGeneration" = metric."globalGeneration"',
      'practice."templateTwinEnabled" = FALSE',
      'NEW."passedPhysicianCount" <> expected_physician_count',
      "TEMPLATE_TWIN_ROLLOUT_CHECKPOINT_PASSED",
      "metricSnapshotSha256",
    ]) {
      expect(checkpoint).toContain(fragment);
    }
  });
});
