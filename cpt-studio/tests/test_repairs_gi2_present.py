"""Repair round gi2, agent 'present' (investigations 'demo' PR5/PR6, RC6-RC8, and 'occurrence' R4 (i)): what the screen
shows of the persisted rows. Synthetic data only; the provider is an in-process fake (no network); node runs the
shipped app.js, so every screen below is checked as it renders.

1. The review queue lists every encounter that waits on a workspace member - an open question, a code to decide, a
   provider request to reconcile, a second review that can be asked for, or coding left incomplete (a documented service
   without a supported proposal) - not only three states: ho-06 (no code selected, a second review available) and ho-09
   (reviewed, its flexible sigmoidoscopy unresolved) were off the queue of the 2b82889f walk. The session's count is the
   same rule. A reviewed encounter whose coding is incomplete reads "Reviewed · coding incomplete" in the lists.
2. Informational candidates are grouped: the GI family of a documented service, or not (outside the documented services
   or not a CPT code, collapsed with its count). Each candidate's cited passage is shown on expand; nothing is dropped and
   nothing becomes selectable.
3. A service date the reader kept as evidence but could not use, and asks for, is quoted on the date chip - never "Not
   documented" beside a check that quotes it.
4. A clarification card leads with its question; the engine's technical reason sits behind a "Details" disclosure.
"""
import re
from unittest import mock

from django.test import Client, TestCase, override_settings

from studio import models, serializers
from studio.providers.base import ProviderUnavailable
from tests.support import factories as f
from tests.test_pipeline_api import FakeProvider, drain
from tests.test_repairs_7c8_p1reports import COLONOSCOPY, page
from tests.test_repairs_7c8_p2reports import Scripted
from tests.test_repairs_ec5_reportfacts import browser
from tests.test_services_second_review import TwoPassProvider, ask

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
SNARE = ('45385', 'was removed with a cold snare')
BIOPSY = ('45380', 'was sampled with cold biopsy forceps')
VISIT_TIME = 'Total time on the date of the encounter was 24 minutes.'
# A letter dated by a "Date:" line: the reader keeps it as evidence and never takes it as the date of service by itself
# (ARCHITECTURE 5.2), so the date is asked.
LETTER = SYNTHETIC + """Date: 10/27/2026
Dear Dr. Synthetic,
Your patient was seen in our office today.
Place of service: Office, in-person outpatient visit
Patient status: Established patient.
Established patient office visit for chronic constipation.
""" + VISIT_TIME + '\n'
UNDATED = LETTER.replace('Date: 10/27/2026\n', '')
# A visit whose place of service is not documented: the E/M proposal carries its own (proposal-scoped) question.
NO_PLACE = SYNTHETIC + """Riverbend Digestive Health (fictional)
Date of service: 2026-10-20
Patient status: Established patient, last seen 2026-03-02.
Chief complaint
Follow-up of chronic constipation.
Medical decision making
Low: one stable chronic illness; prescription drug management.
""" + VISIT_TIME + '\n'

QUEUE_NODE = ('{queue: app.listBody("queue", data.rows), described: app.listDescription("queue", data.rows), '
              'rows: data.rows.map(row => app.documentRow(row)), invite: app.inviteMarkup(data.rows)}')


def listed_ids(html):
    return re.findall(r'href="#doc/([0-9a-f-]{36})"', html)


def esc(text):
    """app.js's escapeHtml."""
    table = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;', '`': '&#x60;'}
    return ''.join(table.get(ch, ch) for ch in text)


def only_inside_details(html, text):
    """Every occurrence of ``text`` in ``html`` sits inside a clarification "Details" disclosure (at least one)."""
    found = [m.start() for m in re.finditer(re.escape(text), html)]
    opener = '<details class="clarification-details"><summary>Details</summary>'
    inside = [at for at in found if html.rfind(opener, 0, at) > html.rfind('</details>', 0, at)]
    return bool(found) and inside == found


@override_settings(**LIVE)
class Harness(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)

    def use(self, provider):
        patcher = mock.patch('studio.jobs.get_provider', return_value=provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.provider = provider
        return provider

    def create(self, text=COLONOSCOPY):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data=None):
        import json
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def detail(self, encounter_id):
        reply = self.client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(reply.status_code, 200, reply.content)
        return reply.json()

    def rows(self):
        return self.client.get('/api/encounters').json()['encounters']

    def row(self, encounter_id):
        (row,) = [item for item in self.rows() if item['id'] == encounter_id]
        return row

    def queue_count(self):
        return self.client.get('/api/session').json()['counts']['queue']

    def screen(self):
        return browser(QUEUE_NODE, {'rows': self.rows()})

    def approve(self, encounter_id, code):
        proposals = self.detail(encounter_id)['assessment']['proposals']
        (proposal,) = [p for p in proposals if p['code'] == code and p['bucket'] == 'selected']
        acknowledgement = self.client.get('/api/session').json()['acknowledgement']
        reply = self.post(f'/api/encounters/{encounter_id}/decisions',
                          {'proposal_id': proposal['id'], 'action': 'approve', 'acknowledgement': acknowledgement})
        self.assertEqual(reply.status_code, 201, reply.content)


# --- 1. the review queue lists what waits on a member (demo RC6, PR5; R9 and R10) ---------------------------------------

class QueueListsWhatWaitsOnAMemberTests(Harness):
    def test_a_reviewed_encounter_whose_coding_is_incomplete_is_queued_and_says_so(self):
        # ho-09's shape: the one selected code approved (state reviewed), a documented act left without a supported
        # proposal, and the bounded second review available for it.
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        encounter_id = self.create()
        drain()
        self.approve(encounter_id, '45385')
        detail = self.detail(encounter_id)
        self.assertEqual(detail['state'], 'reviewed')
        self.assertEqual(detail['coding']['state'], 'incomplete')
        self.assertTrue(detail['second_review']['available'])
        row = self.row(encounter_id)
        self.assertEqual(row['coding_state'], 'incomplete')
        self.assertEqual(row['queue_reasons'], ['incomplete', 'second_review'])
        self.assertEqual((detail['coding_state'], detail['queue_reasons']), (row['coding_state'], row['queue_reasons']))
        self.assertEqual(self.queue_count(), 1)
        shown = self.screen()
        self.assertEqual(listed_ids(shown['queue']), [encounter_id])
        self.assertTrue(shown['described'].startswith('One document '), shown['described'])
        (rendered,) = shown['rows']
        self.assertIn('<span class="status amber">Reviewed · coding incomplete</span>', rendered)
        self.assertNotIn('status green', rendered)
        self.assertIn('Reviewed · coding incomplete', shown['invite'])
        self.assertIn('Second review available', shown['queue'])

    def test_a_no_codes_encounter_with_a_second_review_available_is_queued(self):
        # ho-06's shape: the provider selected no code (it listed one only as a candidate), the documented colonoscopy
        # has no supported proposal, and a reviewer can ask the provider once more.
        self.use(Scripted(candidates=[('cpt', '45378', 'The colonoscope was advanced to the cecum')]))
        encounter_id = self.create()
        drain()
        detail = self.detail(encounter_id)
        self.assertEqual((detail['state'], detail['state_label']), ('no_codes', 'No code selected for approval'))
        self.assertTrue(detail['second_review']['available'])
        row = self.row(encounter_id)
        self.assertEqual(row['queue_reasons'], ['incomplete', 'second_review'])
        self.assertEqual(self.queue_count(), 1)
        shown = self.screen()
        self.assertEqual(listed_ids(shown['queue']), [encounter_id])
        self.assertIn('No code selected for approval', shown['queue'])
        self.assertIn('Second review available', shown['queue'])
        self.assertIn('Coding incomplete', shown['queue'])

    def test_a_provider_this_installation_cannot_build_is_never_offered_and_never_breaks_a_list(self):
        # Every page loads the session and a list: a live provider with no credentials configured can be asked nothing,
        # so no second review is claimed, and the encounter stays queued for its incomplete coding.
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        encounter_id = self.create()
        drain()
        self.approve(encounter_id, '45385')
        missing = ProviderUnavailable('Live provider mode needs CPT_STUDIO_CORTI_CREDENTIALS_FILE.')
        with mock.patch('studio.jobs.get_provider', side_effect=missing):
            listed = self.client.get('/api/encounters')
            self.assertEqual(listed.status_code, 200)
            (row,) = listed.json()['encounters']
            self.assertEqual((row['state'], row['queue_reasons']), ('reviewed', ['incomplete']))
            session = self.client.get('/api/session')
            self.assertEqual((session.status_code, session.json()['counts']['queue']), (200, 1))

    def test_control_a_reviewed_encounter_whose_coding_is_complete_is_not_queued(self):
        self.use(TwoPassProvider(first=[SNARE, BIOPSY], later=[]))
        encounter_id = self.create()
        drain()
        self.approve(encounter_id, '45385')
        self.approve(encounter_id, '45380')
        detail = self.detail(encounter_id)
        self.assertEqual((detail['state'], detail['coding']['state']), ('reviewed', 'reviewed'))
        row = self.row(encounter_id)
        self.assertEqual((row['coding_state'], row['queue_reasons']), ('reviewed', []))
        self.assertEqual(self.queue_count(), 0)
        shown = self.screen()
        self.assertEqual(listed_ids(shown['queue']), [])
        (rendered,) = shown['rows']
        self.assertIn('Reviewed</span>', rendered)
        self.assertIn('status green', rendered)
        self.assertNotIn('coding incomplete', rendered + shown['invite'])

    def test_an_undecided_code_and_a_question_are_queued(self):
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        encounter_id = self.create()
        drain()
        self.assertEqual(self.detail(encounter_id)['state'], 'ready_for_review')
        self.assertEqual(self.row(encounter_id)['queue_reasons'], ['decision', 'incomplete', 'second_review'])
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        letter = self.create(LETTER)
        drain()
        self.assertEqual(self.detail(letter)['state'], 'needs_clarification')
        self.assertEqual(self.row(letter)['queue_reasons'], ['question', 'decision', 'incomplete'])
        self.assertEqual(self.queue_count(), 2)
        self.assertEqual(sorted(listed_ids(self.screen()['queue'])), sorted([encounter_id, letter]))

    def test_an_unreconciled_request_is_queued_until_a_member_reconciles_it(self):
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY], outcomes=['succeeded', 'unknown']))
        encounter_id = self.create()
        drain()
        self.approve(encounter_id, '45385')
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        self.assertEqual(self.detail(encounter_id)['state'], 'provider_unknown')
        self.assertIn('reconciliation', self.row(encounter_id)['queue_reasons'])
        self.assertIn('Provider outcome to reconcile', self.screen()['queue'])
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state='unknown')
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(unknown.pk), 'note': 'Checked the provider console: no response.'})
        self.assertIn(reply.status_code, (200, 201), reply.content)
        drain()
        self.assertNotIn('reconciliation', self.row(encounter_id)['queue_reasons'])

    def test_control_an_encounter_being_processed_waits_on_its_stages_not_on_a_member(self):
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        encounter_id = self.create()  # its stages are queued, not run
        row = self.row(encounter_id)
        self.assertEqual((row['state'], row['queue_reasons']), ('processing', []))
        self.assertEqual(self.queue_count(), 0)
        self.assertEqual(listed_ids(self.screen()['queue']), [])

    def test_the_session_count_is_the_queue_the_page_lists(self):
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        reviewed = self.create()
        drain()
        self.approve(reviewed, '45385')
        self.use(TwoPassProvider(first=[SNARE, BIOPSY], later=[]))
        complete = self.create(COLONOSCOPY.replace('Colonoscopy report', 'Colonoscopy report (second copy)'))
        drain()
        self.approve(complete, '45385')
        self.approve(complete, '45380')
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        letter = self.create(LETTER)
        drain()
        self.create(UNDATED)  # still processing
        shown = self.screen()
        queued = listed_ids(shown['queue'])
        self.assertEqual(sorted(queued), sorted([reviewed, letter]))
        self.assertEqual(self.queue_count(), len(queued))
        self.assertEqual(sorted(row['id'] for row in self.rows() if row['queue_reasons']), sorted(queued))
        self.assertTrue(shown['described'].startswith('2 documents '), shown['described'])

    def test_a_state_that_always_waited_on_a_member_is_never_left_off(self):
        # Whatever else is found (here: nothing), the three states the queue listed before stay on it.
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        encounter_id = self.create(LETTER)
        drain()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        for state in sorted(serializers.QUEUE_STATES):
            encounter.state = state
            with mock.patch.object(serializers.review, 'live_assessment', return_value=None), \
                    mock.patch.object(serializers.review, 'coding_completeness', return_value={'state': 'reviewed'}):
                self.assertEqual(serializers.queue_reasons(encounter), ['state'], state)
        encounter.state = 'no_codes'
        with mock.patch.object(serializers.review, 'live_assessment', return_value=None), \
                mock.patch.object(serializers.review, 'coding_completeness', return_value={'state': 'reviewed'}):
            self.assertEqual(serializers.queue_reasons(encounter), [])


# --- 3. the date chip quotes the date the reader kept as evidence (occurrence RC5, R4 (i)) -------------------------------

class DateChipQuotesTheKeptEvidenceTests(Harness):
    def chips(self, detail):
        codes = page(detail)['codes']
        (paper,) = re.findall(r'<span><b>SERVICE DATE</b>(.*?)</span>', codes)
        header = re.search(r'<div class="review-meta"><span>(.*?)</span>', codes).group(1)
        return paper, header, codes

    def test_an_asked_date_with_kept_evidence_is_quoted_never_not_documented(self):
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        encounter_id = self.create(LETTER)
        drain()
        detail = self.detail(encounter_id)
        fact = detail['context']['facts']['service_date']
        self.assertEqual((fact['origin'], fact['value']), ('missing', None))
        self.assertEqual([span['text'] for span in fact['evidence']], ['Date: 10/27/2026'])
        asked = [c for c in detail['clarifications'] if c['fact'] == 'service_date' and c['state'] == 'open']
        self.assertEqual(len(asked), 1)
        paper, header, codes = self.chips(detail)
        self.assertEqual(paper, 'Asked — “Date: 10/27/2026” is not read as the date of service')
        self.assertEqual(header, 'Service date asked — “Date: 10/27/2026” is not read as the date of service')
        self.assertNotIn('ot documented', paper + header)
        # the check it now agrees with
        self.assertIn('the document states “Date: 10/27/2026”, which is not read as one', page(detail)['checks'])

    def test_control_a_date_nothing_states_stays_not_documented(self):
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        encounter_id = self.create(UNDATED)
        drain()
        detail = self.detail(encounter_id)
        self.assertEqual(detail['context']['facts']['service_date']['evidence'], [])
        paper, header, _ = self.chips(detail)
        self.assertEqual((paper, header), ('Not documented', 'Service date not documented'))

    def test_control_a_documented_date_is_shown_as_the_date(self):
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        encounter_id = self.create(NO_PLACE)
        drain()
        paper, header, _ = self.chips(self.detail(encounter_id))
        self.assertEqual((paper, header), ('20 October 2026', '20 Oct 2026'))


# --- 4. a clarification card leads with its question; the technical reason is behind "Details" (demo RC8, PR7) ---------

class ClarificationCardsLeadWithTheQuestionTests(Harness):
    def test_the_encounter_question_card_leads_with_the_question(self):
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        encounter_id = self.create(LETTER)
        drain()
        detail = self.detail(encounter_id)
        (asked,) = [c for c in detail['clarifications'] if c['fact'] == 'service_date']
        codes = page(detail)['codes']
        card = codes[codes.index('<div class="clarification-card">'):]
        card = card[:card.index('</details>') + len('</details>')]
        question = card.index(f'<h3 class="clarification-lead">{esc(asked["question"])}</h3>')
        details = card.index('<details class="clarification-details"><summary>Details</summary>')
        self.assertLess(question, details)
        self.assertNotIn('A question is better', codes)
        self.assertTrue(only_inside_details(codes, esc(asked['reason'])), asked['reason'])

    def test_a_proposal_question_on_its_code_card_keeps_the_reason_behind_details(self):
        self.use(FakeProvider(selections=[('99213', VISIT_TIME)]))
        encounter_id = self.create(NO_PLACE)
        drain()
        detail = self.detail(encounter_id)
        inline = [c for c in detail['clarifications'] if c['state'] == 'open' and c['scope'] != 'encounter']
        self.assertTrue(inline, detail['clarifications'])
        codes = page(detail)['codes']
        for clarification in inline:
            question = codes.index(esc(clarification['question']))
            self.assertLess(question, codes.index('<summary>Details</summary>', question))
            self.assertTrue(only_inside_details(codes, esc(clarification['reason'])), clarification['reason'])


# --- 2. informational candidates are grouped, nothing dropped, nothing selectable (demo RC7, PR6) -----------------------

QUOTE_CECUM = 'The colonoscope was advanced to the cecum'
QUOTE_SNARE = 'was removed with a cold snare'
QUOTE_BIOPSY = 'was sampled with cold biopsy forceps'


class CandidatesAreGroupedTests(Harness):
    def test_candidates_of_a_documented_service_family_lead_and_the_rest_are_collapsed_with_their_count(self):
        self.use(Scripted(codes=[('cpt', '45385', QUOTE_SNARE)],
                          candidates=[('cpt', '45380', QUOTE_BIOPSY), ('cpt', '33512', QUOTE_CECUM),
                                      ('cpt', 'G0121', QUOTE_CECUM), ('cpt', '99213', '')]))
        encounter_id = self.create()
        drain()
        detail = self.detail(encounter_id)
        alternatives = {p['code']: p for p in detail['assessment']['proposals'] if p['bucket'] == 'alternative'}
        self.assertEqual(sorted(alternatives), ['33512', '45380', '99213', 'G0121'])
        codes = page(detail)['codes']
        start = codes.index('<h2>Alternatives (never selectable)</h2><span class="small-badge">4</span>')
        ends = [at for at in (codes.find('<div class="section-heading">', start + 1),
                              codes.find('<div class="review-insight">', start)) if at > 0]
        section = codes[start:min(ends)]  # up to the next section (excluded candidates) or the panel's closing note
        same_at = section.index('Same GI family as a documented service · 1')
        other_at = section.index('<details class="check-list-card candidate-group"><summary>'
                                 'Outside the documented services or not a CPT code · 3</summary>')
        self.assertLess(same_at, other_at)
        same, other = section[same_at:other_at], section[other_at:]
        self.assertIn('<strong>45380 · Colonoscopy</strong>', same)
        for code in ('33512', 'G0121', '99213'):
            self.assertIn(f'<strong>{code} · ', other)
            self.assertNotIn(f'<strong>{code} · ', same)
        self.assertEqual(sum(section.count(f'<strong>{code} · ') for code in alternatives), 4)  # each listed once
        # each candidate's cited passage on expand, or that it cites none
        self.assertIn(f'<summary>Cited passage</summary><p>“{QUOTE_BIOPSY}”</p>', same)
        self.assertEqual(other.count(f'<p>“{QUOTE_CECUM}”</p>'), 2)
        self.assertIn('No exact source passage is linked to this candidate.', other)
        self.assertNotRegex(section, r'<details[^>]* open')
        # never selectable: no candidate gains an action
        for proposal in alternatives.values():
            self.assertNotIn(f'data-proposal="{proposal["id"]}"', codes)
