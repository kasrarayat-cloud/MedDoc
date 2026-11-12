# Design v2 (FINAL): Gemini owns the interpretation, a second call appraises it, the rules read facts only

**Status.** The synthesized design of the design-v2 workflow, written by its judge on 2026-11-12, and REVISED the same day
against four refutation lenses (self-certification, holds, contract, migration and operations): 28 findings, 1 critical
and 8 high. Every finding's decision (accepted, or partly accepted with the rejected part's reason and a concrete
counter-input) is in `design-v2/REFUTATIONS.md`; the text before the revision is kept unchanged as
`design-v2/FINAL-V2-pre-refutation.md` (sha256 `cc5c2888...a00`). It is a design: nothing was built, sent, installed or run
in docker. It was written blind to the acceptance set: neither `acceptance-a1/` (in the session directory or in the
repository) nor any sealed set was opened. The scoring and the reason for every original choice are in
`design-v2/judging.md`.

**Governs.** The owner's directive of 2026-11-12 with the session's interpretation (a)-(j), and the 2026-11-09 directive
with its checklist (`docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`; HARNESS.md, the migration section). Where this
design and the directive disagree, the directive wins and the disagreement is a defect of this design.

**Base.** `feat/cpt-studio-gemini-interpreter-20261109` at `95d8aa347`. The code is identical at the worktree's head
`ddbdbfc5b` (checked at the revision: no change under `studio/`, `ops/`, `cptstudio/`, `tests/` or `scripts/`); the later
commits add only the a1 freeze and scoring documents, which were not opened. Paths are relative to `cpt-studio/`; a bare
module name is under `studio/interpretation/`.

**Provenance tags.** `[A]`, `[B]` and `[C]` mark what was taken from design A (extend), B (requirements) or C (two-pass).
`[J]` marks the judge's correction or addition; `judging.md` sections 3 and 5 give each reason. `[R:<finding>]` marks a
change made for a refutation finding: SC-A to SC-D (self-certification), HO-1 to HO-9 (holds), CO-1 to CO-8 (contract),
MO-1 to MO-7 (migration and operations); REFUTATIONS.md gives each. A tag on a heading covers its section. Appendix B maps
every part to its source.

Surveys are cited S1-S4 (contract, readers, rules, failures), failure classes by their S4 ids (T1, E2, ...), and v1
decisions as D-numbers.

---

## 0. The design on one page

```
revision text --contract/segment.py--> numbered units [S1]..[Sn]: sentences (hard wraps joined, initials kept);  [C][R]
   |                                    offsets, lines, pages (geometry only)
   v
PASS 1  extraction   stage interpret, purpose 'interpretation', gemini-events@2                               [C][A][B]
   sections (whose entry, what part, when its acts were done, who did them), people, encounter, sessions,
   anatomy, lesions, events, and DOUBTS. Every judgment is a FACT {state, value, qualifiers, sources[units, words,
   link], options}; a silent attribute is an empty slot; a doubt keeps the value and names what it doubts.
   No verified flag, no confidence, no default.
   |
   v  strict read, then deterministic checks: schema, source integrity, revision binding, attachment geometry,
   |  consistency of values, date literals, qualifiers. A failed check makes the fact UNRESOLVED.          [C][A][B]
   v
contract/claims.py: every fact a coding rule reads becomes CPT Studio's fixed sentence (act-phrased for an act,
   statement-phrased for a denial) citing the anchor's whole sentence; every READY- or exclusion-deciding fact also
   gets a generated CONTRARY CONTROL, and every place disjointness a rule reads gets PAIR CONTROLS         [B][C][J][R]
   |
   v
PASS 2  appraisal    stage appraise, purpose 'appraisal', gemini-appraisal@1                                  [C]
   sees the segmented document, the claims, and cards that name only an object's type and its sentence. Never
   pass 1's JSON, values, states, options, qualifiers, doubts or unknowns. Per claim: supports | contradicts |
   qualified | unclear; attached; qualifiers; evidence units. Plus 'unlisted': acts, denials and doubts no
   card's claims describe.                                                                                    [C][B][R]
   |
   v
contract/settle.py: one RESULT per fact (per act for an inherited fact)                                       [C][J]
   supported | negated   every check passed AND supported with attached evidence AND the control rejected
   contradicted          pass 1 reported both sides, or two statements in conflict (never appraised away)
   unknown               silent, or doubted by pass 1 (the value kept for the doubt arm)
   unresolved            anything else: a failed check, a qualifier, a disagreement, an incoherent control,
                         a fact no claim covered
   -> ONE EventInventory row, bound to the revision, both Gemini runs, the claim set and the versions
   |
   v
engine/ (cpt-studio-events@2): a typed, text-free FactSet; v1's coding rules forked into engine/ and rewired    [A][B][C][J]
   per code: required facts -> READY | HELD (one focused question or explanation) | EXCLUDED (by citation)
```

**The directive, item by item.**

| directive | how this design meets it | sections |
|---|---|---|
| Gemini owns timing, causality, entry ownership, targets, techniques, examined stations and extent, in a source-linked inventory, with supported, explicitly negated, contradicted and unknown kept apart | the v2 inventory: sections carry entry, occasion and performer; sessions carry extent (the endoscope's, a device's kept apart), completion, stations, tract, approach and encounter; events carry kind, status, date relation, target, technique, causality and yield; every fact has a source link and a state, and Gemini's doubts are kept beside its values (unknown, never absent) [R:CO-1] | 1, 2 |
| keyword reinterpretations and semantic vetoes leave the new path, none renamed; schema, source-integrity, revision-binding and coding-rule checks stay | the 17 v1 interpretation modules are denied in place as RETIRED (every function in them is off the new path); 145 readers are listed by name; static rules forbid text access and word lists in the new packages; a runtime property proves the rules read no text | 3.1, 3.5, 5 |
| verification is honest: a quote existing proves only that it exists; attachment to the right event and surrounding qualifications are checked; no self-certification | a claim cites its anchor's whole sentence (hard wraps joined, initials kept, the sentence closure); geometry checks where each source sits; a second call judges each claim against its text and surroundings, with statement-phrased sentences for denials, and must reject a generated contrary control (pair controls wherever a rule reads place disjointness); a degenerate appraisal is refused whole; nothing Gemini sets is read as verification [R:CO-3][R:HO-2][R:SC-B][R:SC-C][R:HO-4] | 1.2, 3 |
| hold only decisions depending on unresolved required facts; one focused explanation or question; unrelated supported codes proceed; broad denials and genuine contradictions preserved; an unknown target never proves that statements cannot conflict | the engine's required facts per code, a fixed rank, one clarification per held code (bound by rank across candidates), the pairing table (one established difference sets a statement apart; an unknown target or kind never does; a statement pass 2 doubts is still a statement), a doubt never read as an absence, monotonicity and independence proved by property tests [R:HO-1][R:HO-2][R:HO-3][R:HO-5][R:HO-8] | 4 |
| Corti, Astra and Fable stay; model agreement never approves; reviewer approval and provider confidentiality stay | unchanged and re-pinned; two Gemini calls agreeing establishes a fact, never a code | 4.12 |
| acceptance frozen before the prompt changes; fresh calls in small bounded batches; install, then the website walk, then the report | step 0a gates every prompt byte and every send; batches D1-D3 and A; the install and walk are steps of the plan | 8, 9 |
| the 2026-11-09 checklist | both calls go through the existing adapter, doors, holds and usage recording; one persisted inventory; every consumer reads it; additive migration; rollback to c2e53f8e | 6, 7 |

**What leaves.** Survey 2's 73 meaning readers, 19 literal readers and primitives, 46 contract-layer word checks and 7
consumers whose rule moves into Gemini's facts: 145 in all, named in section 5. Also gone: frame defaults (EB2), the
marker basis of exclusion (EB3), C-11's dismissal of Gemini's contradictions by literals, region moves of acts between
sessions, and the word-reading parity shims (4.13).

**What stays.** The adapter envelope and model pin; strict reading; revision binding; the interpreter hold, Stop, resume
and reconcile; the catalogue and every CPT, NCCI and reference rule of S3; the participants; reviewer approval; provider
confidentiality; rollback to `cpt-studio:c2e53f8e7d33`.

**What the refutation changed** (2026-11-12; REFUTATIONS.md gives each finding, what the judge verified, and the
decision). Doubts are kept beside committed values, so a doubt is never an absence (HO-1, CO-1). Units are sentences: hard
wraps joined, initials kept, words across consecutive units, a 12-unit item-level bound (CO-3, CO-4, CO-5). A placing
sentence anywhere in the document can place an act or a part (CO-2). Denials are claimed with statement-phrased
sentences, and one established difference sets a statement apart (HO-2). A statement pass 2 doubts stays a statement
(HO-3), and an unknown kind never narrows a pairing (HO-5). Controls are generated for every READY- or exclusion-deciding
attribute, cards carry no pass-1 label, pair controls guard every place disjointness a rule reads, and an empty station
list stands for "no limitation" only through an appraised completeness claim (SC-B, SC-C). The restatement role that moves
an entry is appraised (SC-D). Unlisted entries are dropped only by same nature and kind (SC-A, HO-6). Health refuses
yes-sayers and no-sayers (HO-4). K2 no longer couples an act to its examination (HO-7). The binding goes by rank and keeps
every candidate's witnesses (HO-8). A reach given both polarities is a contradiction (HO-9). An examination told across
several parts keeps its extent, per D36 (CO-6). Identical cards are made distinct (CO-7). The endoscope's reach is kept
apart from a device's (CO-8). Operations: the installer asserts v1 rows only, causes name no vendor and both denylists see
joined forms, pass 2 takes D49's deadlines, a legacy context save is an explicit re-check, the claim set is bound into the
appraisal's identity, the budget is set against the shared cap, and D59's rollback limit is stated (MO-1 to MO-7).

**Cost and latency** (section 7; both passes; FRESH-2 modelled at pass-1 output equal to v1's; revised after the
refutation): median about $0.083 and mean about $0.118 per document at November rates, $0.166 and $0.236 from
2026-12-01; about 1.85x v1. Median about 53 s, p90 about 138 s, largest document about 336 s. The binding constraint is
the output size: pass 1 must stay at or below 1.03x v1's output so that the live maximum (19,398 characters, GI Note #8)
still fits the 20,000-character bound, and pass 2's claim set must stay under its per-request bound (1.8).

---

## 1. The inventory schema v2

### 1.1 Versions and principles

| label | v1 | v2 | names | a change needs |
|---|---|---|---|---|
| `INTERPRETATION_VERSION` | `gemini-events@1` | `gemini-events@2` | pass 1: instruction, LOCAL and RESPONSE schemas, bounds, read rules, the segmentation rule | new pass-1 and pass-2 recordings |
| `APPRAISAL_VERSION` [C] | - | `gemini-appraisal@1` | pass 2: instruction, schemas, bounds (the per-request claim bound included), read rules, claim templates (act- and statement-phrased), the CLAIMED selection (by sha), the CONTROLS generator and its tables (KIND_SIBLINGS, SESSION_SIBLINGS, CONTRAST_PLACES, the pair-control and completeness rules, UNCONTROLLED), the seed rule, the health thresholds [R:SC-C][R:HO-2][R:HO-4] | new pass-2 recordings; pass 1's are reused |
| `INVENTORY_VERSION` | `gemini-inventory@1` | `gemini-inventory@2` | the checks, inheritance, the settle table, the doubt mapping, the reasons | a re-settle of the stored pass-1 bytes; stored pass-2 verdicts are reused only for claims whose content is unchanged, and a changed claim set needs a new pass-2 send, an explicit act for an existing record (6.2) [R:MO-5] |
| `REQUIREMENTS_VERSION` [B] | - | `cpt-requirements@1` | the requirement table, its read-sets, the CLAIMED table, RANK | a pin test refuses a CLAIMED change without an APPRAISAL_VERSION bump |
| `ENGINE_VERSION` (= `coverage.CODING_VERSION`) | `cpt-studio-events@1` | `cpt-studio-events@2` | the engine and `event_coding@2` | a recompute over the frozen inventory, with no send |
| `CONTEXT_VERSION`, `ROUTING_VERSION` | `gemini-context@1`, `gemini-routing@1` | `@2` | `engine/derive.py` | - |
| `ADAPTER_VERSION` | `gemini-generate@cptstudio-1` | `gemini-generate@cptstudio-2` | two request kinds | - |
| `MODEL` | `gemini-4-argon` | unchanged | no substitution (D13) | - |
| `EventInventory.interpretation_version` | `gemini-events@1` | `gemini-events@2/appraisal@1` (27 of 40 characters) | the pair asked and read, so the existing unique key holds per appraisal version | - |

Principles, each enforced by a test named in section 9:

| # | principle | from | what it rules out |
|---|---|---|---|
| P1 | **Words never decide.** The engine reads a typed FactSet of enumeration values, ids, states and offsets. Text exists only in segmentation, quote location, date-literal transcription and wording | [B] | every keyword reader, frame list, label grammar and clause reader, under any name |
| P2 | **One requirement table.** Each code's required facts are data; the claims of pass 2, the question rank and the acceptance trace derive from it | [B] | a rule reading an undeclared input; a claim no rule needs |
| P3 | **Four states, no defaults.** Silence is unknown, and so is an empty or short list: no rule reads a list's completeness except through an established completeness claim or rejected pair controls [R:SC-B]. A doubt is an unknown that keeps its value [R:HO-1][R:CO-1]. A frame is a cited fact. Inheritance from a section is a stated, checked and appraised edge, never a default | [B][C][A][J][R] | EB2's "silence certifies": 858 times and 758 performers verified by omission on FRESH-2 (S1 finding 3), and its return through a short list (SC-B) |
| P4 | **Attachment is geometry; meaning is a reading.** Deterministic checks prove where a source sits, never what it means | [B][C] | "verified" meaning "bound" (S1 finding 2) |
| P5 | **Support needs three independent things:** the checks pass, a second call supports the claim with evidence attached to the same statement, and that call rejects the contrary control | [C] | Gemini certifying its own answer; a verifier that agrees with everything |
| P6 | **Fail closed and monotone.** Weakening any fact (an established fact to unresolved, a control left unrejected, an added doubt, a deleted member of a list) never turns HELD into READY or EXCLUDED and never releases a rival | [B][R:HO-1][R:SC-B] | absences releasing rivals (D163); an unknown target or kind proving independence; a doubt read as an absence |
| P7 | **One item per held code**: the highest-ranked unresolved requirement as a question, or an established failure as an explanation | [B][C][A] | one question per rule (S3 9.2); a question naming the wrong act (Q1) |
| P8 | **Coding rules stay; word-reading shims leave** | [B] | rules that were word readers wearing coding clothes |
| P9 | **No model string stored.** Units and words are stored as offsets; a text slice is stored only where `store.row` proves it equals the revision | v1 P9 | model text in the database |

### 1.2 Units: the citation substrate (`contract/segment.py`) [C; revised R:CO-3, CO-4, CO-5]

The request stays a pure function of the revision text and the pinned instructions (D1). `segment.units(text, pages)` cuts
the revision into units, which are meant to be sentences:

1. Lines are split on `\n`. An empty or whitespace-only line is a paragraph break.
2. **Hard wraps are joined** [R:CO-3]. A line break inside a paragraph continues the unit when the earlier line does not
   end in `.`, `!`, `?` or `:` (closing quotes or brackets after them allowed) and the next line begins with a lowercase
   letter. Every other line break ends the unit. The test reads two characters, never a word.
3. Inside a unit, a unit ends after `.`, `!` or `?`, optionally followed by closing quotes or brackets, when one or more
   spaces follow and then a character that is not a lowercase letter, EXCEPT after a token of one or two letters whose
   first letter is uppercase: an initial or a short title ("E. Morgan", "Dr. B. Prior") [R:CO-4]. There is no
   abbreviation list: the exception is a character shape.
4. A unit longer than 600 characters is split at the last space before 600 and marked `forced`.
5. Units never cross a page boundary. Each unit is `{id: "S<k>", start, end, line, paragraph, page, forced}`, offsets in
   the revision text, trimmed of surrounding whitespace.
6. **The sentence closure** of a run of units [R:CO-3]: extended backward over the preceding units of the same paragraph
   while the preceding unit does not end in `.`, `!`, `?` or `:`, and forward over the following units of the paragraph
   until one ends in them, at most 12 units in all. Claims cite, and cards show, the closure of the anchor, and the
   evidence check (3.2.5) accepts any unit of it, so a wrap the join rule misses (a continuation that begins with an
   uppercase letter) still brings its negator to the claim and the card.
7. **Words may run over consecutive units** [R:CO-4]. A source cites one or more consecutive units of one paragraph; its
   `words` are located in the revision slice from the first unit's start to the last unit's end, any run of whitespace
   (line breaks included) matching any run of whitespace. The same rule serves anchors and sources (3.1 I2, I3).
8. The framed text keeps v1's page framing (`[Page N]` lines and marker lines). Each unit is written `[S<k>] <text>`, a
   joined hard wrap inside it written as one space; units of one line are separated by one space, lines by `\n`, blank
   lines kept. If the revision already contains a match of `\[S\d+\]`, no request is built (a not-sent run,
   `refused: unbuilt`), recorded as a limit.

**Why a residual over-split is now harmless.** A sentence still cut (after a two-letter token's period, or at a wrap
continued by an uppercase letter) is harmless by rules 6 and 7: the claim shows the whole sentence and the words may cross
the cut. The pre-refutation rule cut at every line break and required words inside ONE unit, so its "an over-split is
harmless" was false (CO-4).

**Measured** on the 358 recorded v1 answers (`design-v2/judge-data/measure_v2r.py` and `seg_v2r.py`, read only, nothing
sent): 20,034 of 20,057 v1 `words` values lie inside one unit under this rule, against 18,297 under the pre-refutation
rule (1,760 crossed a unit); the kind or status words of 13 of 2,950 events cross a unit, against 545; every v1 passage
spans at most 6 units (1 unit 5,085 times, 2 units 639, 3 units 16, 4 units 1, 5 units 2, 6 units 1), so rule 7 and the
12-unit bound of 1.8 cover them. GI Note #8 has 181 units instead of 317, and its three wrapped denials ("historical only;
no / esophagogastroduodenoscopy ... was performed", "No colonic / stent was placed.", "No / hemostatic cautery ... was
performed in the rectum.") and its extent sentence are each one unit.

Units are geometry. `contract/geometry.py` derives `line(u)`, `paragraph(u)`, `consecutive(us)`, `closure(us)` and section
containment from them (3.1 G). A section may start in the middle of a unit, at the offset of its start words [J][B].

### 1.3 The fact and the doubt (`contract/types.py`, `contract/extract_schema.py`) [C, compacted by J; revised R:HO-1, CO-1, CO-2]

```python
FACT_STATES = ('supported', 'negated', 'contradicted')
LINKS = ('statement', 'section', 'frame', 'placing', 'document_frame', 'antecedent', 'other_statement')
QUALIFIERS = ('hedged', 'conditional', 'reported', 'partial', 'named_only', 'restatement_only', 'reference_only',
              'approximate')
DOUBT_BASES = ('stated', 'conflict', 'unclear')

SOURCE = {'units': [unit ids, consecutive], 'words': '<exact words inside the cited units, or "" for all of them>',
          'link': LINKS}
FACT   = {'state': FACT_STATES,
          'value': '<an enumeration value, an id or an ISO date; "" when contradicted>',
          'qualifiers': [QUALIFIERS],
          'sources': [SOURCE],
          'options': [{'value': '<value>', 'sources': [SOURCE]}]}   # contradicted only: one per side
SLOT   = [] | [FACT]        # [] = unknown, silent: nothing in the document governs it
FACTS  = [FACT, ...]        # multi-valued: places, reached points, stations, joins, distinct_from, same_as
DOUBT  = {'about': DOUBT_ABOUT, 'objects': [ids], 'units': [unit ids], 'basis': DOUBT_BASES,
          'readings': ['<values of that attribute the doubt leaves open>']}   # answer level, like v1's open_questions
```

| state | meaning | value | sources | options |
|---|---|---|---|---|
| `supported` | the document states the value for this object | a value | at least 1 | `[]` |
| `negated` | the document explicitly states the value does NOT hold for this object (the act was not done; the station was not examined; nothing was retrieved; the cecum was not reached) | the value denied | at least 1 | `[]` |
| `contradicted` | the document states incompatible values for the same attribute of one object (Y5: "two stones were removed. No stones were retrieved.") | `""` | the union of both sides | at least 2, each with its own sources |
| empty slot | silent: nothing in the document governs the attribute | - | - | - |

| a doubt (a `doubts` entry) | when | what settle does to each fact it names (3.3) |
|---|---|---|
| basis `stated` | the document itself states doubt ("It is unclear whether ...", "may have been") | unknown (`doubt_stated`); the value kept, the readings added |
| basis `unclear` | the words admit two or more readings ("Once, a 22 mm polyp was found ... It was removed piecemeal", BF2) | unknown (`doubt_unclear`); the value kept, the readings added |
| basis `conflict` | another statement of the document cannot be true together with the fact although it is not a value of that attribute (a part reported normal where an act on a lesion of that part is reported: W1S-499) | contradicted (`contradicted_by_pass1`), the doubt's units as the sides |

The directive's four states are kept distinct: supported, explicitly negated, contradicted, and unknown, which is silent
(an empty slot) or doubted (a fact a doubt names, its value kept). A silent unknown costs no output tokens, which is how
the richer inventory stays near v1's size (7.3).

**Why a doubt keeps the value, and why it sits beside it** [R:HO-1][R:CO-1]. Gemini commits a value and states its doubt
beside it. Across the 358 recorded v1 answers it gave status `uncertain` 0 times and time `unknown` 6 times in 2,950
events, but raised 111 open questions, and a question about time or performer sat on an event carrying a definite value
124 of 129 times (FRESH-1 r1 on BF2's document: time `earlier_encounter` from "Once", plus an open question on time). The
`doubts` list keeps that habit, and settle turns it into the state the rules need. The kept value is also what makes the
doubt arm work: `possibly` reads the value and the readings, and a status that is not established leaves every status
possible (4.2). The pre-refutation design asked instead for an `ambiguous` or `stated_doubt` state with value `""` and no
options, a state Gemini does not use, and `possibly` then read the most explicit doubt as an absence: base and E/M codes
went READY beside a doubted act (HO-1, critical).

A doubt can only demote: it never creates, sets or changes a value, and a doubted, contradicted, silent or failed fact is
never claimed. A doubt names attributes, never words; its units are checked to exist (I1), its objects to resolve (I4).

**Qualifiers** record what the statement says about itself. Any qualifier except `approximate` makes the fact unresolved
(3.1 Q1); `approximate` ("approx. 30 cm") is recorded and never lowers [B]. Plans, attempts and denials are NOT qualifiers:
they are status values, so one meaning has one encoding [B].

**Link types** (each with a deterministic geometry, 3.1 G):

| link | what the cited unit is |
|---|---|
| `statement` | the object's own statement: an event's anchor units; a session's examination anchor; a lesion's description unit |
| `section` | the start (heading, label, signature, opening words) or the closing signature of the section that contains the object |
| `frame` | a framing sentence inside the containing section ("All of the above was done by her previous surgeon.") |
| `placing` | a sentence anywhere in the document that says when, or by whom, this act or the acts of a part were done, from after the act or from another part ("This was done at the referring facility in 2024."; "Second opinion on an upper endoscopy done elsewhere; the procedure is described below."; "No endoscopy was done today; the narratives above are from 2023."; an attestation that the findings sections occurred on the date of service) [R:CO-2] |
| `document_frame` | a unit of section N0 that is a source of an encounter fact: the title, the date-of-service line, the documenting clinician's line |
| `antecedent` | the earlier statement an anaphoric frame refers to ("At that time" -> the outside EGD of March 2023, or this procedure's earlier sentence) |
| `other_statement` | another statement about the same object (a later sentence, a restatement); meaning appraised |

### 1.4 The answer of pass 1 (`gemini-events@2`): the exact shape

Written in `schema.py`'s LOCAL form: every object requires every property and forbids others; no nullable union; types are
object, array, string and integer only. RESPONSE_SCHEMA is derived by the same `gemini_schema` generator, copied into
`contract/jsonschema.py` so that v2 executes no v1 code (5.7).

```python
ANSWER = {'encounter': ENCOUNTER, 'people': [PERSON], 'sections': [SECTION], 'sessions': [SESSION],
          'anatomy': [ANATOMY], 'lesions': [LESION], 'events': [EVENT], 'doubts': [DOUBT]}             # [R:CO-1]

ENCOUNTER = {
  'date_of_service': {'state': DATE_STATES, 'value': '<ISO or "">', 'sources': [SOURCE],
                      'options': [{'value': '<ISO>', 'sources': [SOURCE]}]},         # v1 states: stated, several, not_stated
  'other_dates': [{'value': '<ISO at its precision>', 'role': FACT(DATE_ROLES)}],     # read only by dates.py's member-date rules
  'documenting_clinician': SLOT(ID)}                                                   # a person id

PERSON = {'id': 'P1', 'name': SOURCE, 'role': FACT(PERSON_ROLES)}

SECTION = {                                    # [A] owner, occasion, performer; [B] role, mid-line labels, closers
  'id': 'N0',                                  # N0 is the document's own opening part
  'start': SOURCE,                             # the heading, label, signature or opening words; units [] and words "" for N0
  'end': [SOURCE],                             # a closing signature ("Documented by Jo Rowe, RN"), else []
  'owner': FACT(OWNERS),                       # whose entry the part is
  'role': SLOT(SECTION_ROLES),                 # what the part is
  'occasion': SLOT(DATE_RELATIONS),            # when the acts TOLD in the part were done, relative to the date of service
  'performer': SLOT(PERFORMERS),               # who did the acts told in the part
  'performer_person': SLOT(ID)}

SESSION = {                                    # [C] the object; [B] through; [J] encounter, reached_anatomy; [R] device_reached
  'id': 'X1',
  'examination': SLOT(ID),                     # its examination or visit event; [] for a session told only by its acts (S3)
  'kind': FACT(SESSION_KINDS),                 # the family (v1 PROCEDURES less unknown)
  'encounter': SLOT(ENCOUNTER_RELATIONS),      # this document's encounter, or a separate one (read by the E/M template only)
  'tract': SLOT(TRACTS),
  'approach': SLOT(APPROACHES),
  'through': SLOT(ID),                         # the anatomy entry the scope went through (a stoma, a pouch)
  'reached': FACTS(EXTENTS),                   # the ENDOSCOPE's reach: supported = reached; negated = stated not reached
  'device_reached': FACTS(EXTENTS),            # points only a guidewire, catheter or capsule reached; no rule reads it [R:CO-8]
  'reached_anatomy': SLOT(ID),                 # the anatomy entry the endoscope's furthest point is (an anastomosis, a pouch)
  'completion': SLOT(COMPLETIONS),             # against the examination's own intended extent [R:CO-8]
  'stations': FACTS(STATIONS),                 # supported = examined; negated = explicitly not examined
  'part_of_session': SLOT(ID)}                 # this session is the endoscopic portion of that one (C3, C-4, N3)

ANATOMY = {'id': 'Y1', 'type': FACT(ANATOMY_TYPES), 'organ': SLOT(LANDMARKS2),
           'subtype': SLOT(ANASTOMOSIS_SUBTYPES), 'joins': FACTS(LANDMARKS2)}

LESION = {'id': 'L1', 'description': SOURCE, 'multiplicity': SLOT(MULTIPLICITY),
          'places': FACTS(LANDMARKS2), 'distinct_from': FACTS(ID), 'same_as': FACTS(ID)}

EVENT = {
  'id': 'E1',
  'anchor': {'units': [ids], 'kind_words': '<words>', 'status_words': '<words>'},   # the act's own statement
  'restatements': [{'units': [ids], 'role': RESTATEMENT_ROLES}],
  'kind': FACT(KINDS),                         # v1's 42; removal and intervention stay umbrellas
  'other_class': SLOT(OTHER_CLASSES),          # only for kind 'other' (G5, T4)
  'status': FACT(STATUSES),                    # 'not done' = negated performed
  'session': SLOT(ID),
  'date_relation': SLOT(DATE_RELATIONS),       # this act's OWN placement; [] = the containing section's occasion governs
  'date': SLOT(DATE),                          # a date the document gives for this act, ISO at its precision
  'performer': SLOT(PERFORMERS),               # own; [] = the containing section's performer governs
  'performer_person': SLOT(ID),
  'target': {'lesion': SLOT(ID), 'structure': SLOT(STRUCTURES), 'places': FACTS(LANDMARKS2),
             'anatomy': SLOT(ID), 'duct': SLOT(DUCTS)},
  'technique': {'device': SLOT(DEVICES2), 'route': SLOT(ROUTES)},
  'purpose': SLOT(PURPOSES), 'cause': SLOT(CAUSES), 'cause_event': SLOT(ID),
  'part_of': SLOT(ID), 'part_relation': SLOT(PART_RELATIONS),
  'yield': SLOT(MATERIALS),                    # extraction acts: what THIS act retrieved
  'access_outcome': SLOT(ACCESS_OUTCOMES),     # cannulation acts [B]
  'scope': {'breadth': SLOT(BREADTHS), 'targets': [lesion ids], 'segment': [landmarks],
            'covers': [event ids], 'excepts': [event ids]},                 # statements only
  'visit': {'basis': SLOT(EM_BASES), 'separately_identifiable': SLOT(SEPARATE)}}
```

**Enumerations.** Each value list carries a one-line definition in the instruction, pinned with the schema.

| name | values | from |
|---|---|---|
| KINDS, DATE_ROLES, DATE_STATES, MULTIPLICITY (less unknown) | v1's | v1 |
| DEVICES2 | v1's DEVICES less `not_stated` (29) | [C] |
| LANDMARKS2 | v1's LANDMARKS less `not_stated`, plus `third_portion_duodenum`, `fourth_portion_duodenum` (containment under `duodenum`) | [A][B][C] |
| EXTENTS | LANDMARKS2 plus `stated_depth` ("to 40 cm": an extent stated without a landmark) | [C] |
| STATUSES | performed, attempted_not_completed, planned | [B][C] |
| DATE_RELATIONS | on_date_of_service, earlier_date, later_date | [J] |
| ENCOUNTER_RELATIONS | this_encounter, separate_encounter | [J] |
| PERFORMERS | documenting_team, other_clinician, other_facility | [C] |
| OWNERS | documenting_clinician, nursing, anesthesia, pathology, radiology, other_clinician, outside_record, patient_reported, administrative | [A][B][C] |
| SECTION_ROLES | header, indication, history, medications, sedation, procedure, findings, impression, complications, specimens, plan, pathology_result, nursing_note, anesthesia_record, addendum, signature, other | [B] |
| PERSON_ROLES | documenting_clinician, trainee, assistant, nurse, anesthesia, pathologist, radiologist, referring, other | [C] |
| OTHER_CLASSES | procedure, test, order, imaging, laboratory, counseling, evaluation, medication, other | [C] |
| SESSION_KINDS | v1's PROCEDURES less `unknown` (16; the family table is unchanged) | [C] |
| TRACTS | upper, lower, pancreatobiliary | [C] |
| APPROACHES | oral, transnasal, transanal, through_stoma, through_pouch, through_gastrostomy, percutaneous | [C] |
| COMPLETIONS | complete (the examination reached the extent it set out to reach, as the document states it), incomplete (stopped short of its intended extent), terminated (stopped early for a stated reason) [R:CO-8] | [B][C] |
| STATIONS | esophagus, stomach, duodenum, jejunum, ileum, colon, rectum | [B] |
| STRUCTURES | lesion, stricture, ulcer, bleeding_site, vessel, varix, stone, stent, duct, pancreatic_fluid_collection, gallbladder, liver, lymph_node, mass, wall, lumen, foreign_body, mucosa, anastomosis, other | [C] |
| DUCTS | biliary, pancreatic, cystic | [C] |
| ROUTES | submucosal, eus_transmural, eus_fine_needle, intraluminal, intraductal, percutaneous, topical | [C] |
| PURPOSES | diagnostic, removal, lift_for_resection, marking, hemostasis (bleeding present at this encounter, treated), prophylaxis (prevention), treatment, access, sampling, drainage, decompression, other | [C] |
| CAUSES | act_of_this_session, pre_existing_lesion, spontaneous, earlier_procedure, other | [C] |
| PART_RELATIONS | step_of, lift_for, access_for, adjunct_of, component_of | [C] |
| MATERIALS | stones, stone_fragments, sludge, debris, stent, foreign_body, tissue, anything (negated `anything` = nothing retrieved) | [C] |
| ACCESS_OUTCOMES | achieved, failed, achieved_after_failed_attempts | [B] |
| BREADTHS | single_target, listed_targets, all_of_kind, exceptive, segment | [B][C] |
| ANATOMY_TYPES | surgically_absent, anastomosis, stoma, ileal_pouch, gastric_pouch, roux_limb, bypass, other_alteration | [C] |
| ANASTOMOSIS_SUBTYPES | ileocolic, colocolic, colorectal, coloanal, ileorectal, ileoanal, gastrojejunal, gastroduodenal, esophagojejunal, esophagogastric, hepaticojejunal, choledochoduodenal, pancreaticojejunal, other | [C] |
| RESTATEMENT_ROLES | restates, summarizes, title, names_only, refers_back | [C] |
| EM_BASES | total_time, medical_decision_making | v1 |
| SEPARATE | stated (denied = negated) | [C] |
| DOUBT_ABOUT | status, kind, session, date_relation, performer, entry, target, technique, purpose, cause, part_of, yield, access_outcome, extent, stations, completion, approach, anatomy, identity, date_of_service, visit, whole (every claimed fact of the named objects) [R:CO-1] | [R] |
| DOUBT_BASES | stated, conflict, unclear (1.3) | [R] |

**Gone from v1's answer.** The passage table (units replace it); `open_questions` as such (the `doubts` list keeps its
shape and Gemini's habit, and settles per named fact [R:CO-1]); `sequence` (read by no rule, S1 5.11); `contradicts[]`
(the `contradicted` state, a doubt with basis `conflict`, and a statement's `covers`); `encounter.reach` and
`visit_facts` (sessions and `visit`); `documenting_endoscopist` and `team` (people and roles); an extent instrument slot
(`device_reached` keeps a device's points out of the endoscope's reach [R:CO-8]); frame defaults of any kind.

### 1.5 Inheritance from sections: stated, checked, appraised [A, with J; revised R:SC-D, CO-2]

FRESH-2 shows most acts carry no time or performer words of their own (858 of 1,079 current times and 758 of 1,063 team
performers were word-less, S1 5.5-5.6). v1 read that silence as "today, by the team" (EB2). Design C instead made every act
cite the document frame, which costs about 135 output tokens per act in exactly the long documents where the size bound
binds (7.3). This design states the frame once per section and lets acts inherit it, then appraises the inherited fact per
act, so the safety is per act and the cost is per section.

- `effective(E, date_relation)` is E's own slot when non-empty; otherwise the containing section's `occasion`; otherwise a
  silent unknown. The same for `performer` and `performer_person`.
- **The containing section** of E is the last section whose start offset is at or before E's anchor start, and whose
  closing signature, when given, is at or after E's anchor end (3.1 G2, G4). Sections are Gemini's; containment is
  offsets.
- **Entry ownership** is never a per-act claim of pass 1: `entry(E)` is the owner of the section containing E's anchor,
  claimed per act (3.2.2). One exception keeps D124's rule, under which only an act told ONLY in another role's entry is
  held: when E has a restatement R with role `restates` that lies in a section the documenting clinician owns, `entry(E)`
  is documenting_clinician, but only when R's role is ESTABLISHED. The role is claimed ("The part of the document beginning
  at {R's units} tells this act in full, in its own words, not only as a summary, a title or a reference to another
  part."), with the control "The part of the document beginning at {R's units} only summarizes this act, names it, or
  refers to where it is told.", and the owner of R's section must be established too [R:SC-D]. When R's role is claimed
  and not established, the entry is not moved and `event_entry` is a QUESTION (U), never the explanation "documented only
  in the nursing entry". `summarizes`, `title`, `names_only` and `refers_back` never count (E3: "Polypectomy as above")
  [J].
- **Placing sentences** [R:CO-2]. A section's occasion or performer, and an act's own date relation or performer, may cite
  a sentence anywhere in the document with link `placing`: a sentence after the act that refers back to it ("This was done
  at the referring facility in 2024."), or a sentence in another part that says when or by whom the acts of this part were
  done (an Indication's "the procedure is described below"; a Plan's "the narratives above are from 2023"; an attestation
  that the findings sections occurred on the date of service). Which facts cite a placing sentence is what says which acts
  or parts it governs; no separate list is kept, so one meaning has one encoding.
- **Not a default.** A section's occasion and performer are Gemini's facts with their sources: the section's start (a
  "History:" heading), a framing sentence in it, a placing sentence elsewhere, or, for a section whose role is a narrative
  of this encounter, the document frame (3.1 K7). An act whose own statement places it differently states its own slot,
  which overrides.
- **Appraised per act.** Every inherited or placed fact of a claimed act is rendered as a claim about THAT act ("This act
  was done on the date of service."; for a denial, "This statement is about biopsies on the date of service."), citing the
  section's or the placing sentence's source, and judged by pass 2 against the act's own sentence and its surroundings
  (3.2). A misplaced inheritance therefore ends unresolved (held), never READY. Probe (b) and T5's "Once, a 22 mm polyp was
  found ... It was removed piecemeal" are the cases this exists for; the latter also carries a doubt (BF2).

### 1.6 The directive's attributes, located

| attribute | field(s) | states | source link | replaces (v1) |
|---|---|---|---|---|
| timing relative to the date of service | `event.date_relation` (own) or the section's `occasion` (inherited); `event.date`; `session.encounter`; `encounter.date_of_service` | all; a doubt keeps the value (BF2) | statement, section, frame, placing (a later sentence or another part, CO-2), document_frame, antecedent (anaphora, T8) | EB2 default; D33 framing words; verify.time_words; facts.day_of and its frames |
| causality / part_of | `part_of` + `part_relation`; `cause` + `cause_event`; `purpose`; `session.part_of_session` | all; a separate act is `part_of` negated | statement, other_statement | v1's citation-less part_of; mapping.hemostasis_in_doubt; D58/D77 place adjacency |
| entry ownership | `section.owner` + `role`; `entry(E)` by containment; a `restates` restatement moves it only with its role established (1.5, SC-D) | all on the owner | section (label, heading, signature), document_frame for N0 | events.another_role_hold and 16 helpers |
| performer | `event.performer` / `section.performer`; `performer_person`; `people` | all | statement, section, frame, document_frame | EB2 default; performer_words; literals.names |
| target | `target.lesion`, `structure`, `places` (every place, never a reference point, never the wall crossed), `anatomy`, `duct`; lesion `same_as` / `distinct_from` | all | statement, other_statement | Context.places(every), compared_landmark, defining_target, wall_place, eus_places, identity rules 2-4 |
| technique | `technique.device`, `technique.route`; the session's `approach`, `through` | all; a device said not used = negated | statement | device_named, submucosal_act, route readers |
| examined stations | `session.stations[]` | supported = examined; negated = not examined; an empty list is unknown, and stands for "no limitation stated" only through an established completeness claim (4.3 STATIONS, SC-B) | statement, other_statement | assess._stated_stations, _denied_station |
| extent | `session.reached[]` (the endoscope's), `device_reached[]`, `reached_anatomy`, `completion` (against the intended extent) | supported = reached; negated = not reached | statement (G5: the examination's sentences, or a unit no act is anchored in) | device_reach, scope_named, beyond_reach, _full_colonoscopy_reach |
| yield | `event.yield` | supported = material; negated `anything` = nothing retrieved; contradicted | statement, other_statement | the 19 ercp yield readers |
| denial scope | `scope.breadth`, `targets`, `segment`, `covers`, `excepts` | all | statement | verify.scope_words; the words-only exceptive (C-7) |
| anatomy type | `anatomy.type`, `organ`, `subtype`, `joins` | all | statement | anastomosis words, pouch_types, gastric_beside |
| session | `sessions[]`; `event.session`; `session.kind`, `encounter`, `part_of_session` | all | statement, section, document_frame | coding_family region moves; procedure_named; the single-family default |

### 1.7 The settled inventory: what is stored and what the engine reads [C][B]

`contract/settle.py` writes the content of ONE `EventInventory` row: `events = {units, encounter, people, sections, sessions,
anatomy, lesions, events, doubts, claims, unlisted}`. Every fact, and every inherited fact per act, is stored as:

```json
{"claim":     {"state": "supported", "value": "on_date_of_service", "qualifiers": [], "options": [],
               "inherited_from": "N2" },
 "sources":   [{"units": ["S2"], "link": "document_frame", "words": {"start": 31, "end": 41, "text": "11/09/2026"},
                "geometry": "ok"}],
 "checks":    {"integrity": "ok", "geometry": "ok", "literal": "ok", "literals": [{"value": "2026-11-09", "precision": "day"}],
               "consistency": "ok", "qualified": false},
 "appraisal": {"claim": "K17", "content": "<sha256 of template id, subject, value, unit ids>", "verdict": "supports",
               "attached": "yes", "qualifiers": [], "evidence": ["S6"], "control": {"claim": "K41", "verdict": "contradicts"}},
 "result":    "supported",
 "reasons":   []}
```

- `result` is one of `supported`, `negated`, `contradicted`, `unknown`, `unresolved`. `reasons` come from the closed list
  `settle.REASONS`, which `store.load` checks.
- **The engine never sees text.** `engine/facts.py` builds the FactSet from the stored row and strips every `text`: the
  engine reads `result`, `claim.value`, `claim.state`, `claim.options`, ids and integer spans. Values are Python `Enum`
  members (P1). `wording.quote(span)` slices the revision for questions after the decision.
- `units` is stored as the segmentation table of offsets, with no text. Every stored `words.text` must equal its revision
  slice (`store.row`, kept). `open_questions` (NOT NULL) is written `[]`. `claims` is the claim list with each claim's
  content key, and its sha256 is among the row's bindings, so a verdict is never read against a different claim
  [R:MO-5]. `verification` holds the settle report: counts per attribute and result, reasons, the doubts applied,
  appraisal health, control coherence, the unlisted statements kept and those dropped with the event that absorbed each
  [R:SC-A], both runs' usage.

### 1.8 Bounds (read, never sent; a whole answer outside them is refused, named by count, never truncated)

Pass 1: events 200; sections 48; sessions 16; people 16; anatomy 16; lesions 64; other_dates 16; restatements 16 per event;
doubts 64, each with at most 16 objects and 4 readings; each slot at most 1; places, reached, device_reached and joins 8;
stations 7; distinct_from and same_as 16; sources 8 per fact; options 4 per fact; targets, segment, covers and excepts 32
each; words 600 characters; cited units 4,000 per answer.

**Units per source: at most 12, an ITEM-level bound** [R:CO-5]. An over-long source fails its fact's check
(`source_too_long`); the answer is not refused. Twelve is D32's margin (about twice) over the measured maximum of 6 units
for any v1 passage under 1.2's rule. The pre-refutation bound of 4 equalled the measured maximum of the old rule, and one
longer sentence would have refused the whole answer.

**Pass 2** [R:MO-3]: exactly one verdict per claim; evidence 8 unit ids per verdict, no words; unlisted 32. **Claims per
request at most 640**, computed so that the bound times the output per verdict (about 24 tokens) plus the largest thinking
measured on FRESH-2 (16,776 tokens) stays under the 32,768-token cap; it is recomputed from D2's measured output per
verdict and pinned in APPRAISAL_VERSION. A claim set over the bound is not sent (7.5). The largest modelled claim set, the
43-event Note #8 family, is about 524 claims (`cost_model_v2r.out.json`). The pre-refutation bound of 1,200 claims was more
than the cap could ever answer (1,200 x 28 = 33,600 tokens).

An unknown unit id, words outside their units, a source over 12 units, or an id that names no object of the answer are
ITEM-level findings: that source or fact fails its check and the fact is unresolved; the answer is not refused (3.1). JSON,
schema shape, enumeration and the other bounds refuse the whole answer, as v1's `read.py` does.

### 1.9 Worked example (synthetic)

```
[S1] COLONOSCOPY REPORT
[S2] Date of service: 11/09/2026
[S3] Endoscopist: Anselm Wrenfield, MD (fictional)
[S4] History: Prior colonoscopy in 2023 with removal of two adenomas.
[S5] Findings: The colonoscope was advanced to the cecum.
[S6] A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.
[S7] Neither biopsy nor tattoo was performed.
[S8] Documented by Jo Rowe, RN: A 4 mm polyp in the rectum at approx.
[S9] 5 cm was biopsied with cold forceps.
```

Pass 1 (abridged):
- Sections: N0 (owner documenting_clinician via S3, document_frame; role header; occasion on_date_of_service via S2
  "11/09/2026"; performer documenting_team via S3). N1 starts at S4 "History:" (role history; occasion earlier_date via its
  start words "Prior colonoscopy in 2023", link section). N2 starts at S5 "Findings:" (role findings; occasion
  on_date_of_service and performer documenting_team, both via the document frame). N3 starts at S8 "Documented by Jo Rowe,
  RN:" (owner nursing via its start, link section; role nursing_note; occasion on_date_of_service via S2; performer []).
- Session X1: examination E1, kind colonoscopy (S1, document_frame), encounter this_encounter (S2), reached [cecum] (S5
  "The colonoscope was advanced to the cecum", statement: the endoscope's own reach, P19).
- E2: anchor S6; kind snare; status performed ("was removed"); session X1; target lesion L1, places [sigmoid_colon]; device
  cold_snare; `date_relation` [] and `performer` [] (N2 governs).
- E3, E4: biopsy and tattoo denials; anchor S7; status negated performed ("Neither biopsy nor tattoo was performed");
  breadth all_of_kind; session X1; performer [] (none stated). Their attributes are claimed with statement-phrased
  sentences ("This statement is about biopsies in session X1.", "This statement is about biopsies on the date of
  service."), which a faithful second reading can support for a denial [R:HO-2].
- E5: anchor [S8, S9] (consecutive units); kind biopsy; status performed; target places [rectum].
- E6: anchor S4; kind removal; status performed; `date` 2023; N1's occasion governs (earlier_date).

What settles and decides (Corti proposes 45385, 45380 and 45378):
- **45385 (E2): READY.** Its kind, status, inherited date relation and performer, entry (N2's owner) and session are each
  supported, appraised against S6 in its place, with the controls rejected. No statement pairs with a snare.
- **45380 (E5): HELD, one question `conflict:biopsy`.** E3 ("Neither biopsy ... was performed", all of its kind in X1, no
  performer stated so it covers any performer) pairs with E5 on every row: a CONTRADICTION. E5's entry is also established
  as nursing (an `event_entry` explanation, another role), recorded in `held_facts`. The contradiction ranks first (4.8), so
  the member sees both statements quoted, and D3 cannot recur. (Should pass 2 doubt E5's status because of S7, E5's status
  is unresolved and the pair is a DOUBT, asked at rank 2 with both statements quoted: held either way.)
- **45378: HELD `base_included`** (an explanation naming 45385): its session has a reportable snare.
- E6 supports nothing and holds nothing: its date relation is earlier_date, established through N1, so it is never
  possibly today's act (and its kind, the `removal` umbrella, could not support a method-specific code anyway).
- Had Gemini filed E4 as a performed tattoo with the status words "tattoo was performed" (probe (a)), the claim would cite
  S7's sentence closure, the whole sentence with its negator (also when a hard wrap splits it, 1.2 rules 2 and 6
  [R:CO-3]); pass 2 contradicts "This act was carried out" against it and supports the control, so E4's status is
  unresolved. E4 then supports nothing, and it is a possible statement: it pairs as a DOUBT with every tattoo or injection
  act of X1 (4.5), so even a second, genuine tattoo would be held, never READY on the strength of E4's misfiling
  [R:HO-3].

---

## 2. The prompt contract v2

### 2.1 What pass 1 must report (`gemini-events@2`) [C, with A, B and J]

The system instruction is fixed and pinned; the user turn is the framed, segmented document alone (D1). The clauses below
are what the instruction must say. The wording is the implementer's, and each clause is pinned by a TEXT-ONLY test that
greps the instruction for its rule. The instruction is written only after the acceptance freeze (8, step 0a) and developed
only on documents outside the acceptance set (9.6).

- **P1 Scope.** Report only what the document states. Never infer, assume or complete anything, and never use clinical
  knowledge to fill a gap. When the document does not say, leave the slot empty.
- **P2 Citation.** Cite units by their ids. `words` are copied exactly from inside the cited units; a statement that runs
  over several units (a sentence split at a period that does not end it, or at a line break) cites all of them, in order,
  and its words may run across them; `""` cites the whole of the units [R:CO-4]. Every source names its link. Never cite a
  unit for a fact it does not state.
- **P3 Objects.** List the PEOPLE named, with their roles; the SECTIONS in document order; each SESSION the document tells
  (an examination, procedure or visit, whether on the date of service, at this encounter or at a separate one, or on
  another occasion the document names, such as "Prior colonoscopy in 2023"); each ANATOMY alteration or absence; each
  LESION (one id per distinct finding an act is done to or a statement is about, never merged); each EVENT.
- **P4 Sections** [A][B]. A section begins at a heading, a role label or note heading, a signature that opens an entry, or
  a sentence that says a new part begins. A label that opens in the middle of a line opens its section where its words
  begin. A part that resumes after another entry is a new section. N0 is the document's opening part. For each section
  give: `owner` (whose entry it is); `role` (what the part is); `occasion` (when the acts TOLD in the part were done,
  relative to the date of service: never when the part was written); `performer` (who did the acts told in the part).
  Cite the section's start, a framing sentence of the part, a sentence elsewhere in the document that says when or by
  whom the acts of this part were done (link `placing`: "the procedure is described below", "the narratives above are
  from 2023", an attestation about the findings sections) [R:CO-2], or, for a part that narrates this encounter, the
  document's title, date line or author line. Leave `occasion` or `performer` empty when the part does not say.
- **P5 Events.** One event per act, and one per STATEMENT about an act: not done, planned, attempted, in doubt, at another
  time, by another clinician or facility, or told in another's entry. The anchor is the act's own statement; a title,
  heading, impression line or "as above" line is never the anchor of an act told elsewhere (X1, E3). When the act is
  stated in full in more than one part, anchor it in the documenting clinician's own report if there is one, and list the
  other statement as a restatement with role `restates` [J]. A composite act told as its parts (an exchange: a stent
  removed and a stent placed) is reported as its parts, each with its own status, timing and duct, linked by
  `part_relation: component_of`; a part the document says was not done is a negated event. One statement that denies
  several acts gives one event per act.
- **P6 Every attribute is a fact** with a state: supported, negated or contradicted; or its slot is empty when the
  document is silent. No default value exists anywhere.
- **P7 Doubt is reported beside the value, never resolved** [R:CO-1][R:HO-1]. When the document itself states doubt ("it
  is unclear whether", "may have been", "possibly"), when the words admit two or more readings, or when another statement
  of the document cannot be true together with a fact although it is not a value of that attribute (a part reported
  normal where an act on a lesion of that part is reported): give the fact the value its own words most directly state,
  or leave the slot empty when they state none, and add a `doubts` entry naming the attribute, the objects, the units
  that raise the doubt, its basis (`stated`, `unclear` or `conflict`) and the readings it leaves open. Never choose a
  reading silently, and never drop a doubt because a value was given.
- **P8 Contradiction is reported, never resolved.** When two statements cannot both be true of the same object, give
  `contradicted` with each side in `options`. A sequence is not a contradiction: failed attempts followed by success are an
  attempted_not_completed event and a performed one, or one cannulation with `access_outcome:
  achieved_after_failed_attempts` (the D127 hazard). Different targets, techniques, times, sessions or performers are not a
  contradiction.
- **P9 Qualifications.** Every hedge, condition, second-hand report, partial statement, title-only, restatement-only or
  reference-only mention that applies to a fact is listed in its `qualifiers`; an approximate measure is `approximate`.
- **P10 Timing** [J][R:CO-2]. Give an act its own `date_relation` when its own statement, an anaphoric frame in it, or
  another sentence that refers to this act ("This was done at the referring facility in 2024.", link `placing`) places
  it:
  - `on_date_of_service`: done on the date of service, at this encounter or at a separate one the same day. "Earlier this
    AM, I performed a flexible sigmoidoscopy" in an office note is on the date of service; its session says it was a
    separate encounter (T1-T3, BF1);
  - `earlier_date` or `later_date`: another date.

  Give `date` when the document gives a date for the act, at the precision written. An anaphoric frame ("At that time",
  "During this procedure") cites its antecedent unit with link `antecedent` (T8). A reference to earlier text of this
  document ("As previously noted") is not another time (T9). A purpose is not a time: a colectomy scheduled for 12/01 is
  the purpose of today's tattoo. When the placing words are vague ("Once, a 22 mm polyp was found"), add a doubt (P7).
  Otherwise leave the slot empty: the containing section's occasion governs, which may itself cite a placing sentence
  (P4).
- **P11 Entry and performer are separate.** The entry is the owner of the section the anchor is told in. The performer is
  who did the act. A nurse's or anesthetist's entry that tells an act does not make the nurse the performer, and the
  endoscopist's "as above" line does not move the act into the endoscopist's entry (E1-E5).
- **P12 Session.** `session` is the session the act was done in, citing the heading of its part, the instrument named, or
  words such as "on withdrawal" or "with the gastroscope". Leave it empty when the document does not say which; never
  decide it from the act's anatomical region (N1, N2). For each session: `encounter` (this document's encounter or a
  separate one); `part_of_session` (an EGD inside an EUS, C3; a sigmoidoscopy "as part of" a colonoscopy, N3); `approach`
  (how the scope entered; an anatomy history clause is not the approach, A3); `through` (the anatomy entry it went
  through).
- **P13 Target.** `places` are every place the act was done. A point measured from ("2 cm distal to the ampulla") is never
  the place (G1, BF8). The wall crossed on the way ("across the posterior gastric wall") is the route, not the target (G3,
  BF9). `structure` is what was acted on. `lesion` is given only when the act's statement names or refers back to it; a
  finding near the site is not the target unless the document says the act was done to it; a place named after an act
  (scar, site, bed) is a place or a lesion, never an act. `anatomy` names the anastomosis, stoma or pouch the act is at. A
  target the document does not state is left empty; a stated target is never left out so that two statements look
  unrelated.
- **P14 Technique.** `device` is the device named; a device said NOT to be used for this act is that fact negated. `route`
  is how the agent reached the tissue: submucosal, EUS-guided transmural, fine needle, intraluminal, intraductal,
  percutaneous or topical (G1).
- **P15 Purpose and cause.** `hemostasis` only when the document says bleeding present at this encounter was treated;
  prevention is `prophylaxis`. For every hemostasis act, `cause` says what caused the bleeding: an act of this session
  (with `cause_event`), a pre-existing lesion, spontaneous bleeding, an earlier procedure, other; or it is left empty. A
  history act is never today's cause (C1-C4, BF4, BF14).
- **P16 Part of.** `part_of` with `part_relation` (step_of, lift_for, access_for, adjunct_of, component_of) only when the
  document says the act was done as part of, to enable, or as a step of another act; always with sources (G3, N3, C4).
- **P17 Yield** (extraction acts only): what THIS act retrieved; `anything` negated when the document says this act
  retrieved nothing; contradicted when both are stated; empty when not stated. Another occasion's, performer's or act's
  retrieval is never this act's yield, and a purpose ("to ensure all stones had been removed") is not a yield (T7, Y1-Y7).
- **P18 Access** (cannulation acts): `access_outcome` achieved, failed or achieved_after_failed_attempts, with the duct in
  `target.duct` [B].
- **P19 Extent** [R:CO-8]. `reached` holds the points the endoscope ITSELF reached (supported) and the points the
  document says it did not reach (negated); a point only a guidewire, catheter or capsule reached goes in
  `device_reached`, never in `reached`; `reached_anatomy` names the anatomy entry when the endoscope's furthest point is an
  anastomosis or pouch; `completion` says whether the examination reached the extent it set out to reach, as the document
  states it: complete, incomplete (stopped short of it) or terminated (stopped early for a stated reason), with its words
  (S4, BF7).
- **P20 Stations.** One fact per station the document mentions: examined (supported) or not examined (negated). A
  statement that only some stations were examined makes the others negated. A reach is not a station, and a station is
  not the reach (S1, S2, BF6).
- **P21 Anatomy.** `type` is the alteration or absence; `subtype` and `joins` say which organs an anastomosis joins. The
  type never depends on a landmark (A1, A2, BF5). An organ seen is not an anatomy entry.
- **P22 Denials.** A denial is an event with status negated. `breadth`: one target; listed targets; every act of its kind
  in its session; every act except the acts already reported (exceptive, listing them in `excepts`); a segment (its first
  and last landmark). `covers` lists every reported act the denial applies to. A denial whose target is unknown is
  reported with its target empty, never left out or narrowed (D1-D3, Y6).
- **P23 E/M.** On a visit event, `visit.basis` and `visit.separately_identifiable` (stated, denied as negated, or empty).
  An act of kind `other` gets `other_class` (G5, T4).
- **P24 Keep separate things separate.** Never merge two acts, lesions, sessions or sections, and never describe one with
  another's words.

### 2.2 Ambiguity, doubt, contradiction and qualification, stated (S4's borderline filings) [B][C]

| BF | phrase | v1 filing | v2 statement | the engine then |
|---|---|---|---|---|
| 1 | "Earlier this AM, I performed a flexible sigmoidoscopy" (office note) | earlier_encounter, or current | the act's date_relation on_date_of_service ("Earlier this AM"); its session encounter separate_encounter | 45330 READY; 99213 held separate_em |
| 2 | "Once, a 22 mm polyp was found ... It was removed piecemeal ..." | earlier_encounter "Once" plus an open question on time (FRESH-1), or unknown plus open questions (FRESH-2) | the act's date_relation as its words state (earlier_date by a placing link, or empty), with a doubt: about date_relation, basis unclear, readings on_date_of_service and earlier_date, units the "Once" sentence [R:CO-1] | the snare code held event_time, never excluded (an exclusion needs an established other date); the same-lesion biopsy code held, its bundling depending on that timing |
| 3 | "At that time, ..." | earlier_encounter (50 of 50) | antecedent link to the occasion the frame names: this procedure's statement, or the March 2023 outside EGD | the act takes that occasion |
| 4 | "History: On June 4, 2026 the stricture was dilated ..." | performed + earlier | the act in a history section, own date 2026-06-04, earlier_date; today's bleeding control never cites it as cause | no candidate; no history act is today's cause |
| 5 | "small gastric pouch", "ileal pouch-anal anastomosis" | landmark pouch, stomach or anastomosis | anatomy gastric_pouch; ileal_pouch joins [ileum, anus] | the enteroscopy classes read types |
| 6 | "EUS imaging was performed from the duodenum only." | kind/status only | stations: duodenum supported; esophagus and stomach negated ("only"). Should pass 1 leave the list empty, the completeness claim it then gets is contradicted by pass 2, so STATIONS stays unmet [R:SC-B] | 43259 and 43242 held (stations) |
| 7 | "reached the anastomosis only"; "The procedure was terminated" | varies | completion incomplete or terminated against the intended extent, with words; reached_anatomy [R:CO-8] | 52/53 consideration; extent per class |
| 8 | "2 cm distal to the ampulla" | target = the reference point | places = the wall injected (duodenum); the ampulla is not a place | 43253 reads route and places |
| 9 | "drainage of the pseudocyst ... across the posterior gastric wall" | landmark = the wall | structure pancreatic_fluid_collection, lesion L1; route eus_transmural; places [stomach] for the route | 43240 reads structure |
| 10 | "Procedure: ERCP with biliary stent exchange." | kind words from the title | a `title` restatement; the components are events with narrative statements; "the existing stent was left in place" negates the removal | 43276 not supported; 43274 READY (X1) |
| 11 | "Impression: ... complete balloon stone extraction." | cited as kind and status | a `summarizes` restatement, never the anchor | - |
| 12 | a hard-wrapped sentence after a label or signature | line passages | consecutive units of one anchor; the label starts a section with its owner | entry by containment |
| 13 | an act told only on a "CRNA note:" line | frame defaults: team, current | the section owner anesthesia; the performer as stated, else empty | held another role (an explanation) |
| 14 | "Cautery was applied ..." | bleeding_control by device | purpose and cause as stated, else empty | 43255 held until stated |
| 15 | a coagulation told after a removal | part_of the whole | part_relation adjunct_of, or cause act_of_this_session | bundled (explanation) |
| 16 | "A polypectomy of the gastric body polyp was performed." | removal; session by heading order | kind removal (method not stated); session as stated, or empty | act_method; procedure |
| 17 | "No other injection was given." | scope not_applicable | breadth exceptive, excepts [E1] | no exclusion of E1's code (D1) |
| 18 | "As previously noted, no polypectomy was performed." | earlier by "previously" | no own date relation (the section's occasion governs); "previously" refers to the text | contradiction with today's snare (T9) |
| 19 | "Double-balloon enteroscopy; the colon was converted into an end ileostomy in 2019" | a route from history | approach as stated for this examination, else empty; the stoma an anatomy entry | the class asks the approach |
| 20 | "Push enteroscopy: ... On withdrawal, a polypectomy ..." | heading order | session as stated ("On withdrawal" of which scope), else empty | procedure question, never a move |
| 21 | "Three stones, the largest 9 mm, were extracted ..." | kind words vary by run | yield stones, supported, linked; independent of how the kind is worded | 43264 reads yield |
| 22 | "This was done at the referring facility in 2024." after the act (f2-after-002) | earlier_encounter and other_facility citing it (2 of 2) | the act's own date_relation earlier_date and performer other_facility, link `placing`, appraised for this act [R:CO-2] | another date and facility established: an exclusion by citation can follow; otherwise held, never READY on an inherited "today" |
| 23 | "Second opinion on an upper endoscopy done elsewhere; the procedure is described below." in the Indication (twins-015) | earlier and other_facility citing it (FRESH-2, 3 of 3), or current (FRESH-1, 2 of 3) | the Procedure section's occasion earlier_date and performer other_facility, link `placing` to the Indication [R:CO-2] | held or excluded, never READY on the inherited date line |
| 24 | "Body and fundus normal" beside "7. Gastric body polyp removed with cold snare." (W1S-499) | the act current, `contradicts` empty, the conflict only in an open question (6 of 6) | the act as stated, with a doubt: about status, basis conflict, both units [R:CO-1] | contradicted: 43251 held `conflict:snare`, both statements quoted |
| 25 | a guidewire advanced beyond the endoscope's furthest point (v6_altered_anatomy_guidewire) | the reach at the anastomosis | `reached` the endoscope's point and its anatomy entry; the guidewire's point in `device_reached` [R:CO-8] | COLFULL reads the endoscope's reach only |
| 26 | "No polypectomy was performed at the last colonoscopy; none was performed today either." in one unit (fb08) | two removal denials with identical kind words | two denials, each with its own status words; the cards quote each one's words [R:CO-7] | each denial's timing appraised apart |

### 2.3 What the prompts never contain [A][B][C]

- A CPT code, a family's code list, a case, an example document or an expected answer (D3). No phrase from S4's
  representative inputs, the U32 registry or the refutation case files; a test pins it [A]. The examples quoted in 2.1's
  clauses and 2.2's table are written for the reader of this design and fall under the same scan.
- A member value, filename or reading (D1).
- In pass 1, any statement that a second reading exists, so its behaviour is not tuned to the checker [C].
- In pass 2, any statement that some claims are controls [C], or any label of pass 1's values on a card [R:SC-C].
- A provider or product name.
- A word list to match. Meanings are described ("a separate encounter on the same date"), never surface forms [B].

### 2.4 Pass 2's contract (`gemini-appraisal@1`) [C, with J; revised R:SC-A, SC-C, CO-2, CO-7, HO-2]

**Request.** A pinned system instruction; one user turn: the same framed, segmented document, the cards and the claims in
their seeded order. Cards are renumbered (A1.. acts and statements about acts, X1.. sessions, N0.. sections, L1.. lesions,
Y1.. anatomy). **A card names only the object's type and the units of its anchor's sentence closure (1.2 rule 6), or of a
lesion's or anatomy entry's description** [R:SC-C]: never a kind, family, owner or other label from pass 1's values, so no
control can be rejected by comparing it with a card. When two events share an anchor unit, each card also quotes that
event's own anchor words (its kind words and status words: document text, never a value), so the two cards differ
[R:CO-7]. Pass 2 never sees pass 1's JSON, ids, order, options, qualifiers, doubts, unknowns or any value that is not
rendered as a claim.

**Clauses** (normative; each pinned by a grep test):
- **A1.** You check claims about a clinical document. Another reader made them, and any claim may be wrong. Judge each
  claim only against the document, and look for what would make it false.
- **A2.** For each claim, read the cited units; then the whole sentence, paragraph and part around them, the heading or
  label above them, the entry they are in (who wrote that part), and every other statement about the same act, session,
  lesion or entry.
- **A3.** `supports`: the document plainly states the claim about THIS object, with no qualification. `contradicts`: the
  document states otherwise, or the cited text is about another act, occasion, performer, entry or target. `qualified`:
  stated, but hedged, conditional, planned, reported second-hand, named only in a title or heading, restated from
  elsewhere, or narrower in scope; name the qualifiers. `unclear`: the document does not let you tell. A claim phrased
  about a statement ("This statement is about ...") asks what the statement concerns, not whether an act was done
  [R:HO-2].
- **A4.** `attached`: `yes` when the cited units, read in their place, are about the object the claim names: its own
  statement; the heading, framing sentence or document line that governs the part of the document where that object is
  told; or a sentence elsewhere that says when, or by whom, this act or the part it is told in was done [R:CO-2]; `no`
  when they are about another object; `unclear` otherwise [J: C left this undefined for frame-cited facts].
- **A5.** `evidence`: the ids of the units you relied on (no words). For contradicts and qualified, the units that
  contradict or qualify.
- **A6.** `unlisted`: every statement of an act, a denial of an act, or a doubt about an act that no card's claims
  describe, with its kind when the document names one and the session card it belongs to when the document says. A
  sentence can tell more than one act ("removed and replaced", "biopsied and then removed") or deny more than one: list
  each act it tells or denies that the claims do not describe, even when a card names that sentence [B][J][R:SC-A].
- **A7.** Answer every claim exactly once. No free text. Do not add claims.

```python
VERDICTS = ('supports', 'contradicts', 'qualified', 'unclear')
ATTACHED = ('yes', 'no', 'unclear')
QUALIFIERS_2 = QUALIFIERS + ('negated_context', 'other_occasion', 'other_performer', 'other_entry', 'other_target',
                             'other_act', 'scope_limited', 'planned_only', 'history_only')
APPRAISAL = {'verdicts': [{'claim': 'K1', 'verdict': VERDICTS, 'attached': ATTACHED, 'qualifiers': [QUALIFIERS_2],
                           'evidence': ['<unit ids>']}],
             'unlisted': [{'units': [ids], 'what': 'act|denial|doubt', 'kind': '<a KINDS value or "">',
                           'session': '<a session card id or "">'}]}
```

### 2.5 Pins and versions [B][C]

The pins are the sha256 of both instructions, both LOCAL schemas, both RESPONSE schemas, the segmentation rule's
constants, `claims.TEMPLATES`, `claims.STATEMENT_TEMPLATES`, the `claims.CONTROLS` generator with its tables
(`KIND_SIBLINGS`, `SESSION_SIBLINGS`, `CONTRAST_PLACES`, the pair-control and completeness rules, `UNCONTROLLED`), the
CLAIMED table, the health thresholds and the per-request claim bound [R:SC-C][R:HO-4][R:MO-3]. They are checked when a
request is built and when an answer is read (the `prompt.check_pins` and `read.check_pin` pattern), and computed in the
commit that fixes each prompt, which comes after the acceptance freeze commit (8, step 0a). A changed byte of pass 1's
pinned objects needs `gemini-events@3`; of pass 2's, `gemini-appraisal@2`; a changed check, settle or doubt-mapping rule,
`gemini-inventory@3`, which re-settles stored pass-1 bytes and re-sends pass 2 only when the claim set changed (6.2)
[R:MO-5].

---

## 3. Verification

**The principle.** A cited unit existing in the revision proves only that it exists. A fact is ESTABLISHED (supported or
negated) only when three independent things hold [C]:
1. every deterministic check passes (3.1): the source exists and is whole, sits where its link says, and agrees with
   Gemini's other values and with the date literals in its own words;
2. a separate Gemini call, which never saw pass 1's answer, supports CPT Studio's rendering of the claim (act-phrased for
   an act, statement-phrased for a denial [R:HO-2]) with evidence attached to the same statement, after reading the
   statement's whole sentence and its surroundings (3.2);
3. that call rejects the generated contrary control (3.2.3); the pinned UNCONTROLLED list names each READY- or
   exclusion-deciding attribute decided without one, with the reason a single verdict there can only hold [R:SC-C].

Each of the three can only demote. None can lift a fact to established by itself, and Gemini sets no field that means
"verified".

### 3.1 What is checked deterministically (`contract/extract_read.py`, `geometry.py`, `consistency.py`, `date_literals.py`)

| id | check | reads | on failure | why it is not a word reader |
|---|---|---|---|---|
| S1 | strict JSON, then LOCAL_SCHEMA_2, bounds, ids unique per object family, ISO shapes (date of service, other dates, event dates) [C] | the answer | whole answer refused (`Refusal`, stage json, schema, bounds or ids), as v1 | shape |
| S2 | the fact shape of 1.3 (value empty exactly for contradicted; sources and options counts) and the doubt shape (each named object carries the attribute; each reading is a value of that attribute's enumeration) [C][R:HO-1] | the fact's and the doubt's own fields | fact unresolved (`shape_inconsistent`); a malformed doubt applies to every claimed fact of its objects (fail-closed) | shape |
| I1 | every cited unit id exists | ids | `unit_unknown` | ids |
| I2 | `words` lie inside the cited units, which may be several consecutive units: exact tier on the slice from the first unit's start to the last unit's end, any whitespace run matching any whitespace run; else the fold tier (the copied `fold`: NFKC, casefold, dash and quote folding, whitespace collapsed); first and last characters on word boundaries (v1's `_bounded_positions`) [R:CO-4] | the cited units' revision slice | `words_not_in_units`, `words_not_bounded` | a substring position, as v1's binding |
| I3 | a source's units are consecutive within one paragraph and at most 12 [R:CO-5]; the anchor's likewise; `kind_words` and `status_words` lie inside the anchor's units by I2's rule, the same rule for anchors and sources [R:CO-4] | offsets | `units_not_consecutive`, `source_too_long` (item-level), `anchor_words` | offsets |
| I4 | every id resolves (session, section, lesion, anatomy, person, event, covers, excepts, targets, cause_event, part_of, part_of_session, through, reached_anatomy); no self reference; part_of, cause_event and part_of_session acyclic | ids | `reference_invalid` | ids |
| B1 | revision binding: the extraction request is built from the revision text (text_sha256) and the pinned instruction, schema and segmentation; the appraisal request from the revision text, the extraction response bytes (sha256), INVENTORY_VERSION (the checks select the claims) and the pinned appraisal objects, never from a member value; `store.row` refuses unless every stored words text IS its revision slice; the row's sha256 covers the bindings, both runs and the claim list's sha256 included [R:MO-5]; `load` refuses unknown versions, shapes, closed values and hash mismatches, and reads every v2 inventory version it has shipped as stored [C][R:MO-5] | hashes, offsets | row not written; load raises | integrity |
| G1 | **link geometry** per source: `statement` units are among the object's anchor units or their sentence closure (an event), its examination's anchor (a session) or its description unit (a lesion); `section` is the containing section's start or closing source; `frame` is a unit inside the containing section's span; `placing` is any unit that is not the object's own anchor, its meaning (which acts or parts it governs) appraised per act [R:CO-2]; `document_frame` is a unit of N0 that is a source of an encounter fact (the date of service, the documenting clinician, a session kind); `antecedent` precedes the anchor; `other_statement` units exist (their meaning is appraised) [C, J] | units, offsets, section spans | `geometry_<link>` | offsets only; it never decides what a heading means (pass 2 does) |
| G2 | **section geometry**: starts strictly increasing by offset; each start located; N0 at the text start; a span runs from its start to the next start, or to its closing source; an overlap or an unlocated start makes that section's owner, occasion and performer unresolved [A][B] | offsets | `section_order`, `section_start_unlocated` | offsets |
| G3 | **statement tie**: a target fact with link `statement` has its words inside the anchor units; `target.lesion`'s description unit is the anchor, a restatement or an antecedent of the event (identity rule 1, generalised; rules 2-5 retire) [C][A] | offsets | `target_detached` | offsets |
| G4 | **inheritance edge**: an inherited fact is attached only when the act's anchor lies inside the section's span and the section's fact passed its own checks [A][J] | offsets | `inherit_unattached` | offsets |
| G5 | **examination evidence** (D36, restated) [R:CO-6]: each of a session's reached, completion, stations, approach and through sources lies in its examination's anchor or one of its restatements, or in a unit that is the anchor of NO act; a source lying only in other acts' anchors, of this session or another, is inferred from where they were done (D36). There is no section test, so an examination told across several parts passes (GI Note #8 tells its insertion, its completion and the neo-terminal ileum in three sections). The pre-refutation wording, "a unit stating an act of that session", was undefined, and its natural reading admitted exactly what D36 forbids (W1S-399's reach from a biopsy sentence) [A][J] | offsets, anchors | `extent_inferred` | offsets |
| G6 | **restatement geometry**: restatement units are not anchor units; a `title` restatement lies in N0 or in a section start | offsets | the restatement is ignored | offsets |
| K1 | **values allowed together** [C][A]: scope only on negated or stated-doubt statements; yield only on extraction kinds; access_outcome only on cannulation; cause and cause_event only with purpose hemostasis; part_of and part_relation together; reached, stations and completion only on endoscopic sessions; visit facts only on em_visit; other_class only on kind other; performed or attempted with later_date, or planned with earlier_date, inconsistent; exceptive needs non-empty excepts, each existing, of a kind the statement covers, and asserted positive; listed_targets needs 2 or more targets; single_target a lesion or a place; segment two landmarks; the umbrella `intervention` only on statements | values | `structure_<rule>` | values |
| K2 | **session consistency** [C][A][R:HO-7]: an event's session exists; a session's examination names it; an act's session kind admits its kind (`catalogue.family_codes_act`); an act's own claimed date relation that differs from its session examination's claimed one makes the ACT'S `session` fact unresolved. The examination's facts are never touched, and different performers in one session are legitimate: there is no performer arm (a surgeon called in to place clips does not unresolve the endoscopist's examination) | ids, values, catalogue | `session_inconsistent`, `session_conflict` | values |
| K3 | **place against session** [B]: an act place whose region (`REGION_OF`, a table over enumeration values) the session's family cannot reach makes the act's session fact unresolved; nothing is ever moved | values | `session_unreachable` | values |
| K4 | **anatomy against places** [A]: an anatomy entry surgically_absent at Y, and a supported reached point, station or act place at Y or inside Y | values | both `anatomy_conflict` (unresolved) | values |
| K5 | **person against performer** [A]: performer documenting_team with a person of another role, or other_* with the documenting clinician | values | `person_conflict` | values |
| K6 | **instrument** [A][B][R:CO-8]: a point both in `reached` (supported) and in `device_reached` (supported) makes that reached point unresolved; `device_reached` never satisfies R6 or a class | values | `instrument_conflict` | values |
| K7 | **frame by role** [B][R:CO-2]: a `document_frame` source, or a `placing` source giving on_date_of_service or documenting_team, for the occasion or performer of a section whose role is history, indication, medications or plan, or whose owner is outside_record | values | that fact unresolved (`frame_role`) | values |
| K8 | **both polarities** [R:HO-9]: a supported and a negated fact of one value, or of a value contained in it (`engine/anatomy.py` containment), on one object's `reached`, `stations` or act `places` | values | the two settle as ONE contradicted fact of pass 1, both sources kept (3.3 row 1): pass 1 reported both sides, so nothing is created | values |
| L1 | **date literals** [C][A][B]: the six copied v1 date parsers read a timing fact's OWN cue words and its date's words, never a unit around them. on_date_of_service needs any day literal to equal the effective date of service; earlier_date needs it to end before; later_date to start after; `date` must equal the literal in its words; the date of service and other dates equal their words' literal. **At claim time** the effective date is the document's own date of service (pass 1's, when its literal passes), and a literal that meets no document date does not stop the claim, so the claim set depends on the revision and pass 1's bytes alone, never on a member value [R:MO-5]. The literals are stored and re-judged at assess and at read time against the effective date (member precedence, `dates.py`), with no text read, which can only demote | stored literals | `literal_mismatch`; `literal_unchecked` (at assess and read time) when a day literal meets no effective date | calendar arithmetic; demotes only |
| Q1 | any qualifier except `approximate` on a fact | the qualifiers | `qualified:<q>`; not appraised | Gemini's report of the qualification, read as a value |

**What a failure does.** It never sets, changes or removes a value. It never creates a fact, an exclusion, a support or a
contradiction, and it never makes anything READY. It makes the fact UNRESOLVED with closed-list reasons. A failed fact is
not sent to pass 2: pass 2 may never repair pass 1's citation, because that would create support.

**Cross-object rules** (settle) [C]: an event whose anchor fails I3 has every fact unresolved (`anchor_invalid`); a
section whose owner is unresolved makes every act inside it entry-unresolved; a section whose occasion or performer is
unresolved makes the facts its acts inherit unresolved; a session whose kind is unresolved makes its acts' family
unresolved. Every doubt is applied to the facts it names (3.3 rows 1 and 2); a doubt about an act's inherited attribute
applies to its effective fact, and a doubt about `whole` names every claimed fact of its objects [R:HO-1][R:CO-1].

### 3.2 The independent pass: the appraisal

#### 3.2.1 Which facts are claimed [B, with J; revised R:HO-2, SC-B, SC-D]

`engine/requirements.CLAIMED` is generated with the requirement table (8, step 1f) and pinned by sha in APPRAISAL_VERSION.
It lists, per object class, the attributes that some coding rule reads:

| object | attributes claimed |
|---|---|
| an act of a codable kind (a kind some family's catalogue lists, an examination, an em_visit, or kind `other`) | kind, other_class, status, session, effective date_relation, date, effective performer, performer_person (other_clinician), entry; device (every codable act); route (injection, tattoo, fiducial, drainage, fna); structure (drainage; an EUS-session injection); duct (ERCP kinds); places and lesion (the lesion-bearing kinds: snare, emr, esd, hot_biopsy, biopsy, ablation, injection, tattoo, clip, bleeding_control, dilation, stent, band_ligation, fna, drainage); purpose, cause, cause_event (clip, injection, bleeding_control, ablation); part_of and part_relation (when present); yield (extraction kinds); access_outcome (cannulation); visit basis and separately_identifiable (em_visit); and the role of a `restates` restatement that lies in a section the documenting clinician owns (1.5) [R:SC-D] |
| a statement (an event whose claimed status is negated) of a codable kind | kind, status, session, effective date_relation, its own performer (when named), breadth, covers, excepts, targets or segment, device (when named), each with a STATEMENT-PHRASED template (3.2.2) [R:HO-2] |
| a session | kind, encounter (a session holding a visit), tract, approach, through, reached, reached_anatomy, completion, stations, part_of_session; and, for an upper EUS session whose stations list is empty, the completeness claim (3.2.2) [R:SC-B] |
| an anatomy entry | type, organ, subtype, joins, for the entries a session's through or reached_anatomy, an act's target.anatomy, or a class rule (stoma, pouch, limb, bypass, a surgically absent organ a reach or station names) reads |
| a lesion | multiplicity, distinct_from, same_as, for lesions of claimed acts |
| the encounter | date_of_service |

Every supported or negated fact in CLAIMED that passed its checks becomes one claim; a doubted, contradicted, silent or
failed fact is never claimed. A fact a coding rule reads but CLAIMED omits settles `unresolved(unappraised)`: an omission
can only hold, never release, and P-READSET (9.4) fails in CI when the engine reads an attribute CLAIMED does not list.
Controls, pair controls and the completeness claim are generated from pass 1's answer before any code is proposed, as
every claim is (3.2.3).

#### 3.2.2 The claims [C]

The assertion comes from the fixed template table `claims.TEMPLATES` (versioned by APPRAISAL_VERSION); labels come from
fixed tables (kind, device, landmark, role, owner, structure). A dash means the attribute has no negated form.

| attribute | supported | negated |
|---|---|---|
| act.kind / other_class | "This act is a {kind label}." / "This act is {class label}." | - |
| act.status performed | "This act was carried out (not only planned, attempted or denied)." | "The document states that this act was not carried out." |
| act.status attempted / planned | "This act was begun but not completed." / "This act is planned or recommended, not done." | - |
| act.date_relation | "This act was done on the date of service." / "... on a date before the date of service." / "This act is to be done, or was done, after the date of service." | - |
| act.date | "This act was done on {the date as written}." | - |
| act.performer | "This act was done by {the documenting clinician or a member of their team / a clinician other than the documenting clinician and their team / another facility}." | "The document states this act was not done by {...}." |
| act.performer_person | "This act was done by the person named at {units}." | - |
| act.entry | "This act is told in the part of the document that begins at {start units}, written by {owner label}." | - |
| act.session | "This act was done during session {X}." (no label: a session's family is claimed only as `session.kind`, with its control [R:SC-C]) | - |
| act.target | "This act was done to lesion {L}." / "... in the {landmark}." / "... to {structure label}." / "... at anatomy {Y}." / "... in the {duct} duct." | "The document states this act was not done in the {landmark}." |
| act.technique | "This act used {device label}." / "This act was {route label}." | "The document states that {device label} was not used for this act." |
| act.purpose | "This act was done for {purpose label}." | - |
| act.cause / cause_event | "The bleeding this act treated was {cause label}." / "... was caused by act {A}." | "The bleeding this act treated was not caused by another act of this procedure." |
| act.part_of | "This act was {relation label} act {A}." | "The document states this act was separate from act {A}." |
| act.yield | "This act retrieved {material label}." | "The document states that this act retrieved nothing." |
| act.access_outcome | "The cannulation {was achieved / failed / was achieved after failed attempts}." | - |
| statement.breadth | all_of_kind: "This statement says no {kind label} at all was done in session {X}." exceptive: "This statement denies only {kind label}s other than acts {A..}." single, listed or segment: "This statement denies {kind label} of {target}." | - |
| statement.covers | "This statement applies to act {A}." (one claim per covered act) | - |
| visit.basis / separately_identifiable | "The visit's level is based on {basis label}." / "The document states the visit was significant and separately identifiable from any procedure." | "The document states the visit was not separately identifiable." |
| session.kind / encounter | "Session {X} is a {label}." / this: "Session {X} is the encounter this document records." separate: "Session {X} was a separate encounter on the date of service, not the one this document records." | - |
| session.tract / approach / through | "Session {X} examined the {tract}." / "In session {X} the scope was passed {approach label}." / "In session {X} the scope passed through anatomy {Y}." | - |
| session.reached / instrument / anatomy / completion | "In session {X} the endoscope itself reached the {point}." / "The furthest point in session {X} was reached by {instrument label}." / "... was at anatomy {Y}." / "Session {X} was {completion label}." | "In session {X} the endoscope did not reach the {point}." |
| session.stations / part_of_session | "In session {X} the {station} was examined." / "Session {X} was the endoscopic portion of session {Z}." | "In session {X} the {station} was not examined." |
| anatomy | "The patient has {type label} (described at {units})." / "The {organ} is surgically absent." / "This anastomosis is {subtype label}." / "... joins the {landmark}." | "The document states the {organ} is not surgically absent." |
| lesion | "Lesion {L} is {a single lesion / a group}." / "Lesions {L} and {M} are different lesions." / "... are the same lesion." | - |
| encounter.date_of_service | "The date of service of this document is {date}." | - |

**Statement-phrased templates** [R:HO-2]. A denial says that an act was NOT done, so a sentence asserting that the act was
done in a session, on a date or at a place is false of it, and a faithful pass 2 must reject it (A3). Every attribute
claimed for an event whose claimed status is negated therefore uses these forms; the act forms above serve every other
status, the planned and attempted ones included:

| attribute | supported | negated |
|---|---|---|
| statement.kind | "This statement is about {kind label}s." | - |
| statement.status negated | "This statement says that {kind label} was not done." | - |
| statement.date_relation | "This statement is about {kind label}s on the date of service." / "... on a date before the date of service." / "... after the date of service." | - |
| statement.session | "This statement is about session {X}." | - |
| statement.performer (own, when named) | "This statement is about {kind label}s by {the documenting clinician or a member of their team / a clinician other than the documenting clinician and their team / another facility}." | - |
| statement.target | "This statement is about {kind label}s of lesion {L}." / "... in the {landmark}." / "... from the {first} to the {last}." / "... at anatomy {Y}." / "... in the {duct} duct." | - |
| statement.device | "This statement is about {kind label}s with {device label}." | - |
| statement.breadth, covers, excepts | the forms above (`statement.breadth`, `statement.covers`), already phrased about the statement | - |

**The completeness claim** [R:SC-B], for an upper EUS session whose stations list is empty: "The document does not say
that the ultrasound examination of session {X} covered only some of the esophagus, the stomach and the duodenum." It is
CPT Studio's rendering of what pass 1's empty list asserts (P20 asks pass 1 to report the other stations as negated when
only some were examined), cited at the examination's sentence closure, and appraised with its control like any claim.

**The restatement role** [R:SC-D]: "The part of the document beginning at {units} tells this act in full, in its own
words, not only as a summary, a title or a reference to another part."

**Pair controls** (3.2.3) [R:SC-B] use the real-claim forms: on an act, "This act was done in the {landmark}." or "This act
was done to lesion {L}."; on a statement, "This statement is about {kind label}s in the {landmark}." or "... of lesion
{L}."

#### 3.2.3 The contrary controls [C, with J; revised R:SC-B, SC-C, CO-7, HO-3, HO-4]

A verifier shown a claim tends to agree with it. Every READY- or exclusion-deciding claim therefore gets a hidden twin that
asserts the contrary about the same object, citing the same units, written with the same templates (the negated and
statement-phrased forms real claims use included), so nothing about its wording marks it. Controls are interleaved by the
seeded order.

**Generated, not hand-listed** [R:SC-C]. `claims.CONTROLS` is a generator over the requirement table's read-sets: for every
(object class, attribute, value) that a rule reads on a READY or exclusion path (P-READSET records them), it yields the
contrary below. P-CONTROLLED (9.4) fails in CI when such an attribute has no generator and is not on the pinned
UNCONTROLLED list. The pre-refutation table was hand-listed, and left `session.kind`, a dozen codable kinds,
`anatomy.subtype`, `reached_anatomy`, `lesion.multiplicity`, `visit.basis`, a statement's targets and `performer_person`
decided by one verdict, the answer this section calls biased (SC-C: a balloon sphincteroplasty filed as a sphincterotomy
went READY as 43262 on a single "supports").

| controlled (attribute, value) | the control asserts |
|---|---|
| act.status performed supported / negated | the negated form / the supported form |
| act.status attempted_not_completed / planned | "This act was carried out (not only planned, attempted or denied)." |
| act.date_relation on_date_of_service / earlier or later | "... on a date before the date of service." / "This act was done on the date of service." |
| act.performer documenting_team / other_* | "... by a clinician other than the documenting clinician and their team." / "... by the documenting clinician or a member of their team." |
| act.performer_person | "This act was done by the person named at {another person's units}" (when another person is named) |
| act.entry {owner} | the same start units, written by the flipped owner label (nursing for the documenting clinician; the documenting clinician otherwise) |
| restatement role `restates` | "The part of the document beginning at {units} only summarizes this act, names it, or refers to where it is told." [R:SC-D] |
| act.session (two or more sessions) | "This act was done during session {another session of the encounter}." |
| act.kind, every codable kind [J][R:SC-C] | "This act is a {sibling kind label}" from KIND_SIBLINGS, which covers every codable kind (generated by step 1f and pinned): snare/emr, emr/snare, esd/emr, hot_biopsy/biopsy, biopsy/hot_biopsy, clip/injection, injection/clip, tattoo/injection, bleeding_control/clip, ablation/bleeding_control, dilation/stent, stent/dilation, band_ligation/injection, stone_extraction/lithotripsy, lithotripsy/stone_extraction, stent_removal/stent, stent_exchange/stent_removal, sphincterotomy/dilation, cannulation/sphincterotomy, cholangioscopy/cannulation, foreign_body/stone_extraction, peg/tube_placement, tube_placement/peg, tube_replacement/tube_placement, decompression/stent, myotomy/dilation, fundoplication/myotomy, fna/biopsy, drainage/fna, capsule_study/examination, manometry/pressure_measurement, pressure_measurement/manometry, ph_monitoring/manometry, rectal_sensation/balloon_expulsion, balloon_expulsion/rectal_sensation. Examination and em_visit are decided through `session.kind` and the visit facts, which are controlled |
| act.other_class | procedure against evaluation; every other class against procedure |
| act.target.places (dilation and stent acts) [J] | "This act was done in the {contrast landmark}" from `CONTRAST_PLACES` (a fixed table of the nearest disjoint landmark: esophagus/stomach, stomach/duodenum, sigmoid colon/rectum, ...) |
| act.target.lesion | "This act was done to lesion {another lesion of the session}" (when one exists) |
| act.technique.device of a technique class (balloon, wire_bougie, bougie) | "The document states that {device label} was not used for this act." |
| act.technique.route eus_transmural | "This act was a submucosal injection." |
| act.target.structure pancreatic_fluid_collection | "This act was done to the wall." |
| act.purpose hemostasis | "This act was done for prevention of bleeding." |
| act.cause (any cause other than act_of_this_session) | "The bleeding this act treated was caused by act {another positive act of the session}" (only when one exists) |
| act.yield supported / negated | "The document states that this act retrieved nothing." / "This act retrieved stones." |
| act.access_outcome achieved / failed | the failed form / the achieved form |
| statement.status negated | "This statement says that {kind label} was done." |
| statement.kind | "This statement is about {sibling kind label}s." |
| statement.date_relation, session, performer | the contrary value, in the statement form |
| statement.targets (single, listed, segment) | "This statement is about {kind label}s in the {contrast landmark}." / "... of lesion {another lesion}." |
| statement.breadth exceptive / all_of_kind | the all_of_kind form / the exceptive form (only when reported acts of the kind exist) |
| statement.excepts (each excepted act) | "This statement applies to act {A}." (the covers form) |
| statement.device | the sibling device of its class (cold_snare/hot_snare, cold_forceps/hot_forceps, balloon/wire_bougie), in the statement form |
| visit.basis | the other basis |
| visit.separately_identifiable, session.encounter, session.stations, session.reached | the opposite polarity or value |
| session.kind [R:SC-C] | "Session {X} is a {sibling family label}" from SESSION_SIBLINGS: colonoscopy/flex_sig, flex_sig/colonoscopy, egd/eus, eus/egd, ercp/egd, enteroscopy/egd, capsule/egd |
| session.completion / approach / tract | complete against incomplete or terminated / oral against through_stoma or through_pouch / upper against lower |
| session.reached_anatomy | "In session {X} the endoscope did not reach the {point at anatomy Y}." |
| the stations completeness claim [R:SC-B] | "The document says that the ultrasound examination of session {X} covered only some of the esophagus, the stomach and the duodenum." |
| anatomy.type ileal_pouch, gastric_pouch, stoma / organ surgically absent | the sibling type (ileal_pouch/gastric_pouch, stoma/anastomosis) / the negated form |
| anatomy.subtype | the sibling subtype (ileocolic/colocolic, colorectal/coloanal, ileorectal/ileoanal, gastrojejunal/gastroduodenal, esophagojejunal/esophagogastric, hepaticojejunal/choledochoduodenal) |
| lesion.multiplicity | the other value |
| lesion.distinct_from | the same-lesion form ("Lesions {L} and {M} are the same lesion.") |

**Pair controls** [R:SC-B]. Wherever a rule sets two objects apart because their places are disjoint (the pairing target
row; D118's one stricture; bundling identity by place) or their lesions differ, the difference counts only when, for each
place of one object outside the other's places, the pair control "This act was done in the {place}." (or "This statement
is about {kind label}s in the {place}.") on the other object was REJECTED, and likewise "... to lesion {L}." for lesions.
Claims.py generates them, in both directions, for every statement with a single, listed or segment target and every act
of a compatible or sibling kind in its session (in any session, when the statement's session is not stated), and for
every pair of acts of one dilation or stricture class in one session. A short list therefore never sets anything apart:
the omitted place is exactly what the pair control asks. (SC-B's case: biopsies "from the transverse colon and the
rectum" filed with the transverse colon only, beside "No biopsies were taken from the rectum.". The contrast control of
the transverse colon is not the rectum, so the pre-refutation design set the pair apart and made 45380 READY; the pair
control "This act was done in the rectum." is supported, so the pair is UNRESOLVED and the code held.)

**Same-anchor siblings** [R:CO-7]. When two events share an anchor unit, their cards quote each event's own anchor words
(2.4). If the two cards are still identical (identical quotes) while the events' claimed values differ, the differing facts
settle unresolved (`cards_indistinct`, 3.3): no reader can tell which act such a claim is about.

**UNCONTROLLED** (pinned; each attribute decided by a single verdict, for the reason given) [R:SC-C]: `act.date` (L1 checks
it against its own literal, and only the date relation, which is controlled, decides a code); `encounter.date_of_service`
(L1 and the member date's precedence check it; a contrary date has no single natural form); `act.part_of`,
`part_relation`, and `purpose` other than hemostasis (they only bundle or explain, so a yes-bias can only hold);
`statement.covers` (it can only turn INDEPENDENT into UNRESOLVED); lesion `same_as` (it only joins, and joining bundles
or holds). R7 and 3.6(3) cite this list, and P-CONTROLLED keeps it closed.

**Coherence.**

| claim verdict | control verdict | result of the pair |
|---|---|---|
| supports, attached yes, evidence attached (3.2.5) | contradicts | established (an uncontrolled fact: the claim alone decides) |
| supports | supports, qualified or unclear | unresolved (`control_incoherent`) |
| contradicts | contradicts | unresolved (`appraisal_contradicts`); counted as uninformative, not incoherent: both can be false (a planned act is neither "done on the date of service" nor "done before it") [R:HO-4] |
| contradicts | supports, qualified or unclear | unresolved (`appraisal_contradicts`) |
| qualified | any | unresolved (`appraisal_qualified:<q>`) |
| unclear | any | unresolved (`appraisal_unclear`) |
| supports with attached no or unclear, or no evidence attached | any | unresolved (`appraisal_detached`) |
| no verdict for the claim | - | unresolved (`appraisal_missing`) |

**The contrary stays possible** [R:HO-3]. A claim pass 2 did not establish leaves its control's value possible: for
`possibly` (4.2), that value joins the fact's possible values whenever the pair is not established, so pass 2's doubt
about a filing is never discarded.

The CONTROLS generator and its tables are versioned with APPRAISAL_VERSION. They may be narrowed or widened only on
development evidence (9.6), each change a DECISIONS entry, never on acceptance results.

#### 3.2.4 The read [C]

Strict JSON, the schema and the bounds refuse the whole answer, as for pass 1. Item-level findings demote only the claim
they affect: a claim id that is unknown or repeated; a missing verdict; an evidence unit that does not exist (the evidence
is ignored). Each verdict is stored with its claim's content key (template id, subject id, value, unit ids), so a later
re-settle never reads a verdict against a different claim [R:MO-5].

#### 3.2.5 The evidence attachment check (deterministic) [C]

A `supports` verdict counts only if at least one evidence unit is among the claim's cited units, the units of the card's
anchor sentence closure or description, or, for an inherited or placed fact, the governing source's units. For
`contradicts` or `qualified`, the evidence units are stored as COUNTER sources and quoted in the hold question, so the
member sees both statements; the verdict demotes even if no evidence unit locates (fail-closed).

#### 3.2.6 Unlisted statements and appraisal health [C][B][J; revised R:SC-A, HO-6, HO-4]

**Unlisted** [R:SC-A][R:HO-6]. An unlisted entry is dropped only when an event whose anchor or restatement includes one of
its units has the same nature (act, denial or doubt), a compatible kind (equal, or one an umbrella of the other) and, when
pass 2 names a session card, that session. Every other entry is kept. Every dropped entry is recorded in `verification`
and in the measure export with the event that absorbed it, so a statement pass 2 did report is never filed as an omission
neither pass reported. (The pre-refutation rule dropped by unit and nature alone: "The existing biliary stent was removed
and replaced with a new ... stent." with only the placement filed lost pass 2's unlisted removal, and 43274 went READY for
an exchange.) Kept entries are stored as `events.unlisted` `{units, what, kind, session}` and consumed, fail-closed, by
exactly five rules:
1. completeness becomes `incomplete` (`unlisted_statement`);
2. a code whose kept evidence overlaps an unlisted unit is held (`performed_status`, quoting it);
3. an unlisted act with a session card is a synthetic doubted act of that session: it holds the session's base code
   (base_included, as a doubt) and is listed in_doubt (O1, G4) [B];
4. an unlisted denial or doubt pairs UNRESOLVED(statement_scope) with every possibly-positive act of a kind its kind
   covers in its session; with no kind, with every possibly-positive act of its session; with no session, of every
   session (Y7) [J][R:HO-6];
5. in an encounter with an E/M visit, an unlisted act is an undatable possible procedure (C-3: `event_time`).

Unlisted entries never support, exclude or release anything.

**Health** [R:HO-4]. Three measures, each pinned in APPRAISAL_VERSION and set from D3's distributions before the acceptance
run:
- **control acceptance**: the share of controls NOT rejected (any verdict but `contradicts`, or none) over the controlled
  pairs; above 0.5, with at least 4 controls, refuses the appraisal (a yes-sayer);
- **establishment**: the share of non-control claims established; below 0.5, with at least 4 claims, refuses it (a
  no-sayer, a detached or degenerate answer, or a pass 1 so wrong that no page should pose as its assessment);
- **completeness**: claims with no verdict above 10% refuse it.

A refusal is recorded on the appraisal ProviderRun and the stage, never as an EventInventory row [J: C's refused rows
collide with the retry on the unique key], and the stage fails with the retry door (7.5). A degenerate appraisal must not
become a page of held codes that looks like an assessment, and every shape the refutation named is now refused: a yes-man
(control acceptance 1.0), every claim contradicted or qualified (establishment 0), every claim detached (establishment 0).
The pre-refutation measure, `1 - (unclear + incoherent pairs) / claims` refused below 0.5, could see none of them.

### 3.3 Settle: the truth table (`contract/settle.py`) [C, with J; revised R:HO-1, CO-1, HO-9, CO-7, SC-D]

For each fact, in this order:

| # | condition | result | reasons |
|---|---|---|---|
| 1 | the claim state is contradicted and both sides' sources pass I1-I3; or a doubt with basis `conflict` names the fact; or K8 joins a supported and a negated fact of one value | `contradicted` | `contradicted_by_pass1` (never appraised, never dismissed; a side failing integrity gives `unresolved`, still a doubt) [R:HO-9] |
| 2 | a doubt with basis `stated` or `unclear` names the fact | `unknown`, the claimed value and the doubt's readings kept for `possibly` (4.2) | `doubt_stated`, `doubt_unclear` [R:HO-1][R:CO-1] |
| 3 | the slot is empty | `unknown` | `silent` |
| 4 | any of S2, I1-I4, G1-G6, K1-K8 or L1 fails | `unresolved` | the check's reasons |
| 5 | Q1: any qualifier but `approximate` | `unresolved` | `qualified:<q>` |
| 6 | the fact is not in CLAIMED | `unresolved` | `unappraised` [J] |
| 7 | two cards are identical while their events' values differ (3.2.3) | `unresolved` | `cards_indistinct` [R:CO-7] |
| 8 | the appraisal pair is established (3.2.3) | `supported` (claim supported) or `negated` (claim negated) | - |
| 9 | otherwise | `unresolved` | the appraisal reason, with pass 2's counter sources stored and the control's value kept as possible (4.2) [R:HO-3] |

An inherited fact (an effective date relation or performer taken from the containing section or from a placing sentence,
and every act's entry, which is its anchor section's owner, or the documenting clinician through an established
`restates` role, 1.5) is settled per act: steps 1-5 on the section's fact (shared by its acts; a doubt that names the act
itself applies to the act's fact alone), G4 on the edge, and steps 6-9 on the per-act claim [J][R:SC-D]. A contradiction
outranks a doubt, so rows 1 and 2 come first. Then the cross-object rules of 3.1 apply. Every reason is in
`settle.REASONS`, which `store.load` checks.

### 3.4 Disagreement is an unresolved fact; the asymmetry of powers [C]

| actor | can | can never |
|---|---|---|
| pass 1 | claim facts with states and sources; report doubts beside its values, contradictions and qualifications | establish a fact by itself |
| the deterministic checks | demote to unresolved | set, change or create a value, a fact, a support, an exclusion or a contradiction |
| pass 2 | demote to unresolved; add counter sources; leave a contrary value possible by not rejecting a control (4.2); report unlisted statements (fail-closed uses only) | create a fact, change a value, resolve an unknown or a doubt, dismiss a contradiction pass 1 reported, choose between readings, make anything READY, exclude anything |
| settle | combine the above by the table | decide what words mean |
| the engine | decide READY, HELD or EXCLUDED from results and coding rules | read document words (5.7) |
| the reviewer | approve, reject, reinstate | - |

When pass 2 disagrees with pass 1, the fact is unresolved; neither reading wins. The worst pass 2 can do in the READY
direction is miss pass 1's error, which is the single-pass status quo. In the hold direction it can cause unnecessary
holds, which are measured and attributed to their cause (9.1).

### 3.5 What is never done [A][B][C]

On the new path, at interpret, appraise, settle, assess, read time, save, reload, review or export:
- no word list, marker list, frame list, label or signature grammar, route phrase, station word, yield verb or clause
  reader, bleeding word, anastomosis or pouch word, device surface form, landmark surface form or procedure name decides,
  confirms or vetoes anything. The V checks retire too (`landmark_words`, `device_words`, `procedure_words`, the reach
  device guard, `basis_words`): pass 2 judges whether words state a value;
- no deterministic code reads text around a citation to infer meaning: geometry reads offsets, line and paragraph breaks
  and the punctuation that ends a unit, never words;
- no default value; silence is unknown, and inheritance is a stated, checked, appraised edge;
- no literal decides identity, distinctness, time or performer (sizes, distances, specimen labels and names are not
  parsed); a date literal is read only to check a value Gemini gave (L1);
- nothing dismisses a reported contradiction: no literal row, no "hard" difference, no name-token comparison (C-11's
  dismissals retire);
- an unknown target, kind, session, timing, performer or technique is never evidence that two statements are about
  different acts (4.5) [R:HO-5];
- an empty or short list is never evidence of absence: a rule reads a list's completeness only through an established
  completeness claim or rejected pair controls (3.2.3) [R:SC-B];
- no act is moved between sessions by its region or by reach words (D114, D141, D148, D153 retire);
- no word-derived value is persisted in the inventory (v1's `map_events` persisted a catalogue kind derived from words,
  S2 section 4);
- a model's agreement (pass 1 with pass 2, or a participant with either) never approves a code.

**ADJUDICATION on the v2 path** (recorded as a DECISIONS entry in step 0a) [A]: EB1 is kept and narrowed (checks read
offsets, unit boundaries and Gemini's own date words only); EB2 is retired (no frame defaults; inheritance replaces them
and is checked and appraised); EB3 is retired (no marker basis; an exclusion needs an established explicit negative);
EB4 is kept (a residual is measured, and a false READY is repaired in the prompt, the schema, the claim templates or a
coding rule, never with a word list).

### 3.6 Why nothing here is self-certification [C][A][B]

1. **Gemini sets no verification field.** Neither schema has `verified`, a confidence or a certainty. Pass 1's states are
   claims; results are computed by CPT Studio.
2. **One generation cannot vouch for itself.** Support needs a second call with a different instruction and no access to
   pass 1's answer, reasoning, options or doubts; it sees claims only in CPT Studio's neutral sentences.
3. **The check is discriminative, not a stamp.** The second call must reject the generated contrary control on every
   READY- or exclusion-deciding claim, except the attributes of the pinned UNCONTROLLED list, each named with the reason a
   single verdict there can only hold (3.2.3) [R:SC-C]; a verifier that agrees with everything produces incoherent pairs,
   and an appraisal that rejects too few controls, or establishes too few claims, is refused whole (3.2.6) [R:HO-4].
4. **Both answers are source-bound.** A verdict without located evidence attached to the same statement does not count.
5. **The powers are asymmetric.** Pass 2 can only demote; nothing in the chain creates support out of agreement.
6. **The facts are not the decision.** Established facts feed the coding rules; READY means ready for review, and approval
   stays a reviewer's acknowledged act. Neither Gemini, nor two Gemini calls agreeing, nor Corti, Astra or Fable agreeing
   approves anything.

### 3.7 Honest limits (stated, measured, never patched with word lists) [C][A; revised R]

- **The two passes are not statistically independent.** Both are `gemini-4-argon` (pinned, D13). Their instructions,
  information and stance differ; their weights do not. A misreading both calls share passes; controls catch yes-bias, not
  a shared misreading. The residual is measured on the acceptance set's paraphrase and meaning-changing families and
  reported. A different appraisal model is an owner decision (classes a and d), not taken here.
- **Omission is caught only partly.** An act or statement neither pass reports is invisible (the O1 and Y7 residual).
  `unlisted` covers acts, denials and doubts, and an entry is dropped only when an event of the same nature and kind
  already covers its unit, every drop recorded (3.2.6) [R:SC-A]; a missed attribute of a reported act is unknown and
  holds only the codes that require it; a missed member of a list is never read as an absence (pair controls, the
  completeness claim) [R:SC-B].
- **Gemini's doubt habit** [R:CO-1]. The `doubts` channel has the shape Gemini used for its open questions; whether v2's
  pass 1 reports the doubts the documents carry is measured by G-DOUBT (9.2), and a shortfall is a prompt repair. A wrong
  committed value with no doubt is caught only by pass 2.
- **Placing sentences rest on pass 2** [R:CO-2]. A sentence that places an act from outside its part can sit anywhere, so
  geometry cannot filter it; whether it governs THIS act is pass 2's per-act judgement, with its control. Measured on the
  placing cases in D3.
- **Hard wraps** [R:CO-3]. The join rule reads two characters; a wrap whose continuation begins with an uppercase letter
  stays a unit boundary, and the sentence closure carries the earlier unit, and so its negator, to the claim and the card.
  A sentence longer than its 12-unit closure can still be cut; pass 2 reads the paragraph (A2), and the cut is measured.
- **Geometry is a sanity filter, not meaning.** Its errors are fail-closed (a wrong split leaves a fact unresolved), with
  one exception: an over-split citation that geometry accepts. That fact still needs pass 2's attached support of the
  whole sentence.
- **Inheritance moves a judgment from each act to its section.** A section misfiled by Gemini (a wrong start, a wrong
  occasion) is caught per act by the appraisal, as an unnecessary hold rather than a wrong READY; its rate is measured
  (`inherit_unattached` and appraisal causes on inherited facts).
- **A possible statement holds its neighbours** [R:HO-3]. An act whose status pass 2 did not establish pairs as a DOUBT
  with every compatible act it is not set apart from, so appraisal noise on one act's status can hold another act's code.
  Measured as the cause `relation:possible_statement` (G-NOISE, R25).

### 3.8 Survey 1's probes, under v2

| probe | document and filing | v1 | v2 |
|---|---|---|---|
| (a) | "Neither biopsy nor snare polypectomy was performed." filed as a performed snare, words "polypectomy was performed" | performed, current, usable | the claim cites the anchor's sentence closure, the whole sentence with its negator, on hard-wrapped lines too (1.2) [R:CO-3]; pass 2 contradicts "This act was carried out" and supports its control, so the status is unresolved and the event is a possible statement that pairs as a DOUBT with every compatible act, a genuine snare elsewhere in the session included (4.5) [R:HO-3]: held, never READY |
| (b) | "History: polypectomy with a hot snare in the rectum in 2023." with no time words | time default current | the act sits in a history section whose occasion is earlier_date: no support. If Gemini filed the section's occasion from the document frame, K7 makes it unresolved; if it filed the role wrongly too, pass 2 contradicts "done on the date of service" against the sentence; a `date` 2023 fails L1 against on_date_of_service. Never current by default |
| (c) | "No polyps were removed." filed exceptive with words "No" | INDEPENDENT against both snares | K1: exceptive with no excepts makes the breadth unresolved, so the statement pairs UNRESOLVED(statement_scope); the breadth claim's control (the all_of_kind form) is also supported, which is incoherent. Both snare codes held |
| (d) | "The ileocecal valve was seen." filed as an absent organ | derived.absent | pass 2 contradicts "The ileocecal valve is surgically absent."; K4 makes both it and any reach at the valve unresolved. Only class and extent rules read anatomy |
| (e) | an injection worded "was seen", part_of E1 with no citation | kind and status verified; a step relation | part_of with no source fails S2: no step. The kind claim "This act is an injection" is contradicted against "A 7 mm polyp was seen in the sigmoid colon.": unresolved |

---

## 4. The decision engine (`studio/interpretation/engine/`, `cpt-studio-events@2`)

The coding rules of S3 stay. Their inputs move to settled facts, and every [W] input of S3 is replaced by the attribute
named in 1.6. The engine reads results, ids and offsets; document text reaches it only through `wording.quote(span)`, after
the decision, for wording.

### 4.1 Inputs, outputs and the text-free boundary [B][A][J]

```
decide(proposal, R, M) -> Evaluation                 # per code: engine/evaluate.py (pure)
combine(evaluations, counted, R, M, Ref) -> ...      # set level: engine/combination.py (base, base-within, competition,
                                                     #   same-day E/M, D105)
proposal = (code, origin, proposed_by, kept evidence as integer spans, R1's results)
R        = the FactSet of the settled inventory (engine/facts.py): enumeration values, ids, results, spans; no text
M        = member context (setting, patient status, billing context, member date) and member answers
Ref      = the reference rows for the date (PFS, MUE): records only (R9)
```

- **The boundary is typed.** `engine/facts.py` builds the FactSet from the stored row and strips every `text`. Its
  accessors return `Fact(result, value: Enum | Id, state, options, reasons, spans)`; none returns a document string [B].
- **The rules are v1's, forked.** v1's coding-rule bodies (`events.py`, `coverage.py`, `classes.py`, `ercp.py`,
  `combination.py`, `assess.py`) are copied into `engine/`, their readers deleted, their inputs rewired. They call
  `engine/reading.py`, a Reading-compatible accessor layer that keeps v1's names (`usable` is "result supported", `value`
  is the claimed value in any state, `done`, `own_spans`, `anchors`, the label ids), so a rule body changes only where it
  read words [A][J]. The v1 originals stay where they are, denied (5.0). Why a fork and not a rewrite: those bodies hold
  177 decisions of fail-closed arms (D62, D74, D87, D104, D163, D167, D177); a clean-room port is where such arms get lost
  (C's R11, B's R13). B's guarantees are kept as properties that run over the fork (9.4).
- **R1 is the one integrity use of the text in assessment.** `engine/assess.py` runs `checks.code_scope` and
  `checks.exact_evidence` (the allowlisted validation checks, FINAL 7.1) with the revision text, before the per-code rule:
  the proposer's quote must be the document's own text. Member answers' passages bind the same way. The text goes no
  further: the per-code rule, the combination, coverage and questions never receive it.

### 4.2 Reading results (`engine/facts.py`) [C][B; revised R:HO-1, HO-3, HO-5, SC-B]

- `holds(f, v)`: result `supported` and `value == v`.
- `denied(f, v)`: result `negated` and `value == v`.
- `established(f)`: result in {supported, negated}.
- `possibly(f, v)`: `holds(f, v)`; or the result is `unresolved`, `contradicted` or `unknown`, and `v` is the claimed
  value, one of the options, one of a doubt's readings, the value of a control pass 2 did not reject, or the fact is
  silent. Two attributes widen it [R:HO-1][R:HO-3][R:HO-5]:
  - a STATUS that is not established leaves every status possible: a doubt about whether an act was done is a doubt about
    its performance and about its denial alike, so the act is a possibly-positive candidate and a possible statement at
    once;
  - a KIND that is not established, on a statement (4.5) or when an exclusion asks whether anything doubts a code's kinds
    (4.6, condition 5), leaves every kind of its session's family possible (every kind, when the session is not
    established either). As a candidate for a code (4.4), an act's unestablished kind is possible only as its claimed
    value, its readings and its control's sibling, so one noisy kind claim does not make an act a candidate for every code
    of its family.

  **This is the fail-closed doubt arm.** S3's "in any state" inputs (D62, D74, D87, D104, D163, D167, D177) read it, so a
  doubt never becomes an absence and never releases a rival. The pre-refutation definition read a stated doubt's empty
  value and empty options as "not possible", so the most explicit doubt the design defined vanished (HO-1).
- `apart_by_lesion(a, b)`: both lesions established and different, `distinct_from` established between them, and the
  lesion pair controls (3.2.3) rejected [R:SC-B].
- `apart_by_place(a, b)`: both place sets established and disjoint on the anatomy chain (`engine/anatomy.py`), and every
  pair control asking one object about a place of the other rejected (3.2.3) [R:SC-B]. A short list never sets anything
  apart: the omitted place is exactly what a pair control asks.
- `effective(inventory, effective_date)`: L1 re-judged on timing facts from the stored literals, with no text; called
  identically by assess and by the overlay, which removes S3's hazard 5 (the read-time path skipped the re-judge).

**The truth of a requirement** (the specification, B's Kleene view): T when its facts hold the needed values; F when a fact
is established with another value (or negated where the negation decides); U otherwise (unknown, unresolved,
contradicted). A U or an F carries a witness `(subject, attribute, result, reason)`. In the forked rules each witness is a
`HeldFact` (4.8). The specification is enforced by P-MONO (weakening a fact never turns HELD into READY or EXCLUDED, never
shrinks a claim) and P-INDEP (9.4).

### 4.3 Each code's required facts [B][C][A]

**SUPPORT(E, C, g): act E supports requirement group g of code C** when every fact below is supported with the value shown:

| # | requirement | replaces (v1) |
|---|---|---|
| 1 | `kind` covers g; a positive umbrella (`removal`, `intervention`) never supports a method-specific code; an examination kind is the session (C-1) | 7.3 |
| 2 | `status` performed; for a base or exam-only code also attempted_not_completed. Attempted on any other code is a hold with the 52/53 consideration (C-9) | 7.3, C-9 |
| 3 | effective `date_relation` on_date_of_service | the EB2 default; facts.day_of |
| 4 | effective `performer` documenting_team | the EB2 default; performer_words |
| 5 | `entry(E)` documenting_clinician (1.5) | the D124 label grammar |
| 6 | `session` X with X.kind the code's family (route a); route (b): E's supported places in the code's regions, at least one | the procedure attribute; coding_family's region moves |
| 7 | the session is done: its examination, when it has one, passes 2-5 (an act-only session: the act itself) [A]. Another act's own performer or date never touches the examination (K2) [R:HO-7] | D31's session doubt |
| 8 | no CONTRADICTION, DOUBT or UNRESOLVED relation on E (4.5), from an established, doubted or possible statement alike [R:HO-3], no unlisted statement pairing with it, and no contradicted fact among 1-7 | the blocking relations |

Requirement 3 accepts any act on the date of service. A procedure the documenting team did on the date of service and
documents here supports its code even when it was a separate encounter that day (T2's 45330 is READY on c2e53f8e); its own
session and R6 facts apply. This is a recorded parity choice (4.13), changeable only by a coding rule.

For an E/M code, the visit's session must also have `encounter` supported this_encounter: the visit billed is the
encounter this document records (unmet: `event_time`) [B's V.this_encounter, J].

**The code-specific requirements** (each a coding rule that stays; Appendix A gives every catalogue code's tags):

| tag | codes | met when | unmet -> fact | established otherwise -> |
|---|---|---|---|---|
| ATT | base and exam-only EUS codes | attempted_not_completed accepted for the examination | - | state incomplete; 52/53 consideration |
| R6:extent | egd, enteroscopy, flex_sig | a reached point supported (the endoscope's, by definition, P19; `stated_depth` counts), or completion supported incomplete or terminated [R:CO-8] | `extent` | - |
| COLFULL | every gi.colonoscopy code | reached supported at a FULL_REACH landmark (cecum, appendiceal orifice, ileocecal valve, terminal ileum, ileum, neo-terminal ileum, small bowel), which is the endoscope's reach (a point also in `device_reached` is unresolved, K6); or reached_anatomy Y supported with Y's subtype ileocolic (D38, D44, D57, D63) [R:CO-8] | `extent` | completion incomplete: 52/53 |
| R6:target | eus | the examination's or a supporting act's places supported | `target` | - |
| R6:cannulation | ercp | a cannulation of the session with status, access_outcome and duct supported | `cannulation` | failed: the D107 warn and 52/53; achieved_after_failed_attempts: a sequence, no conflict, no 52/53 |
| R6:em_basis | office_em | `visit.basis` supported | `em_basis` | - |
| R6:context | office_em | member-entered setting and patient status (D3: never read from the document) | `setting` (its text names patient status too when both are missing), else `patient_status` | - |
| DEF:k | the D27 narrowed codes: 44365, 43232, 43238, 43242, 43253, 43240, 45342, 45392, 44407, 43265, 49440 | a supporting act of the defining kind | as SUPPORT | - |
| TECH:c | balloon: 43214, 43220, 43233, 43249, 43277, 44381, 44405, 45340, 45386; wire_bougie: 43226, 43248 | `technique.device` supported in the class | `technique` | another class: held `another_technique` (explanation) |
| SITE:s | esophageal: 43213, 43214, 43220, 43226, 43233, 43248, 43249; gastric or duodenal: 43245 | every supported place of the act and its supported lesion within the class, at least one | `act_target` | outside: held `another_site` (explanation) |
| STRUCT:pfc | 43240 | `target.structure` supported pancreatic_fluid_collection, and no supported place biliary or hepatic (D120, D136, D145) | `target` | another structure: held (explanation) |
| ROUTE | 43253 | `technique.route` supported eus_transmural (D171(4), D177(2)) | `technique` | submucosal: held, never READY on a wall injection (G1) |
| TRACT | the upper EUS codes (43231, 43232, 43237, 43238, 43240, 43242, 43253, 43259); the lower EUS codes | the session's `tract` supported upper (lower for 45341-45392 and 44406-44407) (D171(2)) | `procedure` | the other tract: held; base questions name only same-tract codes (D177(1)) |
| STATIONS | 43242, 43259 (full) | esophagus, stomach and duodenum each supported examined and reached at or beyond the duodenum; or the stations list empty, the completeness claim established (3.2.2), and reached supported at or beyond the duodenum [A][R:SC-B]. Pass 1's empty list alone is never evidence: BF6 filed with an empty list is held | `exam_stations` | a station negated: held (the class explanation) |
| LIMITED | 43231, 43232 (esophagoscopic); 43237, 43238 | 43231, 43232: reached short of the duodenum; 43237, 43238: a station established negated, or reached short (D28, D171(3)) [J: the row's columns repaired] | `exam_stations` | all three examined: held (class) |
| LOWER | 45341/45342, 45391/45392, 44406/44407 (D43) | reached in the class reach; the stoma codes also an anatomy entry of type stoma supported and approach through_stoma | `extent` | misfit: held (class) |
| ENT | 44360-44373 jejunal; 44376-44379 ileal; 44380-44384 stoma; 44385-44386 pouch (D108, D114) | approach supported (oral for jejunal and ileal; through_stoma with a stoma entry; through_pouch with an ileal_pouch entry, never a gastric pouch or a Roux limb) and reached in the class reach; for the deeper classes, completion not incomplete | `procedure` (approach) or `extent` | misfit: held, one item naming both doubts (D89) |
| YIELD | 43264 | `yield` supported in {stones, stone_fragments, sludge, debris} on the supporting act (D106) | `act_yield` | negated: no support from that act (explanation "documented as retrieving nothing"); contradicted: `conflict:stone_extraction` |
| XCHG | 43274, 43275, 43276 (D105, D127) | 43276: a stent removal and a stent placement each supporting, in one duct (duct supported and equal), or a stent_exchange act supporting; 43274 or 43275: no possibly-performed counterpart in the same or an unknown duct | `act_target` (duct) or `performed_status` | the removal negated: 43276 not supported, 43274 can be READY (X1) |
| CAUSE | every code covering bleeding_control | purpose supported hemostasis, and cause supported pre_existing_lesion, spontaneous or earlier_procedure | `act_cause` | cause act_of_this_session: bundled as a procedural adjunct (explanation); purpose prophylaxis: not a bleeding control (COMMON_BUNDLED's clip rule) |
| C3+SEP | office_em | the same-day rule (4.7) | `event_time` (undatable) or `separate_em` | separately_identifiable denied: `separate_em`, the denial quoted |
| ADDON | 43273, 91013, 99153, 99417 | its primary counted | as today | - |
| D80 | 99152, 99153 | never | `performed_status` (recognised_only) | - |
| route (d) | unprofiled codes, another family | never READY (C-6) | `performed_status` (unprofiled) | - |
| bundling | every code (4.7) | part_of and part_relation, cause and cause_event, lesion identity, duct; the whole's status and timing read by `possibly` | `act_part`, or `act_target` (bundling identity) | bundled: held (explanation naming the whole) |
| combination | as v1 (4.7) | base, base-within, competing over facts | `base_included`, `competing_codes` | - |
| R7, R9 | every code | the date of service known (document or member); the references are records | encounter-scope date question | - |

A code's REQUIRED facts are exactly these, over its E* acts, their session, the statements paired with its candidates
(4.5), the doubts that name their facts, the unlisted statements that touch them (3.2.6) and the encounter's date. Nothing
else can hold it (4.9).

### 4.4 The outcome function (`engine/evaluate.py`, assembled in `engine/assess.py`) [A][C][B; revised R:HO-1, HO-8, MO-2]

```python
def decide(code, kept, R) -> Evaluation:                   # pure; reads facts and offsets only
    link = catalogue.code_link(code)
    if not link.linked or not catalogue.requirements(link):  return held('unprofiled')            # C-6
    if catalogue.recognised_only(link):                       return held('recognised_only')       # D80
    supporting, held_facts, bindings = [], [], {}
    for group in catalogue.requirements(link):                                                     # C-1
        cands = [E for E in R.events if candidate(link, group, E)]   # possibly(kind) in the group; not denied(status, performed)
        found = [E for E in cands if support(code, link, group, E, R).all_true]
        if found:
            supporting += found
            continue
        positive = [E for E in cands if possibly(E.status, 'performed') or possibly(E.status, 'attempted_not_completed')
                    if not established_other_date(E) and not established_other_performer(E)]
        if positive:                                                      # 7.4: possibly today's act, in doubt
            for E in positive:                                            # EVERY candidate's witnesses [R:HO-8]
                held_facts += support(code, link, group, E, R).witnesses
            bindings[group] = choose(code, kept, positive, R)             # 4.8: by rank across the candidates
            continue
        ex = exclusion(code, link, group, cands, kept, R)                 # 7.5 (4.6)
        if ex.excluded:  return excluded(ex)                              # reinstatable
        held_facts.append(ex.item or not_documented(group))               # statement_scope (C-7) or 7.6
    held_facts += code_requirements(code, link, supporting, R)            # 4.3's code-specific rows
    held_facts += bundling(code, supporting, R)                           # 4.7
    return Evaluation(supporting, held_facts, bindings)
```

- Every hold carries ALL its unresolved facts, over EVERY positive candidate of its groups, not only the act its item
  names [R:HO-8]: there is no early return before the code-specific rules (Q2), and a contradiction on a candidate the item
  does not name is still in `held_facts`, so 9.1 never counts it as a dropped question.
- A doubted act, and an act whose status pass 2 did not establish, is a positive candidate, because `possibly` leaves every
  status open for it (4.2) [R:HO-1]. HO-1's document A ("It is unclear whether the polyp was removed with the cold
  snare.") therefore binds 45385's item at rank 2 and holds 45378 as base_included, as v1 does (`events.py` 1213 counts
  `uncertain` as positive), and its office note ("A flexible sigmoidoscopy may have been performed in the office today")
  holds 99214 on the same-day rule.
- `engine/assess.py` then appends the R6 facts, the class and code checks, the combination holds (base, base-within,
  competing, separate_em, event_time) and R7, ranks the whole list (4.8) and sets the status: `excluded` (R1, 7.5, or a
  member's answer); `needs_clarification` (any held fact, or the date of service unknown); else `ready`, with the
  considerations (52/53, 25, 59/XS, PC/TC) and the R9 records.
- `HeldFact` = `{fact (a questions.FORM key), attribute, subject (event, session or lesion), kind: question | explanation,
  cause, reason, spans, rank}`, where `cause` is one of `reading_unknown`, `reading_contradicted`,
  `unestablished:<reason>`, `appraisal:<verdict or coherence>`, `relation:<type>`, `unlisted`, `coding_rule:<id>`,
  `context_missing`, `date_unknown` [A][R:MO-2]. The cause gives every hold an owner in measurement (9.1). Causes name no
  vendor and are operator data: no customer string carries one (4.12).

### 4.5 Statements against acts: the pairing table (`engine/pairing.py`) [C][B][A][J; revised R:HO-2, HO-3, HO-5, SC-B]

**Which pairs.** A statement D is an event whose status is established negated; or whose status is NOT established, by a
doubt, a contradiction, a failed check or an appraisal that did not establish it (a POSSIBLE statement: the reading that
it was not done is open, 4.2) [R:HO-1][R:HO-3]; or whose date relation or performer is established as another. D is
paired with every other event A for which `possibly(A.status, performed)` and whose kind is compatible with D's: possibly
equal (4.2, so a statement whose kind is not established is compatible with every kind of its session's family
[R:HO-5]), a tattoo with an injection, or an umbrella covering it. `claimed` means D's `covers` names A.

**The rows.** Every row is evaluated, and none decides alone [R:HO-2].

| row | INDEPENDENT when (established facts; the row's precondition first) | UNRESOLVED(attribute) when | SAME when |
|---|---|---|---|
| session (C-8) | both sessions established and different | either not established while two or more sessions of a compatible family exist | otherwise |
| timing | both effective date relations established and different | either not established | both established and equal |
| performer | (D's own statement names a performer) both established and of different classes; or both other_clinician with different established persons | D names a performer and either side's is not established; or both other_clinician with no established persons | **D's own statement names no performer: a general denial covers any performer** (a performer D would only inherit from its section never narrows it) [B; corrects C]; or both established and equal |
| breadth | D's breadth established exceptive and A among its established excepts [A] | D's breadth not established; or exceptive with A not excepted while A's status is established (a "no other" against an act it does not except) | all_of_kind within D's session; single, listed or segment (the target row decides) |
| target | (D's breadth established single, listed or segment; for a possible statement, its own established target read as a single target) `apart_by_lesion(D, A)` or `apart_by_place(D, A)`, the pair controls rejected (4.2) [R:SC-B] | either side's lesion or places not established; a pair control not rejected. **An unknown target never proves independence** | same lesion, or places overlapping (containment) |
| technique (C-16) | (D names a device, established) A's device established and different | D names a device and either side's is not established | D names no device; or the same device |

**The pair's relation:**
1. INDEPENDENT when at least ONE row proves it. One established difference (of session, date, performer class, exception,
   target or device) means that D does not concern A, whatever else is unknown. If the pair is `claimed`, the relation is
   UNRESOLVED(statement_scope) instead: Gemini says D applies to A while the facts say apart, and that disagreement is
   never resolved [C].
2. Otherwise, UNRESOLVED(the attribute of the first unresolved row, in the order above) when any row is unresolved. For a
   possible statement, an UNRESOLVED relation asks `statement_scope`, quoting both statements ("Does 'Neither biopsy nor
   snare polypectomy was performed.' refer to the polyp removed with the cold snare?").
3. Otherwise (every row SAME): CONTRADICTION when D's negated status and A's performed status are both established; DOUBT
   otherwise (D doubted or possible, or A's status not established).

**Why every row is evaluated** [R:HO-2]. Under the pre-refutation rule, "the first row that returns decides", an
unestablished timing on D stopped the target row from ever setting apart a denial of another lesion, and every denial's
timing was claimed with an act's sentence ("This act was done on a date before the date of service."), which a faithful
pass 2 must reject for an act that was not done. Together they held every act beside every compatible denial. The v3
development document ("At the 2024 colonoscopy the anastomosis was narrowed, but no dilation was performed." beside
today's dilation) held 45386, which v1 sets apart by time; a screening report with "No prior colonoscopy." held its only
code; and "No other injection was given." held the very injection it excepts (BF17). With statement-phrased claims
(3.2.2) a denial's session and timing can be established, and with every row evaluated one established difference
suffices. Neither change lets an unknown count as a difference.

**A possible statement's scope** [R:HO-3]. An act-filed event whose status pass 2 did not establish has no breadth. Its own
place and lesion facts, when established by act-phrased claims, stand for a single target without pair controls: pass 2's
support of "This act was done in the {place}" already says where the act, if done, was done, and an act's sentence denies
nothing elsewhere. When they are not established (a denial misfiled as an act gets its act-phrased place claims rejected
too), nothing sets it apart, so it holds every compatible act of its session. S1's probe (a) beside a genuine snare ("A 6 mm
sessile polyp in the sigmoid colon was removed with a cold snare. Neither biopsy nor snare polypectomy was performed.",
the denial filed as a performed snare and caught by pass 2) is held, never READY. Under the pre-refutation rule only an
established negated status made a statement, so the caught misfiling dropped out of every pair and 45385 went READY.

- A CONTRADICTION or a DOUBT makes A unsupported (4.3 row 8) and asks h1 (`conflict:<kind>`) or h2 (`performed_status`),
  quoting both statements. An UNRESOLVED(attribute) asks that attribute, or `statement_scope` (h3).
- A fact pass 1 reported `contradicted`, a doubt with basis `conflict`, and a K8 polarity pair are contradictions on their
  attribute (h1). An unlisted denial or doubt pairs UNRESOLVED(statement_scope) (3.2.6 rule 4).
- Nothing dismisses a contradiction: no literal row, no name comparison, no place adjacency (C-11's dismissals and
  D58/D77 retire).

### 4.6 Exclusion: the only path to EXCLUDED besides R1 and member answers [C][A][B]

A code with no supporting act and no positive candidate is EXCLUDED (reinstatable) by a statement D only when all of these
hold:
1. **D concerns the code:** D's kind covers a requirement group (or umbrella); D's session supported and of the code's
   family (route b: D's places in the code's regions).
2. **D's deciding fact is ESTABLISHED** (appraised, control rejected): status negated performed, or planned; or its date
   relation earlier_date or later_date (**never on the date of service, never unknown**: T2); or its performer
   other_clinician or other_facility. An attempted status never decides (C-9). There is no marker, negator, date-literal or
   titled-name basis: EB3 and `verify.exclusion_basis` retire.
3. **D is not exceptive:** for a denial, its breadth is established and is not exceptive; an unestablished breadth is no
   exclusion (C-7). A statement of another date, another performer or a plan carries no breadth (K1). D's date relation and
   performer here are its effective ones (1.5): an act told in a part whose occasion is earlier_date, or whose performer
   is another clinician ("All of the above was done by her previous surgeon."), is such a statement.
4. **The code covers D by citation** (C-10, kept as geometry over offsets): a kept span overlaps D's anchor, and every kept
   span lies within D's `kind_words` and `status_words` spans plus its statement-linked target and timing words. A partial
   cover gives `statement_scope`.
5. **Nothing doubts the kinds:** no candidate of the code's kinds is possibly today's act (possibly performed, possibly on
   the date of service, possibly by the documenting team; a doubted act and one whose status pass 2 did not establish are
   possibly performed, 4.2 [R:HO-1]); no DOUBT relation; no unlisted denial or doubt of those kinds; and no act of the
   kind is a possible bleeding control in doubt (D157(2), from facts).

A broad statement (status negated, breadth all_of_kind, its session supported, its date relation on_date_of_service, each
claimed in the statement form, 3.2.2 [R:HO-2]) that the code does not cite gives `statement_scope`, never an exclusion
(C-7). A negated statement of the code's kinds whose session or date relation is not established (possibly this session,
possibly today) also gives `statement_scope`, never `not_documented`, so a broad denial is never dropped.

### 4.7 The coding relations that stay, forked and rewired [A][B][C]

| rule | stays as | v2 inputs | gone |
|---|---|---|---|
| sessions (S3 6.2) | `engine/coverage.sessions` from the sessions table | `session.kind`, the examination's facts (done = 4.3 rows 2-5), `part_of_session`; possible sessions (D62) by `possibly` | coding_family's region moves (D114, D141, D148, D153), eus_places |
| reportable / doubted | v1's shapes | reportable: done, status performed, kind of the family's catalogue acts, not bundled; doubted: possibly positive (a doubted status and one pass 2 did not establish included, 4.2 [R:HO-1]) with any required fact not supported, or a relation, or an unlisted act of the session (3.2.6) | D115's word-derived possible control (now from purpose and cause) |
| bundling (7.7, COMMON_BUNDLED) | v1's rules | NOT_REPORTED (clip, cannulation); a family's bundled kinds; lift_injection (part_relation lift_for or step_of to an EMR or ESD, or purpose lift_for_resection on the same lesion); resection_technique; stent_included (D45: same duct); procedural adjunct (D30, D79: part_relation adjunct_of, or cause act_of_this_session with cause_event); biopsy_of_removed_lesion (C-2: same lesion, single, or the same anchor unit); drainage_step (G3: part_relation access_for or step_of to the drainage, or the same lesion); the whole read by `possibly` | D41's lexical identity; D58/D77 place adjacency |
| bundling identity | asked | `same_as` / `distinct_from`, supported places | literal distinctness (sizes, distances, specimen labels) |
| base_included (FINAL 7.9, D119, D177(1)) | unchanged structure | sessions; reportable and doubted acts | - |
| base_within (C3, C-4, D70) | unchanged | `part_of_session` supported (C3); C-4 structural over supported session kinds and tracts (a done EGD beside a done upper EUS on the date); possibly_part_of by `possibly` | eus_places' word reading |
| competing (D40, D55, D74, D104, D118, D163, D167) | unchanged; a held code keeps its claims | claims over E* and over acts read by `possibly`; D118's one stricture by same lesion or places not disjoint; the D29 site fit | - |
| same-day E/M (C-3; D81, D94, D109, D111, D130, D133, D134) | unchanged rule | procedure day: any act of a procedural family, a SAME_DAY_KIND, or other_class procedure, possibly positive (a doubted act included [R:HO-1]), with its effective date relation supported on_date_of_service. An act possibly positive whose date relation is not established, or an unlisted act, is undatable (`event_time`). The visit's own session encounter must be supported this_encounter. **The performer is not read** (legacy parity; S3 hazard 7) | facts.day_of and its frames; _stated_procedure's head words |
| separate statement (D113) | the rule | `visit.separately_identifiable` supported = a statement; negated = a denial (quoted); otherwise none | the negator re-read |
| modifier review (59/XS) | consideration only | `target.lesion` supported and `distinct_from` supported | literal distinctness |
| 52/53 (D61, D71, D107, C-9) | consideration only | completion incomplete or terminated; status attempted supported; access_outcome failed | - |
| read-under (S3 2.3) | unchanged | kind, session family, places | - |
| ERCP D105, D107, D127 | the rules | stent components and ducts; the cannulation's access_outcome | the D127 conflict shim; _named_only_apart (its principle is the anchor rule: a title is never a statement) |
| EUS checks (D28, D43, D171, D177) | the rules | tract, stations, reached, route, structure, part_of (drainage step) | _stated_stations, _lower_place's word reading, submucosal_act, wall_place |
| enteroscopy classes, act_elsewhere (D108, D114) | the rules | approach, through, anatomy types, reached, completion; act_elsewhere becomes the act's own session fact | route phrases, pouch words, gastric_beside, beyond_reach |
| reconcile, completeness, event_coding, service questions (S3 6.3) | unchanged shapes, `cpt-studio-events@2` | results; `unlisted` makes completeness incomplete | - |
| R7, R9 | unchanged | date of service; PFS and MUE rows | - |
| the routing stand-in, the derived context (`facts.derive`) | `engine/derive.py` [J] | the date of service, member values, date relations | day_of |

### 4.8 The one-question policy [A][B][C]

**One clarification per held code.** Each held code carries exactly ONE clarification: the item of its highest-ranked
non-T requirement on its chosen binding. It is a QUESTION when that requirement is unresolved (U) and an EXPLANATION when
an established fact fails it (F: "documented only in the anesthesia entry"; "documented with a guide-wire dilator";
"documented as retrieving nothing"; "part of the resection") [B]. The other non-T requirements are recorded in
`support.held_facts`, ranked, each with its cause, over every positive candidate [R:HO-8]: visible to the operator with
their causes, and to the reviewer only as CPT Studio's fixed sentence per fact key, never a cause [R:MO-2]; never asked as
separate questions, and re-evaluated after an answer or an addendum [A][C].

**RANK** (fixed and pinned in `engine/requirements.py`; the first four keep v1's h1-h4 order) [A][C][J]:

| rank | fact key | what |
|---|---|---|
| 1 | `conflict:<kind>` | a contradicted required fact (a doubt with basis conflict and a K8 polarity pair included), or a CONTRADICTION relation on the deciding act (h1). Ranked first so a contradicted act is never bundled out of its question (D3) |
| 2 | `performed_status` | a doubt: a DOUBT relation (from a doubted or possible statement), a doubt pass 1 reported on status (basis stated or unclear), an unlisted denial or doubt of its kind, an unlisted unit on its evidence (h2) [R:HO-1][R:HO-3] |
| 3 | `statement_scope` | an UNRESOLVED relation on breadth, target or covers; a broad denial the code does not cite (h3) |
| 4 | `performed_status` | status not established; attempted on a non-examination code (C-9); not documented |
| 5 | `event_entry` (new) | whose entry the act is told in: another role (F) or not established (U) |
| 6 | `event_time` | the date relation not established; an undatable act beside an E/M |
| 7 | `event_performer` | |
| 8 | `procedure` | the session not established; tract or approach for a class |
| 9 | `act_method` | a positive umbrella beside a method-specific code (h5) |
| 10 | `technique` | technique class; EUS route |
| 11 | `act_target` | site class, region (route b), duct |
| 12 | `target` | the EUS target (R6); 43240's structure |
| 13 | `exam_stations` (new) | full and limited EUS stations |
| 14 | `extent` | R6 extent, the colonoscopy reach, the class reach, completion |
| 15 | `act_yield` (new) | 43264 |
| 16 | `cannulation` | R6 ERCP access |
| 17 | `act_part` (new), `act_cause` (new), `act_target` (bundling identity) | a bundling that depends on an unresolved fact |
| 18 | `performed_status` (bundled) | an explanation naming the whole act |
| 19 | `em_basis` | |
| 20 | `separate_em` (key-bound) | |
| 21 | `base_included` (key-bound) | |
| 22 | `competing_codes` | |
| 23 | `setting`, `patient_status` | member context (D3) |
| - | `service_date` | encounter scope, as today; it blocks the reviewed report |

Facts are what the document must settle, so they come before coding relations (bundled, base, competing), which a fact may
make moot; member context comes last.

**The binding** (which act, and so which act the item names) [C][A][B][R:HO-8]: among the positive candidates, (1) those
whose anchor the code's kept spans overlap, when any does; (2) then the candidate whose top item ranks highest (a
contradiction on any of them is asked before anything else, as v1's `_focused` asks h1 across every candidate); (3) then
the fewest non-T requirements (closest to READY); (4) at an equal rank, an unresolved requirement (a question) before an
established failure (an explanation), because an explanation can never become T; (5) then document order. Never simply
the first act in reading order (Q1). Every candidate's witnesses are in `held_facts`, whichever is bound. A hold never
lowers what a code claims: claims read acts by `possibly`, never a held code's state (Q3, D163, D167 kept). HO-8's two
cases are fixtures: a contradicted date on the act the item does not name stays in `held_facts` (and is asked when no kept
span selects the other act), and of two dilations under 43249, the esophageal one with an unstated device is asked about
its device before the duodenal one with a balloon is explained.

**Read time.** `overlay.review_view` recomputes the base and competing holds over the counted set, as v1 does, inserts them
into `held_facts` at their rank, and presents the first live item; a released item gives way to the next [A].

**Service questions** (scope `service`; they hold nothing): one per (session, fact) for an in-doubt act no counted code
reads (in_doubt_questions) and per done session with no extent that no code asks (D125). Each names its act or session,
chosen by the binding rule. They are de-duplicated against the codes' items by (act or session, fact), and a code's item
never displaces another code's (D89).

**Member answers** are unchanged: the only values are "Not documented" and "Cannot confirm"; an answer excludes the code
whose item it answers; no answer confirms a fact or releases a hold (D7). v2 items have new fingerprints, so pre-v2 answers
are `asked_differently`, except the key-bound facts (`base_included`, `separate_em`), which bind by key
(`questions.bind`).

**The five new facts** `event_entry`, `exam_stations`, `act_yield`, `act_cause` and `act_part` join `wording.NEW_FACTS` with
their MISSING sentences ("whose entry the act is told in", "which parts of the upper tract were examined", "what the
extraction retrieved", "what caused the bleeding the act treated", "whether the act was part of another act"). That is
the path v1 already uses for its seven new facts, and `customer_api` already reads `wording.MISSING` [C].

### 4.9 How unrelated codes proceed [B][C]

A code's outcome is a function of its **requirement closure** alone: its candidates' and E* acts' facts; their session and
the anatomy its class reads; the statements paired with its candidates and the unlisted statements touching them; its
acts' lesions; for an E/M, its visit and every act the same-day rule reads; the claims of the counted codes it can compete
with; the encounter's date of service and member context. `engine/requirements.dependencies(code)` computes it.

The only couplings between codes are the coding relations themselves: base (a base code beside its session's acts),
competition (two codes on one act), the same-day E/M, the exchange, and the date of service. There is no global "anything
unresolved holds everything": D31's session doubt is replaced by the session facts each code requires.

**P-INDEP** (9.4): perturbing any fact outside a code's closure leaves its status, its item and its held facts unchanged.
A dilation whose device is unknown holds 43249 and nothing else; 43239's biopsy stands.

**P-INDEP-SETTLE** (9.4) [R:HO-7] runs the same perturbation from constructed pass-1 and pass-2 answers through settle, so
a coupling made before the FactSet exists is visible: perturbing one object's fact changes another object's facts only
through the listed cross-object rules (an invalid anchor, a section's owner, occasion and performer, a session's kind, a
doubt naming several objects). The pre-refutation K2 let one act's other performer unresolve its session's examination,
and so hold every code of the session (a surgeon called in to place clips held the endoscopist's 45385 and 45378); P-INDEP,
which starts from the FactSet, could not see it.

### 4.10 Broad denials and genuine contradictions [B][C]

- **A broad denial** ("No polyp was removed today.") is a statement: kind removal (an umbrella), status negated performed,
  breadth all_of_kind, its session supported, its date relation on the date of service, no performer stated.
  - Against a positive snare of that session, every row of 4.5 is SAME (a general denial covers any performer), so the
    relation is a CONTRADICTION and the snare's code is held `conflict:snare`, quoting both statements.
  - With no positive act and the code citing the denial: EXCLUDED, reinstatable (4.6).
  - Not cited: held `statement_scope` (C-7).
  - It is never neutralised: an exceptive filing without excepts is unresolved (K1); its breadth claim has a control; an
    unknown breadth pairs UNRESOLVED, never INDEPENDENT.
- **Genuine contradictions** come in three forms, all preserved and none dismissed: an attribute stated two ways
  (`contradicted`), a statement covering an act (4.5), and pass 2's counter-evidence on a claim (an unresolved fact whose
  question quotes both statements). Each holds only the codes whose required facts it touches.
- **Different targets, techniques, times and performers** do not contradict when ONE of them is established on both sides
  and different (4.5: one established difference suffices) [R:HO-2]; an unknown side is never a difference, and with no
  established difference the pair is UNRESOLVED.

### 4.11 An unknown target [B]

The target row returns UNRESOLVED whenever either side's lesion or places are unknown, unresolved, doubted or
contradicted, or a pair control was not rejected: an omitted place is as unknown as a missing one [R:SC-B]. With no other
row's established difference, the code is held with `statement_scope`:

> Does "No polyp was removed from the rectum." refer to the polyp removed with the cold snare?

An unknown target never proves INDEPENDENT; only another row's established difference can (4.5). In bundling, competition,
the modifier review and the adjunct rule, an unknown identity never sets two acts apart, and a place difference counts only
with its pair controls rejected. Missing identifiers manufacture neither a match nor a non-match (2026-11-09 checklist).

### 4.12 Participants, approval and confidentiality (unchanged) [A][B][C]

- Corti's selected codes, Astra's and Fable's admitted first readings (P-ADMIT, I3) and the second review (D10) all go
  through the one outcome function; no readiness rule reads a code's origin.
- Agreement adds names to `support.proposed_by` and nothing else; `test_agreement_adds_proposers_and_nothing_else` stays and
  gains a v2 fixture. Disagreement is a warn.
- Two Gemini calls agreeing is model agreement about a FACT; it never approves a code. A code still needs every coding rule,
  and approval stays a reviewer's acknowledged act, offered only on READY with exact evidence (`review._actions`,
  `review._record_decision`). Nothing auto-approves.
- Provider and model names stay operator fields. The customer surface translates CPT Studio's sentences (`customer_api`) and
  shows no support details. `held_facts` causes are operator data and name no vendor (`reading_unknown`,
  `reading_contradicted`); a reviewer, a customer workspace member, sees each held fact only as CPT Studio's fixed sentence
  for its fact key [R:MO-2]. Progress steps name functions, never vendors: pass 1 is "Reading the documented procedures"
  (existing), pass 2 "Checking the reading against the document" (new, `progress.DETAILS['appraise']`). The scan of
  customer outputs for provider and model names runs over v2 fixtures.
- **Both confidentiality nets see joined forms** [R:MO-2]. `customer_api.FORBIDDEN` and
  `ops/verification/customer-denylist.json` replace the word boundary around the provider names with letter-and-digit
  boundaries, `(?i)(?<![a-z0-9])(?:corti|astra|fable|openai|anthropic|claude|gemini|google)(?![a-z0-9])`, which matches
  `gemini_unknown`, `reading_gemini_x` and `Gemini`, and not `corticosteroid` or `cortical`; the test vectors pin both
  sides. Before this, `\bgemini\b` missed `gemini_unknown`, because `_` is a word character (the judge ran the pattern: no
  match), so a vendor-named cause would have passed both nets.

### 4.13 Parity shims dropped, parity choices kept (recorded as DECISIONS in step 0a) [B][A][J]

**Dropped** (each was a word reader or a word-derived stand-in):
- C-11's dismissal of Gemini's contradictions by "hard" literal rows, and the literal hardness of `time_row`,
  `procedure_row` and `performer_row`;
- D58/D77's place adjacency used as causality (`relations.adjacent`, `adjunct_apart`, `_adjunct_places_apart`): causality is
  `part_of` and `cause`;
- D127's cannulation "conflict" for a failure followed by success: `access_outcome`;
- D115, D142, D149 and D157's bleeding words and adjective keys: `purpose` and `cause`;
- D31's hold of a whole session on Gemini's open question: each doubt holds only the facts it names (1.3) [R:CO-1], K2
  touches only the act's own session fact [R:HO-7], and each code reads its own session facts;
- the region moves of D114, D141, D148 and D153: the act's own session fact;
- the label and signature grammar of D124-D172: the section owner;
- the frames and markers of D35, D42, D54, D64 and D109-D162: the date relation.

**Kept as rules over facts:**
- D157's doubt: a clip or injection whose purpose or cause is not established may be a bleeding control, so its denial
  never excludes (`possibly`);
- D163 and D167: a held code keeps its claims;
- D134: an office visit set apart beside a done procedure session (a listing rule, no status effect);
- C-3 counts any performer's same-day procedure (legacy parity, S3 hazard 7);
- an act on the date of service at a separate encounter supports its code (T2; c2e53f8e READY).

The last two are diagnostic against c2e53f8e (owner amendment of 2026-11-09: parity is diagnostic) and change only by a
coding rule recorded in DECISIONS, never by a reader.

---

## 5. The retirement list

### 5.0 What "retired" means [C][B][J]

- **The 17 v1 interpretation modules stay unchanged in the tree and are denied whole** by the sentinel's new RETIRED kind:
  `prompt, schema, read, normalize, verify, literals, identity, lexicon, relations, mapping, classes, ercp, facts, events,
  coverage, combination, assess`. Every function in them is off the new path, not only the named readers. Nothing is
  moved, renamed or deleted; v1's own tests keep running unscoped, as the record of v1's behaviour; the legacy reader of
  c2e53f8e stays archived for rollback, as the directive allows.
- **The new path lives in two new packages**, `contract/` and `engine/`. v1's coding-rule bodies are forked into `engine/`
  with their readers deleted (4.1). A reader is never copied; the static rules prove it (5.7).
- **Copied as source integrity only:** the six date-literal parsers (`contract/date_literals.py`, used by L1 alone); `fold`
  and `fold_char` (`contract/fold.py`, quote location); `gemini_schema`, `canonical` and `sha256_of`
  (`contract/jsonschema.py`); the catalogue's vocabulary tables over enumeration values (`engine/catalogue.py`,
  `engine/anatomy.py`), each proved equal to v1's by value.
- **Kept modules**, edited where they import retired ones (5.7): `__init__, adapter, holds, sentinel, readers, overlay,
  store, wording, report, replay, dates`.

| part | functions named |
|---|---|
| 5.1 survey 2's meaning readers (57 rows; row 9 enumerates `another_role_hold`'s 16 nested helpers) | **73** |
| 5.2 literal readers with meaning uses only (15) and the phrase-search primitives (4) | **19** |
| 5.3 contract-layer word checks (S1 section 4: verify, normalize, identity, relations) | **46** |
| 5.4 consumers whose rule moves into Gemini's facts | **7** |
| **total named, all inside the 17 denied modules** | **145** |

### 5.1 Survey 2's meaning readers (all 73) [B][C], from `survey/readers.json`

| # | FILE:FUNCTION | lines | D (made by) | judged | replaced by (v2) | the rule that stays over it |
|---|---|---|---|---|---|---|
| 1 | `lexicon.py:other_occasion` | 519-526 | D35 | timing | effective `date_relation`, appraised | SUPPORT row 3 |
| 2 | `lexicon.py:current_frame` | 560-568 | D54 | timing | `date_relation` with its link (G1, G4) and appraisal; no frame list | SUPPORT row 3 |
| 3 | `lexicon.py:dated_frame` | 576-583 | D64 | timing | `event.date` and L1 (calendar arithmetic) | SUPPORT row 3 |
| 4 | `facts.py:_same_day_word` | 171-187 | D131 D151 | timing | `date_relation` on_date_of_service | C-3 same-day E/M |
| 5 | `facts.py:_frame_parts` | 200-208 | D109 | timing | as 4 | C-3 |
| 6 | `facts.py:_same_day_frame` | 211-236 | D109 D112 D132 D162 | timing | as 4; anaphoric frames by the `antecedent` link | C-3 |
| 7 | `facts.py:day_of` | 239-284 | D109 D111 D112 D131 D132 D151 D162 | timing (relative to the date of service) | effective `date_relation` | C-3; the exclusion's date basis (4.6); the routing stand-in (`engine/derive.py`) |
| 8 | `lexicon.py:markers` | 502-509 | C1, EB3 | status, time and performer qualifications | status values (planned, attempted), `date_relation`, `performer`, each appraised | SUPPORT; the established negative (4.6) |
| 9 | `events.py:another_role_hold`, with its nested helpers `fold` 675-676, `whole` 678-679, `phrase_end` 681-682, `unlead` 684-688, `entry_rest` 690-705, `label_of` 707-723, `heading_of` 725-760, `physician` 762-766, `heading_end` 768-772, `signed` 784-900, `signed.word` 824-825, `signed.standing` 827-835, `signed.spaced` 839-849, `signed.read` 851-873, `role_of` 934-962, `role_of.by_sentence` 942-945 | 634-988 | D124 D139 D146 D152 D158 D165 | entry ownership | `section.owner` and `entry(E)` by containment (1.5), appraised per act | the D124 rule: an act told only in another role's entry is held (`event_entry`) |
| 10 | `relations.py:Context.places` | 246-269 | D34 D78 | target (every place) | `target.places` and the lesion's places | D29 site classes; D78's adjacency retires |
| 11 | `mapping.py:compared_landmark` | 374-388 | D34 | target (anastomosis place) | `target.anatomy` / `reached_anatomy` with the entry's subtype and joins | D29; the pairing target row |
| 12 | `mapping.py:defining_target` | 481-498 | D120 D136 | target (structure) | `target.structure` | STRUCT:pfc (43240) |
| 13 | `coverage.py:eus_places` | 514-536 | D96 D123 | target, station (place of an EUS act) | `session.tract`, `target.places` | TRACT; R6:target; C-4 |
| 14 | `lexicon.py:device_named` | 368-391 | contract 5.3 | technique | `technique.device` | TECH:c (R4) |
| 15 | `classes.py:route_phrase` | 285-314 | D141 D153 D160 | technique (approach) | `session.approach`, `through` | ENT (D108, D114) |
| 16 | `classes.py:named_routes` | 317-337 | D114 D141 D153 D160 | technique (approach) | as 15 | ENT |
| 17 | `classes.py:examination_route` | 340-351 | D114 D141 D153 D160 | technique (approach) | as 15 | ENT |
| 18 | `mapping.py:submucosal_act` | 555-576 | D171 D177 | technique (route) | `technique.route` | ROUTE (43253) |
| 19 | `mapping.py:wall_place` | 531-552 | D177 | route; place in the wall | `target.places` (never a reference point) and `technique.route` | ROUTE |
| 20 | `assess.py:_stated_stations` | 516-535 | D171 D177 | examined stations | `session.stations[]`; for an empty list, the appraised completeness claim (SC-B) | STATIONS, LIMITED |
| 21 | `lexicon.py:_without_through_the_scope` | 404-405 | contract 5.3, EB1 | extent | `reached` as the endoscope's own reach (P19), `device_reached` for a device's point | R6:extent |
| 22 | `lexicon.py:device_reach` | 408-411 | contract 5.3, EB1 | extent | `device_reached` (K6) | R6:extent |
| 23 | `lexicon.py:scope_named` | 414-418 | contract 5.4 | extent | `reached`, the endoscope's by definition (P19) | R6:extent |
| 24 | `coverage.py:beyond_reach` | 578-609 | D141 D148 D153 | extent (duodenal portion) | `reached` at portion precision; `event.session` (never a move) | sessions; the region-and-reach session rule |
| 25 | `assess.py:_full_colonoscopy_reach` | 253-277 | D34 D38 D44 D57 D63 | extent through an anastomosis | `reached`, `reached_anatomy`, the entry's subtype | COLFULL |
| 26 | `events.py:_h3_denial` | 1304-1309 | D86 | is the statement a denial | status negated, established | the one-question policy (`statement_scope`) |
| 27 | `lexicon.py:negation` | 467-477 | contract 5.3, C1 | is this a denial | status negated; `visit.separately_identifiable` negated | the established negative (4.6); pairing; D113 |
| 28 | `ercp.py:_simple_clause` | 491-501 | D147 | yield | `event.yield` with its qualifiers | YIELD (D106) |
| 29 | `ercp.py:_negator` | 504-505 | D106 | yield | as 28 | YIELD |
| 30 | `ercp.py:_governed` | 508-517 | D106 D127 | yield | as 28 | YIELD |
| 31 | `ercp.py:_denial` | 520-542 | D106 D127 | yield | as 28 | YIELD |
| 32 | `ercp.py:_guarded` | 545-550 | D140 | yield | as 28: a purpose or doubt is a qualifier or another value | YIELD |
| 33 | `ercp.py:_yield_pairs` | 553-572 | D127 D140 D147 | yield | as 28 | YIELD |
| 34 | `ercp.py:_states_yield` | 575-579 | D140 | yield | as 28 | YIELD |
| 35 | `ercp.py:_simple_yield` | 582-592 | D140 D147 | yield | as 28 | YIELD |
| 36 | `ercp.py:_own_yield` | 602-620 | D140 D147 D155 D173 | yield | as 28 | YIELD |
| 37 | `ercp.py:_yields` | 623-646 | D127 D140 D147 | yield | as 28 | YIELD |
| 38 | `ercp.py:_clause_yield` | 649-662 | D168 D173 | yield | as 28 | YIELD |
| 39 | `ercp.py:_nominal` | 665-669 | D173 | yield | as 28 | YIELD |
| 40 | `ercp.py:_appositive_yield` | 672-707 | D173 | yield | as 28 | YIELD |
| 41 | `ercp.py:_free_simple_yield` | 710-727 | D173 | yield | as 28 | YIELD |
| 42 | `ercp.py:_own_sentence_yield` | 730-739 | D168 D173 | yield | as 28 | YIELD |
| 43 | `ercp.py:states_nothing_retrieved` | 742-751 | D106 D127 | yield (no production caller; tests only) | as 28 | - |
| 44 | `ercp.py:_later_statement` | 807-846 | D168 D173 | yield | as 28; a later denial is a contradicted yield (Y5) | YIELD |
| 45 | `ercp.py:nothing_retrieved` | 849-1000 | D106 D127 D140 D147 D155 D168 D173 | yield | as 28 | YIELD |
| 46 | `ercp.py:_states_own_yield` | 1110-1141 | D173 | yield | as 28; E* = the acts whose yield is supported (Y2) | YIELD |
| 47 | `relations.py:performer_row` | 363-375 | contract 6.4, C-11 | performer identity | performer class and `performer_person`; no name tokens, no hardness | the pairing performer row (4.5) |
| 48 | `combination.py:separate_statement` | 400-424 | D113 | E/M separately identifiable | `visit.separately_identifiable` | C3+SEP |
| 49 | `combination.py:_stated_procedure` | 282-308 | D130 D133 | is an "other" act a procedure | `other_class` | the same-day rule (4.7) |
| 50 | `lexicon.py:anastomosis_type_places` | 301-304 | D34 | anatomy type | `anatomy.subtype`, `joins` | D34's place rule over enumeration values |
| 51 | `mapping.py:anastomosis_place` | 355-371 | D34 | anatomy type (anastomosis place) | `anatomy.subtype` with `target.anatomy` / `reached_anatomy` | COLFULL; D29 |
| 52 | `lexicon.py:anastomosis_places` | 294-298 | D34 | anatomy type | `anatomy.subtype`, `joins` | as 50 |
| 53 | `classes.py:gastric_beside` | 215-248 | D153 D160 | anatomy type (gastric pouch, bypass) | `anatomy.type` (gastric_pouch, roux_limb, bypass) with `session.approach` / `through` | ENT |
| 54 | `classes.py:pouch_types` | 179-188 | D141 D148 | anatomy type (pouch) | `anatomy.type` ileal_pouch or gastric_pouch, `subtype` | ENT |
| 55 | `mapping.py:hemostasis_in_doubt` | 209-270 | D115 D142 D149 D157 | bleeding control in doubt | `purpose`, `cause`, `cause_event`; the catalogue kind from facts; D157's doubt by `possibly` | CAUSE; bundling (D30, D79) |
| 56 | `mapping.py:bleeding_stated` | 194-206 | D115 | bleeding treated today | as 55 | CAUSE |
| 57 | `lexicon.py:procedure_named` | 448-451 | contract 5.3 | session (which procedure) | `event.session` and `session.kind`; K3 | SUPPORT row 6; the pairing session row |

### 5.2 Literal readers and primitives [B][C]

**Retired (19).**
- landmarks: `lexicon.py:landmarks_named` 272-280 (its literal use was the V-class `landmark_words`; its meaning uses are
  rows 10, 13, 19, 20 above);
- durations: `literals.py:durations_min` 234-242, `_number` 227-231 (no rule reads a parsed duration);
- names: `literals.py:names` 285-322, `name_tokens` 325-327, `Name.surname` 256-258, `Name.as_record` 260-261,
  `_without_parentheticals` 272-276, `_word` 279-282; `relations.py:_name_tokens` 290-291, `named_family` 296-300;
- sizes and distances: `literals.py:sizes_mm` 214-224, `distances_cm` 209-211, `_mm` 200-202, `_clean` 205-206 (lesion
  identity is Gemini's, plus anatomical disjointness);
- primitives: `lexicon.py:found` 77-85, `holds` 88-89, `_alternation` 66-69, `_compiled` 73-74.

**Copied, for source integrity only (8):** `literals.py:full_dates` 103-111, `dates` 114-137, `dates.free` 119-120,
`_year` 71-76, `_month` 79-80, `_full_value` 83-100 into `contract/date_literals.py` (L1 alone); `lexicon.py:fold_char`
43-58 and `fold` 61-63 into `contract/fold.py` (quote location). The originals stay denied.

### 5.3 Contract-layer word checks (46) [B]

| module | functions | origin | replaced by |
|---|---|---|---|
| `verify.py` (15) | `time_words` 138 (the D35, D42/D54, D64 and EB3 arms; D67(a)), `_date_reasons` 184, `performer_words` 201, `size_words` 233, `landmark_words` 239, `reach_words` 256, `device_words` 265, `procedure_words` 274, `status_words` 283, `scope_words` 297, `basis_words` 306, `separate_words` 318, `identity_literals` 326, `single_family` 368, `exclusion_basis` 420 | contract 5.3-5.4, C1, C-15, EB1-EB3, D35, D42, D54, D64, D67, D169 | the fact states and doubts, G1-G6, K1-K8, L1, the appraisal; the established negative (4.6); no defaults |
| `normalize.py` (6) | `_Default` 130, `_defaulted` 317, `_fall_back` 326, `_place_free` 366, `_bind_names` 408, `_team_for` 430 | EB2, D35, D37, D67, D92, S16 r2 | no defaults; units replace passages; people and roles; K5 |
| `identity.py` (18) | `content_tokens` 103, `reference_only` 114, `specimen_labels` 121, `lesion_facts` 156, `sizes_apart` 184, `sizes_meet` 199, `_apart` 207, `same_place` 211, `distinct_reason` 217, `distinguish` 235, `_lexical_tie` 293, `_conflicts` 304, `_literal_single` 315, `_distance` 332, `_adjacent` 342, `_single` 356, `judge` 365, `link` 406 | contract 6.2-6.3, C-11, C-15 | `target.lesion` with G3 and the appraisal; `same_as` / `distinct_from`; disjoint supported places |
| `relations.py` (7) | `judge_claim` 485, `judge_positive_claim` 518, `Context.distinct` 235, `Context.stated_places` 271, `adjacent` 684, `adjunct_apart` 699, `_adjunct_places_apart` 707 | C-11, D34, D58, D77, D78 | contradictions never dismissed (4.5, 4.10); causality by `part_of` and `cause` |

Replaced structurally (they read no words, so they are not counted): `verify.scope_permitted`, `scope_fits`,
`umbrella_fits`, `status_time_consistent`, `reach_permitted`, `reach_stated` (D36), `usable`, `time_state`, `currency`,
`rejudged`; `identity._statement_tie`, `through_lesion`, `verified_lesion`, `same_or_possibly_same`. They become K1-K8,
G1-G6, `possibly` and `effective`.

### 5.4 Consumers whose rule moves into Gemini's facts (7) [B]

| FILE:FUNCTION | lines | D | replaced by |
|---|---|---|---|
| `events.py:_off_the_date` | 1736-1746 | D162 D169 | the effective date relation |
| `events.py:deciding` | 1712-1733 | D169; 7.5(2) | the established negative (4.6) |
| `events.py:session_doubt` | 1001-1014 | D31 | K2 and each code's session facts |
| `ercp.py:_other_times` | 787-804 | D87 D173 | the yield of each act; another occasion's retrieval is never this act's |
| `ercp.py:cannulation_conflict` | 1324-1356 | D127 (a parity shim, S3 14.6) | `access_outcome` |
| `ercp.py:_named_only_apart` | 253-273 | D173(5) | the anchor rule (a title is never a statement) |
| `coverage.py:coding_family` | 612-660 | D114 D141 D148 D153 | `event.session`; K3 can only unresolve, never move |

### 5.5 Consumers forked and rewired: the rule stays, its input becomes facts [A][B]

| v1 module | into | functions (rule bodies kept, readers deleted) | new inputs |
|---|---|---|---|
| `events.py` | `engine/evaluate.py`, `engine/questions.py` | evaluate, requirements, is_candidate, supports, _without_support, _focused (into the rank), defining_fit, site_places, site_fit, _target_hold, the `_h3_*` assembly, _kind_in_doubt, _exclusion, concerns, broad, coverage_of, within_words, support_spans | SUPPORT (4.3), pairing relations, the established negative, CAUSE |
| `ercp.py` | `engine/evaluate.py` | ruled, exchange_pairs, exchange_hold, retrieval_hold, _carries, access_not_completed, the hold wordings | YIELD, XCHG, `access_outcome`, ducts |
| `mapping.py` | `engine/catalogue.py` | code_link, covers, the defining table, code_technique, region tables, catalogue_kind (now from kind, purpose and cause), key, read_under | facts; nothing word-derived persisted |
| `coverage.py` | `engine/coverage.py` | sessions, reportable, doubted, bundled_reason, bundling_doubt, _possibly_of_lesion, drainage_step, _lower_eus, _placed_eus, reconcile, completeness, event_coding, in_doubt_questions, service_extent_questions, eus_unprofiled_entries | the sessions table, `part_relation`, `cause`, lesion relations, `unlisted` |
| `classes.py` | `engine/classes.py` | code_class, fits, routes, doubted_routes, act_elsewhere, enteroscopy_hold, class_misfit, class_hold, elsewhere_hold | approach, through, anatomy types, reached, completion, the act's session |
| `relations.py` | `engine/pairing.py` | Context, target_place, procedure_row, time_row (no hardness), _bundling, identity_in_doubt | 4.5's rows |
| `assess.py` | `engine/assess.py` | _reach, _inventory_fact, _examination_class, _eus_code_hold, _proposal, assess, _claims, _one_stricture, _MemberAnswers, _Participants, _incomplete_session | R6, TRACT, STATIONS, ROUTE, STRUCT, the rank |
| `combination.py` | `engine/combination.py` | base_included, base_within, competition, procedure_day, visit_basis, modifier_review, endoscopic_rows | date relations, `other_class`, `separately_identifiable`, `unlisted` |
| `facts.py` | `engine/derive.py` [J] | derive, context_of, document_date, routing_stand_in, _status | the date of service, member values, date relations |

### 5.6 What still touches document text, and why (the allowlist) [A][C]

| where | operation | why it is not a reader |
|---|---|---|
| `contract/segment.py: units, closure` | splits at paragraph breaks, at line breaks that are not hard wraps (the earlier line's last character and the next line's first), and after `.`, `!`, `?` followed by space and a non-lowercase character unless a one- or two-letter token beginning with an uppercase letter precedes the period; computes sentence closures [R:CO-3][R:CO-4] | geometry (S2 classes boundaries as geometry); character classes only, no vocabulary |
| `contract/geometry.py: bind_words, bounded_positions` | locates a cue inside its own unit (exact, then fold tier; word boundaries) | source integrity: WHERE a quote is, never what it means |
| `contract/fold.py` | folds characters for the fold tier | source integrity |
| `contract/date_literals.py` via `consistency` L1 | parses the date literal in Gemini's own date and timing words | the transcription check of a value Gemini gave; demotes only; pinned to v1's eight functions by AST equality and its two month and weekday tables by sha (5.7) |
| `store.row` | compares each stored quote with its revision slice | revision binding |
| `engine/assess.py` -> `checks.code_scope`, `checks.exact_evidence`; member-answer passage binding | the proposer's quote is the document's own text | integrity (R1), before and outside the per-code rule |
| participants' Locator | locates Astra's and Fable's kept spans | integrity, unchanged |
| `wording.quote(span)` and the display builders | copy slices into questions, explanations and labels after the decision | display; nothing branches on what they return (static rule) |

`contract/claims.py` copies no text: cards and claims carry unit ids, and the document reaches pass 2 through the framing.

### 5.7 How the guard proves that none of it runs on the new path [C][B][A]

1. **Deny by module, counted at runtime** [C]. `sentinel.RETIRED_MODULES` = `studio.interpretation.` + the 17 modules of
   5.0. They are armed by the existing machinery: code objects computed at start-up, nested ones and lru_cache wrappers
   included; PY_START set locally; the ContextVar labels; forked children merged. They carry a distinct kind, RETIRED, so
   the D22 record reports `retired_calls` apart from `legacy_calls`. `expected_retired()` asserts the set equals
   `glob(studio/interpretation/*.py)` minus KEPT (`__init__, adapter, holds, sentinel, readers, overlay, store, wording,
   report, replay, dates`); a new top-level module neither kept nor retired refuses the install, so new code must go under
   `contract/` or `engine/`. Each retired file's code-object count is pinned (PINNED_SIZES, RETIRED_SIZE).
2. **The write gate** [C]. `sentinel.gate` refuses a new-path write (assessment, decision, member answer, report) when the
   scope counted any RETIRED or legacy execution: `Tripped`, and the AuditEvent `sentinel.tripped`.
3. **A positive control in every process, the deployed image included** [C][B]. `PROBE_CALL_RETIRED =
   ('studio.interpretation.lexicon', 'negation', ('no',))` must be counted exactly once under the probe label at install,
   beside `gi.cues.page_number_line('3')`. Any failure leaves the process refusing new-path writes.
4. **"Words never decide": static rules** (`tests/test_guard_static.py`) [B][C][A]:
   - `WordsNeverDecide`, over `engine/**`, `contract/settle.py`, `contract/claims.py`, `contract/consistency.py`,
     `overlay.py` and `readers.py`, forbids: an import of any RETIRED module (no allowlist: v2 copies the pure tables it
     needs), of `re`, `regex`, `unicodedata`, `difflib`, `fnmatch`, `lexicon`, `literals`, or of contract's text modules
     (`segment`, `geometry`, `fold`, `date_literals`), except `consistency.py`'s import of `date_literals` for L1; in
     `engine/`, any attribute or subscript named `text`, `words`, `quote` or `unit_text`; `reading.text` and
     `revision.text` anywhere in scope; calls of str methods (find, index, rfind, startswith, endswith, split, rsplit,
     partition, lower, upper, casefold, strip, replace, count, istitle, isupper) on a non-literal receiver; `in` or `not in`
     with a string-constant operand; a display helper's return used anywhere but as an argument to a wording function, a
     HeldFact or clarification constructor, an f-string, a join, or another display helper's return.
   - `NoWordLists`, over `contract/**` and `engine/**`, forbids a module-level tuple, list, set or dict of two or more string
     literals unless every literal is a value of a contract enumeration or a pinned fact key, or the collection is one of
     the pinned OUTPUT tables (the enumeration definitions of `extract_schema.py`, `claims.TEMPLATES` and the label tables),
     whose sha is in a version label and which no code compares with document text (WordsNeverDecide refuses any such
     comparison). The copied catalogue and anatomy tables pass; a phrase list fails [B][J]. `contract/date_literals.py`,
     which needs v1's month and weekday tables, is the one exemption, closed by pinning instead: a test asserts that its
     functions are AST-equal to v1's eight named functions, that its two tables equal v1's by sha, and that it holds no
     other module-level string collection, so a timing frame list added under a date-literal name fails it (the guard gap
     the self-certification lens named).
   - `SingleCharacterGeometry`, over `contract/segment.py` and `contract/geometry.py`, refuses `import re`, a string
     literal longer than one character in a comparison, and any str call but `isspace`, `islower`, `isalnum`, indexing,
     and `find`/`rfind` given a one-character literal [A]. (The `[S\d+]` collision check scans characters.)
   - Every pin is used, and each rule refuses a planted control, as the existing rules do. This is the one measure that
     catches a veto re-written under a NEW name; counting cannot.
5. **Typing as a fence** [B]. `mypy --strict` over `engine/types.py`, `engine/facts.py` and `engine/reading.py`: FactSet
   values are `Enum` members and ids, so a string operation on a fact value is a type error at the boundary.
6. **A runtime proof of text-freeness**: P-TEXTFREE (9.4) [B, restated by J].
7. **Mutation proofs** (`tests/test_guard_mutation.py`) [C][B][A]. Each plant is applied in memory and asserted applied,
   then restored and asserted restored by sha256 printed before and after (AGENTS.md); each turns its guard red, naming
   only itself, and a control plant (a comment) stays green. The plants: `facts.day_of` called from
   `engine/combination.procedure_day`; `lexicon.negation` from `engine/pairing`; `events.another_role_hold` from
   `engine/evaluate`; `re.search` in `overlay.counted_codes`; `verify.status_words` from `contract/settle`; a word tuple in
   `contract/geometry.py`; `fold(words['text']).startswith('no')` in `engine/evaluate`.
8. **The matrix** (`tests/test_guard_matrix_new_path.py`) [C][B]. Generated from `cptstudio/urls.py`, `jobs.STAGES` (now
   with `appraise`) and the in-image scripts, over v2 assessments only: zero under every label for the legacy and the
   retired sets, with a positive control per class and label. The worlds: assess FIRST, FINAL and AGAIN; answer recompute;
   context save; the review view; decision save; reload (customer state and list); export (approved, draft, operator); the
   peer request; a reinstated code's `reviewed_completeness` (the read-time re-evaluation S3 section 10 flags). A
   separate world asserts that a v1 row is never read under `new_path`.
9. **Operator evidence after install** [A][B][C]. For every walked encounter: the D22 record (`legacy_calls: 0`,
   `retired_calls: 0`, deny_size, retired_size, both positive controls); both ProviderRuns (purposes `interpretation` and
   `appraisal`) with `returned_model == 'gemini-4-argon'`; the EventInventory row's versions (`gemini-events@2/appraisal@1`,
   `gemini-inventory@2`) bound to both runs; the engine version `cpt-studio-events@2`; the operator report's interpretation
   section with usage and cost per run; the in-image self-test showing the retired probe counted once. This is the
   directive's "the deployed runtime uses Gemini and does not invoke the retired semantic vetoes", shown, not inferred.
10. **The retirement manifest** [A][B]. `tests/v2/test_retirement_manifest.py` holds the 145 names of 5.1-5.4 and asserts
    that each resolves to a code object inside a RETIRED module, so each is armed by measure 1; the count is pinned.

**What defeats each, and what covers it.** Counting (1, 3, 8, 9) sees only armed code: a reader re-implemented in a new
function is caught by 4-6. The static rules see only the modules they scan, so the read-time modules, settle and claims
are in scope, and a dynamic import or a module named in a string is caught by counting. Both need the read-time path
exercised, which the matrix's reinstated-code world does.

**Kept modules that import retired ones today, and how each stops** [C, verified by the judge]:
- `store.py` imports `schema` and `read`: its v2 reader imports only `contract/` (Refusal, iso_date and the enumerations are
  copied there); v1's reader stays as `store._v1_reader`, reached only through `readers`' V1 branch.
- `adapter.py` imports `prompt` and `read`: replaced by `contract/extract_prompt`, `contract/appraise_prompt` and their
  readers.
- `dates.py` imports `literals`: rewired to `contract/date_literals`.
- `overlay.py` imports `combination`, `coverage` and `events`: rewired to `engine/`.
- `readers.py` imports `events` and `store` locally: the v2 dispatch; v1 rows go through a V1 branch labelled
  `legacy_record`, read as stored, UNREADABLE for re-evaluation.
- `jobs.py` imports `facts` and `assess` (as `events_engine`) at module top, and `normalize` and `read` locally: rewired to
  `contract/` and `engine/`, with `facts.derive` replaced by `engine/derive.py` [J].

---

## 6. Compatibility

### 6.1 Versions

As 1.1. A changed pass-1 byte needs `gemini-events@3`; a changed pass-2 byte, `gemini-appraisal@2`; a changed check or
settle rule, `gemini-inventory@3` (re-settled from the stored bytes, no send); an engine change, a recompute.

### 6.2 Existing records [C][B][A; revised R:MO-1, MO-4, MO-5]

- **Live (c2e53f8e).** Every legacy assessment, decision, approval and export stays as it is, read by LegacyReader; reload
  and export read the persisted rows as today, and the legacy matrix stays byte-identical. Nothing is re-assessed silently
  (2026-11-09 interpretation (e)). The branch was never installed, so live holds no `cpt-studio-events@1` assessment and
  no EventInventory table. **The installer asserts on the target, before the switch, that no v1 rows exist**: no
  Assessment whose engine version is `cpt-studio-events@1`, and no EventInventory row whose `interpretation_version` is
  `gemini-events@1`; it refuses otherwise [R:MO-1]. v2's own rows never trip it, so a fix release after the walk, a
  re-install after a switch-back, and a same-revision `app` re-run (a provider-mode switch, the access check run again,
  the recovery of a failed `app`: INSTALL.md, D83) all pass. A test runs install, writes one v2 row, switches back,
  re-installs and re-runs `app`. (The pre-refutation predicate, the family pattern `cpt-studio-events@%` and any
  EventInventory row, would have refused every install after v2's first row, on append-only tables only a deletion could
  clear.)
- **Legacy encounters and context saves** [R:MO-4]. A c2e53f8e encounter has no inventory, and on v2 the legacy reader no
  longer runs. A context save on such a revision stores the member's values and queues nothing. The encounter then says
  that its codes were checked before the change; a new approval or export of the legacy assessment is refused until it is
  checked again; and the action "Check again with the current reading" says, before it runs, that the document will be
  read again by the automated reading and that decisions made on the earlier check will need review again. Only that
  explicit act queues the interpret stage (both passes, about $0.08 to $0.17). The kept code's `_save_before_reading`,
  which queued the reading on the save itself (`jobs.py` 4443-4464), changes in step 5b. Existing decisions and downloaded
  reports stay as records; nothing is rewritten. That a legacy approval does not carry across engines (6.5) is reported to
  the owner before the install as an accepted-capability loss (class b).
- **Test instances that hold v1 rows.** `interpretation.is_new_assessment` dispatches the `cpt-studio-events@` family to
  EventReader; EventReader @2 sends @1 rows to the V1 branch (label `legacy_record`), read AS STORED with the UNREADABLE
  blocker: revoke only; approve, export and a reinstatement's reviewed completeness are refused until an explicit
  re-assessment (two new sends). v1 EventInventory rows are never read by v2 (their versions differ; the doors ignore
  them).
- **Older v2 inventory versions** [R:MO-5]. EventReader reads every v2 inventory version it has shipped (a `READ_VERSIONS`
  list, as the adapter keeps), as stored: a new INVENTORY_VERSION never makes an earlier v2 assessment UNREADABLE.
  Re-settling one under the new version is an explicit re-assessment: pass 1's stored bytes are checked again; a stored
  verdict is reused for each claim whose content key is unchanged; when the claim set changed, a new pass-2 send is made,
  an explicit act and never a save's (D8). A verdict is never read against a different claim.
- **Recordings.** fresh-frozen, fresh2-frozen and the trial's stay byte-identical as v1 evidence; they cannot be replayed
  by v2 (different request bytes). v2's recordings are new (9.6). A check repair changes the claim set and so the pass-2
  requests: the re-measure of development batches after one is a pass-2 re-send over the stored pass-1 answers, budgeted
  in 7.6 [R:MO-5].
- **Re-assessment** of a legacy or v1 revision is always an explicit act that creates new rows; the install re-assesses
  nothing (D16).

### 6.3 Migration 0015 (additive; no backfill, no RunPython) [C, corrected by J]

- `0014_event_inventory` is on the branch and not applied on live; it installs with v2 unchanged (EventInventory,
  InterpreterHold, InterpreterHoldRelease, `Assessment.event_inventory`, `Assessment.interpretation`,
  `EncounterContext.event_inventory`).
- `0015_inventory_appraisal` adds `EventInventory.appraisal_run`: `ForeignKey(ProviderRun, on_delete=PROTECT, null=True,
  related_name='+')`. Nothing else: no existing column changes, no default, no NOT NULL. `appraisal_run_id` joins store's
  BINDINGS, so the row's sha256 binds both runs.
- **The unique key `(revision, interpretation_version, inventory_version, provider_run)` is unchanged and stays
  sufficient**, because: a `read` row is written only when both passes are settled; a refused pass-1 answer writes a
  `refused` row with `appraisal_run` NULL (v1's pattern; its retry is a new pass-1 run); a refused or unhealthy pass-2
  answer is recorded on the appraisal ProviderRun and the stage, never as a row; the appraise doors allow one read row per
  pass-1 run and version pair. (Design C wrote refused pass-2 rows, which collide on this key with the read row of the
  retry: judging.md defect 13.)
- `Job.kind` `appraise` (8 characters of 10) and `ProviderRun.purpose` `appraisal` (9 of 16) fit the existing columns.

### 6.4 Rollback to `cpt-studio:c2e53f8e7d33` (D15; FINAL 12, extended) [C][A][B]

- **The old image never reads the new rows.** It knows neither EventInventory nor the new column. A v2 assessment keeps
  writing `SERVICES_STUB` into `services`, `INVENTORY_PROBLEMS` into `completeness`, the legacy check ids and the legacy
  context notes, so the old image reads it fail-closed ("never less held"): it reads statuses as stored (FINAL 12.1-12.2),
  so a held code stays held and a READY code stays approvable there, as on v2. One recorded limit stays (DECISIONS D59
  finding 13) [R:MO-7]: a reinstatement made ON the old web reads the v2 record through `SERVICES_STUB`, which adds no base
  hold, so the diagnostic base code can stay approvable beside the reinstated therapeutic code (v2 excludes 45385 by a
  cited "No polypectomy was performed." and leaves 45378 READY; reinstating 45385 on the old web leaves both approvable and
  exportable). INSTALL.md (Switching back) states it, the switch-back note names such encounters `reinstatable`, v2's
  install receipts keep that note, and the operator re-checks those encounters on v2 before anyone reviews them on the old
  web. The pre-refutation sentence "approves or exports none of it" was false.
- **No v2 job reaches the old worker.** `ops/install.py` adds `appraise` to `CLOSE_STAGES` and `UNRUNNABLE_STAGES` (the old
  worker would die on `STAGES['appraise']`) and to the undo receipts' note (P-1).
- **The D15 runtime rollback test** (FINAL 12.3) runs on v2 records: an interpreted and appraised upload; a held, an
  excluded and a reinstated code; an approved code with a modifier, and its export; a member answer; a second review; an
  interpreter hold; a queued `interpret` job; a queued `appraise` job; a pass-2 refusal; an unhealthy appraisal; a held code
  whose item is a new fact (`event_entry`). Its transcript is attached to the install declaration.
- **The current site stays available** until the switch (the install phases are unchanged); the rollback images stay
  tagged; existing records are kept; decisions recorded on v2 assessments are never rewritten.

### 6.5 The overlay, member answers and fingerprints [B][C]

- `overlay.read_coding` reads `event_coding@2` only; @1 is UNREADABLE (fail-closed). `is_new_assessment` dispatches @2.
- `reviewed_completeness` runs the pure engine over the frozen settled inventory (`store.load`, checked against the
  revision text sha256 and both runs' response bytes), with `effective()`. Assess and read time have identical inputs,
  which closes S3's hazard 5 (no date re-judge and no `reading.text` at read time).
- **Fingerprints** no longer carry word texts (v1's `events.basis_of`): they carry the engine, code, family, the (check
  id, status) pairs, context values, units, status, and the read facts' ids, results, values and spans. Rendered question
  text still enters the question fingerprint, as today. ENGINE_VERSION @2 changes every fingerprint, so decisions never
  carry across engines (D7); live holds no new-path decisions.
- **Member answers:** the binding is unchanged; pre-v2 answers are `asked_differently` except the key-bound facts; answers
  are kept and never applied silently.

---

## 7. Cost, latency, Stop and resume, failure handling

### 7.1 Cost per document [J; C's model; revised after the refutation]

Modelled over the 179 FRESH-2 documents by `design-v2/judge-data/cost_model_v2r.py` (output `cost_model_v2r.out.json`; read
only, nothing sent): the pre-refutation model (`cost_model_final.py`) with two parameters the refutation changed. About 12
claims per event instead of 10 (controls generated for every READY- or exclusion-deciding attribute, pair controls, and the
completeness claim), and about 24 output tokens per verdict instead of 28 (evidence carries unit ids only). The other
inputs are unchanged: v1's prices fit $2 per million input and $10 per million output tokens (thinking billed as output);
v1's median per-call cost $0.045; median document 887 characters and 5 events; largest 19,460 characters and 43 events;
pass-1 fixed prompt about 10,000 tokens; unit markers about 0.05 tokens per character (an over-estimate now: joined wraps
cut GI Note #8 from 317 units to 181); pass-1 output F1 x v1's for the same document (band 0.85 / 1.0 / 1.2); pass 2 4,000
fixed tokens and 30 input tokens per claim; thinking at the measured mean, 320 tokens, for cost (the tail is used in 7.2
and 7.4). Each is re-measured by the first bounded batch.

| per document, both passes | F1 0.85 | **F1 1.0** | F1 1.2 |
|---|---|---|---|
| median, November ($2 / $10) | $0.079 | **$0.083** | $0.088 |
| mean, November | $0.111 | **$0.118** | $0.128 |
| p90, November | $0.161 | **$0.174** | $0.191 |
| largest, November | $0.430 | **$0.468** | $0.518 |
| median / mean from 2026-12-01 ($4 / $20) | $0.158 / $0.222 | **$0.166 / $0.236** | $0.177 / $0.256 |
| pass 2's share of the total (mean) | 41% | 38% | 35% |
| the 179-document corpus once, November | $19.83 | **$21.13** | $22.86 |

About 1.85x v1 at the median (the pre-refutation figure was 1.8x). Prices double from 2026-12-01, and the install and the
walk will likely fall after that date. The per-document production cost is reported to the owner before the install
(standing authority class d); the recording budget against the cap is 7.6.

### 7.2 Latency (two passes in series; FRESH-2's median generation rate, 100.8 tokens per second)

| | F1 0.85 | F1 1.0 | F1 1.2 | v1 (measured) |
|---|---|---|---|---|
| median | 49 s | 53 s | 59 s | 28 s |
| p90 | 125 s | 138 s | 155 s | 84 s |
| largest | 306 s | 336 s | 376 s | 219 s |

Pass 2's largest modelled output is about 12,900 tokens at the mean thinking, about 19,100 at FRESH-2's p99 thinking (6,544
tokens), and about 29,400 at its largest (16,776 tokens, measured on an 848-character document: thinking does not follow
size). At the slowest measured rate, 82.4 tokens per second, the last takes about 356 s, past the pre-refutation 300-second
read; pass 2 therefore takes pass 1's deadlines (7.4) [R:MO-3].

### 7.3 The size bound, and why pass 1 must stay lean [C][J]

D25 set `INTERPRET_MAX_CHARS = 20,000` from v1's fit (output = 2,173 + 1.081 x characters, p99 residual 3,593), so that the
predicted p99 stays under 84% of the 32,768-token cap. With v2's factor F1 the same rule gives `max_chars = (27,525 / F1 -
5,766) / 1.081`: about 24,600 at F1 0.85, 20,100 at 1.0, 19,400 at 1.03, 15,900 at 1.2.

The live maximum is 19,398 characters (D25, the read-only dump of 2026-11-10), and that document is GI Note #8, the
owner's case (HARNESS). **Any F1 above about 1.03 refuses it.** That is why this design uses units (no passage copies:
16% of v1's output), empty slots for silence, and section inheritance (about 135 tokens saved per inheriting act, most
in the long documents). The rule:
- the bound stays 20,000;
- G-SIZE (9.2) measures F1 on the first development batch, its two largest documents included, before anything larger
  is sent;
- if F1 exceeds 1.03, the schema is compacted first, as a new INTERPRETATION_VERSION: options move to an event-level list;
  `restatements` carry ids only; `qualifiers` move to an event-level list with `applies_to` (B's form); enumeration values
  are shortened;
- if F1 still exceeds 1.03, the owner is asked before the bound changes (an accepted-capability loss, class b). A larger
  maxOutputTokens, if the model documents one, is the other recorded option. Nothing is lowered silently.

### 7.4 The pipeline, Stop and resume, duplicates, usage [C][B]

```
extract -> interpret (pass 1) -> appraise (pass 2) -> analyze (engine/derive) -> predict (Corti) -> astra -> fable
        -> assess #1 -> astra_peer -> fable_peer -> assess #2                      [review2 -> assess] member-asked only
```

**Keys.** `interpret:<revision>:gemini-events@2`; `appraise:<revision>:<extraction run>:<the first 16 hex of the appraisal
request's sha256>` (99 characters; with `:after-reconcile:<run>` and `:resume:<uuid>`, 196 of `Job.idempotency_key`'s 200).
The request's sha covers the claim set, so a changed check, version or claim set is a new key, never a reuse [R:MO-5];
`analyze:<revision>:<inventory>`; the suffixes `:retry:<run>`, `:retry-release:<run>`, `:after-reconcile:<run>` and
`:settled:<run>` work as today.

**The appraise stage's doors**, before anything is built, in predict's order:
0. the claim bound: a claim set over the per-request bound (1.8) is not sent; the stage ends TOO_LONG (7.5) [R:MO-3];
1. an inventory already `read` for this extraction run and these versions: no send; queue analyze;
2. a stored SUCCEEDED appraisal answer to the identical request in the same workspace: reused
   (`usage_basis='reused_retained_result_no_new_usage'`); the reuse never crosses a workspace (tenant isolation, as v1's
   P-2);
3. the encounter-wide unknown-outcome block;
4. the failed-before door, except a run released for one recorded retry;
5. `_live_gate`;
6. the interpreter mode and hold (D11): a not-sent run with `scope.held`, ended CANCELLED (resumable);
7. send: one exchange, no tools, `gemini-4-argon` only.

The appraisal request is a pure function of the revision text, the stored extraction response bytes, INVENTORY_VERSION
(the checks select the claims, and L1 judges against the document's own date at claim time) and APPRAISAL_VERSION, never
of a member value [R:MO-5], so replay and reuse work exactly as for pass 1. The interpret stage keeps its doors unchanged.

**Stop and resume.** Stop is observed before each send. A Stop between the passes leaves pass 1's answer stored; Resume
queues `appraise`, which reuses it and sends pass 2 only. Resume queues the first missing stage: `interpret` (no read
extraction at the current versions), else `appraise` (no inventory at the current versions), else today's chain. D8
holds on every revision with a v2 inventory: saves never call Gemini; a context save re-derives over the frozen inventory
(`engine/derive.py`, with `effective()`); an answer recomputes AGAIN with nothing sent. On a revision only the legacy
reader read, a context save stores the values and sends nothing; the explicit re-check of 6.2 is the only way that
revision is read again [R:MO-4]. (The pre-refutation sentence "saves never call Gemini" was false there: the kept code
queued a reading on the save.)

**Duplicates:** idempotency keys per stage; the single-flight provider lock; request-sha256 reuse; the unique key of
EventInventory (6.3).

**Usage.** Each run records `usage` (provider-reported tokens) and `usage_basis`; the operator report sums both passes per
encounter and per batch; the recording harness labels each run `fresh-dev`, `fresh-acceptance`, `replay`, `text-only` or
`synthetic`.

**Quota and authentication.** One classifier (`adapter.classify`, `holds.py`) serves both purposes. A HOLD (auth,
permission, quota including a bare 429 per D39, or a model mismatch) stops every request of either pass,
installation-wide; the encounter reads "paused"; an operator releases it; the member resumes.

**Deadlines** [R:MO-3]. Pass 1 unchanged: read 480 s, send 510 s, stage 560 s. Pass 2 takes D49's settings too: read
480 s, send 510 s, stage 560 s (new settings `APPRAISER_READ_TIMEOUT_SECONDS`, `APPRAISER_SEND_DEADLINE_SECONDS`,
`JOB_DEADLINE_SECONDS['appraise']`). A cut-off answer of 32,768 tokens at the slowest measured rate (82.4 tokens per second)
needs about 398 s, inside the read, so it is recorded TOO_LONG, never UNKNOWN. At the pre-refutation 300 s it would have
been UNKNOWN: an operator's reconcile, an encounter-wide block on every send, a paid resend and an unrecorded usage, which
is D49's defect, repeated on pass 2. The largest modelled pass 2 with the largest measured thinking (16,776 tokens, 1 of 179
FRESH-2 calls) is about 29,400 tokens, about 356 s at that rate. All stay below the 600-second stale sweep. D2 and D3
measure pass 2's thinking tail and rate, instead of assuming the mean.

**No fallback.** Pass 1 alone is never used: a document without a settled appraisal has no new-path assessment, and the
encounter shows the failed stage truthfully, with Retry. There is no fallback to the legacy reader or to v1, and no silent
model substitution.

### 7.5 Failure handling [C][B]

| outcome | pass 1 (interpret) | pass 2 (appraise) | the member sees (no provider name) |
|---|---|---|---|
| definite failure (5xx, a per-minute paid-tier 429, another 400, an unreadable envelope) | FAILED; Retry offered (a recorded retry; no automatic retry, D11) | FAILED; a retry re-sends pass 2 only | "The documentation could not be read." / "The reading is being checked; retry" |
| auth, permission, quota (a bare 429 included), model substitution | the installation-wide InterpreterHold; nothing is built while it stands | the same hold | "Paused" |
| unknown outcome | UNKNOWN; the reconcile flow (`:after-reconcile:`) | the same | "Checking a previous request" |
| answer refused by the reader | EventInventory `refused`, appraisal_run NULL; the retry door | recorded on the appraisal run; no inventory row; the retry door | as the definite failure |
| MAX_TOKENS | TOO_LONG; never re-sent for a member (C5) | TOO_LONG, inside the read timeout (7.4) [R:MO-3] | "This document is too long for automatic reading." |
| a claim set over the per-request bound (1.8) | - | not sent; TOO_LONG; reported, and taken to the owner if a live document reaches it (class b) [R:MO-3] | as above |
| over the size bound | not sent; INTERPRET_TOO_LONG_MESSAGE | - | as above |
| appraisal unhealthy (3.2.6) | - | recorded on the appraisal run; no inventory row; the retry door | as the definite failure |
| worker died mid-stage | `mark_stale` settles from the recorded exchange (`:settled:`, P-6) | the same | - |
| settle findings (an unlocated unit, a failed geometry or consistency check, a qualifier, a disagreement) | - | the facts unresolved | the one item on that fact |
| a legacy or retired call on the new path | the sentinel gate refuses the write (`sentinel.tripped`); the install self-test fails | the same | - |

### 7.6 The recording budget (fresh calls, bounded; the testing authority of 2026-11-11, cap about $300) [C][B][A; revised R:MO-6]

Every batch runs with concurrency one under its own cost cap enforced by the harness; every request's usage is recorded;
fresh, replay and text-only runs are labelled apart; the new recordings are frozen by sha256 BEFORE anyone reads them (the
trial-1 discipline); prior recordings (fresh-frozen, fresh2-frozen, the trial's) stay unchanged.

| batch | what | about (November / December) |
|---|---|---|
| D1 | the acceptance probe: one development document, both passes (the API accepts both response schemas; model pin; read; settle) | $0.10 / $0.20 |
| D2 | 10 development documents x 1, the two largest included (GI Note #8 and PAIR-4-W2 where the exclusion list allows, 9.6): G-SCHEMA, G-SIZE with the claim count, claims per event, health, coherence, latency and the thinking tail | $1.6 / $3.3 |
| D3 | 30 development documents x 3, the refutation's documents included (9.6): stability, G-HEALTH, G-DOUBT, G-NOISE | $11 / $23 |
| iterations | each prompt or template iteration re-records 30 x 1; each check repair re-sends pass 2 only, over D3's latest pass-1 answers | $3.5 / $7 each; $1.4 / $2.8 each |
| A | the frozen acceptance set x 3 runs (about 215 cases), by the acceptance owner's tool, at the FRESH-2 mean | about $76 / $152 |
| A' | one re-run of A after a repair of the prompt, the schema or the templates, which changes the request bytes so that A cannot be replayed (9.6) [R:MO-6] | about $76 / $152 |
| W | the website walk on the installed site; then the sealed c6 and c7 walks | under $2, then per document as 7.1 |

**Against the cap** [R:MO-6]. At December prices one cycle with one repair (D1 to D3, two iterations, A and A') comes to
about $350, more than the shared monthly cap of about $300 (2026-11-11). Therefore:
1. before A is sent, the owner receives the total against the cap and the month's recorded spend (class d), with the
   choice of spreading A and A' over two months or raising the cap; nothing is sent past the cap on the session's own
   judgement;
2. the harness stops every batch when the month's recorded spend (its own ledger plus the installed site's usage from the
   operator report) plus that batch's cap would exceed the cap less a reserve kept for the installed site (pinned; about
   $40);
3. after the switch, the installed site shares the Google project, and so the cap, with the test instance
   (`testinst/gemini_cred.sh` makes a test-only copy of the owner's credential). A reached cap returns a bare 429, an
   installation-wide hold that pauses every new upload until the reset (D39, 7.4). A separate test key or project, or a
   sub-cap, is an owner decision (class d: keys and money), asked before any post-switch batch; until it is made,
   post-switch batches run only inside the reserve rule of item 2.

---

## 8. The build plan

### 8.0 Rules for the builders [C][B][A]

- **One owner per file.** Every file below has exactly one owning step. A later step that needs a change in an earlier
  step's file asks the integration owner, who applies it serially; no two agents edit one file at once. The shared files
  are owned once: `interpretation/__init__.py` and `cptstudio/settings.py` by 0b (pins applied by the integration owner on
  request from 2a and 2c); `studio/models.py` and `interpretation/store.py` by 1d; `wording.py` and `studio/customer_api.py`
  by 3c; `studio/jobs.py`, `studio/progress.py` and `studio/review.py` by 5b; `sentinel.py` by 6a; `ops/` by 6b.
- **The 17 retired modules are edited by no step**, and neither are their tests.
- **Worktrees.** Each builder works in its own worktree made by the integration owner with `setup-worktree.sh` (relinking
  the venv first); nobody runs `git -C` against the shared tree or edits `/opt/meddoc-pro`.
- **Tests** live in per-module files owned by the module's step (`tests/v2/test_<module>.py` unless named otherwise).
- **Merges.** Only the integration owner merges, in the step order below. At every merge the tree imports cleanly and the
  full suite is green, v1's suites included (v1's modules are untouched, so they keep passing).
- **The switch.** Steps 0b-4d add new code beside v1; `jobs.py` keeps calling v1 until step 5b switches it; 5c switches read
  time; 6a arms the RETIRED deny set, so it merges only after 5a-5c, when no new-path code calls a retired module.
- **No prompt byte and no send before step 0a's gate.** The owner wrote "Before changing the prompt, freeze the acceptance
  cases"; step 0a verifies the a1 v2 hash commit (THRESHOLDS amendment 1) exists before 2a writes instruction text and
  before any fresh call.
- **Read-only lenses.** Refutation lenses and measurement agents get read-only copies; no agent mutates a file another agent
  is editing (AGENTS.md: a mutation proof asserts its own application and restoration; never give an agent write access to
  a file you are editing).

### 8.1 The steps

| step | owner | files (exclusive) | depends on | done when |
|---|---|---|---|---|
| **0a** | integration owner | `docs/gemini-migration/DECISIONS.md` (the adoption entry for this design after its refutation; the ADJUDICATION amendments EB1-EB4 of 3.5; the shims dropped and the parity choices kept, 4.13; the new question facts; the one-item policy); HARNESS.md status and checklist rows; RULINGS cross-reference if the owner rules on 4.13 | the acceptance freeze commit (a1 v2 hashes) | the a1 v2 hash commit is verified to exist; the acceptance owner has handed builders the DEVELOPMENT EXCLUSION LIST (the sha256 of every acceptance document text, hashes only; builders never open the set) |
| **0b** | integration owner | `interpretation/__init__.py` (v2 labels; pin placeholders); `contract/__init__.py`; `engine/__init__.py`; `contract/types.py` (Unit, Source, Fact, SettledFact, Claim, Verdict, Card: frozen dataclasses; every enumeration as an Enum); `engine/types.py` (FactSet, Fact, Span, HeldFact, Evaluation, Outcome); `contract/jsonschema.py` (gemini_schema, canonical, sha256_of, copied from v1's schema.py); `cptstudio/settings.py` (`APPRAISER_READ_TIMEOUT_SECONDS=480`, `APPRAISER_SEND_DEADLINE_SECONDS=510`, `JOB_DEADLINE_SECONDS['appraise']=560`: D49's settings [R:MO-3]); `tests/v2/__init__.py`, `tests/v2/test_types.py` | 0a | the types import with no v1 module; `mypy --strict` passes on both `types.py`; the suite is green |
| **1a** | SEG | `contract/segment.py` (units, hard-wrap joins, the short-token rule, sentence closures, framing); `tests/v2/test_segment.py` | 0b | boundaries on fixtures (initials and short titles, hard wraps joined and not joined, pages, forced splits, list enumerators); GI Note #8's three wrapped denials and its extent sentence each one unit; PAIR-4-W2's "At / this examination" and "endoscopic mucosal / resection" each inside one unit; closures of at most 12 units; the `[S\d+]` refusal; every unit's offsets reproduce its revision slice; the framed text is a pure function of the text [R:CO-3][R:CO-4] |
| **1b** | XS | `contract/extract_schema.py` (enumerations with definitions, LOCAL_SCHEMA_2 with `doubts` and `device_reached`, RESPONSE_SCHEMA_2, BOUNDS_2); `contract/extract_read.py` (strict read; item-level findings, a source over 12 units among them); tests | 0b | every refusal stage and bound by count, with a planted case each; item-level demotions; the RESPONSE schema derives mechanically [R:CO-1][R:CO-5][R:CO-8] |
| **1c** | GEO | `contract/geometry.py` (bind_words over consecutive units, bounded_positions, consecutive units, closures, section spans and containment, link geometry G1 with `placing`, G2-G6 with G5 restated); `contract/fold.py`; `contract/date_literals.py`; tests | 0b, 1a's interface | every link type with a positive and a negative fixture; section containment with mid-line labels and closers; G5 on GI Note #8's examination told in three sections (accepted) and on D36's W1S-399 reach from a biopsy sentence (inferred); the date parsers equal v1's on v1's literal fixtures (by value, the comparison run once in the test) [R:CO-2][R:CO-4][R:CO-6] |
| **1d** | STORE | `studio/models.py` (`EventInventory.appraisal_run`); `studio/migrations/0015_inventory_appraisal.py`; `interpretation/store.py` (v2 shapes; `appraisal_run_id` in BINDINGS; a v2 reader importing only `contract/`; v1's reader kept as `store._v1_reader`); tests, including the migration test | 0b | `migration_verdict` additive (nullable); `load` refuses every unknown version, shape, closed value and hash mismatch; `row` refuses any words not equal to the revision slice; no refused pass-2 row path exists |
| **1e** | CAT | `engine/anatomy.py` (containment, regions, disjoint, compatible over enumeration values); `engine/catalogue.py` (code_link, requirement groups, covers, umbrellas, defining kinds, technique classes, site classes, the EUS, enteroscopy and colonoscopy class tables, the family maps, ported as pure tables from `mapping.py`, `classes.py` and lexicon's tables); `tests/v2/test_catalogue_parity.py` | 0b | for all 163 codes every ported value equals v1's (computed from v1 in the test, by value); NoWordLists holds |
| **1f** | REQ | `scripts/gen_requirements.py` (reads the worktree's catalogue, profiles, mapping and classes tables; starts from B's generator and C's tags, Appendix A); `engine/requirements_table.py` (generated, committed); `engine/requirements.py` (templates, read-sets, CLAIMED, RANK, `dependencies(code)`); tests | 0b, 1e | the committed table equals the regenerated one; every code's tags match 4.3's rows; RANK pinned; CLAIMED's sha computed |
| **2a** | XP | `contract/extract_prompt.py` (INSTRUCTIONS_2 from 2.1's clauses; build_request with the unit framing); tests; the pins handed to the integration owner | 0a, 1a, 1b | each clause pinned by a grep test; the body has exactly v1's three keys; no member value, code, case or S4 phrase (a scan); the framing test |
| **2b** | CONS | `contract/consistency.py` (K1-K8, L1, Q1); tests | 1b, 1c | each rule with a violating and a satisfying fixture; K2 with a second performer in one session (no effect) and with an act's own other date (its session fact only); K8 on a reach given both polarities; L1 at day, month and year precision, at claim time against the document's own date, and re-judged with a member date [R:HO-7][R:HO-9][R:MO-5] |
| **2c** | APP | `contract/claims.py` (selection from CLAIMED; cards with type and closure only; TEMPLATES and STATEMENT_TEMPLATES; the CONTROLS generator with KIND_SIBLINGS, SESSION_SIBLINGS, CONTRAST_PLACES, pair controls, the completeness claim and UNCONTROLLED; claim content keys; the per-request bound; the seeded order); `contract/appraise_schema.py`; `contract/appraise_prompt.py`; `contract/appraise_read.py`; tests; pins handed to the integration owner | 1b, 1c, 1f | a byte-identical request for identical inputs; a template for every (attribute, state), statement-phrased for every attribute a denial is claimed on; a control for every READY- or exclusion-path attribute not on UNCONTROLLED (P-CONTROLLED), textually a real-claim form; pair controls in both directions; no label of pass 1's values on a card; no option, state, qualifier, doubt or unknown of pass 1 in the request (a scan) [R:HO-2][R:SC-B][R:SC-C][R:CO-7] |
| **2d** | FACTS | `engine/facts.py` (FactSet from the stored row, text stripped; holds, denied, established, possibly; `effective`); `engine/reading.py` (the Reading-compatible accessor layer); `engine/derive.py` (derive, context_of, document_date, routing_stand_in over facts); `interpretation/dates.py` (its `literals` import rewired to `contract/date_literals`); tests, `tests/test_interpretation_dates.py` updated | 1c, 1d, 1e | `mypy --strict` on facts and reading; no accessor returns a string; derive equals v1's on the fact-equivalent fixtures for date of service and member values |
| **3a** | SETTLE | `contract/settle.py` (S2, I, G, K, L, Q orchestration; inheritance; the doubt mapping; the 3.3 table; the cross-object rules; the unlisted drop rule and its records; health; verdicts bound by content key; the verification report); tests | 1b, 1c, 2b, 2c | the exhaustive truth table (state x doubt x check x qualifier x CLAIMED x verdict x control x attached x evidence, giving result and reason); S1's probes (a)-(e) each end unresolved; SC-A's three unlisted cases kept; a yes-man, an all-contradicts and an all-detached appraisal each refused [R:HO-1][R:SC-A][R:HO-4][R:MO-5] |
| **3b** | ADAPT | `interpretation/adapter.py` (the appraisal request kind from the revision plus the stored extraction bytes; shared envelope rules; per-purpose timeouts (pass 2 at D49's 480 and 510 s); the claim bound checked before a request is built; the v1 `prompt` and `read` imports removed); `interpretation/holds.py` (purpose `appraisal`); `interpretation/replay.py` (both purposes, by request sha256); tests (adapter, holds, replay) | 2a, 2c | the envelope rules for both purposes; the model pin; MAX_TOKENS is TOO_LONG; a bare 429 holds both |
| **3c** | WORD | `interpretation/wording.py` (additive: NEW_FACTS and MISSING for the five new facts; question and explanation builders from message ids; `quote(span)`); `studio/customer_api.py` (the translation entries for the new facts and the appraise progress step); tests, including the customer-output scan for provider and model names | 1f | v1's wording functions unchanged (v1's suites green); every message id has a sentence; no provider or model name on any customer string; `FORBIDDEN` matches the joined and underscored forms (`gemini_unknown`) and not clinical words that begin with a name (`corticosteroid`); no held-fact cause on any customer string [R:MO-2] |
| **3d** | PAIR | `engine/pairing.py`; tests | 2d | every row of 4.5 at every state; independence by any one established difference (HO-2's v3 document READY; "No prior colonoscopy." READY; BF17's excepted injection READY); a general denial covers any performer; possible statements pair (probe (a) beside a genuine snare: held); an unknown kind or target never sets apart; pair controls decide place independence (SC-B's short list: held); `claimed` turns apart into UNRESOLVED [R:HO-2][R:HO-3][R:HO-5][R:SC-B] |
| **4a** | EVAL | `engine/evaluate.py` (forked from `events.py` and `ercp.py`, readers deleted; SUPPORT; the code-specific rows; exclusion with C-10 geometry ported from `coverage_of` and `within_words`); `engine/questions.py` (RANK applied; the binding choice; question or explanation; held_facts; message ids); tests | 2d, 3c, 3d, 1f | v1's per-code rule tests re-expressed over settled fixtures; the C-10 shared-sentence fixture; Q1's act choice; the binding by rank and every candidate's witnesses (HO-8's two cases); a doubted act positive (HO-1's documents A and B held); no early return before the code rules (Q2) [R:HO-1][R:HO-8] |
| **4b** | COV | `engine/coverage.py` (forked: sessions from the sessions table, reportable, doubted with unlisted acts, bundling over part_relation, cause and lesion relations, reconcile, completeness, event_coding@2, service questions); tests | 2d, 3d | v1's coverage rule tests re-expressed; a contradicted act is never bundled out of its question (D3) |
| **4c** | CLS | `engine/classes.py` (forked: class fit over approach, through, anatomy types, reached and completion; act_elsewhere as the act's session); tests | 2d, 1e | v1's class tests re-expressed; a gastric pouch or Roux limb never makes the pouch class |
| **4d** | COMB | `engine/combination.py` (forked: base_included, base_within, competition with D163/D167 claims by `possibly`, procedure_day over date relations, other_class and unlisted acts, the separate statement, the modifier review, endoscopic rows); tests | 2d, 3d | v1's combination tests re-expressed; a held code never releases a rival |
| **5a** | ASSESS | `engine/assess.py` (forked: R1-R9 assembly, R6, the EUS code checks, participants unchanged, member answers, fingerprints over facts, the D22 fields, SERVICES_STUB, INVENTORY_PROBLEMS); `engine/measure.py` (9.1); tests | 4a, 4b, 4c, 4d, 1d | agreement adds proposers and nothing else (the pinned test); READY never without exact evidence; P-INDEP on the assess fixtures |
| **5b** | PIPE | `studio/jobs.py` (stage_interpret v2: extract-read, check and claim; stage_appraise; settle; keys; doors; reconcile; mark_stale; resume; STAGES and SENDING_PURPOSES; `facts` and `events_engine` imports rewired to `engine/derive` and `engine/assess`; `_change_context` on a revision with no v2 inventory stores the values and queues nothing, with the explicit re-check action of 6.2 [R:MO-4]; the appraise key from the request sha [R:MO-5]); `studio/progress.py` (STEP_OF and DETAILS for `appraise`); `studio/review.py` (`_failed_stage_state` for `appraise`); tests | 3a, 3b, 5a, 2d | replay stage tests for both passes; Stop between the passes; every failure row of 7.5; the reuse door per workspace; no inventory from pass 1 alone; D8 (a save sends nothing, on a legacy revision too; a new approval of a legacy assessment whose context changed is refused until the re-check) [R:MO-4] |
| **5c** | READ | `interpretation/overlay.py` (reads event_coding@2; `counted_codes` runs the engine over the persisted inventory with `effective()`); `interpretation/readers.py` (dispatch @2; every shipped v2 inventory version read as stored [R:MO-5]; the V1 branch labelled legacy_record, read as stored); `interpretation/report.py` (both runs, health, coherence, retired_calls); the management command `interpretation_report`; tests | 5a | read time equals assess time on every fixture; a v1 row is read as stored and blocked; the report shows both runs and the usage sums |
| **6a** | GUARD | `interpretation/sentinel.py` (RETIRED_MODULES, the RETIRED kind, expected_retired, PINNED_SIZES and RETIRED_SIZE, PROBE_CALL_RETIRED, the gate); `tests/test_guard_static.py` (WordsNeverDecide, NoWordLists, SingleCharacterGeometry, the `date_literals` pin, and the existing pins extended to `contract/` and `engine/`); `tests/test_guard_matrix_new_path.py` (the v2 worlds); `tests/test_guard_mutation.py` (the seven plants and a control); `tests/test_interpretation_sentinel.py` additions; `tests/v2/test_properties.py` (9.4); `tests/v2/test_retirement_manifest.py` | 5a, 5b, 5c | 5.7 measures 1-8 and 10 green, each with a positive control; each plant red naming only itself, applied and restored by sha256; the control green |
| **6b** | OPS | `ops/install.py` (`appraise` in CLOSE_STAGES and UNRUNNABLE_STAGES; the zero-v1-rows assertion, on v1 rows only; the retired probe in the in-image self-test; the receipts' note, D59's `reinstatable` limit kept); `ops/verification/*` (the D22 fields; both runs; `customer-denylist.json` with the letter-and-digit boundaries and their vectors); the D15 rollback test additions (6.4) | 5b, 6a | the rollback test passes on the test instance's restored dump; install, one v2 row, switch-back, re-install and a same-revision `app` all pass the assertion [R:MO-1][R:MO-2][R:MO-7] |
| **6c** | FIX | `tests/fixtures/interpretation_v2/**` (documents; constructed pass-1 and pass-2 answers per failure class, borderline filing and refutation case in three variants, 9.5; the gate-6 FactSet corpus; replay recordings after D2 and D3); `tests/v2/test_failure_classes.py`, `tests/v2/test_gate6.py`, `tests/v2/test_refutation_cases.py` | 5a | 9.5 green; variant (iii) recorded as residuals, never as passes |
| **7** | TOOLS (session directory, not the repository) | `gemini-migration/tools/v2/`: the recording harness (a cost cap per batch, the project-level stop with the installed site's reserve (7.6) [R:MO-6], concurrency one, labels, the freeze before reading), the replay runner, the acceptance scorer's adapter over `cpt-studio-measure@1`, the gate5 v2 diagnostic against c2e53f8e | 3b, 5a | the harness stops at its cap and at the project-level threshold; the scorer runs on a dummy export; replay reproduces an assessment byte for byte |
| **8** | integration owner | no code | all | in order: the full suite; D1; D2 and its gates (7.3 compaction or the owner if G-SIZE fails); D3; prompt and template iteration on development documents only (each a DECISIONS entry and a version bump); freeze the prompts and the development recordings (hashes committed); the owner told the budget against the cap (class d, 7.6), the legacy context-save loss (class b, 6.2) and the post-switch test-key question (class d) [R:MO-4][R:MO-6]; the acceptance run A by the acceptance owner's tool; the mandatory adversarial pass over the FINISHED DIFF (9.8); a PR, made a draft at the first doubt; CI; `scripts/merge-pr.sh`; a declaration committed in `docs/foundation/mutations/`; `scripts/run-ruled-mutation.sh` (the install); the website walk (9.9); the sealed c6 and c7 walks; the report. Nothing is called complete before the installed walk |

**Parallelism.** Wave 1 (1a-1f) has six agents; wave 2 (2a-2d) four; wave 3 (3a-3d) four; wave 4 (4a-4d) four; wave 5
(5a-5c) three, with 5b and 5c after 5a; wave 6 (6a-6c) three; step 7 runs beside waves 5-6. Step 2a may not start before
0a, whatever else is ready.

---

## 9. The test plan

### 9.1 What the engine exposes so the blind acceptance set can be measured (`engine/measure.py`, `cpt-studio-measure@1`) [C][B][A]

The acceptance set and its expected outcomes are frozen and blind to this design. The engine exports a superset of
everything an expected outcome can name, keyed by revision offsets (anchors are run-independent; Gemini's event ids and
unit ids are not), so the acceptance owner's comparator scores it without reading the engine. The export is operator data,
kept out of customer screens.

```json
{"schema": "cpt-studio-measure@1",
 "case": {"document_sha256": "...", "revision_text_sha256": "...", "run_index": 1},
 "runs": {"label": "fresh-acceptance | fresh-dev | replay | text-only | synthetic",
          "pass1": {"run": "<uuid>", "request_sha256": "...", "response_sha256": "...", "model": "gemini-4-argon",
                    "usage": {"prompt": 0, "candidates": 0, "thoughts": 0}, "usd": 0.0, "seconds": 0.0},
          "pass2": {"...": "the same"}},
 "versions": {"interpretation": "gemini-events@2/appraisal@1", "inventory": "gemini-inventory@2",
              "requirements": "cpt-requirements@1", "engine": "cpt-studio-events@2"},
 "encounter": {"date_of_service": {"value": "2026-11-09", "result": "supported"}, "service_questions": [],
               "unlisted": {"kept": [[2210, 2251]], "dropped": [{"units": [[2290, 2330]], "absorbed_by": "E6"}]},
               "doubts": [{"about": "date_relation", "objects": ["E3"], "basis": "unclear", "units": [[1180, 1252]]}]},
 "codes": [{"code": "45385", "origin": "corti | participant | second_review", "proposed_by": ["corti", "astra"],
            "status": "ready | needs_clarification | excluded",
            "acts": [{"event": "E3", "kind": "snare", "session": "X1", "anchor": [[1203, 1252]]}],
            "item": {"fact": "event_entry", "kind": "question | explanation", "subject": "E3", "anchor": [[1180, 1252]],
                     "cause": "appraisal:contradicts"},
            "held_facts": [{"fact": "event_performer", "subject": "E3", "result": "unknown", "reason": "doubt_unclear",
                            "cause": "reading_unknown", "rank": 7}],
            "trace": [{"requirement": "SUP.3", "truth": "U", "witness": {"subject": "E3", "attribute": "date_relation",
                       "result": "unresolved", "reason": "appraisal_unclear"}}],
            "exclusion": {"event": "E7", "fact": "status", "cover": "citation", "anchor": [[2001, 2040]]},
            "considerations": ["52", "25", "59|XS"]}],
 "facts": [{"subject": "E3", "attribute": "date_relation", "inherited_from": "N2",
            "claim": {"state": "supported", "value": "on_date_of_service"}, "result": "supported", "reasons": [],
            "verdict": "supports", "control": "contradicts"}],
 "relations": [{"statement": "E7", "act": "E3", "type": "CONTRADICTION", "row": "breadth all_of_kind"}],
 "health": {"appraisal": 0.97, "controls_coherent": 0.99},
 "guard": {"legacy_calls": 0, "retired_calls": 0}}
```

With it, the comparator computes, per code and per run:
- **wrong READY**: READY where the expected status is not; READY whose acts' anchors do not overlap the expected act
  (wrong act); READY whose deciding fact contradicts the expected one (wrong session, timing, entry or code class);
- **wrong exclusion**, with its deciding anchor;
- **dropped genuine question**: an expected contradiction, broad denial or doubt neither the item nor in `held_facts`;
- **unnecessary hold**: held where READY is expected, each with its `cause` (Gemini's unknown or doubt, a geometry or
  consistency failure, an appraisal verdict, control incoherence, a relation, a possible statement's included, a coding
  rule), so every hold has an owner;
- **absorbed unlisted statement**: an unlisted statement pass 2 reported that the drop rule absorbed, scored apart from an
  omission neither pass reported [R:SC-A];
- **READY recall** over the READY-expected codes, so an all-held result is visible and fails;
- **stability**: the same status per code across repeated runs of one document.

### 9.2 The gates

**The acceptance gate** is the acceptance owner's, frozen in `acceptance-a1/THRESHOLDS.md` (with amendment 1) before any
measurement; this design does not set it. As summarized in PLAN.md at 02:31Z: zero wrong READY, zero wrong exclusions and
zero dropped questions in every run; unnecessary holds at most 15% (independent documents and g1) and 25% (the regression
family), and never above c2e53f8e's rate; at least 70% of the READY-expected rows READY, so an all-held result fails;
stability at least 95%; no provider names. The THRESHOLDS cell "expected EXCLUDED, actual HELD" is reported as a SAFE
MISMATCH (HARNESS). Metrics are reported per failure family (T, E, G, S, N, A, C, Y, X, D, Q, O), per paraphrase family and
per meaning-changing variant, fresh and replay apart. c2e53f8e on the same documents is reported beside them as a
DIAGNOSTIC (owner amendment of 2026-11-09); a READY that c2e53f8e also gives wrongly still counts as a wrong READY, and a
regression (held to READY on the exact input) counts as a wrong READY whatever c2e53f8e's own correctness.

**Design-internal gates**, fixed here before any recording [J; revised R]:

| gate | measured on | passes when | if it fails |
|---|---|---|---|
| G-SCHEMA | D1, D2 | 0 whole-answer refusals for both passes | simplify the schema before any further batch (C's R15) |
| G-SIZE | D2 (its two largest documents included) | F1 at most 1.03 on the largest documents and at the median; predicted p99 pass-1 output at 19,460 characters at most 27,525 tokens; the largest claim set at most 85% of the per-request bound, which is recomputed from the measured output per verdict and the measured thinking [R:MO-3] | compaction (7.3; for pass 2, fewer controls on attributes that can only hold), then the owner (class b) |
| G-HEALTH | D3 | median establishment at least 0.90; control acceptance at most 5% of controlled pairs; no development document refused by the 3.2.6 thresholds, which are set from this distribution [R:HO-4] | claim templates, controls or the A-clauses revised on development documents (APPRAISAL_VERSION bump) |
| G-DOUBT [R:CO-1] | D3 (development documents with v1 recordings and expected outcomes) | on every development case whose expected outcome rests on a doubt (the registry's "uncertain time is never performance"; a conflict between two statements, W1S-499), v2's pass 1 reports it in every run, as a doubt, a contradicted fact or a silent slot on that attribute. v1's open-question count is printed beside v2's doubt count as a diagnostic, never as a target: a parity target would turn silent slots into doubts and tune toward over-doubting | the doubt clause (P7) revised on development documents |
| G-NOISE | D3 (development documents with FRESH expected outcomes, outside the acceptance hash list) | unnecessary holds at most 12%, and READY recall at least 75%, before the acceptance run is spent; reported by cause (`words_not_in_units`, `anchor_words`, `source_too_long`, `extent_inferred`, `cards_indistinct`, `unlisted`, `doubt_*`, `relation:possible_statement`, `appraisal:*`) | the dominant `cause` is repaired (prompt, templates, geometry, a coding rule), never settle weakened, never a word list |
| G-GUARD | every measured assessment | `legacy_calls = retired_calls = 0` | a defect; the sentinel refuses the write |

**The release gate** (before the PR leaves draft): the acceptance gate and every design gate pass; every wrong READY or
wrong exclusion found anywhere is investigated and repaired in the prompt, the schema, the claim templates or a coding
rule (never a word list, EB4) and re-measured.

### 9.3 Unit tests (TEXT-ONLY and SYNTHETIC; CI; no network) [C][B][A]

- **segment**: boundaries (initials and short titles, hard wraps joined and not joined, pages, forced splits); sentence
  closures; the `[S\d+]` refusal; offsets reproduce slices; GI Note #8's wrapped denials and PAIR-4-W2's wrapped EMR
  sentence each inside one unit [R:CO-3][R:CO-4].
- **extract_read, appraise_read**: every refusal stage and bound by count; item-level demotions; the evidence check.
- **geometry**: each link type, positive and negative; E2's wrap (a label and the act in one paragraph, read as the
  nursing entry); E4 (two labels on one line give two sections); E3 (an "as above" restatement does not move the entry);
  section containment with closers; G3's statement tie; G4's inheritance edge; G5's examination evidence.
- **consistency**: K1-K8 each violated and satisfied; L1 at day, month and year precision, at claim time against the
  document's own date; the re-judge with a member date.
- **claims**: byte-identical requests; the seeded order stable; controls textually indistinguishable (every control
  sentence form is a real-claim form); no unknown, doubted, contradicted, qualified, failed or unclaimed fact rendered; a
  scan finds no option, state, qualifier or doubt of pass 1; statement-phrased templates for every attribute a denial is
  claimed on; P-CONTROLLED; pair controls in both directions; the completeness claim only for an empty upper-EUS station
  list; no pass-1 label on a card; same-anchor cards quoting each event's words [R:HO-2][R:SC-B][R:SC-C][R:CO-7].
- **settle**: the exhaustive truth table; the doubt mapping (stated, unclear, conflict, whole); K8; inheritance per act;
  the cross-object rules; the unlisted drop rule (SC-A's three cases kept); the health refusals; verdicts read by content
  key after a check change; S1's probes (a)-(e) end unresolved [R:HO-1][R:HO-9][R:SC-A][R:HO-4][R:MO-5].
- **facts, pairing**: each predicate (`possibly` on a doubted or unestablished status and kind; `apart_by_lesion`,
  `apart_by_place`); each row at each state; independence by any one established difference; possible statements; the
  general denial; `claimed`; C-16; the unknown target and kind [R:HO-1][R:HO-2][R:HO-3][R:HO-5][R:SC-B].
- **requirements, evaluate, questions**: every 4.3 row met, unmet and established-otherwise; exclusion only by citation
  (C-10's shared-sentence fixture); attempted never excludes (C-9); exceptive never excludes (C-7); RANK for every pair of
  ranks; the binding choice (Q1); question versus explanation; held_facts recorded.
- **coverage, classes, combination**: v1's rule tests re-expressed over settled fixtures (base, base-within, competing with
  D163 and D167, C-3 with a separate same-day session and with an unlisted act, the separate statement negated, the
  modifier review, the classes).
- **assess**: participants' agreement adds proposers only (the pinned test kept); fingerprints stable; the D22 fields;
  SERVICES_STUB and INVENTORY_PROBLEMS written; no provider name on a customer string.
- **pipeline**: replay stage tests for both passes; Stop between the passes; every failure row of 7.5; the reuse door;
  no inventory from pass 1 alone; D8.
- **read time**: the overlay equals assess on every fixture, with `effective()`; a v1 row read as stored and blocked.
- **store and migration**: the additive verdict; version and sha refusals; earlier v2 inventory versions read as stored;
  the rollback image against 0015 (a CI job with the old image, as the 2026-11-09 install did) [R:MO-5].
- **ops**: the zero-v1-rows assertion across an install, a v2 row, a switch-back, a re-install and a same-revision `app`;
  the denylists' letter-and-digit boundaries against `gemini_unknown` and `corticosteroid` [R:MO-1][R:MO-2].

### 9.4 Property tests (hypothesis, in CI) [B, with J; revised R]

| property | statement |
|---|---|
| P-MONO | for random settled FactSets and random weakenings, the READY and EXCLUDED sets never grow and the claims never shrink. The weakenings: an established fact to unresolved; an established control to not rejected; an added doubt (stated, unclear or conflict) on any fact [R:HO-1]; a deleted member of a multi-valued list (places, stations, reached), the list's completeness claim and pair controls left as they were [R:SC-B]; an event's established status to unresolved, which makes it a possible statement [R:HO-3]. Deleting a whole event is not a weakening, and REFUTATIONS.md (SC-B) gives the input that shows why |
| P-INDEP | perturbing any fact outside `dependencies(code)` leaves the code's status, item and held facts unchanged |
| P-INDEP-SETTLE [R:HO-7] | the same from constructed pass-1 and pass-2 answers through settle: perturbing one object's fact changes another object's facts only through the listed cross-object rules |
| P-TEXTFREE | with R1's results and the kept spans given, replacing every character of the revision text and of every stored slice with `x` (same lengths) leaves every outcome, item fact key, held fact and witness of the per-code rule, the combination, coverage and questions byte-identical; only rendered text changes [J: B's form ignored that R1 reads the text by design] |
| P-DET | identical inputs give byte-identical assessments (sha256) |
| P-READSET | the attributes each rule reads (a recording proxy over the FactSet accessors) are a subset of CLAIMED for that object class |
| P-CONTROLLED [R:SC-C] | every attribute that a READY or exclusion path reads (P-READSET's recording) has a control generator, or is on the pinned UNCONTROLLED list with its reason |
| P-DEMOTE | for any appraisal answer, every settled result is at most pass 1's claim in information order: pass 2 never creates, changes or upgrades a fact, and a doubt never upgrades one either |
| P-UNKNOWN-TARGET | for every combination of row states, an unknown, unresolved, doubted or contradicted target on either side, or a pair control not rejected, never makes the target row yield INDEPENDENT |
| P-UNKNOWN-KIND [R:HO-5] | a statement whose kind is not established pairs with at least every act of its session's family that the same statement with an established kind would pair with |
| P-ANY-ROW [R:HO-2] | a pair with one row proving independence is INDEPENDENT (unless `claimed`) whatever the other rows' states; a pair with none is never INDEPENDENT |

### 9.5 Gate 6 and the failure classes as fixtures [B][C]

**Gate 6** (engine only, offline, unit speed): a corpus of hand-built settled FactSets. Being facts, they carry no words:
paraphrase invariance holds by construction there, and the paraphrase risk lives in Gemini, which the recordings measure.
It holds every template x requirement x state (at least one T, U and F case per requirement of every code, generated from
Appendix A) and the directive's named cases as facts. It gates every engine change in CI and does not replace the
acceptance set.

**The failure-class fixtures** (`tests/fixtures/interpretation_v2/`): for each of S4's 52 classes and 21 borderline filings,
three variants of constructed pass-1 and pass-2 answers:

| variant | pass 1 | pass 2 | expected |
|---|---|---|---|
| (i) correct | the right filing | supports; controls rejected | the documented outcome (READY, HELD on the named fact, or EXCLUDED) |
| (ii) caught | the attested or constructed misfiling of the class | contradicts or qualified | HELD on that fact with one item; never a wrong READY or a wrong exclusion |
| (iii) shared misreading | the misfiling | supports it (a correlated error) | the outcome the engine gives, RECORDED AS A RESIDUAL; never counted as a pass; its rate is what the acceptance set measures |

Plus the owner's checklist examples, each as (i) and (ii): the original seven cases and the four reported Gemini slips
(unsupported historical extent, biopsy-site conflation); the scar; historical and current acts; different lesions at one
site; technique-specific denials; different performers; future purpose (C-13); guidewire-versus-scope extent; genuine
contradictions; "No polyp was removed today."

**The refutation's cases** [R], each as (i) and (ii), and as (iii) where the finding names a shared misreading: probe (a)
beside a genuine snare (HO-3); the stated doubt beside a base code, the office note with a doubted same-day sigmoidoscopy,
and a cited rectal biopsy denial beside a doubted sigmoid biopsy, which must not exclude 45380 (HO-1: one fixture per
consumer of the doubt arm: the positive candidate, doubted and base_included, the C-3 procedure day and 4.6(5)); the
historical denial beside a current act (v3), "No prior colonoscopy." and BF17 (HO-2); the
sibling-misfiled denial (HO-5); the stent exchange and the biopsy-then-snare sentences, and the shared denial anchor
(SC-A, HO-6); BF6 with an empty station list, and the short place list beside a rectal denial (SC-B); a balloon
sphincteroplasty filed as a sphincterotomy (SC-C); a nursing note with a summarizing impression (SC-D); two performers in
one session (HO-7); the two binding cases (HO-8); a reach given both polarities (HO-9); GI Note #8's wrapped denials and its
extent across three sections (CO-3, CO-6); PAIR-4-W2 (CO-4, CO-5); fb08 (CO-7); v6 (CO-8); BF2, W1S-499, f2-after-002,
twins-015, W1S-222 and C2MEM-031 (CO-1, CO-2). Every engine case among them is also a gate-6 FactSet.

These are engine and settle tests. They prove what the engine does given a filing, and nothing about Gemini's reading;
they are never acceptance evidence.

### 9.6 Recordings, labels, and development kept apart from acceptance [C][B][A]

- **Development documents** are synthetic documents whose sha256 is NOT on the acceptance owner's exclusion list: FRESH-1
  and FRESH-2 inputs, the U32 registry inputs, the refutation rounds' case files. Prompt and template iteration uses only
  them; every change is a DECISIONS entry and a version bump.
- **D2 and D3 carry the refutation's documents** [R:CO-1..CO-8], each only when its sha256 is not on the exclusion list
  (otherwise its nearest development variant replaces it): in D2, GI Note #8 and PAIR-4-W2 (the size bound, the wraps,
  the long sentences, the extent across sections); in D3, C2MEM-031, W1-u29b-rel-p3-aside-of-twins-015, W1S-222,
  W1-u30a-rel-f2-after-002, W1-u30a-rel-f4-unread-before-017 (BF2), W1S-499, W1S-465, fb08 and
  v6_altered_anatomy_guidewire.
- **The acceptance run** is made by the acceptance owner's tool from its manifest; builders never read its documents or
  expected outcomes.
- **Labels:** `fresh-dev`, `fresh-acceptance`, `replay`, `text-only`, `synthetic`.
- **Each batch's manifest** (case, document sha256, both requests' and responses' sha256, usage, latency, model, finish) is
  hashed and committed BEFORE evaluation.
- **Replay** reproduces the settled inventory and the assessment byte for byte; a changed prompt, schema, segmentation or
  claim rendering fails loudly ("No recorded response for this request.").

### 9.7 The guard tests

Section 5.7, measures 1-10: the deny set and its pins, the positive controls, the write gate, the three static rules, the
typing fence, P-TEXTFREE, the seven mutation plants and their control, the matrix with zero under every label, and the
retirement manifest.

### 9.8 The refutation of the finished diff (mandatory; told to REFUTE; FILE:LINE plus a concrete input and the wrong output; NOTHING FOUND permitted; every finding verified first-hand) [C][A][B]

1. **False READY through agreement**: a shared misreading; pass 1's flags leaking into the claims; distinguishable
   controls; evidence attachment that passes on the wrong statement; an inherited fact appraised on the wrong statement.
2. **The deterministic layer**: segmentation, link geometry, section containment, inheritance, L1, the settle table:
   "find an input where a fact is established that should not be, or a supported fact is demoted for no reason".
3. **The engine**: required facts, the outcome function, the rank and the binding, unrelated codes, the doubt arms
   (D163-class releases), broad denials, unknown targets, the ERCP, EUS and enteroscopy class rules, the requirement table.
4. **Readers under a new name**: any text access, word list, phrase test or vocabulary comparison in `contract/`,
   `engine/` or the kept modules; the allowlist of 5.6; the copied tables.
5. **The guard, compatibility and operations**: a retired reader reachable on any new-path world (the read-time path
   included); store binding; the migration; rollback; the v1-row policy; Stop and resume; the holds; confidentiality.

The PR is made a draft at the moment of doubt (AGENTS.md), not after triage.

### 9.9 The installed walk and the report (the directive's completion) [B][C][A]

1. **Upload** PDF and Word documents through actual ingestion, on the installed site.
2. **Progress, truthfully**: both passes shown as stages, named by function, never by provider.
3. **Review**: exactly one item per held code (questions and explanations); READY codes approvable with the explicitly
   labelled synthetic approval and the acknowledgement.
4. **Save, reload.**
5. **Download the reports**: their content equals the saved decisions, with no provider or model name, joined and
   underscored forms included (`gemini_unknown`) [R:MO-2].
6. **Operator evidence** (5.7 measure 9): legacy_calls 0, retired_calls 0, both runs `gemini-4-argon`, the versions.
7. **Availability and rollback**: the old image starts against the migrated database and shows v2 rows fail-closed.
8. **The report**: the installed revision, the remaining defects, the incorrect approvals, the unnecessary holds, the
   usage and the actual download results. The migration is not complete at the design, recording or offline-test stage.

---

## 10. Risks, and what would make each check fail

| # | risk | control | what would make the control fail |
|---|---|---|---|
| R1 | **The two passes share a misreading** (same model, 3.7) | independent instruction, information and stance; controls; measured on the paraphrase and meaning-changing families; fixture variant (iii) | a family where pass 2 supports a wrong pass 1 (G1 above 0); then a different appraisal model is the owner's call (classes a, d); no word list is the repair |
| R2 | **Unnecessary holds from appraisal noise**: unclear verdicts, detached evidence, incoherent controls on correct facts. A code needs about 6-8 established facts; at 1% noise per fact that adds about 6-8% holds | claims only where a rule reads (CLAIMED); claims at a rule's granularity (date relation, not encounter detail); `attached` defined for frame-sourced facts; G-HEALTH and G-NOISE on development documents before the acceptance run; every hold carries its cause | G-NOISE missed: the dominant cause is repaired in templates, controls, A-clauses or geometry and re-measured on development documents, never by weakening settle |
| R3 | **Output size**: F1 above 1.03 refuses Note #8 (19,398 characters) at the 20,000 bound | units, slots, section inheritance; G-SIZE on D2; compaction levers (7.3) | a live document over the bound after compaction: an accepted-capability loss only the owner may accept (class b) |
| R4 | **Section misfit** (Gemini starts parts in the wrong place, files a wrong occasion, or leaves a narrative part's occasion or performer empty) makes many inherited facts unresolved or unknown, near all-held for that part | per-act appraisal catches misinheritance as a hold, not a READY; G2 fails per section; K7; the `inherit_unattached` and appraisal-cause counts | a high hold share caused by inheritance on D3: the section clauses of 2.1 revised on development documents |
| R5 | **Cost**: about 1.8x v1; doubling from 2026-12-01; the acceptance run of about $75-150 | per-batch caps; usage per request; the budget of 7.6; reported to the owner (class d) | spend near the cap: batches stop at their own caps |
| R6 | **Latency**: about 2x v1 (53 s median, about 336 s at worst; a pass 2 with the largest measured thinking about 356 s) | deadlines below the stale sweep, pass 2 with D49's 480-second read [R:MO-3]; Stop between the passes; truthful progress | a pass 2 over 480 s: UNKNOWN, then reconcile; the thinking tail measured in D2 and D3 |
| R7 | **Yes-bias on a single verdict**: the pinned UNCONTROLLED attributes (3.2.3), each listed with why a single verdict there can only hold | controls generated for every other READY- or exclusion-path attribute; P-CONTROLLED in CI; attachment and evidence still required [R:SC-C] | a wrong READY traced to a single verdict: its attribute leaves UNCONTROLLED (APPRAISAL_VERSION, a pass-2 re-send only) |
| R8 | **Omission**: an act or statement neither pass reports (O1, Y7) | `unlisted` with kind and session, dropped only when an event of the same nature and kind covers its unit, every drop recorded (3.2.6) [R:SC-A]; a missed attribute is unknown, so it holds; a short list never sets anything apart [R:SC-B] | a wrong READY whose missing evidence pass 2 did not list (an omission residual), or listed and the drop absorbed (a defect of the drop rule), measured apart |
| R9 | **Segmentation artifacts**: forced splits, the `[S\d+]` collision, a wrap continued by an uppercase letter, a sentence longer than its 12-unit closure | hard wraps joined, initials kept, words across consecutive units, the sentence closure on every claim and card (1.2) [R:CO-3][R:CO-4]; the collision refuses visibly; pass 2 judges the whole statement | a geometry failure on a legitimate citation (a hold, G-NOISE by cause: `words_not_in_units`, `anchor_words`, `source_too_long`), or a negator outside the closure (pass 2 must still read the paragraph) |
| R10 | **A fail-closed arm lost in the fork** | rule bodies forked, not rewritten; v1's rule tests re-expressed; `possibly` for every [G*] input; P-MONO; the D163 tests; gate 5 v2 as a diagnostic against c2e53f8e | a release found by lens 3 or the diagnostic: restored in the engine |
| R11 | **The requirement table, CLAIMED and the rules drift apart** | one generator (1f); P-READSET; gate 6 per template; the pin that forces an APPRAISAL_VERSION bump when CLAIMED changes | an unclaimed attribute read by a rule: P-READSET fails in CI (an omission can only hold at runtime) |
| R12 | **A same-date separate-encounter procedure supports its code** (T2; 4.13) | recorded parity choice; c2e53f8e READY; lens 3 | an acceptance expectation that holds it: re-ruled as a coding rule, never by a reader |
| R13 | **C-3 counts any performer's same-day act** (parity) | stated, not decided here | the owner rules otherwise (class a): a one-line change in `engine/combination.procedure_day`, re-measured |
| R14 | **One item per code** means more round trips | held_facts visible to the reviewer; an answer can still exclude | a UX complaint, not an interpretation defect |
| R15 | **Appraisal health refusals repeat** on one document (paid retries) | the threshold in APPRAISAL_VERSION; no automatic retry (D11) | a document refused twice: recorded, shown truthfully, measured |
| R16 | **Development leaks into acceptance** | the exclusion list of hashes (0a); the acceptance owner runs the set | an incomplete list: the acceptance owner verifies it before the run |
| R17 | **The API refuses the larger response schemas** | batch D1 is the probe; one call | a 400 at D1: the schema is simplified before any batch |
| R18 | **Pass 1's false contradictions cannot be relieved by pass 2** (by design) | P8 of 2.1 defines sequence versus contradiction; measured in G-NOISE | a high false-contradiction rate: repaired in the prompt, never by letting a model dismiss contradictions |
| R19 | **Build size and integration** (two new packages, a forked engine, two stages) | the wave plan with exclusive files; pure functions with typed interfaces; the suite green at every merge; gate 6 | an integration defect found late: the refutation lenses and the matrix find it before merge |
| R20 | **Dropping the word-reading shims changes outcomes against c2e53f8e in both directions** | each dropped shim named (4.13); the diagnostic compares with c2e53f8e; a regression counts as a wrong READY | a held-to-READY regression on an exact input: repaired by a coding rule over facts |
| R21 | **Gemini commits a value and keeps its doubt elsewhere** (CO-1) | `doubts` shaped like v1's open questions; a doubted fact is unknown and its status possibly positive; G-DOUBT | G-DOUBT fails: P7 revised on development documents; a wrong committed value with no doubt rests on pass 2 |
| R22 | **Placing sentences** are not filtered by geometry (CO-2) | per-act appraisal with its control; the placing cases in D3 | a family where pass 2 attaches a placing sentence to the wrong part: the P4 and P10 clauses revised |
| R23 | **The spend cap is shared with the installed site after the switch** (MO-6) | the reserve rule; the owner's budget statement before A; the test-key question (class d) | a post-switch batch reaching the cap: every new upload pauses (D39) until the reset or the owner raises the cap |
| R24 | **A legacy encounter's context change needs an explicit re-check** (MO-4) | values stored, new approvals of the stale assessment refused, the re-check action, the owner told (class b) | a member surprised that a re-check needs re-review: a UX finding, never a silent loss |
| R25 | **Possible statements add holds** (HO-3) | independence by any one established difference; a possible statement's own established target | `relation:possible_statement` dominant in G-NOISE: the status templates or controls revised, never the pairing weakened |

---

## Appendix A. Every catalogue code's required facts

Step 1f generates the committed table from the worktree's own tables (`studio/gi/catalogue.py`, `profiles.py`,
`mapping.DEFINING`, `DILATION_SITES`, `examination_class`, `eus_tract`, `classes.code_class`). Two generated tables,
read only, are its starting points and must be reproduced:
- design C's per-code tags, in the tag names of 4.3: `design-v2/designs/C-two-pass-data/required_tags.md` (sha256
  `3b447b4244ca82144d0e13cc1e5e45389812acc961f291bea217db6181fb83a4`), from `required_by_code.json` (sha256
  `26038cabad0617761c468101b59009877749dd8d3706f3375294902231faf634`);
- design B's templates per code: `design-v2/designs/B-requirements-data/codes.json` (sha256
  `8fb878f3bcaa7171ac48ac35046d8dc8e37cefc95f350db720b986ea18ea4008`) and `requirements-table.md`.

**Templates** (B), each code in exactly one: BASE 11 (43197, 43200, 43235, 43260, 44360, 44376, 44380, 44385, 44388,
45330, 45378); ACT 97 (the therapeutic endoscopic codes); EUS_EXAM 6 (43231, 43237, 43259, 45341, 45391, 44406); EUS_ACT 8
(43232, 43238, 43240, 43242, 43253, 45342, 45392, 44407); ADDON_ACT 2 (43273, 91013); FEEDING 8 (43762, 43763, 49440,
49441, 49446, 49450-49452); TEST 15 (capsule, motility, reflux, anorectal); EM 13 (the office E/M codes); EM_ADDON 1
(99417); RECOGNISED 2 (99152, 99153). Route (b) codes (46221) and every unprofiled code (route (d)) are held, never READY.

**Every code** needs SUPPORT (4.3) for each non-examination kind it covers (the examination's SUPPORT for base and
exam-only codes, with ATT), the bundling rules, R7 and R9. **The code-specific tags** are 4.3's rows: R6 per family
(extent: egd, enteroscopy, flex_sig; COLFULL: colonoscopy; target: eus; cannulation: ercp; em_basis and context:
office_em; none: capsule, motility, reflux, anorectal, feeding tube); DEF for the D27 narrowed codes; TECH for the balloon
and wire_bougie codes; SITE for the dilation codes; STRUCT for 43240; ROUTE for 43253; TRACT for the upper and lower EUS
codes; STATIONS for 43242 and 43259; LIMITED for 43231, 43232, 43237 and 43238; LOWER for the lower EUS codes; ENT for
44360-44386; YIELD for 43264; XCHG for 43274, 43275 and 43276; CAUSE for every code covering bleeding_control (C's table:
43227, 43255, 44366, 44378, 44391, 45334, 45382); C3+SEP for the office E/M codes; ADDON for 43273, 91013, 99153 and
99417; D80 for 99152 and 99153.

The test of step 1f asserts that the committed table equals the regenerated one and that every code's tags follow from
4.3's rows; gate 6 generates its T, U and F cases from it.

---

## Appendix B. Where each part came from, and why

| part | from | why (judging.md section 5 gives the full reasoning and the rejected alternatives) |
|---|---|---|
| units cut by CPT Studio, cited by id (1.2) | C; R (hard-wrap joins, the short-token rule, sentence closures, words over consecutive units: CO-3, CO-4, CO-5) | a claim cites its anchor's whole sentence; no passage copies in the output; source integrity is an id check |
| the fact shape with slots; `basis` folded into the state (1.3) | C, compacted (J) | the four states kept apart at the lowest output cost |
| sections with owner and role (1.4) | B | entry ownership by containment, no label grammar; mid-line labels; closers |
| section occasion and performer, inherited by acts and appraised per act (1.5) | A (inheritance), J (per-act appraisal, entry by `restates`) | the output saving lands where the size bound binds, without a default |
| sessions as objects; instrument; through; reached_anatomy; encounter (1.4) | C, B, J | act-only sessions; no region moves; guidewire-versus-scope extent; the E/M encounter |
| timing as a date relation per act, the encounter relation per session (1.4, 2.1 P10) | J | one judgment per rule input; fewer claims |
| `access_outcome` (1.4) | B | ERCP access is Gemini's judgment; the D127 shim leaves |
| the prompt clauses (2.1) | C, with A's sections and B's attribute rules | the most complete normative text; each clause closes a recorded class |
| the borderline filings, stated (2.2) | B, C | ambiguity is reported with options, never chosen |
| deterministic checks (3.1) | C (S, I, B, G1, G3, L1, X), A (G4, G5, K2, K4-K6), B (G2, K3, K7), R (K8; G5 restated after D36; K2 narrowed; `placing` geometry) | where a source sits and whether Gemini's values agree; never meaning |
| the appraisal pass, controls, coherence, evidence check, unlisted, health (3.2) | C | the directive's verification item, literally |
| claims chosen by read-sets; unclaimed facts unresolved (3.2.1) | B (read-sets), J (settlement) | cost and noise only where a rule reads; an omission can only hold |
| sibling-kind and contrast-place controls (3.2.3) | J | a wrong kind or place is a wrong READY path |
| unlisted with kind and session (3.2.6) | C, B | O1 and Y7 beside base and extraction codes |
| pass-2 refusals on the run, not the inventory (3.2.6, 6.3) | J | additive migration; no unique-key collision on retry |
| the text-free typed FactSet (4.1) | B | text-freeness at the boundary, by type |
| the forked rule bodies (4.1, 5.5) | A, J | v1's fail-closed arms preserved |
| SUPPORT and the code-specific rows (4.3) | C (4.0, 4.1), B (4.5), A (G7, the stations fallback) | the coding rules that stay, over facts |
| the outcome function with all held facts collected (4.4) | A, C | no early return; every hold has its causes |
| the pairing table (4.5) | C (rows, `claimed`), B (a general denial covers any performer), A (exceptive without the act) | contradictions kept and asked as contradictions; an unknown target never apart |
| exclusion by an established negative and citation (4.6) | all three | EB3's markers leave; C-7 and C-10 stay |
| one item per code, RANK, question versus explanation, the binding (4.8) | A (rank, closest act), B (question versus explanation), C (one row, held_facts, kept-span overlap) | the directive's one focused explanation or question |
| the five new question facts (4.8) | C | an existing path (`wording.NEW_FACTS`) |
| parity shims dropped and kept (4.13) | B (P8), A (R12), J | rules, not readers |
| deny the 17 modules in place; the manifest; the static rules (5.0, 5.7) | C (mechanism), B (manifest, stronger rules, typing), A (single-character geometry, display data flow) | nothing renamed or moved; a rewritten veto is caught statically |
| migration 0015, rollback, CLOSE/UNRUNNABLE stages (6) | C, corrected by J | additive; the old worker never meets a v2 stage |
| `engine/derive.py` (4.7, 5.5) | J | `jobs.py` calls `facts.derive`; neither B nor C replaced it |
| the cost model and the size-bound gate (7) | C's model, J's parameters and G-SIZE | Note #8 must fit |
| the exposure with trace and cause (9.1) | C, B, A | every unnecessary hold has an owner |
| property tests (9.4) | B, restated by J (P-TEXTFREE), added by J (P-DEMOTE, P-UNKNOWN-TARGET) | mechanical proof of the hold policy and the text-free engine |
| gate 6 and the three-variant fixtures (9.5) | B, C | engine regression net; the shared-misreading residual recorded, never counted as a pass |
| every change marked `[R:...]` | the refutation of 2026-11-12 | `REFUTATIONS.md`, finding by finding, with what the judge verified first-hand |

---

## Appendix C. S4's failure classes under this design

"Caught by" says which layer turns the class's misfiling into a hold: D = deterministic checks, P2 = the appraisal, E = the
engine's coding rules over facts. "Residual" is what remains Gemini's reading and is measured, never caught by a check.

| class | deciding fact | v2 rule | caught by | residual |
|---|---|---|---|---|
| T1-T3 (same-day timing) | date relation; the session's encounter | on_date_of_service for any same-day act; C-3 reads the date relation only | P2 (the date-relation claim and its control, statement-phrased for a denial), L1 | a date relation both passes misread |
| T4 (an unknown-date act beside a visit) | `other_class`, date relation | an act possibly positive with no established date relation is undatable: `event_time` | E | an act filed `test` or `evaluation` wrongly by both |
| T5, T6, D3 (an unverified earlier whole absorbs today's act) | date relation; `part_of`; a doubt | a bundling into a whole read by `possibly` is asked, never silent; a contradicted act is never bundled (rank 1); BF2's vague "Once" carries a doubt, so the act is held, never excluded [R:CO-1] | E, D (the doubt) | a vague timing both passes read as plain |
| T7, Y1-Y6 (yield) | `yield` per act; qualifiers | YIELD; contradicted yield is a conflict; a hedged yield is unresolved | P2, Q1, E | a yield both misread |
| T8 ("At that time") and placing sentences | `antecedent` link; `placing` for a later sentence or another part [R:CO-2] | the act takes the antecedent's or the placing sentence's occasion | D (G1), P2 (per act) | a wrong antecedent or placing both accept |
| T9 ("As previously noted") | the section's occasion | not another time (2.1 P10); the pairing gives a CONTRADICTION | P2, E | - |
| E1-E5 (entry ownership) | `section.owner`; containment; a `restates` role (1.5) | SUPPORT row 5; `event_entry` (an explanation when another role; a question when a restatement's role is unresolved) | D (G2), P2 (the entry claim, the restatement-role claim [R:SC-D], their controls) | an owner or a role both misread |
| G1 (43253 on a tattoo) | `technique.route`; places never a reference point | ROUTE | P2 (route control) | - |
| G2 (an upper code on a lower EUS) | `session.tract` | TRACT; same-tract base questions | P2 (tract control) | - |
| G3 (an FNA as a drainage step) | `part_relation access_for` | drainage_step bundling; unknown is asked | P2, E | - |
| G4 (an unlisted EUS act) | doubted acts; `unlisted` | base_included doubt | P2 (unlisted), E | an act neither pass reports |
| G5 (labs, an H&P counted) | `other_class` | not a procedure | P2 | - |
| S1, S2 (stations) | `session.stations`; the completeness claim | STATIONS (all three supported, or an empty list with an established completeness claim), LIMITED | P2 (station controls; the completeness claim and its control) [R:SC-B] | a limitation both passes miss |
| S3, N1-N3 (session) | `event.session`; `part_of_session`; K3 | never moved; an unknown session asks `procedure` | D (K2, K3), P2 (session control), E | a session both misread |
| S4 (terminated ERCP) | `completion` | 52/53 consideration | P2 | - |
| A1-A3 (pouch, bypass, route) | anatomy types; `approach`, `through` | ENT | P2 (type and approach controls) | - |
| C1-C4 (bleeding control) | `purpose`, `cause`, `cause_event`, `part_relation adjunct_of` | CAUSE; procedural-adjunct bundling | P2 (purpose and cause controls), E | - |
| X1 (a title-named exchange) | the anchor rule; components | a title is never a statement; XCHG | D (G6, I3), P2 | - |
| D1, D2 (denial scope) | `breadth`, `excepts`, `covers`, targets | K1 (exceptive needs excepts); statement-phrased claims [R:HO-2]; independence by one established difference; pair controls for place [R:SC-B]; an unknown target or kind is UNRESOLVED; `claimed` turns apart into UNRESOLVED | D (K1), P2 (breadth, target and pair controls), E | - |
| Q1-Q4 (question policy) | - | RANK; the binding by kept-span overlap; one item per code; no early return | E | - |
| Q5-Q7 | - | unchanged (answer binding, listing and display policies) | - | out of scope |
| O1, Y7 (omission) | `unlisted` | rules 1-5 of 3.2.6; an entry dropped only by same nature and kind, every drop recorded [R:SC-A] | P2 | an act or statement neither pass reports |
| hard-wrapped negators (CO-3) | the anchor's sentence closure | a wrap joined (1.2 rule 2) or carried by the closure (rule 6) | D | a sentence longer than its 12-unit closure |
| doubts beside committed values (CO-1, HO-1) | `doubts` | unknown or contradicted per named fact; a doubted status is possibly positive | D (settle), E | a doubt pass 1 does not report and pass 2 does not catch |
| a misfiled denial beside a genuine act (HO-3) | the status; possible statements | an event whose status pass 2 did not establish pairs as a DOUBT | P2, E | a misfiling both passes accept |
