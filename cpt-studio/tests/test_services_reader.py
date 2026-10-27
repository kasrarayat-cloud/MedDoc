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
    def test_day_month_year_with_hyphens(self):
        facts, _ = read(HEAD + 'Endoscopy unit\nDate: 03-Nov-2026\nThe gastroscope was passed to the second part of '
                               'the duodenum.\n')
        self.assertEqual((facts['service_date'].value, facts['service_date'].origin), ('2026-11-03', 'document'))

    def test_a_labelled_date_in_a_table_row(self):
        facts, _ = read(HEAD + 'Field | Value\nProcedure date | 2026-09-30\nScope | adult colonoscope\n')
        self.assertEqual(facts['service_date'].value, '2026-09-30')

    def test_a_dated_note_title(self):
        facts, _ = read(HEAD + '\nHepatology clinic note - 9/28/2026\n\nSeen for ascites follow-up.\n')
        self.assertEqual(facts['service_date'].value, '2026-09-28')

    def test_a_dated_title_never_beats_a_labelled_date_and_a_qualified_one_is_no_date(self):
        facts, _ = read(HEAD + 'Office visit - 2026-09-01\nDate of service: 2026-09-02\nSeen today.\n')
        self.assertEqual(facts['service_date'].value, '2026-09-02')
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
        _, inv = read(HEAD + 'Date of service: 2026-10-14\nUpper endoscopy report\n' + body)
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
        _, inv = read(HEAD + 'Date of service: 2026-10-14\nUpper endoscopy report\nThe gastroscope was passed to the '
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
        _, inv = read(HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope reached the cecum.\n'
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
        text = HEAD + ('Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope reached the cecum.\n'
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
        _, inv = read(HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the '
                             'cecum. A 30 mm laterally spreading lesion in the ascending colon was tattooed and not '
                             'removed; it is referred for EMR.\n')
        self.assertIn('tattoo', kinds(one(inv, 'gi.colonoscopy')))
        _, inv = read(HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the '
                             'cecum. Biopsies of the sigmoid colon were obtained and a dilation was not performed.\n')
        svc = one(inv, 'gi.colonoscopy')
        self.assertIn('biopsy', kinds(svc))
        self.assertIn('dilation', kinds(svc, 'negated'))

    def test_a_negation_in_a_subordinate_clause_leaves_the_mention(self):
        _, inv = read(HEAD + 'Date of service: 2026-10-14\nOffice visit\nPlan: possible EGD with PEG placement if '
                             'oral intake does not improve.\n')
        egd = [s for s in inv.services if s.family == 'gi.egd']
        self.assertTrue(all(s.status != 'negated' for s in egd), [(s.status, s.cues) for s in egd])

    def test_controls_a_negation_of_the_act_itself_still_denies_it(self):
        for line, kind in (('Biopsies were not obtained.', 'biopsy'), ('The polyp was not removed with a snare.', 'snare'),
                           ('Cold forceps biopsy was not performed because of anticoagulation.', 'biopsy')):
            with self.subTest(line=line):
                _, inv = read(HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to '
                                     'the cecum. ' + line + '\n')
                svc = one(inv, 'gi.colonoscopy')
                self.assertNotIn(kind, kinds(svc))
        _, inv = read(HEAD + 'Date of service: 2026-10-14\nOffice visit\nThe patient did not undergo EGD today.\n')
        self.assertTrue(all(s.status not in services.POSITIVE for s in inv.services if s.family == 'gi.egd'))


class MemberConflictQuestionTests(SimpleTestCase):
    """A member's encounter metadata that conflicts with the document is asked once, as that conflict, with both sides;
    never as an undocumented fact, and never left unasked when no proposal asks about it."""

    def test_a_conflicting_setting_is_asked_at_the_encounter(self):
        for body in ('Place of service: 11 - Office\nGastroenterology office visit for heartburn.\n',
                     'Gastroenterology office visit for heartburn.\n'):
            text = HEAD + 'Date of service: 2026-10-20\n' + body
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
