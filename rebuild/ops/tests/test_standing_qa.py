"""The standing-authority runner (ops/standing_qa.py), offline: no network, no Django, no database, no credential.

What each group proves, stated so a reader can see how it would fail:
  · AUTHORITY AND DECLARATION — the committed authority record says what the runner implements; the committed TEST
    declaration is exactly the template filled; it parses to what it states; the template itself, a wrong authority id,
    the historical campaign/authority/root/database, ANY money limit (a line, a decorated second line, a number for the
    ceiling, an old stage form, a budget name), owner words that are not verbatim, an authority record that is not the
    one named, an uncommitted or modified declaration, unsafe bounds and a revocation are each refused; a command that
    sends refuses a test declaration.
  · NO CEILING — wherever a limit would stand (declaration, limits, their records, attempts, runs, status) it is None.
  · ADMISSION — an eligible synthetic request under the new authority is admitted and its attempt carries the run and
    attempt identities; the Stop file, a campaign stop, an open attempt, a failed or passed stage, a missing
    prerequisite, no open run, the run's cap, the stage's send count and changed terms are each refused; no money limit
    is invented (a large maximum is admitted, bounded by the per-request limits instead).
  · DUPLICATES AND INPUTS — a send that already has an attempt, a send its run did not select, an input its run does not
    allow and a restricted development original are refused at the last door before a send.
  · RUNS AND RECONCILIATION — gapless runs, one open; an attempt left without an outcome is recorded interrupted_unknown,
    its stage failed and its run closed as interrupted, and the path stays stopped; a closed partial run keeps its stage
    open; remaining sends skip attempted and unexercisable ones; batches never split a mapping form from its encounter.
  · CONFIGURATION — the eligible configuration passes; a contract flag, a non-QA database, the installed database, tree
    or state, a layout socket, another model or rate, an invalid profile, a profile past the per-request bounds and a
    wrong pricing version are each a problem.
  · CREDENTIAL AND DOOR — the declared credential file with the wrong mode is refused; a send outside the ruled-mutation
    door, or through a door opened for another declaration or commit, is refused; with no live declaration committed,
    `run` and `preflight` refuse before any credential is read.
  · PREFLIGHT — one GET to the models endpoint of the declared model, recorded before it leaves, the response retained,
    the returned id compared; another id, an error, another URL or method, a second request and the Stop file each fail
    or refuse; no key is retained; it is never generation proof, and `run` requires a matching one.
  · REQUEST BOUNDS — the capture refuses a request naming another model or asking for more output than the bound, before
    it is recorded or sent.
  · HISTORICAL — the historical runner refuses run/reopen/recover on the historical root before reading anything, keeps
    `status` and `plan` readable, its declaration is byte-identical, its declaration and ledger are refused here.
  · PLANS — the plan definitions: model_check 1, mapping 10 (f1-f6), the notes comparison 28 (14 cases x 2 requests),
    D30/D31-structure and transcription not established; the declared send counts equal the plans; flags agree with the
    historical runner's.
  · PRICING — the pricing command reproduces the historical declaration's versions for claude-sonnet-5 (positive
    control) and refuses claude-sonnet-5-5 while the application has no profile for it.
No socket is opened (network_guard); the provider is an in-process MockTransport.
"""
import dataclasses
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc
from ops import sonnet5_qa as sq
from ops import standing_qa as st
from . import network_guard

REPOSITORY = Path(__file__).resolve().parents[3]
REBUILD = REPOSITORY / 'rebuild'
FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'standing-declaration-test.md'
RECORD = REPOSITORY / st.AUTHORITY_RECORD
HISTORICAL_DECLARATION = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
HISTORICAL_DECLARATION_SHA256 = '76bfb6af8dea0d7184be00e7ca9d30f3c1bbc99f62057b1002f3d3643efb5d15'
SYNTHETIC_KEY = 'sk-ant-api03-SYNTHETIC-STANDING-OFFLINE-KEY-222222222222222222222222222222222-CCCCCCCC'
GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic Test',
       '-c', 'user.email=synthetic@test.invalid']
DECLARATION_NAME = '20261001-quillmd-v1-standing-api-testing.md'
RUNNER_COMMIT = '1' * 40


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


def scratch(test):
    directory = Path(tempfile.mkdtemp(prefix='standing-test-'))
    test.addCleanup(shutil.rmtree, directory, True)
    return directory


def git(root, *args, check=True):
    return subprocess.run([*GIT, '-C', str(root), *args], capture_output=True, check=check)


def fixture_text():
    return FIXTURE.read_text(encoding='utf-8')


def repository(test, text, *, record=None, name=DECLARATION_NAME, commit=True):
    """A scratch checkout holding `text` as a committed declaration and the authority record (the real one by default)."""
    root = scratch(test)
    git(root, 'init', '-q')
    folder = root / 'docs' / 'foundation' / 'mutations'
    folder.mkdir(parents=True)
    (root / st.AUTHORITY_RECORD).parent.mkdir(parents=True)
    (root / st.AUTHORITY_RECORD).write_bytes(RECORD.read_bytes() if record is None else record)
    path = folder / name
    path.write_text(text, encoding='utf-8')
    git(root, 'add', '--', st.AUTHORITY_RECORD)
    if commit:
        git(root, 'add', '--', str(path.relative_to(root)))
    git(root, 'commit', '-q', '-m', 'Synthetic standing declaration')
    return root, path


def parse(test, text=None, *, uses=('live', 'test'), record=None):
    root, path = repository(test, fixture_text() if text is None else text, record=record)
    return st.declared_standing(path, repository=root, uses=uses, out=io.StringIO())


def edited(old, new, text=None, count=1):
    text = fixture_text() if text is None else text
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def fill_template(values, use, where):
    """The template's declaration part, its <FILL …> placeholders replaced in order, the use and the 'Where it runs'
    lines substituted — the one recipe by which the committed TEST declaration was made."""
    text = st.TEMPLATE.read_text(encoding='utf-8')
    body = text[text.index('# Declaration —'):]
    parts = re.split(r'<FILL[^>]*>', body)
    assert len(parts) - 1 == len(values)
    out = parts[0] + ''.join(value + part for value, part in zip(values, parts[1:]))
    out = edited('declaration_use: live', f'declaration_use: {use}', out)
    for old, new in where.items():
        out = edited(old, new, out)
    return out


FIXTURE_VALUES = ['3', '15', '0.30', 'disabled', 'medium'] + ['configured-v1:' + c * 64 for c in 'abcd']
FIXTURE_WHERE = {
    'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261001': 'root: /nonexistent/standing-qa-test-root',
    'qa_database: quillmd_qa_standing_20261001': 'qa_database: quillmd_qa_v2_auth_fixture',
    'credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key':
        'credential_file: /nonexistent/standing-qa-test-root/credential/anthropic-api-key',
    'qa_database_password_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password':
        'qa_database_password_file: /nonexistent/standing-qa-test-root/qa-db/password',
    'restricted_inputs_ledger: /opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/metadata/'
    '053-original-dev40-exact-rights-ledger.json': 'restricted_inputs_ledger: /nonexistent/standing-qa-test-root/'
                                                    'rights-ledger.json'}
FIXTURE_HEAD = ('# TEST DECLARATION — used only by rebuild/ops/tests/test_standing_qa.py (declaration_use: test; never '
                'sends)\n\n')


def rights_ledger(test, restricted=(), authorized=()):
    """A synthetic rights ledger in the custody shape: each restricted hash `paid_or_model_stage1_authorized: false`."""
    path = scratch(test) / 'rights-ledger.json'
    records = ([{'id': f'R{i}', 'sha256': h, 'paid_or_model_stage1_authorized': False} for i, h in enumerate(restricted)]
               + [{'id': f'A{i}', 'sha256': h, 'paid_or_model_stage1_authorized': True} for i, h in enumerate(authorized)])
    data = json.dumps({'records': records}).encode()
    path.write_bytes(data)
    return str(path), hashlib.sha256(data).hexdigest()


RESTRICTED_SAMPLE = ('f' * 64, 'e' * 64)


class Base(unittest.TestCase):
    def campaign(self, declaration=None, restricted=RESTRICTED_SAMPLE):
        declaration = parse(self) if declaration is None else declaration
        ledger, digest = rights_ledger(self, restricted)
        declaration = dataclasses.replace(declaration, restricted_inputs_ledger=ledger,
                                          restricted_inputs_ledger_sha256=digest)
        root = scratch(self) / 'campaign'
        campaign = st.StandingCampaign(declaration, root)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        return campaign

    def open_model_check_run(self, campaign, cap=1):
        return st.begin_run(campaign, 'model_check', st.standing_plan('model_check'), None, cap,
                            {'runner_commit': RUNNER_COMMIT})

    def model_check_attempt(self, campaign, number=None, form=sq.FORM_SHA256, maximum='0.050000', **changes):
        d = campaign.declaration
        number = len(campaign.ledger.rows()) + 1 if number is None else number
        record = {'number': number, 'campaign': d.campaign, 'authority_id': d.authority_id, 'stage': 'model_check',
                  'maximum_cost': maximum, 'exposure_bound': format(Decimal(maximum) * pc.GEO_MARGIN, 'f'),
                  'rates': d.rates.as_dict(), 'form_sha256': form, 'notes_sha256': sq.NOTES_SHA256,
                  'declaration_sha256': d.sha256, 'declaration_commit': d.commit, 'limits': campaign.limits().record(),
                  'terms': campaign.pinned_terms().record(), 'runner_commit': RUNNER_COMMIT, 'started_at': pc.now()}
        record.update(changes)
        return record

    def completed(self, campaign, number):
        campaign.ledger.write_outcome(number, {'class': 'completed', 'usage': {
            'input_tokens': 1000, 'output_tokens': 200, 'inference_geo': 'global'}})

    def pass_model_check(self, campaign):
        run = self.open_model_check_run(campaign)
        campaign.admit('model_check', '0.05', runner_commit=RUNNER_COMMIT)
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        campaign.ledger.write_stage('model_check', 'passed', {'attempt': attempt['number']})
        campaign.runs.close(campaign.ledger, run['run'], {'closed_as': 'decided', 'sends': [
            {'send': {'id': st.MODEL_CHECK_SEND}, 'attempt': attempt['number'], 'stops_stage': False}]})
        return attempt

    def open_notes_run(self, campaign, sends, cap=10):
        inputs = sq.stages_module().frozen_inputs()
        return st.begin_run(campaign, 'notes_comparison', sends, inputs, cap, {'runner_commit': RUNNER_COMMIT}), inputs

    def notes_attempt(self, campaign, send, inputs, changes=None):
        d = campaign.declaration
        record = {'number': len(campaign.ledger.rows()) + 1, 'campaign': d.campaign, 'authority_id': d.authority_id,
                  'stage': 'notes_comparison', 'send': send.record(), 'maximum_cost': '0.100000',
                  'rates': d.rates.as_dict(), 'form_sha256': st.send_inputs(send, inputs)['form_sha256'],
                  'limits': campaign.limits().record(), 'terms': campaign.pinned_terms().record(),
                  'runner_commit': RUNNER_COMMIT, 'started_at': pc.now()}
        record.update(changes or {})
        return record


# ── authority and declaration ────────────────────────────────────────────────────────────────────────────────────

class AuthorityAndDeclarationTests(Base):
    def test_the_committed_authority_record_states_what_the_runner_implements(self):
        record = json.loads(RECORD.read_text(encoding='utf-8'))
        self.assertEqual((record['authority_id'], record['mode']), (st.AUTHORITY_ID, st.MODE))
        self.assertIsNone(record['owner_imposed_monetary_ceiling'])
        self.assertIs(record['per_batch_monetary_confirmation_required'], False)
        self.assertEqual(record['historical']['preserved_authority'], st.HISTORICAL['authority_id'])
        template = st.TEMPLATE.read_text(encoding='utf-8')
        words = re.search(r'^owner_words: (.*)$', template, re.M).group(1)
        self.assertEqual(words, record['owner_words'])                              # verbatim, typos and double space
        self.assertIn('all the  stuuf', words)
        sha = re.search(r'^authority_record_sha256: ([0-9a-f]{64})$', template, re.M).group(1)
        self.assertEqual(sha, hashlib.sha256(RECORD.read_bytes()).hexdigest())

    def test_the_test_declaration_is_exactly_the_template_filled(self):
        self.assertEqual(fixture_text(), FIXTURE_HEAD + fill_template(FIXTURE_VALUES, 'test', FIXTURE_WHERE))

    def test_the_test_declaration_parses_to_exactly_what_it_states(self):
        out = io.StringIO()
        root, path = repository(self, fixture_text())
        d = st.declared_standing(path, repository=root, uses=('test',), out=out)
        self.assertEqual((d.campaign, d.authority_id, d.mode, d.use), (st.CAMPAIGN, st.AUTHORITY_ID, st.MODE, 'test'))
        self.assertIsNone(d.monetary_ceiling)
        self.assertIsNone(d.total_limit)
        self.assertIs(d.per_batch_monetary_confirmation, False)
        self.assertEqual((d.provider, d.model, d.thinking, d.effort, d.inference_geo),
                         ('anthropic', 'claude-sonnet-5-5', 'disabled', 'medium', ''))
        self.assertEqual(d.rates, pc.Rates('3', '15', '0.30'))
        self.assertEqual(dict(d.pricing_versions), {'model_check': 'configured-v1:' + 'a' * 64,
                                                    'mapping': 'configured-v1:' + 'b' * 64,
                                                    'ordinary_notes': 'configured-v1:' + 'c' * 64,
                                                    'ordinary_notes_field_relations': 'configured-v1:' + 'd' * 64})
        self.assertEqual((d.concurrency, d.automatic_retries, d.max_sends_per_run, d.max_output_tokens_per_request,
                          d.request_deadline_seconds), (1, 'none', 10, 20000, 180))
        self.assertEqual([(s.id, s.sends, s.requires, s.limit) for s in d.stages],
                         [('model_check', 1, None, None), ('mapping', 10, 'model_check', None),
                          ('notes_comparison', 28, 'model_check', None)])
        self.assertEqual(d.owner_words, json.loads(RECORD.read_text())['owner_words'])
        self.assertIn(d.commit, out.getvalue())
        self.assertIn('monetary ceiling none', out.getvalue())

    def test_the_template_is_never_a_declaration(self):
        with self.assertRaisesRegex(pc.Refused, 'template placeholders'):
            parse(self, st.TEMPLATE.read_text(encoding='utf-8'))

    def test_the_template_filled_for_live_use_parses_and_names_the_live_places(self):
        values = ['3', '15', '0.30', 'disabled', 'medium'] + ['configured-v1:' + c * 64 for c in 'abcd']
        d = parse(self, fill_template(values, 'live', {}), uses=('live',))
        st.require_live(d)
        self.assertEqual((d.root, d.qa_database), (str(st.LIVE_ROOT), st.DATABASE_NAME))
        self.assertEqual(d.credential_file, str(sq.HISTORICAL_ROOT / 'credential' / 'anthropic-api-key'))

    def test_a_wrong_authority_id_is_refused(self):
        with self.assertRaisesRegex(pc.Refused, 'names the authority'):
            parse(self, edited('authority_id: quillmd-v1-private-api-testing-standing-20260930',
                               'authority_id: quillmd-v1-private-api-testing-standing-20261231'))
        with self.assertRaisesRegex(pc.Refused, 'standing authorization'):
            parse(self, edited('standing authority quillmd-v1-private-api-testing-standing-20260930 with',
                               'standing authority quillmd-v1-something-else with'))
        with self.assertRaisesRegex(pc.Refused, 'standing authorization'):
            parse(self, edited('authorization: owner 2026-09-30', 'authorization: owner 2026-10-01'))

    def test_the_historical_campaign_authority_root_and_database_are_refused(self):
        cases = [
            ('campaign: quillmd-v1-standing-api-testing-20261001', 'campaign: quillmd-v1-sonnet5-staged-40', 'new campaign'),
            ('authority_id: quillmd-v1-private-api-testing-standing-20260930',
             'authority_id: quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk', 'names the authority'),
            ('root: /nonexistent/standing-qa-test-root', 'root: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign',
             'its own'),
            ('root: /nonexistent/standing-qa-test-root',
             'root: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/standing', 'its own'),
            ('root: /nonexistent/standing-qa-test-root', 'root: /opt/meddoc-pro/rebuild/.runtime', 'its own'),
            ('root: /nonexistent/standing-qa-test-root', 'root: /var/lib/quillmd/standing', 'its own'),
            ('qa_database: quillmd_qa_v2_auth_fixture', 'qa_database: quillmd_qa_sonnet5', 'synthetic database of its own'),
            ('qa_database: quillmd_qa_v2_auth_fixture', 'qa_database: quillmd_fresh', 'synthetic database of its own')]
        for old, new, why in cases:
            with self.subTest(new=new), self.assertRaisesRegex(pc.Refused, why):
                parse(self, edited(old, new))

    def test_any_money_limit_is_refused(self):
        anchor = 'max_sends_per_run: 10\n'
        variants = [
            edited(anchor, anchor + 'total_limit_provider_usd: 40.00\n'),
            edited(anchor, anchor + '- monetary_ceiling: 1000000\n'),
            edited('monetary_ceiling: none', 'monetary_ceiling: 1000000'),
            edited('monetary_ceiling: none', 'monetary_ceiling: 0'),
            edited('stage: mapping sends 10 requires model_check_passed',
                   'stage: mapping limit_provider_usd 25.00 requires model_check_passed'),
            edited(anchor, anchor + 'budget_usd: 5\n'),
            edited(anchor, anchor + '> **spend_limit**: 100\n'),
            edited(anchor, anchor + 'unused_stage_budget_transfers: no\n'),
            edited(anchor, anchor + 'stage: extra max_requests 10\n'),
            edited(anchor, anchor + 'ceiling_usd: 40\n'),
            edited(anchor, anchor + '* monetary_cap: 5\n'),
            edited(anchor, anchor + '| max_spend | : 100 |\n'),
            edited('## Money', '## Money\n\nCost ceiling: $40 for this campaign.'),
            edited('mode: standing_unlimited_monetary', 'mode: staged_monetary_limits'),
            edited('per_batch_monetary_confirmation: not_required', 'per_batch_monetary_confirmation: required')]
        for text in variants:
            with self.subTest(text=text[text.index('## Money'):text.index('## Model')][:200]):
                with self.assertRaises(pc.Refused):
                    parse(self, text)

    def test_owner_words_must_be_the_records_verbatim(self):
        with self.assertRaisesRegex(pc.Refused, 'verbatim'):
            parse(self, edited('also add thsi propmt', 'also add this prompt'))
        with self.assertRaisesRegex(pc.Refused, 'verbatim'):
            parse(self, edited('all the  stuuf', 'all the stuuf'))
        record = RECORD.read_bytes().replace(b'"owner_words": "also add', b'"owner_words": "Also add')
        with self.assertRaisesRegex(pc.Refused, 'sha256 differs'):
            parse(self, record=record)
        record_text = RECORD.read_text().replace('"owner_imposed_monetary_ceiling": null',
                                                 '"owner_imposed_monetary_ceiling": "40.00"')
        sha = hashlib.sha256(record_text.encode()).hexdigest()
        text = edited('authority_record_sha256: 9178279297a173697f8becc89d0ab24f510b87231c3d692934e8d60fce41652c',
                      f'authority_record_sha256: {sha}')
        with self.assertRaisesRegex(pc.Refused, 'no owner ceiling'):
            parse(self, text, record=record_text.encode())

    def test_an_uncommitted_modified_or_misplaced_declaration_is_refused(self):
        root, path = repository(self, fixture_text(), commit=False)
        with self.assertRaisesRegex(pc.Refused, 'tracked, committed and unmodified'):
            st.declared_standing(path, repository=root, uses=('test',), out=io.StringIO())
        root, path = repository(self, fixture_text())
        path.write_text(edited('max_sends_per_run: 10', 'max_sends_per_run: 11'), encoding='utf-8')
        with self.assertRaisesRegex(pc.Refused, 'tracked, committed and unmodified'):
            st.declared_standing(path, repository=root, uses=('test',), out=io.StringIO())
        elsewhere = root / 'docs' / DECLARATION_NAME
        elsewhere.write_text(fixture_text(), encoding='utf-8')
        with self.assertRaisesRegex(pc.Refused, 'mutations'):
            st.declared_standing(elsewhere, repository=root, uses=('test',), out=io.StringIO())

    def test_unsafe_bounds_are_refused(self):
        cases = [('concurrency: 1', 'concurrency: 2', 'one at a time'),
                 ('automatic_retries: none', 'automatic_retries: 2', 'never re-sent'),
                 ('max_output_tokens_per_request: 20000', 'max_output_tokens_per_request: 64000', 'at most 21333'),
                 ('request_deadline_seconds: 180', 'request_deadline_seconds: 900', 'at most 600'),
                 ('stage: notes_comparison sends 28', 'stage: transcription sends 28', 'No standing plan'),
                 ('stage: mapping sends 10 requires model_check_passed', 'stage: mapping sends 10 requires none\n'
                  'stage: mapping sends 10 requires none', 'twice')]
        for old, new, why in cases:
            with self.subTest(new=new), self.assertRaisesRegex(pc.Refused, why):
                parse(self, edited(old, new))

    def test_a_revocation_is_refused(self):
        with self.assertRaisesRegex(pc.Refused, 'revocation'):
            parse(self, edited('## Retained evidence', 'This authority is revoked.\n\n## Retained evidence'))

    def test_every_command_that_sends_refuses_a_test_declaration(self):
        with self.assertRaisesRegex(pc.Refused, 'live use'):
            parse(self, uses=('live',))
        with self.assertRaisesRegex(pc.Refused, 'Only a live declaration sends'):
            st.require_live(parse(self))


# ── no ceiling, anywhere ─────────────────────────────────────────────────────────────────────────────────────────

class NoCeilingTests(Base):
    def test_no_ceiling_is_none_everywhere_and_never_a_number(self):
        campaign = self.campaign()
        d, limits = campaign.declaration, campaign.declaration.limits()
        self.assertIsNone(d.monetary_ceiling)
        self.assertIsNone(d.total_limit)
        self.assertTrue(all(stage.limit is None for stage in d.stages))
        self.assertIsNone(limits.total)
        self.assertTrue(all(stage.limit is None for stage in limits.stages))
        record = limits.record()
        self.assertIsNone(record['monetary_ceiling'])
        self.assertTrue(all(entry['limit_provider_usd'] is None for entry in record['stages'].values()))
        self.assertEqual(st.StandingLimits.from_record(json.loads(json.dumps(record)), 'x'), limits)
        run = self.open_model_check_run(campaign)
        self.assertIsNone(run['monetary_ceiling'])
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)
        written = json.loads((campaign.root / 'ledger' / '001-attempt.json').read_text())
        self.assertIsNone(written['monetary_ceiling'])
        self.assertIsNone(written['limits']['monetary_ceiling'])
        self.assertIsNone(campaign.limits().total)

        def money_values(value, path=''):
            """Every value under a key naming a ceiling or a money limit."""
            if isinstance(value, dict):
                for key, item in value.items():
                    if re.search(r'ceiling|limit_provider_usd|^limit$|total_limit', key):
                        yield path + '/' + key, item
                    yield from money_values(item, path + '/' + key)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    yield from money_values(item, f'{path}[{index}]')
        for where, value in [*money_values(record), *money_values(written), *money_values(run)]:
            self.assertIsNone(value, where)
        self.completed(campaign, 1)
        campaign.ledger.release()
        out = io.StringIO()
        root, path = repository(self, fixture_text())
        with redirect_stderr(io.StringIO()):
            report = st.status(campaign.root, path, repository=root, out=out)
        campaign.ledger.acquire()
        self.assertIsNone(report['monetary_ceiling'])
        self.assertIsNone(report['total']['limit'])
        self.assertTrue(all(stage['limit'] is None for stage in report['stages'].values()))
        for where, value in money_values(json.loads(out.getvalue())):
            self.assertIsNone(value, where)

    def test_a_recorded_money_figure_is_not_a_standing_record(self):
        record = parse(self).limits().record()
        for broken in ({**record, 'monetary_ceiling': '1000000'}, {**record, 'monetary_ceiling': 0},
                       {**record, 'stages': {**record['stages'], 'mapping': {**record['stages']['mapping'],
                                                                              'limit_provider_usd': '25.00'}}},
                       {**record, 'total_limit_provider_usd': '40.00'}, {**record, 'mode': 'staged'}):
            with self.subTest(broken=broken), self.assertRaises(pc.Refused):
                st.StandingLimits.from_record(broken, 'Attempt 1')


# ── admission ────────────────────────────────────────────────────────────────────────────────────────────────────

class AdmissionTests(Base):
    def test_an_eligible_synthetic_request_is_admitted_under_the_new_authority(self):
        campaign = self.campaign()
        run = self.open_model_check_run(campaign)
        bound = campaign.admit('model_check', '0.05', runner_commit=RUNNER_COMMIT)
        self.assertEqual(bound, Decimal('0.05') * pc.GEO_MARGIN)
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)
        written = json.loads((campaign.root / 'ledger' / '001-attempt.json').read_text())
        self.assertEqual((written['campaign'], written['authority_id'], written['mode']),
                         (st.CAMPAIGN, st.AUTHORITY_ID, st.MODE))
        self.assertEqual((written['run'], written['run_id']), (run['run'], 'run-0001'))
        self.assertEqual(written['attempt_id'], f'{st.CAMPAIGN}/run-0001/attempt-001')
        self.assertEqual((written['send'], written['send_key']), ({'id': st.MODEL_CHECK_SEND},
                                                                  'model_check:' + st.MODEL_CHECK_SEND))
        self.assertEqual(set(written['engine_files']), set(st.WATCHED_FILES))
        self.assertIn('rebuild/core/mapping_wire.py', written['engine_files'])
        self.assertEqual(campaign.rows()[0][0]['number'], 1)

    def test_no_money_limit_is_invented(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        self.assertEqual(campaign.admit('model_check', '1000000'), Decimal('1000000') * pc.GEO_MARGIN)

    def test_the_stop_file_and_a_campaign_stop_admit_nothing(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        campaign.stop_file().write_text('')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            campaign.admit('model_check', '0.05')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            campaign.ledger.write_attempt(self.model_check_attempt(campaign))
        campaign.stop_file().unlink()
        campaign.stop_file().mkdir()                               # (any kind of file: a directory stops it too)
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            campaign.admit('model_check', '0.05')
        campaign.stop_file().rmdir()
        campaign.ledger.write_stop({'reason': 'synthetic'})
        with self.assertRaisesRegex(pc.Refused, 'campaign is stopped'):
            campaign.admit('model_check', '0.05')
        self.assertEqual(campaign.ledger.rows(), [])

    def test_an_unreconciled_open_attempt_admits_nothing(self):
        campaign = self.pass_model_check_campaign()
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        self.open_notes_run(campaign, plan[:2])
        campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs))
        with self.assertRaisesRegex(pc.Refused, 'no outcome'):
            campaign.admit('notes_comparison', '0.10')
        with self.assertRaisesRegex(pc.Refused, 'no outcome'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[1], inputs))

    def pass_model_check_campaign(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        return campaign

    def test_a_stage_before_its_prerequisite_passed_is_refused(self):
        campaign = self.campaign()
        with self.assertRaisesRegex(pc.Refused, 'requires model_check'):
            campaign.stage_open('notes_comparison')

    def test_a_failed_or_passed_stage_admits_nothing(self):
        campaign = self.pass_model_check_campaign()
        with self.assertRaisesRegex(pc.Refused, 'already passed'):
            campaign.admit('model_check', '0.05')
        campaign.ledger.write_stage('mapping', 'failed', {'reasons': ['synthetic safety failure']})
        with self.assertRaisesRegex(pc.Refused, 'path is stopped'):
            campaign.stage_open('mapping')

    def test_no_open_run_the_runs_cap_and_the_stages_count_are_enforced(self):
        campaign = self.campaign()
        with self.assertRaisesRegex(pc.Refused, 'No run of stage model_check is open'):
            campaign.admit('model_check', '0.05')
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        run, _ = self.open_notes_run(campaign, plan[:3], cap=1)
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        with self.assertRaisesRegex(pc.Refused, 'has made all 1 sends'):
            campaign.admit('notes_comparison', '0.10')
        with self.assertRaisesRegex(pc.Refused, 'has made all 1 sends'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[1], inputs))
        # (the model check declares ONE send: a second, in any run, is refused)
        small = dataclasses.replace(campaign.declaration)
        self.assertEqual(campaign.limits().stage('model_check').max_requests, small.stage('model_check').sends)

    def test_the_stages_declared_send_count_is_enforced(self):
        d = parse(self, edited('stage: notes_comparison sends 28', 'stage: notes_comparison sends 1'))
        campaign = self.campaign(d)
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        self.open_notes_run(campaign, plan[:2])
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        with self.assertRaisesRegex(pc.Refused, 'all 1 sends it declares'):
            campaign.admit('notes_comparison', '0.10')

    def test_terms_other_than_the_pinned_ones_admit_nothing(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        edited_declaration = dataclasses.replace(campaign.declaration, rates=pc.Rates('1', '5', '0.10'))
        other = st.StandingCampaign(edited_declaration, campaign.root)
        with self.assertRaisesRegex(pc.Refused, 'differ from those the ledger'):
            other.stage_open('notes_comparison')


# ── duplicates and inputs ────────────────────────────────────────────────────────────────────────────────────────

class DuplicateAndInputTests(Base):
    def test_a_send_that_already_has_an_attempt_is_never_attempted_again(self):
        campaign = self.campaign()
        attempt = self.pass_model_check(campaign)
        self.assertEqual(attempt['send_key'], 'model_check:' + st.MODEL_CHECK_SEND)
        self.open_model_check_run(campaign)                         # (a second run naming the same send)
        with self.assertRaisesRegex(pc.Refused, 'never made twice'):
            campaign.ledger.write_attempt(self.model_check_attempt(campaign))
        self.assertEqual(st.remaining_sends(campaign, 'model_check', st.standing_plan('model_check')), [])

    def test_a_send_its_run_did_not_select_or_of_another_campaign_is_refused(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        self.open_notes_run(campaign, plan[:1])
        with self.assertRaisesRegex(pc.Refused, 'did not select'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[1], inputs))
        with self.assertRaisesRegex(pc.Refused, 'another campaign, authority or stage'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs,
                                                             {'campaign': st.HISTORICAL['campaign']}))
        with self.assertRaisesRegex(pc.Refused, 'another campaign, authority or stage'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs,
                                                             {'authority_id': st.HISTORICAL['authority_id']}))
        with self.assertRaisesRegex(pc.Refused, 'another campaign, authority or stage'):
            campaign.ledger.write_attempt(self.notes_attempt(campaign, plan[0], inputs, {'stage': 'mapping'}))

    def test_an_input_its_run_does_not_allow_is_refused(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        with self.assertRaisesRegex(pc.Refused, 'not one of the synthetic inputs'):
            campaign.ledger.write_attempt(self.model_check_attempt(campaign, form='0' * 64))

    def test_a_restricted_development_original_is_refused_before_any_send(self):
        restricted = sq.FORM_SHA256                                 # (pretend the fixed form were a restricted original)
        campaign = self.campaign(restricted=(restricted,))
        with self.assertRaisesRegex(pc.Refused, 'no provider upload'):
            self.open_model_check_run(campaign)
        self.assertIsNone(campaign.runs.current())
        # (and at the last door, should a run ever allow it)
        campaign = self.campaign(restricted=('9' * 64,))
        run = self.open_model_check_run(campaign)
        tampered = {**run, 'restricted_inputs': [sq.FORM_SHA256]}
        with patch.object(campaign.runs, 'current', return_value=tampered):
            with self.assertRaisesRegex(pc.Refused, 'no provider upload'):
                campaign.ledger.write_attempt(self.model_check_attempt(campaign))

    def test_the_rights_ledger_must_be_the_declared_one_and_readable(self):
        campaign = self.campaign()
        d = campaign.declaration
        self.assertEqual(st.restricted_hashes(d), frozenset(RESTRICTED_SAMPLE))
        with self.assertRaisesRegex(pc.Refused, 'sha256 differs'):
            st.restricted_hashes(dataclasses.replace(d, restricted_inputs_ledger_sha256='0' * 64))
        path, digest = rights_ledger(self, (), ('a' * 64,))           # (only an authorised original: no restriction)
        with self.assertRaisesRegex(pc.Refused, 'names no restricted original'):
            st.restricted_hashes(dataclasses.replace(d, restricted_inputs_ledger=path,
                                                     restricted_inputs_ledger_sha256=digest))
        broken = scratch(self) / 'broken.json'
        broken.write_bytes(b'{"records": [{"sha256": 7}]}')
        with self.assertRaisesRegex(pc.Refused, 'cannot be read whole'):
            st.restricted_hashes(dataclasses.replace(d, restricted_inputs_ledger=str(broken),
                                                     restricted_inputs_ledger_sha256=hashlib.sha256(
                                                         broken.read_bytes()).hexdigest()))

    @unittest.skipUnless(os.access('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/metadata/'
                                   '053-original-dev40-exact-rights-ledger.json', os.R_OK),
                         'the custody rights ledger is on the VPS only')
    def test_no_planned_input_is_a_restricted_original_in_the_real_rights_ledger(self):
        d = parse(self, fill_template(FIXTURE_VALUES, 'live', {}), uses=('live',))
        restricted = st.restricted_hashes(d)
        self.assertEqual(len(restricted), 40)
        inputs = sq.stages_module().frozen_inputs()
        for stage in ('model_check', 'mapping', 'notes_comparison'):
            for send in st.standing_plan(stage, inputs):
                self.assertNotIn(st.send_inputs(send, inputs)['form_sha256'], restricted, send.id)


# ── runs and reconciliation ──────────────────────────────────────────────────────────────────────────────────────

class RunsAndReconciliationTests(Base):
    def test_runs_are_gapless_with_at_most_one_open(self):
        campaign = self.campaign()
        run = self.open_model_check_run(campaign)
        self.assertEqual((run['run'], run['run_id'], run['sends']), (1, 'run-0001', [st.MODEL_CHECK_SEND]))
        with self.assertRaisesRegex(pc.Refused, 'already open'):
            self.open_model_check_run(campaign)
        campaign.runs.close(campaign.ledger, 1, {'closed_as': 'refused_before_attempt', 'sends': []})
        with self.assertRaises(FileExistsError):
            pc.write_new(campaign.root / 'runs' / '0001-closed.json', {'run': 1})
        self.assertEqual(self.open_model_check_run(campaign)['run'], 2)
        (campaign.root / 'runs' / 'stray.json').write_text('{}')
        with self.assertRaisesRegex(pc.Refused, 'not a run record'):
            campaign.runs.listing()

    def test_an_interrupted_attempt_is_reconciled_its_stage_failed_and_its_run_closed(self):
        campaign = self.campaign()
        self.open_model_check_run(campaign)
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)                       # (the process died here, mid-send)
        result = st.settle(campaign)
        self.assertEqual(result['recovered'], [1])
        self.assertEqual(result['failed_stages'], ['model_check'])
        self.assertEqual(result['run_closed_as_interrupted'], 1)
        outcome = json.loads((campaign.root / 'ledger' / '001-outcome.json').read_text())
        self.assertEqual(outcome['class'], 'interrupted_unknown')
        self.assertEqual(json.loads((campaign.root / 'runs' / '0001-closed.json').read_text())['closed_as'],
                         'interrupted')
        with self.assertRaisesRegex(pc.Refused, 'path is stopped'):
            campaign.stage_open('model_check')
        self.assertEqual(st.earlier_stops(campaign, 'model_check')[0]['attempt'], 1)

    def test_a_closed_partial_run_keeps_its_stage_open_and_its_attempts_decided(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        run, _ = self.open_notes_run(campaign, plan[:1])
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        self.assertEqual(campaign.ledger.undecided(), {'notes_comparison': [attempt['number']]})
        campaign.runs.close(campaign.ledger, run['run'], {'closed_as': 'partial', 'sends': [
            {'send': plan[0].record(), 'attempt': attempt['number'], 'stops_stage': False}]})
        self.assertEqual(campaign.ledger.undecided(), {})
        self.assertEqual(st.settle(campaign)['failed_stages'], [])
        self.assertEqual(campaign.ledger.stage_state('notes_comparison')['state'], 'open')
        left = st.remaining_sends(campaign, 'notes_comparison', plan)
        self.assertEqual([s.id for s in left], [s.id for s in plan[1:]])
        self.assertEqual(st.earlier_stops(campaign, 'notes_comparison'), [])

    def test_a_stopped_send_means_the_stage_can_never_pass(self):
        campaign = self.campaign()
        self.pass_model_check(campaign)
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('notes_comparison', inputs)
        run, _ = self.open_notes_run(campaign, plan[:1])
        attempt = self.notes_attempt(campaign, plan[0], inputs)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        campaign.runs.close(campaign.ledger, run['run'], {'closed_as': 'failed', 'sends': [
            {'send': plan[0].record(), 'attempt': attempt['number'], 'stops_stage': True, 'recorded_as': 'unsafe'}]})
        self.assertEqual(st.earlier_stops(campaign, 'notes_comparison')[0]['why'], 'it stopped the stage (unsafe)')

    def test_batches_keep_a_mapping_form_with_its_encounter_and_set_aside_orphans(self):
        inputs = sq.stages_module().frozen_inputs()
        plan = st.standing_plan('mapping', inputs)
        chosen, orphans = st.select_batch(plan, 8)
        self.assertEqual([s.id for s in chosen], ['mapping:f1-guidance-confirmation', 'mapping:f2-leave-checkboxes',
                                                  'mapping:f2b-leave-checkboxes-owner', 'mapping:f3-selection-instructions',
                                                  'mapping:f4-exam-grid', 'mapping:f5-negative-controls',
                                                  'mapping:f6a-long-answer', 'generation:f6a-long-answer'])
        self.assertEqual(orphans, [])
        rest = [s for s in plan if s not in chosen]
        self.assertEqual([s.id for s in st.select_batch(rest, 8)[0]],
                         ['mapping:f6b-admin-missing', 'generation:f6b-admin-missing'])
        self.assertEqual([s.id for s in st.select_batch(plan, 10)[0]], [s.id for s in plan])
        without_form = [s for s in plan if s.id != 'mapping:f6a-long-answer']
        chosen, orphans = st.select_batch(without_form, 10)
        self.assertEqual([s.id for s in orphans], ['generation:f6a-long-answer'])
        self.assertNotIn('generation:f6a-long-answer', [s.id for s in chosen])
        notes = st.standing_plan('notes_comparison', inputs)
        self.assertEqual(len(st.select_batch(notes, 10)[0]), 10)


# ── configuration ────────────────────────────────────────────────────────────────────────────────────────────────

def snapshot(declaration, root, stage='model_check', **changes):
    """An eligible configuration for `stage`, in settings_snapshot's shape."""
    values = {'database': {'NAME': declaration.qa_database, 'HOST': '127.0.0.1', 'PORT': '55731'},
              'state_dir': str(Path(root) / 'qa-state'), 'media_root': str(Path(root) / 'qa-state' / 'files'),
              'synthetic_only': True, 'data_mode': 'synthetic', 'ai_mode': 'live', 'provider': 'anthropic',
              'model': declaration.model, 'rates': declaration.rates.as_dict(), 'thinking': declaration.thinking,
              'effort': declaration.effort, 'inference_geo': declaration.inference_geo,
              'settings': st.expected_settings(stage),
              'request_profile': {'profile': 'synthetic-5-5-v1', 'max_output_tokens': 8000, 'timeout_seconds': 120},
              'pricing_version': declaration.pricing_version(st.STAGE_PRICING[stage][0])}
    for key, value in changes.items():
        if key == 'settings':
            values['settings'] = {**values['settings'], **value}
        else:
            values[key] = value
    return values


class ConfigurationTests(Base):
    def setUp(self):
        self.d = parse(self)
        self.root = scratch(self) / 'campaign'
        self.worktree = scratch(self) / 'worktree' / 'rebuild'

    def problems(self, stage='model_check', rebuild=None, **changes):
        return st.check_configuration(snapshot(self.d, self.root, stage, **changes), self.d, stage, self.root,
                                      rebuild=self.worktree if rebuild is None else rebuild)

    def test_the_eligible_configuration_passes_for_every_stage(self):
        for stage in ('model_check', 'mapping', 'notes_comparison'):
            self.assertEqual(self.problems(stage), [], stage)

    def test_a_contract_flag_other_than_the_stages_is_a_problem(self):
        cases = [('model_check', {'V3_FIELD_RELATIONS': True}), ('model_check', {'WM_NARRATIVE': True}),
                 ('model_check', {'QUILLMD_MAPPING_ASSISTANCE': True}), ('model_check', {'QUILLMD_WORD_ENGINE': 'v3'}),
                 ('notes_comparison', {'V3_FIELD_RELATIONS': True}), ('notes_comparison', {'V3_GENERATION_BATCHES': True}),
                 ('notes_comparison', {'V3_HISTORY_CONTEXT': True}), ('mapping', {'QUILLMD_MAPPING_ASSISTANCE_LIVE': False}),
                 ('mapping', {'QUILLMD_LAYOUT_SOCKET': '/run/quillmd/layout.sock'})]
        for stage, flags in cases:
            with self.subTest(stage=stage, flags=flags):
                found = self.problems(stage, settings=flags)
                self.assertTrue(found and all('contract flag' in p for p in found), found)

    def test_a_database_other_than_the_declared_qa_one_is_a_problem(self):
        cases = [{'NAME': 'quillmd_qa_sonnet5', 'HOST': '127.0.0.1', 'PORT': '55731'},
                 {'NAME': 'quillmd_qa_other', 'HOST': '127.0.0.1', 'PORT': '55731'},
                 {'NAME': self.d.qa_database, 'HOST': '10.0.0.5', 'PORT': '55731'},
                 {'NAME': 'quillmd_fresh', 'HOST': '127.0.0.1', 'PORT': '55438'}]
        for database in cases:
            with self.subTest(database=database):
                self.assertTrue(self.problems(database=database))
        installed = self.problems(database={'NAME': self.d.qa_database, 'HOST': '127.0.0.1', 'PORT': '55438'})
        self.assertTrue(any('installed release' in p for p in installed), installed)

    def test_the_installed_worker_route_is_a_problem(self):
        self.assertTrue(any('installed tree' in p for p in self.problems(rebuild=st.INSTALLED['tree'])))
        self.assertTrue(any('installed tree' in p for p in self.problems(rebuild=st.INSTALLED['tree'] / 'ops')))
        found = self.problems(state_dir='/var/lib/quillmd', media_root='/var/lib/quillmd/files')
        self.assertTrue(any('installed release\'s state' in p for p in found), found)
        self.assertTrue(any('not under the campaign root' in p for p in found), found)
        self.assertTrue(self.problems(state_dir=str(scratch(self) / 'elsewhere')))

    def test_another_mode_model_rate_or_profile_is_a_problem(self):
        cases = [{'synthetic_only': False}, {'data_mode': 'real'}, {'ai_mode': 'fixture'}, {'model': 'claude-sonnet-5'},
                 {'provider': 'openai'}, {'rates': {'input': '2', 'output': '10', 'cached': '0.20'}},
                 {'thinking': 'adaptive'}, {'effort': 'high'}, {'inference_geo': 'us'},
                 {'request_profile': {'invalid': 'no profile'}},
                 {'request_profile': {'profile': 'x', 'max_output_tokens': 20001, 'timeout_seconds': 120}},
                 {'request_profile': {'profile': 'x', 'max_output_tokens': 8000, 'timeout_seconds': 181}},
                 {'request_profile': {'profile': 'x', 'max_output_tokens': '8000', 'timeout_seconds': 120}},
                 {'pricing_version': 'configured-v1:' + 'e' * 64}]
        for change in cases:
            with self.subTest(change=change):
                self.assertTrue(self.problems(**change))


# ── credential and door ──────────────────────────────────────────────────────────────────────────────────────────

class CredentialAndDoorTests(Base):
    def test_the_credential_file_with_the_wrong_mode_is_refused(self):
        folder = scratch(self) / 'credential'
        folder.mkdir(mode=0o700)
        key = folder / 'anthropic-api-key'
        key.write_text(SYNTHETIC_KEY + '\n')
        d = dataclasses.replace(parse(self), credential_file=str(key))
        os.chmod(key, 0o644)
        with self.assertRaisesRegex(pc.Refused, 'mode 0600'):
            pc.load_credential(d.credential_file, d)
        os.chmod(key, 0o600)
        self.assertEqual(pc.load_credential(d.credential_file, d), SYNTHETIC_KEY)
        with self.assertRaisesRegex(pc.Refused, 'Only the declared credential_file'):
            pc.load_credential(str(folder / 'other'), d)

    def test_only_the_ruled_mutation_door_for_this_declaration_and_commit_opens(self):
        d = parse(self)
        relative = str(Path(d.path).relative_to(d.repository))
        with self.assertRaisesRegex(pc.Refused, 'ruled-mutation door'):
            st.require_door(d, {})
        with self.assertRaisesRegex(pc.Refused, 'another declaration'):
            st.require_door(d, {'RULED_MUTATION_DECLARATION': 'docs/foundation/mutations/20260928-quillmd-v1-sonnet5-'
                                                              'staged-campaign.md', 'RULED_MUTATION_DECL_COMMIT': d.commit})
        with self.assertRaisesRegex(pc.Refused, 'another commit'):
            st.require_door(d, {'RULED_MUTATION_DECLARATION': relative, 'RULED_MUTATION_DECL_COMMIT': '0' * 40})
        self.assertEqual(st.require_door(d, {'RULED_MUTATION_DECLARATION': relative,
                                             'RULED_MUTATION_DECL_COMMIT': d.commit})['commit'], d.commit)
        self.assertEqual(st.require_door(d, {'RULED_MUTATION_DECLARATION': d.path,
                                             'RULED_MUTATION_DECL_COMMIT': d.commit})['commit'], d.commit)

    def test_with_no_live_declaration_committed_nothing_is_read_or_sent(self):
        missing = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20261001-standing-test-never-committed.md'
        self.assertFalse(missing.exists())

        def forbidden(*args, **kwargs):
            raise AssertionError('a credential or a database password was read')
        with patch.object(st, 'DECLARATION', missing), patch.object(pc, 'load_credential', forbidden), \
                patch.object(pc, 'read_private', forbidden), patch.object(os, 'execve', forbidden), \
                patch.object(st, 'ensure_database', forbidden):
            for argv in (['run', '--stage', 'model_check'], ['preflight'], ['run', '--stage', 'notes_comparison']):
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertEqual(st.main(argv), 2, argv)
                self.assertIn('REFUSED', err.getvalue())


# ── the two processes: outer (the door, then a scrubbed exec) and inner (re-checks, then the preflight) ──────────────

class ProcessTests(Base):
    """outer() and inner() for the preflight in a scratch checkout whose LIVE declaration names scratch places (the
    runner's constants patched to them): what outer() hands the request process, and inner() re-checking everything
    and making the ONE models request through the guard (the network is a MockTransport)."""

    def setUp(self):
        self.repo = scratch(self)
        self.live_root = self.repo / 'runtime' / 'standing'
        secret_dir = self.repo / 'secrets'
        secret_dir.mkdir(mode=0o700)
        self.key = secret_dir / 'anthropic-api-key'
        self.key.write_text(SYNTHETIC_KEY + '\n')
        os.chmod(self.key, 0o600)
        password = secret_dir / 'password'
        password.write_text('synthetic-qa-password\n')
        os.chmod(password, 0o600)
        ledger, digest = rights_ledger(self, RESTRICTED_SAMPLE)
        where = {'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261001': f'root: {self.live_root}',
                 'credential_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key':
                     f'credential_file: {self.key}',
                 'qa_database_password_file: /opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password':
                     f'qa_database_password_file: {password}',
                 'restricted_inputs_ledger: /opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/metadata/'
                 '053-original-dev40-exact-rights-ledger.json': f'restricted_inputs_ledger: {ledger}',
                 'restricted_inputs_ledger_sha256: 5abaabb031c6e1552944dab1bc3e7fbd3ae5876436c840ffe1ee6312281851d7':
                     f'restricted_inputs_ledger_sha256: {digest}'}
        git(self.repo, 'init', '-q')
        (self.repo / 'docs' / 'foundation' / 'mutations').mkdir(parents=True)
        (self.repo / st.AUTHORITY_RECORD).parent.mkdir(parents=True)
        (self.repo / st.AUTHORITY_RECORD).write_bytes(RECORD.read_bytes())
        self.declaration_path = self.repo / 'docs' / 'foundation' / 'mutations' / DECLARATION_NAME
        self.declaration_path.write_text(fill_template(FIXTURE_VALUES, 'live', where), encoding='utf-8')
        (self.repo / 'rebuild').mkdir()
        (self.repo / 'rebuild' / 'README').write_text('scratch checkout\n')
        (self.repo / '.gitignore').write_text('runtime/\nsecrets/\n')
        git(self.repo, 'add', '-A')
        git(self.repo, 'commit', '-q', '-m', 'Scratch live declaration')
        self.commit = git(self.repo, 'log', '-1', '--format=%H').stdout.decode().strip()
        for name, value in (('DECLARATION', self.declaration_path), ('REBUILD', self.repo / 'rebuild'),
                            ('LIVE_ROOT', self.live_root)):
            patcher = patch.object(st, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.door = {'RULED_MUTATION_DECLARATION': f'docs/foundation/mutations/{DECLARATION_NAME}',
                     'RULED_MUTATION_DECL_COMMIT': self.commit}

    def outer(self, environ):
        captured = {}

        def execve(path, argv, env):
            captured.update(path=path, argv=argv, env=env)
            raise SystemExit('execve captured')
        with patch.dict(os.environ, environ), patch.object(os, 'execve', execve), patch.object(os, 'chdir'), \
                redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                st.outer('preflight')
        return captured

    def inner(self, env, **patches):
        """st.inner() under `env` (nothing else in the environment), with the process-wide umask and signal handlers
        patched (this is the test process) and the ledger lock it takes released afterwards (a real request process
        holds it for life; a second inner() here would otherwise meet it)."""
        held, real = [], pc.hold_lock

        def hold(path):
            fd = real(path)
            held.append(fd)
            return fd
        try:
            with patch.dict(os.environ, env, clear=True), patch.object(os, 'umask'), patch.object(st.signal, 'signal'), \
                    patch.object(pc, 'hold_lock', hold), redirect_stderr(io.StringIO()):
                return st.inner()
        finally:
            for fd in held:
                os.close(fd)

    def test_outside_the_door_nothing_is_read(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('the credential was read outside the door')
        with patch.object(pc, 'load_credential', forbidden), patch.dict(os.environ, {}, clear=False), \
                redirect_stderr(io.StringIO()):
            os.environ.pop('RULED_MUTATION_DECLARATION', None)
            os.environ.pop('RULED_MUTATION_DECL_COMMIT', None)
            with self.assertRaisesRegex(pc.Refused, 'ruled-mutation door'):
                st.outer('preflight')
            with patch.dict(os.environ, {**self.door, 'RULED_MUTATION_DECL_COMMIT': '0' * 40}):
                with self.assertRaisesRegex(pc.Refused, 'another commit'):
                    st.outer('preflight')
        self.assertFalse(self.live_root.exists())

    def test_the_stop_file_refuses_before_the_credential_is_read(self):
        self.live_root.mkdir(parents=True, mode=0o700)
        (self.live_root / st.STOP_NAME).write_text('')

        def forbidden(*args, **kwargs):
            raise AssertionError('the credential was read under the Stop file')
        with patch.object(pc, 'load_credential', forbidden), patch.dict(os.environ, self.door), \
                redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(pc.Refused, 'Stop file'):
                st.outer('preflight')

    def test_outer_hands_the_request_process_a_scrubbed_environment_and_inner_makes_one_models_request(self):
        import httpx
        captured = self.outer({**self.door, 'ANTHROPIC_BASE_URL': 'https://example.invalid', 'HTTPS_PROXY': 'x',
                               'ANTHROPIC_AUTH_TOKEN': 'synthetic-token'})
        env = captured['env']
        self.assertEqual(captured['argv'][-1], '_inner')
        self.assertEqual(env['ANTHROPIC_API_KEY'], SYNTHETIC_KEY)
        self.assertFalse([name for name in env if pc.forbidden_name(name)])
        self.assertNotIn('ANTHROPIC_BASE_URL', env)
        self.assertNotIn('ANTHROPIC_AUTH_TOKEN', env)
        self.assertEqual((env['RULED_MUTATION_DECLARATION'], env['RULED_MUTATION_DECL_COMMIT']),
                         (self.door['RULED_MUTATION_DECLARATION'], self.commit))
        self.assertEqual((env['QUILLMD_AI_MODEL'], env['QUILLMD_ENV_MANAGED'], env['QUILLMD_DB_NAME']),
                         ('claude-sonnet-5-5', '1', st.DATABASE_NAME))
        context = json.loads(env[st.CONTEXT_VARIABLE])
        self.assertEqual((context['command'], context['root']), ('preflight', str(self.live_root)))
        self.assertEqual(sorted(os.listdir(self.live_root)), sorted(['ledger', 'runs', 'evidence', 'preflight',
                                                                     'qa-state', 'access', 'home', 'tmp', 'forms']))
        calls = []

        def models(request):
            calls.append((request.method, str(request.url)))
            return httpx.Response(200, json={'id': 'claude-sonnet-5-5', 'type': 'model',
                                             'display_name': 'Claude Sonnet 5.5'})
        out = io.StringIO()
        with patch.object(httpx, 'HTTPTransport', lambda: httpx.MockTransport(models)), redirect_stdout(out):
            code = self.inner(env)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [('GET', 'https://api.anthropic.com/v1/models/claude-sonnet-5-5')])
        result = json.loads(out.getvalue())
        self.assertEqual((result['matches_declared'], result['model_returned']), (True, 'claude-sonnet-5-5'))
        self.assertNotIn(SYNTHETIC_KEY, out.getvalue())
        self.assertEqual(pc.leaked(self.live_root, SYNTHETIC_KEY), [])
        # (the request process re-checks the door itself: the same environment without it is refused)
        # (and the credential it was handed must be the declared file's, byte for byte)
        with self.assertRaisesRegex(pc.Refused, 'does not carry the declared credential'):
            self.inner({**env, 'ANTHROPIC_API_KEY': SYNTHETIC_KEY.replace('2222', '9999')})
        with self.assertRaisesRegex(pc.Refused, 'ruled-mutation door'):
            self.inner({k: v for k, v in env.items() if not k.startswith('RULED_MUTATION_')})
        (self.live_root / st.STOP_NAME).write_text('')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            self.inner(env)
        self.assertEqual(len(calls), 1)


# ── the preflight ────────────────────────────────────────────────────────────────────────────────────────────────

class PreflightTests(Base):
    def setUp(self):
        self.campaign_ = self.campaign()
        self.calls = []
        self.answer = (200, {'id': 'claude-sonnet-5-5', 'type': 'model', 'display_name': 'Claude Sonnet 5.5',
                             'created_at': '2026-09-30T00:00:00Z', 'max_input_tokens': 1000000, 'max_tokens': 128000})

    def transport(self):
        import httpx

        def handler(request):
            self.calls.append((request.method, str(request.url), dict(request.headers)))
            status, body = self.answer
            return httpx.Response(status, headers={'request-id': 'req_synthetic_models'}, json=body)
        return httpx.MockTransport(handler)

    def test_the_guard_is_on(self):
        network_guard.positive_control(self)

    def test_one_get_to_the_declared_models_url_is_recorded_and_compared(self):
        result = st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
        self.assertEqual(len(self.calls), 1)
        method, url, headers = self.calls[0]
        self.assertEqual((method, url), ('GET', 'https://api.anthropic.com/v1/models/claude-sonnet-5-5'))
        self.assertEqual(headers['x-api-key'], SYNTHETIC_KEY)                    # (the real request carried it)
        self.assertTrue(result['matches_declared'])
        self.assertEqual((result['model_returned'], result['display_name'], result['max_tokens']),
                         ('claude-sonnet-5-5', 'Claude Sonnet 5.5', 128000))
        self.assertIs(result['generation_proof'], False)
        self.assertIn('not', result['statement'])
        evidence = self.campaign_.root / 'preflight' / '001'
        request = json.loads((evidence / 'request.json').read_text())
        self.assertEqual((request['method'], request['url']), ('GET', 'https://api.anthropic.com/v1/models/claude-sonnet-5-5'))
        self.assertNotIn('x-api-key', request['headers'])
        self.assertEqual(json.loads((evidence / 'result.json').read_text())['model_returned'], 'claude-sonnet-5-5')
        self.assertEqual(pc.leaked(self.campaign_.root, SYNTHETIC_KEY), [])
        self.assertEqual(st.require_preflight(self.campaign_)['preflight'], 1)
        self.assertEqual(self.campaign_.ledger.rows(), [])                      # (not a paid attempt)

    def test_another_id_or_an_error_never_matches_and_run_stays_refused(self):
        self.answer = (200, {'id': 'claude-sonnet-5', 'type': 'model', 'display_name': 'Claude Sonnet 5'})
        self.assertFalse(st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
                         ['matches_declared'])
        self.answer = (404, {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model not found'}})
        result = st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
        self.assertFalse(result['matches_declared'])
        self.assertEqual(result['error'], {'class': 'NotFoundError', 'status_code': 404})
        self.assertEqual(len(self.calls), 2)                                     # (one request each, no retry)
        with self.assertRaisesRegex(pc.Refused, 'No preflight has shown'):
            st.require_preflight(self.campaign_)

    def test_another_url_method_or_a_second_request_is_refused_before_it_leaves(self):
        import httpx
        evidence = scratch(self)
        guard = st._preflight_transport_class()(self.transport(), st.MODELS_URL + 'claude-sonnet-5-5', evidence,
                                                SYNTHETIC_KEY)
        with self.assertRaisesRegex(pc.Refused, 'only GET'):
            guard.handle_request(httpx.Request('POST', st.MODELS_URL + 'claude-sonnet-5-5'))
        with self.assertRaisesRegex(pc.Refused, 'only GET'):
            guard.handle_request(httpx.Request('GET', 'https://api.anthropic.com/v1/messages'))
        with self.assertRaisesRegex(pc.Refused, 'only GET'):
            guard.handle_request(httpx.Request('GET', 'https://api.deepgram.com/v1/listen'))
        self.assertEqual(self.calls, [])
        guard.handle_request(httpx.Request('GET', st.MODELS_URL + 'claude-sonnet-5-5'))
        with self.assertRaisesRegex(pc.Refused, 'second preflight request'):
            guard.handle_request(httpx.Request('GET', st.MODELS_URL + 'claude-sonnet-5-5'))
        self.assertEqual(len(self.calls), 1)

    def test_the_stop_file_refuses_the_preflight(self):
        self.campaign_.stop_file().write_text('')
        with self.assertRaisesRegex(pc.Refused, 'Stop file'):
            st.run_preflight(self.campaign_, secret=SYNTHETIC_KEY, transport=self.transport())
        self.assertEqual(self.calls, [])


# ── the request bounds at the capture ────────────────────────────────────────────────────────────────────────────

class RequestBoundsTests(unittest.TestCase):
    def setUp(self):
        import anthropic
        import httpx
        self.root = scratch(self)
        self.evidence = self.root / 'evidence' / '001'
        self.evidence.mkdir(parents=True, mode=0o700)
        self.seen = []

        def handler(request):
            self.seen.append(request)
            return httpx.Response(200, json={'id': 'msg_synthetic', 'type': 'message', 'role': 'assistant',
                                             'model': 'claude-sonnet-5-5', 'content': [{'type': 'text', 'text': '{}'}],
                                             'stop_reason': 'end_turn', 'stop_sequence': None,
                                             'usage': {'input_tokens': 10, 'output_tokens': 2}})
        self.client = anthropic.Anthropic(api_key=SYNTHETIC_KEY, max_retries=0,
                                          http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        pc.install_request_capture()
        self.addCleanup(pc.uninstall_request_capture)
        self.addCleanup(pc.CURRENT_ATTEMPT.clear)
        self.addCleanup(pc.REQUEST_BOUNDS.clear)
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        pc.REQUEST_BOUNDS.update(model='claude-sonnet-5-5', max_tokens=20000)

    def send(self, model='claude-sonnet-5-5', max_tokens=8000):
        return self.client.messages.create(model=model, max_tokens=max_tokens,
                                           messages=[{'role': 'user', 'content': 'synthetic'}])

    def test_another_model_or_more_output_is_refused_before_it_is_recorded_or_sent(self):
        for model, tokens in (('claude-sonnet-5', 8000), ('claude-sonnet-5-5', 20001), ('claude-opus-5', 8000)):
            with self.subTest(model=model, tokens=tokens), self.assertRaisesRegex(pc.Refused, 'per-request bounds'):
                self.send(model, tokens)
        self.assertEqual(self.seen, [])
        self.assertFalse((self.evidence / 'request.json').exists())

    def test_a_request_inside_the_bounds_is_captured_and_sent(self):
        self.send()
        self.assertEqual(len(self.seen), 1)
        self.assertEqual(json.loads((self.evidence / 'request.json').read_text())['body_json']['max_tokens'], 8000)


# ── the historical campaign ──────────────────────────────────────────────────────────────────────────────────────

class HistoricalTests(Base):
    def test_its_declaration_is_byte_identical(self):
        self.assertEqual(hashlib.sha256(HISTORICAL_DECLARATION.read_bytes()).hexdigest(), HISTORICAL_DECLARATION_SHA256)

    def test_its_runner_refuses_every_write_before_reading_anything(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('the historical runner read something before refusing')
        with patch.object(pc, 'declared', forbidden), patch.object(pc, 'load_credential', forbidden), \
                patch.object(pc, 'read_private', forbidden), patch.object(os, 'execve', forbidden):
            for argv in (['run', '--stage', 'model_check'], ['run', '--stage', 'mapping'],
                         ['run', '--stage', 'ordinary_notes'], ['reopen', '--stage', 'mapping', '--diagnosis', 'x'],
                         ['recover']):
                err = io.StringIO()
                with redirect_stderr(err):
                    self.assertEqual(sq.main(argv), 2, argv)
                self.assertIn('closed for new sends', err.getvalue())

    def test_its_closure_covers_the_root_and_everything_under_it_and_nothing_else(self):
        for root in (sq.HISTORICAL_ROOT, sq.HISTORICAL_ROOT / 'ledger', sq.HISTORICAL_ROOT.parent):
            with self.subTest(root=root), self.assertRaisesRegex(pc.Refused, 'closed for new sends'):
                sq.require_not_historical(root)
        sq.require_not_historical(scratch(self))
        sq.require_not_historical(st.LIVE_ROOT)

    def test_its_status_stays_readable(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(sq.status(root=scratch(self) / 'empty'), 0)
        report = json.loads(out.getvalue())
        self.assertEqual((report['campaign'], report['total']['limit']), (st.HISTORICAL['campaign'], '40.00'))

    @unittest.skipUnless(os.access(sq.HISTORICAL_ROOT / 'ledger', os.R_OK), 'the historical ledger is on the VPS only')
    def test_the_live_historical_ledger_reads_as_recorded(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(sq.status(), 0)
        report = json.loads(out.getvalue())
        self.assertEqual((len(report['outcomes']), report['total']['exposure'], report['open_attempts']),
                         (24, '0.130880', []))
        self.assertEqual({k: v['state'] for k, v in report['stages'].items()},
                         {'model_check': 'passed', 'mapping': 'failed', 'ordinary_notes': 'failed'})

    def test_its_declaration_and_ledger_are_never_a_standing_campaigns(self):
        with self.assertRaises(pc.Refused):
            parse(self, HISTORICAL_DECLARATION.read_text(encoding='utf-8'))
        d = parse(self)
        with self.assertRaisesRegex(pc.Refused, 'historical campaign\'s root'):
            st.StandingCampaign(d, sq.HISTORICAL_ROOT)
        root = scratch(self) / 'old'
        ledger = pc.Ledger(root / 'ledger')
        ledger.acquire()
        self.addCleanup(ledger.release)
        ledger.write_attempt({'number': 1, 'campaign': st.HISTORICAL['campaign'], 'authority_id':
                              st.HISTORICAL['authority_id'], 'stage': 'model_check', 'maximum_cost': '0.01'})
        with self.assertRaisesRegex(pc.Refused, 'another campaign or authority'):
            st.StandingCampaign(d, root).rows()
        ledger.release()
        root2 = scratch(self) / 'forged'
        forged = pc.Ledger(root2 / 'ledger')
        forged.acquire()
        self.addCleanup(forged.release)
        forged.write_attempt({'number': 1, 'campaign': d.campaign, 'authority_id': d.authority_id,
                              'stage': 'model_check', 'maximum_cost': '0.01'})
        with self.assertRaisesRegex(pc.Refused, 'not a standing campaign attempt'):
            st.StandingCampaign(d, root2).rows()


# ── plans ────────────────────────────────────────────────────────────────────────────────────────────────────────

class PlanTests(Base):
    @classmethod
    def setUpClass(cls):
        cls.inputs = sq.stages_module().frozen_inputs()
        cls.definitions = st.plan_definitions(cls.inputs)

    def test_the_model_check_and_mapping_plans(self):
        self.assertEqual([s['id'] for s in self.definitions['model_check']['sends']], [st.MODEL_CHECK_SEND])
        self.assertEqual(self.definitions['model_check']['sends'][0]['inputs'],
                         {'form_sha256': sq.FORM_SHA256, 'notes_sha256': sq.NOTES_SHA256})
        mapping = [s['id'] for s in self.definitions['mapping']['sends']]
        self.assertEqual(mapping, [f'mapping:{name}' for name in sq.stages_module().MAPPING_ORDER]
                         + ['generation:f6a-long-answer', 'generation:f6b-admin-missing'])
        self.assertTrue(all(s['pricing_key'] == 'mapping' for s in self.definitions['mapping']['sends']))

    def test_the_notes_comparison_sends_14_cases_on_both_requests(self):
        sends = self.definitions['notes_comparison']['sends']
        self.assertEqual(len(sends), 28)
        default = [s for s in sends if s['path'] == 'default']
        relations = [s for s in sends if s['path'] == 'field_relations']
        cases = ['N01', 'N02', 'N03', 'N04', 'N05', 'N06', 'N07', 'N08', 'N09', 'N10', 'N11', 'N12', 'N13', 'N16']
        self.assertEqual(sorted(s['case'] for s in default), cases)
        self.assertEqual([s['case'] for s in relations], cases)
        self.assertEqual(sends[-14:], relations)                      # (the relations path runs last)
        self.assertEqual({s['pricing_key'] for s in default}, {'ordinary_notes'})
        self.assertEqual({s['pricing_key'] for s in relations}, {'ordinary_notes_field_relations'})
        for send in sends:
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == send['case'])
            self.assertEqual(send['inputs']['notes_sha256'], hashlib.sha256(case['notes'].encode()).hexdigest())

    def test_d30_d31_structure_and_transcription_are_not_established(self):
        self.assertFalse(self.definitions['d30_d31_structure']['established'])
        self.assertIn('no provider upload', self.definitions['d30_d31_structure']['statement'])
        self.assertFalse(self.definitions['transcription']['established'])
        self.assertIn('neither this runner nor the historical one has a transcription stage',
                      self.definitions['transcription']['statement'])
        with self.assertRaisesRegex(pc.Refused, 'not established'):
            st.standing_plan('d30_d31_structure', self.inputs)

    def test_the_declared_send_counts_and_pricing_keys_are_the_plans(self):
        d = parse(self)
        for stage in d.stages:
            self.assertEqual(stage.sends, self.definitions[stage.id]['count'], stage.id)
            for send in self.definitions[stage.id]['sends']:
                self.assertIn(send['pricing_key'], dict(d.pricing_versions))

    def test_the_stage_flags_are_the_historical_runners(self):
        stages = sq.stages_module()
        self.assertEqual({k: v for k, v in st.STAGE_FLAGS['model_check'].items() if k in sq.PLAIN_PROFILE_FLAGS},
                         sq.PLAIN_PROFILE_FLAGS)
        self.assertTrue(set(sq.PLAIN_PROFILE_FLAGS) <= set(st.STAGE_FLAGS['model_check']))
        for stage, theirs in (('mapping', 'mapping'), ('notes_comparison', 'ordinary_notes')):
            self.assertEqual({k: v for k, v in st.STAGE_FLAGS[stage].items() if k in stages.STAGE_FLAGS[theirs]},
                             stages.STAGE_FLAGS[theirs])
        self.assertEqual(st.expected_settings('notes_comparison')['V3_FIELD_RELATIONS'], False)
        self.assertEqual(stages.steps.PATH_FLAGS['field_relations']['V3_FIELD_RELATIONS'], True)


# ── the pricing command ──────────────────────────────────────────────────────────────────────────────────────────

class PricingCommandTests(unittest.TestCase):
    def pricing(self, model, rates):
        return subprocess.run([sys.executable, '-B', str(REBUILD / 'ops' / 'standing_qa.py'), 'pricing', '--model', model,
                               '--input', rates[0], '--output', rates[1], '--cached', rates[2], '--thinking', 'disabled',
                               '--effort', 'medium'], capture_output=True, text=True, timeout=300, cwd=str(REBUILD),
                              env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'HOME': str(scratch(self)),
                                   'PYTHONDONTWRITEBYTECODE': '1'})

    def test_it_reproduces_the_historical_declarations_versions_for_sonnet_5(self):
        done = self.pricing('claude-sonnet-5', ('2', '10', '0.20'))
        self.assertEqual(done.returncode, 0, done.stderr)
        report = json.loads(done.stdout)
        historical = HISTORICAL_DECLARATION.read_text()
        version = re.search(r'^pricing_version model_check: (\S+)$', historical, re.M).group(1)
        self.assertEqual(report['pricing_versions']['model_check'], version)
        self.assertEqual(report['pricing_versions']['mapping'], version)
        self.assertEqual(report['pricing_versions']['ordinary_notes'], version)
        amendment = (REPOSITORY / 'docs' / 'foundation' / 'mutations' /
                     '20260929-quillmd-v1-sonnet5-relations-contract-amendment.md').read_text()
        amended = re.search(r'^amended_pricing_version: (\S+)$', amendment, re.M).group(1)
        self.assertEqual(report['pricing_versions']['ordinary_notes_field_relations'], amended)
        self.assertEqual(report['request_profiles']['mapping_request']['max_output_tokens'], 20000)

    def test_it_refuses_a_model_the_application_has_no_profile_for(self):
        done = self.pricing('claude-sonnet-5-5', ('3', '15', '0.30'))
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn('no valid request profile for claude-sonnet-5-5', done.stderr)
        self.assertEqual(done.stdout, '')


if __name__ == '__main__':
    unittest.main()
