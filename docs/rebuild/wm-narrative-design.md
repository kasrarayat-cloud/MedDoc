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
| **support:** the value is not written in a cited unit: a measurement's number (at most 12 characters, as the engine reads one: `1800.00000000 ms` is none) in its column's own unit (a diameter in a reflux-time column is no answer: round 17e's review, `7.4 mm` pre-filled as a reflux time and refused only by the engine) with a unit word of that column (a reflux time may be in seconds), not approximate, bounded, ranged or an alternative (`7.4 mm+`, not `7.4 mm + reflux`); text copied (ASCII case folded, every other character exact, as the engine compares it); a choice is an option | held |
| **support:** the value's own sentence strikes it in place: a correction inside a sentence strikes only what it stands right after — correcting to a number, the number just before it (with at most a few words after it) when of that unit or bare (`6.1 mm, correction, 7.6 mm`, `6.9 correction 6.6 millimeters`, spoken numbers too); correcting to a number, only that number's quantity (`7.4 mm right, correction, 7.6 mm` keeps the right); correcting to words, the few words just before it, never the side said with them unless it corrects to a side (`Left leg, I mean, the great saphenous vein …` keeps the left; `The right sorry left …` strikes the right); a SPOKEN correction opening its sentence still strikes what it stands right after; a bare number only when written as the correction's number is (`6.9 correction 6.6 millimeters`; not `grade 2 reflux, correction, 6.9 mm`); a correction that first repeats the old number strikes the repeat too only when it says right after it that it is wrong (`6.1 mm, correction, 6.1 mm is wrong, 7.6 mm`) — any other repeat is held for the pre-fill (`7.4 mm, I mean 7.4 mm, at the SFJ with reflux of 1.8 seconds`, `6.1 mm, correction, 6.1 mm was misdictated`; review accepts it) and is no rival of the value it corrects to (`6.1 mm, correction, 6.1 mm should read 7.6 mm` corrects to 7.6); a spoken `no` between two numbers corrects the first (`6.1 no 7.6 millimeters`); `sorry, make that` is one correction. A measurement is denied WHEREVER it is written by a denial in its own clause that reaches it through intensifiers only (`not 6.1 mm`, `no longer 6.1 mm`, `is not really 6.1 mm`, `rather than 6.1 mm`, `instead of 6.1 mm`; `… 7.6 mm at the saphenofemoral junction, not 6.1 mm as previously reported`; not `without reflux, 5.3 mm`, `without reflux measures 4.4 mm`, `6.1 no I mean 7.6`, `6.1 no 7.6 millimeters`), and never from the sentence before (`…, reflux is absent.` / `7.6 mm is the diameter …` denies nothing); a value its own sentence says is wrong right after it is not live either (`6.1 mm is incorrect`, `… 6.1 mm was a dictation error`) | held |
| **support:** a line labelled with this question disagrees, at a line start or after a bullet (prose under a choice's label is interpretation) — its value read to the next label on the line, after a run of spaces, a tab, a separator (`,` `|` `;` `/`), a spaced dash or a space (`Patient name: SYNTHETIC PATIENT B    DOB: …    Allergies: none`, `Patient name: SYNTHETIC PATIENT B, DOB: 06/30/1959, Allergies: none`, `Date of service: 09/22/2026 | Indication: …`), and for demographics to a bracket, a spaced dash or a run of spaces or a tab too (`06/30/1959 (not verified by patient)`, `09/22/2026 - no prior study for comparison`, `06/30/1959    not verified`); for any other question only to a label of this form's (round 14: `Swelling, today: denies`, `Leg pain, Note: patient denies leg pain` lost their own denial to a label nobody listed), never short of the value's own words (`Leg pain (-)`, `Swelling    denies`, `7.4 mm (not measured today, prior study)` disagree) — for a measurement its value is negative only in its own clause or in a remark with a negative clause that is not nothing but a finding's denial, or names the question's own (round 16: `(not reliable due to thrombus)`, `, not measurable due to thrombus` deny the value) (`Right GSV at the SFJ: diameter (mm): 7.4 mm, reflux: none`, `7.4 mm (no reflux)`, `7.4 mm, no thrombus`, `7.4 mm - competent, no reflux` carry it; `reflux time (ms): 2100 ms, no reflux`, `7.4 mm (no reflux, not confirmed)`, `7.4 mm, no, 6.1 mm` do not — round 15: the diameter was refused at review, which could not complete); a demographic's remark calling its value wrong or replaced after it (`Date of birth: 06/30/1959 - incorrect, DOB is 06/03/1959`, `Patient ID: SYN-0042    old ID, now SYN-0043` — round 15; `typo`, `amended`, `duplicate`, `changed` — round 16) disagrees too; a unit labelled for another question supports nothing | held |
| **support:** a Right/Left question whose value NO reading of the text places on that side (or both) — see *Sides* below; ruling #127: the model never asserts laterality | held |
| **governing:** a Right/Left question whose PRIMARY reading is not that side — the readings compete, or the side comes only from another cited unit | held (the clinician may choose any side a reading gives) |
| **support:** a measurement ROW's value that every place it is written is read for another row: its own item names another vein or level, and its sentence names the row's own nowhere before it (`LEFT LEG:` / `The small saphenous vein measures 5.4 mm at the saphenopopliteal junction.` is no reading of the left GSV at the knee's 5.4 mm) — see *Rows* below (round 17) | held (`row`; review refuses it too) |
| **governing:** a measurement row's value no place of which is read for the row: no level written for it, a level only near the row (`mid thigh`, `above the knee`), two readings, or only a vein the sentence or paragraph wrote earlier where another vein is named: a vein word this reader does not know between them (`The AAV measures …`, the word before `vein` in `the circumflex vein`, `the superficial epigastric vein`, `the intersaphenous vein`, `a dilated vein` — an adjective names a vein of its own; only `the vein`, `this vein` point back — and a lower-case `aav`), such a word after the item's own vein in its sentence (`The right great saphenous vein is competent and the circumflex vein measures 4.2 mm …`), or a vein named anywhere after the value in its sentence (`a 6.8 mm anterior accessory saphenous vein`, `… demonstrated only in the anterior accessory saphenous vein`, `6.8 mm and 1.2 seconds of reflux in the anterior accessory saphenous vein`, a bracket or an apposition naming the subject: `the dominant refluxing vein (anterior accessory saphenous vein)`, `…, which is the anterior accessory saphenous vein, …`) — unless that vein opens a statement of its own: a value right after it (`… 1.2 seconds small saphenous vein 3.3 millimeters`), a level before its next value (`… right small saphenous at the spj 3.9 millimeters`), or a finding of its own (`…, and the small saphenous vein is competent`, `(SSV normal)`); and a value of what is no vein (`a 9 mm lymph node`). `varicose` said of the vein right before it (`… is varicose and measures 7.4 mm`) is no tributary; `there are varicose vessels` is. A row's reading reaches `WRAP_REACH` after the value in a hard-wrapped sentence (a vein two lines on is read) | held (`row_unknown`, its sentences shown; review accepts the clinician's choice) |
| **governing:** a choice whose option says more than its cited units (`option_reason`): an option listing the deep veins its finding is in (`with evidence of an acute DVT of CFV, FV, POP V, PTV.`) needs each of them joined to a finding by nothing but list words (`thrombus in the popliteal vein`, `DVT of the common femoral, femoral, popliteal and posterior tibial veins`; not `CFV and FV compressible`, nor `… with CFV unremarkable`); a qualified option (`retained small saphenous vein`, `duplicate …`) needs its qualifier described in the clause naming that vein, and the plain one beside it is a wording decision where it is (`Previously treated SSV has recanalized`; not `retained right great saphenous vein …; left small saphenous vein is absent`) — round 17, the held-out H06 | held (`overstated`, `wording`; the original template is unchanged, and leaving it blank is an answer) |
| **governing:** a choice whose cited sentences name nothing clinical at all — no vein, level, side or finding, nor the option's own words (`Venous duplex performed today; images saved for review.` for `Bilateral Detailed`); whose finding is denied, directly (within four words, no number between) and at every place its words are written (`She denies leg swelling or pain.` for `Leg pain`; not `…, reflux is absent; … with reflux of 1.4 seconds`, nor an option that is itself an absence); or hedged in its clause at every place it is written (`possible reflux …; this is questionable` for `reflux positive.`; not one plain statement of it) — `choice_evidence_reason`, round 17 | held (`absent`, `negative`, `uncertain`) |
| **governing:** a rival: another live value the notes give this measurement's row on this side, in another sentence or the cited one (`The left great saphenous vein measures 6.9 mm at the saphenofemoral junction.` against `Summary: left GSV at the SFJ 9.6 mm`; in the cited sentence also one of the row's vein with no level written, `…, repeat measurement 9.6 mm`, and in its paragraph one whose level points back, `On repeat imaging it measures 9.6 mm there.` — not an existential `There is …`; a bound is one where the answer is outside it, `less than 3 mm`, not within, `less than 10 mm`; an estimate, a range or an alternative that is not the answer is one, `about 7 mm`, `6-8 mm`; not a value of what is no vein, `9 mm lymph node`). A value held for itself is still a rival unless what holds it says it is not today's value of this row on this leg: an earlier study's or a plan's, a correction's, someone else's, a denied one, one placed on the other leg or another row outright, or a heading whose own line says one of those (`Prior study:`, `Plan:`, `Family history:`) — a hedge, a side or a row read two ways, a date not told apart from the study's, and a heading the reader cannot classify (`Repeat measurements:`, `Second look:`) leave it a rival. A value read two ways — by its own sentence or from its paragraph — is a rival where every reading it gives is this leg (`… 9.6 mm at the saphenofemoral junction with reflux in the left leg`; `Right after augmentation the great saphenous vein at the saphenofemoral junction measures 9.6 mm.` under this leg's heading), not under the other leg's heading or paragraph. For a sided choice, another option of four or more words that states a finding, written as such on this side (`the right deep venous system is without evidence of obstruction or insufficiency` against `chronic DVT of the right CFV, FV, POP V and PTV`) — `row_rivals`, `option_rivals`, round 17; round 17e's review and its focused pass | held (`conflict`, the rival shown) |
| **governing:** the value's whole sentence as the reader wraps it, within its block, where only part of it was cited (`whole_sentence_entries`): every governing reader above, and the relative and planned-treatment backstops, read over it as well — citation limits what can support an answer, never what can govern it (`Her mother's right great saphenous vein … measures` / `6.1 mm.`, `… but denies` / `leg pain and heaviness.`, `Plan: … is expected at` / `6.1 mm.`, each with only the value's line cited) — round 17c's review | held |
| **governing:** a measurement's own clause and sentence: a hedge before the value (`possibly measures 6.1 mm`; not the next finding's, `… 5.3 mm … with possible reflux`), or after it before a `;`, the next value or the next vein (`6.1 mm (possibly artifact)`, `…, possibly artifact`, `…, which may be artifact`, a question ending its sentence `…?` but not a tag `…, correct?`, `…, questionable due to thrombus`, `…, both possibly artifact` after several values, `…, and I think this may be artifact`), or in a bracket opening the next line (`… 6.1 mm` / `(possibly artifact).`); `maybe`/`perhaps` right beside the value (`measures maybe 6.1 mm`); not a finding's hedge (`… with possible thrombus in a tributary`), the next value's (`… 7.4 millimeters reflux probably 2 seconds`), a cause's or a treatment's (`…, likely the source of her symptoms`, `likely from chronic reflux`, `possibly worth treating`, `would likely benefit from …`); the value attributed to an earlier study, its nearest such phrase with no other value between (`… 6.1 mm on the prior study`, `the prior duplex showed …`, `previously measured …`; `7.4 mm … compared with 6.1 mm on the previous exam` holds the 6.1, not the 7.4) — read before any date; or a date in its sentence, the nearest before or after it with no other value nor `;` between, read to the day it gives (`03/14/2023`, `3/14/23`, `14/03/2026`, `2023-03-14`, `March 14, 2023`, `Jan. 2023`), earlier than the note's own study date (a `Date of service`, `Exam date`, `DOS` label, or a title opening its line, `Venous duplex 09/25/2026`; never one with a prior word around it, `Comparison: exam date …`, `Study date (prior): …`), or any date where the note gives none (`9.6 mm in 2023`, `In 2023, the …`, `Back in 2023 the …`, `The 2023 duplex shows …`, `… on the pre-ablation duplex of 2023`, `… after ablation in 2019`). Not a comparison's date (`Compared with the prior study of 03/2025 … now measures`, `since 2023`, `unchanged from 2023`), a date of birth, one a word of today stands after (`… in 2021 today the right …`; not `now ablated`, `currently occluded`, `before this study`), one before a value whose own predicate is a measurement in the present where a leg or a treatment is named before the date (`the left leg was done in 2021 the great saphenous vein at the knee measures …`, `History of left great saphenous vein ablation in 2021, right great saphenous vein measures 6.1 mm`), nor the other leg's treatment after it (`…, and the left great saphenous vein was ablated in 2021`); today's value compared with a dated one stands, `6.1 mm …, compared with 9.6 mm in 2023`, the compared one held as another study's — `measurement_context`; the model's qualifiers read these first, this holds a model that missed them | held (`uncertain`, `timing`; `dated` where a date cannot be told from the study's) |
| **governing:** a choice's finding denied by a denial verb before a list it is in, past the denial's own phrase (`denies any history of`, `denies experiencing any`, `denies complaints of`), with nothing but list words between, however long the list (`She denies leg pain and swelling.`, a review of systems of nine findings); the list ends at a verb, a contrast, a positive finding, a new subject with its own verb (`… her legs ache and she gets swelling`), a `;`, a number, `, with …` or `, history of …`, and an option affirmed right after it in its clause is not denied (`… right great saphenous vein reflux positive.`; not `at present`); a bare `no`/`without` reaches four words only (`… but no restless legs, and aching leg pain` is not read across) — `choice_evidence_reason` | held (`negative`) |
| **governing:** a line that goes on with the unfinished value of a label line above it (`Clinical indication: she denies` / `leg pain and swelling.`), or left open on a denial and its own words (`… she denies any`, `… negative for any of`) whatever the next line or the list under it opens with (a capital, `- leg pain` / `- swelling`, a numbered list, one blank line before it, a bulleted label), is read with that label by the readers that only ever hold, from the label value's last sentence (`History: right GSV ablation in 2019. Today` / `the great saphenous vein measures …` goes on from `Today`); never by the refusal-only reader of a value's own sentence — `_continues_label` | held |
| **support:** the value's whole sentence, cited or not, gives it only the other side (`The great saphenous vein measures 6.1 mm at the` cited alone, `saphenofemoral junction in the left leg.` on the next line, for the right) — `own_sentence_other_side`, round 17c's review | refused at review (`side`) |
| `subject` unclear, a relative before it in its sentence (in a transcript's run-on sentence, the 25 words before it) or after it within its sentence and 12 words (`Leg ulcer, per mother, not the patient.`; not one with a finding of its own there, `… because her mother has varicose veins` — its own verb that is not a copula, nothing tying it back to the value: `a leg ulcer that her mother has had`, `her mother has it`/`this`/`these`, `her mother is actually the affected person` and the value's words again all hold; `family physician` is not one; a relative in the NEXT sentence is the model's `subject` to read), `certainty` uncertain, `conflict`, a timing that does not fit the question (previous treatment: prior, its outcome also current; a clinical indication: current or prior; demographics: any; everything else: this examination), or a previous treatment written as planned (`scheduled for ablation`, `recs: EVLA`) | held |
| **governing:** a heading or pointer the installed vocabulary says changes meaning (a denial, a family history, a hypothetical) holds its block, sub-headings and a spaced list included, to a new prose paragraph; any heading with a word nobody listed fails closed the same way | held with the governing lines |
| **governing:** a SECTION heading or label (`section_holds`) holds only what its content cannot answer: a plan holds everything (a plan joined to the assessment, `Assessment and plan:`, is the assessment's); a history or prior study holds all but a previous treatment and a clinical indication; a treatment/procedure section that does not say it was before holds a previous treatment; a complaint section (`HPI:`, `CC:`, `REASON FOR EXAM:`, `S:`) holds this examination's findings; demographics are never held by a section; a structural heading (sides, limbs, this form's veins and rows, report sections) holds nothing, and one naming the question's own section does not hold that question | held with the governing lines |
| **governing:** a cited sentence's own short label (up to four words) that is unknown, a section word before a comma in it (`Prior study 2019, right GSV:`) or anywhere in a longer label (`Prior study 2019 right GSV SFJ:`, `Previous right GSV SFJ diameter:`), the question's own label with a denying value unless the answer is written there with no denial right before it (`Swelling: none.`, `Leg pain: denies leg pain.`; not `Right GSV SFJ: 7.4 mm, no reflux`), longer text before a colon with the denial vocabulary or a rule-out, or a fragment under a denying label (`Denies: leg pain. Swelling.`) | held |
| **governing:** a correction that may have replaced the value without striking it: one inside its sentence, after the value, that `concerns` it (unless it is PLACED: a number corrected to a number that opens what it corrects to, with no location of its own in its few words, or a location bound to it that is the same site as the number it stands after — `6.9 correction 6.6 millimeters`, `7.9mm, correction, 8.3mm at the SFJ`; not `…correction, SFJ 7.1 mm`, not `… proximal thigh 6.3 millimeters correction 7.4 millimeters at the junction …`, nor — where the number it stands after names no site — a location at the site of the number before that one: `… SFJ 7.1 millimeters small saphenous vein 6.3 millimeters correction 7.4 millimeters at the SFJ …`); one opening its sentence in the answer's own unit or paragraph that concerns it, unless the answer is what it corrects TO — for a measurement, its FIRST quantity after it, with no later quantity of its unit in the unit but a denied one, and every other word of its sentence saying only where and what the value is — an inclusion list, so an unlisted word holds (`Correction: the right SFJ diameter is 7.6 mm.`, `Correction: right GSV SFJ 7.6 mm, not 6.1 mm.` correct to 7.6, never to 6.1; not `Correction: 6.1 mm at the SFJ is wrong.`, `disregard 6.1 mm`, `6.1 mm was misdictated`, `6.1 mm should read 7.6`); a correction whose reach writes more than one quantity of the answer's unit, the answer's value among them (`6.1 mm should read 7.6 mm`, `Correction: 6.1 mm at the saphenofemoral junction should be 7.6 mm`; a placed correction's reach ends at the next location after its first number) — for the pre-fill only, the clinician who reads it may choose either; a later one whose corrected text mentions the value — and one opening its sentence BEFORE the answer (on a line above the answer's, anywhere in its sentence unless placed: `Addendum: Right GSV SFJ diameter corrected to 7.6 mm.` above the report), read the same way, unless its reach holds the answer's own sentence, writes its value, and writes no other quantity of its unit nor a denied one (`Correction: the right GSV at the SFJ measures 6.9 mm, not 7.4 mm.` above the report holds 7.4; `CORRECTION:` over the value it corrects to does not; `CORRECTION:` / `… 7.6 mm, not 6.1 mm.` / `… 6.1 mm …` holds 6.1); a cited correction unit that does not write the value, a correction restating the value (`6.1 mm belongs to the left leg`); a later one that replaced this very value where it stands (`Right GSV SFJ 7.4, correction, 7.9 mm.` below `… 7.4 mm at the SFJ.`); a later one stating a quantity of the answer's unit, unless it is placed in its sentence (resolved where it stands), this answer cites it, or it says which values it replaces — as many of the quantities it writes denied as not (`… measures 6.7 mm, not 6.1 mm`: then only the values it writes; not `… is 4.4 mm, not 4.0 mm, and the GSV at the SFJ is 6.9 mm`) — never because another answer cites it (the model's choice of what to cite decides nothing); for a one-sided question, a sentence saying the legs were swapped, before or after the answer, cited or not (`transposed`, `mislabeled`, `reversed` — `The sides in the dictation above are reversed.`; with or without a side word; not `reversed flow`; flow or its direction reversed is reflux only when its sentence names at most one leg and speaks only of flow, veins, the patient's position and the manoeuvre — `flow … is reversed for 1.8 seconds`, `Flow is reversed in both great saphenous veins`, `Flow is reversed in the great saphenous veins of both legs with Valsalva.`, `… with the Valsalva maneuver`, `With the patient standing, …`, `…, consistent with reflux.`; not `The flow values above are reversed.`, `The flow measurements of both legs were reversed.`, `… between the two legs`, `The flow above is reversed.`, `The diameters and flow of both legs were reversed.`, `Flow and reflux in both legs were reversed.`: an inclusion list, so an unlisted word holds; `reflux` reversed is data swapped, for one leg or both: `The reflux times for the right and left legs were reversed.`, `The reflux values for the left leg were reversed.`, `The reflux values above are reversed.`; read within its line, joined across a hard wrap) or a correction in another paragraph naming a side, a quantity with it or not, unless it says which values it replaces and every side it names is written before a value in its clause (`Correction: the right GSV at the SFJ measures 7.6 mm, not 6.1 mm.`: then only those; not `Correction: the SFJ diameter is 7.6 mm, not 6.1 mm, and all of the above findings are in the left leg.`, `…, and the above findings with reflux of 1.8 seconds are all in the left leg.`); and a sentence anywhere — a cited one too — that denies the value where it writes it, says it is wrong right after it, or calls it the old one in its clause on its line — within six words before it (`previously`, `prior`, `originally` …), or after it in its sentence before its next value, a joined clause (`and`, `but`, `while`, `whereas`, `;`) or a bracket holding the next value, commas included, and through a list of values it heads (`the 6.1 mm and 5.0 mm values above are incorrect`, `6.1 mm (SFJ) and 5.0 mm (knee) … in error`, `6.1 mm, 5.0 mm above are wrong` — round 14; a few words between the values too, `the SFJ 6.1 mm and knee 5.0 mm values`, `6.1 mm at the SFJ and 5.0 mm at the knee above were dictated in error`, `6.1 mm / 5.0 mm above are wrong` — round 15) (`disregard`, `superseded`, `erroneously`, `incorrect`, `wrong`, `error`, `misdictated` …; not `prior` or `previously` after it, `… 6.1 mm, unchanged from the prior exam`: inclusion lists that only ever hold) — with or without a correction word (`…, not 6.1 mm as originally dictated`, `… 6.1 mm is incorrect; …`, `… 6.1 mm was reported in error`, `Please disregard the prior right SFJ diameter of 6.1 mm; …`, `… corrected to 7.6 mm (previously 6.1 mm)`, `the 6.1 mm right SFJ diameter above should be disregarded`, `… 6.1 mm dictated previously is superseded`, `… of 6.1 mm, as previously reported, is incorrect; …`). `concerns`: its value or words, a side for a one-sided question, a quantity of its unit (or a bare number, or none) for a measurement, and for anything else everything except a correction stating only a measurement (`Correction: it measures 7.6 mm there.`) of a symptom or history — never of this examination's findings (`… without evidence of … insufficiency. Correction: reflux of 1.5 seconds in the common femoral vein.`) — and a side it names never releases it. What a written correction corrects TO ends at the first clause break after its first number, or its sentence's end, and in a run-on sentence after 40 words. At most eight governing lines are kept | held |
| otherwise | supported (pre-filled; the clinician still reviews every answer) |

**Rows** (round 17). A measurement question of the form's table names its row in its label (`Right GSV at the SFJ:
diameter (mm)`, `Left tributary row 25: reflux time (ms)`): a vein, and a level except on a tributary row
(`field_row`, read as `field_side` reads the side; no stored mapping changes). Each place a value is written is read for
its row, per sentence, as ITEMS left to right (`_rows_of_sentence`): a vein or a level opens an item and the values
after it are its own until another opens (`GSV SFJ 6.8 mm with 1.2 s reflux, proximal thigh 6.1 mm …`); a level written
right after a value (after a preposition, a reflux phrase or a side: `6.8 mm at the SFJ`, `2.1 seconds of reflux at
the saphenofemoral junction`, `5.0 mm on the left at the SFJ`) is its item's where the item has none, and where it has
one it opens the next item when a value follows it (`… 1.9 seconds at the knee it's 4.8 millimeters`, `… 1950
milliseconds in the proximal thigh 5.1 millimeters`) and is otherwise a second reading; a vein written right after a
value is the value's (`reflux of 1.6 seconds is seen in the great saphenous vein at the proximal thigh`). A second value
of one unit in an item opens an item with no level — unless it corrects the first (`6.1 mm at the SFJ, correction: 7.6
mm`, `6.1 mm should read 7.6 mm`, `7.6 mm rather than 6.1 mm`), or a side written between them or right after it makes
it the other leg's parallel (`4.2 mm and the left 4.0 mm at the SFJ`, `7.4 mm at the SFJ, compared with 5.0 mm on the
left`), which shares its level either way. A junction places its vein where the item names none (the saphenopopliteal
is the small saphenous vein's: `At the saphenopopliteal junction it measures 3.0 mm` after a sentence about the great
saphenous vein; the saphenofemoral the great saphenous vein's unless an accessory is read there), a trunk's level with
no vein written anywhere is that trunk's (`Proximal thigh: right 6.2 mm`), a region with one row of the vein is that row
(`GSV thigh 5.9 mm`), a worksheet's abbreviation right after its vein is its row (`R GSV PT 6.8 mm`, `GSV K`), a
correction sentence with no row of its own takes the row of the value it corrects (`… 6.1 mm at the saphenofemoral
junction. Correction: it measures 7.6 mm.`), and a line's own label names the row of a value after its `;` where no
value of that unit stands between (`Right GSV at the SFJ: reflux absent; 6.1 mm diameter.`). A vein named only in an
insertion that holds no value of its own — a relative clause, an apposition, a bracket (`the great saphenous vein, which
receives the anterior accessory saphenous vein, measures 6.8 mm`, `…, not the AAGSV, …`, `(not the AAGSV)`) — is never
the item's, and is not counted as named before it; one that holds a value is read as usual (`…, which is larger than the
AAGSV at 5.1 mm`). A sentence runs over its hard-wrapped lines, as the side does, and a number the wrap put before its
unit's line (`… it measures 6.9` / `mm without reflux.`) is one quantity (the shared quantity pattern reads one line
break between them, in the parent and the engine alike) in one unit (the narrative units join the two lines; the
labelled and tab contracts' units are unchanged). The pre-fill needs a place read for the row (and then its side is read from that
place only); review refuses only a value every place of which is another row's and whose sentence names the row's vein
and level nowhere before it — a refusal is final, so anything less certain is the clinician's. Named before it means since the value
before it — in its own item or an insertion — not anywhere earlier in its sentence: in a run-on transcript every
earlier item's vein and level were, each contradiction was relaxed, and review took any row's value for any row named
before it (round 17c's review: 1,355 wrong-row offers accepted in the row mirror's transcripts). An item whose level
came right after the value before it keeps the whole sentence's (`… reflux of 1.9 seconds at the knee it's 4.8
millimeters`: that level may be the other value's, and the value then has none — held for the junction, never
refused). The same reading serves
generation, the page, the save, review and finalization (`side_verdict`, which every one of them calls).

**Sides.** Read from the text over a whole-text index (a search cut inside a word would read `both` in `bothersome`);
lines and paragraphs split at every break `str.splitlines` reads, as units do (U+2028, VT, FF, NEL, U+2029, FS, CR;
`\r\n` is one break, so a browser's line is no blank line), and a line of characters that show nothing (a no-break or
zero-width space, U+3000: generation's `blanks()`) is blank; a note with an invisible character in the text of a line
that shows anything — any character `blanks()` removes from a reading: every format character and other
default-ignorable code point (a soft hyphen, zero-width spaces and joiners, bidirectional marks, embeddings and
isolates, variation selectors, the combining grapheme joiner, fillers, tags, U+FFF9..FFFB, U+13430..), every control
character that is not whitespace (DEL, ESC, the C1 controls) and the blank braille cell — inside a word or beside one
(U+00AD inside `sorry`, `left`, `mother`; U+202A inside `left`; U+200B after `… asymptomatic.`; DEL inside `sorry`) —
holds every pre-fill, since it can hide a correction, a side or a relative from the reader's words and the engine's
alike, or leave a sentence reading as an unstopped heading (round 14: the round-13 list missed most of them; round 15:
the hold's own list again missed DEL, ESC and U+FFF9, which the parent's reading already removes — `sor`+DEL+`ry`
pre-filled the value it corrects, and `le`+DEL+`ft` the other leg's). A break
inside a sentence — this line ending in a word no sentence ends in (`was`, `than`, `the` …), standing alone (not the
tail of `N/A` or `and/or` — round 15: `Left leg: N/A` ended in the article `a`, joined the value's line into the left's
label and pre-filled the left, round 14 too), or the next opening with a
small letter or a value (`… measures` / `7.6 millimeters …`; not a list's number, `2. Left …`) after a line that may not
be a heading (not capitals, markup, a closing dash, a section's words, a limb's label with no colon, `Right leg` —
unless the next line denies its examination, `Right leg` / `not examined.`; a line opening with a preposition is no
limb's label, `in the left leg.` — nor a short unstopped line that may head a section, `Other`, `Also noted`, `Update
09/25/2026`), never after a stop, a colon or a blank line, and never into a line that may be a heading (`Reflux: no` /
`IMPRESSION`) unless it opens with a small letter and ends its sentence (`… without reflux` / `left leg.` — round 14:
the sentence's own side phrase was read as the next heading, and the value took the side before) and no lowercase line
or row writing a number follows it — then it heads what follows (`gsv knee 5.2 mm, reflux 1.1 s` / `left leg.` / `gsv
sfj 5.0 mm, no reflux`, `GSV at the SFJ 7.4 mm reflux 1.8 s` / `left leg.` / `GSV at the SFJ 5.0 mm …` — round 15:
joined, the other leg's heading made every row of the run above it either leg's; round 16: a row is a number with no
closing stop and no verb, and never after a line breaking mid-sentence — `… without reflux in the` / `left leg.` / `The
great saphenous vein measures 5.0 mm …` and `Dictated 09/25/2026.` split a sentence from its tail) — is a hard wrap
(and a line ending a sentence in its middle is no heading: `Symptoms are in the right leg. The left` / `leg is
asymptomatic.` — round 16): the
lines it joins are read as one sentence (`the left leg was` / `not imaged.`, `larger than` / `the left.`, `Flow … is` /
`reversed for 1.8 seconds.`; not `IMPRESSION` / `great saphenous vein reflux positive.`), and a line wrapped into the
next is never a heading. A sentence begins where its wrapped lines do, read at most 1,200 characters back from its unit
from the first line starting within them (a wrapped transcript's `right leg …` three lines up reads its value; round
14's cost lens: read from the start of a long run for every unit, 92 s; round 15's: from the start of the line holding
the limit, a 45,000-character first line was read whole for every place, 46 s), its context read from that beginning,
and ends with the cited unit — or, where the next cited units carry the sentence on, each across one line break, with
the last of them (`The great saphenous vein measures 6.1 mm at the` / `saphenofemoral junction with 2.1 seconds of
reflux in` / `the left leg.`, all cited, is read as its unwrapped note is; round 17c: read in the value's line alone,
review refused 1,209 of the wrapped mirror's answers with their whole sentence cited, the left leg's value as the
right's, and accepted it on the right's row; a line not cited, or one after a blank line, is still not read:
`cited_sentence`), within the value's block — never into a later cited line that opens a block of its own (a heading, a
limb's label, a label before a colon: `SSV SPJ 3.9 mm, no reflux` / `Left lower extremity: Deep veins normal.`, both
cited, read the left for a value of the right's block — round 17c's own review) unless the wrap joins it to the line
above (`… reflux in the` / `right leg.`), nor back past the line opening the value's — as the engine reads it. Only the
cited text carries a side to acceptance; the value's whole sentence, cited or not, can still refuse it
(`own_sentence_other_side`) and govern it (`whole_sentence_entries`). A side word of the sentence further back, with none within the
reach, is read once where it stands: the value is only held, that word's reading its candidates — the paragraph's too
where that reading is no side (round 15: `… now moving to the left leg the deep veins are compressible` / 18 lines / `…
5.1 millimeters` was read by neither the place nor its context, and the paragraph's right was pre-filled); the
pre-fill of such a value is lost, and review accepts that word's side. A sentence's denial is read over the sentence joined across its wrap, over the side's own clause in it, and — where
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
common femoral vein. The great saphenous vein measures …` on one line was the left's) — in a system's list to the end
of its line too where the paragraph has lines opening with both legs' labels, or nothing before it names another leg,
and no side heading above the paragraph names another (round 16: the both-legs case only where nothing BEFORE the
paragraph names another leg — `Exam: right lower extremity …` / `Right: …` / `Left: No DVT in the common femoral vein. The
great saphenous vein measures 7.2 mm …` was the left's) (`DEEP VENOUS SYSTEM: No DVT.` / `Right: …` / `Left: …` /
`SUPERFICIAL VENOUS SYSTEM: …` / `Right: GSV SFJ 7.1 mm, reflux 2.2 s. GSV knee 5.0 mm, reflux 1.0 s.` — round 15;
not under `RIGHT LOWER EXTREMITY VENOUS DUPLEX`, nor after `Exam: right lower extremity venous duplex.`); a LIMB's
label opening its line
(a leg, limb or extremity named, `RIGHT LOWER EXTREMITY:`, `Right leg:`) heads its leg's block, the system's and veins'
sub-headings under it with it (`FINDINGS:` / `RIGHT LOWER EXTREMITY: Deep veins patent and compressible.` / `Superficial
venous system:` / …, `Right leg: No DVT.` / `Great saphenous vein:` / … / `Left leg: No DVT.` / … — round 14: round 13
held these), unless the line above is the other leg's label, a list of both legs' labels (`Right leg: No DVT.` / `Left
leg: No DVT.` / …, round 12: a candidate) — and only a label over findings (`Left leg: to be scanned next week.`, `Left
leg: exam deferred.` head nothing), where every leg named before it in its paragraph was named by such a label opening
its line (`RIGHT LEG:` / … / `Left leg: No DVT in the common femoral vein.` / … is the other leg's check inside the
right's block, and heads nothing — round 15: round 14 released both; round 16: over a finding line's words, not any
finding word — `Left leg: patient declined; prior DVT.`, `…: DVT ruled out in 2019.`, `…: normal per outside report.`
headed the block — and only where nothing before the paragraph names another leg, a one-leg study's title or exam line;
the line above is a list's item only where its own item writes no value, since a label over its leg's values is that
leg's block — `RLE: … GSV SFJ 7.8 mm …` / `LLE: … SSV` / `SPJ 3.0 mm …`); a bare side's label or a vein's (`Left: No DVT in
the common femoral vein.`,
`Left CFV: …`) heads nothing after its item where the paragraph named a leg before it (not one only said to be
unexamined, `The right leg was not examined.` / `Left leg: …`), where the paragraph opens with a system's or a vein's
heading or label naming no side (a list of that system's items, with or without a finding after its colon: `DEEP VENOUS
SYSTEM:`, `DEEP VENOUS SYSTEM: No DVT.`, `Deep veins: compressible …` / `Left: No DVT in the common femoral vein.`, the
other leg's common femoral vein checked in a one-leg study; a limb's heading, `RIGHT LOWER EXTREMITY:`, is none), or
past a heading line, an anatomy sub-heading with no colon (`Great saphenous vein`, `Superficial venous system` —
round 15) or a line opening with an anatomical label naming no side, the value's own line included (`FINDINGS:` /
`Left: No DVT …` / `SUPERFICIAL VENOUS SYSTEM:` / …, `Superficial venous system: The great saphenous vein measures …`)
— but not a vein's value row, its label followed by a number (`GSV SFJ: 7.4 mm, reflux 2.1 s`), where the paragraph
has lines opening with both legs' labels over findings and nothing before the paragraph names another leg (`Venous
duplex` / `Right: No DVT.` / `GSV SFJ: 7.4 mm, …` / `Left: No DVT.` / … — round 15: round 14 held every row; round 16:
`RIGHT LOWER EXTREMITY VENOUS DUPLEX` / `FINDINGS:` / `Left: No DVT in the common femoral vein.` / rows / `Right: …` read
the rows as the left's; `RIGHT LOWER EXTREMITY VENOUS DUPLEX` / `FINDINGS:` / `Left:
No DVT in the common femoral vein.` / `GSV SFJ: 7.2 mm …` still is): its leg is then a candidate beside any the paragraph named before it and the side heading above the
paragraph (`DEEP VENOUS SYSTEM:` / `Right: No DVT.` / `Left: No DVT in the common femoral vein.`, `RIGHT LOWER
EXTREMITY:` / … / `Left: No DVT in the common femoral vein.`, a sentence or a line between, one leg twice); otherwise it
heads its block (`FINDINGS:` / `RIGHT LOWER EXTREMITY: No DVT.` / `The great saphenous vein measures …`, as a label
opening its paragraph does); a label with nothing after it heads its block (`RIGHT GSV:`); a leg a sentence of its own
only mentions — writing no value of it, no limb label or heading of its block — inside another leg's block lends a later
sentence only a reading beside that leg (`RIGHT LEG:` / … / `Left leg to be scanned next week.`, `She had left GSV
ablation in 2019.`, `Left leg exam deferred.`, `The contralateral left common femoral vein is patent …` / `GSV at the
knee 5.1 mm.` — round 14; and with the value's sentence on its line, `Left leg asymptomatic. GSV at the knee 5.1 mm.` —
round 15: its full stop was read without the space after it and missed; or ending at its line with no stop, `… reflux
2.0 s. Left leg N/A` / `GSV at the knee 5.1 mm.`, never at a `;`; not `Left leg.`, a spoken heading, nor a
sentence of the leg's own words and filler alone, a dictated leg change — `Now the left leg.`, `Next, the left leg.`,
`On the left.`, `Left leg now.`, round 15; not `Turning to the left.`, which may be the patient's position, nor `Moving
on to the left leg.`; the leg's own words are side, limb and filler, not anatomy — round 16: `Varicosities in the left
leg.`, `Reflux on the left.` read as leg changes, and the left was pre-filled — nor a leg in the value's own sentence
before a `;`; and a line is the leg's heading only when it says nothing but the leg's words, anatomy that is no finding,
an examination's word or a report's, and does not go on a sentence from the line above — round 16: `Left leg N/A`,
`Left leg declined`, `LEFT LEG N/A` headed the next value, and `… a prior ablation in the` / `left leg.` did too); a weak
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
the sentence speaks of the other leg without naming it — `the other`, `other`, `opposite` or `contralateral` with a
limb, a vein, a site or `one` (`the other knee`, `The opposite SFJ`, `the opposite one`, `the other GSV`; not `the other
veins`), or `contralateral(ly)` ending its clause, `on the other` (not `on the other hand`), `other` before a limb, and
`the unaffected` or `asymptomatic` leg (round 15; round 16: a bare `opposite` or `other` before anything refused sides
written plainly — `flow in the opposite direction`, `opposite wall`, `any other great saphenous vein segment` — so
`opposite` needs a leg, a vein or a site again) — in the value's own clause when its sentence names a side (`The right GSV measures 7.4 mm
…, and the opposite GSV measures 5.0 mm …`), in its sentence when the side would come from around it (`RIGHT LOWER
EXTREMITY:` / `The opposite great saphenous vein measures 5.0 mm …`) — with no candidate, since no leg is written, and
no cited unit's side stands in for one at review (round 14: the side around it was offered at review, and it is the
wrong one; round 15: a cited heading was); unless a comparison after the value introduces that phrase, which is then the
compared thing (`The right great saphenous vein measures 7.4 mm at the saphenofemoral junction compared with the
contralateral side.`, `… 7.7 mm … compared with 5.1 mm in the other leg` for 7.7; under `RIGHT LEG:` too — round 15:
the value's own written side was refused); a value a comparison introduces on the other leg (`… versus 5.0 mm on the
other side.` for 5.0; past a comma too, `vs 5.0 mm, other leg.`, `…, compared with 5.0 mm, contralaterally.` — round
16) has no side written either (round 15: the side before the comparison, the other value's, was
accepted at review, and the other leg refused); when a weak side form is in its clause, when a side a comparison introduces in another clause
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
never a primary reading: a bracketed letter after a word that is neither anatomy, a unit nor a finding's word (`GSV SFJ
5.1 mm, no reflux (L)`, `competent (L)` are the side — round 15: weak there, and outside the value's clause no
candidate, it left the line above's `(R)` to pre-fill the right) and before nothing that places it — a colon, a measurement or anatomy (`ClosureFast (R) in 2019`, `ClosureFast (R) 2 years ago`; `(R) GSV`, `SSV
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
included in this study …`) or withholds it (`we could not image the left leg`, `we did not examine the left leg`,
`unable to scan the left leg due to a cast`, `left leg deferred`, `the left leg will be done next week`, `we are
skipping the left leg today` — round 15, and a leg named earlier in the sentence is then a candidate too) — unless the
context reads the same leg, nor where that clause names the other leg too
(`right leg she had the left leg treated in 2021 and today the great saphenous vein … 7.2 millimeters`; not a side a
correction struck, nor an earlier clause's scope, `… right leg detailed left leg screening … on the right the common
femoral …`), nor where that clause is an earlier one only mentioning its leg — writing no quantity, no label (a colon
ends it: `Left previous treatment: outcome: …`), the leg itself named (not a vein of it, `2. Competent left great
saphenous vein, 5.0 mm …`) and more than the leg's own words and filler (not `…, and on the left, the great saphenous
vein …`) — or, round 16, a vein of it with a finite verb (`She had left GSV ablation in 2019 and today …`) — where the
sentence before it or the reading around it names the other leg (`Right leg. Deep veins compress normally. She had the
left leg treated in 2021 and today the great saphenous vein at the knee measures 5.1 millimeters.` — round 15, as a
sentence's mention is read; round 16: not the whole paragraph's legs, which made `Left leg: No DVT. The left leg is less
symptomatic, and the GSV measures 5.2 mm …` either leg's and review accepted the right; an unpunctuated run in one clause, `… no clot the left leg
was done in 2021 by doctor synthetic the great saphenous vein …`, is not caught — *Known limits*); a sentence pairing values and legs `respectively` reads both ways; and a side written after the value on
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

**The technique wording is its answers'** (round 17, `threshold_wording`). Claim 19's two wordings differ by one
sentence — `This study documents reflux as lasting more than 500 milliseconds in either the saphenous veins or the
perforator veins.` — and the careful response chose the wording without it on ten notes documenting saphenous reflux well past
500 ms (1.5–2.4 seconds at most). The pair's choice is the reflux answers': the wording stating the threshold where a pre-filled saphenous
reflux time is past it (that answer's sentences join the evidence), the one without it where none is past it and none
is held; where only a HELD answer is past it (`possible reflux of approximately 550 ms … may be artifact`, a value
written twice), or the model chose the wording stating it and no answer does (the form has no perforator row to read),
nothing is pre-selected and the page says why (`data-statement-held`). The pair is found by the variants' own text, so a
mapping whose wording differs keeps the model's proposal as before.

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

**Who gave an answer (round 17e's review).** Generation writes `supported`, and only an answer generation wrote on its
own evidence stays so: an answer the clinician (or anyone) types, chooses from a held candidate, or cites to other
sentences is stored `edited` with `edited_by` — whoever made that change, carried forward until someone changes it
again — and `reviewed_by` is only who ticked its review. The page names the author beside every `edited` answer
("entered by …, not read from the notes") and shows the reader's qualifiers ("Read from the notes as: …") only beside a
`supported` one; its badge is the review's (`conflict` until reviewed). Finalization's recheck (`held_now`) holds on
the stored evidence everything generation's `decide` holds besides `governing` — someone else's finding, a planned
treatment — so an answer whose evidence came to be `Her mother has a leg ulcer.` is refused, never finalized as
supported; an `edited` answer is the clinician's decision and is not rechecked. A generation request over answers or
statement wordings a clinician has reviewed or decided is refused (the focused pass: statement reviews alone were replaced
by a second, billed draft) (the page offers generation only before any answer exists; a new draft
follows a source edit, which clears the answers); an employee's save keeps generation's statement proposals for the
clinician's page (pre-selections still to be reviewed and ticked); a finalized record is not re-reviewed by whoever
views it. Where one posted line is written under both legs with the side only on the line after it, the save keeps
the copy that runs straight on to the clinician's next (or previous) posted line. Reproduced before repair: `7.4 mm`
re-cited to the mother's sentence stayed `supported` through finalization and export; an employee's choice of leg read
as the reviewing clinician's; a held statement proposal (`{'held': …}`) raised on the first page for every owner and
clinician.

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
- **Scores as they stand (round 17, `wm_narrative_benchmark.run`), every category the scorer counts.** An ANSWER is
  scored against the case's expected outcome — a value (`supported`), blank (`missing`) or the clinician's decision
  (`decision`); `wrong_supported` counts every pre-filled answer that is not the expected value, a pre-fill where a
  decision or a blank was expected included. A STATEMENT is scored by the variant the proposal pre-selects; one not
  pre-selected (`{'held': reason}`) counts as missed.
  | set | answers pre-filled correct | wrong pre-filled | unnecessary holds | other | statements correct / wrong / missed |
  |---|---|---|---|---|---|
  | frozen, careful (the gate) | **338** | **0** | **0** | 7 correct holds; 6 decisions shown as missing (C18) | 161 / **0** / 2 |
  | frozen, weak (injected model errors) | 330 | **0** | 0 | 7 correct holds; 6 decisions shown as missing; 3 missed; 12 held where a blank was expected; 5 held with the wrong value | 157 / **0** / 6 |
  | held-out, careful (a regression set now) | **254** | **0** | **17** | 14 correct holds; 6 decisions shown as missing | 83 / **0** / 10 |
  (Round 16: careful statements 153 / 10 / 0; weak 11 wrong, 2 of them wrong values; held-out 2 wrong answers and 2
  wrong statements. Round 17's first pass left the weak set 9 wrong answers and 2 wrong statements; each was then read
  for what its evidence shows — two values and one option the notes contradict (`row_rivals`, `option_rivals`), two
  hedged, two resting on nothing clinical, two denied (`choice_evidence_reason`) — and every one was detectable, so
  each is now held, and the two statements built from them are not proposed.) The careful gate is `wrong_supported 0, unnecessary_hold 0, correct_supported ≥ 338`
  (`CAREFUL_GATE`), and it passes. What remains, named: the careful set's 2 statements not pre-selected are claim 19 on
  C16 (reflux of 900 ms and 2.1 s for one row, held as a conflict) and C17 (`possible reflux of approximately 550 ms …
  may be artifact`, held), each shown with its reason; the weak set has no wrong answer left (its 2 wrong values,
  another row's, are held with the wrong value; its 9 other errors are held for what their evidence shows); the
  held-out set's H06 answers are held (`overstated`, `wording`) and claims 30 and 31 are no longer proposed; its 17
  unnecessary holds are H12's 8 unitless shorthand values (`6.8/1.9s`, held by design) and 9 pre-fill holds in H02 (3),
  H03 (1), H05 (3) and H11 (2) that review accepts, unchanged since round 3. Every held-out case has now been read
  while repairing, so it measures regressions, not generalisation.
- **Held-out benchmark** (`heldout-cases.json`, `3af6e471`; blind careful responses `d92cc499`): 12 cases written after
  the implementation by an author who did not read it — headed reports, raw transcripts, shorthand, a letter, a SOAP
  note. Scored on the implementation as it stood: 201 correct, **0 wrong**, **70 unnecessary holds**. After the first
  refutation round's repairs: 253 correct, 2 wrong (choices whose only option overstates the note), 18 unnecessary
  holds; after the second round's: 256 correct, the same 2 wrong, 15 unnecessary holds; after the third round's: **254
  correct, the same 2 wrong, 17 unnecessary holds** (8 are unitless shorthand, `6.8/1.9s`, held by design; most of the
  rest are pre-fill holds the clinician clears at review), 83 statement proposals correct; the same after the fourth to
  sixteenth rounds'. Round 3 closed fourteen classes of wrong pre-fill that round 2's releases had opened; the price is
  two pre-fills that now read both ways. The repairs were checked against this set, so it is now a development set too.
- **Refutation.** Sixteen rounds of sealed, write-disabled lenses over the finished diff (four each; three in round 16's
  focused pass) (false green, false
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
  Round 15 found round 14's releases wrong again and older gaps under them. False green (lens 1: 7 HIGH, 2 MEDIUM; lens
  2: 4 HIGH; lens 3: 2 HIGH, through the real engine): a limb's label over no finding (`Left leg: to be scanned next
  week.`), or inside another leg's block, heading the rest of it; the list guard defeated by a hard wrap; a side word
  more than 1,200 characters back in its own wrapped sentence read by nothing, so the paragraph's other leg was
  pre-filled (and read differently under `\r\n` and trailing spaces); `contralaterally`, `opposite`, `on the other`, the
  unaffected leg not read as the other leg; old values listed with words between them; examinations withheld in words
  the reader had not (`could not image`, `deferred`, `will be done`); a bare label heading past an unstopped
  sub-heading; a mention's full stop missed when the value's sentence shared its line; a bracketed `(L)` after a
  finding's word read as a brand's; a clause of the value's own sentence mentioning the other leg; control and format
  characters the hidden hold did not list (`sor`+DEL+`ry`); `N/A` read as ending in the article `a` (found writing a
  mutation row; round 14 too). The integrity lens also found the mention memo keyed by sentence alone (a reading
  depended on what was read first) and the statement copy choice still asking the note-wide hidden hold; and
  review accepted `… versus 5.0 mm on the other side` as the right's through a cited unit's side (found in triage,
  round 14 too). False rejection (lens 2's new battery of 43 notes, 213 correct answers: round 13 126, round 14 108, now
  117; its 300 generated reports, 2,115 answers: round 13 1,133, round 14 994 with 50 reviews blocked, now 1,175 with
  none blocked): the other leg in the value's own clause refusing its written side (`… compared with the contralateral
  side`); a measurement's labelled line with a remark on another finding (`diameter (mm): 7.4 mm, reflux: none`);
  vein value rows under both legs' labels, a lowercase stopped heading over rows, a system's list whose second
  sentence was held, dictated leg changes — each restored; realistic pastes with invisible characters stay held
  (0 of 11), as documented. Round 12's battery 238/270, battery 3 101/132, battery 4 143/212 and the round-13
  generated reports 2,216/2,272 are unchanged row for row, the same with CRLF, review completing for all. Cost (lens
  4: 4 HIGH): see *Cost* — a sentence label's pattern backtracked cubically on a run of spaces. Every case is pinned
  (`ROUND_15`, 161 rows; 131 failed on the round-14 commit, the rest controls, correct-answer rows and mutation rows the old code
  already read), with the order, save, pattern, hidden-hold and cost tests (each failed or errored there). Of 48 mutants over round 15's rules, 43 were killed at once; the four survivors each got the row or test
  their rule exists for (a limb label over no finding under a sibling — only examination-withholding words had been
  pinned, which another rule holds anyway; a label's clause naming its leg; a system's prose ending the first label's
  block; the reach's line start, which the cost test did not reach: it cited the lines past the long one, 1.7 s with the
  snap, and now cites those within its reach, 5.5 s per validation) and are killed; one — the label pattern restored —
  ran past 55 minutes of CPU on the module's own space-run shapes (the unmutated module takes about two minutes) and
  is recorded as killed by its deadline, not by an assertion. The batch runs each mutant under a deadline and restores
  every file in a `finally`; every restoration was verified by sha256 and the unmutated module passes.
  Round 16 — a FOCUSED pass over round 15's diff (three sealed lenses) — found round 15's releases and holds wrong
  again, and older edges under them; every finding was reproduced before it was repaired. False green (lens 1: 11
  HIGH, 1 MEDIUM, through the real engine; lens 2: 2 HIGH): a finding on the other leg read as a dictated leg change
  (`Varicosities in the left leg.`, `Reflux on the left.`); a list of both legs' lines or labels releasing under a
  one-leg study's exam line or title; a remark on the leg read as its heading (`Left leg N/A`, `Left leg declined`); a
  sibling label over a prior or declined finding; the acceptance rule's `underwent`, a comma and `per the outside
  study`; a compared value's other leg past a comma; a sentence's tail across a wrap read apart (`… in the` / `left
  leg.`, `and/or` / `left leg.`, and — lens 2 — `Dictated 09/25/2026.` under it); `She had left GSV ablation in 2019 and
  today …`; a remark calling the value unreliable carried (`(not reliable due to thrombus)`); a demographic's `typo`;
  a stray `The left` read as a heading (since round 13). Review regressions (lens 2): the clause rule read the whole
  paragraph's legs, so review accepted the wrong leg; a list's line above over its own leg's values made a list. False
  rejection (lens 2): a bare `opposite` or `other` refused sides written plainly (86 of 160 answers in that style); the
  acceptance rule held present-tense leg states (9 of 11). Cost (lens 3): the compared-other-leg check per place (the
  page 146 s at 13,000 characters), a leg's predicate re-reading a run of spaces per place (26 s), a label's findings
  per context reading (23 s). Every one is pinned (`ROUND_16`, with its right-leg review where it applies) with a cost
  test; the benchmarks and every saved battery are unchanged row for row, lens 2's round-15 battery 117 of 213 and
  generated reports 1,175 of 2,115 unchanged. Lens 2's generator hard-wrapped at 17 widths (16,655 answers, each also
  mirrored onto the other leg's row): pre-filled 9,055 → 10,549, refused at review 3,591 → 2,480, and wrong-leg
  pre-fills 105 → 80 — the 41 whose value is written once gone, every one left a value the other leg also writes, for
  another row (*Which row*, a known limit). Of 23 mutants over round 16's rules, 20 were killed at once; two had been written without the
  marker the harness asserts, so they never ran — the harness reported them unapplied — and, re-marked, both are killed;
  one, a per-note memo of a leg's predicate, was measured as not needed at the note limit (1.76 s against 1.35 s: the
  possessive runs carry it) and removed. Every restoration verified by sha256; the unmutated module passes.
  Round 17 (rows, option scope, the technique wording; the known wrong pre-fills): lens 2's wrapped generator (16,655
  answers, each mirrored onto the other leg's row) — wrong-leg pre-fills 80 → 0; correct pre-fills 10,549 → 11,427 and
  refused at review 2,480 → 1,209 once a number the wrap puts before its unit's line is read as one quantity in one unit
  (965 gained on round 16, none newly refused; 87 lost to round 6's side-after-the-value hold, which the unwrapped
  notes already had — *Known limits*). Every battery pre-fills nothing it did not, and holds
  11 more (`row_unknown`): 9 small saphenous diameters written with no level, which the form's two SSV rows could each
  take, and 2 `mid thigh` values, which no row is (round 12's battery 237/270, battery 3 100/132, battery 4 140/212,
  lens 2's round-15 battery 111/213; the generated 2,216/2,272 and gen2 1,175/2,115 unchanged). 32 mutants over round
  17's rules, run with the unmutated module FIRST (a first batch ran it last, and it failed: every one of its 30 "kills"
  had stopped at that failure, so none counted — the harness now aborts on a failing baseline and names the test that
  kills each mutant): 29 killed at once; two survived for want of a test (the review refusal kept for a row named
  before the value; a denied finding stating veins) and one was killed only by a time limit (any word joining a vein
  to its finding) — each now killed by a test of its own; one, the deep-vein list walked per finding over every vein,
  is quadratic but 1.57 s at the note limit (0.48 s at half), measured as not material, and the bisection kept. Every
  restoration verified by sha256; the unmutated module passes.
  Round 17c (insertions, wrapped values, the weak set's evidence, rivals, the cited wrapped sentence): the benchmarks
  as above (weak 0 wrong answers, 0 wrong statements; careful and held-out unchanged). The wrapped mirror, once a
  cited hard-wrapped sentence is read over its cited lines: pre-filled 11,427 → 13,531 (2,445 gained, 341 now held as
  their unwrapped notes are — a side after the value, *Known limits*), refused at review 1,209 → 17 and none newly
  refused (the 17 are one answer at 17 widths whose citation the generator maps to the other leg's copy of a sentence
  both legs write word for word — a refusal that is right), wrong-leg pre-fills 0, the other leg's value accepted at
  review 11,932 → 11,525 (**corrected by round 17d: those two figures counted every mirror the generator never
  evaluated — the other leg's row already had an answer of its own — as accepted; over the 5,795 it did evaluate, 1,072
  → 665**). Batteries: battery 3 100 → 102 and lens 2's round-15 battery 111 → 112 (the side a cited line of the
  value's sentence names — **round 17d: battery 3's two were read across a heading, and went back to held**), gen2
  1,175 → 1,191; the rest unchanged. The bound, cited-sentence rival and cost changes moved no answer of any of these. Mutation
  proofs, the unmutated module FIRST: 14 mutants over the bound, cited-sentence and index rules, all killed (a first
  batch stopped at its baseline, which a pinned row the new rival rule had legitimately changed failed — no kill was
  counted); and 3 over the cited wrapped sentence (read in the value's line only; every line of the notes' sentence read, cited or not — killed by round 17's other-row refusal; a blank line joining), all killed. Each refactor was also compared against the old reader on 28,000-30,000 random inputs: 0 differences
  (planted controls: 267-673).
  Round 17d (the independent review's acceptance questions, answered on the round-17c candidate `3b943982` by the
  author while the review itself was blocked — not independent): **(1) rows.** A row mirror offered each generated value,
  with its own citation, to every other named row of its leg and column (34,466 offers, unwrapped and at four widths):
  0 wrong-row pre-fills on `3b943982` and now; review accepted 2,315, since a vein and level named anywhere earlier in a
  run-on sentence relaxed every contradiction — now 359, all one generator style (a vein carried from a sub-heading,
  offered to the accessory's row at the same level: the clinician's, *Known limits*). **(2) Review.** A clinician's own
  answer is stored `edited`, generation's `supported`, and the page badge shows which; review never records the other
  leg's value as `supported`. Of 5,795 mirrored answers evaluated, 0 are pre-filled on the wrong leg and 580 are
  accepted at review as the clinician's choice (561 letters whose sentence compares the legs, `The left leg is more
  swollen, and the great saphenous vein measures …`; transcripts with a side after the value, `… measures 5.1
  millimeters on the right leg there is no reflux …`, or the same value on both legs; 2 labelled). **(3) Uncited lines.**
  A relative, a denial, a plan, a hedge and a prior study on the uncited part of the value's own wrapped sentence all
  pre-filled; each now holds (`whole_sentence_entries`, `measurement_context`), and review refuses the other leg where
  the uncited rest of the sentence names it (`own_sentence_other_side`). `3b943982`'s own cited-sentence rule was wrong
  twice and is repaired: it read across worksheet rows into the next block's label (review accepted the left for a
  value of the right's block), and, bounded by the reader's wrapped-line run instead, it lost transcripts whose lines
  the reader takes for headings. **(4) The 17 harness refusals.** The generator's citation mapping takes the first unit
  a needle's text matches; four picks in two notes name a sentence both legs write word for word, and for the left
  leg's two the first copy is the right leg's. The original results are kept (`g16-r34`); replayed with an
  order-aware mapping (the first copy after the previous needle's unit), the left SSV of `G096 letter` is pre-filled at
  16 of 18 variants (2 held by the bare-negative rule on `The left leg is asymptomatic,`) and accepted at review at all
  18, and `G097 labelled`'s is pre-filled and accepted; with the original mapping both are refused — right for the copy
  cited, and `G097`'s had been ACCEPTED on `3b943982` (the next block's label read into the cited sentence), the
  review defect repaired above. Benchmarks unchanged in every category; batteries as round 17c's less battery 3's two;
  the wrapped mirror 13,531 pre-filled and 17 refused as round 17c; cost at or below round 17c's on every ReviewCost
  shape once the new readers index their spans and each cited sentence's reach is read once per citation (the round-16
  and round-14 shapes had passed their limits: 7.0 s on the latter). Mutation proofs, the unmutated module first: 15 mutants over these rules,
  all killed — two only after a test was added for the shape they changed (a comparison in the value's own clause; a
  vein bound after one value, then another value). Each new test was shown to fail without its repair (on the
  earlier reader, or on the mutant that reverts it).
  Round 17e (the three source-context gaps d3733330 left, each reproduced first): a label line's denial split onto the
  next line (`Clinical indication: she denies` / `leg pain and swelling.`) and, found by the same reproduction, a list
  under a denial verb (`She denies leg pain and swelling.`) pre-filled `Leg pain`/`Swelling`; a hedge after a measurement
  (`6.1 mm, possibly artifact`) and a year dating it (`9.6 mm in 2023`) pre-filled it as today's definite value, and the
  live 2023 value held today's (`6.1 mm …, compared with 9.6 mm in 2023`) as a conflict. All five now hold, and today's
  value compared with a dated one stands. The first cut over-held six benchmark answers (C02, C06, C12, H11: a bare
  `no`/`without` read across a list) and two battery answers (B24, B37: a year that was a treatment's or a comparison's),
  and three pinned rows (R13T, R15T, a tag question) — each narrowed before commit. Benchmarks, batteries, the wrapped
  mirror and the row mirror are identical to d3733330; ReviewCost 32/32. Mutation proofs: 17 mutants, 13 killed at once,
  4 after a test for their shape; one equivalent by construction (a year-shaped quantity — the no-value-between bounds
  already exclude it).
  Round 17e's review — the bounded independent review of the frozen `538d7dae` (tag `wmn-candidate-r17e-538d7dae`):
  four read-only lenses in sealed checkouts, no concurrent edits. Every finding was reproduced on `538d7dae` before any
  repair. The false-green lens: 32 careless answers pre-filled and passed finalization's recheck — a value given a vein
  the notes did not give it (a vein written after the value, in a bracket, or named by a word the reader lacked; a
  predicate `varicose` read as a tributary), a dated value released (a date past a comma or an `and`, `from 2023`, a
  prior exam's date read as the study's, a day of the study's own year, `3/14/23`, `Back in 2023`, `now-ablated`), a
  rival exempted because it was held for a hedge, a side or a date, a ninth finding past the list denial's eight words, a
  label's open denial over a capital or a bullet, a question mark, `due to`, `both …`, a bracketed or `maybe` hedge, and a
  diameter in a reflux-time column. The false-rejection lens: three review dead ends (a wrapped line carrying a label
  after a stop lost the sentence above its side; a line written under both legs saved to the other leg's copy; a label's
  continuation read from before a stop refused the value) and four over-holding readers (the list denial, a cause's
  hedge, a treatment's year, a prior study's phrase over its whole clause). The provenance lens: a held statement proposal
  raised on the first page for every owner and clinician; an answer re-cited to a relative's sentence stayed `supported`
  through finalization and export; an employee's answer carried no author; plus four lower findings (an employee's save
  dropped the proposals, a generation request replaced reviewed decisions, a finalized record was re-reviewed by its
  viewer, the reader's qualifiers were shown beside a typed answer). All are repaired and pinned (`ReviewRound17e`, and
  five workflow tests through the real page, save and engine); each new test was run on `538d7dae`'s code and fails there
  (50 subtests and 5 errors across the 14 tests). Benchmarks, every battery, the wrapped mirror (13,531 pre-filled, 0
  wrong-leg) and the row mirror (0 wrong-row, 359 accepted at review) are identical to `538d7dae`; the second generator
  holds 2 more of 2,115 (the `mention` notes H092 and H158, see *Known limits*). The cost lens: two shapes past the
  worker's 120 s timeout on the page — a choice's hedge searched over its whole clause per place of its option (`knee`
  repeated: validation 244 s, the page 243 s at 49,000 characters) and a rival search rebuilding a unit's strike table
  per value (272 s) — and four over 5 s: a year before the value read by a backtracking pattern per place (20.6 s; that
  reader is gone), a wrapped sentence's rows re-read from every line to its end (55.5 s, and 528 MB of row readings kept
  — a worker's RSS 1,218 MB over six notes), and a rival's governors re-judged per call (9.1 s). Each now reads once per
  quote, unit, line window or question: the same shapes take 0.2 to 4.1 s at the limit, a worker's RSS over six such
  notes plateaus at 171 MB, and `ReviewRound17eCost` pins five of them (each 8 to 32 s on `538d7dae`, 0.2 to 2.6 s now).
  Finalization's new relative recheck reuses generation's reading of the same cited text (kept per field kind, unit,
  value and text), so the round-13 and round-16 `ReviewCost` shapes read at or below `538d7dae`'s
  (3.2 to 4.1 s against 4.1 to 4.5 s on this host).
  The author's own probe after the review found one more of the lens's class and it is repaired with them: an unknown
  vein word after the item's own vein, in its sentence (`The right great saphenous vein is competent and the circumflex
  vein measures 4.2 mm at the saphenofemoral junction` pre-filled the GSV at the SFJ). Mutation proofs, the unmutated
  classes first and every restore checked by hash: 53 mutants over the new rules, the page, the save and the cost
  repairs, all killed — 8 only after a test for the shape they changed (a transcript's next vein opening its own value,
  an unknown vein after the value, today's value against a compared dated one with no study date, an affirmed option
  after a denied list, a label's continuation kept from the refusal reader, a hedge after another subject, a prior
  study's phrase after another value, an absence option after a denied list), and 4 only once their form was corrected
  to change the rule at all (a mutant that edits a rule into an equivalent is no proof); two further mutants were
  dropped, one vacuous in form (its real form is killed) and one equivalent by construction (a `;` bound the sentence
  already gives — that code is removed).
  Its focused pass — three read-only lenses over `538d7dae..3a6f88a4` (tag `wmn-candidate-r17f-3a6f88a4`), every finding
  reproduced first — found the repairs' own releases leaking, as every round's has: 63 careless answers pre-filled and
  passed finalization (a vein after a value read only after the sentence's last value, or two lines on past the new row
  reach; an adjective or an apposition hiding a vein; `varicose` before a noun the reader lacked; a present word anywhere
  releasing a past date; the treatment-year release; `now ablated`, `before this study`; a prior word beside a study-date
  label; `Jan. 2023` ending a sentence; day-first dates; a new subject, a cause word or `worth` releasing a hedge; `at
  present` and vein names releasing a denied list; the own-clause four-word denial; a label's open denial over `any`, a
  numbered list or a blank line; unclassified headings, a bare `from` and a missing heading exempting rivals). The fix was
  to REMOVE or narrow releases rather than add exceptions to them, accepting holds the clinician resolves: the treatment
  year after a value now holds (only the other leg's treatment is released), a hedge after another subject now holds,
  the rival exemption is the short list of what says a value is not today's. The false-rejection lens found two review
  dead ends — both from the repairs' line joins (a bracket line, `lt.` read as a stop in a label) — and the refusal of
  generation missing reviewed statement decisions; nine over-holds, each narrowed (a date of birth, a lymph node, an
  existential `There is`, a vein with a finding of its own, `maybe` beside the next value, a cause after `likely`); its
  battery of 33 realistic answers pre-fills 27 as `538d7dae` did (`3a6f88a4`: 12, with 4 dead ends), and its dead-end
  probes are back to `538d7dae`'s counts (28 of 224, 18 of 100). The cost lens: the pointing-back search per value per
  answer (the page 183 s) and a rival repeated through one unit judged per place (217 s, and on `538d7dae` too) — each now
  read once (1.3 s and 0.4 s at the limit), a unit's strikes shared across answers (7.7 s to 1.4 s), and the relative memo
  bounded (a worker's RSS plateaus at 154 MB over 400 notes). `FocusedPass17e` pins all 63 and the realistic notes; each
  new test fails on `3a6f88a4`. Benchmarks row for row identical to `538d7dae`, every battery identical, the wrapped
  mirror 13,529 pre-filled (2 fewer) with 0 wrong-leg, the row mirror 0 wrong-row; the second generator holds 25 more of
  2,115, all generated `mention` notes (a line naming the other leg inside a block, whose sentence the reader runs across
  the next block's heading).
  The focused pass's repairs' mutation proofs — 87 mutants, the unmutated classes first, every restore checked by hash
  — killed 74 on the first run. Of the 13 survivors, one was a finding: a value read two ways from its paragraph rather
  than its sentence was never a rival (`LEFT LEG:` / `The great saphenous vein measures 6.9 mm at the saphenofemoral
  junction.` / `Right after augmentation the great saphenous vein at the saphenofemoral junction measures 9.6 mm.`
  pre-filled the left's 6.9 mm and did not show the 9.6). `3a6f88a4` held it; the pass's own narrowing, made to spare
  the generated `mention` notes, had re-opened it, and its other conditions spare those notes alone. The mutant that
  counted it was the safer rule and is now the rule (the second generator's 2,115 answers are unchanged by it). Two were equivalent by construction, and their code is
  removed rather than kept as a second reader: a check of the words before a study-date label that the check of its
  line already makes, and a lymph-node check in the rival search that the row reader already makes. The other ten were
  rules no test separated, each now pinned by the note that does: a vein in a plain bracket or in an insertion naming
  the subject (`the dominant refluxer (anterior accessory saphenous vein)`, `, which is the …,`, `(that is, …)`),
  `now-sclerotic`, a leg's word before a date with a past predicate, an existential `There is`, `maybe` right before
  the next value, a new subject's verb and the legs' own predicate ending a denied list, the pointing-back cost shape
  moved into the cited paragraph where its search is asked, and generation refused over an answer typed with nothing
  ticked. Rerun with the tests and the repair: all 85 remaining mutants killed, every restore checked by hash.
  Round 18 — the bounded independent review of the finished `f01107aa` (tag `wmn-candidate-r17g-f01107aa`): five sealed,
  write-disabled lenses, each on its own checkout and throwaway database and given the claims rather than the intent
  (clinical attribution; sides and governing context; clinician decisions; finalization and export provenance; cost),
  every finding verified by a separate agent and reproduced here before any repair. 48 findings: 36 confirmed, 8
  reproduced but classed as known limits, 1 refuted (the engine's own `<<insert location>>` marker in a reviewed-missing
  cell, `main`'s pinned behaviour), and the cost lens's 3. Most HIGH findings were the focused pass's own releases, and
  each is repaired by restoring the hold, never by a new exemption: a vein's own finding released its other-vein rival
  (`At the saphenofemoral junction a 6.8 mm anterior accessory saphenous vein is incompetent.`), a date after the value
  was exempted when the other leg's treatment stood between, `born in 2023` read as a birth date, a title-shaped history
  sentence (`Ultrasound 03/14/2023 showed …`) read as the study's date, `varicose` said of something unnamed, a rival
  dropped when a `no lesion` or `lymph node` stood near it, `maybe`/`perhaps` read only beside the value, a hedge before
  a cause (`likely artifact from thrombus`), a leg's own label before a date, an existential `There is` rival, and the
  not-today label list (`post`, `pre`, `no`, `not`, `last`, `compared` exempted today's rival). The older gaps: a side
  after `except`/`excluding`/`as opposed to` or in a bracketed statement placed the value on that leg; a leg named only
  as unexamined placed it; a bracketed remark on the next line (`(on the prior study)`, `(left leg)`, `(in error)`) was
  not read; and choices and statements had no order, relative, prior-study or date reader (`Rule out right great
  saphenous vein reflux.`, `Her mother has reflux …` pre-selected). Through the page: a statement wording saved without
  its tick, and an answer a person cleared, were replaced by a second generation; an employee's save emptied the
  clinician's statement decisions (now kept, unreviewed, with the withdrawn reviews audited); a cleared answer showed as
  a plain `missing` (now `cleared by …`); `&p`, `&l`, `&m`, `&b`, `&&` in a table cell, which the engine's replace
  writes as breaks, are refused at review. Cost: the row window reached `WRAP_REACH` from every value — the save 101 s
  and 3.1 GB at 49,623 characters; a line's values now share one window (the pinned shape: a 15 s CPU limit). Every reproduced careless answer — 204, among them 26 bracketed remarks under two heads at two positions — is
  held; the benchmarks, batteries 1–3, 5 and 6, both generators, the wrapped-leg mirror (0 wrong-leg
  pre-fills of 16,655) and the row mirror (0 wrong-row pre-fills of 34,466) read row for row as `f01107aa`, except
  battery 4's ten lowercase shorthand answers (`rt gsv sfj 7.4 mm, reflux 2.1 s` / … / `lt gsv sfj 5.0 mm`) now
  pre-filled correctly instead of held both ways; review dead ends 40 → 15, every one already on `f01107aa`.
  Its mutation proofs — 46 mutants over the repairs, loaded in memory in their own process (no file written), the
  unmutated suites first — found three repairs of the repairs, each reproduced first. The first form of the side-item
  rule split `… without reflux` / `left leg.`, and the value took the right leg of the line above (round 14's pinned
  `R14M`; the full suite found it): a side naming a limb goes on as before, which returns nine older dead ends
  (`GSV SFJ 7.4 mm` / `lt. leg not examined.`). The dated-study pattern's possessive modifiers ate `duplex` in `2023
  duplex shows`, and the other leg's words were searched across a `;` into another sentence: `The left leg was normal;
  the 2023 duplex shows the right great saphenous vein measures 9.6 mm` pre-filled a 2023 value (as on `f01107aa`). A
  label exempted its rival for a not-today word anywhere in it (`Mapping, family history reviewed:`): the label must
  now open with it. Ten rules no test separated are now pinned by the notes that do; one is equivalent by
  construction and kept as a second guard (an employee's statement ticks are refused by the role check before the
  save's own `reviewed=False`). Rerun: the other 45 killed, each by an assertion, none by a crash.
  Round 19 — a focused refutation pass over round 18's repairs (`f01107aa..207a26a8`, tag `wmn-candidate-r18-207a26a8`):
  four sealed read-only lenses (reader releases; the page; cost; the campaign runner), every finding verified by a separate
  agent and reproduced here. 23 findings, every one confirmed (11 HIGH, 10 MEDIUM, 2 LOW as the verifiers assessed them), and most were round 18's own
  repairs: setting a side apart by changing where a value is PLACED dropped a rival that named it (`Repeat (the right leg
  was re-examined standing): great saphenous vein 9.6 mm …` let the right's 7.4 mm pre-fill) and refused correct values
  at review (`except the right great saphenous vein, which measures 9.6 mm`); the side-item split's list of what names a
  limb leaked (`… without reflux` / `left thigh.` gave the value the right leg); dropping the check beside the value
  released `6.1 mm maybe, reflux 2.1 s`; stopping each value's row window at the next value put an accessory vein's 1.8 s
  two lines on onto the great saphenous vein's row; narrowing what is no vein released `9.6 mm, oval lymph node`; the
  title-date rule skipped a real title with a subtitle and took an earlier study's date; a bare `(left).` below the value
  was an item's marker (older); and `finding_context` read one window per located word over every date of the unit
  (211 s at 49,578 characters). Repaired, each toward a hold: a set-apart side places what it placed on `f01107aa`, and
  the sentence is held instead (measurements, sided choices and statements) with its value a rival for either leg — an
  exclusion or contrast that owns its clause keeps its side; the side-item split is reverted; `maybe`/`perhaps` first
  after a value holds it; a line's values share the window of its LAST value; the loose not-a-vein form holds the value's
  own row while only the narrow one drops a rival; a title-shaped date later than every certain one makes the study's
  date unknown; a side bracket marks an item only when a value follows it on its line; windows deduplicated, dates
  bisected, the unexamined rule read once per sentence (211 s → 0.6 s, 37 s → 1.0 s, 7.4 s → 1.5 s at 50,000
  characters, against `f01107aa`'s 0.4–1.3 s). The page: an employee's save keeps the clinician's decision whole where
  the wording is unchanged (a browser posts nothing for the disabled basis box — the rendered-form test helper posted it,
  so the round-18 test could not see the loss; a browser-faithful form now drives it); the `&` blocker names a spelling
  that completes; a cleared answer reads `emptied by`. The runner: see *Live verification* and the offline bullet below.
  Measured, row for row against `f01107aa`: benchmarks, all six batteries (battery 4's ten shorthand pre-fills are held
  again with the split reverted), both generators, the wrapped-leg mirror and the row mirror are IDENTICAL; review dead
  ends are `f01107aa`'s 40 of 289 probe rows, none new (round 18's reduction went with its reverted placement). On
  `207a26a8` the round-19 class fails 31 rows; on `f01107aa` only the five bare side brackets, which it also
  pre-filled. Mutation proofs: 22 mutants (reader, page, runner), the unmutated suites first, all 22 killed by an
  assertion. ⚠️ **Round 19's own repairs have had NO independent pass**: a two-lens pass over them was prepared and not
  started, because the host's disk stood over the preflight's 90% line after this session's own sandboxes were reaped
  (report `docs/preflight-reports/preflight-20260926T212542Z.md`). A self-check instead — not independent — fuzzed the
  one reader change that could release against `f01107aa` (a line's values sharing its last value's window) over 62,088
  answers on short and 1,300–2,600-character lines: 0 differences from `f01107aa`; and read the runner's recovery delta
  adversarially, which found one defect of its own — a kill between a record's temporary file and its link left
  `.partial-…-attempt.json`, which `Path.glob` matches, so every restart failed; the ledger now reads only
  `NNN-<case>-attempt.json` records (reproduced, then pinned). An independent pass over round 19 remains due before merge.
  Round 20 — the independent pass over round 19 (`207a26a8..86a1e52c`): three sealed read-only lenses (reader; page;
  runner), each finding verified by a separate agent and reproduced here before any repair. 18 findings: 17 confirmed
  (7 HIGH, 6 MEDIUM, 4 LOW as the verifiers assessed them), 1 refuted (an employee's two wording changes dropping the
  clinician's basis: the first change legitimately replaced the decision). The reader's: an exclusion's clause of its
  own exempted the whole sentence (`Except for the right leg, which was examined last week, the great saphenous vein
  measures 9.6 mm` pre-filled the right, as `f01107aa` did) — the clause now places only a value inside it, the words
  before `which`/`where` must be the limb's or the vein's own, and a set-apart side in a later clause places nothing of a
  value; a set-apart side a sentence earlier, which the paragraph's reading took (`Unilateral study excluding the right
  leg.` / `The great saphenous vein measures 9.6 mm …`), is held where it is the side that reading gives; `maybe` after a
  bracket, quote or colon, or across a comma before the value (`6.1 mm (perhaps artifact)`, `Right GSV SFJ, maybe, 6.1
  mm`), is held again as on `f01107aa`; a side bracket below the value is an item only with a measured value on its line
  (`(left) - repeat 09/25/2026` was an item, older); up to three words of the limb's own between an exclusion or a
  contrast and its side (`except for the painful right leg`, older); and a set-apart sentence's hold comes after the
  hedge, the earlier study and the date, whose reasons say more. The page's: under the labelled contract the `&` advice
  named a spelling the engine refuses (it accepts a labelled answer only as its line writes it) — that contract now has
  its own blocker, whose advice names the notes' line, and review refuses what finalization refuses; an employee's
  changed statement source under the clinician's wording is still not kept, and the saver is told. The runner's: a
  resume against another database read the missing job as proof nothing was sent — a captured request, or a missing
  encounter, is now an unknown outcome at its maximum that stops the stage, and a campaign is bound to its database by
  its first encounter; no verdict is written while any attempt lacks its outcome, its manifest entry or its score, or
  the records are not exported (`OPEN`, exit 6: the next start records them and re-derives every stop first); the
  replay is published whole and the manifest says whether it matches its answer; a retained response is named by its
  attempt and kept once; every line reading as an authorization counts, and any revocation word refuses; the declaration
  path is a literal pathspec. Each repair is pinned by tests that fail on `86a1e52c` (the reader's 29 of 31 held rows, 3
  statements and 2 reasons; the runner's 4 new tests), and my own probes of the new rules found one over-hold of my first
  paragraph rule (`RIGHT LEG:` / `All segments were imaged, unlike the left.` / …), narrowed before commit.
  Measured on `1335f780`, row for row against `f01107aa`: benchmarks, all six batteries, both generators, the
  wrapped-leg mirror (0 wrong-leg of 16,655) and the row mirror (0 wrong-row of 34,466) are IDENTICAL — every hold
  round 20 adds is on an input the harnesses never had. 27 mutants over the round-20 repairs (reader 15, page 3, runner
  9), the unmutated baselines first: all 27 killed by an assertion (one first killed by a crash, whose test now asserts
  the missing entry explicitly), every restore checked by hash. The offline campaign validation passes 22 of 22 scenarios
  and 356 checks, the four new ones included. Suites: core 1,357 with one failure — `ReviewCost.test_round_13…`'s 5.0 s
  wall guard at 5.17 s under this shared host's contention, the reconciled failure (the module alone: 191 OK; the
  guard's own workload in interleaved fresh processes, 4.35–4.64 s CPU against `86a1e52c`'s 4.33–4.54 s); documents 101,
  ops 945, the real-engine workflow 31. My own probes of the new rules found two quadratic reads of my own before commit
  (a whole-unit slice compared per value; the paragraph's reading taken for every sentence of a note that sets no side
  apart). ⚠️ **Round 20's own repairs have had no independent pass.** Evidence:
  `docs/deploy-reports/wm-narrative-round20-evidence-20260927.md`.
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
  1,200 characters of its wrapped sentence back). Round 15's, on the lens's own probes, cold: a sentence label's runs of
  spaces backtracking — cubically where a run led a line, quadratically after a word — a header of 100 spaces over 700
  values, validation 142 s → 0.2 s, review 137 s → 0.2 s, the page 139 s → 0.2 s (the real app: the generation job 142 s,
  the page 147 s, the save 152 s), 12,000 spaces after a word 185 s → 0.1 s, a value line indented 560 spaces 126 s →
  0.04 s (`sentence_label`: the pattern read linearly, and proved the pattern's match on 40,000 texts of a fixed sample);
  a mention's line shape read per sentence of one long line, 146 s → 0.8 s (once per line); a label's line copied and
  searched per context reading, 4.8 s → 2.4 s (once per label); the wrap reach snapped to the start of a 45,000-character
  first line, 46 s → 0.8 s (from the first line starting within the reach; a far side word read once).
  Round 13's cost lens's five shapes re-measured on round 15's candidate, cold (every cache cleared per path, a fresh
  process per shape), at 12,000 / 25,000 / 49,000 characters: validation 0.4–0.8 / 0.6–1.5 / 0.9–3.0 s, the page's
  recheck, finalization's and review each at most 2.3 s at 49,000; through the real app and Word engine at 49,000, the
  job 2.9–3.3 s, the page 4.3–4.4 s, the save 4.3–4.5 s, the page after it 4.1–4.3 s (round 13: 133–137 s), and a
  page served warm, its caches kept, 2.2–2.4 s.
  Round 16's, on the lens's probes, cold: whether every other-leg phrase of a clause is a compared thing, read per place
  — validation 143 s → 0.55 s at 13,000 characters, the round-15 accepted sentence 78 s → 2.3 s at 49,000 (the phrases
  and comparisons read once per scope, bisected per place); a leg's predicate re-reading a run of spaces per place 25 s
  → 1.4 s (its limb and verb read once per side word); a label's findings per context reading 23 s → 0.3 s (once per
  item).
- **The real workflow**: `test_wm_workflow.WMNarrativeWorkflow` (CI, real Word runtime): retained narrative response
  → generation → the page as rendered → decisions → finalization → export into the unchanged original; forged
  narrative answers refused at fill.
- **The local 5 s guard (round 18's reconciliation; the failed result is kept, the threshold unchanged).** On this
  shared host the full core suite of `f01107aa` failed `ReviewCost.test_round_13_a_whole_leg_unexamined_is_read_once_per_sentence`
  at 5.634 s against its 5.0 s wall limit; CI's GitHub-hosted runners passed it. A controlled comparison — the test's
  own workload in fresh processes, interleaved and order-rotated, 24 samples per commit, CPU and wall time recorded —
  gave `f01107aa` 4.38 s CPU median (4.08–4.89), its CI-green predecessor `538d7dae` 4.46 s (4.20–4.94), `3a6f88a4`
  4.32 s, no sample over 5 s at host loads of 3 to 13; the two full suites run side by side in one window BOTH failed
  the guard (`538d7dae` 5.94 s, `f01107aa` 5.58 s). The candidate is not slower than the commit before it; the
  failure is contention (co-tenant test runs, swap full) against a guard with about 12% headroom in isolation — spent
  before this candidate (`e95bab90`: 3.44 s). That capacity limit stays: on this host under load the 5 s guard (and
  the 0.25 s title guard, 0.21–0.30 s on a first call for every commit) is not a reliable measure; CI is.
  Round 18's tree (`207a26a8`) against `f01107aa` the same way in one interleaved window: 4.25 s CPU median (4.01–4.65)
  against 4.32 s (4.05–4.74); round 19's (`f920f7ab`): 4.40 s (4.14–4.75) against 4.40 s (4.20–4.66), 24 samples each,
  none over 5 s — the repairs cost this shape nothing. Their full core suites on this host failed the same guard at
  5.20 s and 5.35 s (the latter beside this session's own mutation batch, row-diff and runner validation, load 8); the
  whole reader module run alone passed it.
- **The live campaign's runner, offline (no provider request possible).** `ops/wm_narrative_campaign_offline.py` on `f920f7ab`,
  again on `c2e2511c` after the ledger fix, and on `72283bc5` with the request capture and the replay manifest (18 of 18,
  323 checks: in every scenario each request the provider received was captured before it was sent, canonically
  identical, and every attempt — a recovered one included — has a manifest entry whose files exist and match their
  sha256; re-checked after the synthetic database was dropped),
  drives the real runner through the candidate's product path (the blank form uploaded through the page, the page's
  quote, Generate, `run_one`, settlement, the validator, the page) against the loopback mock with retained careful
  responses and a fixed non-secret marker: all 18 scenarios pass and no scenario database is left (14 on `207a26a8`;
  round 19 added the four interruptions its focused pass found mishandled — a kill after Generate queued the job and
  before the worker, which now cancels that job through the product so it can never run under the next attempt; a
  wrong-model answer and a 401, each followed by a kill, now recovered with the model and the error class the product
  recorded; and a SIGTERM as the answer lands, after which the draft is scored before the verdict). A clean stage: 5
  requests, provider exposure $0.502 (with the 1.1 margin), wallet $0.685, a replay file and a score per answer. A wrong
  answer stops after its case is scored; one transport failure is retried once, the failed attempt counted at its $0.329 maximum; two consecutive
  transport failures, or a third with both retries used, stop (three unsettled attempts: exposure $1.19); a 401 stops
  without retry; an unusable answer is settled and absorbed (the provider paid, the customer not); a cost above the
  quoted maximum, another model, and key-shaped text in evidence each stop. A kill mid-request is recorded on restart
  as `interrupted_unknown` with its job and counted at its maximum, its case then retried as a retry; a kill after
  the worker adopted is recovered from the job record and scored, nothing resent. Live mode without its committed
  declaration or outside its fixed evidence place, stage 2 before a stage-1 PASS, a re-run of a stage with a verdict
  and a non-loopback offline provider are refused before any request. Every received request was a ledger attempt
  carrying only the offline marker, the declared model and `max_tokens`; exposure and wallet recompute exactly from
  the ledger and the exported database rows.

## Known limits (this candidate does not solve them)

Every one of these fails closed (a hold, or a statement the clinician must source) unless it says otherwise.

- **A set-apart side holds more than it must in two shapes (round 20, accepted).** In a dictated transcript with no
  punctuation, one set-apart phrase (`… unlike the right side the left small saphenous vein is competent`) holds every
  sided value before it in the run-on sentence; and a side bracket with no measured value on the line below a value
  (`(L) GSV SFJ competent, no reflux`) is read as a remark, so the value above is held. Both are over-holds the
  clinician resolves at review; the release of the opposite readings is what rounds 18–20 closed.
- **Under the labelled contract, a table-cell value written with `&p`, `&l`, `&m`, `&b` or `&&` completes only by
  changing the notes' line and generating again (round 20).** The engine accepts a labelled answer only as its line
  writes it, and its cell replace rewrites those sequences; the advice says so. The narrative contract takes the
  capitalized spelling at review.

- **Interpretation the text does not signal.** A model that misses a negation, swaps two values within a sentence,
  invents a choice, leaves a real conflict unflagged, misses hedging or reads a plan as the past can still pre-fill a
  wrong answer where no deterministic signal exists (the weak benchmark set's 11 at round 16 all turned out to have
  one — contradictory values or findings, hedges, denials, nothing clinical cited, another row — and are held; a model
  error the notes give no sign of remains possible, and this is not a claim of universal detection). Every pre-filled answer
  is reviewed by the clinician; that review is the control, and live verification measures how often it is needed.
- **Rows (round 17), what they do not read.** A value's trunk diameter written with no level (`the small saphenous vein
  measures 3.2 mm with no reflux`) is held, since the form has two rows for it; so is a level only near a row (`mid
  thigh`) — both necessary holds (the row is not written). Two veins named before one value with no insertion between
  (`the great saphenous vein and the anterior accessory saphenous vein measure 6.8 mm`) are read for the last one and held
  for the first — never refused. The vein and level words are closed lists; a word they lack reads as no row, which
  holds, and a vein-like word they lack (`AAV`, `SFV`, `the accessory`) stops an earlier vein carrying — but a level word
  they lack after a value in an item with a level (`… with reflux in the distal segment`) is read as that item's level.
- **Rivals (round 17), what they read.** A rival is a live value in another unit read for the same row and side. A
  bound is read by its direction (`less than`, `up to`, `not exceeding`, `or less` at most; `greater than`, `at least`,
  `or more`, `+` at least); an estimate, a range or an alternative (`about 7 mm`, `6-8 mm`, `6 or 8 mm`) is not read for
  its span, so one that is not the answer holds it even where the answer is within it — an unnecessary hold review
  accepts. The cited sentence's own other values are read too: one at the row's level (`… 6.9 mm at the saphenofemoral
  junction and 9.6 mm at the saphenofemoral junction`, which pre-filled either value before) and one of the row's vein
  with no level written (`Left GSV at the SFJ 6.9 mm, repeat measurement 9.6 mm`) are rivals — so is a depth or a wall
  written that way (`…, 8 mm deep to the skin`): the reader does not know what a number of the vein measures, and holds
  (unnecessary, accepted at review). Not a rival: a prior one (`previously 9.6 mm`), another row's (`and 5.1 mm at the
  knee`, `4.1 mm at mid thigh`), the other leg's, an accessory's. A year is not read as a prior study's there (`9.6 mm in
  2023` holds). The search asks each other value of the row once whether it is governed, and reads each unit's colons
  and words once (4,000 plan values: 12 s before, 1.4 s). None of this changed an answer of the benchmarks, the
  batteries or the wrapped mirror.
- **A side written after the value, the same as its paragraph's** (`LEFT LEG:` … `The great saphenous vein measures 4.9
  mm at the knee with 2.7 seconds of reflux in the left leg.`) is held as ambiguous (round 6's rule, for a side that may
  be another finding's): an unnecessary hold, older than round 17, which review accepts. Round 17's wrapped-value join
  made 87 wrapped answers read as their unwrapped note already did (the wrap had cut that side off the unit), and round
  17c's cited wrapped sentence 341 more (their side had been taken from a neighbouring sentence).
- **Rounds 17d and 17e, what is not read.** `measurement_context`'s earlier-study wording is a closed list of
  attributions, and a prior study's phrase is read as the nearest value's only (in an unpunctuated run, one right after
  another value is that value's). A date is read in the value's own sentence only — the nearest before it and after it,
  not past another value or a `;` — so a date in the sentence before (`The 2023 study: … . The great saphenous vein
  measured 9.6 mm.`) and a date in words (`last year`, `two years ago`) are not read; a date before the value is not the
  value's only where the value's own predicate is a measurement in the present and a leg or a treatment is named before
  the date (so `In 2023, the great saphenous vein measures 9.6 mm` is held, and `History of left GSV ablation in 2021, the
  right GSV measures 6.1 mm` is not); a date after the value is its own, a treatment's too (`… 3.1 mm at the knee after
  ablation in 2019` is held — the clinician decides), unless what stands between names the other leg and a treatment; a
  date with no study date in the note holds its value even where it is this study's, and only the note's own labelled
  study date or a title opening its line is read as the study's (`Date of service`, `Exam date`, `DOS`, `Venous duplex
  09/25/2026`; a date in prose is none). A day-first date is read as such only where its first part exceeds 12. A
  bare `no` or `without` is not read across a list (`no reflux and swelling`), only a denial verb, and a list ends at
  its first verb, contrast, positive finding, vein, number, `;`, `, with …` or `, history of …` (`She denies numbness, with
  nocturnal cramping` pre-fills `Cramping`). A hedge after the value that a finding word follows is read as the finding's
  (`… 6.1 mm with possible reflux`), and one of a cause or a treatment written as such right after it (`likely the source
  of her symptoms`, `possibly worth treating`, `would likely benefit from …`) is not the value's; any other hedge after
  the value in its sentence is, whoever the sentence goes on about (`…, and she would possibly prefer compression` holds
  it); a tag question (`…, right?`, `…, correct?`) is none. A rival is a value read for the row, or one with no level in the cited sentence
  or pointing back at a level in its paragraph (`there`, `at that level`): another value whose row the reader cannot read
  (`It measures 9.6 mm as well.`) is no rival, and one read two ways under the other leg's heading is none either — while
  one whose own sentence reads it for this leg only is (the generated `mention` notes, a line naming the other leg inside
  a block whose sentence the reader runs on into the next block's heading, hold 25 of 2,115 answers this way). A vein word the reader does not know is read only as
  the word before `vein` or a known abbreviation: a vein named otherwise, with no `vein` after it and no carried vein's
  name, leaves the paragraph's vein carried. A label's open value continues onto at most 40 list items under it. A vein carried from a sub-heading
  (`Great saphenous vein` / `SFJ 5.6 mm`) is not refused for the accessory's row at the same level: review accepts the
  clinician's choice there (359 of the row mirror's 34,466 wrong-row offers); none is pre-filled. Review accepts the
  other leg where a reading gives it — a sentence comparing the legs, a side after the value in a run-on — as the
  clinician's decision, stored `edited` with who made it. A label line whose own sentence names the other leg and runs on
  by a wrap to the value's line (`Comment: the right leg is the treated one, and` / `the great saphenous vein measures …`
  under `LEFT LOWER EXTREMITY:`) is refused for the left unless that comment line is cited too (lens 2 of round 17e's
  review: not a dead end, a citation completes it).
- **Options (round 17), what they read.** The deep-vein list reads CFV, FV, the popliteal and posterior tibial veins by
  name and abbreviation; an option listing others is not read as a list. The qualifier evidence is a closed list of
  treatment and duplication words in the vein's clause: a qualifier the notes describe otherwise leaves the plain option
  pre-filled. H06 is a regression case now, not fresh evidence.
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
  value, while a LIMB's label heads its block only over findings and where any leg named before it was named by such a
  label (round 15 corrected this line: it said a contralateral check written `Left leg: No DVT in the common femoral
  vein.` inside the right leg's block still headed what follows it, under a heading saying every entry fails closed —
  that one failed OPEN, the right's values pre-filled on the left; it now heads nothing, and the values are held); a leg a
  sentence only mentions inside another leg's block is a reading only (`Left leg to be scanned next week.`); an
  invisible character on any line that shows something holds every pre-fill, a byte-order mark opening the notes
  included (its first line's heading also reads as an unknown word — held before round 14 too); round 15's
  false-rejection lens measured its cost on three realistic pastes — a left-to-right mark before a date, zero-width
  spaces after commas, a variation selector after a check mark: 0 of 11 correct answers pre-filled (round 13: 11), review
  completing for all.
- **Refused at support, so review cannot complete without the notes edited (round 14's false-rejection lens):** a value
  or its unit with an invisible character inside it (`7.3 milli`+U+00AD+`meters`, `7.3`+U+200B+` mm`); a spoken
  correction that does not repeat the unit (`7.1 millimeters, correction, 7.4 with reflux …`, `1.2 seconds, I mean
  1.4.`: the corrected-to number carries no unit, and the engine reads none); a bare leading decimal (`reflux .8 s`);
  and in a one-leg study that never names the other leg, that leg's reflux statement (claim 36 or 32): its
  `not_documented` wording rests on no answers in the mapping and no sentence names the leg — the clinician adds `Left
  leg not examined.` (then it completes). A labelled value after an FS, GS or RS line break is accepted at review and
  refused at fill, like the other non-`\n` breaks below (fails closed).
- **Held by design since round 15:** a value more than 1,200 characters after the only side word of its hard-wrapped
  sentence (`left leg the great saphenous vein …` / 18 wrapped lines / `… 4.4 millimeters`) — the pre-fill is lost and
  review accepts that word's side (round 14 read neither and pre-filled the paragraph's side); a clause of the value's
  sentence only mentioning the other leg (`She had the left leg treated in 2021 and today the great saphenous vein …`
  under the right leg) reads both ways; a leg change dictated in words beyond the leg's own and filler (`Turning to the
  left.`, `Moving on to the left leg.`, `The left leg was examined next.`) inside another leg's block is a reading only;
  a system's list whose bare label heads the rest of its line only where both legs are listed or nothing names another
  leg, and no heading names one (its later sentences are held otherwise, review accepting either leg); a value a
  comparison introduces on the other leg (`… versus 5.0 mm on the other side.`) is refused at support for either leg —
  the clinician writes its side; a pasted date carrying left-to-right marks (`‎9/‎25/‎2026`) is refused as labelled
  (an invisible character inside a value, above); an unpunctuated transcript opening on the other leg's examination
  denied (`left leg not examined right leg great saphenous vein junction measures 7.1 millimeters …`) is held, review
  accepting either leg; so is a limb's label written in mid-line in a dictated paragraph (`Right leg. … without reflux.
  LEFT LEG: The deep veins are compressible. The great saphenous vein measures 4.6 mm …` on one line).
- **Held by design since round 15's acceptance repair (narrowed in round 16):** an unpunctuated run naming the other leg
  anywhere before this leg in the sentence, or around it, then this leg with a predicate of its own — a PAST finite verb
  (`was`, `were`, `had`, `underwent`, `received`) within two words of its limb word, naming no anatomy before it, no
  examination in the two words after it (`was examined`, `was scanned`) and no quantity after it — that reaches a vein
  as a new subject before the value (`… no clot the left leg was done in 2021 by doctor synthetic the great saphenous
  vein at the knee measures 5.1 millimeters`, `… the left leg had ablation last year the great saphenous vein …`, with a
  comma or `and` before it too, `… the left leg underwent ablation in 2021 …`, `… was done in 2021 per the outside
  study …`) reads both ways, review accepting either leg. Round 16 narrowed it to the past tense: a present state is
  the leg's examination today (`the left leg has no dvt`, `is normal`, `is negative for dvt` are the left's). Still the
  left's: `… now the left leg the great saphenous vein …`, `… the left leg was examined next …`, `left leg gsv at the
  knee is 5.1 millimeters`, `left leg was 5.1 millimeters`, `the left leg has reflux measuring 5.1 millimeters`, `the
  left leg was 7.2 millimeters at the junction the great saphenous vein …`, `left leg gsv is dilated the small
  saphenous vein …`, and a run naming one leg only. A leg's predicate in words the rule does not see — a finite verb
  further than two words on, a present-tense verb about a prior event, a site instead of a vein as the new subject — is
  still read as that leg's: the model's timing and the clinician's review remain the control there.
- **Held since round 16, costs measured:** a sibling limb label over something other than a finding line's words (`Left
  leg: Swelling and pain.`, `Mild edema.`, `Symptomatic.`) heads nothing, so its block is held and review accepts either
  leg (round 16's false-rejection lens: 73 of 287 labelled answers in that style); an anatomy sub-heading with no colon
  under a bare `Right:` label (`Great saphenous vein`) ends the label's block (85 of 124 right rows in that style); a
  list of both legs' lines or labels under a one-leg study's title or exam line releases nothing, and review of the rows
  the other leg's label heads refuses the study's own leg unless the title is cited (`RIGHT LOWER EXTREMITY VENOUS
  DUPLEX` / `FINDINGS:` / `Left: No DVT in the common femoral vein.` / `GSV SFJ: 7.2 mm …` / … / `Right: …`).
- **What review cannot complete without the notes edited, most common first (round 15's false-rejection lens, 147
  hand-written notes and 300 generated reports):** a one-leg study that never names the other leg — that leg's reflux
  statement (claim 36 or 32) has no source: 36 of 147 notes (24%) and 58 of 300 reports (19%), the one owner-shaped
  gap (a `not_documented` wording resting on a title that names only the examined leg is a mapping decision, not the
  reader's); a number and its unit split across a hard wrap, 12 of 203 wrapped answers at 72 columns; a spoken
  correction without its unit, 5 of 7 correction forms; then a bare leading decimal and a side written after the value
  across a hard wrap (all above).
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
- **Round 18's review, what remains (each reproduced; none a wrong pre-fill).**
  - *Held for the clinician by design — the repairs restore holds rather than add exemptions, so these are held and
    accepted at review:* an existential `There is 9.6 mm on the repeat image.` read as a rival; a date right after the
    value that belongs to the other leg's treatment (`Right GSV SFJ 7.4 mm, s/p left GSV RFA 2019.`, `…, and the left
    GSV was ablated in 2021`); a value with no vein of its own before another vein's finding (`At the saphenofemoral
    junction 6.8 mm (AASV competent).`, `… 6.8 mm and the SSV is competent.` — with its vein named, `the great saphenous
    vein measures 6.8 mm (AASV competent)`, it pre-fills); a hedge before a cause (`likely from chronic reflux`); a label
    whose not-today word is not its first (`Her prior study:`); and a choice or statement sentence carrying any date where
    the study's own date cannot be read. (Each verified on `207a26a8`.)
  - *Review dead ends — 40 of the 289 rows of round 18's clinician-decision probe, the same 40 as on `f01107aa`:* a line
    opening with a small letter goes on from the line above
    when that line has no stop, so a sentence about a leg or a side item on the next line (`GSV SFJ 7.4 mm, reflux 2.1 s`
    / `lt. leg not examined.`, `left leg scanned last month.`, `rt. GSV SFJ 7.4 mm, reflux 2.1 s` / `lt. GSV SFJ 5.0 mm`)
    is read with it, and review refuses the right value it now names the left beside. The pre-fill holds. Ending the
    value line with a stop completes it — a note edit, which clears the draft and needs a second generation. (Round 18
    split side items onto their own line; its list of what names a limb leaked — `… without reflux` / `left thigh.`
    gave the value the right leg — and round 19 reverted it.)
  - *LOW (as on `f01107aa`):* `… without reflux in the` / `lt. IMPRESSION: Right GSV reflux.` — the pre-fill is held,
    but review accepts a clinician-typed 5.0 mm on the right row and refuses it on the left.
  - *MEDIUM, provenance (as on `f01107aa`):* a pre-fill citing a number and its unit joined across a hard wrap (`… 7.4`
    / `mm at …`) is rendered with its line break; an unchanged save re-posts it as the two physical lines, so
    generation's answer becomes the saver's `edited` entry (the page says "entered by …") and review asks for an exact
    labelled source that the page cannot re-post — the value can only be left blank, or the notes edited (which clears
    every decision and needs a second, billed generation). The value is right; nothing wrong is exported: a dead end.
  - *MEDIUM, cost (older; linear):* at 45,000–50,000 characters of dense hard-wrapped values the save takes 6.9–8 s CPU,
    the page 6.5–10.9 s and finalization's recheck 5.7 s — above the 5 s review target, far below the 120 s request
    limit (the cost lens's L5-02 and L5-03; round 18's own widening of the row window, 101 s, is repaired).

## Live verification (NOT run; needs the owner's authorization)

**What it measures.** How the real model's answers fare through the frozen candidate's product path — the page's own
quote, the doctor's Generate request and its hold, ONE provider request by the worker's own `run_one`, settlement, the
validator, the page — scored by the frozen scorer (`core/tests/wm_narrative_benchmark.score_case`) against
expectations written before any live response existed. Every response is kept with a replay file keyed by the notes'
sha256, so each result can be reproduced offline.

**Model and pricing, verified 2026-09-26 without reading the private environment.** Anthropic's live pricing and
model-status pages: `claude-sonnet-4-6` is Active (retirement not before 2027-02-17), $3 input / $15 output / $3.75
5-minute cache write / $0.30 cache read per MTok, 1M context at standard price, structured outputs (`output_config`
JSON schema) GA on it, and US-only inference (`inference_geo`) 1.1 × on Claude 4.6+. The application's own records
(jobs of 2026-09-21 and 2026-09-22) carry provider `anthropic:claude-sonnet-4-6` and pricing version
`configured-v1:fcc80267…` — recomputed exactly from those records' non-secret fields (anthropic, claude-sonnet-4-6,
$3 / $15 / $0.30, discount 0, Deepgram $0.0043 per minute). The 2026-09-17 record's `48bd430d…` differs only in the
voice-rate field; generation rates are unchanged. The runner stops before any request if the application's
configuration, the page's quote, the queued job or the provider's answer names another model or pricing version.

**Per request, fixed by the code** (`core/generation.py`, `core/wm_narrative.py`): one `messages.create`,
`max_tokens=12000`, `timeout=240 s`, `max_retries=0`; a truncated answer adopts nothing. The quoted maximum is
`(bytes sent + 12,000) × input rate + 12,000 × output rate`: $0.2978–$0.2999 for the stage-1 cases, $0.2975–$0.3066
for all 29 (`ops/wm_narrative_campaign.py plan`); the hold is 1.5 × that.

**Two money limits, enforced separately, because one does not bound the other.** The wallet cannot bound what the
provider bills QuillMD: an answer the validator cannot use is settled and then ABSORBED (the customer's charge is
reversed, the provider is still paid), a timeout leaves the outcome unknown with the hold kept, and a cost above the
hold is absorbed. So:

| | stage 1 | stage 2 | campaign |
| --- | --- | --- | --- |
| requests | 5 cases + ≤ 2 transport retries = **7** | 24 + ≤ 4 = **28** | 35 |
| **provider expenditure** — every attempt at its settled cost, or unsettled at its maximum, × 1.1 (US-inference multiplier this key's workspace cannot be checked for) | **$2.40** (worst case 7 × $0.3299 = $2.309) | **$9.60** (28 × $0.3373 = $9.444) | **$12.00** |
| **wallet charges** — 1.5 × cost, never above a hold; the synthetic wallet is funded to the stage limit once | **$3.50** (7 × $0.4498 = $3.149) | **$13.00** (28 × $0.4598 = $12.878) | **$16.50** |
| expected | ≈ $0.50 provider, ≈ $0.75 charged | ≈ $2.40 / $3.60 | ≈ $2.90 / $4.35 |

Provider-side billing cannot be read with the generation key (the organization cost API refused it, 2026-09-17), so
every provider figure is configured-rate arithmetic over provider-reported token counts, never an invoice.

**Every attempt is accounted for.** The runner (`rebuild/ops/wm_narrative_campaign.py`) writes an O_EXCL, synced
attempt record BEFORE the hold and the request and an O_EXCL outcome after. An attempt with no outcome (a kill, a crash)
is recorded on the next start as `interrupted_unknown`, linked to the job the product created, counted at its maximum,
and never forgotten; every ORIGINAL request is captured as the product passes it to the SDK — in the campaign process
only, O_EXCL, before it is sent, with its canonical sha256 and the client's timeout and retries (a second request inside
one attempt fails on that record and is never sent) — and a replay manifest entry per attempt links the case, job,
notes hash, request, response and replay files by sha256 with the model, usage, costs and failure; a retried case always counts against the stage's retries. Before each attempt the worst case of
the whole ledger plus this attempt's maximum must fit the stage's and the campaign's limits. One runner per campaign
(an exclusive lock); live evidence has one fixed place per campaign id; a stage with a verdict is never re-run.
A captured request, or an attempt whose encounter the database does not hold, is never `not_run`: it is an unknown
outcome at its maximum (its wallet at its hold) and the stage stops; a campaign is bound to its database by its first
encounter's random id and is never resumed against another. No verdict is written while any attempt lacks its outcome,
its manifest entry or its score, or the records are not exported: the run ends `OPEN` (exit 6) with a dated open report,
and the next start records what is missing from the product and the durable ledger and re-derives every stop before
anything could be sent. A key found in the evidence still closes the stage `STOPPED`.

**Stops (nothing further is sent):** a wrong pre-filled answer or wrong pre-selected statement; a settled cost above its
quoted maximum or a charge above its hold; a job, receipt or usage row no attempt accounts for; another model or pricing
version; a configuration failure (400/401/403/404); two consecutive transport failures, or one once the retries are
used; any runner error. Retries only for a timeout, connection failure, 429 or 5xx, each after 60 s, never for an
answer. An adopted draft is scored and its page rendered before any stop, so a stopped stage keeps its evidence.
Pass: 0 wrong pre-filled answers and 0 wrong statements over every case; unnecessary holds and misses are reported.

**Where it runs:** one process, localhost only, from a clean detached checkout of the candidate with no `.env`, its own
throwaway synthetic Postgres (`quillmd_wmn_campaign*`), its own state directory, `QUILLMD_WM_NARRATIVE=1` in that
process only, umask 077. Production (`dedac162`, which carries no narrative code), public maintenance, MFA, records and
financial history are not touched.

**The key — no new key is needed.** The existing authorized delivery is the protected application configuration
(`/opt/meddoc-pro/rebuild/.env`), given to the hardened production units by systemd `EnvironmentFile=`; the recorded
precedent for reusing it elsewhere is `ops/backup_alerts.py`, a reviewed reader that takes only its allowlisted fields
under a declared act. Its recorded scope is the private services' own synthetic generation; nothing on record authorizes
a separate candidate process, so the reuse is part of the owner's authorization. The runner takes ONLY the provider
fields (key, provider, model, rates) into a scrubbed environment for its own process, refuses live mode BEFORE opening
the configuration unless a committed, unmodified declaration (`docs/foundation/mutations/`, run through
`scripts/run-ruled-mutation.sh`) names the campaign, stage, limits, model, pricing version and exactly one line
`authorization: owner <YYYY-MM-DD> approved stage <n> at the stated limits` with nothing after it (the owner's own words
go on an `owner_words:` line, recorded and never parsed; every line that reads as an authorization, in any case or
markdown, counts toward the one; any revocation word — `revok…`, `rescind`, `withdrew`/`withdraw…`, `cancel…` — anywhere
refuses; the path is read as a literal pathspec), never prints or copies the
key, and scans every evidence file for the key and key-shaped text before and after its report.

**Offline validation (no provider request possible):** `rebuild/ops/wm_narrative_campaign_offline.py` drives the real
runner end to end through the candidate's product path against a loopback mock (`ops/wm_narrative_mock_provider.py`,
retained careful responses) with a fixed non-secret marker instead of a key — see *Qualification* for its results.

**Stage 2** is a separate declaration and a separate authorization; the runner refuses it unless stage 1's verdict in
the same campaign is PASS. Enabling the flag for doctors stays a separate owner decision after the campaign.
