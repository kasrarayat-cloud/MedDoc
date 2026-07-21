import { describe, expect, it } from "vitest";

import { exactDatabasePrincipalCatalogQuery } from "./exact-database-principal-query";

const querySource = exactDatabasePrincipalCatalogQuery({
  loginRole: "meddoc_runtime",
  boundaryRole: "quillmd_runtime",
}).strings.join("?");

describe("exact database-principal relation manifest", () => {
  it("freezes user triggers but excludes nondeterministic internal RI trigger names", () => {
    expect(querySource).toContain("trigger.tgisinternal = FALSE");
    expect(querySource).toContain("pg_catalog.pg_get_triggerdef(");
    expect(querySource).toContain("pg_catalog.pg_get_functiondef(");
  });

  it("freezes normalized internal RI enforcement state with each constraint", () => {
    expect(querySource).toContain("constraint_object.convalidated");
    expect(querySource).toContain("constraint_object.connoinherit");
    expect(querySource).toContain("pg_catalog.pg_get_constraintdef(");
    expect(querySource).toContain("enforcement_trigger.tgenabled");
    expect(querySource).toMatch(
      /enforcement_trigger\.tgconstraint\s*=\s*constraint_object\.oid/u,
    );
    expect(querySource).toContain("enforcement_trigger.tgisinternal = TRUE");
    expect(querySource).not.toContain("enforcement_trigger.tgname");
  });
});
