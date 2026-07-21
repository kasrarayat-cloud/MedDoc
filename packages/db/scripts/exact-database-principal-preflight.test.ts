import { describe, expect, it } from "vitest";

import {
  buildExactDatabasePrincipalPreflightConnectionString,
  EXACT_DATABASE_PRINCIPAL_PROFILES,
  exactDatabasePrincipalProfile,
} from "./exact-database-principal-preflight";
import {
  buildDatabaseConnectionString,
  buildRuntimeDatabaseConnectionString,
} from "../src/database-connection-string";

describe("exact database-principal preflight profiles", () => {
  const base =
    "postgresql://meddoc_runtime:synthetic@postgres:5432/meddoc?schema=public";

  it("uses exactly the production runtime connection-string contract", () => {
    expect(buildExactDatabasePrincipalPreflightConnectionString(base)).toBe(
      buildDatabaseConnectionString(base),
    );
    expect(
      new URL(
        buildExactDatabasePrincipalPreflightConnectionString(base),
      ).searchParams.getAll("options"),
    ).toEqual(["-c search_path=pg_catalog,public -c statement_timeout=30000"]);
  });

  it.each([undefined, "250", "900000"])(
    "uses the runtime-selected statement timeout (%s)",
    (timeout) => {
      const environment = { PRISMA_STATEMENT_TIMEOUT_MS: timeout };
      expect(
        buildExactDatabasePrincipalPreflightConnectionString(base, environment),
      ).toBe(buildRuntimeDatabaseConnectionString(base, environment));
    },
  );

  it.each(["", " ", "0", "1.5", "2147483648"])(
    "rejects the same unsafe runtime timeout (%s)",
    (timeout) => {
      const environment = { PRISMA_STATEMENT_TIMEOUT_MS: timeout };
      expect(() =>
        buildExactDatabasePrincipalPreflightConnectionString(base, environment),
      ).toThrow("DATABASE_CONNECTION_OPTIONS_INVALID:STATEMENT_TIMEOUT");
      expect(() =>
        buildRuntimeDatabaseConnectionString(base, environment),
      ).toThrow("DATABASE_CONNECTION_OPTIONS_INVALID:STATEMENT_TIMEOUT");
    },
  );

  it.each([
    ["surrounding whitespace", `${base} `],
    ["duplicate options", `${base}&options=x&options=y`],
    ["unreviewed role option", `${base}&options=-c%20role%3Downer`],
    ["direct search path", `${base}&search_path=public`],
    ["query login override", `${base}&user=alternate`],
    ["duplicate ordinary key", `${base}&schema=public`],
  ])("rejects %s exactly as runtime does", (_label, databaseUrl) => {
    expect(() =>
      buildExactDatabasePrincipalPreflightConnectionString(databaseUrl),
    ).toThrow("DATABASE_CONNECTION_OPTIONS_INVALID");
    expect(() => buildDatabaseConnectionString(databaseUrl)).toThrow(
      "DATABASE_CONNECTION_OPTIONS_INVALID",
    );
  });

  it.each(Object.entries(EXACT_DATABASE_PRINCIPAL_PROFILES))(
    "resolves the finite %s profile",
    (name, expected) => {
      expect(exactDatabasePrincipalProfile(name)).toEqual(expected);
    },
  );

  it.each([undefined, "", "runtime ", "meddoc_runtime", "arbitrary"])(
    "rejects a non-exact profile (%s)",
    (profile) => {
      expect(() => exactDatabasePrincipalProfile(profile)).toThrow(
        "EXACT_DATABASE_PRINCIPAL_PROFILE_INVALID",
      );
    },
  );
});
