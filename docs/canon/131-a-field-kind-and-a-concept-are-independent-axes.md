# A FIELD **KIND** AND A **CONCEPT** ARE INDEPENDENT AXES

**Ratified 2026-09-07.** A near-miss worth writing down, because the two words
that describe them sound like the same word.

Ruling #233 specifies `total_time_minutes` as **"an L3 field, number"**. The
controls it must fill — *"Total minutes spent with patient"* and *"Total time
minutes"* — compile to **`narrative_text`**, `expectedDataType: 'text'`. That
looks like a contradiction and is not.

| axis | decided by | what it says |
|---|---|---|
| **concept** | the registry + the doctor's confirmation | **what this field MEANS** |
| **`expectedDataType`** | `expectedDataTypeForFieldKind`, reading the COMPILER's field `kind` | **what SHAPE the control is** |

`expectedDataTypeForFieldKind` is a pure switch over the compiler's `kind` and
**never looks at the concept.** So a number-valued L3 fact projected as a string
fills a narrative control perfectly well, and the concept is free to be about
time while the control is free to be prose.

⚠️ **THE TRAP IS THE OTHER DIRECTION, AND IT IS REAL.** On the same form, the
`Age` control compiles `kind: number` → `expectedDataType: 'number'`,
`unitPolicy: 'optional'` — and the resolver's number arm **refuses a value
carrying a unit**. So `"61-year-old"` fails `number_contains_unapproved_unit`
and only a bare `61` resolves. **The kind constrains the VALUE, not the meaning.**

> **When a ruling says a concept is "a number", ask which axis it is talking
> about.** Almost always it means the extraction type — and reading it as the
> control's `expectedDataType` sends you looking for a conflict that is not
> there, or worse, changing a compiled kind to remove one.
