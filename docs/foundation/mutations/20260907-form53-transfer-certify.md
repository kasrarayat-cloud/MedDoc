# §2.5 MUTATION DECLARATION — upload, certify and ACTIVATE the 53-control form

**STRICT. Committed BEFORE the act**, so its commit timestamp provably precedes
the rows it predicts. Ruling **#225**: this is the second half of the maintenance
act whose first half was the deploy of `43fcf4a6`, and it follows without an
interval.

⚠️ **FILED HERE, NOT IN `docs/foundation/deploys/`, AND THAT IS DELIBERATE.**
`declaration_resolve` scans that directory and **refuses any name it does not
recognise** — its keep-list is `README`, `BASELINE-*`, `*-JUDGED`,
`*-RETROSPECTIVE`, `*-backfill-declaration`. A mutation declaration under a new
name would have refused the next deploy. This is not a backfill, so it is not
given that suffix to sneak past the check.

| | |
|---|---|
| act | upload → certify → activate the pinned 53-control consult form |
| runs against | production, code at `43fcf4a6` (the deployed commit) |
| door | `bash scripts/run-ruled-mutation.sh --declaration <this file> -- …` |
| authority | ruling **#225**, and **#209** for the form's identity |

## THE TWO PINNED SIDES, ASSERTED BEFORE ANYTHING IS WRITTEN

| | |
|---|---|
| package sha256 | `5367fd075472cc2c6a1de768c5224e7522691ccad3d2c7aafc47071752920642` |
| `word/document.xml` sha256 | `ecb817039a035e975cf73605f4e5ba68a88362a5a27f02d204e6e11903cf241d` |

The script **refuses on any mismatch and writes nothing.** #209: the form is
produced once and this is that artifact; #215: its identity salt is the zip
container, so a regenerated copy would mint different `fieldId`s and match
nothing it was certified against.

## BASELINE — captured before anything changes

| quantity | value |
|---|---|
| note templates | **15** |
| compiled versions | **4** |
| field definitions | **185** |
| semantic mappings | **185** (all CERTIFIED) |
| CERTIFIED compiled versions | **3** of 4 |
| certifications | **3** |
| fill manifests | **5** |
| source artifacts | **6** |
| **visits** | **58** |
| **signed visits** | **40** |
| ACTIVE GI note template | `cmtlqpwju000o01nmnvqg3vkc` → compiled `9e758c45` (35 fields) |

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **M1** | note templates | 15 | **16** | the upload created nothing |
| **M2** | compiled versions | 4 | **5** | no twin was compiled from the form |
| **M3** | field definitions | 185 | **238** (+53) | the form did not compile to 53 controls |
| **M4** | semantic mappings | 185 | **238** (+53) | a compiled field without a mapping cannot be certified |
| **M5** | the new compiled version's `ros_gi_weight` kind | — | **`narrative_text`** | ⚠️ #216's whole purpose. `measurement` here means the compiler change did not reach production, and the GI alarm feature is unfillable |
| **M6** | the ACTIVE GI note template | `cmtlqpwju000o01nmnvqg3vkc` | **the new 53-field template** | ⚠️ **#225's second half.** Without this the deploy is unfinished and the degraded window stays open |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **M-N1** | **visits 58 / signed 40** | unchanged | never omitted. This act must not touch a single clinical record |
| **M-N2** | the existing **185** mappings | unchanged in count and status | an upload creates; it must not rewrite what is already certified |
| **M-N3** | the ULTRASOUND compiled version `617d6de9` | `structureSha256` `37813a60…`, still CERTIFIED | the other doctor-facing template is not part of this act |
| **M-N4** | rows with non-null `conceptScope` | **0** | the model may propose one, but nothing is certified with a scope the doctor has not confirmed |
| **M-N5** | `AuditAction` cardinality | **158** | this act runs no migration |

## WHAT WOULD MAKE THE CHECK FAIL

- **M5 reading `measurement`** — #216 did not reach the running code, and the act
  must stop rather than certify a form whose alarm-feature clause cannot be filled.
- **M6 not moving** — the act is incomplete by #225's own terms, and the silent
  styled-export degradation stays live on the owner's active template.
- **any movement in M-N1** — this act has touched a clinical record, which it has
  no authority to do.

## THE JUDGEMENT ROW #225 ADDS

> **"the active GI template fills end-to-end" — measured AFTER activation.**

Evidence is the certification chain's own synthetic test — `compile → derive →
REAL fill → CERTIFIED` — which is a genuine end-to-end fill through the
production wiring and reads no patient's record.
