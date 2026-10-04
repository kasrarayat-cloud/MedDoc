# D30 A20 original-source diagnosis — 2026-10-04

The unchanged D30 still misses A20 under the fixed 62-area protocol. Exact `9412736a107c481707a146c9ed122c6394f36e36` detection yields 61 fields and maps the complete accommodation question and all eight descriptors to the sole blank answer box. It does not create an automatic selection field in the eight bullet paragraphs. The reader's three direct module bytes equal the frozen Word `e76de10ed4d8e0ec2157c88221c4e279cf967267` bytes. Later integration changes were not silently substituted into this probe.

The original is SHA256 `fdeafbee872f987325e544953ad930e8e8db8ed6bd30ccab0375f2b50ecbff2f`; the unchanged fixed ground truth is `9328d7dbbe820f11f00e6c76f99f2f38e7c01fc971b3bc2789ef71ab3cb14b53`. The actual archived automatic score remains 61/62, A20 missed, no wrong/extra/duplicate destinations. Its 62/62 explicit manual recovery remains separate. The preexisting append-only source adjudication and both annotator/reviewer maps are preserved.

## Concrete source and cause

The source question is `word/document.xml#b/p[72]`. Its eight options/descriptors are p73–80: first four use numId23/abstractNum13; final four use numId24/abstractNum23. Both are plain bullet levels whose printed marker is `o` in Courier New. They contain no checkbox controls/glyph runs and print no choose-one/all-that-apply/marking operation. The blank box after the list is `b/tbl[4]/tr[0]/tc[0]`. The fixed reviewer map assigns A20 multi_choice to the paragraphs and explicitly explains an inferred bold/highlight/delete convention. That convention is absent from the original. The separate original annotator assigns choice while acknowledging non-exclusivity. Neither map establishes a printed cardinality.

At exact `rebuild/documents/word_v3.py:2386`, question/list/box ownership runs before paragraph option detection. `paragraph_list_box_source` at line6753 reads the complete question, list and blank-box relation; line6847 records cardinality unspecified. `rule_question_boxes` at line7107 adds the full-question long_text cell and line7110 claims the eight descriptor paragraphs. The later option rule also requires a lettered list or deeper numbered list at line5849; plain body bullets are outside that automatic contract. Thus `v3_20` preserves the complete prompt and source descriptors but provides no selection destination matching fixed A20.

This is a deliberate source-authority boundary rather than an omitted first-item/suffix parser accident. No automatic multi_choice inference is justified solely by this original's bullet formatting. It would invent both cardinality and a marking convention. Removing other options or rewriting the original question is not an acceptable repair.

The source-bound explicit recovery at `word_v3.py:6909` accepts a clinician-appointed complete list. It binds all eight physical paragraphs and records the requested one/many cardinality at line6969. The pure original probe verifies this recovery metadata only; it does not perform or count another export. The archived actual recovery inserted only the two intended selection markers and preserved the other original content. That archived preservation evidence remains separate.

## Finite controls

Six synthetic source controls completed with actual exit0 in2.957011 seconds under a60-second bound: plain Courier bullets and plain Calibri bullets remain complete-question long_text; explicit choose-one lettered options become choice; explicit select-all lettered options become multi_choice; numbering-level checkbox markers and an existing selection do not become pristine descriptors. These are direct reader controls, not replacements for D30 or an added corpus denominator.

The exact original inspector still exposes the three signature fields `v3_36`, `v3_40` and `v3_55`, the manager-reserved `v3_39`, and protected document-review attestation `v3_61`. No answer or finalizer identity was supplied. This establishes their observed roles only, not a new signing safety qualification.

The source reader emits no A20-specific coverage issue after claiming the complete descriptor/box relation. The archived route manifest has automatic_complete=false, review_required=true and block_generation=true due the distinct human attestation. Therefore this packet does not demonstrate a falsely advertised complete-success result. A separate understandable list-review warning/action could expose the possible selection intent, using the existing explicit list mapping and one/many decision; that would be assisted recovery, not automatic correctness. The fixed automatic A20 failure must remain until automatic selection support has genuine source/contract authority and its own verification.

## Evidence and limits

Protected scratch: `B/clinical/d30-a20-9412736a`, where B is `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z`. The second result includes exact physical XML, numbering definitions, complete inspected fields, roles, control sources and mapping. Result SHA256 `6df304fcd643ddff6a7426cd52754773a4773cbef1b69afedd3e7b94a5aa48f4`.

The first instrument run ended1 because it assumed the GT key was `areas`; its actual key is `answer_areas`. Its original script/log and first generated inputs remain retained. Only the instrumentation key and distinct output directory changed for the second run. No source, original, ground truth, score threshold or expectation changed.

This work performed no database, provider, credential, renderer, shared-runtime, source-pin, installation or service action. It cannot close the whole-document automatic gate, useful generation, or native Word acceptance. C08 and all campaign histories remain unchanged.

## Existing mapping-review action verified — docs only

At exact UI `04fb7603282dc47eda98058c6d790f407951acba`, `rebuild/templates/template_detail_v3.html:43` already directs the clinician to choose a plain list's question or first item and one or several printed options, explains the added `☒` mark, and promises that original wording/list bullets remain. `core/v3_mapping.py:27` provides the distinct labels One printed option and Printed options (several). `core/views.py:751` gives an actionable rejection when the place cannot provide printed options; line765 records a new immutable manual mapping version that needs confirmation. No copy change is needed.

The actual unchanged D30 outline and `v3_mapping.open_places` put p72 at zero-based open-place index136 and p73 at137, within the existing300-place first page. Search for accommodation finds the question. A pure rendering of the existing actual v3 template using these source-bound field/outline data retains both places, exact one/many kind controls, marker/preservation explanation, and new-version/confirmation actions. Eight checks pass with actual exit0 in0.524721 seconds; no HTTP or persistence claim follows. Display-only test context is synthetic and is not an installed configuration attestation.

This resolves the requested mapping-copy inspection without a source change. The original fixed A20 automatic miss and separate manual62/62 evidence remain unchanged. Source-derived automatic multi_choice authority remains unestablished; no GT/scorer/cardinality rewrite or additional paid qualification occurred.
