// ============================================================================
// THE TRANSFER TOOL'S ARGUMENTS AND GUARDS — pure, so an arm can drive them.
// ----------------------------------------------------------------------------
// `transfer-certification-to-active.ts` moved the certified dispositions from
// one compiled version onto another. It named both versions and the expected
// field count as FILE CONSTANTS, because it was written for one doctor's
// stranded Gastroenterology Consultation and nothing else.
//
// Ruling 2 (2026-09-07) makes the re-issue ONE declared, machine-driven act,
// and the transfer is its third step. A tool whose target is a constant cannot
// be a step in an act whose target is decided by the act — so source, target
// and expected count become REQUIRED arguments.
//
// ⚠️ PARAMETERISING A TOOL CREATES HAZARDS THE CONSTANTS MADE IMPOSSIBLE, AND
// THOSE ARE THE ONES NOBODY LOOKS FOR. Two hardcoded ids can never be equal and
// a hardcoded `35` can never be zero. Both become reachable the moment a caller
// types them, and both fail in the direction that looks like success:
//
//   · source === target — a self-transfer writes each field's mapping back onto
//     itself. Every "identical" guard passes BECAUSE it is the same row.
//   · expectFields = 0 — every count guard reads `0 === 0` against an empty
//     field set and passes VACUOUSLY, and the end-state assertion agrees. The
//     tool would print ten green guards having done nothing at all.
//
// Both are refused HERE, at parse time, with a named reason — before a database
// is opened, so a refusal cannot be mistaken for a failed lookup.
//
// ⚠️ AND `parseInt` IS NOT THE INSTRUMENT FOR THIS. `parseInt('53x')` is 53 and
// `parseInt('5.9')` is 5 — both silently accept a count the caller did not
// write, and the resulting guard compares a real field count against a number
// nobody chose. The whole string must be an integer or the parse refuses.
//
// ── WHY THIS IS A SEPARATE, PURE MODULE ─────────────────────────────────────
// The same split `declaration_strictness_for_migrations` already makes: the
// GATHERING is I/O (a Prisma read) and the DECISION is arithmetic. Kept
// together they are untestable without a database, and the decision is exactly
// the half that can be wrong in a way nobody notices. Split, an arm drives
// every guard with injected values.
//
//   PROOF: __tests__/gate-transfer-args.test.ts
// ============================================================================

/** A compiled-version row, reduced to what the guards actually read. */
export interface TransferSide {
  fields: Array<{
    fieldId: string;
    mappingStatus: string | null;
    sourceType?: string | null;
  }>;
  structureSha256: string | null;
  staticContentSha256: string | null;
  templateStatus: string | null;
  doctorId: string | null;
  practiceId: string | null;
}

export interface TransferArgs {
  source: string;
  target: string;
  expectFields: number;
  /** The premise guard 10 asserts. KEPT as a premise, parameterised as a value. */
  targetStatus: string;
  /** `null` = ALL source sourceTypes carry across. Otherwise the selected set. */
  transferSourceTypes: Set<string> | null;
  expectTransfer: number;
  commit: boolean;
}

export type ParseResult =
  | { ok: true; args: TransferArgs }
  | { ok: false; reason: string };

const USAGE =
  "usage: transfer-certification-to-active.ts --source <compiledVersionId> " +
  "--target <compiledVersionId> --expect-fields <n> --target-status <draft|active> " +
  "--transfer-source-types <all|type[,type...]> --expect-transfer <n> [--commit]";

const TARGET_STATUSES = ["draft", "active"];

/**
 * Parse the tool's argv (already sliced past node and the script path).
 *
 * ⚠️ FAIL-CLOSED ON CANNOT-TELL, in the house posture. An unrecognised flag, a
 * flag whose value is missing, a repeated flag, or a count that is not a plain
 * positive integer all REFUSE. None of those is a state a caller meant to be
 * in, and guessing at any of them puts a wrong id or a wrong count in front of
 * guards that will then compare it faithfully.
 */
export function parseTransferArgs(argv: string[]): ParseResult {
  let source: string | undefined;
  let target: string | undefined;
  let expectRaw: string | undefined;
  let targetStatus: string | undefined;
  let transferRaw: string | undefined;
  let expectTransferRaw: string | undefined;
  let commit = false;

  // ⚠️ A VALUE THAT LOOKS LIKE A FLAG IS A MISSING VALUE, NOT A VALUE.
  // `--source --target abc` would otherwise bind source='--target' and then
  // report "missing --target" — a refusal that names the wrong argument and
  // sends the reader to fix something that is not broken.
  const takeValue = (flag: string, next: string | undefined): string | null => {
    if (next === undefined || next.startsWith("--")) return null;
    return next;
  };

  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i]!;
    switch (a) {
      case "--commit":
        commit = true;
        break;
      case "--source": {
        if (source !== undefined)
          return { ok: false, reason: "--source given more than once." };
        const v = takeValue(a, argv[i + 1]);
        if (v === null)
          return { ok: false, reason: `--source needs a value.\n${USAGE}` };
        source = v;
        i += 1;
        break;
      }
      case "--target": {
        if (target !== undefined)
          return { ok: false, reason: "--target given more than once." };
        const v = takeValue(a, argv[i + 1]);
        if (v === null)
          return { ok: false, reason: `--target needs a value.\n${USAGE}` };
        target = v;
        i += 1;
        break;
      }
      case "--expect-fields": {
        if (expectRaw !== undefined)
          return { ok: false, reason: "--expect-fields given more than once." };
        const v = takeValue(a, argv[i + 1]);
        if (v === null)
          return {
            ok: false,
            reason: `--expect-fields needs a value.\n${USAGE}`,
          };
        expectRaw = v;
        i += 1;
        break;
      }
      case "--target-status": {
        if (targetStatus !== undefined)
          return { ok: false, reason: "--target-status given more than once." };
        const v = takeValue(a, argv[i + 1]);
        if (v === null)
          return {
            ok: false,
            reason: `--target-status needs a value.\n${USAGE}`,
          };
        targetStatus = v;
        i += 1;
        break;
      }
      case "--transfer-source-types": {
        if (transferRaw !== undefined)
          return {
            ok: false,
            reason: "--transfer-source-types given more than once.",
          };
        const v = takeValue(a, argv[i + 1]);
        if (v === null)
          return {
            ok: false,
            reason: `--transfer-source-types needs a value.\n${USAGE}`,
          };
        transferRaw = v;
        i += 1;
        break;
      }
      case "--expect-transfer": {
        if (expectTransferRaw !== undefined)
          return {
            ok: false,
            reason: "--expect-transfer given more than once.",
          };
        const v = takeValue(a, argv[i + 1]);
        if (v === null)
          return {
            ok: false,
            reason: `--expect-transfer needs a value.\n${USAGE}`,
          };
        expectTransferRaw = v;
        i += 1;
        break;
      }
      default:
        return {
          ok: false,
          reason:
            `unrecognised argument '${a}'.\n${USAGE}\n` +
            "   Refusing rather than ignoring it: an argument this tool does not " +
            "understand\n   is an instruction it was given and did not carry out.",
        };
    }
  }

  const missing = [
    source === undefined ? "--source" : null,
    target === undefined ? "--target" : null,
    expectRaw === undefined ? "--expect-fields" : null,
    targetStatus === undefined ? "--target-status" : null,
    transferRaw === undefined ? "--transfer-source-types" : null,
    expectTransferRaw === undefined ? "--expect-transfer" : null,
  ].filter(Boolean);
  if (missing.length > 0) {
    return {
      ok: false,
      reason:
        `missing required argument(s): ${missing.join(", ")}.\n${USAGE}\n` +
        "   These used to be file constants naming one doctor's stranded template.\n" +
        "   They are required so this tool can never act on a target nobody named.",
    };
  }

  // ⚠️ THE WHOLE STRING, OR NOTHING. See the header — `parseInt` accepts '53x'
  // and '5.9' and yields a number the caller never wrote.
  if (!/^[0-9]+$/.test(expectRaw!)) {
    return {
      ok: false,
      reason:
        `--expect-fields '${expectRaw}' is not a plain non-negative integer.\n` +
        "   Not parsed leniently on purpose: a partially-read count is compared\n" +
        "   faithfully by every guard below it, and the mismatch it causes points\n" +
        "   at the database rather than at the typo.",
    };
  }
  const expectFields = Number(expectRaw);

  if (expectFields === 0) {
    return {
      ok: false,
      reason:
        "--expect-fields 0 is REFUSED.\n" +
        "   Zero is not a smaller version of this act, it is the absence of it:\n" +
        "   every count guard would read 0 === 0 against an empty field set and\n" +
        "   PASS VACUOUSLY, and the end-state assertion would agree. The tool\n" +
        "   would print a full set of green guards having transferred nothing.",
    };
  }

  if (source === target) {
    return {
      ok: false,
      reason:
        `--source and --target are the same compiled version (${source}).\n` +
        "   A self-transfer writes every mapping back onto itself, and each\n" +
        '   "identical" guard passes BECAUSE it is the same row rather than\n' +
        "   because two versions agree. That is a guard measuring itself.",
    };
  }

  // ── --target-status: an ENUM, because a typo must not become a premise ──
  // ⚠️ Guard 10 asserted `status === 'active'` as a literal. The ruled order
  // (#263) transfers BEFORE certify-and-activate and a freshly ingested
  // template is `draft` (create-draft.ts:436), so the literal refuses the very
  // act it is being parameterised for. The GUARD IS KEPT — the premise is still
  // asserted and still declared on the command line — but its VALUE is now
  // named by the caller. A free-form string would let `--target-status activ`
  // through as a premise nothing can satisfy, so the set is closed.
  if (!TARGET_STATUSES.includes(targetStatus!)) {
    return {
      ok: false,
      reason:
        `--target-status '${targetStatus}' is not one of: ${TARGET_STATUSES.join(", ")}.\n` +
        "   Guard 10 asserts the target template is in this state. A value outside\n" +
        "   the set is a premise no row can satisfy, so it would refuse later and\n" +
        "   blame the database.",
    };
  }

  // ── --transfer-source-types: which of the SOURCE's dispositions carry across ──
  // ⚠️ `all` IS SPELLED OUT RATHER THAN DEFAULTED. The GI act transferred every
  // field and that is a legitimate mode; making it the DEFAULT would mean the
  // 53-control act copies its ten re-proposals over by omission. An explicit
  // word costs one argument and removes a silent wrong answer.
  let transferSourceTypes: Set<string> | null;
  if (transferRaw === "all") {
    transferSourceTypes = null;
  } else {
    const parts = transferRaw!
      .split(",")
      .map((x) => x.trim())
      .filter((x) => x.length > 0);
    if (parts.length === 0) {
      return {
        ok: false,
        reason:
          `--transfer-source-types '${transferRaw}' names no source type.\n` +
          "   Use 'all' to transfer every field, or a comma-separated list.",
      };
    }
    transferSourceTypes = new Set(parts);
  }

  if (!/^[0-9]+$/.test(expectTransferRaw!)) {
    return {
      ok: false,
      reason: `--expect-transfer '${expectTransferRaw}' is not a plain non-negative integer.`,
    };
  }
  const expectTransfer = Number(expectTransferRaw);

  // ⚠️ THE SELECTOR WITHOUT THIS COUNT IS AN UNGUARDED QUERY. `--transfer-source-types
  // extraction` selects however many rows happen to carry that type, and an
  // irreversible act must not discover its own size. The caller declares it and
  // the tool measures it — the §2.5 shape, one layer down.
  if (expectTransfer === 0) {
    return {
      ok: false,
      reason:
        "--expect-transfer 0 is REFUSED — a transfer that moves nothing is not a\n" +
        "   smaller transfer, it is the absence of one, and it would report success.",
    };
  }
  if (expectTransfer > expectFields) {
    return {
      ok: false,
      reason:
        `--expect-transfer ${expectTransfer} exceeds --expect-fields ${expectFields}.\n` +
        "   The transferred set is a subset of the field set; it cannot be larger.",
    };
  }

  return {
    ok: true,
    args: {
      source: source!,
      target: target!,
      expectFields,
      targetStatus: targetStatus!,
      transferSourceTypes,
      expectTransfer,
      commit,
    },
  };
}

/**
 * Every premise this act rests on, as [name, got, want] triples.
 *
 * ⚠️ THE ORIGINAL TEN ARE KEPT, IN CONTENT AND IN ORDER. The parameterisation
 * replaced three constants with three arguments; it did not get to decide which
 * premises still matter. `EXPECT_FIELDS` is now `expectFields`, and that is the
 * only change to any of them.
 *
 * ⚠️ FOUR MORE ARE ADDED, BECAUSE PARAMETERISATION MADE AN EXISTING WEAKNESS
 * REACHABLE. Four of the original ten are equality tests over NULLABLE columns:
 *
 *     structureSha256 identical      null === null  ->  true
 *     staticContentSha256 identical  null === null  ->  true
 *     same owning doctor             null === null  ->  true
 *     same practice                  null === null  ->  true
 *
 * Two rows that record NOTHING about their structure agree perfectly about it.
 * That is a guard passing because the evidence is ABSENT — the same shape as
 * `--expect-fields 0`, and the same direction: it looks exactly like a pass.
 *
 * With two hardcoded ids naming two rows the author had read, it could not
 * happen. With a caller supplying the ids it can, so the presence of each value
 * is now asserted BESIDE the equality rather than assumed by it. Four added
 * guards is a wider net, never a looser one: nothing that passed the original
 * ten and carries real values fails here.
 */
export function buildTransferGuards(
  source: TransferSide,
  target: TransferSide,
  expectFields: number,
  opts?: {
    targetStatus?: string;
    transferSourceTypes?: Set<string> | null;
    expectTransfer?: number;
  },
): Array<[string, unknown, unknown]> {
  const targetStatus = opts?.targetStatus ?? "active";
  const srcCertified = source.fields.filter(
    (f) => f.mappingStatus === "CERTIFIED",
  ).length;
  const tgtCertified = target.fields.filter(
    (f) => f.mappingStatus === "CERTIFIED",
  ).length;
  const srcIds = source.fields.map((f) => f.fieldId).sort();
  const tgtIds = target.fields.map((f) => f.fieldId).sort();

  const present = (v: unknown) => typeof v === "string" && v.length > 0;

  return [
    ["source field count", source.fields.length, expectFields],
    ["target field count", target.fields.length, expectFields],
    ["source CERTIFIED mappings", srcCertified, expectFields],
    ["target CERTIFIED mappings (must be none)", tgtCertified, 0],
    [
      "fieldId sets identical",
      JSON.stringify(srcIds) === JSON.stringify(tgtIds),
      true,
    ],
    [
      "structureSha256 identical",
      source.structureSha256 === target.structureSha256,
      true,
    ],
    [
      "staticContentSha256 identical",
      source.staticContentSha256 === target.staticContentSha256,
      true,
    ],
    ["same owning doctor", source.doctorId === target.doctorId, true],
    ["same practice", source.practiceId === target.practiceId, true],
    [
      `target template is ${targetStatus.toUpperCase()}`,
      target.templateStatus,
      targetStatus,
    ],

    // ── the four added presence guards; see the note above ──
    [
      "structureSha256 PRESENT on both (not two nulls agreeing)",
      present(source.structureSha256) && present(target.structureSha256),
      true,
    ],
    [
      "staticContentSha256 PRESENT on both (not two nulls agreeing)",
      present(source.staticContentSha256) &&
        present(target.staticContentSha256),
      true,
    ],
    [
      "owning doctor PRESENT on both (not two nulls agreeing)",
      present(source.doctorId) && present(target.doctorId),
      true,
    ],
    [
      "practice PRESENT on both (not two nulls agreeing)",
      present(source.practiceId) && present(target.practiceId),
      true,
    ],

    // ── the SELECTION guard, emitted ONLY when the caller declared a count ──
    // ⚠️ A guard appended unconditionally as `expectTransfer ?? <measured>`
    // would compare the measurement against itself and pass forever — the exact
    // vacuity this module refuses `--expect-fields 0` for. No declared count,
    // no guard.
    ...(opts?.expectTransfer === undefined
      ? []
      : ([
          [
            "fields selected for transfer",
            selectTransferFieldIds(source, opts.transferSourceTypes ?? null)
              .length,
            opts.expectTransfer,
          ],
        ] as Array<[string, unknown, unknown]>)),
  ];
}

/**
 * The fieldIds whose SOURCE disposition carries across.
 *
 * ⚠️ SELECTED ON THE **SOURCE**'s sourceType, NEVER THE TARGET'S. "The 43
 * certified dispositions" (#247) is a fact about the CERTIFIED version. The
 * target's rows are the fresh proposals this act deliberately does NOT
 * overwrite, and their sourceTypes are whatever the new registry proposed —
 * so selecting on the target would pick a set nobody ever certified.
 *
 * ⚠️ AND THIS IS **NOT** "WHICH FIELDS TO SEND". Measured, not assumed:
 * `updateTemplateTwinMappings` throws `FIELD_SET_MISMATCH` unless the payload
 * carries the EXACT compiler field set — `certification-lifecycle.ts:445-452`,
 * `byId.size !== fieldById.size || [...byId.keys()].some(...)`. **All 53 always
 * go.** This selects which of them carry the SOURCE's row; the rest carry the
 * TARGET's own, untouched. A "send only the 43" reading compiles, reads
 * correctly, and throws at the one moment it matters.
 */
export function selectTransferFieldIds(
  source: TransferSide,
  transferSourceTypes: Set<string> | null,
): string[] {
  if (transferSourceTypes === null) return source.fields.map((f) => f.fieldId);
  return source.fields
    .filter(
      (f) => f.sourceType != null && transferSourceTypes.has(f.sourceType),
    )
    .map((f) => f.fieldId);
}

/** How many of the guards fail. Shared so the script and the arm agree. */
export function countFailedGuards(
  guards: Array<[string, unknown, unknown]>,
): number {
  return guards.filter(
    ([, got, want]) => JSON.stringify(got) !== JSON.stringify(want),
  ).length;
}
