import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const repositoryRoot = resolve(process.cwd(), "../..");
const migration = readFileSync(
  resolve(
    repositoryRoot,
    "packages/db/prisma/migrations/20260719160000_template_twin_production_control_plane_v1/migration.sql",
  ),
  "utf8",
);
const route = readFileSync(
  resolve(
    repositoryRoot,
    "apps/transcribe-md/src/app/api/admin/template-twin/releases/route.ts",
  ),
  "utf8",
);

describe("Template Twin production control-plane migration contract", () => {
  it("is additive, empty, and leaves both persisted rollout scopes default-off", () => {
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_candidates"',
    );
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_authorities"',
    );
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_checkpoints"',
    );
    expect(migration).toContain(
      'CREATE TABLE "template_twin_release_metric_snapshots"',
    );
    expect(migration).not.toMatch(
      /UPDATE\s+"template_twin_rollout_controls"[\s\S]{0,160}SET[\s\S]{0,80}"enabled"\s*=\s*TRUE/iu,
    );
    expect(migration).not.toMatch(
      /UPDATE\s+"practices"[\s\S]{0,160}"templateTwinEnabled"\s*=\s*TRUE/iu,
    );
    expect(migration).not.toContain(
      'INSERT INTO "template_twin_release_authorities"',
    );
    expect(migration).toContain(
      "requires a disabled, open-fence rollout baseline",
    );
  });

  it("serializes with rollback and binds enablement to a transaction-local exact release capability", () => {
    expect(migration).toContain("pg_advisory_xact_lock(73119, 20260719)");
    expect(migration).toContain("template_twin_issue_release_capability");
    expect(migration).toContain('cap."transactionId" = txid_current()');
    expect(migration).toContain('cap."backendPid" = pg_backend_pid()');
    expect(migration).toContain(
      "production enablement capability is forged or stale",
    );
    expect(migration).toContain(
      "aab_template_twin_global_release_capability_guard",
    );
    expect(migration).toContain(
      "aab_template_twin_practice_release_capability_guard",
    );
    expect(migration).toContain(
      "Template Twin release capability receipts are immutable",
    );
  });

  it("makes identity, approval, metric, checkpoint, and audit evidence immutable", () => {
    expect(migration).toContain("Template Twin release identity is immutable");
    expect(migration).toContain(
      "Template Twin release evidence is append-only",
    );
    expect(migration).toContain(
      "Template Twin release audit identity is immutable",
    );
    expect(migration).toContain(
      "Template Twin release audit receipt is immutable",
    );
    expect(migration).toContain(
      "Template Twin release evidence cannot be truncated",
    );
    expect(migration).toContain("template_twin_release_approvals_are_current");
    expect(migration).toContain(
      "Revoke the active Template Twin release before revoking its human authority",
    );
  });

  it("enforces a complete ordered rail and current human authority at commit", () => {
    for (const stage of [
      "CANARY",
      "PERCENT_10",
      "PERCENT_25",
      "PERCENT_50",
      "PERCENT_100",
    ]) {
      expect(migration).toContain(`'${stage}'`);
    }
    expect(migration).toContain("creator/finalizer cannot approve");
    expect(migration).toContain("current human approvals are incomplete");
    expect(migration).toContain(
      "checkpoint rail is incomplete or out of order",
    );
    expect(migration).toContain(
      "persisted exposure is outside the release checkpoint",
    );
  });
});

describe("Template Twin release admin route boundary", () => {
  it("uses the dedicated admin gate, strict same-origin JSON, a byte ceiling, and no authority mutation", () => {
    expect(route).toContain("adminApi(");
    expect(route).toContain('request.headers.get("host")');
    expect(route).toContain('request.headers.get("origin")');
    expect(route).toContain("MAX_BODY_BYTES");
    expect(route).toContain('action: z.literal("record_approval")');
    expect(route).not.toMatch(
      /grant_authority|create_authority|assign_authority/iu,
    );
  });
});
