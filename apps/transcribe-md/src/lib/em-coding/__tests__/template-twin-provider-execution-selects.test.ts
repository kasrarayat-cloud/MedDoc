import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const PROVIDER_EXECUTION_SELECT =
  /templateTwinProviderExecutions:\s*\{\s*select:\s*\{\s*id:\s*true\s*\},\s*take:\s*1,?\s*\}/u;
const RESERVED_PATIENT_SELECT =
  /patient:\s*\{\s*select:\s*\{[\s\S]*?externalId:\s*true/u;

function source(path: string): string {
  return readFileSync(
    resolve(process.cwd(), "src/lib/em-coding/__tests__", path),
    "utf8",
  );
}

describe("Template Twin E/M durable provider-execution census", () => {
  it.each([
    ["base score route", "../../../app/api/visits/[id]/em-score/route.ts"],
    [
      "apply-additions route",
      "../../../app/api/visits/[id]/em-score/apply-additions/route.ts",
    ],
    ["suggestion actions", "../../../actions/suggestion-actions.ts"],
    ["visit server render", "../../../app/visits/[id]/page.tsx"],
    ["signing selection", "../../template-twin/signing-gate.ts"],
  ])("loads provider executions at the %s boundary", (_label, path) => {
    const boundary = source(path);
    expect(boundary).toMatch(PROVIDER_EXECUTION_SELECT);
    expect(boundary).toMatch(RESERVED_PATIENT_SELECT);
  });
});
