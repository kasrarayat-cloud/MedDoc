"""The documented-service reader on the wording of the wider GI catalogue (studio/gi/services.py, context.py).

Each text is a fresh synthetic paraphrase written for the case under test; the expected readings are written here,
outside the reader. None of them is a sentence the reader matches by its exact wording.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import NormalizedResponse
from studio.validation.engine import assess

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'


def read(text):
    facts = gi_context.extract_context(text)
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin == 'document' and fact.value else None
    return facts, services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)


def one(inv, family):
    found = [s for s in inv.services if s.family == family]
    assert len(found) == 1, f'{family}: {[(s.family, s.status) for s in inv.services]}'
    return found[0]


def kinds(svc, status='performed'):
    return sorted({a.kind for a in svc.acts if a.status == status})


class ServiceDateTests(SimpleTestCase):
    # Refutation phase 2 (P2DATES): a "Date:" line and a title are evidence (rule 2), and a table row is no header block
    # (rule 1): each date is asked, and read - the member's answer with it agrees; in a header block a label states it.
    def test_day_month_year_with_hyphens(self):
        facts, _ = read(HEAD + 'Endoscopy unit\nDate: 03-Nov-2026\nThe gastroscope was passed to the second part of '
                               'the duodenum.\n')
        self.assertEqual((facts['service_date'].value, facts['service_date'].origin), (None, 'missing'))
        self.assertEqual(gi_context._date_readings(facts['service_date'].evidence), {'2026-11-03'})
        facts, _ = read(HEAD + 'Endoscopy unit\nProcedure date: 03-Nov-2026\n\nThe gastroscope was passed.\n')
        self.assertEqual((facts['service_date'].value, facts['service_date'].origin), ('2026-11-03', 'document'))

    def test_a_labelled_date_in_a_table_row(self):
        facts, _ = read(HEAD + 'Field | Value\nProcedure date | 2026-09-30\nScope | adult colonoscope\n')
        self.assertEqual(gi_context._date_readings(facts['service_date'].evidence), {'2026-09-30'})
        self.assertEqual(facts['service_date'].origin, 'missing')

    def test_a_dated_note_title(self):
        facts, _ = read(HEAD + '\nHepatology clinic note - 9/28/2026\n\nSeen for ascites follow-up.\n')
        self.assertEqual(gi_context._date_readings(facts['service_date'].evidence), {'2026-09-28'})
        self.assertEqual(facts['service_date'].origin, 'missing')

    def test_a_dated_title_never_beats_a_labelled_date_and_a_qualified_one_is_no_date(self):
        facts, _ = read(HEAD + 'Office visit - 2026-09-01\nDate of service: 2026-09-02\n\nSeen today.\n')
        # Refutation round 2 (rule B, c2:1): the note's own dated title and its labelled date that differs are a
        # conflict - asked, both kept - never a silent choice of either (a planned procedure's labelled date had won
        # over a report's title this way, was sent, and an act done that day was excluded against it). This pin had
        # the labelled date win silently; the title still never beats it.
        fact = facts['service_date']
        self.assertEqual((fact.origin, set(gi_context.documented_values(fact))),
                         ('conflict', {'2026-09-01', '2026-09-02'}))
        facts, _ = read(HEAD + 'Previous visit - 2026-03-01\nSeen today for follow-up.\n')
        self.assertEqual(facts['service_date'].origin, 'missing')

    def test_a_report_date_and_a_birth_date_are_not_the_service_date(self):
        facts, _ = read(HEAD + 'Report date: 2026-10-30\nDate of birth: 1960-02-02\nSeen today.\n')
        self.assertEqual(facts['service_date'].origin, 'missing')


class DocumentPartTests(SimpleTestCase):
    TEXT = HEAD + """Date of service: 2026-10-14
PART 1 - CLINIC VISIT
Assessment: cirrhosis with ascites.
Plan:
- Adjust diuretics.
=====================================
PART 2 - PROCEDURE NOTE: ESOPHAGOGASTRODUODENOSCOPY WITH BAND LIGATION
=====================================
The gastroscope was passed to the second part of the duodenum. Three bands were deployed on the distal esophageal
varices. No biopsies were taken.
"""

    def test_a_numbered_part_never_inherits_the_previous_part_s_plan(self):
        _, inv = read(self.TEXT)
        egd = one(inv, 'gi.egd')
        self.assertEqual(egd.status, 'performed', egd.cues)
        self.assertIn('band_ligation', kinds(egd))
        self.assertIn('biopsy', kinds(egd, 'negated'))


class RoutingDisagreementTests(SimpleTestCase):
    def test_a_planned_repeat_never_makes_today_s_documented_acts_uncertain(self):
        text = HEAD + """Date of service: 2026-10-14
Colonoscopy
The scope reached the cecum. A 9 mm sigmoid polyp was resected with a hot snare.
Plan: repeat colonoscopy in three years.
"""
        _, inv = read(text)
        colon = one(inv, 'gi.colonoscopy')
        self.assertEqual(colon.status, 'performed', colon.cues)
        self.assertIn('snare', kinds(colon))

    def test_a_cancellation_in_today_s_report_still_holds(self):
        text = HEAD + """Date of service: 2026-10-14
Colonoscopy Report
Procedure: Colonoscopy was cancelled before the scope was inserted because the preparation was inadequate.
A cold snare polypectomy was performed.
"""
        _, inv = read(text)
        colon = one(inv, 'gi.colonoscopy')
        self.assertNotEqual(colon.status, 'performed', colon.cues)


class CompletionTests(SimpleTestCase):
    def test_an_insertion_statement_is_no_extent_and_no_incompleteness(self):
        text = HEAD + """Date of service: 2026-10-14
Colonoscopy Report
The colonoscope was inserted into the rectum and advanced under direct vision. Two 5 mm polyps in the transverse
colon were removed with a cold snare.
"""
        _, inv = read(text)
        colon = one(inv, 'gi.colonoscopy')
        self.assertEqual((colon.status, colon.completion), ('performed', 'unknown'))

    def test_a_checked_landmark_box_completes_a_colonoscopy(self):
        text = HEAD + """Date of service: 2026-10-14
Structured Colonoscopy Report
Furthest point reached: [X] Cecum   [ ] Terminal ileum   [ ] Other
Findings: one 4 mm polyp in the descending colon, removed with a cold snare.
"""
        _, inv = read(text)
        self.assertEqual(one(inv, 'gi.colonoscopy').completion, 'complete')

    def test_a_landmark_described_as_seen_completes_an_egd(self):
        text = HEAD + """Date of service: 2026-10-14
Upper endoscopy report
The gastroscope was introduced without difficulty.
Esophagus - normal. Stomach - mild erythema, biopsied with cold forceps. Duodenum - normal bulb and second portion.
"""
        _, inv = read(text)
        self.assertEqual(one(inv, 'gi.egd').completion, 'complete')

    def test_a_denied_landmark_never_completes(self):
        text = HEAD + """Date of service: 2026-10-14
Colonoscopy Report
The colonoscope could not be advanced to the cecum because of a fixed angulation in the sigmoid colon.
"""
        _, inv = read(text)
        self.assertNotEqual(one(inv, 'gi.colonoscopy').completion, 'complete')

    def test_an_esophagoscopy_reaching_only_the_esophagus_is_not_incomplete(self):
        text = HEAD + """Date of service: 2026-10-14
Office transnasal esophagoscopy
The esophagoscope was passed transnasally. The examination was confined to the esophagus by design; the scope was
not advanced past the gastroesophageal junction. Biopsies were taken at 38 cm with cold forceps.
"""
        _, inv = read(text)
        egd = one(inv, 'gi.egd')
        self.assertEqual((egd.kind, egd.status), ('esophagoscopy', 'performed'))

    def test_an_enteroscopy_short_of_the_ileum_is_not_incomplete(self):
        text = HEAD + """Date of service: 2026-10-14
Single-balloon enteroscopy report
The enteroscope was advanced about 150 cm beyond the ligament of Treitz into the mid jejunum; the ileum was not
reached. Two angioectasias were treated with argon plasma coagulation.
"""
        _, inv = read(text)
        entero = one(inv, 'gi.enteroscopy')
        self.assertEqual(entero.status, 'performed', entero.cues)
        self.assertIn('ablation', kinds(entero))


class FamilyTests(SimpleTestCase):
    def test_a_peg_is_an_egd_act_not_a_feeding_tube_service(self):
        text = HEAD + """Date of service: 2026-10-14
PERCUTANEOUS ENDOSCOPIC GASTROSTOMY - PROCEDURE RECORD
The gastroscope was passed to the second part of the duodenum. A 20 Fr gastrostomy tube was pulled through and
secured at 3 cm. Impression: successful PEG placement.
"""
        _, inv = read(text)
        self.assertFalse([s for s in inv.services if s.family == 'gi.feeding_tube' and s.status == 'performed'])
        self.assertIn('peg', kinds(one(inv, 'gi.egd')))

    def test_a_bedside_tube_replacement_is_a_feeding_tube_service(self):
        text = HEAD + """Date of service: 2026-10-14
Bedside note: gastrostomy tube replacement
The dislodged tube was examined. A new 18 Fr balloon tube was inserted through the existing mature tract and the
balloon was filled with 7 mL of water. No endoscopy or imaging was used.
"""
        _, inv = read(text)
        self.assertIn('tube_replacement', kinds(one(inv, 'gi.feeding_tube')))

    def test_an_egd_inside_an_eus_is_included_and_asks_for_no_code(self):
        text = HEAD + """Date of service: 2026-10-14
Upper endoscopy with endoscopic ultrasound
The gastroscope was passed to the second part of the duodenum; the stomach was normal.
The radial echoendoscope was then introduced and the examination was confined to the gastric wall. A 12 mm
hypoechoic lesion of the muscularis propria was seen. No fine-needle sampling was performed.
"""
        _, inv = read(text)
        egd, eus = one(inv, 'gi.egd'), one(inv, 'gi.eus')
        self.assertEqual(egd.included_in, eus.id)
        self.assertEqual(egd.status, 'performed')

    def test_anorectal_manometry_is_never_esophageal_motility(self):
        text = HEAD + """Date of service: 2026-10-14
Anorectal physiology laboratory
Study: anorectal manometry with balloon expulsion test
Manometry
- Resting pressure 60 mmHg.
"""
        _, inv = read(text)
        self.assertFalse([s for s in inv.services if s.family == 'gi.motility' and s.status == 'performed'])
        self.assertIn('manometry', kinds(one(inv, 'gi.anorectal')))

    def test_a_physiology_part_with_a_digit_in_its_heading_is_its_own_report(self):
        text = HEAD + """Date of service: 2026-10-14
PART A - HIGH-RESOLUTION ESOPHAGEAL MANOMETRY
A 36-sensor catheter was placed transnasally and ten swallows were recorded.
PART B - 24-HOUR pH-IMPEDANCE MONITORING
A combined pH-impedance catheter was then passed transnasally and the recording lasted 23 hours.
"""
        _, inv = read(text)
        self.assertIn('ph_monitoring', kinds(one(inv, 'gi.reflux')))

    def test_an_unnamed_endoscope_in_the_upper_gi_tract_is_an_egd(self):
        text = HEAD + """Date of service: 2026-10-14
Therapeutic endoscopy report
An ultraslim endoscope was then used; the stomach and duodenum to the second portion were examined and were normal.
A covered metal stent was deployed across the distal esophageal stricture.
"""
        _, inv = read(text)
        egd = one(inv, 'gi.egd')
        self.assertEqual(egd.status, 'performed')
        self.assertIn('stent', kinds(egd))


class ActWordingTests(SimpleTestCase):
    def _egd(self, body):
        _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nUpper endoscopy report\n' + body)
        return one(inv, 'gi.egd')

    def test_moderate_sedation_by_the_endoscopist(self):
        egd = self._egd('Sedation: moderate sedation was given by me with an independent trained observer; intraservice '
                        'time 17 minutes.\nThe gastroscope was passed to the second part of the duodenum.\n')
        self.assertIn('moderate_sedation', kinds(egd))

    def test_a_balloon_inflated_across_a_ring_is_a_dilation(self):
        egd = self._egd('The gastroscope was passed to the duodenum.\nImpression:\n1. Lower esophageal ring at 38 cm, '
                        'disrupted with a through-the-scope balloon inflated to 18 mm.\n')
        self.assertIn('dilation', kinds(egd))

    def test_a_guidewire_named_for_a_dilator_is_not_the_dilation(self):
        egd = self._egd('The gastroscope was passed to the duodenum. A Savary guidewire was positioned in the gastric '
                        'antrum. Dilators of 14 and 15 mm were then advanced over the wire.\n')
        dilations = [a for a in egd.acts if a.kind == 'dilation' and a.status == 'performed']
        self.assertTrue(dilations)
        self.assertFalse([a for a in dilations if 'gastric antrum' in a.anatomy])

    def test_submucosal_dissection_without_the_word_endoscopic(self):
        egd = self._egd('The gastroscope was passed to the duodenum. Submucosal dissection was carried out with a '
                        'needle-type knife and the antral lesion was removed en bloc.\n')
        self.assertIn('esd', kinds(egd))

    def test_closure_clips_and_a_stent_named_as_a_place(self):
        egd = self._egd('The gastroscope was passed to the duodenum. A covered metal stent was deployed across the '
                        'stricture. The scope was not passed through the newly deployed stent. The mucosal entry was '
                        'closed with four clips.\n')
        self.assertIn('stent', kinds(egd))
        self.assertNotIn('stent', kinds(egd, 'negated'))
        self.assertIn('clip', kinds(egd))

    def test_a_limit_on_further_sampling_is_not_a_denied_biopsy(self):
        _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nUpper endoscopy report\nThe gastroscope was passed to the '
                             'duodenum. Antral biopsies were taken with cold forceps. No tissue was sampled beyond the '
                             'containers listed above.\n')
        self.assertEqual(inv.conflicts, ())


class ErcpTests(SimpleTestCase):
    TEXT = HEAD + """Date of service: 2026-10-14
ERCP report
History: an outside EUS-guided biopsy showed adenocarcinoma.
The duodenoscope was advanced to the papilla. Deep cannulation of the bile duct was obtained on the second attempt.
A 10 mm by 60 mm covered metal stent was then deployed across the distal stricture.
"""

    def test_an_attempt_counted_to_its_success_and_an_outside_study(self):
        _, inv = read(self.TEXT)
        ercp = one(inv, 'gi.ercp')
        self.assertIn('cannulation', kinds(ercp))
        self.assertIn('stent', kinds(ercp))
        self.assertEqual(ercp.completion, 'complete')
        self.assertFalse([s for s in inv.services if s.family == 'gi.eus' and s.status == 'performed'])


class AttributionTests(SimpleTestCase):
    def roles(self, sentence):
        _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nColonoscopy report\nThe colonoscope reached the cecum.\n'
                      + sentence + '\n')
        return {a.role for a in inv.attributions}

    def test_other_providers(self):
        self.assertIn('anesthesia', self.roles('Sedation: propofol given by a nurse anesthetist from a separate '
                                               'anesthesia group; billed separately.'))
        self.assertIn('anesthesia', self.roles('Anesthesia: MAC by the department of anesthesiology.'))
        self.assertIn('pathology', self.roles('Specimens: two jars (cecum; rectum) to Fictional Valley Pathology.'))
        self.assertIn('facility', self.roles('The hospital reports the technical component.'))
        self.assertIn('radiology', self.roles('Fluoroscopy images were interpreted by Dr. Fictional, radiology.'))

    def test_a_denied_other_provider_is_not_attributed(self):
        self.assertNotIn('anesthesia', self.roles('No anesthesia professional was involved; moderate sedation was '
                                                  'given by me.'))
        self.assertNotIn('pathology', self.roles('No specimens were sent to pathology.'))


class ConflictTests(SimpleTestCase):
    TEXT = HEAD + """Date of service: 2026-10-14
Flexible sigmoidoscopy report
The sigmoidoscope was advanced to 45 cm. Three internal hemorrhoid columns were ligated with rubber bands.
No biopsies were obtained.
NURSING PROCEDURE RECORD
Specimen collected   [X] Yes   [ ] No
"""

    def test_a_recorded_specimen_beside_a_denied_biopsy_is_a_conflict(self):
        _, inv = read(self.TEXT)
        self.assertEqual([c.subject for c in inv.conflicts], ['biopsy'])
        self.assertEqual({side.role for side in inv.conflicts[0].sides}, {'nursing', 'physician'})

    def test_a_recorded_specimen_beside_a_removed_polyp_is_that_polyp_s(self):
        text = self.TEXT.replace('No biopsies were obtained.', 'A 6 mm rectal polyp was removed with a cold snare. No '
                                                               'biopsies were obtained.')
        _, inv = read(text)
        self.assertEqual(inv.conflicts, ())


class SentenceTests(SimpleTestCase):
    def test_a_wrapped_field_value_stays_one_sentence(self):
        text = HEAD + ('Date of service: 2026-10-14\n\nColonoscopy report\nThe colonoscope reached the cecum.\n'
                       'Rectum: a separate 4 mm flat lesion was sampled with cold forceps for\nhistology (jar C).\n')
        _, inv = read(text)
        lesion = next(l for l in one(inv, 'gi.colonoscopy').lesions if l.anatomy == 'rectum')
        self.assertEqual(lesion.specimen, 'C')


class EngineReleaseTests(SimpleTestCase):
    def test_an_unresolved_negation_the_inventory_reads_as_completion_never_holds(self):
        from studio.types import EvidenceSpan, ProviderCode
        text = HEAD + """Date of service: 2026-10-14

Colonoscopy Report
The colonoscope was advanced to the cecum. The examination was complete and was not discontinued.
A 7 mm polyp in the descending colon was removed with a cold snare.
"""
        quotes = ['The examination was complete and was not discontinued.', 'was removed with a cold snare']
        spans = tuple(EvidenceSpan(0, text.index(q), text.index(q) + len(q), q, True) for q in quotes)
        facts = gi_context.extract_context(text)
        day = date(2026, 10, 14)
        result = assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                        normalized=NormalizedResponse('replay', 'test@1', (
                            ProviderCode('selected', 'cpt', '45385', 'UNVERIFIED PROVIDER WORDING', spans),)),
                        reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')
        code = next(p for p in result.proposals if p.code == '45385')
        self.assertEqual(code.status, 'ready', [(c.id, c.detail) for c in code.checks if c.status != 'pass'])


class NegationScopeTests(SimpleTestCase):
    """A "not" that governs another predicate never denies the act; every other one still does (fail-closed)."""

    def test_a_negation_on_another_predicate_leaves_the_act(self):
        _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nColonoscopy report\nThe colonoscope was advanced to the '
                             'cecum. A 30 mm laterally spreading lesion in the ascending colon was tattooed and not '
                             'removed; it is referred for EMR.\n')
        self.assertIn('tattoo', kinds(one(inv, 'gi.colonoscopy')))
        _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nColonoscopy report\nThe colonoscope was advanced to the '
                             'cecum. Biopsies of the sigmoid colon were obtained and a dilation was not performed.\n')
        svc = one(inv, 'gi.colonoscopy')
        self.assertIn('biopsy', kinds(svc))
        self.assertIn('dilation', kinds(svc, 'negated'))

    def test_a_negation_in_a_subordinate_clause_leaves_the_mention(self):
        _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nOffice visit\nPlan: possible EGD with PEG placement if '
                             'oral intake does not improve.\n')
        egd = [s for s in inv.services if s.family == 'gi.egd']
        self.assertTrue(all(s.status != 'negated' for s in egd), [(s.status, s.cues) for s in egd])

    def test_controls_a_negation_of_the_act_itself_still_denies_it(self):
        for line, kind in (('Biopsies were not obtained.', 'biopsy'), ('The polyp was not removed with a snare.', 'snare'),
                           ('Cold forceps biopsy was not performed because of anticoagulation.', 'biopsy')):
            with self.subTest(line=line):
                _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nColonoscopy report\nThe colonoscope was advanced to '
                                     'the cecum. ' + line + '\n')
                svc = one(inv, 'gi.colonoscopy')
                self.assertNotIn(kind, kinds(svc))
        _, inv = read(HEAD + 'Date of service: 2026-10-14\n\nOffice visit\nThe patient did not undergo EGD today.\n')
        self.assertTrue(all(s.status not in services.POSITIVE for s in inv.services if s.family == 'gi.egd'))


class MemberConflictQuestionTests(SimpleTestCase):
    """A member's encounter metadata that conflicts with the document is asked once, as that conflict, with both sides;
    never as an undocumented fact, and never left unasked when no proposal asks about it."""

    def test_a_conflicting_setting_is_asked_at_the_encounter(self):
        for body in ('Place of service: 11 - Office\nGastroenterology office visit for heartburn.\n',
                     'Gastroenterology office visit for heartburn.\n'):
            text = HEAD + 'Date of service: 2026-10-20\n\n' + body
            facts = gi_context.merge_user_values(gi_context.extract_context(text), {'setting': 'asc'})
            day = date(2026, 10, 20)
            result = assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                            normalized=NormalizedResponse('replay', 'test@1', ()),
                            reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')
            with self.subTest(body=body):
                asked = [c for c in result.clarifications if c.fact == 'setting']
                self.assertEqual(len(asked), 1)
                self.assertEqual(asked[0].scope, 'encounter')
                self.assertIn('gives asc; the document gives office', asked[0].reason)
                self.assertNotIn('does not state its setting', ' '.join(c.reason for c in result.clarifications))


class UnknownDateTests(SimpleTestCase):
    def test_a_dated_act_statement_is_held_without_a_service_date(self):
        # an undated note: the dated colonoscopy cannot be placed in time, so it is never read as performed today
        _, inv = read(HEAD + 'Gastroenterology office visit.\nResults reviewed\nColonoscopy 2026-09-03: a 6 mm '
                             'sigmoid polyp was removed with a cold snare.\nEstablished patient, seen for constipation.\n')
        colon = [s for s in inv.services if s.family == 'gi.colonoscopy']
        self.assertTrue(colon and all(s.status not in services.POSITIVE for s in colon),
                        [(s.status, s.cues) for s in colon])


def _assess(text, picks, day=date(2026, 10, 21)):
    """The engine's result for provider-selected (code, quote) picks against an empty reference."""
    from studio.types import EvidenceSpan, ProviderCode
    codes = []
    for code, quote in picks:
        start = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(quote), quote, True),)))
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def _proposal(result, code):
    return next(p for p in result.proposals if p.code == code)


def _unresolved(result):
    return [(u.get('act'), u.get('reason')) for u in (result.completeness or {}).get('unresolved_items', [])]


class HypotheticalWordingTests(SimpleTestCase):
    """A predicate under a modal states nothing done (routing:18): an act or a service under a perfect or a conditional
    modal, a recommendation or a possibility, or inside a condition that opens its clause, reads uncertain with a
    non-silent cue - never performed - so it is no unresolved act (no paid second review) and no act a diagnostic code
    leaves unreported; an act verb the clause states for itself still reads, and a hypothetical reach completes nothing."""

    EGD = (HEAD + 'Date of service: 2026-10-21\n\nProcedure: EGD\nFindings: The gastroscope was passed to the second part '
           'of the duodenum. The mucosa looked normal. {sentence}\n')
    GASTRO = 'The gastroscope was passed to the second part of the duodenum.'

    def test_a_hypothetical_act_reads_uncertain(self):
        for sentence, kind in (('Were a ring present, it would have been dilated with a balloon.', 'dilation'),
                               ('Gastric biopsies could have been obtained but were judged unnecessary.', 'biopsy'),
                               ('The ring would have been treated with balloon dilation had it been tight.', 'dilation'),
                               ('If biopsies were taken, they would be labelled by site.', 'biopsy'),
                               ('Biopsies of the antrum should be obtained per protocol.', 'biopsy')):
            text = self.EGD.format(sentence=sentence)
            with self.subTest(sentence=sentence):
                _, inv = read(text)
                egd = one(inv, 'gi.egd')
                self.assertNotIn(kind, kinds(egd))
                act = next(a for a in egd.acts if a.kind == kind)
                self.assertEqual(act.status, 'uncertain')
                self.assertTrue(act.cues[0].startswith(services.HYPOTHETICAL_CUE), act.cues)
                result = _assess(text, [('43235', self.GASTRO)])
                self.assertEqual(_proposal(result, '43235').status, 'ready')
                self.assertEqual(_unresolved(result), [])

    def test_an_act_verb_the_clause_states_still_reads(self):
        for sentence, kind in (('Biopsies were taken from the antrum and would be sent for H. pylori testing.', 'biopsy'),
                               ('The ring was dilated with an 18 mm balloon; a second dilation would have been performed '
                                'had it persisted.', 'dilation'),
                               ('Biopsies, which would be sent to pathology, were taken from the antrum.', 'biopsy'),
                               ('Balloon dilation was performed, which would have been difficult without fluoroscopy.',
                                'dilation')):
            text = self.EGD.format(sentence=sentence)
            with self.subTest(sentence=sentence):
                _, inv = read(text)
                self.assertIn(kind, kinds(one(inv, 'gi.egd')))
                result = _assess(text, [('43235', self.GASTRO)])
                self.assertEqual(_proposal(result, '43235').status, 'needs_clarification')  # base_included, as before
                self.assertIn((kind, 'not_covered'), _unresolved(result))  # still named: no missed service is hidden

    def test_a_hypothetical_reach_completes_nothing(self):
        for findings in ('The colonoscope would have been advanced to the cecum had the preparation been adequate.',
                         'The colonoscope was inserted into the rectum. It would have been passed to the cecum, but the '
                         'preparation was poor.'):
            with self.subTest(findings=findings):
                _, inv = read(HEAD + f'Date of service: 2026-10-21\n\nProcedure: Colonoscopy\nFindings: {findings}\n')
                self.assertNotEqual(one(inv, 'gi.colonoscopy').completion, 'complete')
        _, inv = read(HEAD + 'Date of service: 2026-10-21\n\nProcedure: Colonoscopy\nFindings: The colonoscope was passed '
                             'to the cecum and would have been advanced into the ileum had the valve allowed.\n')
        self.assertEqual(one(inv, 'gi.colonoscopy').completion, 'complete')

    def test_an_office_note_s_modal_service_is_no_missed_service(self):
        office = (HEAD + 'Date of service: 2026-10-21\n\nPlace of service: Office (POS 11)\nEstablished patient office '
                  'visit for dysphagia.\nAssessment: Dysphagia. {sentence}\nMedical decision making: moderate.\n')
        for sentence in ('EGD with biopsy would be done if the dysphagia persists.', 'EGD should be done.',
                         'If an EGD were done today, the sedation risk would be high.',
                         'An EGD would have been performed had the dysphagia persisted.'):
            text = office.format(sentence=sentence)
            with self.subTest(sentence=sentence):
                # the reader's own reading, without routing's family doubt
                inv = services.build(text, service_date=date(2026, 10, 21), routing=None,
                                     context_facts=gi_context.extract_context(text))
                egd = one(inv, 'gi.egd')
                self.assertEqual(egd.status, 'uncertain', egd.cues)
                self.assertTrue(egd.cues[0].startswith(services.HYPOTHETICAL_CUE), egd.cues)
                result = _assess(text, [('99214', 'Established patient office visit for dysphagia.')])
                self.assertEqual(_unresolved(result), [])  # no unresolved EGD, so no second review is asked for

    def test_a_listing_or_its_report_never_promotes_a_hypothetical(self):
        day = date(2026, 10, 21)
        # a procedure line lists the service: the reader's own reading (routing=None) keeps the modal predicate
        text = (HEAD + 'Date of service: 2026-10-21\n\nProcedures: EGD; colonoscopy would have been performed had the '
                'preparation been adequate.\nFindings: The gastroscope was passed to the second part of the duodenum.\n')
        inv = services.build(text, service_date=day, routing=None, context_facts=gi_context.extract_context(text))
        self.assertEqual(one(inv, 'gi.colonoscopy').status, 'uncertain')
        # ... or an act
        _, inv = read(HEAD + 'Date of service: 2026-10-21\n\nProcedure: EGD; balloon dilation would be performed for any '
                             'stricture.\nFindings: The gastroscope was passed to the second part of the duodenum.\n')
        egd = one(inv, 'gi.egd')
        self.assertNotIn('dilation', kinds(egd))
        self.assertIn('dilation', kinds(egd, 'uncertain'))
        # inside its own report the hypothetical sentence documents nothing of the service
        sentence = 'Colonoscopy would have been completed sooner had the preparation been adequate.'
        _, inv = read(HEAD + 'Date of service: 2026-10-21\n\nCOLONOSCOPY REPORT\nThe colonoscope was advanced to the cecum. '
                      + sentence + '\n')
        self.assertNotIn(sentence, [e.text for e in one(inv, 'gi.colonoscopy').evidence])

    def test_a_plan_line_keeps_its_planned_reading(self):
        _, inv = read(HEAD + 'Date of service: 2026-10-21\n\nPlace of service: Office (POS 11)\nEstablished patient office '
                             'visit for dysphagia.\nAssessment: Dysphagia.\nPlan: EGD should be done.\n')
        self.assertEqual(one(inv, 'gi.egd').status, 'planned')


class IntentTests(SimpleTestCase):
    """A service's intent is read like its extent. For a family routing reads it is routing's intent (today's indication
    and procedure text only: never a question, a hedge, a pending confirmation, a denial, a plan or a history; routing
    reads it for a colonoscopy), so the words of another service's intent are never this one's; for a family routing
    does not read, the reader's own intent words are read with the same doubts. A doubted intent is no screening
    intent, so no screening-became-therapeutic consideration is raised for it."""

    COLON = (HEAD + 'Date of service: 2026-10-21\n\nIndication: {indication}\nProcedure: Colonoscopy\nFindings: The '
             'colonoscope was passed to the cecum. A 4 mm sigmoid polyp was removed with a cold snare.\n')
    SNARE = 'A 4 mm sigmoid polyp was removed with a cold snare.'
    LOWER = (HEAD + 'Date of service: 2026-10-21\n\nLOWER ENDOSCOPY REPORT\nIndication: {indication}\nThe colonoscope was '
             'passed to the cecum. The colon was normal.\n')

    def screening_consideration(self, text):
        code = _proposal(_assess(text, [('45385', self.SNARE)]), '45385')
        return any('documented intent is screening' in c for c in code.modifier_considerations)

    def test_a_doubted_denied_or_planned_intent_states_none(self):
        for indication in ('Could this be a screening colonoscopy? Rectal bleeding for a month.',
                           'Possibly a screening colonoscopy.',
                           'Screening colonoscopy, still to be confirmed with the referring clinic.',
                           'Non-screening colonoscopy for rectal bleeding.',
                           'Rectal bleeding for a month.\nPlan: Surveillance colonoscopy in three years.'):
            text = self.COLON.format(indication=indication)
            with self.subTest(indication=indication):
                _, inv = read(text)
                self.assertEqual(one(inv, 'gi.colonoscopy').intent, '')
                self.assertFalse(self.screening_consideration(text))

    def test_a_service_routing_does_not_read_as_done_takes_no_intent_from_its_plan(self):
        # routing reads a planned or doubted colonoscopy's intent from the plan; today's service never takes it
        text = (HEAD + 'Date of service: 2026-10-21\n\nProcedure: Colonoscopy?\nFindings: A 4 mm sigmoid polyp was removed '
                'with a cold snare.\nPlan: Screening colonoscopy in 10 years.\n')
        self.assertEqual(detect.route(text, date(2026, 10, 21)).finding('gi.colonoscopy').status, 'uncertain')
        _, inv = read(text)
        self.assertEqual(one(inv, 'gi.colonoscopy').intent, '')

    def test_a_stated_intent_is_kept(self):
        text = self.COLON.format(indication='Average-risk screening colonoscopy.')
        _, inv = read(text)
        self.assertEqual(one(inv, 'gi.colonoscopy').intent, 'screening')
        self.assertTrue(self.screening_consideration(text))
        _, inv = read(self.COLON.format(indication='Surveillance colonoscopy; adenomas were removed in 2019.'))
        self.assertEqual(one(inv, 'gi.colonoscopy').intent, 'surveillance')

    def test_another_service_takes_no_intent_from_the_colonoscopy_s_words(self):
        text = (HEAD + 'Date of service: 2026-10-21\n\nIndication: Average-risk screening colonoscopy; epigastric pain.\n'
                'Procedures: EGD and colonoscopy\nFindings: The gastroscope was passed to the second part of the '
                'duodenum and gastric biopsies were taken. The colonoscope was passed to the cecum. The colon was '
                'normal.\n')
        _, inv = read(text)
        self.assertEqual(one(inv, 'gi.colonoscopy').intent, 'screening')
        self.assertEqual(one(inv, 'gi.egd').intent, '')
        code = _proposal(_assess(text, [('43239', 'gastric biopsies were taken')]), '43239')
        self.assertFalse(any('documented intent is screening' in c for c in code.modifier_considerations))

    def test_where_routing_reads_no_family_the_reader_s_own_words_keep_their_doubts(self):
        for indication, intent in (('Average-risk screening examination.', 'screening'),
                                   ('Could this be a screening examination? Rectal bleeding.', ''),
                                   ('Screening examination, to be confirmed with the referring clinic.', ''),
                                   ('Rectal bleeding.\nPlan: Screening examination again in ten years.', '')):
            text = self.LOWER.format(indication=indication)
            with self.subTest(indication=indication):
                _, inv = read(text)
                self.assertIsNone(detect.route(text, date(2026, 10, 21)).finding('gi.colonoscopy'))
                self.assertEqual(one(inv, 'gi.colonoscopy').intent, intent)


class BoxAndFieldRowTests(SimpleTestCase):
    """Check-box rows and form fields as the documented-service reader reads them (the boxes_text triage of the GI core
    repair). A row's own reading is never overruled by the line it is on, a field's answer - never a participle in its
    label - states its item, and a checked box documents its act only in a list of what was done."""
    REPORT = HEAD + ('Date of service: 2026-10-14\n\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to '
                     'the cecum. No polyps were seen.\n{rows}\n')
    CECUM = 'The colonoscope was advanced to the cecum.'

    def assess_codes(self, text, *picks):
        from studio.types import EvidenceSpan, ProviderCode
        codes = []
        for code, phrase in picks:
            start = text.index(phrase)
            codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                      (EvidenceSpan(0, start, start + len(phrase), phrase, True),)))
        facts = gi_context.extract_context(text)
        day = date(2026, 10, 14)
        result = assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                        normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                        reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')
        return {p.code: p for p in result.proposals}, result

    def test_an_unmarked_row_on_a_procedure_line_documents_no_act(self):
        """"Interventions: ☐ Hot snare ☐ Biopsy" read as a done snare and biopsy ("listed on the procedure line"): codes
        citing the cecum sentence were ready, and a diagnostic code alone listed both as unresolved."""
        for row in ('Interventions: ☐ Hot snare ☐ Biopsy', 'Interventions: [ ] Cold snare polypectomy [ ] Biopsy'):
            with self.subTest(row=row):
                text = self.REPORT.format(rows=row)
                _, inv = read(text)
                self.assertEqual(kinds(one(inv, 'gi.colonoscopy')), [])
                proposals, _ = self.assess_codes(text, ('45380', self.CECUM), ('45385', self.CECUM))
                self.assertEqual({code: p.status for code, p in proposals.items()},
                                 {'45380': 'needs_clarification', '45385': 'needs_clarification'})
                _, result = self.assess_codes(text, ('45378', 'Colonoscopy'))
                self.assertEqual(result.completeness['unresolved_items'], [])

    def test_a_field_s_answer_states_its_item(self):
        """"Biopsy taken: No" and "Tattoo placed: None" read as a performed biopsy and tattoo (the participle in the
        label); "Biopsy: Yes" in a form-field block read as nothing at all."""
        block = '\n[PDF form fields on page 1]\n{fields}\n'
        fields = 'Biopsy taken: No\nTattoo placed: None'
        for typed in (False, True):
            with self.subTest(fields=fields, typed=typed):
                text = self.REPORT.format(rows=fields if typed else block.format(fields=fields))
                colon = one(read(text)[1], 'gi.colonoscopy')
                self.assertEqual((kinds(colon), kinds(colon, 'negated')), ([], ['biopsy', 'tattoo']))
        # A "Yes" or "checked" field documents its act only through the printed item it names in a list of what was
        # done (the owner's strict-box decision, 2026-10-25; triage round 2 skeptic: a "Biopsy: Yes" answering a printed
        # "Biopsy recommended at follow-up?" had been read as a done biopsy and sent for a paid second review). Alone, it
        # is a doubt for the reviewer, never a done act and never nothing at all.
        text = self.REPORT.format(rows=block.format(fields='Biopsy: Yes'))
        colon = one(read(text)[1], 'gi.colonoscopy')
        self.assertEqual((kinds(colon), kinds(colon, 'uncertain')), ([], ['biopsy']))
        for printed in ('Biopsy recommended at follow-up?   Yes   No', 'Consent obtained for: Biopsy',
                        'Discussed with patient: Biopsy'):
            with self.subTest(printed=printed):
                colon = one(read(self.REPORT.format(rows=printed + '\n' + block.format(fields='Biopsy: Yes')))[1],
                            'gi.colonoscopy')
                self.assertEqual(kinds(colon), [])
        listed = self.REPORT.format(rows='Interventions:\nBiopsy\n' + block.format(fields='Biopsy: Yes'))
        self.assertEqual(kinds(one(read(listed)[1], 'gi.colonoscopy')), ['biopsy'])
        # a question that names the item among other words holds it, never denies or performs it
        for fields in ('Biopsy (Y/N): N', 'Biopsy in the last 10 years: Yes', 'Biopsy in the last 10 years: No'):
            with self.subTest(fields=fields):
                colon = one(read(self.REPORT.format(rows=block.format(fields=fields)))[1], 'gi.colonoscopy')
                self.assertEqual((kinds(colon), kinds(colon, 'negated')), ([], []))

    def test_an_unanswered_label_takes_its_tied_field_s_answer_or_its_words(self):
        """A printed "Biopsy taken:" answered "No" in its page's form fields is denied with it, never a done biopsy in
        conflict with the field; a label over a list of sites still states the act; a passage read whole is no field."""
        text = self.REPORT.format(rows='Interventions:\nBiopsy taken:\n\n[PDF form fields on page 1]\nBiopsy taken: No')
        colon = one(read(text)[1], 'gi.colonoscopy')
        self.assertEqual((kinds(colon), kinds(colon, 'negated')), ([], ['biopsy']))
        self.assertEqual(read(text)[1].conflicts, ())
        listed = self.REPORT.format(rows='Biopsies taken:\n- sigmoid colon x2\n- rectum x1')
        self.assertEqual(kinds(one(read(listed)[1], 'gi.colonoscopy')), ['biopsy'])
        start = text.index('Biopsy taken:')
        self.assertTrue(services.current_statement(text, start, start + len('Biopsy taken:'), date(2026, 10, 14)))

    def test_a_checked_box_documents_its_act_only_in_a_list_of_what_was_done(self):
        """Routing finds a checked box silent where its section gives no default: under "Interventions:" (or standing
        alone) the box is the row's one marked option and its act was done; under a consent or risks label it is not."""
        for rows in ('Interventions:\n[ ] Biopsy\n(x) Cold snare polypectomy',
                     'Interventions:\n☒ Cold snare polypectomy'):
            with self.subTest(rows=rows):
                self.assertEqual(kinds(one(read(self.REPORT.format(rows=rows))[1], 'gi.colonoscopy')), ['snare'])
        for rows in ('Consent obtained for:\n☒ Biopsy\n☒ Cold snare polypectomy',
                     'Informed consent: ☒ Biopsy ☒ Cold snare polypectomy',
                     'Risks discussed for:\n[x] Cold snare polypectomy'):
            with self.subTest(rows=rows):
                text = self.REPORT.format(rows=rows)
                self.assertEqual(kinds(one(read(text)[1], 'gi.colonoscopy')), [])
                proposals, result = self.assess_codes(text, ('45385', self.CECUM))
                self.assertEqual(proposals['45385'].status, 'needs_clarification')
                _, result = self.assess_codes(text, ('45378', 'Colonoscopy'))
                self.assertEqual(result.completeness['unresolved_items'], [])

    def test_a_screening_question_is_no_service_heading(self):
        """"Colonoscopy in the last 10 years:" printed on an office form read as a bare colonoscopy heading, so the
        visit documented a colonoscopy performed today: listed unresolved, and sent for a second review, where the note
        documents none."""
        note = HEAD + ('Date of service: 2026-10-14\n\nPlace of service: Office\nEstablished patient office visit for '
                       'dyspepsia.\nChief complaint: Dyspepsia.\nMedical decision making: low.\n{line}\n')
        # and the questions' other wordings (triage round 2 skeptic): a label line names a service and heading words only
        for line in ('Colonoscopy in the last 10 years:', 'Upper endoscopy within the last 3 years:',
                     'Flexible sigmoidoscopy in the past 5 years:', 'Colonoscopy within 10 years:',
                     'Colonoscopy (last 10 yrs):', 'Colonoscopy since 2016:', 'Colonoscopy ever:',
                     'Colonoscopy up to date:', 'Colonoscopy due:', 'Upper endoscopy within 3 years:'):
            with self.subTest(line=line):
                text = note.format(line=line)
                _, inv = read(text)
                self.assertEqual([s.family for s in inv.services if s.status in services.POSITIVE], ['gi.office_em'])
                _, result = self.assess_codes(text, ('99214', 'Established patient office visit for dyspepsia.'))
                self.assertEqual(result.completeness['unresolved_items'], [])


class FormOptionLineTests(SimpleTestCase):
    """An extraction block writes each option of a printed question as its own field line ("Biopsy taken: no:
    checked"): the checked option decides the item, never the participle in the label; an unmarked option says
    nothing. Outside an extraction block the rule does not apply."""

    REPORT = (HEAD + 'Date of service: 2026-10-14\n\nColonoscopy report\nThe colonoscope was advanced to the cecum.\n'
              'Cold snare polypectomy of a 6 mm sigmoid polyp was performed.\n\n[PDF form fields on page 1]\n'
              'Biopsy taken: yes: {yes}\nBiopsy taken: no: {no}\n')

    def test_the_checked_option_decides(self):
        _, inv = read(self.REPORT.format(yes='not checked', no='checked'))
        self.assertNotIn('biopsy', kinds(one(inv, 'gi.colonoscopy')))
        self.assertIn('biopsy', kinds(one(inv, 'gi.colonoscopy'), 'negated'))
        _, inv = read(self.REPORT.format(yes='checked', no='not checked'))
        self.assertNotIn('biopsy', kinds(one(inv, 'gi.colonoscopy'), 'negated'))


class ConsentObjectTests(SimpleTestCase):
    """What a consent, an authorization or an approval is for is named, never stated done: the predicate of "Consent was
    obtained for biopsy" is the consent's (session bc7df129: read as a done biopsy and snare removal, the codes were
    ready on the cecum sentence and a paid second review was queued for acts the report never states). Held, never
    excluded; an act with a predicate of its own is still done."""

    REPORT = HEAD + ('Date of service: 2026-10-14\n\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to '
                     'the cecum. A 6 mm sigmoid polyp was seen.\n{line}\n')

    def test_what_a_consent_is_for_is_not_done(self):
        for line in ('Consent was obtained for biopsy and cold snare polypectomy.',
                     'Written consent for biopsy and cold snare polypectomy was obtained.',
                     'Consent obtained for: Biopsy   Cold snare polypectomy',
                     'Informed consent was given for biopsy, cold snare polypectomy and tattoo.',
                     'Biopsy consent was obtained.',
                     'Informed consent was obtained after explaining the risks of biopsy and cold snare polypectomy, '
                     'including bleeding and perforation.'):
            with self.subTest(line=line):
                colon = one(read(self.REPORT.format(line=line))[1], 'gi.colonoscopy')
                self.assertEqual(kinds(colon), [])
                self.assertIn('biopsy', kinds(colon, 'uncertain'))
                self.assertEqual(kinds(colon, 'negated'), [])

    def test_an_act_with_its_own_predicate_is_done(self):
        for line in ('Consent was obtained for colonoscopy and biopsies were taken from the sigmoid polyp.',
                     'Biopsies were obtained after consent was given.',
                     'After informed consent was obtained, biopsies were taken from the sigmoid polyp.',
                     'After consent was obtained, biopsies were taken from the sigmoid polyp.'):
            with self.subTest(line=line):
                colon = one(read(self.REPORT.format(line=line))[1], 'gi.colonoscopy')
                self.assertEqual(kinds(colon), ['biopsy'])

    def test_an_authorization_in_an_office_note_documents_no_service(self):
        note = HEAD + ('Date of service: 2026-10-14\n\nPlace of service: Office\nEstablished patient office visit for '
                       'rectal bleeding.\nChief complaint: Rectal bleeding.\nMedical decision making: moderate.\n{line}\n')
        for line in ('Prior authorization was obtained for colonoscopy.', 'Consent was obtained for colonoscopy.',
                     'Insurance approval was received for capsule endoscopy.'):
            with self.subTest(line=line):
                _, inv = read(note.format(line=line))
                self.assertEqual([s.family for s in inv.services if s.status in services.POSITIVE], ['gi.office_em'])


class SnareSiteTests(SimpleTestCase):
    """"The polypectomy site was clipped" names a place, not a snare removal; a checked snare line followed by a "Site:"
    field on the next line still documents the snare (boxes_pdf skeptic: the place rule read across the line break and
    dropped the act, which hid a missed service)."""

    REPORT = HEAD + ('Date of service: 2026-10-14\n\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to '
                     'the cecum. A 6 mm sigmoid polyp was seen.\nInterventions:\n{rows}\n')

    def test_a_site_field_on_the_next_line_keeps_the_snare(self):
        colon = one(read(self.REPORT.format(rows='\u2612 Cold snare polypectomy\nSite: sigmoid colon'))[1], 'gi.colonoscopy')
        self.assertIn('snare', kinds(colon))

    def test_the_polypectomy_site_is_a_place(self):
        text = self.REPORT.format(rows='\u2612 Cold snare polypectomy') + 'The polypectomy site was clipped.\n'
        colon = one(read(text)[1], 'gi.colonoscopy')
        self.assertEqual(sum(1 for a in colon.acts if a.kind == 'snare' and a.status == 'performed'), 1)


class ModalPredicateScopeTests(SimpleTestCase):
    """facts_wording skeptic (triage round 2) on the modal-predicate repair: a modal predicate makes an act hypothetical
    only when it governs the act; past ability that today's narrative states is done; a hypothetical statement never
    turns a denial elsewhere into an exclusion; and the hypothetical wordings include contractions, any adverb and the
    "get" passive."""

    COLON = HEAD + ('Date of service: 2026-10-21\n\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to the '
                    'cecum. {x}\nImpression: as above.\n')
    EGD = HEAD + ('Date of service: 2026-10-21\n\nProcedure: EGD\nFindings: The gastroscope was advanced to the second part '
                  'of the duodenum. The mucosa was normal.\nImpression: Normal EGD. {x}\n')
    ERCP = HEAD + ('Date of service: 2026-10-21\n\nERCP report\nThe duodenoscope was advanced to the major papilla and the '
                   'bile duct was cannulated. {x}\n')

    def test_a_modal_on_another_subject_leaves_the_act_done(self):
        for template, family, x, kind in (
                (self.COLON, 'gi.colonoscopy', 'Cold snare polypectomy of the 8 mm sigmoid polyp, after which the '
                                                'examination could be completed.', 'snare'),
                (self.COLON, 'gi.colonoscopy', 'Cold snare polypectomy of a 12 mm polyp in the ascending colon, which '
                                                'could be retrieved for histology.', 'snare'),
                (self.EGD, 'gi.egd', 'Band ligation of three esophageal varices, after which the procedure could be '
                                     'completed.', 'band_ligation'),
                (self.ERCP, 'gi.ercp', 'Biliary sphincterotomy with a sphincterotome, so that the stones could be '
                                       'extracted.', 'sphincterotomy'),
                (self.ERCP, 'gi.ercp', 'Plastic biliary stent placement across the distal stricture, so that the bile '
                                       'duct could be decompressed.', 'stent')):
            with self.subTest(x=x):
                self.assertIn(kind, kinds(one(read(template.format(x=x))[1], family)))

    def test_past_ability_in_today_s_narrative_is_done(self):
        svc = one(read(self.COLON.format(x='The 8 mm sigmoid polyp could be removed en bloc with a cold snare.'))[1],
                  'gi.colonoscopy')
        self.assertIn('snare', kinds(svc))
        svc = one(read(self.EGD.format(x='Biopsies from the gastric antrum could be obtained without difficulty.'))[1],
                  'gi.egd')
        self.assertIn('biopsy', kinds(svc))
        text = HEAD + ('Date of service: 2026-10-21\n\nProcedure: Colonoscopy could be performed only to the splenic flexure '
                       'and was then terminated because of poor preparation.\n')
        self.assertEqual(one(read(text)[1], 'gi.colonoscopy').status, 'incomplete')

    def test_a_hypothetical_statement_never_turns_a_denial_into_an_exclusion(self):
        text = HEAD + ('Date of service: 2026-10-21\n\nIndication: Anemia. No colonoscopy was performed at the outside '
                       'hospital.\nPlan: Colonoscopy would have been performed today had the preparation been '
                       'adequate.\n')
        self.assertNotIn(one(read(text)[1], 'gi.colonoscopy').status, ('negated', 'cancelled'))

    def test_hypothetical_wordings(self):
        for x in ("Had there been a stricture, it would've been dilated with a balloon.",
                  'Had there been a stricture, it would\u2019ve been dilated with a balloon.',
                  'Had there been a stricture, it would certainly have been dilated with a balloon.',
                  'In the event of a stricture, it would get dilated with a balloon.',
                  'A biopsy would ordinarily have been taken had the mucosa been abnormal.'):
            with self.subTest(x=x):
                egd = one(read(self.EGD.format(x=x))[1], 'gi.egd')
                self.assertEqual([k for k in kinds(egd) if k in ('dilation', 'biopsy')], [])
        office = HEAD + ('Date of service: 2026-10-21\n\nPlace of service: Office\nEstablished patient office visit for '
                         'dysphagia.\nChief complaint: Dysphagia.\nMedical decision making: moderate.\nEGD would\'ve been '
                         'done today had the patient fasted.\n')
        _, inv = read(office)
        self.assertEqual([s.family for s in inv.services if s.status in services.POSITIVE], ['gi.office_em'])


class UnreadableFieldAnswerTests(SimpleTestCase):
    """A field answer this reader cannot read as done or not done holds its item; a participle in the label never states
    it done (triage round 2 skeptic: "Biopsy taken: None obtained" and printed option pairs read as a done biopsy and
    queued a paid second review). Details stay a statement of the act; a negated predicate still denies it."""

    REPORT = HEAD + ('Date of service: 2026-10-14\n\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to '
                     'the cecum. No polyps were seen.\n{line}\n')

    def test_an_unreadable_answer_holds(self):
        for line, kind in (('Biopsy taken: None obtained', 'biopsy'), ('Biopsies taken: zero', 'biopsy'),
                           ('Biopsy taken: no biopsy', 'biopsy'), ('Tattoo placed: none needed', 'tattoo'),
                           ('Biopsy taken:   Yes   No   N/A', 'biopsy'), ('Biopsy taken:  Y  N', 'biopsy'),
                           ('Biopsy taken: Yes ___ No ___', 'biopsy'), ('Biopsy taken: Yes / No (circle one)', 'biopsy'),
                           ('Tattoo placed: Yes __ No __', 'tattoo')):
            with self.subTest(line=line):
                colon = one(read(self.REPORT.format(line=line))[1], 'gi.colonoscopy')
                self.assertNotIn(kind, kinds(colon))

    def test_a_dash_separated_field_is_a_field_whose_denial_holds(self):
        for line, kind in (('Biopsy taken - No', 'biopsy'), ('Biopsy taken - None', 'biopsy'),
                           ('Biopsy taken \u2013 no', 'biopsy'), ('Tattoo placed - none', 'tattoo')):
            with self.subTest(line=line):
                colon = one(read(self.REPORT.format(line=line))[1], 'gi.colonoscopy')
                self.assertNotIn(kind, kinds(colon))
                self.assertNotIn(kind, kinds(colon, 'negated'))  # held, never newly excluded
        for line in ('Biopsy taken - yes', 'Biopsy taken - 2 from the sigmoid colon'):
            with self.subTest(line=line):
                self.assertIn('biopsy', kinds(one(read(self.REPORT.format(line=line))[1], 'gi.colonoscopy')))

    def test_a_checked_row_labelled_for_something_else_holds(self):
        """Strict boxes (2026-10-25): a row done only by its section's default must be listed by its own label."""
        colon = one(read(self.REPORT.format(line='Risks discussed - \u2612 Biopsy \u2612 Cold snare polypectomy'))[1],
                    'gi.colonoscopy')
        self.assertEqual([k for k in kinds(colon) if k in ('biopsy', 'snare')], [])
        colon = one(read(self.REPORT.format(line='Interventions: \u2612 Biopsy'))[1], 'gi.colonoscopy')
        self.assertIn('biopsy', kinds(colon))

    def test_details_state_the_act_and_a_negated_predicate_denies_it(self):
        colon = one(read(self.REPORT.format(line='Biopsies taken: 3 from the sigmoid colon'))[1], 'gi.colonoscopy')
        self.assertIn('biopsy', kinds(colon))
        colon = one(read(self.REPORT.format(line='Tattoo placed: not placed'))[1], 'gi.colonoscopy')
        self.assertNotIn('tattoo', kinds(colon))


class ReferralTests(SimpleTestCase):
    """Refutation r1 (report lens): "for EMR referral" names what the patient is referred for, never an EMR done today."""

    def test_an_act_named_for_a_referral_is_planned(self):
        text = HEAD + ('Date of service: 2026-10-14\n\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to the '
                       'cecum. A 25 mm laterally spreading lesion in the ascending colon was biopsied with cold forceps '
                       'and tattooed for EMR referral.\n')
        colon = one(read(text)[1], 'gi.colonoscopy')
        self.assertNotIn('emr', kinds(colon))
        self.assertIn('biopsy', kinds(colon))


class NegationScopeTests(SimpleTestCase):
    """Refutation r1 (release lens; regressions against the installed revision, which held these): a negation reaches
    the act through its list and the act's own auxiliary, never through another predicate."""

    REPORT = HEAD + ('COLONOSCOPY PROCEDURE REPORT\nDate of service: 10/14/2026\n\nThe colonoscope was advanced to the '
                     'cecum. A 6 mm sessile polyp was seen in the sigmoid colon. {x}\n')

    def test_a_denied_act_is_negated(self):
        for x, kind in (('On withdrawal, no polyp was snared.', 'snare'),
                        ('Per patient preference, no lesion was biopsied.', 'biopsy'),
                        ('The polyp was neither biopsied nor removed.', 'biopsy'),
                        ('Biopsy not obtained given incomplete exam.', 'biopsy'),
                        ('Polypectomy not performed due to discontinuation of the procedure.', 'snare'),
                        ('The polyp was not biopsied, nor was it snared.', 'snare'),
                        ('Snare polypectomy of the polyp, since it appeared deeply invasive, was not performed.',
                         'snare')):
            with self.subTest(x=x):
                colon = one(read(self.REPORT.format(x=x))[1], 'gi.colonoscopy')
                self.assertIn(kind, kinds(colon, 'negated'))
                self.assertNotIn(kind, kinds(colon))

    def test_a_negation_of_another_predicate_leaves_the_act_done(self):
        for x, kind in (('No bleeding was seen after the polyp was snared.', 'snare'),
                        ('The polyp was snared and no bleeding was seen.', 'snare'),
                        ('No polyps were seen, and biopsies were taken from the rectum.', 'biopsy'),
                        ('Cold snare polypectomy was performed because the polyp did not appear invasive.', 'snare')):
            with self.subTest(x=x):
                self.assertIn(kind, kinds(one(read(self.REPORT.format(x=x))[1], 'gi.colonoscopy')))


class UnestablishedServiceCompletenessTests(SimpleTestCase):
    """Refutation r1 (report lens): a documented service not established as performed that no proposal reads keeps
    coding incomplete; completeness never says every documented service has a proposal."""

    def test_an_uncertain_service_without_a_proposal_keeps_coding_incomplete(self):
        from studio.types import EvidenceSpan, ProviderCode
        text = HEAD + ('Date of service: 2026-10-14\n\nEUS: Normal pancreas and common bile duct; no mass.\nColonoscopy: The '
                       'colonoscope was advanced to the cecum. A 7 mm sessile polyp in the sigmoid colon was removed with '
                       'a cold snare.\n')
        quote = 'was removed with a cold snare'
        start = text.index(quote)
        day = date(2026, 10, 14)
        result = assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                        normalized=NormalizedResponse('replay', 'test@1', (ProviderCode(
                            'selected', 'cpt', '45385', 'UNVERIFIED PROVIDER WORDING',
                            (EvidenceSpan(0, start, start + len(quote), quote, True),)),)),
                        reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')
        self.assertEqual(result.completeness['state'], 'incomplete')
        self.assertIn('1 documented service not established as performed and read by no proposal',
                      result.completeness['reasons'])
