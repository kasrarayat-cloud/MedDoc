import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), "utf8");
}

function transcribeVisitReadWhereClauses(code: string): string[] {
  const marker = "prisma.transcribeVisit.findUnique";
  const clauses: string[] = [];
  let cursor = 0;
  while (cursor < code.length) {
    const call = code.indexOf(marker, cursor);
    if (call < 0) break;
    const where = code.indexOf("where:", call);
    const select = code.indexOf("select:", where);
    if (where < 0 || select < 0) {
      throw new Error("Could not isolate worker visit query");
    }
    clauses.push(code.slice(where, select));
    cursor = select + "select:".length;
  }
  return clauses;
}

describe("worker clinical-read current authority", () => {
  it("binds the queued actor lifecycle and patient tenant in every worker PHI read", () => {
    const clauses = transcribeVisitReadWhereClauses(source("src/worker.ts"));
    expect(clauses).toHaveLength(7);
    for (const clause of clauses) {
      expect(clause).toContain("currentClinicalVisitActorWhere");
    }
  });

  it("binds the same authority in the retry checkpoint projection", () => {
    const resume = source("src/worker/resume-state.ts");
    const clauses = transcribeVisitReadWhereClauses(resume);
    expect(clauses).toHaveLength(1);
    expect(clauses[0]).toContain(
      "currentClinicalVisitActorWhere(actorUserId)",
    );
  });
});
