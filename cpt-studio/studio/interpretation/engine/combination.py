"""The combination rules of design v2 (docs/gemini-migration/FINAL-V2.md 4.7, 4.1, 4.8, 4.9 and 4.13; step 4d of 8.1;
DECISIONS D191, the arbiter triage's hand-off 1e:R3, D227's 4d items, built by the repair r4d, D231's combination half,
D240's and D244's R-N3, built by its round r4d of build-v2/w7r, D253's QE13, D255, D256 and D257's ``within``,
built by its round r4d of build-v2/w8r, and D268's base-rule filter and D269, built by its round r4d of build-v2/w9r):
v1's studio/interpretation/combination.py -
base, base-within, competing, the same-day E/M, the separate statement, the separate-lesion modifier review and the
endoscopic rows - and the competition's claims (v1's assess._claims, _one_stricture, _technique_doubts and
_stricture_claims: D55, D74, D104, D118, D163, D167), forked into engine/ with their readers deleted and their inputs
rewired to settled facts. Nothing here reads text: every input is an enumeration member, an id, a result or a span of
the FactSet (engine/facts.py), a code string read as a number (engine/catalogue.py), or a record another step hands in.

**The synthetic act** (FINAL-V2 3.2.6 rule 3; DECISIONS D216, D231, D232, D256). A kept unlisted ACT or DOUBT
(``synthetic``; a doubt about whether an act was done leaves it possibly performed, refute-r4a-r1 F1; a denial is no
act) is a possibly performed act of its kind for EVERY rule of this module whose release depends on the absence of a
possibly performed act (D231: "D216 reaches every absence condition in combination.py"), read as its filed doubted form
would be - its kind as the entry names it (every kind when it names none), its status the doubt, its date, performer,
device, places and lesion unknown. WHERE a rule reads it follows its card, as the rulings give each rule; a card
naming a session the FactSet does not hold is read as no card (contract/appraise_read reads a card that names no
session card of the request as no session, so the pipeline never hands one in; ``synthetic_sessions`` keeps the id
itself first, and reads every session after it, as for no card):
- base_included's (c) (``_unlisted_acts``): a CARDED act (``_card``: its card a session of the FactSet) holds its card's
  session's base code, whatever its kind (3.2.6 rule 3: "an unlisted act with a session card"); one with no card that
  names a kind holds the base code of every session whose family may hold that kind as coverage.doubted_in reads it -
  where step 4b's event_coding would list its filed doubted form among the session's doubted acts
  (``_listed_doubted``: a reportable kind of a family the session may be) - DECISIONS D256 P1, the step's question
  Q-CARD option (c), "exactly what coverage.doubted_in admits for the filed doubted form", worded as the carded form
  is; one with no card that names no kind holds the base code when the document tells one session - counting beside
  the held session only a session that one of its own filed events establishes as performed today and that its own
  established examinations do not establish not done today (DECISIONS D285 ruling A.1, D269's count) - and stays out
  in a document of more than one (D256: the named residual Q-UNNAMED, counted in D276's replays since D277 runs no
  D2-D3, D285 A.4);
- D119's PEG arm (D231 row 3: "whose card may be the feeding tube's session"), the claims' D55 and D118 openings (row 4:
  "whose card may be of the code's family") and the competition over the act itself (row 5: "an unlisted act with a
  card", ``synthetic_claims``): a CARDED act only - those rows name a card (refute-r4d-r1 of build-v2/w7r, F3);
- session_done's act-only arm (row 1, D232's reading, evaluate.synthetic_in's): its card's session, and EVERY session
  when it names none (``synthetic_sessions``: 2.4 A6 gives the card "when the document says", so S is possible for every
  S - 3.2.6 rule 4's "with no session, of every session");
- session_possibly_done (row 2: "an unlisted act with card S (or no card, S possible)", as DECISIONS D256 P2 and D269
  read it): its card's session; with no card, every session - and, when it names a kind, only a session whose family
  holds that kind (K2) -; never a session whose examination is established and established not done on the date of
  service (planned, or done on another date), which no act makes possibly done, carded or not (D269);
- every one - the same-day rule's undatable acts (3.2.6 rule 5: "in an encounter with an E/M visit, an unlisted act").
Each moves one way when an entry is added: claims, competitions, holds and wholes only grow, and a session's done and an
established whole only fall (EXPLANATION to QUESTION, never READY). The step's NOTES list every absence condition of the
module with whether, and where, it reads the synthetic act. A kept unlisted act carded to a session established not
done today makes it neither possibly done nor a whole (DECISIONS D269: "every act possibly in a session S, placed or
supported"), and leaves it established not done (``not_done_today`` reads the filed events: the step's question
Q-CARDEXAM).

The engine applies these rules over the codes it counts (engine/assess.py, step 5a) and the read-time overlay
(interpretation/overlay.py, step 5c) applies the same functions over a reviewer's counted set: one implementation each,
so the two cannot drift (v1's rule, kept).

**What a member is** (``Member``; v1's ``members`` (code, family, session id) and assess's counted selections): a
counted code - its proposal key, its code, the family it routes to, the session it is matched to (None when its family
has none at this encounter), its E* (the acts supporting it), its origin (kept, never read: D40), whether it is a
procedure (assess._procedural, read from the reference rows) and whether the per-code rule supports it (v1's state
performed or incomplete). Every function here takes members in their order and keys its output by member key.

**base_included** (FINAL 7.9, D119, D177(1); 4.7: "unchanged structure | sessions; reportable and doubted acts"). A
base code (``is_base``: a base profile - an endoscopic family's examination or an office visit code, whose two codes of
one visit hold each other - or an examination-only EUS code, every one of whose covers is the examination) matched to
session S is held, never excluded, beside (a) another counted code of its family matched to S that accounts for an act,
(b) S's reportable acts, or (c) S's doubted acts. An ADD-ON code (``is_addon``: a key of engine/assess.ADDON_PRIMARIES -
43273, 91013, 99153, 99417 - reported in addition to its primaries) is never such a code under (a): it never causes a
base hold and is never named in one, and an add-on and its primaries are governed by assess's ADDON row alone
(DECISIONS D255, refute-r3c-r1 R3C1-02: 99215 beside 99417 was held "99215 is normally not reported separately from
it", the inverse of ADDON_PRIMARIES). Rules (b) and (c) read no act that a counted add-on code of S accounts for as its
supporting act (``addon_acts``: the add-on's E*; DECISIONS D268, refute-r4d-r1 V8R4D1-1: an ERCP's cholangioscopy
beside a counted 43273 held 43260 base_explained, "which this diagnostic code does not account for", steering the
reviewer to reject the primary and leave the add-on approvable alone) - 43260 beside 43273 with the cholangioscopy
documented is READY, as 43273 is - and, by DECISIONS D286 ruling E (G3-12, amending D268's narrowing, refute-r4d-r1
V9R4D1-4), no act of a kind that a counted add-on code of S covers and that no non-add-on code of S's family covers
(``addon_kinds``, catalogue profiles): an act filed with its kind supported so, or a kept unlisted entry naming it
(a duplicate mention of 43273's cholangioscopy no longer holds 43260: D255's effect "43260 beside 43273 alone is
READY"); a kindless entry, or an act whose kind is not established, is still read. Without the add-on counted, the
rules read as built. The reportable and doubted acts
are step 4b's (engine/coverage's event_coding@2, 4.7's "reportable / doubted | v1's shapes" row), handed in as
``coding`` (SessionActs per session), never re-derived here: two derivations would drift. DECISIONS D119: an upper
endoscopy's base code reads, as (b) and (c), the PEG acts of every feeding-tube session too (a session whose kind may be
the feeding tube's, an act whose kind may be a PEG, both read by facts.possibly), and the synthetic acts of kind PEG or
none carded to such a session (D231 row 3). FINAL-V2
3.2.6 rule 3, as DECISIONS D231, D232 and D256 read it: a synthetic act (a kept unlisted act or doubt) carded to S is a
synthetic doubted act of S, read here from the FactSet (R.unlisted), so it holds S's base code as a doubt whatever its
kind and whatever the coding lists. One with no card that names a kind holds S's base code exactly where step 4b lists
the same act filed in doubt with its session slot silent: event_coding would list that form among S's doubted acts
(coverage.doubted_in: a reportable kind of a family S may be; never an E/M kind, the session's own service) - D256 P1,
Q-CARD option (c): read as no session, a one-session colonoscopy's 45378 went READY beside an unlisted biopsy whose card
pass 2 left empty (refute-r4d-r2 P1). One with no card that names no kind holds S's base code only when S is the
document's one session (D256; beside more than one session it stays out, the named residual Q-UNNAMED - refute-r4d-r1
F1's office visit beside a colonoscopy, whose hold could name nothing), the sessions counted beside it being only those
one of whose own filed events establishes them performed today and whose own established examinations do not establish
them not done today (DECISIONS D285 ruling A.1, amending D269's count, refute-r4d-r1 V8R4D1-3 and V9R4D1-1: a planned
repeat colonoscopy filed as a session of its own no longer turns the hold off, and neither does a session only possibly
done today, whatever a weakening does to its facts). D177(1): the codes the hold NAMES are those of the base code's
own EUS tract (catalogue.eus_tract); with none, the hold names the acts; with neither, every code beside it (the
recorded residual: naming nothing would drop the hold). The hold is an EXPLANATION (F, 4.8) when
the examination is established included - (b), a reportable act - and a QUESTION (U) when only (a), counted codes
beside it (a proposal with no act documented is one), or doubted or synthetic acts hold it; it never reads another
code's support, which rests on facts outside its closure (4.9). ``coding`` must list every session it is asked about:
step 4b's event_coding@2 lists every session of the FactSet, so a session it does not list is a wiring error, refused
(ValueError), never read as a session with no acts (which would release a base code beside acts nobody listed).

**base_within** (C3, C-4, D70; 4.7: "part_of_session supported (C3); C-4 structural over supported session kinds and
tracts (a done EGD beside a done upper EUS on the date); possibly_part_of by possibly"), from the FactSet:
- C3: the session's part_of_session supported, naming another session - established;
- C-4: the session's kind supported EGD and done, beside another session whose kind is supported EUS, whose tract is
  supported upper and which is done - established (a tract that may be upper or pancreatobiliary - an upper EUS
  examining the pancreas - leaves it possible: v1 read every EUS not placed lower as upper). A session is done (4.3
  row 7: "its examination, when it has one, passes 2-5 (an act-only session: the act itself)") when one of its
  examinations - an event whose kind is supported examination and whose session is supported that session, a digital
  examination excepted - passes rows 2-5 (engine/reading.done); with no such examination, when one of its acts (session
  supported; a digital examination excepted) passes them and no event that may be its examination is left open (a kind
  possibly the examination, possibly in the session, possibly today's, no digital examination), nor a synthetic act of
  kind examination or none that may be in the session (DECISIONS D231 row 1, read only there, in an act-only session:
  beside an established examination a synthetic one adds nothing, D232), so an EUS told only through its done acts is
  the session (D121, D135). The digital examination (FINAL 5.6 E13: "no session") is read as evaluate._digital reads it
  (DECISIONS D253, QE13 option (a), repair r4a's R2): an event that may be an examination whose device CLAIMS manual -
  supported manual, or manual its claimed value or one of its readings - so a weakened device never turns a digital
  examination into the session's own, and the act-only session is evaluate.act_only's (``_digital``);
- D70, by possibly: the part_of_session claim not established, naming the session (its value or an option); or C-4's
  structure possible on every fact (each kind and the tract possibly so, both sessions possibly done: an event possibly
  in the session that may have been done today, facts.possibly - an event whose session fact names an id the FactSet
  does not hold may be in any session, DECISIONS D227 R2-2, as its family read already was - or a synthetic act that
  may be in it, D231 row 2) - a possible whole, the code held as one that is, never READY. A tract supported lower, or
  any fact established against the structure, sets nothing up (v1's lower EUS includes no EGD). An entry with no card
  that names a kind makes possibly done only a session whose family holds that kind (DECISIONS D256 P2's K2).
  DECISIONS D269 (Q-P2DATE option (c); 4.3 row 7): a session whose examination is established, and established not
  done on the date of service (``not_done_today``: planned, or done on another date), is possibly done by NO act -
  filed or kept unlisted, placed, supported, carded or with no card, whatever its date or session slot - and is never
  a whole, by C3, D70 or C-4 (refute-r4d-r2 P2: an EGD beside a planned EUS was held "the endoscopic portion of the
  endoscopic ultrasound" on any entry with no card; D256 P2's letter left an unplaced act dated today making it
  possible, so weakening that date released the hold: Q-P2DATE). "Established not done" reads every event the
  document places in the session that may be its examination: one that may be done today keeps the session from it
  (the step's question Q-NDT: read from the established examinations alone, a session whose examination done today is
  weakened out of them - its session or kind to unresolved - became established not done beside its planned
  examination, and the whole was released). Step 4b's _part_of_session reads session_possibly_done (D227's one
  derivation).
A base code whose session is (possibly) the endoscopic portion of a whole W is held beside the counted codes matched to
W that include its family's examination (catalogue.includes_examination), or beside none when W has no counted code.
W's counted codes that include no such examination hold nothing when W is a whole by C-4's structure alone (43231, the
esophagoscopic EUS, includes no EGD); when the session's own part_of_session claim names W - C3's established whole, or
D70's claim not established - the code is held whatever W's counted codes include (DECISIONS D244 R-N3: a flexible
sigmoidoscopy "performed as part of the colonoscopy" is held beside 45378, which includes no sigmoidoscopy by the
catalogue's table; the claim's weakened form holds it too, so a weakening never releases it), and beside every one of
them (DECISIONS D257: ``within`` names the stated whole's counted codes, whatever they include - 45330 within a
colonoscopy whose 45378 is counted names 45378). An add-on code (D255) is no counted code of W here: it is never named,
and a whole whose only counted codes are add-ons is a whole with no counted code. The hold is an EXPLANATION when an
established whole holds it, a QUESTION when only a possible one does. v1's eus_places and its lower-evidence word
reading are gone (4.7).

**The competition's claims** (``claims``; D40, D55, D74, D104, D118, D163, D167 - 4.7: "claims over E* and over acts
read by possibly; D118's one stricture by same lesion or places not disjoint; the D29 site fit"; 4.8: "A hold never
lowers what a code claims: claims read acts by possibly, never a held code's state"; 9.4 P-MONO: "the claims never
shrink"). A code claims, whatever its state:
- OWN: its E*, and every act that may be its act - an act that may be of a kind of one of its requirement groups (a
  kind the act may be by facts.possibly, read as the catalogue reads it: a clip or an injection whose purpose is
  supported hemostasis is a bleeding control only, one whose purpose may be hemostasis is both; a tattoo and an
  injection as one act; never an umbrella act, whose established kind is none of its members by possibly - v1's READY
  codes never claimed one, and an INTERVENTION act would otherwise hold every READY code of its family), possibly
  positive (possibly performed or attempted: a status not established leaves both open), its date relation not
  established as another date and its performer not established as another (4.4's positive-candidate frame), and
  possibly in a session of the code's family (by possibly over its session - every session of the FactSet when its
  session fact names none - and that session's kind; READ_UNDER's rule admits an act of the family it reads under;
  on route (b), of any family) - kept only where the code could account for it: for a technique code (a dilation code
  that names a technique), its device not established as another technique class (R4: "a dilation of another
  technique is no act the code accounts for"). This is D163's "a held code keeps, as claims, the acts it could account
  for", read by possibly: 4.4 records every positive candidate's witnesses in held_facts [R:HO-8], and this set holds
  every such act of the code's family. D29'S SITE FIT (DECISIONS D240: the installed reading kept, "A verified target
  outside the class does not support"): no arm claims, for a site-specific dilation code (catalogue.site_class), an act
  whose target is established outside its class (``site_outside``, evaluate's SITE row failing: the lesion and every
  place established, every supported place outside the class, none surgically made or unplaced) - "The distal
  esophageal stricture was dilated with a balloon. The duodenal bulb stricture was dilated with a balloon." gives
  43249 the esophageal act and 43245 the duodenal one, and they never compete. A place or a lesion not established
  leaves the act claimed (fail-closed), and a dilation listed at the distal esophagus and the pylorus is claimed by
  both. NAMED RELEASE (D240's preamble: the installed reading is kept and its exception named in 6a's property tests
  and the final report): 9.4's deleted-member weakening of a place list - the pylorus deleted from that list - sets the
  act outside 43245's class, which then drops it and may stop competing. No other place list is read: route (b)'s
  regions and READ_UNDER's regions would set an act apart on its listed places alone (P6);
- D55, D74, D104, D167: a narrowed code (D27: CodeLink.defining) whose family has an act that may be of a defining kind,
  possibly positive and not established at another date - a filed act, or a synthetic act of a defining kind or none
  whose card may be of its family (DECISIONS D231 row 4) - (or whose E* is not empty) also claims every act
  that may be of its other covered kinds, possibly positive, not established at another date, possibly of its family -
  any performer, as v1's current performed acts were (only 43265, 44365 and 49440 have such kinds);
- D118: a technique code also claims every act of its family that may be of its kinds (a dilation), possibly positive,
  not established at another date (any performer, any technique), done on ONE stricture with ANOTHER act of its own
  (``one_stricture``: the two lesions possibly the same; else not set apart by facts.apart_by_lesion, nor, when no
  lesion is possibly shared, by facts.apart_by_place - both read the pair controls [R:SC-B]) - never with itself. A
  synthetic act of its kinds or none whose card may be of its family is another act of its own (D231 row 4), on one
  stricture with every act (its identity is unknown, 4.11).
Every condition reads facts by possibly or as "not established otherwise", and only D29's site fit reads a place list,
so weakening a fact (to unresolved, an added doubt, a control left unrejected) can only add claims (P-MONO), and a
deleted place member removes one only through D240's named release: a hold is never a lowered input that releases a
rival. v1's G4 exception (a technique code held for its site adds no claim) read the code's hold reason, which 4.8
forbids reading; the site fit reads the act's own established facts instead, whatever the code's state.

**competition** (P-ADMIT2 as D40 amends it, unchanged): two counted codes with different codes whose claims intersect -
the same documented act - are each held with one competing_codes question naming the others, whoever proposed either.
``combine`` reads the same rule over the synthetic acts too (DECISIONS D231 row 5, ``synthetic_claims``): two counted
codes of different codes that may both account for one CARDED synthetic act ("an unlisted act with a card") - its kind
one of each code's kinds (every kind when it names none; a narrowed code's opened D55 kinds among them), its card's
session possibly of each code's family - compete, both held competing_codes, as they do for its filed doubted form;
their item quotes its units. An entry with no card is no act any code competes for (refute-r4d-r1 of build-v2/w7r,
F3: an unlisted biopsy of no session beside an EGD's and a colonoscopy's own biopsies made 43239 and 45380 "proposed
for the same documented act").
``Combination.claims`` stays the documented events (what step 5a reads); the synthetic acts' claims and shared acts
are ``unlisted_claims`` and ``unlisted_contested``.

**The same-day E/M** (C-3; D81, D94, D109, D111, D130, D133, D134, D227; 4.7). ``procedure_day`` reads every event
that may be other than an E/M visit or prolonged time (an event whose every possible kind is an E/M kind is never a
procedure; one whose kind may also be another, a doubt, is read as the other too - fail-closed, so a weakened visit kind
can only add a POSSIBLE procedure, never a done one: D227 R2-1), possibly positive, and procedural:
- of a procedural family - its session possibly of one of SAME_DAY_FAMILIES (the procedure families and gi.other, D81),
  read over the sessions its session fact may name (every session of the FactSet when it names none, or names an id the
  FactSet does not hold: D227 R2-2);
- or possibly of a SAME_DAY_KIND (every kind a procedural family's catalogue entry lists - its acts, its bundled and its
  unsupported kinds, catalogue.BUNDLED_KINDS and UNSUPPORTED_KINDS (hand-off 1e:R3) - the examination and the
  umbrellas: every kind but the visit's, prolonged time, moderate sedation and other; read from D191's one table of a
  session family's kinds, requirements_table.FAMILY_KINDS, less the moderate sedation and other it adds to every
  procedural family), an examination whose kind is supported examination and whose device is supported manual
  excepted (E13: a digital examination);
- or possibly of kind other with other_class possibly procedure (D130's statement reading, rewired: its head words and
  DONE_STATEMENTS are gone, 4.7).
Its effective date relation (engine/facts.py's stored per-act fact; the caller passes facts.effective's FactSet, so L1
is re-judged) decides: supported on_date_of_service, it makes the procedure day (DONE when its status is supported
performed or attempted, its kind is supported and no E/M kind - D227 R2-1: an act whose kind is not established may be
the visit itself, whatever its session's family, so it is never a done procedure - and what made it procedural is
established - its session's family, or its kind supported, and for an examination outside a procedural family's session
its device established as other than manual, so a digital examination left open never counts as done - else possible;
an act counted by its class alone is only ever possible, D130); established as another date, it is no procedure day;
otherwise it is UNDATABLE (event_time). **The performer is not read** (legacy parity, S3 hazard 7, 4.13: C-3 counts any
performer's same-day procedure). FINAL-V2 3.2.6 rule 5: every synthetic act of no E/M kind (a kept unlisted act or
doubt: the same-day rule's release is an absence condition, DECISIONS D216 and D231) is an undatable possible
procedure. A counted procedural code adds its family to the done list when the per-code rule
supports it and to the possible list otherwise (engine._encounter's selected procedural codes). ``same_day_holds``
gives an E/M code (catalogue.EM_FAMILIES) its holds, by v1's rule with its one release that a weakening could reach
closed (9.4 P-MONO: "the READY ... sets never grow"; C-3: an undatable event is "a question and never READY"):
- on a procedure day (done or possible) with no separate statement documented: separate_em (rank 20) - an EXPLANATION
  quoting the denial when the visit's separately_identifiable is negated, a QUESTION otherwise (v1's item);
- otherwise, with an undatable act (or an unlisted one) and no ESTABLISHED procedure day (``ProcedureDay.established``:
  a done procedure act, every fact that made it one established, its kind among them - never a counted code's support
  alone, which rests on that code's own facts, outside the E/M code's closure, 4.9): event_time (rank 6) for each
  undatable act (every witness, 4.4). v1 asked it only with no procedure day at all; a merely possible procedure day
  beside a documented statement released the code, and a weakening (a status, a device, a kind, a class left open)
  creates a possible procedure day - so v1's rule turned a held code READY under a weakening. An established procedure
  day cannot be created by a weakening (each fact it rests on is established, and a weakening only makes a fact less
  established; an E/M event whose kind gains another reading is a possible procedure, never a done one: D227 R2-1),
  and beside one the undatable act's date decides nothing for the E/M code (the day is a procedure day whatever it
  is), so there the documented statement releases it, as v1's did (D227 R2-3: ADJUDICATION C-3's "never READY" does
  not apply when another act establishes the procedure day);
- otherwise none.
Every input of the hold therefore moves one way under a weakening: an act of the procedure day stays one or, its date
weakened, becomes undatable (so the procedure day and the undatable acts together only grow, and the undatable acts
alone only grow); the established procedure day and the documented statement only shrink. A code held separate_em
whose only act of the day becomes undatable is held event_time instead (no act then establishes the day); with the day
still a procedure day (another act, or a counted procedural code), it stays held separate_em. The visit's own session
encounter (4.3's V.this_encounter) is step 4a's requirement and is not repeated. ``visit_basis`` (v1's, 5.5) is the
visit's supported basis, which the support display shows; whether R6:em_basis is met is step 4a's row.

**The separate statement** (D113; 4.7: "visit.separately_identifiable supported = a statement; negated = a denial
(quoted); otherwise none"): read from the code's own visit events, then from every other visit of this encounter (kind
supported em_visit, date relation supported on the date of service, its session's encounter supported this_encounter,
its performer supported documenting_team), never another encounter's. Every condition on another visit is established,
so a weakening can only drop a visit, never add one: v1 admitted a visit whose performer was merely not established as
another's, and weakening such a visit's performer (supported other_clinician to unresolved) added its statement and
released a held E/M code. A supported statement on any of them is the statement - a denial never releases, and neither
silences another visit's statement (FRESH-2 fb10's shape) -; else the first denial; else none.

**The modifier review** (59/XS; consideration only, never a status; 4.7: "target.lesion supported and distinct_from
supported"): a code's own acts (E*) of a distinct-lesion kind (catalogue kind supported in DISTINCT_LESION_KINDS) on
supported lesions, beside another counted code of its session, of another code, whose own such acts' lesions are each
supported distinct (distinct_from supported in either lesion's list) from every one of its own. An unknown identity
never pairs (4.11).

**endoscopic_rows**: code -> PFS row of every (code, PFS row or None) pair that has a row (unchanged).

**What a hold is** (engine/types.HeldFact, 4.4, 4.8): base_included (rank 21; key-bound), competing_codes (rank 22),
separate_em (rank 20; key-bound), event_time (rank 6); each with its cause (coding_rule:<rule>, or for event_time the
date fact's own: reading_unknown, reading_contradicted, appraisal:<verdict or coherence>, unestablished:<reason>;
unlisted for an unlisted act or doubt), operator data that names no vendor, and the spans its item quotes (the acts'
anchors, and a synthetic act's own units).
The codes and acts a hold names (BaseIncluded, BaseWithin, the competition's rivals, the ProcedureDay) are returned
beside it, as v1's holds' inputs were: the sentences are step 3c's wording, never built here. ``combine`` applies every
rule to a counted set and gives each member its combination holds (4.1's combine, 4.4's "the combination holds").

**The text-free boundary** (P1, FINAL-V2 5.7 measures 4 and 5): this module imports the standard library,
contract/types.py and engine's anatomy, catalogue, facts, pairing, reading, requirements, requirements_table and types
only - no retired v1 module, none of contract's text modules - holds no word, phrase or marker list (every module-level
collection holds enumeration members or is computed from them), reads no text and returns no document string (a cause
is CPT Studio's own code). ``mypy --strict`` passes over it.
"""
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, unique
from types import MappingProxyType
from typing import TypeVar

from studio.interpretation.contract.types import (Attribute, DateRelation, Device, EmBasis, EncounterRelation, Kind,
                                                  Landmark, OtherClass, Performer, Purpose, Qualifier2, Reason, Result,
                                                  Separate, SessionKind, Status, Tract, UnlistedWhat, VerdictValue)
from studio.interpretation.engine import anatomy, catalogue, pairing, reading, requirements_table
from studio.interpretation.engine import facts as facts_
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.catalogue import TechniqueClass
from studio.interpretation.engine.types import Fact, FactSet, HeldFact, Id, ItemKind, Span, UnlistedStatement

_A = Attribute

# --- the tables (module docstring) ------------------------------------------------------------------------------------

# The E/M families and kinds (lexicon.EM_PROCEDURES' families, lexicon.EM_KINDS): an E/M code gets the same-day rule; an
# act of an E/M kind is never a procedure of the day, nor an act beside its own visit.
EM_FAMILIES: frozenset[SessionKind] = catalogue.EM_FAMILIES
EM_KINDS: frozenset[Kind] = catalogue.EM_KINDS
# DECISIONS D81: the families whose acts make a procedure day - the procedure families and gi.other (another GI
# service). v1's gi.unsupported (D94, NOT_GI) is not here: an act of a non-GI session counts by its kind or, for kind
# other, by its other_class (4.7), never by the family alone.
SAME_DAY_FAMILIES: frozenset[SessionKind] = catalogue.PROCEDURAL_FAMILIES | frozenset({SessionKind.OTHER_GI})
# DECISIONS D109, D111: every kind a procedural family's catalogue entry lists (its acts, bundled and unsupported
# kinds), the examination and the umbrellas - every kind but the visit's, prolonged time, moderate sedation and
# other. Read from THE table of a session family's kinds (requirements_table.FAMILY_KINDS, DECISIONS D191: one table,
# which K2 and possibly's kind arm read too), less moderate sedation and other, which it adds to every procedural
# family; tests/v2/test_combination.py pins it equal to the catalogue entries' kinds (catalogue.FAMILY_ACTS,
# BUNDLED_KINDS and UNSUPPORTED_KINDS: the arbiter's hand-off 1e:R3) with the examination and the umbrellas, and to
# v1's by value.
SAME_DAY_KINDS: frozenset[Kind] = frozenset(
    kind for family in catalogue.PROCEDURAL_FAMILIES
    for kind in requirements_table.FAMILY_KINDS.get(family, frozenset())
    if kind not in (Kind.MODERATE_SEDATION, Kind.OTHER))
# engine.DISTINCT_LESION_KINDS (v1's, by value): the acts a separate-lesion modifier consideration can concern.
DISTINCT_LESION_KINDS: tuple[Kind, ...] = catalogue.REMOVAL_MEMBERS + (Kind.BIOPSY, Kind.ABLATION, Kind.INJECTION,
                                                                       Kind.TATTOO)
# DECISIONS D119: the base rule reads an upper endoscopy's PEG of the encounter's feeding-tube session as its act too.
PEG_FAMILY, PEG_SESSION_KIND = SessionKind.EGD, SessionKind.FEEDING_TUBE
# C-4 (D69, D70, D121): an upper endoscopy within an upper EUS. An EUS whose tract may be pancreatobiliary may be an
# upper EUS examining the pancreas or the biliary tree (v1 read every EUS not placed lower as upper): a possible whole,
# never an established one (the step's NOTES record the question).
WITHIN_FAMILY, WHOLE_FAMILY, WHOLE_TRACT = SessionKind.EGD, SessionKind.EUS, Tract.UPPER
POSSIBLY_UPPER: frozenset[Tract] = frozenset({Tract.UPPER, Tract.PANCREATOBILIARY})
# A status that says the act was done, or begun (v1's verify.POSITIVE; 4.3 row 2).
POSITIVE: frozenset[Status] = reading.POSITIVE
# The date relation of an act done on the date of service (C-3).
ON_DATE: DateRelation = DateRelation.ON_DATE_OF_SERVICE
# The device of a digital examination (FINAL 5.6 E13: no session, no procedure of the day).
DIGITAL: Device = Device.MANUAL
# The performer of another visit whose separate statement the E/M code may read (D113): the documenting team,
# established.
TEAM: Performer = Performer.DOCUMENTING_TEAM
# The family an act counted by its kind or class outside a procedural family is named by (v1: OTHER_GI's label,
# "another GI service"; D109, D130).
OTHER_SERVICE: SessionKind = SessionKind.OTHER_GI
# DECISIONS D231 (refute-r4a-r1 F1): the natures of a kept unlisted entry read as 3.2.6 rule 3's synthetic act - an act,
# and a doubt (a doubt about whether an act was done leaves it possibly performed: 4.2 [R:HO-1]); never a denial (3.2.6
# rule 4 pairs it). The same set evaluate.synthetic_possible reads (D231: "the four modules read one set").
SYNTHETIC_WHAT: frozenset[UnlistedWhat] = frozenset({UnlistedWhat.ACT, UnlistedWhat.DOUBT})
# DECISIONS D29, D240: the places that are never outside a dilation's site class - the surgically made places, whose
# position in the tract cannot be told (an anastomosis, a stoma, a pouch), and a place named as none of the chain's -
# exactly evaluate's SITE row's (D29: "An unverified or ambiguous target (an anastomosis) holds").
UNPLACED_SITES: frozenset[Landmark] = anatomy.ALTERED | anatomy.UNPLACED
# DECISIONS D256 P1 (Q-CARD option (c)): what step 4b's coverage.doubted_in reads of a kind for the act filed in doubt
# with its session slot silent - the kinds never an act beside a session (the examination, the session itself, and the
# umbrellas: coverage._NOT_ACTS; a removal umbrella is doubted as any of its members, D117) and the stent's own acts a
# family whose acts hold the stent placement reports (D116: coverage.STENT_ACTS). ``_listed_doubted`` reads them as
# coverage reads them; tests/v2/test_combination.py pins the two equal over every kind and session shape.
_NOT_ACTS: frozenset[Kind] = frozenset({Kind.EXAMINATION, *catalogue.UMBRELLAS})
_STENT_ACTS: frozenset[Kind] = frozenset({Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE})


@unique
class Modifier(Enum):
    """checks.DISTINCT_LESION_OPTIONS (v1's, by value): the separate-lesion modifiers a reviewer may choose - none or
    one - offered by the modifier review and never assigned."""
    M59 = '59'
    XS = 'XS'


# The holds' causes (FINAL-V2 4.4), operator data that names no vendor: the coding rule that raises the hold; a fact
# read as unknown or contradicted; an unresolved fact's own appraisal or reason; an unlisted statement.
BASE_CAUSE = 'coding_rule:base_included'
WITHIN_CAUSE = 'coding_rule:base_within'
COMPETING_CAUSE = 'coding_rule:competing_codes'
SAME_DAY_CAUSE = 'coding_rule:same_day_em'
UNLISTED_CAUSE = 'unlisted'
READING_UNKNOWN = 'reading_unknown'
READING_CONTRADICTED = 'reading_contradicted'
UNESTABLISHED = 'unestablished'


@unique
class Coherence(Enum):
    """The appraisal outcomes 3.2.3's coherence table names that are no verdict, as a cause names them (4.4:
    appraisal:<verdict or coherence>)."""
    INCOHERENT = 'control_incoherent'
    DETACHED = 'detached'
    MISSING = 'missing'


# Each appraisal reason of 3.3 row 9 -> the verdict or coherence its cause names.
APPRAISAL_CAUSES: Mapping[Reason, VerdictValue | Coherence] = MappingProxyType({
    Reason.APPRAISAL_CONTRADICTS: VerdictValue.CONTRADICTS, Reason.APPRAISAL_UNCLEAR: VerdictValue.UNCLEAR,
    Reason.APPRAISAL_QUALIFIED: VerdictValue.QUALIFIED, Reason.CONTROL_INCOHERENT: Coherence.INCOHERENT,
    Reason.APPRAISAL_DETACHED: Coherence.DETACHED, Reason.APPRAISAL_MISSING: Coherence.MISSING,
    **{Reason(f'appraisal_qualified:{qualifier.value}'): VerdictValue.QUALIFIED for qualifier in Qualifier2},
})

# The holds' items at their RANK rows (4.8; engine/requirements.RULES' combination and C3+SEP rows ask exactly these).
BASE_ITEM = rq.Item(rq.Rank.BASE_INCLUDED, rq.FactKey.BASE_INCLUDED)
COMPETING_ITEM = rq.Item(rq.Rank.COMPETING, rq.FactKey.COMPETING_CODES)
SEPARATE_ITEM = rq.Item(rq.Rank.SEPARATE_EM, rq.FactKey.SEPARATE_EM)
TIME_ITEM = rq.Item(rq.Rank.TIME, rq.FactKey.EVENT_TIME)


# --- the records ------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Member:
    """One counted code (module docstring): ``key`` its proposal key; ``code`` the code; ``family`` the family it routes
    to; ``session`` the session it is matched to (None: its family has none at this encounter); ``supporting`` its E*;
    ``origin`` who proposed it (kept, never read: D40); ``procedural`` whether it is a procedure (assess._procedural:
    a non-E/M code of a procedure profile, or with a global period other than XXX); ``supported`` whether the per-code
    rule supports it (v1's state performed or incomplete: E* not empty and no held fact)."""
    key: str
    code: str
    family: SessionKind
    session: Id | None = None
    supporting: tuple[Id, ...] = ()
    origin: str = ''
    procedural: bool = False
    supported: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, 'supporting', tuple(self.supporting))


@dataclass(frozen=True, slots=True)
class SessionActs:
    """What the base rule reads of one session from step 4b's event_coding@2 (v1's coding['sessions'][S] 'reportable'
    and 'doubted'; FINAL-V2 4.7's "reportable / doubted | v1's shapes"): ``reportable``, the session's reportable acts
    (done, status performed, kind of the family's catalogue acts, not bundled); ``doubted``, its doubted acts (possibly
    positive with a required fact not supported, or a relation; an act possibly in the session included). Neither holds
    the session's own visit (an E/M kind): the session's own service is never an act beside itself."""
    reportable: tuple[Id, ...] = ()
    doubted: tuple[Id, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, 'reportable', tuple(self.reportable))
        object.__setattr__(self, 'doubted', tuple(self.doubted))


@dataclass(frozen=True, slots=True)
class BaseIncluded:
    """A base code held beside its session's interventions (base_included): ``key``, ``code`` and ``session`` the base
    code's; ``beside`` every other counted code of its family and session that accounts for an act (rule (a)), never an
    add-on code (DECISIONS D255); ``others`` those of its own EUS tract, the codes the hold names (D177(1));
    ``reportable`` and ``doubted`` the acts of rules (b) and (c) (with D119's PEG acts), never an act a counted add-on
    code of its session accounts for as its supporting act (DECISIONS D268: ``addon_acts``), ``unlisted`` the indices in
    FactSet.unlisted of the synthetic acts that hold it (3.2.6 rule 3 as D231, D232 and D256 read it: the kept unlisted
    acts and doubts carded to its session; those with no card that name a kind whose filed doubted form step 4b would
    list doubted there; in a document of one session - counted as D285 ruling A.1 counts it, ``_one_session``: beside
    it only a session established performed today by one of its own filed events and not established not done today
    by its own established examinations - those with no card that name no kind; and, for an upper endoscopy's code,
    those of kind PEG or none carded to a session that may be the feeding tube's - D231 row 3),
    and ``unlisted_kinds`` the kinds those entries name, each once (an entry that names none can be named by no
    kind)."""
    key: str
    code: str
    session: Id
    beside: tuple[str, ...]
    others: tuple[str, ...]
    reportable: tuple[Id, ...]
    doubted: tuple[Id, ...]
    unlisted: tuple[int, ...]
    unlisted_kinds: tuple[Kind, ...] = ()

    @property
    def established(self) -> bool:
        """The examination is established included (an EXPLANATION, 4.8: "an established fact fails" the requirement):
        a reportable act of its session - an intervention established done - holds it (rule (b)). Rule (a) alone, a
        counted code beside it, is no fact: the code may be a proposal with no act documented, whose rejection releases
        the base code (the refutation's F2), so it, like doubted and unlisted acts, holds it as a QUESTION. A code the
        per-code rule supports rests on an established done act, which step 4b lists as reportable, so no fact is lost;
        reading ``Member.supported`` here instead would let the base code's item move with the other code's own facts,
        outside its closure (4.9, P-INDEP)."""
        return bool(self.reportable)

    @property
    def named_codes(self) -> tuple[str, ...]:
        """The codes the hold names (D177(1)): its own tract's codes; with none and no act to name, every code beside it
        (the recorded residual); () when it names acts. A synthetic act that names no kind is no act the hold can name,
        so beside only such acts the hold names the codes beside it: whether the code is held is unchanged. With no
        code beside either, it names nothing - DECISIONS D254's label words it ("another act": step 3c's absence
        form, step 5c's item_slots), as for a kindless entry with no card in a document of one session (D256). Never an
        add-on code (D255: ``beside`` holds none)."""
        if self.others:
            return self.others
        return () if self.reportable or self.doubted or self.unlisted_kinds else self.beside


@dataclass(frozen=True, slots=True)
class Whole:
    """A session another session is, or may be, the endoscopic portion of (C3, C-4, D70): ``session`` that whole;
    ``established``, True when C3's part_of_session is supported or C-4's structure established, False when only
    possible (D70: held as one that is, never READY)."""
    session: Id
    established: bool


@dataclass(frozen=True, slots=True)
class BaseWithin:
    """A base code held because its session is (possibly) the endoscopic portion of another (base_within): ``key``,
    ``code`` and ``session`` the base code's; ``wholes`` the sessions it is within; ``within`` the counted codes of
    those sessions that include its family's examination, and every counted code of a whole its own part_of_session
    claim names, whatever it includes (DECISIONS D257), never an add-on code (D255) - () when they have no counted code;
    ``established`` whether an established whole holds it."""
    key: str
    code: str
    session: Id
    wholes: tuple[Id, ...]
    within: tuple[str, ...]
    established: bool


@dataclass(frozen=True, slots=True)
class VisitBasis:
    """The documented basis of an E/M visit (v1's combination.visit_basis, contract 9.2's em_basis; FINAL-V2 5.5): the
    visit event whose visit.basis is supported, its value, and the spans of that fact (for wording.quote)."""
    event: Id
    basis: EmBasis
    spans: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class ProceduralCode:
    """A counted code for the procedure day (v1's procedure_day ``codes``): its code and family, whether it is a
    procedure (assess._procedural), and whether the per-code rule supports it."""
    code: str
    family: SessionKind
    procedural: bool
    supported: bool


@dataclass(frozen=True, slots=True)
class ProcedureDay:
    """The procedure day by date of service (C-3; v1's ProcedureDay over ids): ``done`` and ``possible``, the families
    of the procedures documented as done, or possibly done, on the date of service (None for a procedure CPT Studio
    could not identify; OTHER_GI for an act counted by its kind or class outside a procedural family), each once;
    ``done_acts`` and ``possible_acts`` the events that make them; ``undatable`` the procedure events whose date
    relation is not established (an E/M code's event_time, never READY); ``undatable_unlisted`` the indices in
    FactSet.unlisted of the kept unlisted acts and doubts of no E/M kind (3.2.6 rule 5, the synthetic act as D231 reads
    it). D151 withdrew D144's unidentified, so the reconcile rule reads ``done`` alone (D134). ``codes`` the counted
    procedural codes the day reads (each ProceduralCode whose ``procedural`` is True, each once, in member order: the
    codes whose families it appends), which SEPARATE_EM's codes form names when the day has no act to list (DECISIONS
    D246; the integration's fix of the combination, repair r3c's R3 and step 5c's R2)."""
    done: tuple[SessionKind | None, ...] = ()
    possible: tuple[SessionKind | None, ...] = ()
    done_acts: tuple[Id, ...] = ()
    possible_acts: tuple[Id, ...] = ()
    undatable: tuple[Id, ...] = ()
    undatable_unlisted: tuple[int, ...] = ()
    codes: tuple[str, ...] = ()

    @property
    def procedure_day(self) -> bool:
        """A procedure is documented as done, or possibly done, on the date of service."""
        return bool(self.done or self.possible or self.done_acts or self.possible_acts)

    @property
    def established(self) -> bool:
        """A procedure is documented as DONE on the date of service by an act whose every fact that made it a done
        procedure is established (``done_acts``): its status supported performed or attempted, its date relation
        supported on the date of service, its kind supported and no E/M kind (DECISIONS D227 R2-1: an act whose kind is
        not established may be the visit itself), and its session's family, or its kind (for an examination, its
        device), established. Each is an established fact of the act or of its session, and a weakening only makes a
        fact less established, so no weakening can create one (module docstring), which is why it alone may moot an
        undatable act's date for an E/M code (D227 R2-3). A counted procedural code never establishes the day by itself:
        its support rests on that code's own facts (its reach, its device, its bundling), and the E/M code's hold would
        then move with facts outside its closure (4.9, P-INDEP); a supported code's act is a done act here anyway."""
        return bool(self.done_acts)

    @property
    def undatable_any(self) -> bool:
        """A procedure event, or an unlisted act or doubt, whose date CPT Studio could not establish."""
        return bool(self.undatable or self.undatable_unlisted)


@dataclass(frozen=True, slots=True)
class SeparateStatement:
    """The documented statement of a significant, separately identifiable E/M (D113): ``stated`` the visit whose
    separately_identifiable is supported (None: none is); ``denied`` the first visit whose separately_identifiable is
    negated, when none is stated; ``spans`` the spans of the fact that decided (for wording.quote)."""
    stated: Id | None = None
    denied: Id | None = None
    spans: tuple[Span, ...] = ()


@dataclass(frozen=True, slots=True)
class Partner:
    """Another counted code of a code's session whose acts lie on lesions each distinct from the code's own: its key,
    code, lesions and acts."""
    key: str
    code: str
    lesions: tuple[Id, ...]
    acts: tuple[Id, ...]


@dataclass(frozen=True, slots=True)
class ModifierReview:
    """The separate-lesion modifier review of one code (review_view._modifier_review's shape, as ids; never assigned):
    its key, code and session; its own lesions and the acts on them; its partners; the modifiers offered."""
    key: str
    code: str
    session: Id
    lesions: tuple[Id, ...]
    acts: tuple[Id, ...]
    partners: tuple[Partner, ...]
    options: tuple[Modifier, ...] = tuple(Modifier)


# --- reading facts ----------------------------------------------------------------------------------------------------


def _fact(R: FactSet, subject: Id | None, attribute: Attribute) -> Fact:
    return facts_.fact(R, subject, attribute)


def _order(R: FactSet) -> Mapping[Id, int]:
    return {event: index for index, event in enumerate(R.events)}


def _ordered(R: FactSet, events: Iterable[Id]) -> tuple[Id, ...]:
    """``events`` each once, in pass 1's order (an id the FactSet does not hold last, in the order given)."""
    order = _order(R)
    found = list(dict.fromkeys(events))
    return tuple(sorted(found, key=lambda event: order.get(event, len(order))))


def _anchor_spans(R: FactSet, events: Iterable[Id]) -> tuple[Span, ...]:
    """The anchor units of ``events``, each once, in document order (what a hold quotes)."""
    return tuple(sorted({span for event in events for span in reading.anchors(reading.Reading.of(R), event)}))


def _unlisted_spans(R: FactSet, indices: Iterable[int]) -> tuple[Span, ...]:
    return tuple(sorted({span for index in indices for span in R.unlisted[index].units}))


def possibly_today(R: FactSet, event: Id) -> bool:
    """4.4's positive-candidate frame: the event is possibly positive (possibly performed or attempted_not_completed),
    its effective date relation is not established as another date and its effective performer is not established as
    another (pairing.positive, other_date, other_performer)."""
    return (pairing.positive(R, event) and not pairing.other_date(R, event)
            and not pairing.other_performer(R, event))


def _possibly_positive_on_date(R: FactSet, event: Id) -> bool:
    """possibly_today without the performer: D55's, D167's and D118's frame (v1's current performed acts were any
    performer's)."""
    return pairing.positive(R, event) and not pairing.other_date(R, event)


def _named_sessions(R: FactSet, event: Id) -> tuple[Id, ...] | None:
    """The sessions ``event``'s session fact may name, by possibly: its supported session; its claimed session and
    options when not established; None (any session) when the slot is silent, negated, or names no id - and when a
    NEGATED claim is not established (its state negated, its result open): "not in X1" left open may be in any
    session, so weakening an established negation never narrows the sessions (9.4 P-MONO; read as its claimed value
    alone, it shrank a code's claims). An overfilled session slot's merged view (AMENDMENT-2 4.3.3 a) names any session,
    as a written denial read alone would - every view, since it cannot tell whether a written fact denied a session
    (facts.open_denial; the step's NOTES question Q1R: a view of X1 written stated and X1 written denied, read as X1
    alone, left a same-day EUS's done examination out of the EUS, and 43235 READY beside it)."""
    found = _fact(R, event, _A.SESSION)
    if found.result is Result.SUPPORTED:
        return (found.value,) if isinstance(found.value, Id) else None
    if facts_.silent(found) or found.result is Result.NEGATED or facts_.open_denial(found):
        return None
    named = tuple(dict.fromkeys(value for value in (found.value, *found.options) if isinstance(value, Id)))
    return named or None


def possible_sessions(R: FactSet, event: Id) -> tuple[Id, ...]:
    """The sessions ``event`` may be in: those its session fact may name; every session of the FactSet when it names
    none (a silent slot). DECISIONS D227 R2-2: when one id it names - its supported value, or, not established, its
    claimed value or a reading - is no session of the FactSet (a dangling id: settle's I4 keeps the claimed value,
    unresolved, reference_invalid), the event may be in ANY session of the FactSet for membership (FINAL-V2 4.11: a
    missing identifier manufactures neither a match nor a non-match), as step 4b's coverage.sessions_of reads it: the
    named ids first, then every session of the FactSet. The dangling id itself is kept, so its family read stays
    fail-closed as before: its kind reads as silent, so any family (``may_be_of_family``, ``_procedural_family``).
    DECISIONS D293 (refute-f3e-r2 N1): so is every id named by a fact that is not established and that the sessions are
    read as open for (``_open_ids``: a negated claim not established, or an overfilled slot's merged view) - kept
    first, then every session of the FactSet - so that reading is never narrower than its written facts read alone
    (AMENDMENT-2 4.3.3 a, 4.4)."""
    named = _named_sessions(R, event)
    if named is None:
        open_ids = _open_ids(R, event)
        return tuple(dict.fromkeys((*open_ids, *R.sessions))) if open_ids else tuple(R.sessions)
    if any(session not in R.sessions for session in named):
        return tuple(dict.fromkeys((*named, *R.sessions)))
    return named


def _open_ids(R: FactSet, event: Id) -> tuple[Id, ...]:
    """The session ids ``event``'s session fact names that the FactSet does not hold (dangling: settle's I4), when the
    fact is not established and ``_named_sessions`` reads it as naming any session (a negated claim left open, or an
    overfilled slot's merged view, ``facts.open_denial``): the event may be in that undefined session too, so its family
    read stays fail-closed (DECISIONS D227 R2-2; D293). An established fact (supported, or a negation that holds) and
    a silent slot name none."""
    found = _fact(R, event, _A.SESSION)
    if found.result in (Result.SUPPORTED, Result.NEGATED) or facts_.silent(found):
        return ()
    return tuple(dict.fromkeys(value for value in (found.value, *found.options)
                               if isinstance(value, Id) and value not in R.sessions))


def _session_may_be(R: FactSet, session: Id, family: SessionKind) -> bool:
    return facts_.possibly(_fact(R, session, _A.KIND), family)


def may_be_of_family(R: FactSet, event: Id, family: SessionKind) -> bool:
    """Whether ``event`` may be in a session of ``family``: a session it may be in (possible_sessions: those its
    session fact may name, every session of the FactSet when it names none or names an id the FactSet does not hold)
    may be of that family; any family when the FactSet has no session at all. Not established otherwise: weakening a
    session or kind fact only widens it."""
    sessions = possible_sessions(R, event)
    if not sessions:
        return True
    return any(_session_may_be(R, session, family) for session in sessions)


def _act_kinds(R: FactSet, event: Id) -> frozenset[Kind]:
    """Every catalogue kind ``event`` may be for coding (catalogue.catalogue_kind, read by possibly): each kind its
    kind fact makes possible (facts.possibly: its value, its options, its control's sibling); a clip or an injection
    whose purpose is supported hemostasis is a bleeding control only (COMMON_BUNDLED's clip rule: no injection code
    accounts for it, as v1's never did), and one whose purpose may be hemostasis is both (D157's doubt, kept as a rule
    over facts, 4.13)."""
    kinds = facts_.possible_kinds(R, event, of_family=False)
    hemostatic = kinds & catalogue.HEMOSTASIS_KINDS
    if not hemostatic:
        return kinds
    purpose = _fact(R, event, _A.PURPOSE)
    if facts_.holds(purpose, Purpose.HEMOSTASIS):
        return (kinds - hemostatic) | frozenset({Kind.BLEEDING_CONTROL})
    if facts_.possibly(purpose, Purpose.HEMOSTASIS):
        return kinds | frozenset({Kind.BLEEDING_CONTROL})
    return kinds


def _may_be_of(R: FactSet, event: Id, wanted: frozenset[Kind]) -> frozenset[Kind]:
    """The kinds of ``wanted`` that ``event`` may be as an act (_act_kinds, read by possibly; a tattoo and an injection
    are one act for coding, catalogue.ONE_ACT). An umbrella act (removal, intervention: its kind established as the
    umbrella) is none of its members by possibly (4.2: an established fact makes possible exactly its value), so no
    code claims it, as v1's READY codes never did; a doubt's reading of a member makes it that member."""
    kinds = _act_kinds(R, event)
    return frozenset(target for target in wanted if target in kinds
                     or (target in catalogue.ONE_ACT and bool(kinds & catalogue.ONE_ACT)))


def _cause(found: Fact) -> str:
    """The cause of a question resting on ``found`` (FINAL-V2 4.4): reading_unknown (silent or doubted),
    reading_contradicted, appraisal:<verdict or coherence> for an appraisal reason, unestablished:<reason> for any other
    reason of an unresolved fact, and SAME_DAY_CAUSE for an established fact (the rule's own doubt)."""
    if found.result is Result.UNKNOWN:
        return READING_UNKNOWN
    if found.result is Result.CONTRADICTED:
        return READING_CONTRADICTED
    if found.result is not Result.UNRESOLVED:
        return SAME_DAY_CAUSE
    reason = found.reasons[0] if found.reasons else None
    if reason is None:
        return UNESTABLISHED
    appraisal = APPRAISAL_CAUSES.get(reason)
    if appraisal is not None:
        return f'appraisal:{appraisal.value}'
    return f'{UNESTABLISHED}:{reason.value}'


def _key(item: rq.Item) -> str:
    return rq.fact_key(item.fact)


def _rank(item: rq.Item) -> int | None:
    return item.rank.value if item.rank is not None else None


# --- 3.2.6 rule 3's synthetic act (DECISIONS D216, D231) --------------------------------------------------------------


def synthetic(R: FactSet) -> tuple[int, ...]:
    """The indices in FactSet.unlisted of the kept entries read as 3.2.6 rule 3's synthetic act (DECISIONS D216, D231),
    in stored order: an unlisted ACT, or an unlisted DOUBT - a doubt about whether an act was done leaves it possibly
    performed (4.2 [R:HO-1]; refute-r4a-r1 F1). A DENIAL is no act: 3.2.6 rule 4 pairs it."""
    return tuple(index for index, entry in enumerate(R.unlisted) if entry.what in SYNTHETIC_WHAT)


def synthetic_sessions(R: FactSet, entry: UnlistedStatement) -> tuple[Id, ...]:
    """The sessions a synthetic act may be in for DECISIONS D231 rows 1 and 2 (row 2: "an unlisted act with card S (or
    no card, S possible)"; row 1 by D232's reading, evaluate.synthetic_in's): its session card when the FactSet holds
    that session (pass 2's card, read as a filed act's supported session); every session of the FactSet when it names
    none (2.4 A6 gives the card "when the document says": the document does not say, so S is possible for every S -
    3.2.6 rule 4's "with no session, of every session"); and, for a card the FactSet does not hold, that id and then
    every session (as for no card: contract/appraise_read reads such a card as none; 4.11). Row 2 reads it with
    DECISIONS D256 P2's K2 for an entry with no card and D269's exemption of a session established not done today
    (``session_possibly_done``); rule (c) of base_included reads its card, or D256 P1's admission with none
    (``_unlisted_acts``); rows 3-5 read a carded act only (``_card``).
    No fact is read, so no weakening moves it."""
    if entry.session is None:
        return tuple(R.sessions)
    if entry.session not in R.sessions:
        return tuple(dict.fromkeys((entry.session, *R.sessions)))
    return (entry.session,)


def synthetic_in(R: FactSet, entry: UnlistedStatement, session: Id) -> bool:
    """Whether the synthetic act ``entry`` may be in ``session`` for rows 1 and 2 (``synthetic_sessions``)."""
    return session in synthetic_sessions(R, entry)


def _card(R: FactSet, entry: UnlistedStatement) -> Id | None:
    """The session a synthetic act's card names, when the FactSet holds it - what 3.2.6 rule 3 ("an unlisted act with a
    session card is a synthetic doubted act of that session") and DECISIONS D231 rows 3-5 ("whose card may be the
    feeding tube's session", "whose card may be of the code's family", "an unlisted act with a card") read; None when
    the entry names none, and when its card names a session the FactSet does not hold (contract/appraise_read reads a
    card that names no session card of the request as no session, so the pipeline never hands one in: read the same way
    here, so DECISIONS D256's readings of an entry with no card apply to it)."""
    return entry.session if entry.session is not None and entry.session in R.sessions else None


def _synthetic_of_family(R: FactSet, entry: UnlistedStatement, family: SessionKind) -> bool:
    """DECISIONS D231 rows 4 and 5, ``may_be_of_family`` for a synthetic act: its card (``_card``) is a session whose
    kind may be ``family`` (facts.possibly over that session's kind). An entry with no card is of no family here: those
    rows read a carded act only (row 2 alone reads "no card, S possible")."""
    card = _card(R, entry)
    return card is not None and _session_may_be(R, card, family)


def _synthetic_kinds(entry: UnlistedStatement) -> frozenset[Kind]:
    """Every catalogue kind a synthetic act may be for coding - ``_act_kinds`` of its filed doubted form (its kind fact
    supported as the entry names it, or an empty slot when it names none; its purpose an empty slot): every kind when
    it names none ("a silent kind admits every kind", D231 row 5); else its kind, and a clip or an injection, whose
    purpose no card states, is a bleeding control too (D157's doubt). An umbrella names itself only, as a filed act
    whose kind is established as the umbrella is none of its members by possibly (4.2)."""
    if entry.kind is None:
        return frozenset(Kind)
    named = frozenset({entry.kind})
    return named | frozenset({Kind.BLEEDING_CONTROL}) if named & catalogue.HEMOSTASIS_KINDS else named


def _synthetic_may_be_of(entry: UnlistedStatement, wanted: frozenset[Kind]) -> frozenset[Kind]:
    """``_may_be_of`` for a synthetic act: the kinds of ``wanted`` it may be (``_synthetic_kinds``; a tattoo and an
    injection as one act, catalogue.ONE_ACT)."""
    kinds = _synthetic_kinds(entry)
    return frozenset(target for target in wanted if target in kinds
                     or (target in catalogue.ONE_ACT and bool(kinds & catalogue.ONE_ACT)))


def _synthetic_read_under(R: FactSet, entry: UnlistedStatement, family: SessionKind, kinds: frozenset[Kind]) -> bool:
    """``_read_under`` for a synthetic act: its card may be a session of a family whose act of one of ``kinds`` is read
    under ``family`` (catalogue.READ_UNDER; its regions not read, as for a filed act)."""
    return any(under is family and kind in kinds and _synthetic_of_family(R, entry, owner)
               for (owner, kind), (under, _regions) in catalogue.READ_UNDER.items())


def _may_hold(R: FactSet, session: Id, kind: Kind) -> bool:
    """K2's admission over THE table of a session family's kinds (requirements_table.FAMILY_KINDS, DECISIONS D191):
    whether a family ``session``'s kind may be (facts.possibly over its kind fact: every family for an empty slot)
    holds ``kind`` - DECISIONS D256 P2's "an entry with no card that names a kind makes possibly done only sessions
    whose family holds that kind (K2)". (P1's no-card arm reads coverage.doubted_in's admission alone:
    ``_listed_doubted``; the step's NOTES, question Q-P1K2.) Weakening the session's kind only adds families."""
    return any(kind in facts_.family_kinds(family) for family in SessionKind if _session_may_be(R, session, family))


def _session_families(R: FactSet, session: Id) -> frozenset[SessionKind]:
    """The families ``session`` may be of as step 4b's coverage.session_families reads them for its doubted list: its
    kind when supported; every other kind when negated; facts.possibly's otherwise (every kind for an empty slot)."""
    found = _fact(R, session, _A.KIND)
    if found.result is Result.SUPPORTED:
        return frozenset(family for family in SessionKind if found.value is family)
    if found.result is Result.NEGATED:
        return frozenset(family for family in SessionKind if found.value is not family)
    return frozenset(family for family in SessionKind if facts_.possibly(found, family))


def _reportable_kinds(family: SessionKind) -> frozenset[Kind]:
    """coverage.reportable_kinds (v1's reportable_kind for ``family``): its catalogue acts but the examination, the
    umbrellas and NOT_REPORTED, and (D116) the stent removal and exchange where its acts hold the stent placement."""
    acts = frozenset(catalogue.FAMILY_ACTS.get(family, ()))
    return frozenset(kind for kind in acts if kind not in _NOT_ACTS and kind not in catalogue.NOT_REPORTED) | (
        _STENT_ACTS if Kind.STENT in acts else frozenset())


def _eus_unlisted_kind(kind: Kind) -> bool:
    """coverage.eus_unlisted_kind (D137, D145): a catalogue kind of an EUS act that the EUS's catalogue entry does not
    list, and no examination, umbrella, E/M kind or NOT_REPORTED kind."""
    return (kind not in catalogue.FAMILY_ACTS[SessionKind.EUS] and kind not in _NOT_ACTS and kind not in EM_KINDS
            and kind not in catalogue.NOT_REPORTED)


def _listed_doubted(R: FactSet, kind: Kind, session: Id) -> bool:
    """DECISIONS D256 P1: whether step 4b's event_coding@2 would list, among ``session``'s doubted acts, the filed
    doubted form of an unlisted entry with no card that names ``kind`` - an act filed with its kind supported ``kind``,
    its status a doubt that it was performed, its session slot silent and every other slot empty (coverage's
    _filed_doubted_form for no card). event_coding never lists an E/M kind beside a session (the session's own service),
    and lists the rest where coverage.doubted_in admits it - which, for that form, reads only the kind and the families
    the session may be of (coverage.session_families): nothing else of the act is established, so its required facts
    are in doubt and it is doubted wherever it may be reportable. Admitted: no examination or umbrella but the removal
    (D117: any of its members); and, in a family the session may be of, a catalogue kind the act may be (a clip or an
    injection, its purpose unknown, is a bleeding control too: D157) among that family's reportable kinds
    (coverage.reportable_kinds), or a removal where the family's acts hold one of its members (D117), or, in an EUS, a
    catalogue kind its entry does not list (D145: coverage.eus_unlisted_kind, kind other included). A session the
    FactSet does not hold is no session the act may be in. coverage imports this module, so its derivation is read
    here, and tests/v2/test_combination.py pins the two readers equal over every kind and session shape (the step's
    NOTES: one home for both is the integration's)."""
    if session not in R.sessions or kind in EM_KINDS or (kind in _NOT_ACTS and kind is not Kind.REMOVAL):
        return False
    members = catalogue.UMBRELLAS.get(kind, (kind,))
    kinds = frozenset(found for member in members if member is not Kind.OTHER
                      for found in ((member, Kind.BLEEDING_CONTROL) if member in catalogue.HEMOSTASIS_KINDS
                                    else (member,)))
    eus = kinds | (frozenset(members) & frozenset({Kind.OTHER}))
    for family in _session_families(R, session):
        acts = catalogue.FAMILY_ACTS.get(family, ())
        if kinds & _reportable_kinds(family):
            return True
        if kind is Kind.REMOVAL and any(member in acts for member in catalogue.REMOVAL_MEMBERS):
            return True
        if family is SessionKind.EUS and any(_eus_unlisted_kind(found) for found in eus):
            return True
    return False


# --- the codes --------------------------------------------------------------------------------------------------------


def is_base(code: str) -> bool:
    """v1's _base: a base profile (CodeProfile.base: an endoscopic family's diagnostic examination, or an office visit
    code - two E/M codes of one visit hold each other), or a code whose covers are all the examination (an
    examination-only EUS code: 43231, 43237, 43259, 45341, 45391, 44406). An E/M add-on (99417) is neither."""
    profile = catalogue.code_profile(code)
    if profile is None:
        return False
    return profile.base or (bool(profile.covers) and all(kind is Kind.EXAMINATION for kind in profile.covers))


def accounts_for_an_act(code: str) -> bool:
    """Whether a code's profile covers a kind (v1's base rule (a): "another counted code ... that accounts for an
    act")."""
    profile = catalogue.code_profile(code)
    return profile is not None and bool(profile.covers)


def is_addon(code: str) -> bool:
    """DECISIONS D255: whether ``code`` is an add-on code - a key of engine/assess.ADDON_PRIMARIES (43273, 91013, 99153,
    99417), read here as the catalogue's add-on profile (catalogue.Profile.addon), which tests/v2/test_assess.py and
    tests/v2/test_combination.py pin equal to those keys and to requirements_table's ADDON codes (engine/assess imports
    this module, so it is not imported here). An add-on is reported in addition to its primaries: it is never a code
    that includes another under the base rules (base_included's (a), the within codes), never causes such a hold and is
    never named in one; an add-on and its primaries are governed by assess's ADDON row alone."""
    profile = catalogue.code_profile(code)
    return profile is not None and profile.addon


# --- the competition's claims (D40, D55, D74, D104, D118, D163, D167) -------------------------------------------------


def _technique_fits(R: FactSet, technique: TechniqueClass | None, event: Id) -> bool:
    """R4: an act a technique code may account for - its device not established as another technique class (a device
    supported in a class other than the code's; a device of no class, or not established, may be the code's)."""
    if technique is None:
        return True
    device = _fact(R, event, _A.TECHNIQUE_DEVICE)
    if device.result is not Result.SUPPORTED or not isinstance(device.value, Device):
        return True
    found = catalogue.technique_class(device.value)
    return found is None or found is technique


def _read_under(R: FactSet, event: Id, family: SessionKind, kinds: frozenset[Kind]) -> bool:
    """catalogue.READ_UNDER over facts: ``event`` may be in a session of a family whose act of one of ``kinds`` is read
    under ``family``. The rule's regions are not read: a place list may be short, and an act set outside them by its
    listed places alone could lose a claim to a deleted member (P6; module docstring)."""
    return any(under is family and kind in kinds and may_be_of_family(R, event, owner)
               for (owner, kind), (under, _regions) in catalogue.READ_UNDER.items())


def site_outside(code: str, R: FactSet, event: Id) -> bool:
    """DECISIONS D29 as D240 keeps it ("A verified target outside the class does not support"): whether ``event``'s
    target is ESTABLISHED outside ``code``'s site class (catalogue.site_class; never for a code with none) - evaluate's
    SITE row failing, read the same way (evaluate._places_of and _row_site, step 4a's; the module docstring): the act's
    target lesion established or an empty slot; every place of the act, and of that lesion when it is supported,
    established; at least one place supported; and every supported place outside the class, none surgically made or
    unplaced (UNPLACED_SITES: D29's "an unverified or ambiguous target (an anastomosis) holds"). A place or a lesion not
    established leaves the act possibly within the class (4.2), so weakening a fact only ever undoes this; only a
    deleted place member can make it hold (D240's named release; the module docstring)."""
    site = catalogue.site_class(code)
    if site is None:
        return False
    lesion = _fact(R, event, _A.TARGET_LESION)
    if not (facts_.established(lesion) or facts_.silent(lesion)):
        return False
    places = list(facts_.members(R, event, _A.TARGET_PLACES))
    if lesion.result is Result.SUPPORTED and isinstance(lesion.value, Id):
        places += facts_.members(R, lesion.value, _A.PLACES)
    if not all(facts_.established(member) for member in places):
        return False
    supported = [member.value for member in places
                 if member.result is Result.SUPPORTED and isinstance(member.value, Landmark)]
    within = catalogue.SITE_CLASSES[site]
    return bool(supported) and all(place not in within and place not in UNPLACED_SITES for place in supported)


def may_account_for(code: str, R: FactSet, event: Id) -> bool:
    """Whether ``code`` may account for ``event`` (the OWN arm of ``claims``; module docstring): a candidate of one of
    its requirement groups, possibly today's (4.4's frame), possibly of its family (route (b): of any family), of its
    technique class, and not established outside its site class (D29's site fit, DECISIONS D240: ``site_outside``).
    No other place list is read: route (b)'s and READ_UNDER's regions could release a rival when a member is deleted
    (P6)."""
    spec = rq.spec(code)
    wanted = frozenset(kind for group in spec.groups for kind in group)
    if not wanted:
        return False
    kinds = _may_be_of(R, event, wanted)
    if not kinds or not possibly_today(R, event):
        return False
    link = catalogue.code_link(code)
    if link.route is not catalogue.LinkRoute.UNRECONCILED and not (
            may_be_of_family(R, event, spec.family) or _read_under(R, event, spec.family, kinds)):
        return False
    return _technique_fits(R, link.technique, event) and not site_outside(code, R, event)


def synthetic_claims(code: str, R: FactSet, supporting: Sequence[Id] = ()) -> tuple[int, ...]:
    """DECISIONS D231 row 5: the synthetic acts ``code`` may account for (``synthetic``; ``claims``' arms over
    FactSet.unlisted, in stored order), each CARDED ("an unlisted act with a card": ``_card``; an entry with no card is
    no act any code claims here): OWN - a kind of one of its requirement groups (``_synthetic_may_be_of``: every kind
    when the entry names none), its card possibly a session of its family (``_synthetic_of_family``; READ_UNDER's rule
    admits one of a family read under it; on route (b), of any family) - and D55's - for a narrowed code whose other
    covered kinds are opened (``_opened_extras``, over the code's E* ``supporting`` and its family's acts), one of those
    kinds, its card possibly of its family - so a code competes for a carded synthetic act exactly where it would
    compete for the act filed in doubt in that session (D118 adds nothing here: a synthetic act's technique is unknown,
    so the OWN arm already admits it). A synthetic act's status, date, performer, device and places are unknown, so
    4.4's frame, R4's technique and D29's site fit never set it apart (each an established fact). Indices, never event
    ids: ``claims`` (which step 5a reads) stays the documented events, and ``combine`` adds the competition these make
    (the module docstring)."""
    spec = rq.spec(code)
    wanted = frozenset(kind for group in spec.groups for kind in group)
    link = catalogue.code_link(code)
    extras = _opened_extras(code, R, supporting)
    if not wanted and not extras:
        return ()
    out: list[int] = []
    for index in synthetic(R):
        entry = R.unlisted[index]
        if _card(R, entry) is None:
            continue  # D231 row 5: "an unlisted act with a card" (refute-r4d-r1 of build-v2/w7r, F3)
        kinds = _synthetic_may_be_of(entry, wanted)
        if kinds and (link.route is catalogue.LinkRoute.UNRECONCILED or _synthetic_of_family(R, entry, spec.family)
                      or _synthetic_read_under(R, entry, spec.family, kinds)):
            out.append(index)
        elif _synthetic_may_be_of(entry, extras) and _synthetic_of_family(R, entry, link.family):
            out.append(index)
    return tuple(out)


def _possible_lesion_values(found: Fact) -> frozenset[Id]:
    """The lesion ids a target.lesion fact may name: its supported value; its claimed value and options when not
    established; none when silent or negated."""
    if found.result is Result.SUPPORTED:
        return frozenset({found.value}) if isinstance(found.value, Id) else frozenset()
    if facts_.silent(found) or found.result is Result.NEGATED:
        return frozenset()
    return frozenset(value for value in (found.value, *found.options) if isinstance(value, Id))


def one_stricture(R: FactSet, first: Id, second: Id) -> bool:
    """DECISIONS D118 over facts ("one stricture by same lesion or places not disjoint", 4.7), erring toward one: the
    two acts' lesions possibly the same (a lesion both may name); else neither set apart by lesion
    (facts.apart_by_lesion: both supported and different, distinct_from supported, the lesion pair controls rejected)
    nor by place (facts.apart_by_place: established, disjoint, the pair controls rejected). An unknown identity never
    sets two acts apart (4.11)."""
    if _possible_lesion_values(_fact(R, first, _A.TARGET_LESION)) & _possible_lesion_values(
            _fact(R, second, _A.TARGET_LESION)):
        return True
    return not (facts_.apart_by_lesion(R, first, second) or facts_.apart_by_place(R, first, second))


def _synthetic_opens(R: FactSet, kinds: frozenset[Kind], family: SessionKind) -> bool:
    """DECISIONS D231 row 4: a synthetic act (``synthetic``) that may be of one of ``kinds`` (every kind when it names
    none) and whose card may be of ``family`` (``_synthetic_of_family``: "whose card may be of the code's family"; an
    entry with no card opens nothing) - a possibly performed act of those kinds in the family, read as a filed doubted
    act of the kind in that session would be."""
    return any(_synthetic_may_be_of(R.unlisted[index], kinds) and _synthetic_of_family(R, R.unlisted[index], family)
               for index in synthetic(R))


def _extra_of_family(R: FactSet, family: SessionKind, event: Id, kinds: frozenset[Kind]) -> bool:
    """D55's act test: ``event`` may be of one of ``kinds``, possibly positive, not established at another date (any
    performer), possibly in a session of ``family``."""
    return (bool(_may_be_of(R, event, kinds)) and _possibly_positive_on_date(R, event)
            and may_be_of_family(R, event, family))


def _opened_extras(code: str, R: FactSet, supporting: Sequence[Id]) -> frozenset[Kind]:
    """D55, D74, D104, D167 (module docstring): a narrowed code's other covered kinds, once its family has an act that
    may be of a defining kind, possibly positive and not established at another date - a filed act, or a synthetic act
    of a defining kind or none whose card may be of its family (DECISIONS D231 row 4) - or its E* is not empty; none
    otherwise."""
    link = catalogue.code_link(code)
    if not link.defining:
        return frozenset()
    others = frozenset(link.acts) - frozenset(link.defining)
    defining = frozenset(link.defining)
    if others and (supporting or any(_extra_of_family(R, link.family, event, defining) for event in R.events)
                   or _synthetic_opens(R, defining, link.family)):
        return others
    return frozenset()


def _defining_extras(code: str, R: FactSet, supporting: Sequence[Id]) -> tuple[Id, ...]:
    """D55, D74, D104, D167 (module docstring): the filed acts of a narrowed code's other covered kinds once they are
    opened (``_opened_extras``), its E* aside."""
    others = _opened_extras(code, R, supporting)
    if not others:
        return ()
    family = catalogue.code_link(code).family
    return tuple(event for event in R.events
                 if event not in supporting and _extra_of_family(R, family, event, others))


def _stricture_claims(code: str, R: FactSet, own: Sequence[Id]) -> tuple[Id, ...]:
    """D118 (module docstring): a technique code's claims on ONE stricture with ANOTHER act of its own - the acts of its
    family that may be of its kinds, possibly positive and not established at another date, any performer and any
    technique. A synthetic act of its kinds or none whose card may be of its family is another act of its own
    (DECISIONS D231 row 4): its technique, its site and its lesion are unknown, so it may be the code's and nothing sets
    it apart from any act (4.11: an unknown identity never sets two acts apart)."""
    link = catalogue.code_link(code)
    if link.technique is None:
        return ()
    kinds = frozenset(link.acts)
    unlisted = _synthetic_opens(R, kinds, link.family)
    if not own and not unlisted:
        return ()
    return tuple(event for event in R.events
                 if _may_be_of(R, event, kinds) and _possibly_positive_on_date(R, event)
                 and may_be_of_family(R, event, link.family)
                 and (unlisted or any(mine != event and one_stricture(R, mine, event) for mine in own)))


def claims(code: str, R: FactSet, supporting: Sequence[Id] = ()) -> tuple[Id, ...]:
    """The acts ``code`` claims for the competition (module docstring; v1's assess._claims as FINAL-V2 4.7 and 4.8
    rewire it), whatever the code's state: its E* and every act it may account for (OWN), D55's and D167's acts of a
    narrowed code's other kinds, and D118's acts on one stricture - E* first, in the order given, then pass 1's order.
    An act a technique code cannot account for (its device established as another technique class, R4) is not claimed
    as its E*, and no act established outside a site code's class is claimed by any arm (D29's site fit, DECISIONS
    D240: ``site_outside``): a dilation the code could never account for is no act it competes for."""
    link = catalogue.code_link(code)
    given = tuple(dict.fromkeys(event for event in supporting if _technique_fits(R, link.technique, event)
                                and not site_outside(code, R, event)))
    own = given + tuple(event for event in R.events if event not in given and may_account_for(code, R, event))
    found = list(own)
    for event in _defining_extras(code, R, supporting) + _stricture_claims(code, R, own):
        if event not in found and not site_outside(code, R, event):
            found.append(event)
    head = [event for event in found if event in given]
    tail = [event for event in found if event not in given]
    return tuple(head) + _ordered(R, tail)


_H = TypeVar('_H', bound=Hashable)


def _rivals(entries: Sequence[tuple[str, str, str, Sequence[_H]]]) -> dict[str, tuple[str, ...]]:
    """competition's rule over any claimed items (event ids, or synthetic acts' indices)."""
    out: dict[str, tuple[str, ...]] = {}
    for key, code, _origin, supporting in entries:
        mine = frozenset(supporting)
        rivals = [other_code for other_key, other_code, _other_origin, other_items in entries
                  if other_key != key and other_code != code and mine & frozenset(other_items)]
        if rivals:
            out[key] = tuple(dict.fromkeys(rivals))
    return out


def _shared(entries: Sequence[tuple[str, str, str, Sequence[_H]]]) -> dict[str, tuple[_H, ...]]:
    """contested's rule over any claimed items."""
    out: dict[str, tuple[_H, ...]] = {}
    for key, code, _origin, supporting in entries:
        shared = [item for item in supporting
                  if any(other_key != key and other_code != code and item in other_items
                         for other_key, other_code, _other_origin, other_items in entries)]
        if shared:
            out[key] = tuple(dict.fromkeys(shared))
    return out


def competition(entries: Sequence[tuple[str, str, str, Sequence[Id]]]) -> dict[str, tuple[str, ...]]:
    """FINAL 7.9 Competing, as the installed engine's completion repair and DECISIONS D40 amend P-ADMIT2 (v1's,
    unchanged): ``entries`` (key, code, origin, claims) of the counted codes; two of them with different codes whose
    claims intersect - the same documented act - are each held with one question naming the others, WHOEVER proposed
    either. ``origin`` is kept in the entry and never read. {key: the rival codes, in entry order, each once} of every
    held code. ``combine`` applies the same rule over the synthetic acts' claims (DECISIONS D231 row 5)."""
    return _rivals(entries)


def contested(entries: Sequence[tuple[str, str, str, Sequence[Id]]]) -> dict[str, tuple[Id, ...]]:
    """For every code ``competition`` holds, the acts it shares with its rivals, in its claims' order (the acts its
    competing_codes item quotes)."""
    return _shared(entries)


# --- base (engine.base_included; FINAL 7.9, D119, D177(1), 3.2.6 rule 3) ----------------------------------------------


def session_acts(coding: Mapping[Id, SessionActs], session: Id) -> SessionActs:
    """Step 4b's reportable and doubted acts of ``session`` (module docstring). event_coding@2 lists every session of
    the FactSet, so a session ``coding`` does not list is a wiring error: ValueError, never "no acts" (the
    refutation's F5: read as empty, it would release a base code beside acts nobody listed)."""
    found = coding.get(session)
    if found is None:
        raise ValueError(f'coding lists no session {session}: event_coding@2 lists every session of the FactSet.')
    return found


def _peg_acts(R: FactSet, coding: Mapping[Id, SessionActs], session: Id) -> SessionActs:
    """DECISIONS D119: the reportable and the doubted acts of every OTHER session (of the FactSet, and any other
    ``coding`` lists) whose kind may be the feeding tube's, that may be PEG placements - each such session read through
    ``session_acts``, so one missing from ``coding`` is refused, never skipped."""
    reportable: list[Id] = []
    doubted: list[Id] = []
    for other in dict.fromkeys((*R.sessions, *coding)):
        if other == session or not _session_may_be(R, other, PEG_SESSION_KIND):
            continue
        acts = session_acts(coding, other)
        reportable += [event for event in acts.reportable if facts_.possibly(_fact(R, event, _A.KIND), Kind.PEG)]
        doubted += [event for event in acts.doubted if facts_.possibly(_fact(R, event, _A.KIND), Kind.PEG)]
    return SessionActs(tuple(reportable), tuple(doubted))


def _one_session(R: FactSet, session: Id) -> bool:
    """DECISIONS D256 as D269 counts it, amended by D285 ruling A.1 (Q-COUNT; refute-r4d-r1 V9R4D1-1): whether
    ``session`` is the one session the document tells - beside it the count counts only a session that one of its OWN
    filed events establishes as performed on the date of service (``_performed_today``: an event whose session is
    supported that session and which is done, 4.3 rows 2-5, a digital examination excepted) and whose own established
    examinations do not establish it not done today (``_examinations_not_done_today``, not_done_today's first arm, the
    one derivation both read; D256 P2's reading). A session told only by planned, earlier, denied, doubted or open
    events, a session with no event, a session only possibly done today, and every kept unlisted entry leave the
    kindless one-session hold on; a settled session never counts, whatever its acts (D269). The count reads neither
    not_done_today's second arm nor ``_claims_session``, so AMENDMENT-2 4.3.3 c's repair of the claimed-value readers
    moves only D269's exemption, never this count (D285, built in one commit with it). Both conditions need established
    facts or their absence over established examinations, so no 9.4 weakening adds a counted session: as built, D269's
    count counted every session that was not established not done today, so a single weakening of the second session's
    planned examination (its kind, session, status or date) released 45378's hold (count_probe: 8, 12 and 12 releasing
    weakenings per shape). Its one release under a weakening is named with Q-UNNAMED (D285 A.1): a second session whose
    examination is established planned or earlier but which holds an established done event of its own today; weakening
    that examination leaves a session established performed today by a filed event, D256's two-session reading. Two
    sessions established performed today keep D256's named residual Q-UNNAMED (an office visit beside a colonoscopy). A
    session the FactSet does not hold is none."""
    if session not in R.sessions:
        return False
    return not any(other != session and _performed_today(R, other) and not _examinations_not_done_today(R, other)
                   for other in R.sessions)


def _performed_today(R: FactSet, session: Id) -> bool:
    """DECISIONS D285 ruling A.1: one of ``session``'s own filed events establishes it as performed on the date of
    service - its session supported ``session`` (facts.holds) and it is done (4.3 rows 2-5, reading.done), a digital
    examination excepted (E13, ``_digital``). Established facts only: no weakening and no kept unlisted entry adds
    one."""
    view = reading.Reading.of(R)
    return any(facts_.holds(_fact(R, event, _A.SESSION), session) and reading.done(view, event)
               and not _digital(R, event) for event in R.events)


def _unlisted_acts(R: FactSet, session: Id) -> tuple[int, ...]:
    """FINAL-V2 3.2.6 rule 3 as DECISIONS D231, D232 and D256 read it: the indices of the synthetic acts (``synthetic``:
    the kept unlisted acts AND doubts) that hold ``session``'s base code as synthetic doubted acts of the session, in
    stored order:
    - one carded to the session (``_card``), whatever its kind (pass 2 names the session; D232: "the base code keeps
      rule 3's base_included hold");
    - one with no card (or a card the FactSet does not hold) that names a kind, where the session's family may hold
      that kind as coverage.doubted_in reads it: step 4b would list its filed doubted form among the session's doubted
      acts (``_listed_doubted``) - D256 P1, Q-CARD option (c), "exactly what coverage.doubted_in admits for the filed
      doubted form": where the same act filed in doubt with its session slot silent holds the base code through 4b's
      doubted list (refute-r4d-r2 P1: read as no session, a one-session colonoscopy's 45378 went READY beside an
      unlisted biopsy whose card pass 2 left empty). Never an E/M kind beside its own session, moderate sedation, an
      umbrella of interventions, or kind other outside an EUS (refute-r4d-r1 of build-v2/w7r, F4's kinds: 4b lists none
      of them);
    - one with no card that names no kind, when the session is the document's one session (D256); in a document of
      more than one session it stays out - the named residual Q-UNNAMED, measured at D2-D3 (refute-r4d-r1 F1: read in
      every session, it held an office visit's base code beside a colonoscopy with nothing the hold could name).
      DECISIONS D269 as D285 ruling A.1 counts it (refute-r4d-r1 V8R4D1-3, V9R4D1-1): "a document that tells one
      session" counts beside the held session only a session one of its own filed events establishes as performed
      today and whose own established examinations do not establish it not done today (``_one_session``), so a planned
      repeat colonoscopy filed as a session of its own leaves the colonoscopy done today the document's one session,
      and so does a second session only possibly done today.
    Every entry is still consumed by its other rules (completeness; an overlapped code; rule 4 for a doubt; the same-day
    rule; rows 1 and 2 here)."""
    alone: bool | None = None  # read once, and only for a kindless entry with no card
    out: list[int] = []
    for index in synthetic(R):
        entry = R.unlisted[index]
        card = _card(R, entry)
        if card is not None:
            held = card == session
        elif entry.kind is None:
            if alone is None:
                alone = _one_session(R, session)
            held = alone
        else:
            held = _listed_doubted(R, entry.kind, session)
        if held:
            out.append(index)
    return tuple(out)


def _unlisted_pegs(R: FactSet, session: Id) -> tuple[int, ...]:
    """DECISIONS D231 row 3 (D119's arm over the synthetic act): the indices of the synthetic acts of kind PEG or none
    whose card (``_card``) is a session other than ``session`` whose kind may be the feeding tube's ("whose card may be
    the feeding tube's session") - possibly a PEG of the feeding-tube session, which D119 reads as an act of the upper
    endoscopy done with it too. An entry with no card is read by no session here (rule (c)'s own arm reads it: a PEG
    with no card holds the upper endoscopy's base code where step 4b would list it doubted, DECISIONS D256 P1)."""
    out: list[int] = []
    for index in synthetic(R):
        card = _card(R, R.unlisted[index])
        if (Kind.PEG in _synthetic_kinds(R.unlisted[index]) and card is not None and card != session
                and _session_may_be(R, card, PEG_SESSION_KIND)):
            out.append(index)
    return tuple(out)


def addon_acts(members: Sequence[Member], session: Id) -> frozenset[Id]:
    """DECISIONS D268 (refute-r4d-r1 V8R4D1-1; r4d's Q-ADDON-ACT option (b), narrowed): the acts a counted add-on code
    (``is_addon``) matched to ``session`` accounts for as its supporting acts (its E*, ``Member.supporting``) - the
    cholangioscopy beside a counted 43273. Base rules (b) and (c) read none of them: the add-on is reported WITH its
    primary (assess's ADDON row), so the act it accounts for is never one "this diagnostic code does not account for";
    DECISIONS D286 ruling E widens this by kind (``addon_kinds``). Read over the counted set alone (the engine's, or a
    reviewer's at read time): with the add-on not counted the rules read as built."""
    return frozenset(event for other in members if other.session == session and is_addon(other.code)
                     for event in other.supporting)


def addon_kinds(members: Sequence[Member], session: Id, family: SessionKind) -> frozenset[Kind]:
    """DECISIONS D286 ruling E (G3-12; amending D268's narrowing, which read the add-on's supporting act alone): the act
    kinds a counted add-on code (``is_addon``) matched to ``session`` covers (catalogue.Profile.covers) that no
    non-add-on code of ``family`` covers (catalogue profiles) - whenever a counted add-on of the session accounts for
    every act of a kind its family's other codes do not, an act of that kind is the add-on's, never one the base code
    "does not account for". On this catalogue only office_em (em_prolonged, 99417) and ERCP (cholangioscopy, 43273) have
    an add-on and base codes, and each kind is covered by its add-on alone (tests/v2/test_combination.py pins that, so a
    catalogue change fails the gate). Empty with no add-on counted: the base rules then read as built."""
    covered: set[Kind] = set()
    for other in members:
        profile = catalogue.code_profile(other.code)
        if other.session == session and is_addon(other.code) and profile is not None:
            covered.update(profile.covers)
    others = {kind for profile in catalogue.CODES.values() if profile.family is family and not profile.addon
              for kind in profile.covers}
    return frozenset(covered - others)


def base_included(members: Sequence[Member], coding: Mapping[Id, SessionActs], R: FactSet) -> tuple[BaseIncluded, ...]:
    """A family's base code matched to session S is held, never excluded, beside (a) another counted code of its family
    matched to S that accounts for an act, never an add-on (DECISIONS D255: ``is_addon``), (b) S's reportable acts, or
    (c) S's doubted acts and the synthetic acts that hold it (``_unlisted_acts``: carded to S, or D256's readings of an
    entry with no card) (module docstring), in member order - rules (b) and (c) never reading an act a counted add-on
    code of S accounts for as its supporting act (DECISIONS D268: ``addon_acts``), nor, by DECISIONS D286 ruling E
    (amending D268's narrowing), an act of a kind a counted add-on code of S covers that no non-add-on code of the base
    code's family covers (``addon_kinds``): a filed act whose kind is supported so, or a kept unlisted entry that names
    that kind. ValueError when ``coding`` does not list S (or, for D119, a session that may be the feeding tube's): step
    4b lists every session (``session_acts``)."""
    found: list[BaseIncluded] = []
    for index, member in enumerate(members):
        session = member.session
        if session is None or not is_base(member.code):
            continue
        acts = session_acts(coding, session)
        beside = tuple(other.code for position, other in enumerate(members)
                       if position != index and other.family is member.family and other.session == session
                       and accounts_for_an_act(other.code) and not is_addon(other.code))  # D255
        tract = catalogue.eus_tract(member.code)
        others = tuple(code for code in beside if catalogue.eus_tract(code) is tract)  # D177 (1)
        reportable, doubted = acts.reportable, acts.doubted
        unlisted = _unlisted_acts(R, session)
        if member.family is PEG_FAMILY:  # D119
            pegs = _peg_acts(R, coding, session)
            reportable, doubted = reportable + pegs.reportable, doubted + pegs.doubted
            unlisted = tuple(dict.fromkeys(unlisted + _unlisted_pegs(R, session)))  # D231 row 3
        accounted = addon_acts(members, session)  # D268: rules (b) and (c) read none of the add-on's own acts
        covered = addon_kinds(members, session, member.family)  # D286 ruling E: nor an act of the add-on's own kind
        accounted = accounted | frozenset(event for event in (*reportable, *doubted)
                                          if any(facts_.holds(_fact(R, event, _A.KIND), kind) for kind in covered))
        reportable = tuple(event for event in _ordered(R, reportable) if event not in accounted)
        doubted = tuple(event for event in _ordered(R, doubted) if event not in reportable and event not in accounted)
        unlisted = tuple(sorted(index for index in unlisted if R.unlisted[index].kind not in covered))
        if beside or reportable or doubted or unlisted:
            named = tuple(dict.fromkeys(kind for kind in (R.unlisted[index].kind for index in unlisted)
                                        if kind is not None))
            found.append(BaseIncluded(key=member.key, code=member.code, session=session, beside=tuple(
                dict.fromkeys(beside)), others=tuple(dict.fromkeys(others)), reportable=reportable, doubted=doubted,
                unlisted=unlisted, unlisted_kinds=named))
    return tuple(found)


# --- base-within (C3, C-4, D70) ---------------------------------------------------------------------------------------


def _manual(R: FactSet, event: Id) -> bool:
    """FINAL 5.6 E13: an examination whose device is supported manual (a digital examination) is no session - the
    established reading, which the possible whole (``session_possibly_done``, and ``not_done_today``'s open
    examination) and the procedure day read: a device not established leaves the event possibly the session's,
    fail-closed. ``session_done`` reads ``_digital``."""
    return (facts_.holds(_fact(R, event, _A.KIND), Kind.EXAMINATION)
            and facts_.holds(_fact(R, event, _A.TECHNIQUE_DEVICE), Device.MANUAL))


def _digital(R: FactSet, event: Id) -> bool:
    """FINAL 5.6 E13's digital examination as ``session_done`` reads it - evaluate._digital's reading (DECISIONS D253,
    QE13 option (a): "the claimed-manual reading (monotone) holds in evaluate and in combination alike", repair r4a's
    R2): an event that may be an examination (its kind possibly the examination, facts.possibly) whose device CLAIMS
    manual - supported manual, or, not established, manual its claimed value or one of its readings
    (facts.possibly_written over a device that is not silent: a claimed value, never DECISIONS D294 RD-3's open
    denial). Each 9.4 weakening keeps a claimed value, so a weakened device never turns a digital
    examination into the session's own examination or into an act that makes it done; a silent device, one established
    as another device, and manual negated claim none. An overfilled device slot's merged view (AMENDMENT-2 4.3.3 c
    [R:truth-T2]) claims manual whenever a written fact states it or a doubt offers it, as that fact read alone would:
    a manual only denied (``negated_values``: every written fact naming it denies it, and no doubt offers it) is no
    claim, so an endoscope written beside a denied manual never turns the examination into a digital one. engine/evaluate imports this module through engine/questions, so its predicate is read here, and
    tests/v2/test_combination.py pins the two equal (``_examinations`` empty exactly where evaluate.act_only holds)."""
    device = _fact(R, event, _A.TECHNIQUE_DEVICE)
    # the kind a possibility, the device a CLAIMED value (4.3.3 c): read without DECISIONS D294 RD-3's open denial
    return (facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION)
            and facts_.possibly_written(device, Device.MANUAL)
            and Device.MANUAL not in device.negated_values and not facts_.silent(device))


def _examinations(R: FactSet, session: Id) -> tuple[Id, ...]:
    """The session's established examinations: kind supported examination, session supported ``session``, a digital
    examination excepted (E13, ``_digital``: a device claiming manual - evaluate.act_only's set)."""
    return tuple(event for event in R.events
                 if facts_.holds(_fact(R, event, _A.KIND), Kind.EXAMINATION)
                 and facts_.holds(_fact(R, event, _A.SESSION), session) and not _digital(R, event))


def _may_be_examination_of(R: FactSet, session: Id, event: Id) -> bool:
    """``event`` may be ``session``'s examination (D62's possible examination): its kind possibly the examination, the
    session possibly ``session`` (possible_sessions: a session id the FactSet does not hold may be any session, D227
    R2-2), possibly today's (4.4's frame), no digital examination (``_digital``: a device claiming manual, QE13)."""
    return (facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION) and session in possible_sessions(R, event)
            and possibly_today(R, event) and not _digital(R, event))


def synthetic_examinations(R: FactSet, session: Id) -> tuple[int, ...]:
    """DECISIONS D231 row 1: the indices of the synthetic acts (``synthetic``: kept unlisted acts and doubts) that may
    be ``session``'s examination - of kind examination or none named, possibly in it (``synthetic_sessions``). Each is
    a possibly performed examination of the session that is never done (its status is the doubt; it has no date,
    performer or entry) and never a digital one (no device is established), as ``_may_be_examination_of`` reads a filed
    examination in doubt."""
    return tuple(index for index in synthetic(R) if Kind.EXAMINATION in _synthetic_kinds(R.unlisted[index])
                 and synthetic_in(R, R.unlisted[index], session))


def session_done(R: FactSet, session: Id) -> bool:
    """A session is done (4.3 row 7: "its examination, when it has one, passes 2-5 (an act-only session: the act
    itself)"; 4.7's "done = 4.3 rows 2-5"): one of its established examinations passes rows 2-5 (reading.done); with
    none, one of its acts (session supported) passes them - a session told only through its acts (D121, D135) - and no
    event that may be its examination is left open (the refutation's F3: an examination whose date is not established
    beside a done FNA leaves the EUS only possibly done; an event whose session fact names an id the FactSet does not
    hold may be any session's examination, D227 R2-2), nor a synthetic act that may be (``synthetic_examinations``:
    DECISIONS D231 row 1, read only in an act-only session - beside an established examination, D232's reading: a
    synthetic examination adds nothing there). A digital examination is excepted throughout (E13), read as evaluate
    reads it (``_digital``: a device claiming manual - DECISIONS D253, QE13 option (a)), so the act-only session is
    evaluate.act_only's. DECISIONS D227: THE derivation of "a session is done" - step 4b's done_examinations,
    possible_examinations and session event must give its answer (its cross-module test reads this function, so its
    signature stays)."""
    view = reading.Reading.of(R)
    exams = _examinations(R, session)
    if exams:
        return any(reading.done(view, event) for event in exams)
    if any(_may_be_examination_of(R, session, event) and not reading.done(view, event) for event in R.events):
        return False
    if synthetic_examinations(R, session):
        return False
    return any(facts_.holds(_fact(R, event, _A.SESSION), session) and reading.done(view, event)
               and not _digital(R, event) for event in R.events)


def _claims_session(R: FactSet, event: Id, session: Id) -> bool:
    """Whether ``event``'s session fact CLAIMS ``session`` (facts.claimed_values, AMENDMENT-2 4.3.3 c and DECISIONS D279
    item 5 [R:truth-T1]): its supported value, or - not established - its claimed value, and each side of a
    contradiction: pass 1's own contradicted session (its settled value empty, its sides the options), a session fact
    settled contradicted, and an overfilled session slot's written sessions that it does not deny - never a doubt's
    reading of a claim that is not contradicted, an empty slot a doubt names alone, or a negated claim. As built the
    reader saw only the claimed value, so pass 1's own contradicted session claimed nothing, and a planned examination
    beside it made its session established not done today (demo_within_contradicted: 43235 READY beside a same-day EUS
    whose done examination's session pass 1 contradicted). Each 9.4 weakening keeps a claimed value (an established fact
    to unresolved, an added doubt) and never removes a side, so an event placed in a session by its session fact stays
    placed in it under every weakening, value-erasing contradictions included (4.4)."""
    return session in facts_.claimed_values(_fact(R, event, _A.SESSION))


def _open_examination(R: FactSet, session: Id, event: Id) -> bool:
    """An event that may be ``session``'s examination done on the date of service (``not_done_today``'s second arm,
    DECISIONS D269 as the step's question Q-NDT builds it): its session fact claims the session (``_claims_session``),
    its kind may be the examination (facts.possibly), it may be positive (pairing.positive) and its date relation is not
    established as another date (pairing.other_date) - what ``not_done_today`` asks of an established examination - and
    it is no established digital examination (``_manual``: E13 as ``session_possibly_done``'s filed arm reads it). An
    established examination of the session is one exactly when it is not established not done today. Every input only
    widens under a weakening, so a weakening adds such events and never removes one."""
    return (_claims_session(R, event, session) and facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION)
            and pairing.positive(R, event) and not pairing.other_date(R, event) and not _manual(R, event))


def _examinations_not_done_today(R: FactSet, session: Id) -> bool:
    """not_done_today's FIRST arm (DECISIONS D256 P2's reading; D285 ruling A.1: the one derivation that not_done_today
    and D269's count, ``_one_session``, both read): the session has an established examination (``_examinations``: kind
    supported examination, session supported, a digital examination excepted) and each of them is established as not
    done today - none possibly positive with its date relation not established as another (pairing.positive,
    pairing.other_date). It reads established examinations only, never another event's session claim."""
    exams = _examinations(R, session)
    return bool(exams) and not any(pairing.positive(R, event) and not pairing.other_date(R, event) for event in exams)


def not_done_today(R: FactSet, session: Id) -> bool:
    """DECISIONS D256 P2 and D269: the session's examination is established, and established not done on the date of
    service - its first arm (``_examinations_not_done_today``: an established examination, each established as not done
    today - its status established as not positive, planned or denied, or its date relation established as another
    date) - and nothing that may be its examination may be done today: no event whose session fact claims it
    (``_claims_session``: its claimed value, a contradiction's sides and an overfilled slot's written sessions it does
    not deny, AMENDMENT-2 4.3.3 c) and whose kind may be the examination is possibly positive with its date not
    established as another (``_open_examination``), and no kept unlisted act or doubt of kind examination or none is
    carded to it (DECISIONS D285 ruling A.3, Q-CARDEXAM option (b): the arm is an absence condition, so it reads the
    synthetic act as it reads that entry's filed doubted form, whose session fact claims the session - D216, D231's
    unlisted-versus-filed-doubted pair; an entry with no card stays unread here, as a silent session slot is, D256 P2's
    filed half). The second arm is the step's question Q-NDT option (a), kept by D285 ruling A.2 for D269's EXEMPTION
    (``session_possibly_done``, ``wholes`` and coverage's mirror read this function, and a settled session there holds
    less): an event the document places in the session that may be its examination done today keeps the session from
    being established not done (D256 P2's first reading, the established examinations alone, released a hold under a
    9.4 weakening - a session whose examination done today is weakened out of the established set became "established
    not done" beside its planned examination, and every act of it exempt). D269's COUNT reads the first arm alone
    (``_one_session``, D285 A.1), so this arm only ever adds holds. Every input of either arm only weakens toward not
    settled, so a weakening only ever undoes this (P-MONO). A session the FactSet does not hold reads its events the
    same way."""
    if not _examinations_not_done_today(R, session):
        return False
    if any(_open_examination(R, session, event) for event in R.events):
        return False
    return not any(_card(R, R.unlisted[index]) == session and Kind.EXAMINATION in _synthetic_kinds(R.unlisted[index])
                   for index in synthetic(R))  # D285 A.3 (Q-CARDEXAM)


def _synthetic_possibly_in(R: FactSet, entry: UnlistedStatement, session: Id) -> bool:
    """D231 row 2 ("an unlisted act with card S (or no card, S possible)") as DECISIONS D256 P2 reads it: a synthetic
    act carded to ``session`` makes it possibly done; one with no card (or a card the FactSet does not hold:
    ``synthetic_sessions``) makes it possibly done, when it names a kind, only where the session's family holds that
    kind (K2: ``_may_hold``) - a pH capsule placement or an office visit act of no session never makes a planned EUS
    today's (refute-r4d-r2 P2). A session established not done today is made possibly done by none of them (DECISIONS
    D269: ``session_possibly_done`` reads ``not_done_today`` first)."""
    if not synthetic_in(R, entry, session):
        return False
    if _card(R, entry) is not None:
        return True
    return entry.kind is None or _may_hold(R, session, entry.kind)


def session_possibly_done(R: FactSet, session: Id) -> bool:
    """A session may be done (D70's possible whole): an event that may be in it (possible_sessions: its session fact may
    name it, names none, or names an id the FactSet does not hold - D227 R2-2), possibly today's (4.4's frame), not an
    established digital examination (E13); or a synthetic act that may be in it (DECISIONS D231 row 2: an unlisted act
    or doubt with card S, or no card - S possible -, or a card the FactSet does not hold: ``synthetic_sessions``), a
    possibly performed act whose date and performer are unknown; an entry with no card that names a kind makes possibly
    done only a session whose family holds that kind (D256 P2's K2; ``_synthetic_possibly_in``). DECISIONS D269
    (Q-P2DATE option (c); 4.3 row 7: a session that has an examination is decided by it): a session whose examination is
    established, and established not done on the date of service (``not_done_today``: planned, or done on another
    date), is possibly done by NO act - filed or kept unlisted, placed, supported, carded or with no card, whatever its
    date or its session slot. This keeps D256 P2's readings (no entry with no card, no act whose session slot is silent
    and whose date is not established) and removes Q-P2DATE's release (an unplaced act dated today no longer makes a
    planned EUS possibly done, so weakening its date releases nothing). Step 4b's _part_of_session reads this function
    (D227's one derivation), so its signature stays."""
    if not_done_today(R, session):
        return False  # D269: no act makes a session established not done today possibly done
    if any(session in possible_sessions(R, event) and possibly_today(R, event) and not _manual(R, event)
           for event in R.events):
        return True
    return any(_synthetic_possibly_in(R, R.unlisted[index], session) for index in synthetic(R))


def wholes(R: FactSet, session: Id) -> tuple[Whole, ...]:
    """The sessions ``session`` is, or may be, the endoscopic portion of (module docstring: C3, C-4, D70), in the
    FactSet's session order, each once (an established whole before a possible one of the same session). DECISIONS
    D269: a session established not done on the date of service (``not_done_today``) is never a whole - not by C3's
    supported claim, not by D70's claim not established, and never by C-4 (``session_possibly_done`` is False for it) -
    so a planned EUS is never named as the whole of today's EGD (the integration's I4 residual). D70's claim not
    established names exactly its claimed value and its options - a contradiction's sides, a doubt's readings and an
    EMPTY slot's doubt included (DECISIONS D286, G3-14 option (a): an empty slot a doubt names is read by its readings,
    3.3 row 2, never as no claim), an overfilled slot's written sessions (AMENDMENT-2 4.3.3 a) - never a session nothing
    names; a pure empty slot names none. ``_named_wholes`` and coverage._part_of_session read this one set (D227)."""
    found: dict[Id, bool] = {}
    part = _fact(R, session, _A.PART_OF_SESSION)
    if part.result is Result.SUPPORTED and isinstance(part.value, Id) and part.value != session:
        if not not_done_today(R, part.value):  # D269
            found[part.value] = True  # C3
    elif part.result in facts_.OPEN:  # D286: an empty slot a doubt names is read by its readings
        for value in (part.value, *part.options):
            if isinstance(value, Id) and value != session and not not_done_today(R, value):  # D269
                found.setdefault(value, False)  # D70, by possibly
    kind = _fact(R, session, _A.KIND)
    if facts_.possibly(kind, WITHIN_FAMILY) and session_possibly_done(R, session):
        done = facts_.holds(kind, WITHIN_FAMILY) and session_done(R, session)
        for other in R.sessions:
            if other == session:
                continue
            other_kind, tract = _fact(R, other, _A.KIND), _fact(R, other, _A.TRACT)
            if not (facts_.possibly(other_kind, WHOLE_FAMILY)
                    and any(facts_.possibly(tract, value) for value in POSSIBLY_UPPER)
                    and session_possibly_done(R, other)):
                continue
            established = (done and facts_.holds(other_kind, WHOLE_FAMILY) and facts_.holds(tract, WHOLE_TRACT)
                           and session_done(R, other))
            found[other] = found.get(other, False) or established  # C-4; D70 when only possible
    order = {item: position for position, item in enumerate(R.sessions)}
    return tuple(Whole(item, established) for item, established in
                 sorted(found.items(), key=lambda pair: order.get(pair[0], len(order))))


def _named_wholes(R: FactSet, session: Id) -> frozenset[Id]:
    """The sessions ``session``'s own part_of_session claim names - C3's supported value, and D70's claimed value and
    options when the claim is not established, an empty slot's doubt included (DECISIONS D286: ``wholes``' first two
    arms, the one set coverage._part_of_session reads too) - never itself: the wholes the document STATES the session is
    part of, as opposed to C-4's structural inference."""
    part = _fact(R, session, _A.PART_OF_SESSION)
    if part.result is Result.SUPPORTED:
        return frozenset({part.value} - {session}) if isinstance(part.value, Id) else frozenset()
    if part.result in facts_.OPEN:  # D286: an empty slot a doubt names is read by its readings
        return frozenset(value for value in (part.value, *part.options) if isinstance(value, Id) and value != session)
    return frozenset()


def base_within(members: Sequence[Member], R: FactSet) -> tuple[BaseWithin, ...]:
    """engine.base_within over facts (module docstring): a base code whose session is (possibly) the endoscopic portion
    of another is held - beside the counted codes of that session that include its family's examination, or beside none
    when that session has no counted code, or, when its own part_of_session claim names that session, beside every
    counted code of it, whatever it includes (DECISIONS D244 R-N3: C3's established whole, and the same claim not
    established, D70's possible whole; D257: ``within`` names the stated whole's counted codes). An add-on code is no
    counted code here (D255: never named; a whole whose only counted codes are add-ons has none). No entry when the code
    is no base, its session is (possibly) part of no other, or every such session is C-4's alone and its counted codes
    include no such examination. In member order."""
    found: list[BaseWithin] = []
    for index, member in enumerate(members):
        session = member.session
        if session is None or not is_base(member.code):
            continue
        within: list[str] = []
        held: list[Id] = []
        established = False
        named = _named_wholes(R, session)
        for whole in wholes(R, session):
            including = [other.code for position, other in enumerate(members)
                         if position != index and other.session == whole.session and not is_addon(other.code)]
            if whole.session in named:
                codes = including  # D244 R-N3, D257: the stated whole's counted codes, whatever they include
            else:
                codes = [code for code in including if catalogue.includes_examination(code, member.family)]
                if including and not codes:
                    continue  # C-4's structural whole: its counted codes include no such examination
            within += codes
            held.append(whole.session)
            established = established or whole.established
        if held:
            found.append(BaseWithin(key=member.key, code=member.code, session=session, wholes=tuple(held),
                                    within=tuple(dict.fromkeys(within)), established=established))
    return tuple(found)


# --- the same-day E/M (C-3; D81, D94, D109, D111, D130, D133, D134) ---------------------------------------------------


def _procedural_family(R: FactSet, event: Id) -> bool:
    """The event may be in a session of a SAME_DAY_FAMILY (every session of the FactSet when its session fact names
    none)."""
    return any(_session_may_be(R, session, family) for session in possible_sessions(R, event)
               for family in SAME_DAY_FAMILIES)


def _established_family(R: FactSet, event: Id) -> SessionKind | None:
    """The event's session family when its session and that session's kind are both supported."""
    return facts_.session_family(R, event)


def _kind_established_not_em(R: FactSet, event: Id) -> bool:
    """DECISIONS D227 R2-1: the event's kind is established (supported) and is no E/M kind, so the event is a procedure
    and never the visit or its prolonged time. An event whose kind is not established - unresolved, contradicted (pass
    1's two sides), doubted (a doubt's readings beside the claimed value) or silent - may be the visit itself, whatever
    its session's family: it is a POSSIBLE procedure, never a DONE one. A weakening that gives an E/M event another
    possible kind therefore establishes no procedure day (the refutation build-v2/w34/refute-4d-r2, R2-1)."""
    kind = _fact(R, event, _A.KIND)
    return kind.result is Result.SUPPORTED and isinstance(kind.value, Kind) and kind.value not in EM_KINDS


def _established_kind(R: FactSet, event: Id) -> Kind | None:
    """The event's kind when it is established a SAME_DAY_KIND and, for an examination, established no digital
    examination (E13: its device supported other than manual, or manual negated); None otherwise. A digital examination
    left open (its device silent or not established) may be no procedure at all, so it is never a DONE procedure by its
    kind: weakening a device supported manual must never create a done procedure (the refutation's F1). A SAME_DAY_KIND
    is never an E/M kind (tests/v2/test_combination.py pins it), so this kind is established and no E/M kind too
    (_kind_established_not_em)."""
    kind = _fact(R, event, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, Kind) or kind.value not in SAME_DAY_KINDS:
        return None
    if kind.value is not Kind.EXAMINATION:
        return kind.value
    device = _fact(R, event, _A.TECHNIQUE_DEVICE)
    if device.result is Result.SUPPORTED and device.value != DIGITAL:
        return kind.value
    if device.result is Result.NEGATED and device.value == DIGITAL:
        return kind.value
    return None


def procedure_day(R: FactSet, codes: Sequence[ProceduralCode] = ()) -> ProcedureDay:
    """The procedure day by DATE OF SERVICE (C-3; module docstring), over the FactSet (the caller passes
    facts.effective's, so every date relation is re-judged against the effective date) and the counted codes."""
    done: list[SessionKind | None] = []
    possible: list[SessionKind | None] = []
    done_acts: list[Id] = []
    possible_acts: list[Id] = []
    undatable: list[Id] = []
    for event in R.events:
        kinds = facts_.possible_kinds(R, event, of_family=False)
        if kinds <= EM_KINDS:
            continue  # the visit, prolonged visit time: never a procedure of the day
        manual = _manual(R, event)
        by_family = _procedural_family(R, event)
        by_kind = bool(kinds & SAME_DAY_KINDS) and not manual
        by_class = Kind.OTHER in kinds and facts_.possibly(_fact(R, event, _A.OTHER_CLASS), OtherClass.PROCEDURE)
        if not (by_family or by_kind or by_class) or not pairing.positive(R, event):
            continue
        date = _fact(R, event, _A.DATE_RELATION)
        if pairing.other_date(R, event):
            continue  # C-3: another date
        if not facts_.holds(date, ON_DATE):
            undatable.append(event)  # UNRESOLVED(time): an E/M code's event_time, never READY
            continue
        family = _established_family(R, event)
        status = _fact(R, event, _A.STATUS)
        in_family = family is not None and family in SAME_DAY_FAMILIES
        # D227 R2-1: done by its family only when its kind is established and no E/M kind - an act that may be the
        # visit (its kind not established) is a possible procedure, never a done one, whatever its session's family
        family_done = in_family and _kind_established_not_em(R, event)
        kind_done = _established_kind(R, event) is not None
        label = family if in_family else OTHER_SERVICE if (by_kind or by_class) else None
        if (status.result is Result.SUPPORTED and isinstance(status.value, Status) and status.value in POSITIVE
                and (family_done or kind_done)):
            done.append(label)
            done_acts.append(event)
        else:
            possible.append(label)
            possible_acts.append(event)
    for code in codes:
        if not code.procedural:
            continue
        (done if code.supported else possible).append(code.family)
    named = tuple(dict.fromkeys(code.code for code in codes if code.procedural))
    # 3.2.6 rule 5 over the synthetic act (DECISIONS D231: the same-day rule's release is an absence condition, D216;
    # an unlisted doubt is a possibly performed act too): every kept unlisted act or doubt of no E/M kind is undatable
    unlisted = tuple(index for index in synthetic(R) if R.unlisted[index].kind not in EM_KINDS)
    families = tuple(dict.fromkeys(done))
    return ProcedureDay(done=families, possible=tuple(item for item in dict.fromkeys(possible) if item not in families),
                        done_acts=tuple(done_acts), possible_acts=tuple(possible_acts), undatable=tuple(undatable),
                        undatable_unlisted=unlisted, codes=named)


def _today_visit(R: FactSet, event: Id) -> bool:
    """A visit of this encounter (D113's "TODAY's visit"): kind supported em_visit, date relation supported on the date
    of service, its session's encounter supported this_encounter, its performer supported documenting_team. Every
    condition is established, so a weakening never adds a visit (v1's "no performer verified to another" did: the
    module docstring)."""
    if not facts_.holds(_fact(R, event, _A.KIND), Kind.EM_VISIT):
        return False
    if not (facts_.holds(_fact(R, event, _A.DATE_RELATION), ON_DATE)
            and facts_.holds(_fact(R, event, _A.PERFORMER), TEAM)):
        return False
    session = _fact(R, event, _A.SESSION)
    return (session.result is Result.SUPPORTED and isinstance(session.value, Id)
            and facts_.holds(_fact(R, session.value, _A.ENCOUNTER), EncounterRelation.THIS_ENCOUNTER))


def separate_statement(R: FactSet, visit_events: Sequence[Id]) -> SeparateStatement:
    """The documented statement of a significant, separately identifiable E/M (module docstring; D113), read from the
    code's own visit events ``visit_events``, then from every other visit of this encounter: the first supported
    statement; else the first denial; else none."""
    own = [event for event in dict.fromkeys(visit_events) if event in R.events]
    today = [event for event in R.events if event not in own and _today_visit(R, event)]
    visits = own + today
    for event in visits:
        found = _fact(R, event, _A.VISIT_SEPARATELY_IDENTIFIABLE)
        if facts_.holds(found, Separate.STATED):
            return SeparateStatement(stated=event, spans=found.spans)
    for event in visits:
        found = _fact(R, event, _A.VISIT_SEPARATELY_IDENTIFIABLE)
        if facts_.denied(found, Separate.STATED):
            return SeparateStatement(denied=event, spans=found.spans)
    return SeparateStatement()


def visit_basis(R: FactSet, visit_events: Sequence[Id]) -> VisitBasis | None:
    """v1's visit_basis over facts (FINAL-V2 5.5): the first of ``visit_events`` whose visit.basis is supported (v1's
    usable basis; EmBasis holds no not_stated, 1.4), with its value and spans; None when none is. Whether R6:em_basis is
    met is step 4a's row (4.3); this is the value the support display shows (v1's assess._inventory_fact 'em_basis')."""
    for event in dict.fromkeys(visit_events):
        found = _fact(R, event, _A.VISIT_BASIS)
        if found.result is Result.SUPPORTED and isinstance(found.value, EmBasis):
            return VisitBasis(event=event, basis=found.value, spans=found.spans)
    return None


def separate_em_hold(member: Member, R: FactSet, day: ProcedureDay, statement: SeparateStatement) -> HeldFact:
    """The separate_em hold of an E/M code on a procedure day with no separate statement (4.3 C3+SEP): an EXPLANATION
    quoting the denial when the visit's separately_identifiable is negated, a QUESTION otherwise; the spans are the
    denial's and the procedure acts'."""
    subject = statement.denied if statement.denied is not None else next(iter(member.supporting), None)
    found = _fact(R, subject, _A.VISIT_SEPARATELY_IDENTIFIABLE) if subject is not None else None
    denied = statement.denied is not None
    spans = tuple(sorted(set(statement.spans) | set(_anchor_spans(R, day.done_acts + day.possible_acts))))
    return HeldFact(fact=_key(SEPARATE_ITEM), attribute=_A.VISIT_SEPARATELY_IDENTIFIABLE, subject=subject,
                    result=found.result if found is not None else None,
                    kind=ItemKind.EXPLANATION if denied else ItemKind.QUESTION, cause=SAME_DAY_CAUSE,
                    reason=found.reasons[0] if found is not None and found.reasons and not denied else None,
                    spans=spans, rank=_rank(SEPARATE_ITEM))


def event_time_holds(R: FactSet, day: ProcedureDay) -> tuple[HeldFact, ...]:
    """An E/M code's event_time holds with no established procedure day (C-3: UNRESOLVED(time), never READY;
    same_day_holds): one per undatable procedure event, its cause the date relation's own, then one per unlisted act
    (cause unlisted)."""
    out: list[HeldFact] = []
    for event in day.undatable:
        found = _fact(R, event, _A.DATE_RELATION)
        out.append(HeldFact(fact=_key(TIME_ITEM), attribute=_A.DATE_RELATION, subject=event, result=found.result,
                            kind=ItemKind.QUESTION, cause=_cause(found),
                            reason=found.reasons[0] if found.reasons else None, spans=_anchor_spans(R, (event,)),
                            rank=_rank(TIME_ITEM)))
    for index in day.undatable_unlisted:
        out.append(HeldFact(fact=_key(TIME_ITEM), attribute=_A.DATE_RELATION, subject=None, result=None,
                            kind=ItemKind.QUESTION, cause=UNLISTED_CAUSE, reason=None,
                            spans=_unlisted_spans(R, (index,)), rank=_rank(TIME_ITEM)))
    return tuple(out)


def same_day_holds(member: Member, R: FactSet, day: ProcedureDay) -> tuple[HeldFact, ...]:
    """The same-day rule's holds of one counted code (module docstring): () for a code outside the E/M families; on a
    procedure day (done or possible) with no separate statement documented, separate_em; otherwise, with an undatable
    act and no ESTABLISHED procedure day, event_time for each undatable act (C-3: never READY); otherwise none. v1 asked
    event_time only with no procedure day, so a possible procedure day a weakening created released a code held for an
    undatable act (the refutation's F1); here only an established procedure day, which no weakening creates (D227 R2-1:
    its act's kind established and no E/M kind among its facts), moots the undatable act's date (D227 R2-3)."""
    if member.family not in EM_FAMILIES:
        return ()
    statement = separate_statement(R, member.supporting)
    if day.procedure_day and statement.stated is None:
        return (separate_em_hold(member, R, day, statement),)
    if day.undatable_any and not day.established:
        return event_time_holds(R, day)
    return ()


# --- the separate-lesion modifier review (FINAL 7.9; 4.7) -------------------------------------------------------------


def _distinct_lesion_act(R: FactSet, event: Id) -> Id | None:
    """The supported lesion of an act of a distinct-lesion kind (its kind supported, read as the catalogue kind with its
    supported purpose, in DISTINCT_LESION_KINDS); None otherwise."""
    kind = _fact(R, event, _A.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, Kind):
        return None
    purpose = _fact(R, event, _A.PURPOSE)
    named = catalogue.catalogue_kind(kind.value, purpose.value if purpose.result is Result.SUPPORTED
                                     and isinstance(purpose.value, Purpose) else None)
    if named is None or named not in DISTINCT_LESION_KINDS:
        return None
    lesion = _fact(R, event, _A.TARGET_LESION)
    return lesion.value if lesion.result is Result.SUPPORTED and isinstance(lesion.value, Id) else None


def lesions_distinct(R: FactSet, first: Id, second: Id) -> bool:
    """Two supported lesions established distinct: different ids, distinct_from supported in either lesion's list."""
    if first == second:
        return False
    return (any(facts_.holds(member, second) for member in facts_.members(R, first, _A.DISTINCT_FROM))
            or any(facts_.holds(member, first) for member in facts_.members(R, second, _A.DISTINCT_FROM)))


def _lesion_acts(R: FactSet, events: Sequence[Id]) -> tuple[tuple[Id, ...], tuple[Id, ...]]:
    lesions: list[Id] = []
    acts: list[Id] = []
    for event in events:
        lesion = _distinct_lesion_act(R, event)
        if lesion is None:
            continue
        acts.append(event)
        if lesion not in lesions:
            lesions.append(lesion)
    return tuple(lesions), tuple(acts)


def modifier_review(R: FactSet, member: Member, members: Sequence[Member]) -> ModifierReview | None:
    """The separate-lesion modifier review of ``member`` (module docstring): its own acts lie on supported lesions, and
    another counted code of its session, of another code, accounts for acts on lesions every one of which is
    established distinct from every one of its own. None otherwise."""
    session = member.session
    lesions, acts = _lesion_acts(R, member.supporting)
    if session is None or not lesions:
        return None
    partners: list[Partner] = []
    for other in members:
        if other.key == member.key or other.code == member.code or other.session != session:
            continue
        theirs, their_acts = _lesion_acts(R, other.supporting)
        if theirs and all(lesions_distinct(R, one, two) for one in lesions for two in theirs):
            partners.append(Partner(key=other.key, code=other.code, lesions=theirs, acts=their_acts))
    if not partners:
        return None
    return ModifierReview(key=member.key, code=member.code, session=session, lesions=lesions, acts=acts,
                          partners=tuple(partners))


# --- the endoscopic rows ----------------------------------------------------------------------------------------------


def endoscopic_rows(pairs: Iterable[tuple[str, Mapping[str, object] | None]]) -> dict[str, Mapping[str, object]]:
    """engine.endoscopic_rows (v1's, unchanged): code -> PFS row of every (code, PFS row or None) pair that has a
    row."""
    return {code: pfs for code, pfs in pairs if pfs}


# --- the holds --------------------------------------------------------------------------------------------------------


def base_hold(found: BaseIncluded, R: FactSet) -> HeldFact:
    """The base_included hold (rank 21, key-bound): an EXPLANATION when the examination is established included (rule
    (b), a reportable act of its session: BaseIncluded.established), a QUESTION when only rule (a) - counted codes
    beside it - or doubted or unlisted acts hold it; its subject the session; its spans the acts'."""
    spans = tuple(sorted(set(_anchor_spans(R, found.reportable + found.doubted))
                         | set(_unlisted_spans(R, found.unlisted))))
    return HeldFact(fact=_key(BASE_ITEM), attribute=None, subject=found.session, result=None,
                    kind=ItemKind.EXPLANATION if found.established else ItemKind.QUESTION, cause=BASE_CAUSE,
                    reason=None, spans=spans, rank=_rank(BASE_ITEM))


def _session_spans(R: FactSet, sessions: Iterable[Id]) -> tuple[Span, ...]:
    """The anchors of the examinations of ``sessions``: the events whose kind may be the examination and whose session
    fact names one of them."""
    wanted = frozenset(sessions)
    return _anchor_spans(R, (event for event in R.events
                             if facts_.possibly(_fact(R, event, _A.KIND), Kind.EXAMINATION)
                             and any(session in wanted for session in _named_sessions(R, event) or ())))


def base_within_hold(found: BaseWithin, R: FactSet) -> HeldFact:
    """The base_within hold (fact base_included, rank 21): an EXPLANATION when an established whole holds it, a QUESTION
    when only a possible one does; its subject the session; its spans the anchors of the examinations of the code's
    session and its wholes."""
    return HeldFact(fact=_key(BASE_ITEM), attribute=None, subject=found.session, result=None,
                    kind=ItemKind.EXPLANATION if found.established else ItemKind.QUESTION, cause=WITHIN_CAUSE,
                    reason=None, spans=_session_spans(R, (found.session, *found.wholes)), rank=_rank(BASE_ITEM))


def competing_hold(acts: Sequence[Id], R: FactSet, unlisted: Sequence[int] = ()) -> HeldFact:
    """The competing_codes hold (rank 22): a QUESTION naming no single fact; its subject the first act it shares with
    its rivals (None when it shares only synthetic acts); its spans those acts' anchors and the units of the synthetic
    acts it shares (``unlisted``, indices in FactSet.unlisted: DECISIONS D231 row 5)."""
    spans = tuple(sorted(set(_anchor_spans(R, acts)) | set(_unlisted_spans(R, unlisted))))
    return HeldFact(fact=_key(COMPETING_ITEM), attribute=None, subject=next(iter(acts), None), result=None,
                    kind=ItemKind.QUESTION, cause=COMPETING_CAUSE, reason=None, spans=spans,
                    rank=_rank(COMPETING_ITEM))


# --- the set level (4.1's combine) ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Combination:
    """What the combination rules give a counted set (4.1's combine): ``claims`` each member's claims; ``bases``,
    ``within`` and ``competes`` (the rival codes) and ``contested`` (the shared acts) for each member they hold;
    ``day`` the procedure day; ``statements`` each E/M member's separate statement; ``reviews`` each member's modifier
    review; ``held`` each member's combination holds - base_included (or base-within when base_included does not hold
    it, v1's order), competing_codes, then the same-day rule's. ``unlisted_claims`` each member's synthetic claims and
    ``unlisted_contested`` the synthetic acts a held member shares with its rivals (indices in FactSet.unlisted,
    DECISIONS D231 row 5; their rivals are in ``competes``). Every mapping is keyed by member key and frozen."""
    claims: Mapping[str, tuple[Id, ...]]
    bases: Mapping[str, BaseIncluded]
    within: Mapping[str, BaseWithin]
    competes: Mapping[str, tuple[str, ...]]
    contested: Mapping[str, tuple[Id, ...]]
    day: ProcedureDay
    statements: Mapping[str, SeparateStatement]
    reviews: Mapping[str, ModifierReview]
    held: Mapping[str, tuple[HeldFact, ...]]
    unlisted_claims: Mapping[str, tuple[int, ...]] = field(default_factory=dict)
    unlisted_contested: Mapping[str, tuple[int, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'claims', MappingProxyType(dict(self.claims)))
        object.__setattr__(self, 'bases', MappingProxyType(dict(self.bases)))
        object.__setattr__(self, 'within', MappingProxyType(dict(self.within)))
        object.__setattr__(self, 'competes', MappingProxyType(dict(self.competes)))
        object.__setattr__(self, 'contested', MappingProxyType(dict(self.contested)))
        object.__setattr__(self, 'statements', MappingProxyType(dict(self.statements)))
        object.__setattr__(self, 'reviews', MappingProxyType(dict(self.reviews)))
        object.__setattr__(self, 'held', MappingProxyType(dict(self.held)))
        object.__setattr__(self, 'unlisted_claims', MappingProxyType(dict(self.unlisted_claims)))
        object.__setattr__(self, 'unlisted_contested', MappingProxyType(dict(self.unlisted_contested)))


def combine(members: Sequence[Member], coding: Mapping[Id, SessionActs], R: FactSet) -> Combination:
    """Every combination rule over the counted ``members`` (4.1's combine; 4.4's "the combination holds (base,
    base-within, competing, separate_em, event_time)"): ``coding`` is step 4b's reportable and doubted acts per session,
    ``R`` the FactSet as assess reads it (facts.effective's). The competition is read over the documented acts' claims
    and, by the same rule, over the synthetic acts' (DECISIONS D231 row 5: two counted codes of different codes that
    may both account for one synthetic act compete, as for a filed act in doubt); a member's rivals are the union, in
    that order. Pure: identical inputs give identical outputs (P-DET)."""
    claimed = {member.key: claims(member.code, R, member.supporting) for member in members}
    entries = [(member.key, member.code, member.origin, claimed[member.key]) for member in members]
    synthetic_claimed = {member.key: synthetic_claims(member.code, R, member.supporting) for member in members}
    synthetic_entries = [(member.key, member.code, member.origin, synthetic_claimed[member.key])
                         for member in members]
    filed_rivals, synthetic_rivals = competition(entries), _rivals(synthetic_entries)
    competes = {member.key: tuple(dict.fromkeys(filed_rivals.get(member.key, ())
                                                + synthetic_rivals.get(member.key, ())))
                for member in members if member.key in filed_rivals or member.key in synthetic_rivals}
    shared = contested(entries)
    shared_unlisted = _shared(synthetic_entries)
    bases = {found.key: found for found in base_included(members, coding, R)}
    within = {found.key: found for found in base_within(members, R)}
    day = procedure_day(R, tuple(ProceduralCode(member.code, member.family, member.procedural, member.supported)
                                 for member in members))
    statements = {member.key: separate_statement(R, member.supporting) for member in members
                  if member.family in EM_FAMILIES}
    reviews = {member.key: review for member in members
               if (review := modifier_review(R, member, members)) is not None}
    held: dict[str, tuple[HeldFact, ...]] = {}
    for member in members:
        items: list[HeldFact] = []
        if member.key in bases:
            items.append(base_hold(bases[member.key], R))
        elif member.key in within:
            items.append(base_within_hold(within[member.key], R))
        if member.key in competes:
            items.append(competing_hold(shared.get(member.key, ()), R, shared_unlisted.get(member.key, ())))
        items += same_day_holds(member, R, day)
        held[member.key] = tuple(items)
    return Combination(claims=claimed, bases=bases, within=within, competes=competes, contested=shared, day=day,
                       statements=statements, reviews=reviews, held=held, unlisted_claims=synthetic_claimed,
                       unlisted_contested=shared_unlisted)
