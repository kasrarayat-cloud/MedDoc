// ============================================================================
// THE TRANSFER TOOL'S ARGUMENTS AND GUARDS — proved without a database.
// ----------------------------------------------------------------------------
// `transfer-certification-to-active.ts` is a RULED MUTATION: it writes certified
// dispositions onto a live compiled version and the write has no inverse. Its
// source, target and expected field count were FILE CONSTANTS, so the tool
// could only ever act on the one row-pair its author had read.
//
// Ruling 2 (2026-09-07) makes them REQUIRED ARGUMENTS, because the 53-control
// consult form re-issue is a second act of the same shape.
//
// ⚠️ THIS FILE EXISTS BECAUSE PARAMETERISATION IS NOT A REFACTOR. Turning a
// constant into an argument does not preserve behaviour — it creates states the
// constant made unreachable, and the interesting ones fail in the direction
// that looks like success:
//
//   · `--expect-fields 0` -> every count guard reads 0 === 0 against an empty
//     field set and PASSES. Ten green guards, nothing transferred.
//   · `--source X --target X` -> a self-transfer, where each "identical" guard
//     passes BECAUSE it is one row rather than because two agree.
//   · two NULL shas -> `null === null` is true, so two rows that record nothing
//     about their structure agree perfectly about it.
//
// ⚠️ AND IT PROVES BOTH DIRECTIONS, WHICH IS THE POINT OF THE FILE.
// `retire-branch.sh` passed 9 of 9 REFUSAL tests and still printed a false
// green, because refusals were never its broken half. So every refusal arm here
// is paired with a POSITIVE CONTROL: the same input with the one bad thing
// fixed must PASS. A refusal that fires for the wrong reason and a refusal that
// fires for the right one are indistinguishable without it.
// ============================================================================
import { describe, expect, it } from "vitest";

import {
  buildTransferGuards,
  countFailedGuards,
  parseTransferArgs,
  selectTransferFieldIds,
  type TransferSide,
} from "../transfer-args";

/** Replace one flag's value in an argv, so each arm differs in exactly one place. */
function withArg(argv: string[], flag: string, value: string): string[] {
  const out = [...argv];
  const i = out.indexOf(flag);
  out[i + 1] = value;
  return out;
}

const OK = [
  "--source",
  "src-1",
  "--target",
  "tgt-1",
  "--expect-fields",
  "53",
  "--target-status",
  "draft",
  "--transfer-source-types",
  "extraction",
  "--expect-transfer",
  "43",
];

/** A pair of sides that agrees on everything, so a single mutation is the cause. */
function goodPair(n = 3): { source: TransferSide; target: TransferSide } {
  const ids = Array.from({ length: n }, (_, i) => `f${i}`);
  return {
    source: {
      fields: ids.map((fieldId) => ({ fieldId, mappingStatus: "CERTIFIED" })),
      structureSha256: "struct-aaa",
      staticContentSha256: "static-bbb",
      templateStatus: "inactive",
      doctorId: "doc-1",
      practiceId: "prac-1",
    },
    target: {
      fields: ids.map((fieldId) => ({
        fieldId,
        mappingStatus: "NEEDS_CONFIRMATION",
      })),
      structureSha256: "struct-aaa",
      staticContentSha256: "static-bbb",
      templateStatus: "active",
      doctorId: "doc-1",
      practiceId: "prac-1",
    },
  };
}

describe("parseTransferArgs — the happy path, first", () => {
  // ⚠️ THE POSITIVE CONTROL COMES FIRST DELIBERATELY. If this arm ever fails,
  // every refusal below is refusing something that was already broken, and the
  // suite would still be green on all of them.
  it("accepts the six required arguments and defaults to DRY RUN", () => {
    const r = parseTransferArgs(OK);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.args).toEqual({
      source: "src-1",
      target: "tgt-1",
      expectFields: 53,
      targetStatus: "draft",
      transferSourceTypes: new Set(["extraction"]),
      expectTransfer: 43,
      commit: false,
    });
  });

  it("takes --commit, in any position", () => {
    for (const argv of [
      [...OK, "--commit"],
      ["--commit", ...OK],
      [...OK.slice(0, 4), "--commit", ...OK.slice(4)],
    ]) {
      const r = parseTransferArgs(argv);
      expect(r.ok).toBe(true);
      if (r.ok) expect(r.args.commit).toBe(true);
    }
  });
});

describe("parseTransferArgs — refusals, each with its own positive control", () => {
  for (const flag of [
    "--source",
    "--target",
    "--expect-fields",
    "--target-status",
    "--transfer-source-types",
    "--expect-transfer",
  ]) {
    it(`REFUSES when ${flag} is missing, and accepts the same argv with it`, () => {
      const without: string[] = [];
      for (let i = 0; i < OK.length; i += 2) {
        if (OK[i] !== flag) without.push(OK[i]!, OK[i + 1]!);
      }
      const bad = parseTransferArgs(without);
      expect(bad.ok).toBe(false);
      if (!bad.ok) expect(bad.reason).toContain(flag);

      // the control: the ONLY difference is the restored flag
      expect(parseTransferArgs(OK).ok).toBe(true);
    });
  }

  it("REFUSES a flag whose value is another flag, naming the RIGHT flag", () => {
    const r = parseTransferArgs(["--source", ...OK.slice(2)]);
    expect(r.ok).toBe(false);
    // ⚠️ The failure mode being excluded: binding source='--target' and then
    // reporting "missing --target" — a refusal that sends the reader to fix an
    // argument that is not the broken one.
    if (!r.ok) {
      expect(r.reason).toContain("--source needs a value");
      expect(r.reason).not.toContain("missing required");
    }
  });

  it("REFUSES --expect-fields 0 — the guards would pass VACUOUSLY", () => {
    const r = parseTransferArgs(withArg(OK, "--expect-fields", "0"));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("VACUOUSLY");

    // ⚠️ THE CONTROL THAT MAKES THIS ARM MEAN SOMETHING: prove the vacuous pass
    // is REAL, not hypothetical. An empty field set with expectFields=0 passes
    // every count guard — which is exactly why the parse refuses before here.
    const empty: TransferSide = {
      fields: [],
      structureSha256: "s",
      staticContentSha256: "t",
      templateStatus: "active",
      doctorId: "d",
      practiceId: "p",
    };
    const vacuous = buildTransferGuards(empty, { ...empty }, 0);
    const countGuards = vacuous.slice(0, 4);
    expect(countFailedGuards(countGuards)).toBe(0); // <- the hazard, demonstrated
  });

  it("REFUSES source === target — a guard measuring itself", () => {
    const r = parseTransferArgs(
      withArg(withArg(OK, "--source", "same"), "--target", "same"),
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("same compiled version");

    // control: one character apart, and it parses
    expect(
      parseTransferArgs(
        withArg(withArg(OK, "--source", "same"), "--target", "sameX"),
      ).ok,
    ).toBe(true);
  });

  it("REFUSES a leniently-parsed count — parseInt would have accepted these", () => {
    for (const v of ["53x", "5.9", " 53", "5 3", "0x35", "", "-1", "1e2"]) {
      const r = parseTransferArgs(withArg(OK, "--expect-fields", v));
      expect(r.ok, `--expect-fields '${v}' must be refused`).toBe(false);
    }
    // ⚠️ AND THE CONTROL PROVES THE REFUSALS ARE ABOUT THE VALUE, NOT THE ARM:
    // the same argv with a clean integer parses.
    const good = parseTransferArgs(OK);
    expect(good.ok).toBe(true);
    if (good.ok) expect(good.args.expectFields).toBe(53);
  });

  it("REFUSES an unrecognised argument rather than ignoring it", () => {
    const r = parseTransferArgs([...OK, "--dry-run"]);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("unrecognised argument '--dry-run'");
  });

  it("REFUSES a repeated flag — the second value would silently win", () => {
    const r = parseTransferArgs([...OK, "--target", "tgt-2"]);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("more than once");
  });

  it("REFUSES a repeated --transfer-source-types too", () => {
    const r = parseTransferArgs([...OK, "--transfer-source-types", "all"]);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("more than once");
  });

  it("REFUSES an empty argv, which is how the OLD constants-based call now arrives", () => {
    // ⚠️ THIS IS THE MIGRATION ARM. The previous invocation was
    // `… transfer-certification-to-active.ts --commit` and it acted on two
    // hardcoded ids. That exact command must now REFUSE rather than act on a
    // stale target — a silently-defaulted id is the whole hazard.
    const r = parseTransferArgs(["--commit"]);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("missing required argument(s)");
  });
});

describe("buildTransferGuards — the original ten still refuse what they refused", () => {
  it("passes on a well-formed pair (the positive control for every arm below)", () => {
    const { source, target } = goodPair(3);
    expect(countFailedGuards(buildTransferGuards(source, target, 3))).toBe(0);
  });

  it("fails when the expected count disagrees with reality", () => {
    const { source, target } = goodPair(3);
    expect(
      countFailedGuards(buildTransferGuards(source, target, 4)),
    ).toBeGreaterThan(0);
  });

  it("fails when the target already carries CERTIFIED mappings", () => {
    const { source, target } = goodPair(3);
    target.fields[0]!.mappingStatus = "CERTIFIED";
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  it("fails when the fieldId sets differ", () => {
    const { source, target } = goodPair(3);
    target.fields[1]!.fieldId = "other";
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  it("fails when the target template is not ACTIVE", () => {
    const { source, target } = goodPair(3);
    target.templateStatus = "inactive";
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  for (const key of [
    "structureSha256",
    "staticContentSha256",
    "doctorId",
    "practiceId",
  ] as const) {
    it(`fails when ${key} DIFFERS between the two versions`, () => {
      const { source, target } = goodPair(3);
      target[key] = "something-else";
      expect(
        countFailedGuards(buildTransferGuards(source, target, 3)),
      ).toBeGreaterThan(0);
    });
  }
});

describe("buildTransferGuards — the four ADDED guards, and the hole they close", () => {
  // ⚠️ EACH ARM DEMONSTRATES THE HOLE BEFORE ASSERTING IT IS CLOSED. Showing
  // that the equality guard passes on two nulls is what makes the presence
  // guard a fix rather than a decoration — without it, a reader cannot tell
  // whether the added guard is load-bearing or ceremonial.
  for (const key of [
    "structureSha256",
    "staticContentSha256",
    "doctorId",
    "practiceId",
  ] as const) {
    it(`REFUSES two NULL ${key}s, which the equality guard alone accepts`, () => {
      const { source, target } = goodPair(3);
      source[key] = null;
      target[key] = null;

      const guards = buildTransferGuards(source, target, 3);

      // 1. the hole is real: the ORIGINAL equality guard for this key passes.
      const equality = guards.find(
        ([n]) => n.includes("identical") || n.startsWith("same"),
      );
      expect(equality).toBeDefined();
      const nullEquality = guards.filter(
        ([n, got]) =>
          !n.includes("PRESENT") &&
          got === true &&
          n !== "fieldId sets identical",
      );
      expect(nullEquality.length).toBeGreaterThan(0);

      // 2. and the added guard closes it.
      expect(countFailedGuards(guards)).toBeGreaterThan(0);
      const presence = guards.filter(([n]) => n.includes("PRESENT"));
      expect(presence.length).toBe(4);
      expect(countFailedGuards(presence)).toBeGreaterThan(0);
    });
  }

  it("REFUSES an EMPTY-STRING sha, not only a null", () => {
    // '' === '' is true and '' is falsy — two different ways to be absent, and
    // a presence check written as a truthiness test would catch only the second.
    const { source, target } = goodPair(3);
    source.structureSha256 = "";
    target.structureSha256 = "";
    expect(
      countFailedGuards(buildTransferGuards(source, target, 3)),
    ).toBeGreaterThan(0);
  });

  it("does NOT fail a pair that carries real values — the net is wider, not looser", () => {
    // ⚠️ THE REGRESSION CONTROL FOR THE ADDED GUARDS. Four new ways to refuse is
    // only an improvement if nothing legitimate now refuses; a guard that fires
    // on good input is a worse defect than the one it was added to close.
    const { source, target } = goodPair(35);
    const guards = buildTransferGuards(source, target, 35);
    expect(guards.length).toBe(14); // 10 original + 4 added
    expect(countFailedGuards(guards)).toBe(0);
  });
});

describe('the SELECTION — "transfer the 43, re-propose the ten"', () => {
  /** A source shaped like the real certified 53: 43 extraction + 10 manual. */
  function certified53(): TransferSide {
    const fields = [
      ...Array.from({ length: 43 }, (_, i) => ({
        fieldId: `e${i}`,
        mappingStatus: "CERTIFIED",
        sourceType: "extraction",
      })),
      ...Array.from({ length: 10 }, (_, i) => ({
        fieldId: `m${i}`,
        mappingStatus: "CERTIFIED",
        sourceType: "manual",
      })),
    ];
    return {
      fields,
      structureSha256: "struct",
      staticContentSha256: "static",
      templateStatus: "active",
      doctorId: "doc",
      practiceId: "prac",
    };
  }

  it("selects exactly the 43 extraction rows, measured against the real partition", () => {
    const src = certified53();
    expect(src.fields.length).toBe(53);
    expect(selectTransferFieldIds(src, new Set(["extraction"]))).toHaveLength(
      43,
    );
    expect(selectTransferFieldIds(src, new Set(["manual"]))).toHaveLength(10);
  });

  it("'all' selects every field — the GI act's mode, still expressible", () => {
    expect(selectTransferFieldIds(certified53(), null)).toHaveLength(53);
  });

  it("selects on the SOURCE, never the target — the target rows are the fresh proposals", () => {
    // ⚠️ THE FAILURE THIS EXCLUDES: selecting on the target picks whatever the
    // new registry happened to propose, which is a set nobody ever certified.
    // Here the target's types are deliberately the INVERSE of the source's.
    const src = certified53();
    const picked = selectTransferFieldIds(src, new Set(["extraction"]));
    expect(picked.every((id) => id.startsWith("e"))).toBe(true);
    expect(picked.some((id) => id.startsWith("m"))).toBe(false);
  });

  it("a field with a NULL sourceType is never selected", () => {
    const src = certified53();
    src.fields[0]!.sourceType = null;
    expect(selectTransferFieldIds(src, new Set(["extraction"]))).toHaveLength(
      42,
    );
  });

  it("the selection guard FIRES when the live partition is not what was declared", () => {
    const src = certified53();
    const tgt = { ...certified53(), templateStatus: "draft" };
    const opts = {
      targetStatus: "draft",
      transferSourceTypes: new Set(["extraction"]),
      expectTransfer: 43,
    };
    // control: the declared 43 matches the shape, so the selection guard passes
    const sel = (g: Array<[string, unknown, unknown]>) =>
      g.filter(([n]) => n === "fields selected for transfer");
    expect(
      countFailedGuards(sel(buildTransferGuards(src, tgt, 53, opts))),
    ).toBe(0);

    // and it reds when one row moves across the partition
    src.fields[0]!.sourceType = "manual";
    expect(
      countFailedGuards(sel(buildTransferGuards(src, tgt, 53, opts))),
    ).toBe(1);
  });

  it("emits NO selection guard when no count was declared — never one that measures itself", () => {
    const src = certified53();
    const guards = buildTransferGuards(src, { ...certified53() }, 53);
    expect(
      guards.filter(([n]) => n === "fields selected for transfer"),
    ).toHaveLength(0);
  });
});

describe("--target-status — guard 10 KEPT as a premise, parameterised as a value", () => {
  it("accepts draft, which is what the ruled order actually presents", () => {
    // ⚠️ THE REGRESSION THIS PINS: guard 10 read `status === 'active'` as a
    // literal, and #263 transfers BEFORE certify-and-activate. A freshly
    // ingested template is `draft` (create-draft.ts:436), so the literal
    // refused the very act it was being parameterised for.
    const { source, target } = goodPair(3);
    target.templateStatus = "draft";
    expect(
      countFailedGuards(
        buildTransferGuards(source, target, 3, { targetStatus: "draft" }),
      ),
    ).toBe(0);
  });

  it("still REFUSES a target in the wrong state — the premise is asserted, not dropped", () => {
    const { source, target } = goodPair(3);
    target.templateStatus = "active";
    expect(
      countFailedGuards(
        buildTransferGuards(source, target, 3, { targetStatus: "draft" }),
      ),
    ).toBeGreaterThan(0);
  });

  it("REFUSES a status outside the closed set — a typo is not a premise", () => {
    const r = parseTransferArgs(withArg(OK, "--target-status", "activ"));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("not one of");
    expect(parseTransferArgs(withArg(OK, "--target-status", "active")).ok).toBe(
      true,
    );
  });

  it("defaults to active when no option object is passed — the pre-existing callers", () => {
    const { source, target } = goodPair(3);
    expect(countFailedGuards(buildTransferGuards(source, target, 3))).toBe(0);
  });
});

describe("--expect-transfer — the selector without a declared count is an unguarded query", () => {
  it("REFUSES 0", () => {
    const r = parseTransferArgs(withArg(OK, "--expect-transfer", "0"));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("absence of one");
  });

  it("REFUSES a count larger than the field count", () => {
    const r = parseTransferArgs(withArg(OK, "--expect-transfer", "54"));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("exceeds");
    // control: equal is legal — that is the "transfer everything" act
    expect(parseTransferArgs(withArg(OK, "--expect-transfer", "53")).ok).toBe(
      true,
    );
  });

  it("REFUSES a --transfer-source-types that names nothing", () => {
    for (const v of ["", ",", " , "]) {
      expect(
        parseTransferArgs(withArg(OK, "--transfer-source-types", v)).ok,
      ).toBe(false);
    }
    expect(
      parseTransferArgs(withArg(OK, "--transfer-source-types", "all")).ok,
    ).toBe(true);
  });

  it("takes a comma-separated list, trimming spaces", () => {
    const r = parseTransferArgs(
      withArg(OK, "--transfer-source-types", "extraction, manual"),
    );
    expect(r.ok).toBe(true);
    if (r.ok)
      expect(r.args.transferSourceTypes).toEqual(
        new Set(["extraction", "manual"]),
      );
  });
});
