"""harness@2's website fixtures (HARNESS.md 11-12) are the serializer's own output; moved out of tests/test_frontend.py so
that module no longer imports tests.test_harness2_api (whose pipeline-test imports lead back to test_frontend: a cycle
once both packages were integrated)."""
import json
import os
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from studio import jobs, models, review, serializers
from studio.types import sha256_json
from tests import test_harness2_api as h2
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.test_frontend import FIXTURES, HARNESS2_SCENARIOS, HARNESS2_TRACE, _fixture, candidate_id


# --- harness@2 (HARNESS.md 11-12): the website's fixtures are the serializer's own output -----------------------------
#
# The encounter-harness2-*.json fixtures and trace-harness2-final.json are made here, by studio.serializers, from the
# rows harness@2 records (tests/test_harness2_api.py's Harness2Case: the real adapters' stored requests, replayed
# response bytes the real readers read, exchanges, tool calls, the assessments' participant entries and a confirmation
# recorded through the real endpoint), never written from API.md's prose. This release offers no reviewer confirmation
# (HARNESS.md 12.10): the peer and final fixtures and the trace are what it serves (unchecked candidates, can_confirm
# false); encounter-harness2-dormant.json and encounter-harness2-confirmed.json are made with
# STUDIO_OFFER_CONFIRMATIONS=True, as the dormant confirmation path serves them, for that path's rendering tests.
# CPT_STUDIO_WRITE_FIXTURES=1 writes them again, with stable ids and times; otherwise the committed files must carry
# exactly the keys, at every level, that the serializer emits now, so a change to the API that the website was not
# built for fails here. Hashes over bytes that name a question (a peer request or answer) are kept as generated: the ids
# they name were made stable after hashing.

WRITE_FIXTURES = os.environ.get('CPT_STUDIO_WRITE_FIXTURES') == '1'
UUID_TEXT = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
TIME_TEXT = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})')
FIXTURE_TIME = datetime(2026, 11, 1, 9, 0, tzinfo=dt_timezone.utc)
TERMINAL_JOBS = {models.Job.SUCCEEDED, models.Job.FAILED, models.Job.UNKNOWN, models.Job.CANCELLED}
PHASE1_JOBS = (models.Job.EXTRACT, models.Job.ANALYZE, models.Job.PREDICT, models.Job.ASTRA, models.Job.FABLE,
               models.Job.ASSESS)
PHASE2_JOBS = (models.Job.ASTRA_PEER, models.Job.FABLE_PEER, models.Job.ASSESS)


def shape(value, path=''):
    """Every (path, type) a JSON value carries - the keys at every level ('[]' for a list's items) and each leaf's
    type - so two payloads compare by their shape, never by their ids, times or hashes."""
    if isinstance(value, dict):
        out = {(path or '.', 'object')}
        for key, item in value.items():
            out |= shape(item, f'{path}.{key}')
        return out
    if isinstance(value, list):
        out = {(path or '.', 'array')}
        for item in value:
            out |= shape(item, f'{path}[]')
        return out
    return {(path or '.', type(value).__name__)}


class StableIds:
    """Stable ids and times for the generated fixtures: each uuid of a scenario becomes <prefix>-0000-4000-8000-<n> in
    the order it first appears, each distinct time FIXTURE_TIME plus its rank among all of them (their order kept), and
    each candidate id is computed again from its question's new id, exactly as studio.candidates computes it."""

    def __init__(self, texts):
        found = sorted({datetime.fromisoformat(value.replace('Z', '+00:00')): value
                        for text in texts for value in TIME_TEXT.findall(text)}.items())
        self.times = {}
        for rank, (_, value) in enumerate(found):
            self.times.setdefault(value, (FIXTURE_TIME + timedelta(seconds=rank)).strftime('%Y-%m-%dT%H:%M:%SZ'))
        self.uuids = {}

    def __call__(self, text, prefix):
        def uuid_of(match):
            value = match.group(0)
            if value not in self.uuids:
                count = sum(1 for known in self.uuids.values() if known.startswith(prefix)) + 1
                self.uuids[value] = f'{prefix}-0000-4000-8000-{count:012x}'
            return self.uuids[value]
        data = json.loads(TIME_TEXT.sub(lambda m: self.times[m.group(0)], UUID_TEXT.sub(uuid_of, text)))
        for clarification in data.get('clarifications') or [] if isinstance(data, dict) else []:
            for candidate in clarification.get('candidates') or []:
                candidate['id'] = candidate_id(clarification['id'], candidate)
        return data


@override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')
class Harness2FixtureTests(h2.Harness2Case):
    """Four encounters as harness@2 records them, serialized: one whose peer reviews are running (assess #1 current,
    Astra's peer stage in flight, Fable's waiting), one after both peer reviews (assess #2, its open questions with
    their candidates, served unchecked: this release offers no confirmation, HARNESS.md 12.10), and - made with the
    dormant confirmation path on - the same scenario as that path serves it, and one whose extent question a reviewer
    confirmed, with the re-assessment that read it. Every assessment is the engine's of the case's stored rows
    (Harness2Case.result; refutation round 3, falsegreen-11: they were written by hand, a hold among them that the
    readers never produce for their note)."""

    def setUp(self):  # the parent's builds one encounter; these tests build each scenario as the pipeline records it
        self.ws = f.workspace()
        self.owner = self.person('owner', 'Synthetic Owner', models.Membership.OWNER)
        self.reviewer = self.person('reviewer', 'Synthetic Reviewer', models.Membership.REVIEWER)

    def person(self, username, label, role):
        user = models.User.objects.create_user(username=username, password='synthetic-pass-123!',
                                               actor_kind=models.User.HUMAN, display_name=label)
        models.Membership.objects.create(user=user, workspace=self.ws, role=role)
        return user

    # --- the rows, as Harness2Case.setUp records them --------------------------------------------------------------

    def first_reading_of(self, name):
        """Fable's first reading proposes 45385 only, so 45380 is first proposed by Fable in its peer review."""
        data = h2.first_reading(name)
        if name == 'fable':
            data['codes'] = [item for item in data['codes'] if item['code'] != '45380']
        return data

    def entry(self, name, *, peer=False):
        """Harness2Case's 12.3 entry, with the codes and not-coded items jobs._participant_record records: each with its
        first located quote, as the screen states a participant's positions from them."""
        record = jobs._participant_record(name, 'read', self.runs[name], self.readings[name], '')
        return {**super().entry(name, peer=peer), 'codes': record['codes'], 'not_coded': record['not_coded']}

    def peer_answer(self, name):
        answer = super().peer_answer(name)
        if name == 'fable':
            answer['additional_codes'] = [{'code': '45380', 'modifiers': [], 'units': 1, 'service_ids': ['s1'],
                                           'basis': 'The report records a polyp biopsied with cold forceps.',
                                           'evidence': [h2.RECTUM_QUOTE], 'confidence': 'medium'}]
        return answer

    def phase1(self, title):
        self.encounter = f.encounter(self.ws, self.reviewer, title=title)
        self.document()  # the revision, its context as the analyze stage records it, and Corti's run (Harness2Case)
        self.now = timezone.now()
        self.adapters = {name: h2.ADAPTERS[name]('/nonexistent/never-read.env') for name in h2.ADAPTERS}
        self.runs, self.readings, self.requests = {}, {}, {}
        for name in h2.ADAPTERS:
            request = self.adapters[name].build_request(h2.NOTE, h2.PAGES, 'paste', None)
            data = (h2.astra_with if name == 'astra' else h2.fable_with)(self.first_reading_of(name))
            run = self.make_run(name, request, data, purpose=models.ProviderRun.INDEPENDENT)
            calls = [('cms_code_facts', {'codes': ['45385'], 'date_of_service': ''}, h2.FACTS_RESULT, [h2.FACT_REF])]
            self.exchanges(run, request.body, data, calls if name == 'astra' else [])
            self.runs[name], self.requests[name] = run, request
            self.readings[name] = self.adapters[name].read(request, data, frozenset(review.run_refs(run)))
        self.frozen = sorted([['astra', sha256_json(self.readings['astra'])], ['corti', self.corti.response_sha256],
                              ['fable', sha256_json(self.readings['fable'])],
                              ['revision', self.revision.text_sha256]])
        self.jobs(PHASE1_JOBS)
        self.first = self.save([self.entry(name) for name in h2.ADAPTERS], self.result(1))

    def phase2(self):
        self.peer_runs, self.reviews = {}, {}
        for name in h2.ADAPTERS:
            self.peer_review(name)
        self.jobs(PHASE2_JOBS)
        self.final = self.save([self.entry(name, peer=True) for name in h2.ADAPTERS], self.result(2))
        self.questions = h2.questions_of(self.final)

    def jobs(self, kinds, state=models.Job.SUCCEEDED):
        for kind in kinds:
            done = state in TERMINAL_JOBS
            pf.job(self.encounter, self.revision, kind, state, context=self.context,
                   provider_run=None if kind in (models.Job.EXTRACT, models.Job.ANALYZE) else self.corti,
                   started_at=timezone.now(), finished_at=timezone.now() if done else None)

    def save(self, entries, result):
        self.encounter.refresh_from_db()
        assessment = review.persist_assessment(
            encounter=self.encounter, revision=self.revision, context=self.context, routing_run=self.routing_run,
            provider_run=self.corti, result=result, participants=entries, retrieval=self.retrieval())
        review.refresh_state(self.encounter)
        return assessment

    def retrieval(self):
        """The reconciliation's own retrieval (Assessment.retrieval), never a participant's: synthetic stand-in text."""
        def passage(key, section, page, topic, value, body):
            text = f'SYNTHETIC FIXTURE TEXT, not CMS text: {body}'
            return {'source_key': 'cms-ncci-policy-manual-2026-ch6', 'release': 'Revision 1/1/2026', 'passage_key': key,
                    'section': section, 'page': page, 'topic': topic, 'topic_value': value,
                    'sha256': h2.sha(text.encode('utf-8')), 'text': text}

        def fact(code, field, value, **extra):
            return {'source_key': 'cms-pfs-rvu26d', 'release': 'RVU26D', 'effective': ['2026-10-01', '2026-12-31'],
                    'sha256': h2.sha(b'synthetic pfs file'), 'field': field, 'value': value, **extra}
        rule = passage('vi-c-3', 'Chapter VI, section C: Endoscopic Services', 'VI-14', 'pfs.endo_base', '',
                       'stands in for the rule that a surgical endoscopy includes the diagnostic endoscopy.')
        # the service date the stage records it for: none (refutation round 3, falsegreen-11: the document's two
        # dates of service disagree, so its context establishes none; this stand-in had named 2026-10-21)
        return [{'code': code, 'service_date': None,
                 'facts': [fact(code, 'status', 'A'), fact(code, 'mult_proc', '3'), fact(code, 'endo_base', '45378')],
                 'passages': [rule], 'lookups': [f'pfs {code} 2026-10-21', 'passages pfs.endo_base'],
                 'notes': ['NCCI procedure-to-procedure edits are not connected, so code pairs are not verified.']}
                for code in ('45385', '45380')]

    def confirm_extent(self):
        """The reviewer confirms 45385's verified extent candidate through the real endpoint; the re-assessment it
        queues is recorded here as the engine makes it, reading the revision's confirmation (jobs.confirmed_findings).
        """
        candidate = self.verified('extent')
        with mock.patch('studio.jobs.reassess_after_confirmation'):
            response = self.confirm('extent', candidate)
        self.assertEqual(response.status_code, 201, response.content)
        confirmation = models.FindingConfirmation.objects.get(clarification=self.questions['extent'])
        self.jobs((models.Job.ASSESS,))
        self.save([self.entry(name, peer=True) for name in h2.ADAPTERS],
                  self.result(2, jobs.confirmed_findings(self.revision)))
        return confirmation

    # --- the scenarios, serialized ------------------------------------------------------------------------------------

    def detail(self, user):
        self.encounter.refresh_from_db()
        membership = models.Membership.objects.get(user=user, workspace=self.ws)
        return serializers.encounter_detail(self.encounter, membership), serializers.encounter_summary(self.encounter)

    def scenarios(self):
        """{fixture: (prefix, detail JSON, list row JSON)} and the final scenario's trace, as the API serves them: the
        release's (HARNESS.md 12.10: no confirmation is offered), then, with STUDIO_OFFER_CONFIRMATIONS=True, the
        dormant confirmation path's - a confirmed finding, and the final scenario as that path offers it (made last, so
        the earlier fixtures' times keep their ranks)."""
        out = {}
        prefix, title = HARNESS2_SCENARIOS['encounter-harness2-peer.json']
        self.phase1(title)
        self.jobs((models.Job.ASTRA_PEER,), models.Job.RUNNING)
        review.refresh_state(self.encounter)
        out['encounter-harness2-peer.json'] = (prefix, *self.detail(self.reviewer))
        prefix, title = HARNESS2_SCENARIOS['encounter-harness2-final.json']
        self.phase1(title)
        self.phase2()
        out['encounter-harness2-final.json'] = (prefix, *self.detail(self.owner))
        trace = serializers.trace_json(self.encounter)
        with override_settings(STUDIO_OFFER_CONFIRMATIONS=True):  # the dormant confirmation path (HARNESS.md 12.10)
            prefix, title = HARNESS2_SCENARIOS['encounter-harness2-confirmed.json']
            self.phase1(title)
            self.phase2()
            self.confirm_extent()
            out['encounter-harness2-confirmed.json'] = (prefix, *self.detail(self.reviewer))
            prefix, title = HARNESS2_SCENARIOS['encounter-harness2-dormant.json']
            self.phase1(title)
            self.phase2()
            out['encounter-harness2-dormant.json'] = (prefix, *self.detail(self.owner))
        return out, trace

    def test_the_harness2_fixtures_are_what_the_serializer_emits(self):
        generated, trace = self.scenarios()
        texts = {name: (json.dumps(detail, ensure_ascii=False), json.dumps(row, ensure_ascii=False))
                 for name, (_, detail, row) in generated.items()}
        stable = StableIds([text for pair in texts.values() for text in pair] + [json.dumps(trace)])
        details, rows = {}, {}
        for name, (prefix, _, _) in generated.items():
            details[name], rows[name] = stable(texts[name][0], prefix), stable(texts[name][1], prefix)
        details[HARNESS2_TRACE] = stable(json.dumps(trace, ensure_ascii=False),
                                         HARNESS2_SCENARIOS['encounter-harness2-final.json'][0])
        listing = _fixture('encounters.json')
        kept = [row for row in listing['encounters'] if row['id'] not in {row['id'] for row in rows.values()}]
        if WRITE_FIXTURES:
            for name, data in details.items():
                (FIXTURES / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
            new = sorted(rows.values(), key=lambda row: row['created_at'], reverse=True)
            (FIXTURES / 'encounters.json').write_text(
                json.dumps({'encounters': new + kept}, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        for name, data in details.items():
            with self.subTest(name):
                committed = _fixture(name)
                self.assertEqual(sorted(shape(committed) ^ shape(data)), [],
                                 f'{name} no longer has the shape the serializer emits; regenerate it with '
                                 'CPT_STUDIO_WRITE_FIXTURES=1 and build the website for the change')
        listed = {row['id']: row for row in _fixture('encounters.json')['encounters']}
        for name, row in rows.items():
            with self.subTest(f'encounters.json {name}'):
                self.assertIn(row['id'], listed)
                self.assertEqual(sorted(shape(listed[row['id']]) ^ shape(row)), [])
                self.assertEqual(listed[row['id']]['state'], row['state'])
