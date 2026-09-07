# A LABEL RULE IS MEASURED AGAINST THE CUSTOMER'S OWN LABELS, NOT AGAINST THE PHRASE IT IS NAMED FOR

**Ratified 2026-09-07, from ruling #247 Stage B.**

`classifyFieldSource` carried a five-entry `MANUAL_LABEL_PATTERNS` list, and one
of its entries was `/referring\s+physician/i`, annotated *"context_default in
waiting"*. Beside it sat a long paragraph explaining the class, the trade, and
the flagged-review lane that would one day let these fill.

**The owner's form does not contain the string "referring physician".** His
control is labelled `Referring MD`, and it has been for as long as the form has
existed — recorded in three independent places in this repository before the
pattern was ever written:

| where | what it says |
|---|---|
| `gate-r2-r3-template-fidelity.test.ts:70` | *"measured from his uploaded .docx: `Referring MD`, `Patient`, `Age`"* |
| `confirm-live-template-mappings.ts:99` | the live-template rule matches `/^referring md/i` |
| `docs/canon/71-…` | the transcript of the form's own 35 labels |

So the rule that was supposedly governing that field **never reached it**. It
fell through to the default arm, got a concept the registry refused, and landed
`clinicalConcept: null` — the same outcome the rule intended, arrived at by
accident, for a different reason, with a paragraph of prose explaining a decision
that was never actually taken.

> **A rule that misses the one label it was written for is worse than no rule:
> it reads as coverage.** The next reader finds a considered paragraph, a
> matching pattern, and a field in exactly the state the paragraph predicts, and
> has no reason to check whether the three are connected.

⚠️ **AND THE SAME MEASUREMENT DECIDED THE PATTERNS THAT REPLACED IT.** The two
record-derived controls are labelled `Patient` and `Age` — **one word each, no
colon, no "name"**. A pattern written from the natural phrasing (`Patient Name`,
`Patient Age`) matches NEITHER. And because those are single common words, the
patterns must be anchored at BOTH ends: a prefix match on `Patient` claims
*"Patient reports intermittent heartburn"*, which is an ordinary scaffolded
narrative control, and a prefix match on `Age` claims *"Age of onset"*. **The
loosening that makes the rule fire on the real label is the same loosening that
makes it fire on prose**, so it has to be exact plus an enumerated set of
spellings that cannot mean anything else.

**THE HABIT, and it is one grep:** before writing or changing a pattern that
selects fields by label, find the labels. They are in the compiled IR, in the
fixtures, in the correction scripts, and in this repository's own recorded
measurements. Then write the arm against those strings and a NON-VACUITY arm
against the nearby prose the pattern must not claim.

**THE GENERAL SHAPE:** any rule keyed on data somebody else authored — a label, a
heading, a filename, a header key, an option string — is a **claim about that
data**, not a statement about the code. It is verified the way every other claim
here is verified: by looking at the data. A pattern's own comment naming the
field it cannot match is the tell, and it is a tell you can only see by reading
the population rather than the rule.

---

## APPENDED 2026-09-07 — AND THE LABEL YOU MEASURED IS NOT THE LABEL THE COMPILER STORES

The rule above sent me to read the population, and I read it — `Patient`, `Age`,
`Referring MD` — and then anchored the patterns at both ends, correctly, against
those strings.

**The compiled `originalLabel` is `REFERRING PHYSICIAN: Choose an item.`** Word's
placeholder is part of the label, not only of the option list, so an
end-anchored pattern matches *nothing* on the very form it was written for. It
cost one control in the F24 census the moment the anchor landed, and the census
is the only reason it was visible at all.

> **A measurement taken from a `.docx`, a spec, or a person is a measurement of
> the SOURCE. The rule runs against the COMPILED artifact, and the compiler is
> entitled to add to it.** Take the measurement from the thing the code will
> actually see.

The fix is not a looser anchor — that reopens `Referring Physician Fax`. It is to
normalise the label through the module that OWNS the placeholder string
(`withoutTrailingPlaceholder`, beside `isWordPlaceholderOption`) before matching,
so there is still exactly one place that knows what the placeholder is.
