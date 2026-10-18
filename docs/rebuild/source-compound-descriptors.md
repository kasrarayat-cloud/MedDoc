# Source compound descriptions

The source inventory has a second pass for complete current patient reports,
including single descriptors and reports its nominal-list grammar cannot parse.
A report is resolved only when every
atom, connector and adjunct is consumed and each atom has exactly one independently
evaluated source finding. Failure preserves the original unresolved source
obligations, whether an opaque gap or unevaluated nominal items; no partial match
adds evidence. This pass uses neither provider results nor saved code selections.

For a successful typed description, incidental unevaluated nominal items lose
only the evidence contributed by that report. Independent evidence and assessed
items remain. Already-resolved ordinary nominal reports receive no new metadata,
preserving their historical inventory and approval digests.

Three bounded relations are available:

- Exact nominal identity, retaining ordinary frequency/severity modifiers and
  explicitly parsed current/daily timing or bowel-movement relief predicates.
  Recognized ordinary modifier words anywhere in the complete literal assessed
  target and extra report prefixes share one conflict check: repeated severity
  or frequency kinds remain unresolved, including duplicates within the target
  itself. Whole-word matching includes hyphen boundaries and does not match
  substrings, erase punctuation or change literal spans. This finite lexical
  guard does not infer synonyms or assert universal clinical consistency.
- Loose/watery stool descriptions with an explicit daily count whose entire
  integer range is at least three, linked only to independently evaluated
  diarrhea. [NIDDK's definition](https://www.niddk.nih.gov/health-information/digestive-diseases/diarrhea/definition-facts)
  supports this quantitative branch. Its alternative relative-to-normal branch
  is deliberately not implemented. Digits and bounded English integers/ranges
  are parsed without discarding punctuation; decimals, alternatives, reversed
  ranges, approximations and quantities crossing below three remain unresolved.
- Cramping in the exact same literal abdominal region as independently
  evaluated abdominal pain. [MedlinePlus describes cramp-like abdominal pain](https://medlineplus.gov/ency/article/003120.htm).
  Only explicit anatomical region grammar is admitted; spelling/order aliases,
  different sites and diagnostic modifiers are not inferred.

The full report, exact object/atom/attribute/connector spans, independently
evaluated targets and typed relation authorities are retained in the inventory
and candidate proof. Relief after a bowel movement remains a symptom modifier;
it establishes no cause or syndrome. Unknown clauses, additional unmatched
findings, conflicting recognized modifiers and ambiguous ownership/timing do not become
descriptive links. Existing historical/foreign-source exclusions remain intact.

The pass creates no diagnosis, code or clinical decision. All existing engine
source checks, authoritative Index routes, Tabular instructions and code
eligibility checks still run. Coverage can therefore remain unresolved after a
descriptor is parsed. Inventory/proof digests include the added source evidence;
this is not permission to rewrite previously saved approvals.

Focused synthetic controls: `core.tests.test_source_compound_descriptors`.
No filled clinical document or retained account note is a repository fixture.
