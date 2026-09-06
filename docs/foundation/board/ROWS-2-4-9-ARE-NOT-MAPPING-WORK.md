# ⚠️ ROWS 4, 2 AND 9 REACH THE L3 PROMPT — MEASURED BEFORE STARTING THE TRANSFER

**Filed 2026-09-06, from enumerating the emitted concept vocabulary against the
registry rather than reading either one.**

The sequence *"rows 2/1/8/9/7"* reads as mapping work. **Two of those five are
extraction-pipeline changes**, and a third row (4) is blocked by a **pre-existing
silent-drop defect** nobody had measured.

## THE EMITTED VOCABULARY, ENUMERATED AGAINST THE REGISTRY

`encounter-facts/index.ts` emits **seven** concept families. **Six are
registered. One is not.**

| emitted | registered by | row |
|---|---|---|
| `exam.<system>` | `/^exam\.[a-z0-9_.]+$/` | 5 ✓ |
| `hpi.<field>` | `/^hpi\.[a-z0-9_]+$/` | 3 ✓ |
| `test.<t>.result`, `test.name` | pattern + concept | ✓ |
| `measurement.<metric>` | enumerated | ✓ |
| `medication.*`, `allergy.*`, `family_history.*`, `social_history.*` | sub-concepts | ✓ |
| `chief_complaint`, `past_medical_history`, `assessment`, `plan` | concepts | ✓ |
| **`ros.<system>`** | **NOTHING** | **4 ✗** |

## ⚠️ ROW 4 — A SILENT DROP, AND THE ASYMMETRY IS THE TELL

The proposer's allowed-concept list offers the model **`'ros.<system>'`**
(`semantic-mapping/index.ts:98`) — one line above **`'exam.<system>'`**. Both are
offered identically. `exam.*` has a registry pattern; **`ros.*` has none**, so
every `ros.*` proposal is nulled at line 518:

    const proposedConcept = candidate && isRegisteredConcept(candidate) ? candidate : null;

**The model is instructed to propose a concept the code then silently discards.**
Measured: `isRegisteredConcept` is `false` for `ros.gi`, `ros.gastrointestinal`,
`ros.constitutional`, `ros.cardiovascular`; `true` for all five exam systems
probed.

> **The facts themselves EXIST.** `entities.ros[]` is populated and
> `encounter-facts:698` projects it. Row 4 is blocked by the **validator alone**,
> which is why it is a one-line fix and not a feature.

⚠️ **`factSatisfiesMapping` never consults the registry**, so a hand-written
`ros.gi` mapping WOULD fill — and then be nulled at the next compile. That is
the trap: it would work until it silently stopped.

## ⚠️ ROWS 2 AND 9 — THE FACTS DO NOT EXIST AT ALL

Neither is a registry gap. **`EncounterEntitySnapshot` cannot carry them:**

| row | wanted | what the schema has |
|---|---|---|
| **2** | `past_surgical_history` as its own concept, surgeries and conditions separated **both ways** | `past_medical_history?: Array<{condition}>` — **one bucket, no surgical field** |
| **9** | marital status as a `social_history` sub-concept | `social_history?: {smoking, alcohol, drugs, occupation}` — **no marital** |

Each needs **four layers**: L3 schema → **the L3 prompt** → the emitter →
the registry → the mapping. *A capability is unreachable until the actor that
invokes it is told, and a model is wired by its prompt.*

⚠️ **`past_surgical_history` appears NOWHERE in the codebase** — zero files.

## WHAT THIS CHANGES

- **Row 4** is a one-line registry fix + arms, and it repairs a defect that has
  been silently discarding ROS proposals for every doctor, not just this form.
- **Rows 2 and 9** are pipeline work reaching the clinical extraction prompt —
  therefore **the mandatory adversarial pass applies to them**.
- **Rows 1, 7, 8** remain mapping/resolver work as expected.

**Nothing here is a decision to be made — the rows are ruled.** It is filed
because the sequence's shape was different from how it reads, and that is worth
knowing before the transfer rather than after.
