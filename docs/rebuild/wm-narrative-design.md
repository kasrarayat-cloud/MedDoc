# Narrative notes on the qualified WM IOV form — design (2026-09-24)

Status: **candidate, behind `QUILLMD_WM_NARRATIVE` (off by default). Not enabled for doctors. Not live-verified.**
Offline qualification only (retained provider-shaped responses and the real Word engine in CI). Live provider
verification is a separate, costed campaign (the last section) that needs the owner's authorization.

## Goal

Ordinary narrative notes, and reviewed voice transcripts adopted into the same `Encounter.notes` field, fill the
existing qualified WM IOV template without `Question label: value` lines and without `Prewritten statement: …`
lines. The template, its mapping, its content controls and the document engine stay the same; the model never
writes the document; finalized exports are never re-rendered.

## Why the form refused narrative (traced 2026-09-24 at `dedac162`)

1. Generation: WM used the legacy quote contract. An unlabelled sentence could only be quoted as a whole line, and
   in a multi-line note one unlabelled line turned every answer into a conflict (`inherited_context`).
2. The provider never received the dropdown options, the measurement units or the statements' variants.
3. WM review (`wm_review._field_decision`) required every answer's evidence to be a labelled line whose value
   equals the answer (`exact_labelled_source_required`), and every statement a `Prewritten statement: <label>:
   <wording>` line (`complete_assertion_source_required`).
4. The document engine (`WmAdapter.cs`) re-checked the same labelled-line rule at fill (`LabelledSupport`).
5. Nothing proposed a statement.

## The contract (`wm-narrative-v1`)

**One reader:** `core/wm_narrative.py`, used by generation, the page, save and finalization.

- **Units.** The notes are split by the existing `generation.source_units` (complete sentences with exact
  code-point offsets; labelled lines are units too). ⚠️ That splitter reads `ms.` as a title abbreviation, so
  `…1500 ms. The left…` is one unit; the frozen benchmark's responses cite those ids, so the splitter is unchanged
  and within a unit `wm_narrative.sentences` reads the sentences for sides and corrections.
- **Provider request.** For every field: key, label, kind, options, unit; for every assertion statement its
  variants (wording, required and omitted answers); the units; the notes. Instructions: `wm_narrative.INSTRUCTIONS`.
- **Provider response** (`NarrativeSelections`, strict): every field exactly once with `value`, `unit_ids`,
  `conflict`, `subject` (patient/family/other/unclear), `certainty` (definite/uncertain), `timing`
  (current/prior/planned/unclear); optional statement proposals `{key, variant, unit_ids}`.
- **The job.** `configuration()` stamps `narrative_contract` into the write-once job config only when the flag is
  on, so the job names the instructions it was sent. A job quoted with the contract and run after the flag went
  off is refused before any request (`NoProviderRequest`: nothing sent, charged or held). Narrative runs only on the
  Anthropic provider (12,000 output tokens, 240 s timeout, under the 5-minute stale-job threshold). The reservation
  is priced from the narrative payload itself.
- **Fixture mode** (never live): a retained response for exactly these notes is read from
  `QUILLMD_AI_REPLAY_DIR/<sha256 of the notes>.json`, else the labelled lines are read as the labelled fixture
  reads them. Either way the one validator judges it. The receipt names it (`synthetic-narrative-replay` /
  `synthetic-narrative-fixture`).

### What the parent decides, deterministically, per answer

Two kinds of rule, and the difference is who can overrule them:

- **Support** (`wm_narrative.support`): whether the cited text CARRIES the value — written there, not struck by its own
  correction, on the question's side. No decision changes that, so review refuses it too and the engine re-checks the
  coarse part of it at fill; the clinician's way through is a sentence (or a labelled line) that carries the answer.
- **Governing** (`wm_narrative.governing`): whether something around the text makes the value uncertain — a heading, a
  label, a correction elsewhere, a relative nearby. It holds the PRE-FILL (the candidate is shown beside what holds it);
  the clinician who reads it may still choose the answer, and finalization re-checks every pre-filled answer.

| condition | outcome |
|---|---|
| empty value | missing |
| a cited unit is not a unit of the notes, a choice is not an original option, a value has no unit, a key is missing/duplicated/unknown | the response is refused |
| instruction-like text in the notes or a label | every answer held |
| **governing:** an invisible character inside a word of the notes (see *Sides*) | every pre-fill held (`hidden`) |
| `subject` family or other | missing (the candidate is shown as someone else's finding) |
| **support:** nothing it cites can carry it (only another question's labelled line, only a structural heading) | held |
| **support:** the value is not written in a cited unit: a measurement's number (at most 12 characters, as the engine reads one: `1800.00000000 ms` is none) with a unit word of its column (a reflux time may be in seconds), not approximate, bounded, ranged or an alternative (`7.4 mm+`, not `7.4 mm + reflux`); text copied (ASCII case folded, every other character exact, as the engine compares it); a choice is an option | held |
| **support:** the value's own sentence strikes it in place: a correction inside a sentence strikes only what it stands right after — correcting to a number, the number just before it (with at most a few words after it) when of that unit or bare (`6.1 mm, correction, 7.6 mm`, `6.9 correction 6.6 millimeters`, spoken numbers too); correcting to a number, only that number's quantity (`7.4 mm right, correction, 7.6 mm` keeps the right); correcting to words, the few words just before it, never the side said with them unless it corrects to a side (`Left leg, I mean, the great saphenous vein …` keeps the left; `The right sorry left …` strikes the right); a SPOKEN correction opening its sentence still strikes what it stands right after; a bare number only when written as the correction's number is (`6.9 correction 6.6 millimeters`; not `grade 2 reflux, correction, 6.9 mm`); a correction that first repeats the old number strikes the repeat too only when it says right after it that it is wrong (`6.1 mm, correction, 6.1 mm is wrong, 7.6 mm`) — any other repeat is held for the pre-fill (`7.4 mm, I mean 7.4 mm, at the SFJ with reflux of 1.8 seconds`, `6.1 mm, correction, 6.1 mm was misdictated`; review accepts it) and is no rival of the value it corrects to (`6.1 mm, correction, 6.1 mm should read 7.6 mm` corrects to 7.6); a spoken `no` between two numbers corrects the first (`6.1 no 7.6 millimeters`); `sorry, make that` is one correction. A measurement is denied WHEREVER it is written by a denial in its own clause that reaches it through intensifiers only (`not 6.1 mm`, `no longer 6.1 mm`, `is not really 6.1 mm`, `rather than 6.1 mm`, `instead of 6.1 mm`; `… 7.6 mm at the saphenofemoral junction, not 6.1 mm as previously reported`; not `without reflux, 5.3 mm`, `without reflux measures 4.4 mm`, `6.1 no I mean 7.6`, `6.1 no 7.6 millimeters`), and never from the sentence before (`…, reflux is absent.` / `7.6 mm is the diameter …` denies nothing); a value its own sentence says is wrong right after it is not live either (`6.1 mm is incorrect`, `… 6.1 mm was a dictation error`) | held |
| **support:** a line labelled with this question disagrees, at a line start or after a bullet (prose under a choice's label is interpretation) — its value read to the next label on the line, after a run of spaces, a tab, a separator (`,` `|` `;` `/`), a spaced dash or a space (`Patient name: SYNTHETIC PATIENT B    DOB: …    Allergies: none`, `Patient name: SYNTHETIC PATIENT B, DOB: 06/30/1959, Allergies: none`, `Date of service: 09/22/2026 | Indication: …`), and for demographics to a bracket, a spaced dash or a run of spaces or a tab too (`06/30/1959 (not verified by patient)`, `09/22/2026 - no prior study for comparison`, `06/30/1959    not verified`); for any other question only to a label of this form's (round 14: `Swelling, today: denies`, `Leg pain, Note: patient denies leg pain` lost their own denial to a label nobody listed), never short of the value's own words (`Leg pain (-)`, `Swelling    denies`, `7.4 mm (not measured today, prior study)` disagree); a unit labelled for another question supports nothing | held |
| **support:** a Right/Left question whose value NO reading of the text places on that side (or both) — see *Sides* below; ruling #127: the model never asserts laterality | held |
| **governing:** a Right/Left question whose PRIMARY reading is not that side — the readings compete, or the side comes only from another cited unit | held (the clinician may choose any side a reading gives) |
| `subject` unclear, a relative before it in its sentence (in a transcript's run-on sentence, the 25 words before it) or after it within its sentence and 12 words (`Leg ulcer, per mother, not the patient.`; not one with a finding of its own there, `… because her mother has varicose veins` — its own verb that is not a copula, nothing tying it back to the value: `a leg ulcer that her mother has had`, `her mother has it`/`this`/`these`, `her mother is actually the affected person` and the value's words again all hold; `family physician` is not one; a relative in the NEXT sentence is the model's `subject` to read), `certainty` uncertain, `conflict`, a timing that does not fit the question (previous treatment: prior, its outcome also current; a clinical indication: current or prior; demographics: any; everything else: this examination), or a previous treatment written as planned (`scheduled for ablation`, `recs: EVLA`) | held |
| **governing:** a heading or pointer the installed vocabulary says changes meaning (a denial, a family history, a hypothetical) holds its block, sub-headings and a spaced list included, to a new prose paragraph; any heading with a word nobody listed fails closed the same way | held with the governing lines |
| **governing:** a SECTION heading or label (`section_holds`) holds only what its content cannot answer: a plan holds everything (a plan joined to the assessment, `Assessment and plan:`, is the assessment's); a history or prior study holds all but a previous treatment and a clinical indication; a treatment/procedure section that does not say it was before holds a previous treatment; a complaint section (`HPI:`, `CC:`, `REASON FOR EXAM:`, `S:`) holds this examination's findings; demographics are never held by a section; a structural heading (sides, limbs, this form's veins and rows, report sections) holds nothing, and one naming the question's own section does not hold that question | held with the governing lines |
| **governing:** a cited sentence's own short label (up to four words) that is unknown, a section word before a comma in it (`Prior study 2019, right GSV:`) or anywhere in a longer label (`Prior study 2019 right GSV SFJ:`, `Previous right GSV SFJ diameter:`), the question's own label with a denying value unless the answer is written there with no denial right before it (`Swelling: none.`, `Leg pain: denies leg pain.`; not `Right GSV SFJ: 7.4 mm, no reflux`), longer text before a colon with the denial vocabulary or a rule-out, or a fragment under a denying label (`Denies: leg pain. Swelling.`) | held |
| **governing:** a correction that may have replaced the value without striking it: one inside its sentence, after the value, that `concerns` it (unless it is PLACED: a number corrected to a number that opens what it corrects to, with no location of its own in its few words, or a location bound to it that is the same site as the number it stands after — `6.9 correction 6.6 millimeters`, `7.9mm, correction, 8.3mm at the SFJ`; not `…correction, SFJ 7.1 mm`, not `… proximal thigh 6.3 millimeters correction 7.4 millimeters at the junction …`, nor — where the number it stands after names no site — a location at the site of the number before that one: `… SFJ 7.1 millimeters small saphenous vein 6.3 millimeters correction 7.4 millimeters at the SFJ …`); one opening its sentence in the answer's own unit or paragraph that concerns it, unless the answer is what it corrects TO — for a measurement, its FIRST quantity after it, with no later quantity of its unit in the unit but a denied one, and every other word of its sentence saying only where and what the value is — an inclusion list, so an unlisted word holds (`Correction: the right SFJ diameter is 7.6 mm.`, `Correction: right GSV SFJ 7.6 mm, not 6.1 mm.` correct to 7.6, never to 6.1; not `Correction: 6.1 mm at the SFJ is wrong.`, `disregard 6.1 mm`, `6.1 mm was misdictated`, `6.1 mm should read 7.6`); a correction whose reach writes more than one quantity of the answer's unit, the answer's value among them (`6.1 mm should read 7.6 mm`, `Correction: 6.1 mm at the saphenofemoral junction should be 7.6 mm`; a placed correction's reach ends at the next location after its first number) — for the pre-fill only, the clinician who reads it may choose either; a later one whose corrected text mentions the value — and one opening its sentence BEFORE the answer (on a line above the answer's, anywhere in its sentence unless placed: `Addendum: Right GSV SFJ diameter corrected to 7.6 mm.` above the report), read the same way, unless its reach holds the answer's own sentence, writes its value, and writes no other quantity of its unit nor a denied one (`Correction: the right GSV at the SFJ measures 6.9 mm, not 7.4 mm.` above the report holds 7.4; `CORRECTION:` over the value it corrects to does not; `CORRECTION:` / `… 7.6 mm, not 6.1 mm.` / `… 6.1 mm …` holds 6.1); a cited correction unit that does not write the value, a correction restating the value (`6.1 mm belongs to the left leg`); a later one that replaced this very value where it stands (`Right GSV SFJ 7.4, correction, 7.9 mm.` below `… 7.4 mm at the SFJ.`); a later one stating a quantity of the answer's unit, unless it is placed in its sentence (resolved where it stands), this answer cites it, or it says which values it replaces — as many of the quantities it writes denied as not (`… measures 6.7 mm, not 6.1 mm`: then only the values it writes; not `… is 4.4 mm, not 4.0 mm, and the GSV at the SFJ is 6.9 mm`) — never because another answer cites it (the model's choice of what to cite decides nothing); for a one-sided question, a sentence saying the legs were swapped, before or after the answer, cited or not (`transposed`, `mislabeled`, `reversed` — `The sides in the dictation above are reversed.`; with or without a side word; not `reversed flow`; flow or its direction reversed is reflux only when its sentence names at most one leg and speaks only of flow, veins, the patient's position and the manoeuvre — `flow … is reversed for 1.8 seconds`, `Flow is reversed in both great saphenous veins`, `Flow is reversed in the great saphenous veins of both legs with Valsalva.`, `… with the Valsalva maneuver`, `With the patient standing, …`, `…, consistent with reflux.`; not `The flow values above are reversed.`, `The flow measurements of both legs were reversed.`, `… between the two legs`, `The flow above is reversed.`, `The diameters and flow of both legs were reversed.`, `Flow and reflux in both legs were reversed.`: an inclusion list, so an unlisted word holds; `reflux` reversed is data swapped, for one leg or both: `The reflux times for the right and left legs were reversed.`, `The reflux values for the left leg were reversed.`, `The reflux values above are reversed.`; read within its line, joined across a hard wrap) or a correction in another paragraph naming a side, a quantity with it or not, unless it says which values it replaces and every side it names is written before a value in its clause (`Correction: the right GSV at the SFJ measures 7.6 mm, not 6.1 mm.`: then only those; not `Correction: the SFJ diameter is 7.6 mm, not 6.1 mm, and all of the above findings are in the left leg.`, `…, and the above findings with reflux of 1.8 seconds are all in the left leg.`); and a sentence anywhere — a cited one too — that denies the value where it writes it, says it is wrong right after it, or calls it the old one in its clause on its line — within six words before it (`previously`, `prior`, `originally` …), or after it in its sentence before its next value, a joined clause (`and`, `but`, `while`, `whereas`, `;`) or a bracket holding the next value, commas included, and through a list of values it heads (`the 6.1 mm and 5.0 mm values above are incorrect`, `6.1 mm (SFJ) and 5.0 mm (knee) … in error`, `6.1 mm, 5.0 mm above are wrong` — round 14) (`disregard`, `superseded`, `erroneously`, `incorrect`, `wrong`, `error`, `misdictated` …; not `prior` or `previously` after it, `… 6.1 mm, unchanged from the prior exam`: inclusion lists that only ever hold) — with or without a correction word (`…, not 6.1 mm as originally dictated`, `… 6.1 mm is incorrect; …`, `… 6.1 mm was reported in error`, `Please disregard the prior right SFJ diameter of 6.1 mm; …`, `… corrected to 7.6 mm (previously 6.1 mm)`, `the 6.1 mm right SFJ diameter above should be disregarded`, `… 6.1 mm dictated previously is superseded`, `… of 6.1 mm, as previously reported, is incorrect; …`). `concerns`: its value or words, a side for a one-sided question, a quantity of its unit (or a bare number, or none) for a measurement, and for anything else everything except a correction stating only a measurement (`Correction: it measures 7.6 mm there.`) of a symptom or history — never of this examination's findings (`… without evidence of … insufficiency. Correction: reflux of 1.5 seconds in the common femoral vein.`) — and a side it names never releases it. What a written correction corrects TO ends at the first clause break after its first number, or its sentence's end, and in a run-on sentence after 40 words. At most eight governing lines are kept | held |
| otherwise | supported (pre-filled; the clinician still reviews every answer) |

**Sides.** Read from the text over a whole-text index (a search cut inside a word would read `both` in `bothersome`);
lines and paragraphs split at every break `str.splitlines` reads, as units do (U+2028, VT, FF, NEL, U+2029, FS, CR;
`\r\n` is one break, so a browser's line is no blank line), and a line of characters that show nothing (a no-break or
zero-width space, U+3000: generation's `blanks()`) is blank; a note with an invisible character in the text of a line
that shows anything — any of Unicode's default-ignorable code points (a soft hyphen, zero-width spaces and joiners,
bidirectional marks, embeddings and isolates, variation selectors, the combining grapheme joiner, fillers, tags), inside
a word or beside one (U+00AD inside `sorry`, `left`, `mother`; U+202A inside `left`; U+200B after `… asymptomatic.`) —
holds every pre-fill, since it can hide a correction, a side or a relative from the reader's words and the engine's
alike, or leave a sentence reading as an unstopped heading (round 14: the round-13 list missed most of them). A break
inside a sentence — this line ending in a word no sentence ends in (`was`, `than`, `the` …), or the next opening with a
small letter or a value (`… measures` / `7.6 millimeters …`; not a list's number, `2. Left …`) after a line that may not
be a heading (not capitals, markup, a closing dash, a section's words, a limb's label with no colon, `Right leg` —
unless the next line denies its examination, `Right leg` / `not examined.`; a line opening with a preposition is no
limb's label, `in the left leg.` — nor a short unstopped line that may head a section, `Other`, `Also noted`, `Update
09/25/2026`), never after a stop, a colon or a blank line, and never into a line that may be a heading (`Reflux: no` /
`IMPRESSION`) unless it opens with a small letter and ends its sentence (`… without reflux` / `left leg.` — round 14:
the sentence's own side phrase was read as the next heading, and the value took the side before) — is a hard wrap: the
lines it joins are read as one sentence (`the left leg was` / `not imaged.`, `larger than` / `the left.`, `Flow … is` /
`reversed for 1.8 seconds.`; not `IMPRESSION` / `great saphenous vein reflux positive.`), and a line wrapped into the
next is never a heading. A sentence begins where its wrapped lines do, read at most 1,200 characters back from its unit
(a wrapped transcript's `right leg …` three lines up reads its value; round 14's cost lens: read from the start of a
long run for every unit, 92 s), its context read from that beginning, and ends with the cited unit, as the engine reads
it. A sentence's denial is read over the sentence joined across its wrap, over the side's own clause in it, and — where
a sentence joined from the line above ends on the side's line — over that line's part of it (`GSV at the SFJ 7.4 mm,
reflux 1.8 s` / `left leg not imaged today.` — round 14: joined, it wrote a quantity and lent the left to the next
line); any strikes its side (`The left leg was not examined and` / `the great saphenous vein measures 7.4 mm …`); never
over a physical line a sentence runs on past, which cuts a wrapped transcript anywhere. Each place a value is written
has a PRIMARY reading and a set of CANDIDATE readings. The pre-fill needs the primary reading to be the question's side
(or both); review accepts the clinician's answer when any candidate is (every candidate is a side word the engine also
finds). The primary reading: a side word inside the value as written; else one bound just after it by a preposition,
bracket or dash (`5.0 mm on the left`, `(left)`, `- left`, `bilaterally`) whose phrase closes there and that nothing
before it in its sentence contradicts; else the nearest side before it in its clause, then its sentence, unless a side
just after it in its clause is its own phrase's and says otherwise; else such a side after it; else the paragraph's
nearest phrase (a side a comparison introduces is none, nor a `both` in a sentence that denies, `No DVT bilaterally`,
nor any side in a sentence of its line that denies and writes no quantity: a denied `both` or `right or left` lends
nothing, and any other leg such a sentence names (`No DVT in the left leg.`, `The left lower extremity demonstrates no
evidence of DVT.`, `The left leg shows no DVT on imaging.`, `The deep veins of the left leg were not evaluated.`) is a
candidate beside what the rest of the reading gives — the pre-fill's only where the rest reads that leg too (`RIGHT
LOWER EXTREMITY:` / `The right … veins are fully compressible with no evidence of thrombus.`), and nothing older reaches
past it alone, whatever it denies — a finding, `In the left leg, reflux was not seen on imaging.`, or the leg's
examination inside another leg's block, `RIGHT LOWER EXTREMITY:` / `Left leg not examined` / … (round 12 read an
examination's denial past to the block's heading; the denial pattern matched finding denials too, and the leg was
dropped), except a sentence saying only that one whole leg was not examined — its examination denied (`not examined`,
`no … imaging`; not `No, the left leg was examined.` — round 14), its words besides the side an inclusion list that
names why at most (`per physician order`, `(unilateral study)`), one leg named (`Left leg not imaged today.`, `The left
leg was not examined.`, `LEFT LEG - NOT EXAMINED`, `No left leg imaging.`, `LLE not examined.`) — which lends no value
that leg, the rest of the reading standing (`RIGHT LEG:` / `Left leg not imaged today.` / `GSV SFJ 7.2 mm …` is the
right's; not `Left leg not examined for reflux.`, `The deep veins of the left leg were not evaluated.`, `… not imaged
today because of a cast`) — unless it is the limb label opening its line over findings, which keeps its leg (`Right
lower extremity: No evidence of DVT.`, `Right: No DVT.`, `Right: reflux absent.`, `RIGHT LOWER EXTREMITY: The deep veins
are patent and compressible with no evidence of DVT.`: every clause or sentence after it to the end of its line that
denies anything denies a finding — `no`, `without` or `negative for` within a few words of the findings' own vocabulary,
or a finding word said absent, its qualifiers joined by `or` too, `No acute or chronic DVT.` — and none names an
examination except as where a finding was seen, after a preposition and at most two words none of which negates, `Right:
No DVT on duplex imaging.`, `No DVT on this study.`, `… in the visualized veins`, `… on compression imaging` (not `No
DVT in segments not imaged.`): not `Left leg: not examined for reflux.`, `Left: not imaged, no DVT symptoms.`, `Left
leg: no evaluation for DVT or reflux.`, `Left: No DVT. Not imaged for reflux.`, `Left: No DVT, reflux study deferred.`);
a side's label INSIDE its paragraph — not opening its first line, with something after it on its line — heads its own
item: to the end of its line and the lines it wraps into when it opens its line (`L: GSV SFJ 5.6 nl, prox thigh 4.7 nl.
SSV SPJ 5.9/2.3s, …`), else, in mid-line or in a system's list, to its first full stop (round 14: `… Left: No DVT in the
common femoral vein. The great saphenous vein measures …` on one line was the left's); a LIMB's label opening its line
(a leg, limb or extremity named, `RIGHT LOWER EXTREMITY:`, `Right leg:`) heads its leg's block, the system's and veins'
sub-headings under it with it (`FINDINGS:` / `RIGHT LOWER EXTREMITY: Deep veins patent and compressible.` / `Superficial
venous system:` / …, `Right leg: No DVT.` / `Great saphenous vein:` / … / `Left leg: No DVT.` / … — round 14: round 13
held these), unless the line above is the other leg's label, a list of both legs' labels (`Right leg: No DVT.` / `Left
leg: No DVT.` / …, round 12: a candidate); a bare side's label or a vein's (`Left: No DVT in the common femoral vein.`,
`Left CFV: …`) heads nothing after its item where the paragraph named a leg before it (not one only said to be
unexamined, `The right leg was not examined.` / `Left leg: …`), where the paragraph opens with a system's or a vein's
heading or label naming no side (a list of that system's items, with or without a finding after its colon: `DEEP VENOUS
SYSTEM:`, `DEEP VENOUS SYSTEM: No DVT.`, `Deep veins: compressible …` / `Left: No DVT in the common femoral vein.`, the
other leg's common femoral vein checked in a one-leg study; a limb's heading, `RIGHT LOWER EXTREMITY:`, is none), or
past a heading line or a line opening with an anatomical label naming no side, the value's own line included
(`FINDINGS:` / `Left: No DVT …` / `SUPERFICIAL VENOUS SYSTEM:` / …, `Superficial venous system: The great saphenous vein
measures …`): its leg is then a candidate beside any the paragraph named before it and the side heading above the
paragraph (`DEEP VENOUS SYSTEM:` / `Right: No DVT.` / `Left: No DVT in the common femoral vein.`, `RIGHT LOWER
EXTREMITY:` / … / `Left: No DVT in the common femoral vein.`, a sentence or a line between, one leg twice); otherwise it
heads its block (`FINDINGS:` / `RIGHT LOWER EXTREMITY: No DVT.` / `The great saphenous vein measures …`, as a label
opening its paragraph does); a label with nothing after it heads its block (`RIGHT GSV:`); a leg a sentence of its own
only mentions — writing no value of it, no limb label or heading of its block — inside another leg's block lends a later
sentence only a reading beside that leg (`RIGHT LEG:` / … / `Left leg to be scanned next week.`, `She had left GSV
ablation in 2019.`, `Left leg exam deferred.`, `The contralateral left common femoral vein is patent …` / `GSV at the
knee 5.1 mm.` — round 14; not `Left leg.`, a spoken heading, nor a leg in the value's own sentence before a `;`); a weak
form there is no pre-fill, the heading's side staying a candidate; an impression's heading or label between them or
opening the sentence (`IMPRESSION:`, `Assessment:`, `Results:`, `Dx:`, `Comments:`, `Note:`, `In summary, …` — a
sentence naming one, `Final images were reviewed on the workstation.`, is none, and a line between them labelled over
what it says is one only under an impression's own label, `IMPRESSION: …`, `Conclusion: …`, not `Comment: good
visualization.`, `Note: patient standing.`), or a side-less line denying the examination that is no finding line (`LEFT
LEG:` / `Not examined.`; not `Negative for DVT.`, `No sonographic evidence of DVT.`, `No DVT or SVT.`, nor a sentence,
`Treated GSV not visualized from the SFJ to the knee, …`), leaves that side a candidate only), else — unless the
sentence opens with its own report, section or timing label naming no side, closed by a colon, a dash or markup
(`IMPRESSION: Great saphenous vein …`, `IMPRESSION - …`, `**IMPRESSION** …`, a date or a number in it saying nothing),
or such a heading stands before it on its line (`Impression. Great saphenous vein reflux positive.`; read only when
short) — the nearest side heading (a label with a report word among at most three words, `Overall impression -`, `Other
findings:`, or of words no list has, `Also noted -`, `Comments:`, leaves that side a candidate only), walking past
anatomical sub-headings and lines whose only side is a weak form (`s/p GSV ablation with ClosureFast (R)`): a line
opening the paragraph that is written as a heading (a colon or dash closing it, markup, capitals, or a report or section
word) and names no side ends the search (`IMPRESSION`, `**IMPRESSION**`, `IMPRESSION -`, `FINAL IMPRESSION`, `ADDITIONAL
FINDINGS`, `3. IMPRESSION`, `IMPRESSION 09/24/2026`, `COMMENTS:`, a longer line all in capitals — `SUMMARY OF THE
FINDINGS OF THIS STUDY`: a side-less impression is no leg), while a finding line (`No DVT`, `CFV patent`, `Deep venous
system: normal`: a short line only of finding words, anatomy and the few words written between them, or an anatomical
label over what it found, `Deep veins: unremarkable.`), a sentence or a vein's sub-heading (`Great saphenous vein`) does
not, and the side is read from above the paragraph; any other short line opening it (`Additional findings`, `Comments`,
`Other`, `3. Other`, `Update 09/25/2026`, `Also noted.`, `DVT evaluation`, `Not examined.`: digits, a stop, a finding
word or a denial make no finding line), a longer one naming a report's part with no stop and no finite verb, or a line
of any length naming an impression's word with no finite verb, stopped or not (`Summary of the findings of this study.`,
`Final impression based on today's duplex findings.`, `Conclusion of this venous duplex study.`), leaves that side a
candidate only. A line writing a value is never a section's label (`GSV SFJ 7.1 mm 2.4 s`: `s` is no SOAP `S:`). The
walk up from a paragraph reads each line the same way: a line denying its leg (`Left leg not examined`, `No DVT in the
left leg`, `LEFT LEG - NOT EXAMINED`), a section's or an unsure line, and a heading whose only side is a weak form
(`FOLLOW-UP ABLATION (L)`) end it; a finding line, a vein's heading (anatomy only: words a report heading shares with
anatomy that name no part of a leg, `Standing views`, `Correction`, `Comments`, make none) and a line that shows nothing
are walked past; a line wrapped with another is a piece of a sentence — one naming a side ends the walk (`The left leg`
/ `is normal.`). A sentence label in a leg's own paragraph (`RIGHT LEG:` then `Findings: GSV …`) keeps that leg.
Statements read the side around a sentence the same way. It is `ambiguous` — no pre-fill — when a phrase names both legs
(`the right and left veins measure 7.4 and 5.0 mm`, `right greater than left`, `in the right or left lower extremity`),
when a bound side runs on into the next finding (`1.8 seconds on the left the great saphenous vein measures 5.0`, `… on
the left great saphenous vein measures 5.0 millimeters`), when a bare side word is all there is (`1.2 seconds right and
…`), when `right` stands as an adverb (`right below the knee`, `right in the groin`, `right from the junction`, `…,
right?`), when the sentence's side differs from the side heading above it (`RIGHT LEG:` over `…; the left GSV …`), when
the sentence speaks of the other leg without naming it — `the other`, `opposite` or `contralateral` with a limb, a vein,
a site or `one` (`the other knee`, `The opposite SFJ`, `the opposite one`; not `the other veins`), in the value's own
clause when its sentence names a side (`The right GSV measures 7.4 mm …, and the opposite GSV measures 5.0 mm …`), in
its sentence when the side would come from around it (`RIGHT LOWER EXTREMITY:` / `The opposite great saphenous vein
measures 5.0 mm …`) — with no candidate, since no leg is written (round 14: the side around it was offered at review,
and it is the wrong one), when a weak side form is in its clause, when a side a comparison introduces in another clause
gives another reading than the value's without it (`…, compared with the left, which measures 5.0 mm`, `The right great
saphenous vein is dilated compared with the left, measuring 7.4 mm …`, `RIGHT LEG:` over `Compared with the left, the
GSV measures 7.4 mm`: either leg is the clinician's), when a side written only after the value, not bound to it, differs
from the side around its sentence (`The right leg was examined first. … mirroring the findings in the left leg.`; the
side around it is then no reading to offer at review, `RIGHT LEG:` a paragraph above `… 4.1 mm over the lower half of
the left calf`), when the sentence named a side its own correction struck and gives the value none (the paragraph's side
is then no pre-fill), and for a measurement read as `both` from the context, unless both legs are what measures it —
only anatomy and a measuring verb between `both` and the one value in one clause (`Both great saphenous veins measure
7.4 mm`; not `Both legs were scanned with the GSV measuring 7.4 mm`, `Both GSVs are dilated with the larger measuring
7.4 mm`, `heaviness in both legs, and the GSV measures 7.4 mm`, `Bilateral study with …`) or from a sentence writing two
quantities of its unit (`Both GSVs measure 7.4 mm and 5.0 mm`). A WEAK form is a candidate the clinician may choose,
never a primary reading: a bracketed letter after a word that is neither anatomy nor a unit and before nothing that
places it — a colon, a measurement or anatomy (`ClosureFast (R) in 2019`, `ClosureFast (R) 2 years ago`; `(R) GSV`, `SSV
(R):`, `7.4 mm (R)`, `reflux (R) 1.8 s` are the side), `right` before a position with no article (`right below knee`),
unless a capital `Right` begins the row's own name or label (`Right below knee GSV`, `Right below knee segment:`), and
`left` after an auxiliary (`was left untreated`, `was left below the knee`) unless a vein or limb, a colon or a
measurement follows (`There is left great saphenous vein reflux` is the side). `the right` (the word `the`: not `breathe
right when`) always names the side. A side a comparison introduces within six words in its clause (`compared with 5.0 mm
on the left`, `larger than the one in the left leg`, `Unlike the left leg,`) is the side of the value the comparison
introduces with no side between them (5.0 is the left's; not `Compared with the left the GSV measures 7.4 mm`), with a
side written after it its own (`Right GSV SFJ 7.4 mm vs 5.0 mm left.` reads 5.0 both ways), and of no other value, in
its sentence or the next (`The GSV is larger than the left. It measures 7.4 mm.`): a side before that value is never the
compared value's when this value has its own (`The right GSV measures 7.4 mm …, compared with 5.0 mm on the left`), and
a value whose sentence names sides only as compared ones has no pre-fill (`Compared to prior the right GSV measures 7.4
mm`, `Compared with the left, the GSV measures 7.4 mm`: the side and the paragraph's are the clinician's), unless it is
one phrase with the side before it (`right greater than left`). A sentence naming a side where its reading of the value
is not written never takes the context's side, for the pre-fill or at review (the clinician who cites the side heading
reads it from there); a side in a denying clause may be the leg denied or the value's own, so it is a candidate, and the
pre-fill's only where the context reads the same leg (`…, and the left leg was not examined today` under `RIGHT LEG:`
and `The left leg was not examined. … 7.4 mm …, with no reflux in the right leg.` read both ways). In a run-on sentence
(over 40 words) a side after the value is read within 8 words. A value's side from its sentence — another clause, or its
own (round 14: `the left leg was not examined the great saphenous vein measures 7.4 millimeters …`, `examined.The great
…`) — is no pre-fill where that clause denies the leg's examination near its side word — within four words before it or
eight after, since the limb's words come first (`The left leg was not examined and the great saphenous vein measures 7.4
mm …`, `The left lower extremity was not examined and …`, `The left leg of the patient was not examined …`, `… is not
included in this study …`) — unless the context reads the same leg, nor where that clause names the other leg too
(`right leg she had the left leg treated in 2021 and today the great saphenous vein … 7.2 millimeters`; not a side a
correction struck, nor an earlier clause's scope, `… right leg detailed left leg screening … on the right the common
femoral …`); a sentence pairing values and legs `respectively` reads both ways; and a side written after the value on
the line its sentence wraps into (`… 6.1 mm at the knee in the` / `left leg …`) makes it ambiguous — never a candidate,
since the cited sentence does not write it. Another cited unit's side BEFORE the value is a candidate only, and only
where the value's own sentence names no definite side: the model's choice of what to cite never places a pre-fill.
`R`/`L` count as capitals before an anatomical word or a number, as a label, in brackets not closing a word, sided or on
a vein's abbreviation; `both` only before plural limbs or a pair each leg has one of (`both legs`, `both deep venous
systems`; not `both great and small saphenous veins`, `both sides of the knee`), `either` before one limb (not `either
side of the knee`); an unforeseen form names no side.

**Parity with the engine.** The four shared patterns are read over `wm_narrative.view(text)`, which classes every
character as .NET's regex does: the four letters Python's ignore-case folds onto ASCII (`İ ı ſ K`, measured over every
code point) become that ASCII letter in both boundaries (the engine's `Reading`), and Python's other class differences
(combining marks and connectors, numerics, U+001C..U+001F) are mapped to what .NET calls them. Text answers compare with
ASCII case folded and every other character exact in both (`JOSÉ` is not `José`, `GROSS` is not `Groß`): the engine's
invariant runtime has no Unicode normalisation to agree on. With the flag off the engine's labelled path is
byte-identical to `main`'s (it splits lines on `\n` only).

No whole-note rule: an unrelated sentence, a correction elsewhere or a conditional instruction affects nothing else.

### Statements

A proposal only pre-selects the page and the resolve; the first save replaces it with the clinician's decision. It
is kept only when its variant exists, its required answers are supported, its omitted answers are empty, its cited
units are not held, and a fixed wording's sentence names its side. Identity and signature are never proposed.

What a statement may rest on at review (and at fill):

- a sentence of the notes the clinician chose: the wording's side must be named (at review, a sentence whose
  surroundings read both ways rests it when one of their readings is its side and none is only the other's; a proposal
  needs the side named); a one-leg statement cannot rest only on headings and titles (`BILATERAL LOWER EXTREMITY VENOUS
  DUPLEX` names both legs and asserts nothing; a title is a unit with no finite verb, no denial and no quantity — a date
  or a code is none — that names the study as its subject, not as where a finding was seen or the subject of a reporting
  verb or predicate, read after a run of study nouns (`Right great saphenous vein reflux on duplex.`, `Exam shows right
  GSV reflux.`, `Duplex ultrasound shows reflux in the right great saphenous vein.`, `Ultrasound consistent with …`, `…
  venous duplex positive for …`, `Right great saphenous vein reflux on today's venous duplex study.` state — a later
  verb only as a finite verb or a participle, `… demonstrating great saphenous vein reflux.`: `… VENOUS DUPLEX TO
  CONFIRM REFLUX`, `… FOR CONFIRMATION OF REFLUX`, `… FOR CONFIRMING REFLUX`, `Venous duplex study requested for
  confirming right GSV reflux`, `…, history positive for DVT` are titles: a participle after `to`, `for`, `by` or `of`
  is no verb); an attribution after a finding states (`Right GSV reflux (duplex).`), a study LABEL never does
  (`Ultrasound: right lower extremity for venous reflux`, `EXAM: RIGHT LOWER EXTREMITY`, `RIGHT LEG - DUPLEX`, `… VENOUS
  DUPLEX WITH REFLUX MAPPING` are titles; so is `Duplex: right GSV reflux`, which fails closed); and only the installed
  denial and reframing vocabulary refuses the sentence here (every other governor held the PROPOSAL, and is the
  clinician's to read);
- a wording **built from its answers** — the answers joined by at most 12 connecting words (`TYPE OF EXAM: {side}`,
  the previous-treatment sentence, `Right {vein} is {finding}`, `Right deep venous system {finding}`) — on those
  answers, each complete and reviewed;
- a `not_documented` wording on the answers whose absence it states, each reviewed and empty.

The technique paragraph (63 and 81 words of its own claims), `none`, `not_assessed`, the reflux findings and
clinical correlation need a sentence of the notes (the paragraph-39 recommendation keeps its recorded rule: it needs
support). The page offers "rests on its answers" as an explicit tick; the answer keys are named from the mapping,
never from the post.

### Review, page and finalization

`wm_review` accepts narrative evidence (`kind: unit`, `kind: answers`) only with the flag on and applies the same
support rules; finalization's `governed_decisions` rechecks every `supported` narrative answer with the same reader
(`wm_narrative.held_labels`), and review runs that same function (a `narrative_held` blocker), so review never reports
complete what finalization refuses, whatever the answer now cites. The page and save show and keep exactly what it
refuses (`wm_narrative.as_currently_held`). The first page reviews the proposed statement wordings; a typed sentence
that the notes write twice goes to a distinct occurrence, preferring the one that carries the answer (for a one-leg
statement, the one naming its side); an earlier citation is kept while it carries it and is left only for a copy that
carries it with nothing governing it there (never a prior study's or a relative's copy, for an answer or a statement),
or for a copy in the paragraph of another line the clinician posted that occurs once (its heading: the clinician's
choice), else the copy nearest after such a line, across paragraphs (`LEFT LEG:` over a blank line and `Measurements:`),
never one something governs (a relative's, a prior study's) — a copy's side is not asked there, since the clinician's
posted line gives it (round 13: a sentence written under both legs read as governed in every copy, and the first, the
other leg's, was stored); where no line is posted with it, a copy nothing governs is kept before one only its side does
(`copy_rank` — round 14: `RIGHT LEG:` / `No DVT in the left leg.` / S kept the right block's S for the left answer), and
the note-wide invisible-character hold is not asked of any copy (it says nothing about one: every copy read as governed,
and the answer went to a prior study's); the cited copies and at most 24 others are tried, and at most 24 are judged for
what governs them. A response citing more than 100 sentences for one answer (review's bound) is refused, a statement
wording citing 100 or more is not proposed, and a save posting more than 100 sentences for one answer is refused before
any is resolved or stored; a statement resting on its answers is saved with at most 99, its answers' entry being the
hundredth (round 9: 101 made review refuse the whole page).

### The engine (`WmAdapter.cs`)

`Evidence` gains an optional `kind`/`answer_keys`; the mapping records are unchanged, so every stored mapping digest is
unchanged. At fill a narrative answer must be written in its cited sentences (the parent's quantity, bound and word
patterns, byte-identical and asserted by a test, read over the same classes of character), agree with its labelled
lines, and for a sided question have a side word of that side (or both) from the start of the notes to the sentence's
end. Every engine check is implied by the parent's (never stricter), so the export never refuses what review accepted
(except `main`'s labelled-line case under *Known limits*, which fails closed). It is a FLOOR, not a replica of the
parent: a forged fill request (one that bypasses the parent) can still pass it with a slice of a sentence, or on a side
ANY earlier side word of that side (or `both`) names — `The left leg was examined first.` anywhere above lets a forged
left answer cite a right-leg sentence. The parent validates every posted unit as a complete sentence of the unchanged
notes, so that needs a compromised parent.

## Qualification (offline — not live evidence)

- **Frozen benchmark** (`core/tests/benchmarks/wm_narrative/`), committed before the implementation: 23 cases, six
  labelled/narrative pairs, a transcript, positive findings, denials, family history, corrections, missing
  information and genuine conflicts; expectations by an independent author (`d6c661a1`), provider-shaped responses
  by a second author blind to the expectations (`17483cc1`): a careful set and a weak set with named injected errors.
  ⚠️ The validator's rules were iterated against it over five scoring rounds, so it is a development set.
- **Held-out benchmark** (`heldout-cases.json`, `3af6e471`; blind careful responses `d92cc499`): 12 cases written after
  the implementation by an author who did not read it — headed reports, raw transcripts, shorthand, a letter, a SOAP
  note. Scored on the implementation as it stood: 201 correct, **0 wrong**, **70 unnecessary holds**. After the first
  refutation round's repairs: 253 correct, 2 wrong (choices whose only option overstates the note), 18 unnecessary
  holds; after the second round's: 256 correct, the same 2 wrong, 15 unnecessary holds; after the third round's: **254
  correct, the same 2 wrong, 17 unnecessary holds** (8 are unitless shorthand, `6.8/1.9s`, held by design; most of the
  rest are pre-fill holds the clinician clears at review), 83 statement proposals correct; the same after the fourth to
  fourteenth rounds'. Round 3 closed fourteen classes of wrong pre-fill that round 2's releases had opened; the price is
  two pre-fills that now read both ways. The repairs were checked against this set, so it is now a development set too.
- **Refutation.** Fourteen rounds of four sealed, write-disabled lenses over the finished diff (false green, false
  rejection, parity and integrity, corrections and sides, cost). Every demonstrated break is a regression row in
  `test_wm_narrative.RefutationRegressions` (or a review, quotation or cost test) beside a control of its class. Round 4
  found wrong pre-fills from weak side forms, a heading against its sentence, `both` read for one value, corrections
  placed on a located number, restated or transposed findings and a planned treatment; review and finalization
  disagreeing when an answer was re-cited; and review, the page and the save still quadratic or worse. The mutation
  proofs over round 4's repairs found two more wrong releases the lenses had not: a placed correction restating the
  value (`6.1 mm, correction, 6.1 mm should read 7.6 mm` pre-filled 6.1) and a spoken correction opening its sentence
  that struck nothing (`The right sorry left …` let review accept the right). Round 5 found round 4's own releases
  wrong: `(R)`/`(L)` opening a shorthand line made weak, so a left line's value took the right leg of the line above and
  was finalized there; an opening `I mean` striking the side; `breathe right when` read as `the right`; comparisons
  beyond four words; a bound side running into the next vein; a placed correction repeating the old number past a
  location; a bare `grade 2` corrected in place; a relative after a comma; `either side of the knee`; a measurement-only
  correction releasing a finding choice; the uncited-correction rule letting the model's citation decide; another cited
  unit's side against the value's own sentence; titles with dates; and the save, the page and validation quadratic again
  through the new readings (207 s, 158 s, 145 s). Triaging it found one more no lens had: a side-less impression line
  taking the leg of the block above it. The pre-fill and review verdict of every case are pinned (`ROUND_5`). Round 6
  found round 5's repairs wrong again (and its mutation proofs found round 5's record wrong: the rule that a corrected
  side lends a sentence no paragraph side, recorded as unreachable, is reached when the correction's target is a weak
  form, `Left, sorry, ClosureFast (R) treated …` under `RIGHT LEG:`): a comparison struck the side a value's own
  sentence named (`Compared to prior the right GSV …` pre-filled from the paragraph); the eight-word bound let a nearer
  side after the value stand against the paragraph; the heading's side offered for review under a sentence naming a
  side; the paragraph's first line read as a heading when it was a finding line, and a sentence's own `IMPRESSION:`
  label not read at all; `left` after `is` made weak before the anatomy it names; `reversed` dropped from the
  transpositions entirely; a measurement denied only by the word right before it (`no longer 6.1 mm`); a correction
  replacing the value in a later unit not holding it; a reflux time's citation attributing a diameter's correction; a
  relative after the value released by any verb (`a leg ulcer that her mother has had`); `Bilateral study` read as both
  legs for a value; a placed number's next location read only within a few words; a one-letter label word (`A/P`) read
  as a section; titles that state (`Ultrasound: left SSV reflux.`); the save moving an answer or a one-leg statement
  onto a prior study's or a relative's copy; and the page 91 s and validation 50 s over one long run-on unit cited by
  many answers. Every case is pinned (`ROUND_6`). Round 7 found round 6's releases wrong in their turn — eight of its
  thirteen wrong answers were new, all exported through the real engine: a side-less `IMPRESSION` without a colon took
  the leg of the block above (round 5's triage case again); `was left below the knee` read as the left leg; `Compared
  with the left the GSV measures 7.4 mm` read as the left's own value; the location bound let `Correction: 6.1 mm at the
  saphenofemoral junction should be 7.6 mm` pre-fill the old value, and the widened placed-number search let a
  junction's superseded value through; the per-note memos gave one note's reading to another at the same offsets (a
  struck value pre-filled, reviewed and exported, depending on which process read which note first); and titles with an
  unlisted word (`… WITH REFLUX MAPPING`, `EXAM: RIGHT LOWER EXTREMITY`) stated, so a one-leg statement rested on a
  title. It also found older gaps: `her mother has this`, a compared side lent to the next sentence, `Both legs were
  scanned with the GSV measuring 7.4 mm` read as both legs, a correction another answer cited releasing the rest (the
  model's citation deciding), `6.1 mm is wrong; … 7.6 mm` releasing 6.1, `exceeds the left`. The false-rejection lens
  found a spoken `no I mean` denying the corrected value, a restating correction refusing every answer of its unit at
  review, and the save unable to reach a governed copy; the cost lens a quadratic save (120 s) and memos defeated by
  distinct citations (20 s). The repairs fail closed: round 6's releases that leaked were reverted, the restatement
  moved from support (which review cannot overrule) to governing (which only holds the pre-fill), and the attribution
  release removed. Every case is pinned (`ROUND_7`), and each of its rows failed on the round-6 commit. Round 8 found
  four of round 7's own changes wrong (the added comparison words hid real sides; narrowing `reversed` lost real
  transpositions; a correction naming one replaced value released another it also changed; a placed number still decided
  by a digit a few words on) and older gaps: an opening correction corrected TO the value it denied (`Correction: right
  GSV SFJ 7.6 mm, not 6.1 mm.`), a denial outside any correction unread (`…, not 6.1 mm as previously reported`), a
  side-less impression with its heading on the same line, a weak `(R)` line read as a heading, a labelled study title
  carrying a one-leg statement; review offering only the wrong leg next to a comparison or a side in a denying clause; a
  short finding line opening a paragraph read as its heading; a value repeated in its own correction struck; `No DVT
  bilaterally` lending both legs; a separator Python strips and the engine keeps; and costs — a later correction's
  denials read per heading per quantity per answer (274 s), units rebuilt per answer over a quadratic heading pattern
  (93 s), the save storing and re-matching any number of sentences (190 s), `both` read word by word per place (32 s).
  Every case is pinned (`ROUND_8`); 42 of its 44 rows failed on the round-7 commit (the other two are controls), and
  each new cost test failed there. Round 9 found round 8's releases wrong again, as round 8 had found round 7's: a side
  in a denying clause dropped when it was the value's own (`…, with no reflux in the right leg.` pre-filled the
  paragraph's left); a compared side struck when the value's own clause was about it (`…, compared with the left, which
  measures 5.0 mm` pre-filled 5.0 on the right); `reversed` excused by any flow word (`The reflux times for the right
  and left legs were reversed.`); a repeated value struck whenever a later number followed (review refused `7.4 mm, I
  mean 7.4 mm, … with reflux of 1.8 seconds`), and kept when said wrong in words no list had; and older gaps — an
  opening correction's value said to be the old one anywhere but right after it (`Correction: 6.1 mm at the SFJ is
  wrong.`, `disregard 6.1 mm`), a correction placed on a number whose site was the number before's, a correction written
  above the report it corrects, a denying sentence lending its side (`The left leg was not scanned today.`), a side
  after a compared value dropped, section lines and labels in words no list had or with digits (`Additional findings`,
  `3. IMPRESSION`, `Overall impression -`), a spoken `no` read as a denial, titles whose study nouns ran together
  (`Duplex ultrasound shows …`). The integrity lens found every line break but `\n` joining what the units split (a
  side-less block took the leg above it and was exported) and a stored side set changed by its caller (what review
  accepted depended on which answer a worker read first); the cost lens `line_side` walked per paragraph over weak forms
  (the page 127 s), a denial read per `both` (186 s) and per side word of a clause (97 s), a line's text before a
  sentence read per value (50 s), `both` found by listing every side word before a value (34 s). The repairs fail closed
  again: each release became a hold of the pre-fill whose readings review still accepts. Every case is pinned
  (`ROUND_9`, 186 rows); 148 of its rows failed on the round-8 commit (the others are controls, or variants round 8
  already held another way), and each new cost, review and save test failed there. Round 10 found round 9's own
  line-break repair wrong: its paragraph pattern read a lone `\r\n` — what a browser posts for every typed line — as a
  blank line, so every paragraph-scoped protection stopped at the next line (a correction heading's stale value
  exported, denied symptoms and a relative's finding pre-filled, round 9's impression fixes undone, the save's heading
  choice lost); all four lenses found it. It also found the walk up from a paragraph blind to round 9's first-line rules
  (a line denying its leg read as its heading, digit headings and `COMMENTS:` and a weak-form heading walked past), a
  digit or a stop defeating the unsure first line, a correction heading releasing the stale value under it, `reflux`
  reversed for one leg read as reversed flow, a denied `both` offered at review, the seconds unit `s` read as SOAP's
  `S:`, statements under round 9's ambiguous readings unable to complete, and a leg label over a finding's denial
  (`Right lower extremity: No evidence of DVT.`, the commonest report shape) stripped of its leg — lens 2's battery of
  22 realistic notes pre-filled 49 of 114 correct answers where round 8 pre-filled 104; and older gaps: an addendum
  denying a value without the word `correction`, a transposition excused by the line above, a blank line of invisible
  characters, a comparison read over the line above. The cost lens found four of round 9's own readings run per place
  past the worker timeout (283 s, 251 s, 155 s, 121 s) and 2.3 GB retained. Every case is pinned (`ROUND_10`, 90 rows;
  82 failed on the round-9 commit, the rest controls); every regression row of every round now reads the same under
  `\r\n`, a lone `\r` and U+2028, and every benchmark scores the same under them. The battery now pre-fills 83 of 114
  (the same with CRLF), and review completes for all 114. Round 11 found eight of round 10's own relaxations wrong, each
  held by round 9: a correction naming its replaced value released a move of the findings to the other leg (`…, not 6.1
  mm, and all of the above findings are in the left leg.`); a flow word excused data swapped (`The flow values above are
  reversed.`); a cited transposition released itself; a leg not examined read as a label over a finding (`Left leg: not
  examined for reflux.`); any short line with a finding word walked past (`DVT evaluation`); and comparisons, denials
  and transpositions read a line at a time across a hard wrap. Older gaps: a leg named only in a finding's denial let an
  earlier sentence's leg win (`The left lower extremity demonstrates no evidence of DVT. The GSV measures 5.0 mm …`
  pre-filled the right); an addendum above the report saying `corrected` held nothing; a cited sentence calling its own
  value wrong was support; a correction heading released a value it never wrote; a long side-less heading, an
  `IMPRESSION:` inside a leg's paragraph, `SFJ` against `saphenofemoral junction`, a denial's window reaching into the
  sentence before, `report` read as a corrected value's word; study titles with `to confirm` stating; a sentence under
  both legs saved as the first copy. The cost lens found a paragraph's first line re-read per sentence (199 s), a
  one-leg run of side words walked back per call (127 s) and a copy of every side word per strike set (201 MB). Every
  case is pinned (`ROUND_11`, 86 rows: 64 of its 73 lens and triage rows failed on the round-10 commit, the rest
  controls; 13 more pin the mutation proofs, 12 of which fail there too). Lens 2's battery of 38 realistic notes (270
  correct answers): round 9 pre-filled 203, round 10 200, round 11 198, the same with CRLF, and review completes for
  all. Of 46 mutants over the round-11 rules, 34 were killed at once; ten survivors each got the row their rule exists
  for, and one of those rows found a defect no lens had (the walk up still passed a line of study words, `Standing
  views`, as a vein's heading: two readers of one rule); another survivor found the round-11 cost test vacuous for its
  own fix (the lens's first line ends in `a`, which the hard-wrap rule joins to the next line, so the cached reader was
  never called). The one survivor left removes round 10's per-sentence context memo, a cost-only overlap round 10
  recorded too. Round 12 found round 11's hard-wrap join wrong three ways — a small letter after a heading joined them
  (`IMPRESSION` / `great saphenous vein reflux positive.` took the leg above; lenses 1 and 3), a line of invisible
  characters joined the lines around it, and a denial joined into the value's line lost its strike — and round 11's
  other repairs incomplete: an examination's denial read past to an earlier sentence's leg, and misread (`… no DVT on
  imaging.`); a leg label kept over `no evaluation for DVT`, over a second denial in the next sentence, and as the last
  of a list of both legs' labels; a correction's side after its values; diameters and legs beside `flow`; old-value
  words after the value; unlisted impression labels (`Assessment:`, `Dx:`, `Note:`). Lens 1 exported nine of these
  through the real Word engine. Older gaps (lens 3): a side in a clause denying its leg's examination read as the
  value's, `respectively` with a location between, a side after the value across a wrap, the save's new copy rule moving
  an answer onto a governed copy. The false-rejection lens measured round 11's cost at 45 of 270 correct answers its
  battery's round 10 had pre-filled — most from a leg's own block read as ambiguous with that leg its only candidate —
  and found a transcript review could not complete and a demographic line refused at support. The cost lens found a
  paragraph's first line re-read per sentence (650 s at 49,000 characters; round 10 had it too). Every case is pinned
  (`ROUND_12`, 89 rows; 80 of its 85 lens rows failed on the round-11 commit, the rest controls and one variant round 11
  already held; 4 more pin the mutation proofs). The repairs fail closed where they hold and restore round 10's
  pre-fills where round 11 held needlessly: the battery pre-fills 238 of 270 (round 10 238, round 11 193), review
  completing for all. Of 38 mutants over the round-12 rules, 34 were killed at once; of the survivors, three got the row
  their rule exists for (a label over a history, a value before its bracketed old one, a leg the phrase's own clause
  corrects away — the last holds its pre-fill through the correction rule, so it is pinned at review), and one was
  equivalent by construction — a label's examination word checked twice, the second unreachable — and was removed. Round
  13 found round 12's releases wrong again. Its reading past an examination's denial to a block's heading also read
  finding denials (`In the left leg, reflux was not seen on imaging.`) and partial examinations (`LEFT: Deep veins not
  imaged.`, `Left leg: not examined for reflux.`) as the leg unexamined, so a leg's own values went to the other leg's
  heading and review refused the right one — exported through the real engine by lenses 1 and 3, and on the design's own
  example once hard-wrapped; it is removed, and a denied leg is a candidate beside the reading whatever was denied.
  Also: a denial's window ended three words after the side word (`The left lower extremity was not examined and …`); the
  list-of-labels rule was bypassed by a sentence, a line or a blank line between, one leg twice, or only the other leg's
  label (lens 1), and misread a side heading after a label line as an item (lens 2); stopped impression lines of more
  than three words (`Summary of the findings of this study.`), short unsure lines (`Other`, `Also noted`) and a
  join-word before a heading (`Reflux: no` / `IMPRESSION`) joined their neighbours or were walked past; a labelled
  line's value end cut off its own negation (`Leg pain (-)`, `7.4 mm (not measured today, prior study)`: lenses 1 and 3)
  while a demographic's other label after a comma, a pipe or a semicolon still refused the name (lens 2); a comma ended
  the old-value window (`…, as previously reported, is incorrect;`); a participle after `for` made order titles state;
  `the opposite great saphenous vein` took the heading's leg; a soft hyphen inside a word hid a correction, a
  transposition, a relative and a side from the reader (lens 3, older); a limb label with no colon over its
  examination's denial on the next line headed the block (`Right leg` / `not examined.`); a 13-character measurement
  passed review and was refused at fill. The save's round-12 copy rule stored the other leg's copy whenever every copy
  was held only for its side (lens 2). The false-rejection lens measured round 12's holds on a new battery of 25 notes
  (132 correct answers: round 12 pre-filled 59, round 11 102) and 300 generated reports (2,272: round 12 1,672, round 11
  2,095) — side-less denial lines not read as finding lines (`Negative for DVT.`, `No sonographic evidence of DVT.`),
  comment and note labels in a leg's block, an examination named where a finding was seen, flow reversed in both legs
  read as data swapped, `… unchanged from the prior exam` after a value — and a number and its unit split across a hard
  wrap refused at support (older; *Known limits*). The cost lens found the read-past rescanning the denying sentence per
  side-less sentence (validation 130 s at 49,000 characters; round 11 had the same scan) and four round-12 readers
  listed per place (36 s, 22 s, 18 s, 6 s). Triaging the repairs against lens 2's batteries found round 13's own label
  rule holding the commonest report shape — `FINDINGS:` or a title, then `RIGHT LOWER EXTREMITY: No DVT.` and the values
  (4 answers of round 12's battery, 88 of the generated reports that round 11 pre-filled) — and `No acute or chronic
  DVT.` and `… on compression imaging` losing the label's leg, and a one-leg study's `Left leg not imaged today.`
  holding every value under `RIGHT LEG:`; a label inside its paragraph now heads its block unless the paragraph named a
  leg before it, opens with a system's heading or has a heading line before the value, and reads its wrapped lines as
  unwrapped, and a sentence saying only that one whole leg was not examined lends no value that leg. Every case is
  pinned (`ROUND_13`, 142 rows; 93 of its 101 lens rows failed on the round-12 commit, the rest controls; 9 more pin the
  mutation proofs and 32 the triage), with the save, label, title and cost tests (each failed there). Round 13 pre-fills
  238 of round 12's battery's 270 (round 12 238), 101 of the new battery's 132 (round 12 59, round 11 102), 2,201 of the
  2,272 generated answers (round 12 1,672, round 11 2,095; none that round 11 pre-filled is held), the same with CRLF,
  and review completes for all. Of 34 mutants over round 13's rules, 29 were killed at once; the five survivors each got
  the row their rule exists for — a bracket before a later value, a paragraph opening with a finding's side-less denial,
  a clause denying its leg's examination (read on the physical line, the leg not examined was pre-filled), a wrapped
  transcript cited on its own line, a `1)` list — and are killed. Of 15 over the triage's, 10 were killed at once; two
  survivors got rows (a sentence naming the other leg examined, `Left leg: no.`), one was equivalent by construction
  (the whole-leg reading's negation check: a denying sentence of those words always holds one) and was removed, one
  found the round-13 review cost test vacuous for the new reading (its 26,000 characters stayed under the limit
  unmemoized; a 49,000-character test fails at 11.5 s), and one — an uncached heading index — costs the same at every
  legal size (a note over 1,000 statements is refused) and its cache was removed. Every restoration was verified by
  sha256 and the unmutated module passes. ⚠️ Round 14 refuted both of those last two calls: `No, the left leg was
  examined.` denies with those words and says the leg WAS examined (lens 1: the right was pre-filled), so the reading
  now needs an examination's denial; and `;` splits one legal unit into thousands of sentences, so the uncached index
  was read per sentence (lens 4: the page 169 s) — the cache is back. An "equivalent" call is a claim like any other.
  Round 14 found round 13's releases and two of its own proofs wrong. False green (lens 1: 5 HIGH; lens 3: 5 HIGH, most
  exported through the real engine; lens 2: 2 HIGH-class): a side's label heading past its item on one line (`… Left: No
  DVT in the common femoral vein. The great saphenous vein measures …`, the other leg's CFV check in a one-leg study)
  and a system's label with a finding after its colon read as no list (`DEEP VENOUS SYSTEM: No DVT.`, `Superficial
  venous system: …`); `the other knee`, `The opposite SFJ` and `the opposite GSV` in the value's own clause not read as
  the other leg; a labelled value cut at any word and colon (`Swelling, today: denies`, `Leg pain, Note: patient denies
  leg pain`); a list of old values read at its last (`the 6.1 mm and 5.0 mm values above are incorrect`); a leg a
  sentence only mentions lending its side (`Left leg to be scanned next week.`, `She had left GSV ablation in 2019.`,
  `Left leg exam deferred.`); invisible characters the hold did not list (bidi isolates and embeddings, U+034F,
  variation selectors, tags) and one after a full stop making a sentence an unstopped heading; `No, the left leg was
  examined.` read as the leg unexamined (round 13 had called that check redundant); a stopless value line joined to
  `left leg not imaged today.` lending the denied leg; an examination denied in the value's own clause (an unpunctuated
  transcript, `examined.The great …`); a wrapped sentence's own side phrase (`in the left leg.`) read as a heading; the
  save keeping the other leg's copy, and every copy governed alike under the note-wide hold. False rejection (lens 2's
  new battery of 36 notes, 212 correct answers: round 11 130, round 12 133, round 13 112): a limb's label under
  `FINDINGS:` held through its system and vein sub-headings, `No evidence of deep venous thrombosis.`, a leg named only
  unexamined before a label, `LLE`/`LE`, reasons a leg was not examined, a demographic's remark after a run of spaces —
  now 143 of 212, the same with CRLF; round 12's battery 238 of 270, battery 3 101 of 132, the generated reports 2,216
  of 2,272 (none that round 13 pre-filled is held), review completing for all. Cost (lens 4: 2 HIGH, 1 MEDIUM; lens 3: 1
  HIGH): round 13's uncached block ends read per sentence (the page 169 s), a labelled value's end tried at every space
  of a run (106 s), and every unit of a hard-wrapped run reading the run from its start per answer's strikes (92 s, 327
  MB) — each linear now (*Cost*). Every case is pinned (`ROUND_14`, 81 rows; 67 failed on the round-13 commit, the rest
  controls, correct-leg refusals that read the same either way, and mutation rows), with the save and cost tests (each
  failed there). Of 40 mutants over round 14's rules, 34 were killed at once; of the six survivors, four got the row
  their rule exists for (a bare label after a leg only said to be unexamined; a spoken limb heading ending a line; a
  wrapped side phrase with no stop; a long wrapped sentence's context read from its start), one found the new cost test
  too small for its path (24,000 spaces stayed under the limit with the bracket unanchored; 49,000 do not), and one was
  equivalent — the known-label window, since `labelled_value` already stops at the longest label (0.10 s against 0.11 s
  at 12,400 would-be labels) — and was removed. Re-proved: all killed, every restoration verified by sha256, the
  unmutated module passing.
- **Cost.** The reader answers every per-place question by bisection over positions read once per text (sides, clause
  breaks, digits, words, numbers, quantities by unit, relatives, paragraphs, lines), the backtracking patterns are
  atomic, a correction's reach, its struck spans and the governors' blocks are read once per unit or note, what a
  correction corrects to is read as a window of the whole text rather than a copy, and every cache is bounded by the
  number of texts it keeps (a cache bounded only by entries kept every note a worker had read: 879 MB after four notes;
  now bounded, with plateaus measured from 83 MB to about 260 MB depending on the notes' shape). Adversarial shapes at
  the 50,000-character note limit read in under a second each (`ReadingCost`), and through generation's validation,
  review of every answer and statement and finalization's recheck in seconds (`ReviewCost`): before round 4, one review
  of a transcript with a correction in every finding took 23 minutes at 48,000 characters, a note of 940 pointer lines
  took the page and the save past the worker's 120 s timeout, and 400 correction headings took the page 273 s. Measured
  after: that review 0.6 s; the page 4.6 s and the save 4.9 s at 940 pointer lines (37,664 characters); the page 4.5 s
  at 400 correction headings (46,602 characters). Round 5's: a save of one sentence repeated 600 times 207 s → 0.3 s, a
  sentence of 1,960 weak forms 158 s (the page) → 2.5 s (review), fragments cited by many answers 145 s → 6 s (the
  page); a sentence's side marks, its unstruck side words, each unit's list head and each question's labelled values are
  read once per note. Round 6's: 52 answers citing one run-on unit of 1,680 spoken corrections (48,900 characters):
  validation 50 s → 2.8 s, finalization's recheck 13 s → 0.2 s, the page 91 s → 2.5 s and the save 111 s → 2.6 s
  (measured through the real page, save and Word engine). Every question citing the unit read the same 1,600 places
  again, and each reading hashed the unit's whole strike table: a place's reading is now read once per note
  (`place_reading`), and a strike table is hashed once (`Struck`). ⚠️ The first repair of it (per-note memos of each
  answer's readings, `note_memo`) was measured, and pinned by a test, on the short `Right leg.` sentence instead of the
  run-on unit: the test passed on the unfixed code and the fix changed nothing on the lens's shape. The mutation proofs
  found it; the test now cites the run-on unit and fails at 61 s without the repair. Round 7's: each answer citing the
  run-on unit and a different correction line, validation, review and finalization's recheck 68 s → 5 s (a place is read
  under its own sentence's strikes, `sentence_strikes`); a save posting one governed sentence 499 times per field 120 s
  → 9 s (at most 24 copies judged for what governs them). Round 8's: 400 correction headings over 400 quantities,
  validation and finalization's recheck 51 s → 1.8 s (a correction's denials read once per note); a review-of-systems
  run of 16,000 `no` reviewed 26 s → 0.6 s (units read once per note; the heading pattern that needs a colon is not
  tried without one); `Both great saphenous veins measure 7.4 mm …` × 6,800, validation 31 s → 2.3 s; a save posting
  more than 100 sentences for one answer is refused; memory after 200 distinct page views 105 → 39 MiB traced,
  flattening (per-note tables keep 128 notes, memo keys hold digests, label sets are shared; since round 10, the heavy
  per-note memo tables keep two long notes and 128 short texts). Round 9's: 997 paragraphs under 6,000 weak forms, the
  context of every paragraph 124 s → 0.1 s (`line_side` read in one pass per note); 12,000 `b/l` in one sentence, the
  pre-fill 97 s → 0.2 s (a denial read once per sentence and per clause); a line of 700 sentences 17 s → 0.02 s and one
  unit of 3,000 values after a long line 50 s → 0.4 s (the text before a sentence read as a label only when short); 26
  answers over a run-on of `both legs 7.4 mm` 34 s → 2.2 s (the nearest `both` by bisection); 52 answers over a run-on
  of opening corrections 8.2 s → 2.7 s (denials and plain-value readings kept per text). Round 10's, at 50,000
  characters: the paragraph's first line re-read per place 283 s → 0.4 s, the line above 251 s → 0.8 s, a glued opening
  correction 155 s → 2.2 s, the compared reading's per-place strike tables 121 s → 1.1 s, struck side words walked back
  195 s → 1.3 s, a joined phrase walked back 125 s → 0.4 s (a sentence's context read once per note, a line start from
  the side table, the compared reading's strikes once per sentence, the words before a place and a denial's window read
  within a few hundred characters, a note-level strike set's unstruck side words indexed); memory over seven notes of
  the compared shape 2.3 GB → 121 MB; a generation job of 26 distinct values after one glued opening correction 505 s →
  6.5 s. (Round 9's own figure of 83–260 MB plateaus did not hold for that shape.) Round 11's, at 50,000 characters on
  the lens's own probes: a 25,000-character first line over a semicolon run, validation 197 s → 0.8 s and review 203 s →
  1.1 s (a line's kind read once per text); a glued run of one leg's side words, `R:R:…`, validation 127 s → 1.1 s and
  the page 124 s → 0.9 s, `rt rt …` 83 s → 0.9 s, the sentence shape 67 s → 1.1 s (a phrase walked at most 16 side words
  back, a longer run read as both legs); the per-line strike sets of a note of one sentence 201 MB → 0.1 MB (struck side
  words passed over a merged run at a time, never copied); 26 answers over 3,960 places of a value, the page 7.1 s → 4.1
  s (denied values read once per note). Round 12's: a first line of 12,000 side words over a run of values, validation
  650 s → 1.4 s at 49,000 characters and review of one answer 178 s → 0.9 s at 25,000, a struck first line 11 s → 1.3 s
  (a paragraph's first line read once per paragraph). Round 13's, at 49,000 characters on the lens's own probes, cold,
  measured after the triage: a denial of the other leg's examination under a heading over a run of values, validation
  130 s → 1.6 s (the read-past, which rescanned the denying sentence per side-less sentence, is gone — round 11 had the
  same scan — and the whole-leg reading that replaces it is read once per sentence: unmemoized it took 11.5 s), the same
  ending in `reflux.` 131 s → 1.9 s; a wrap into a run of side words 36 s → 2.0 s and a clause of side words 18 s → 2.0
  s (both read once per sentence end or clause and stopped once both legs are seen); a line of 4,452 `R: No DVT;` labels
  22 s → 0.9 s (a label's examination words read per piece, not to the line's end per label); a context reading's line
  copied per call 6.1 s → 3.0 s. The page, finalization's recheck and review of every answer on each shape: at most 2.1
  s. Round 14's, at 49,000 characters on the lens's own probes: the lines ending a label's block read per sentence (`;`
  makes one legal unit thousands of them) — the page 169 s → 1.1 s, a cache round 13 had removed as costing nothing; a
  labelled value's end tried at every space of a run, 106 s → 0.2 s; every unit of a hard-wrapped run reading the run
  from its start per answer's strikes, validation of 26 answers 92 s and 327 MB → 1.4 s and 80 MB (a place reads at most
  1,200 characters of its wrapped sentence back).
- **The real workflow**: `test_wm_workflow.WMNarrativeWorkflow` (CI, real Word runtime): retained narrative response
  → generation → the page as rendered → decisions → finalization → export into the unchanged original; forged
  narrative answers refused at fill.

## Known limits (this candidate does not solve them)

Every one of these fails closed (a hold, or a statement the clinician must source) unless it says otherwise.

- **Interpretation the text does not signal.** A model that misses a negation, swaps two values within a sentence,
  invents a choice, leaves a real conflict unflagged, misses hedging or reads a plan as the past can still pre-fill a
  wrong answer where no deterministic signal exists (the weak benchmark set: 11 such answers). Every pre-filled answer
  is reviewed by the clinician; that review is the control, and live verification measures how often it is needed.
- **Which row, not only which side.** The reader verifies that a value is written in the cited sentence and on the
  question's side, not which vein or segment it belongs to (`left GSV 5.0 mm, left SSV 7.4 mm` can pre-fill 7.4 on
  the left GSV row if the model puts it there).
- **Choices whose only option overstates the note** (a recanalized vein, a popliteal-only clot: the held-out set's two
  wrong answers) — wording the clinician judges.
- **Statement polarity.** A proposal's cited sentence is checked for its side and its governors, not for saying the
  variant (a `negative` wording on a sentence stating reflux is not refused); the clinician's review is the control.
  A one-leg statement cannot rest on a sentence naming both legs and the other one (`bilateral reflux, worse on the
  left`); a normal leg has no truthful `selected` impression variant (a mapping limitation).
- **Written forms held by design:** unitless shorthand (`6.8/1.9s`), grouped digits (`1,800 ms`), numbers as words
  (`six point one` — so a voice transcript's numbers must arrive as digits; Deepgram with `smart_format=false` is
  UNVERIFIED on that), a spoken `I mean`/`sorry` that is filler (round 11's false-rejection lens measured more than this
  line used to say: one opening a transcript, `okay sorry …`, holds every value after it, and one mid-transcript every
  earlier value of its kind), `right` used as an adverb (`Right at the SPJ`), a phrase naming both legs.
- **Corrections** are read by rule: only what a correction stands right after is struck; everything else it may
  concern is held for the clinician (in a transcript's one sentence, every earlier value of its kind), and one that
  names nothing identifiable holds every answer in its paragraph.
- **Sides that read both ways** are never pre-filled (`respectively`, a bound side running into the next finding, an
  adverb `right`): the clinician chooses among the readings the text gives.
- **Text answers** compare ASCII case-insensitively and every other character exactly (`JOSÉ` ≠ `José`): the clinician
  types a name as the notes write it.
- **Engine floor**, above; a pasted control character in a typed answer (`medial\x0bthigh`) is refused at finalize.
- **A text answer over 1,000 characters** is never read as written (the form's text answers are dates, names,
  identifiers and anatomical locations; its longest option is 89 characters): the clinician shortens it.
- **Backstop vocabularies are not complete.** The words that hold a relative (`grandma`, `stepmother`), a planned
  treatment (`awaiting`, `booked for`), a transposition (`switched`, `dictated on the wrong leg`) or an adverbial
  `right` back up the model's own qualifiers; a form nobody listed is the model's to read and the clinician's to review.
  Growing them into a global keyword filter is what the brief rules out.
- **Held by design since round 5:** `RIGHT LEG:`, a blank line, then `FINDINGS:` — the section heading ends the side
  search, as `IMPRESSION:` must (review completes when the side heading is cited); a side stated only in a LATER cited
  unit (`All of the above measurements are from the right leg.`) is not a reading; since round 6, a correction to a
  number written `I mean no 1.8 seconds` (the `no` reads as denying the corrected value, which is held).
- **Failing closed since round 7:** a finding led by its study noun (`Duplex evidence of right GSV reflux.`, `Right leg
  venous duplex - great saphenous vein reflux.`) is a title — a one-leg statement needs another sentence; a labelled or
  attributed study states only with a finding word written before it (a short list: an unlisted finding reads as a
  title), and a labelled study never does (`Duplex findings: right GSV reflux …` needs another sentence); a restating
  correction holds the pre-fill of the values it writes, and the clinician who reads it may accept either (the old one
  too, deliberately); a later correction stating a quantity holds every value of its unit unless it names the value it
  replaces (`not 6.1 mm`), whichever answer the model gave it to; the save moves an answer onto a copy something
  governs only when the clinician posts that copy's heading (or another line occurring once) with it; one value is
  both legs' only in the tight phrase above; the comparison vocabulary (`than`, `compared`, `unlike` …) is not
  complete — round 8 took `exceeds`, `double`, `twice` and `half` out again because they hid real sides (`the lower half
  of the left calf`) — so `The great saphenous vein measures 7.4 mm which exceeds the left.`, with no other side in the
  note, still pre-fills the left: an unlisted comparative is the model's to read and the clinician's to review.
- **Held by design since round 9:** a side in a denying clause (`…, and the left leg was not examined today`) or one a
  comparison introduces in another clause (`…, compared with the left, measuring 7.4 mm`) reads both ways unless the
  context agrees, so there is no pre-fill (review accepts either leg); a side only a denying sentence names is a
  candidate only (`No DVT in the left leg.` then `The great saphenous vein measures 5.0 mm …` is held; review accepts
  the left), as is the side above a short paragraph line that is neither a finding line nor a vein's (`Additional
  findings`, `Comments`, `Other`), above an unknown label (`Also noted -`), or above a heading whose only side is a
  weak form (`FOLLOW-UP ABLATION (L)`); an opening correction whose sentence says anything but where and what its value
  is (`… 7.6 mm, and not 6.1 mm as dictated`: `as`, `dictated`) holds that value; one opening its sentence above the
  report holds every value of its unit below it, and every one-sided value when it names a side, unless it names the
  one it replaces; a repeat in a placed correction
  is held (struck only when said wrong right after it); a transcript's spoken correction whose next finding names
  another site before its number holds what it may concern (`… 1.2 seconds sorry 1.3 seconds small saphenous vein
  junction 4.0 …`); a diameter written in centimetres (`0.74 cm`) is none of this form's millimetre column (refused at
  support: the clinician enters it in millimetres).
- **A correction written in no word the reader knows is NOT held — this one does not fail closed.** `Erratum:`,
  `Amended:`, `revised to`, `on review of the images` above or below the report correct nothing to the reader, so the
  value they supersede can be pre-filled if the model gives it (round 11's false-rejection lens). The reader reads
  corrections by the words that make them (`correction`, `sorry`, `I mean`, a denial of the value, `previously`,
  `disregard` …); a correction without one is the model's to read and the clinician's to review. The structural rule
  that would catch it — a second value written for the same row and leg anywhere in the note — needs the row a value
  belongs to, which the reader does not decide (*Which row*, above). `Please ignore prior dictation of 5.8 mm` meets
  `main`'s instruction-like-text detector instead: every answer is held and review is blocked until the notes are edited.
- **Held by design since round 11:** a leg named in a finding's denial inside another leg's block (`RIGHT LOWER
  EXTREMITY:` / `No DVT in the left leg.` / `The great saphenous vein measures 7.4 mm …`) reads both ways, so there is no
  pre-fill (review accepts either leg); so does an impression's label or heading inside a leg's paragraph (`RIGHT LEG:`
  / `Impression: GSV at the SFJ 7.4 mm …`), a line run on into the next with a small letter (`The left leg was imaged` /
  `no reflux seen.` is one denying sentence), a sentence `neither … nor` (no denial to generation's shared vocabulary,
  so a phrase naming both legs), and a comparison wrapped across a line (`… larger than` / `the left, measuring 7.4
  mm …`, as unwrapped); a short line of anything but findings and anatomy (`Images reviewed.`, `Valsalva performed.`,
  `Mild edema.`, `Duplicated GSV.`) ends the walk up from a later paragraph (review completes when the side heading or
  the answer's own sentence is cited); a flow reversal in any word beyond flow, veins and the manoeuvre (`Flow above the
  knee is reversed.`, `Doppler signal reversed …`) reads as the legs swapped and holds every one-sided value; a value its
  own clause calls the old one (`prior`, `previously`) holds the pre-fill of that value written elsewhere (a history's
  `prior … 6.1 mm` holds today's 6.1 mm); `misdictated` in an addendum reads as legs swapped. Lens 2's battery of 38
  realistic notes (270 correct answers) pre-fills 198 (round 10: 200, round 9: 203), the same with CRLF, and review
  completes for all of them; citing only each value's sentence, 205 pre-fill and 11 need the clinician to cite the side
  heading.
- **Held by design since round 12:** a leg named in any denying sentence — of a finding or of its examination — is a
  candidate beside the rest of the reading, so review accepts it even where the notes say it was not examined (`Left
  leg: not examined for reflux.` then a side-less value: the clinician decides); it is the pre-fill only where the rest
  reads the same leg (round 13 removed round 12's reading past an examination's denial to its block's heading: it read
  finding denials so too, and dropped the denied leg from review; only a sentence saying nothing but that a whole leg
  was not examined is read past now); a limb label inside its paragraph heads nothing after it (round 13; round 12 read
  only the last of a list of both legs' labels, `Right: No DVT.` / `Left: No DVT.`); a limb label over findings keeps
  its leg only when nothing on its line names an examination but as where a finding was seen (round 13: `Right: No DVT
  on duplex imaging.` keeps it, `Left: No DVT. Not imaged for reflux.` does not); a side-less line denying the
  examination inside a leg's paragraph (`LEFT LEG:` / `Not examined.`) and an impression labelled inside it leave the
  leg a candidate (round 13: not a finding's denial, `Negative for DVT.`, nor a comment, a note, a result or an
  assessment labelled over what it says, which held whole blocks); a side written after a value across a hard wrap makes
  it ambiguous, and review cannot accept that leg at all unless a cited line before the value names it (review reads
  sides before the value, as the engine does) — a MEDIUM false rejection left open, since offering it would let review
  accept what the engine refuses; a study noun with an adjective phrase further on (`… consistent with …`, `… positive
  for …`) is a title. A cited bare negative line (`Right: No DVT.`) still holds the value it is cited for, and a
  `negative` statement proposal resting on `LEFT: No saphenous reflux.` is dropped (the clinician chooses it; review
  completes). Round 12's false-rejection lens's battery of 40 realistic notes (270 correct answers): round 10 pre-filled
  238, round 11 193, round 12 238, the same with CRLF, and review completes for all of them without a heading cited;
  round 11's battery: 197 (round 11 198, round 10 200).
- **Held by design since round 13:** a leg named in a denying sentence inside another leg's block reads both ways unless
  the sentence says only that the whole leg was not examined (`RIGHT LOWER EXTREMITY:` / `Left leg not examined for
  reflux.` or `In the left leg, reflux was not seen on imaging.` / `The great saphenous vein measures 7.4 mm …`: review
  accepts either leg); a limb label inside its paragraph leaves its leg a candidate for what follows it on other lines
  where the paragraph named a leg before it, opens with a system's heading, or has a heading line before the value
  (`RIGHT LOWER EXTREMITY:` / `Left: No DVT in the common femoral vein.` / `The small saphenous vein measures 4.1 mm …`;
  `FINDINGS:` / `RIGHT LOWER EXTREMITY: Deep veins patent.` / `Great saphenous vein:` / `SFJ 7.0 mm …` is held too —
  review accepts the right); a short unstopped line that may head a section (`Other`, `Also noted`) takes no
  small-letter line into its sentence and leaves the side above a candidate; a line naming an impression's word with no
  finite verb, of any length, leaves it a candidate; a sentence speaking of `the opposite`, `other` or `contralateral`
  leg or vein takes no side from around it; an invisible character inside any word of the note holds every pre-fill
  (review completes: the clinician reads the notes; text pasted from a word processor can carry soft hyphens, and no
  lens battery has measured how often).
- **A number and its unit split across a hard wrap** (`… with reflux of 1.2` / `seconds.`, `… measures 5.3` / `mm at the
  …`) is refused at SUPPORT whatever the clinician cites: the quantity pattern the parent shares with the engine allows
  only spaces or tabs between a number and its unit, and every line is its own unit. Review cannot complete without the
  notes being edited (the line joined). Round 13's false-rejection lens wrapped its battery's prose notes at 60 to 80
  columns: 5 to 15 correct answers of about 270 (2–6%), in 4 to 13 notes, could not be accepted. It fails closed;
  reading across the break needs the engine's pattern changed with the parent's, which this candidate leaves unchanged.
- **Held or refused by design since round 14:** a leg named only as `the other`/`opposite`/`contralateral` one is no
  side review can accept either (the engine needs the side written; the clinician writes it into the notes); a bare
  side's or a vein's label inside a paragraph (`Left: No DVT in the common femoral vein.`) heads nothing after its item
  where a leg was named before, the paragraph is a system's list, or a heading or an anatomical label comes before the
  value, while a LIMB's label heads its block (a contralateral check written `Left leg: No DVT in the common femoral
  vein.` inside the right leg's block still heads what follows it — a limb's label is read as a block); a leg a
  sentence only mentions inside another leg's block is a reading only (`Left leg to be scanned next week.`); an
  invisible character on any line that shows something holds every pre-fill, a byte-order mark opening the notes
  included (its first line's heading also reads as an unknown word — held before round 14 too).
- **Refused at support, so review cannot complete without the notes edited (round 14's false-rejection lens):** a value
  or its unit with an invisible character inside it (`7.3 milli`+U+00AD+`meters`, `7.3`+U+200B+` mm`); a spoken
  correction that does not repeat the unit (`7.1 millimeters, correction, 7.4 with reflux …`, `1.2 seconds, I mean
  1.4.`: the corrected-to number carries no unit, and the engine reads none); a bare leading decimal (`reflux .8 s`);
  and in a one-leg study that never names the other leg, that leg's reflux statement (claim 36 or 32): its
  `not_documented` wording rests on no answers in the mapping and no sentence names the leg — the clinician adds `Left
  leg not examined.` (then it completes). A labelled value after an FS, GS or RS line break is accepted at review and
  refused at fill, like the other non-`\n` breaks below (fails closed).
- **A relative's attribution in the NEXT sentence** (`Leg ulcer at the medial ankle. Her mother has it.`; a semicolon
  ends a sentence here too) is the model's `subject` to read: the relative backstop reads the value's own sentence.
- **Answers carry their cited sentences' text to the engine**, so about fifty answers citing one unit of 40,000
  characters or more (an hour of unpunctuated dictation) exceed the engine's 2 MiB request limit (`main`'s): the page
  says so and nothing is exported (fails closed). The clinician splits the transcript into sentences.
- **Held by design since round 10:** `RIGHT LEG:`, a blank line, then a report sub-heading (`Measurements:`, `Findings
  summary`, `3. IMPRESSION`) ends the side search, as `FINDINGS:` does; a short side-less line that states no finding
  (`Patient tolerated well.`) ends the walk up from a later paragraph; an addendum above the report naming a side
  without the value it replaces (`Correction: the right GSV at the SFJ is 7.6 mm.`, `… 7.6 mm (previously 6.1 mm)`)
  holds every one-sided value below it; review completes by citing the side heading or the answer's own sentence.
- **A labelled line after a non-`\n` line break** (inherited from `main`): the engine's labelled path splits lines on
  `\n` only, so an answer whose evidence is the value of a labelled line after U+2028, VT, FF, NEL or a bare `\r`
  (`Patient ID: SYN-1` U+2028 `Patient name: Jane Doe`) is accepted at review and refused at fill
  (`unsupported_answer`); it fails closed, and the clinician cites the whole line instead.
- **A reviewed-empty answer whose label and value another line break separates** (inherited from `main`): the engine's
  labelled path splits lines on `\n` only (byte-identical with the flag off) where the parent splits on every line
  break, so `Patient name:` U+2028 `Jane Doe` (or `\v`, `\f`, `\x85`, a bare `\r`) lets review accept the answer left
  empty while the engine reads the value there and refuses the fill (`missing_documented_answer`, shown as the generic
  refusal). It fails closed; the clinician enters the answer. So does `Patient name::` (the engine reads the first colon
  matching the label, the parent the last).
- **The engine's labelled-line reading is `main`'s** and is unchanged: it compares the text before every colon of every
  line with each missing field's label, so a note of 24,000 colons on one line runs to the engine's time limit and is
  refused (`advanced_processor_unavailable`, fails closed). The parent's reading of the same lines is linear.

## Live verification (NOT run; needs the owner's authorization)

**One campaign:** the 17 narrative and transcript cases of the frozen benchmark, then the held-out cases, through the
live provider on the synthetic account (`QUILLMD_WM_NARRATIVE=1` on the QA stack or a synthetic encounter; never a real
visit), scored by the same scorer (`core/tests/wm_narrative_benchmark.py`), with each response retained as a replay
file so every later run can be reproduced offline.

**Size, measured on the frozen cases:** 468,149 input bytes (27.5 KB per request: payload, instructions, schema) and,
from the careful responses, ~13.7 KB of output per request. The application reserves per request (input bytes +
12,000) input tokens and 12,000 output tokens at the configured rates and shows that maximum before sending.

**Cost** (the configured rates are in the private environment and were not read; three list-price assumptions):

| assumed $/M tokens (in / out) | expected, 17 requests | reservation bound | ×1.5 customer limit |
|---|---|---|---|
| 3 / 15 | ≈ $1.56 | $5.08 | $7.62 |
| 5 / 25 | ≈ $2.60 | $8.46 | $12.69 |
| 15 / 75 | ≈ $7.81 | $25.38 | $38.07 |

(expected = input bytes/3.5 and output bytes/3 tokens; the bound is what is held, not what is charged; add the
held-out cases at the same per-request figures.)

**Pass criteria, fixed before the run:** on the narrative/transcript cases, no wrong pre-filled answer; unnecessary
holds and missed answers reported separately with every row; any wrong pre-filled answer stops the campaign and is
analysed before anything else. Enabling the flag for doctors is a separate owner decision after it.
