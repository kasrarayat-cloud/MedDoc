# CPT Studio completion repair (owner directive 2026-11-06): stage 1, the exact remaining failures

Session a12d8fb3, 2026-11-06, 06:50Z to 08:20Z. Checklist item 1 (`CPT-HARNESS-CHECKLIST.md`, "Completion repair,
2026-11-06"); contract C1 (`cpt-studio/HARNESS.md`, "Completion repair (2026-11-06)").

The installed release is `fd8040d71e44`. This branch's `cpt-studio/studio` is byte-identical to it: only the harness's
documentation differs. Every FILE:LINE below is relative to `cpt-studio/` at that tree.

## How it was reproduced

**The data:**
- one read-only `pg_dump` of the live database, through its own container, in a read-only transaction;
- one throwaway copy restored on the test server (`cptc_repro_20261106t065244z`, port 55461; the live port is refused
  by every tool).

Nothing on the live site was written, and nothing was sent to any provider. The dump and the exports are session
scratch, reaped at close-out.

**Recompute, not reassess.** Re-assessing a retained case through the pipeline returns the stored assessment, because
the assess job's key de-duplicates identical inputs. So that was not counted as a reproduction. Instead,
`tools/recompute.py` gathers exactly the inputs `jobs.stage_assess` gathers for a re-assessment and calls
`jobs._assess_child`, in memory, on the installed code:
- the Corti run;
- the participants' frozen first readings and peer reviews, re-read as recorded;
- the context facts, the service date, the reference lookup and the confirmed findings.

**All four retained cases recompute identical to their stored final assessments.** The cases are 39f0ac49, d44a77b3
(h3a, PDF), e888f9ce (h3b, Word) and the guard 88d9db32. This was run twice, independently: by the session, and by the
architecture lens from an unmodified copy.

**Five read-only lenses** traced the cases at the installed tree, each in a sealed sandbox, with nothing edited:
- c1-trace-ab: U1 and U2;
- c1-trace-routing: U3, U4 and U12;
- c1-corpus: the counterexample corpus;
- c1-questions: U9 to U11;
- c1-arch: the fact map and the seam.

The session reproduced each headline claim itself before recording it.

## The traces

### d44a77b3 and 39f0ac49: labelled procedure paragraphs inside the Indications (U2), the bolus (U1)

**Source:** each report has an "Indications:" line, then a paragraph "Upper endoscopy: The gastroscope was advanced
..." and a paragraph "Colonoscopy: The colonoscope was introduced ...", then "Impression:".

**Section boundaries (U2).** `sections._heading` (sections.py:384-414) opens no section for these lines:
- "upper endoscopy" and "colonoscopy" are not in HEADINGS (:398); only "... findings" is;
- a bare label must have nothing after its colon (:405);
- the service-name-only route refuses any colon (:752).

So Indications runs to Impression: [301:1500] in d44a77b3 and [217:3141] in 39f0ac49. 39f0ac49's "Preprocedure
assessment:" is no heading either, because HEADINGS has only the hyphenated form (:124). Measured:
`_heading('Upper endoscopy: The gastroscope was advanced into the esophagus.') -> None`.

**Routing.** detect.py:2162-2164 turns every "performed: was advanced/introduced" cue in an indication section into
uncertain. `_landmarks` counts only performed or incomplete hits (:3613, :3624), so no extent fact is read, and
`_missing` lists extent (:7684-7686). Result: gi.egd and gi.colonoscopy are both uncertain, with extent missing.

**The documented-service reader.** `_time_parts` ends the indication at its own line (services.py:1661-1671), so the
reader reads the paragraphs' acts as performed. `_finish` then folds routing's doubt into each service
(services.py:5943-5959), and takes the extent from routing's missing fact (:5901, :5964). Both services become
uncertain. The cue quoted to the customer is the performance cue itself, "(uncertain: routing holds the family:
performed: was advanced)" (:5958).

**Admission.** For every Corti code, the "service_uncertain" match (reconcile.py:155-161) adds a performed_status
question, and the missing extent adds an extent question (checks.py:664-688, 728-746). Results:
- d44a77b3: 43239, 45385 and 45381 are needs_clarification;
- 39f0ac49: 43239, 45380 and 45385 are needs_clarification.

**The bolus (U1).** The foreign-body act's vocabulary is "foreign body", "food bolus" or "food impaction" only
(services.py:252, the base's again after F-ACTS was dropped). So "the bolus was removed through the mouth" names no act.

The vocabulary is not the only cause. With the bolus read in memory, the act is still dropped as unattributed:
- the labelled paragraph opens no part, so the part family is '';
- the sentence names no site;
- two families are present;
- so `_family_for_act` returns '' (services.py:3907-3940) and the act is skipped (:5118-5134).

Measured minimal input: an EGD paragraph alone binds the act; adding a "Colonoscopy:" paragraph unbinds it; naming
"from the esophagus" binds it again.

**Admission of 43247.** Astra and Fable each proposed 43247, quoting the removal sentence exactly, and both peer reviews
support it. Corti did not propose it.
- `_documented_items` has no foreign-body item.
- `_open_items_covered` returns nothing (engine.py:439-442).
- `_not_admitted_why` returns PARTICIPANT_NO_ACT, "the act it accounts for is not documented as done on the date of
  service" (engine.py:719-722, :3382).
- The alternative is never reinstatable (engine.py:3935).

The reason states a document fact the document contradicts (U9).

**Questions and review (U10).** Every proposal question is a "confirm" row whose only accepted answers are "Not
documented" and "Cannot confirm" (answers.py:475-478, refused otherwise at :648-660). Both exclude the code through the
read-time overlay (review_view.py:182-190, 305-312, 553-563). A held code's only action is Reject (review.py:431-437).
Reviewer confirmation is off: decision D7, kept by the owner's instruction of 2026-11-03.

On 39f0ac49 the member was shown no passage. The member was told "The document does not establish the forceps biopsy
as done", although the reader reads that biopsy performed (U9's summary). The member answered "Not documented" on five
rows, which wrote six answers. 43239, 45380 and 45385 were excluded.

**Export.** Measured with the report's own snapshot, read-only:
- 39f0ac49's reviewed report has no blocker. It exports all three codes as excluded, so no code is billable, and 43247
  is absent.
- d44a77b3's reviewed report is refused, because three codes have open questions.

### e888f9ce: a failed polypectomy makes the colonoscopy incomplete (U3), and the title (U4)

**Source:**
- the title is "Colonoscopy Report (fictional)";
- "Procedure: The colonoscope was advanced to the terminal ileum.";
- random biopsies;
- a 6 mm polyp removed with a cold snare;
- "Hot snare polypectomy of a 14 mm pedunculated polyp in the sigmoid colon was attempted, but the polypectomy was
  unsuccessful because of poor positioning; the polyp was left in place.";
- the Plan is a repeat colonoscopy in 2 months.

**Routing.** gi.colonoscopy reads incomplete. Its mentions:
- the title, uncertain and silent;
- "was unsuccessful", incomplete;
- the Plan's "colonoscopy", planned.

The "failed cannulation" entry of `cues.INCOMPLETE_CLAUSE` ends in a bare alternative, `\b(?:was|were)\s+unsuccessful\b`
(cues.py:470). `_references` reads any such clause as the family's incompleteness when the clause names no service
(detect.py:5856-5913). Its only exemption is a terminal-ileum, ileocecal-valve or retroflexion sub-act. `_aggregate` is
incomplete when any mention is (:6492-6493), and `_adjustment` pushes it onto every performed passage (:7724-7729).

The same happens for "Biopsy attempts were unsuccessful", "Clip placement was unsuccessful" and, through the "could not"
entry, "The snare could not be passed around the polyp" (cues.py:450-451). In an EGD, a failed dilation also rewrites
the extent to "incomplete: second part of duodenum" (detect.py:6020-6022, :6526).

**U4.** `PROCEDURE_TITLE` (cues.py:727) needs the line to end in "report" or "note", so a title with an aside opens no
section and reads silent. The narrative's own course is never a family mention, because instruments give facts only
(detect.py:115-122; cues.py:681-694). Routing's own `todays_procedure_report()` recognises the head, but it feeds only
the extent reach (detect.py:4007-4030).

**U3 masks U4.** Measured by removing only the bare alternative, in memory, on the unmodified case:
- routing reads the colonoscopy PLANNED, through the ELSEWHERE_ORDER fallback on the Plan's mention (detect.py:6502);
- both codes are held.

So U3 and U4 are one repair.

**The services reader on its own** (routing=None) reads the colonoscopy performed and complete. It reads the hot snare
act as "uncertain: attempted". `_finish` then adopts routing's incompleteness and cites routing's reach sentence as the
evidence (services.py:5914-5923).

**Admission.** 45385 and 45380 are READY. Each carries a service.incomplete warning: "Documented as incomplete: 'The
colonoscope was advanced to the terminal ileum.'" (engine.py:2238-2241; checks.py:603-606). Routing.family passes
incomplete as positive (checks.py:24, :157).

**Export.** Both codes are approved in the reviewed report, still carrying that warning.

**Adjacent (measured).** The interventions fact lists "hot snare" from the failed attempt (detect.py:5921-5935). "Right
and left colon" is read as the descending colon only (services.py:102, :3713). The 14 mm polyp's disposition is
"unknown", although the text says "left in place" (services.py:6004-6018).

### One fact, three readers (U12), measured

| fact | readers | measured disagreement |
|---|---|---|
| section kind | sections.layout for routing; services.parts and `_time_parts`; the admission's held_section | 14, 34 and 22 lines differ in d44a77b3, 39f0ac49 and 88d9db32; D1a (a labelled EGD paragraph after Indications: routing indication, services other, 43239 held) |
| act status | routing per name or reference; services per act; the admission reads routing again | the services reader copies routing's status, then the admission counts routing a second time as an independent second opinion (services.py:5899-5972; engine.py:1260-1271, 1407-1425, 1499) |
| placement against outcome | services | D3a: a failed hot snare attempt sharing the Procedure line is promoted to a performed act (services.py:5181-5183), so a 45385 citing it is READY. On its own line it is held. |
| date binding | routing DATE_REACH=40 (detect.py:66); services `_date_owner` (services.py:2311-2348); checks' own | D4a: "... was performed on 03/14/2025" reads performed in routing and historical in services; the code is held with a reason quoting the opposite reading |
| performer | services only (OTHER_SOURCE, AGENT_NAMED); routing reads a facility as a time | D5a to D5c read differently per reader |
| extent and completion | routing for extent; services completion, overridden by routing; the admission reads routing only | D10b: "Cecal intubation was achieved." is complete to services and missing to routing, so the code is held for extent; D1b: a narrative naming only the gastroscope, no routing finding |
| lesion | services binding; reconcile re-derives; routing counts | D6: the EMR is bound to the 4 mm polyp's lesion; the admission distrusts it |
| confirmation | reconcile.status_stated on routing's layout | D11a: the confirmation would refuse "performed" for a passage the services reader reads performed |

Records of the lens probes are in session scratch. The stage-1 regression fixture carries each measured input.

## The counterexamples, recovered and pinned

`tests/fixtures/gi4/completion/corpus.json` holds 611 entries over 532 synthetic texts. It is measured by
`ops.gi4.completion` and pinned by `tests/test_completion_corpus.py`. It reads the same on this tree as on the lens's
measurement: 815 of 815 readings identical. The verdict port reproduces the lens's 566 verdicts exactly.

**Group A, 443 entries.** These are the counterexamples to 18 withdrawn or narrowed releasing rules, each measured on
that rule's own trees:
- F-SECTIONS T, 57; F-SECTIONS L, 34;
- F-ACTS, 43 round-1 and 22 rebuilt;
- F-TIME R, 35;
- the package rules: "marked ... and not resected" 81, "for future localization" 27, "excised" 17, decompression 17,
  kindless branch 3;
- the round-1 and cycle-3 narrowings, 23 and 17;
- competition by act identity, 19, and the "a second"/"another" release, 2;
- the provider-neutral admission's broad form, 14;
- F-NEG S's stage form, 6; the fronted "Today,", 6;
- the stage-3 negation release, 20.

At the installed tree they read:
- 181 as required;
- 244 held where a listing is required, which is the safe side;
- 3 listed where a hold is required;
- 4 false holds (F4: a balloon dilation's 43249 held for competition);
- 1 false READY by judgment (F5: "It is unknown whether hot snare polypectomy was performed." leaves 45378 READY);
- 10 waiting on a coding ruling.

**Group B, 56 entries.** These are the base's recorded false READYs, among them C3-4-4, 5, 8, 10, 11 and 12 and "The
polyp was left in place.". 53 are false READYs; 3 are READY before a coding ruling.

**Group C, 67 entries.** These are the base's recorded false holds, among them every target the withdrawn rules were
built to release. 66 are false holds and 1 is pending a ruling.

**Group D, 45 entries.** These are the lenses' minimal pairs and the two fictional walk documents with their recorded
Corti, Astra and Fable codes. 19 read as required; the rest:
- 11 false holds: U2, U4 and the narrative, D10b, the bolus pairs, and d44a77b3;
- 3 false READYs: a failed attempt on the Procedure line, for 45385 and 43249;
- 6 WRONG FLAG: a READY code carrying a false service.incomplete (U3: e888f9ce, a1, a2, d1, d2, D2a);
- 6 safe side.

**New, found by measuring (F1).** F-NEG S, a kept rule, makes three of the earlier repair's own counterexamples READY
on both paths: L6-1, L6-2's "today" form and the "Referral letter:" form. Both base 406843018 and main 8645fd54 held
them. The cause is services.py:542-546, :857-859 and :2724, with the indication rule at :1790-1797 and :2875. They are
recorded in group B, with their plain-form siblings, as false READYs of the installed tree itself, so the new false
READY guard's baseline carries them until a repair closes them.

**The guard is proved.** The test was mutation-proved by restoring the withdrawn bare-"bolus" vocabulary: 82 failures,
including new false READYs. The services file was restored byte-identical (sha256 `788f152ff2ba8cf5`).

## Owner questions this stage found (class (a), not decided here)

- **Push technique:** whether 43247 covers a food bolus pushed into the stomach. 13 entries wait on it, and Corti reads
  3 of them READY at installed.
- **Two dilation techniques on one stricture:** an NCCI question, and NCCI is not connected (L2).
- **Checklist 4.6** stays the owner's decision: a human-override confirmation, or none.
  - Item 5 forbids a forced addendum that repeats existing documentation, and a blanket override.
  - So stated facts must be read by the readers themselves; that is option (ii).
  - D7 stays off under the instruction of 2026-11-03.

## Measured and inferred

Everything in the traces above was measured by a probe or by the session, except these, read from code:
- the PARTICIPANT_NO_SERVICE and second-review arms of U9;
- that an accepted confirm answer queues no job (answers.py:705-711; executing it would write);
- that an addendum re-sends to the providers.

Not verifiable offline: the answer, recompute and reload sequence on the live site (U11), which is walked in item 7.
