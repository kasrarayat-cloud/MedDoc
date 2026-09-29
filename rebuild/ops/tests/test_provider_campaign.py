"""The generic campaign machinery (ops/provider_campaign.py), offline and without Django.

What each group proves, stated so a reader can see how it would fail:
  · DECLARATION — the committed declaration parses to exactly the numbers it states; an untracked, uncommitted, staged,
    assume-unchanged-hidden, revoked, doubly-authorized or unauthorized declaration is refused.
  · LEDGER — records are write-once and gapless, only the lock holder writes, and an attempt left without an outcome is
    recovered as `interrupted_unknown` in a NEW record, the attempt untouched.
  · EXPOSURE — provider-reported usage is priced at the declared rates (cache writes 1.25x / 2x, reads at the cached
    rate, US geography 1.1x); anything unknown counts at the maximum x 1.1.
  · ADMISSION — over the stage cap, over the total cap, over the request count, with an open attempt, before the
    prerequisite passed, after a stage decision: refused.
  · CREDENTIAL — only the declared file; a `.env` path (written or resolved) is refused BEFORE anything is opened; the
    wrong mode, owner or shape is refused.
  · ENVIRONMENT, CAPTURE, LEAKS — the request process inherits nothing; the captured request never carries the key; a
    planted key is found wherever it hides.
No socket is opened except to the QA database address (network_guard); the provider is an in-process MockTransport.
"""
import builtins
import dataclasses
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc
from . import network_guard

REPOSITORY = Path(__file__).resolve().parents[3]
REAL_DECLARATION = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
REAL_TEXT = REAL_DECLARATION.read_text(encoding='utf-8')
SYNTHETIC_KEY = 'sk-ant-api03-SYNTHETIC-OFFLINE-TEST-KEY-000000000000000000000000000000000000-AAAAAAAA'
MAXIMUM = '0.104896'
GIT = ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', '-c', 'user.name=Synthetic Test',
       '-c', 'user.email=synthetic@test.invalid']


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


def scratch(test):
    directory = Path(tempfile.mkdtemp(prefix='campaign-test-'))
    test.addCleanup(shutil.rmtree, directory, True)
    return directory


def git(root, *args, check=True):
    return subprocess.run([*GIT, '-C', str(root), *args], capture_output=True, check=check)


def repository_with(test, text, name='20260928-test-declaration.md', commit=True):
    root = scratch(test)
    git(root, 'init', '-q')
    folder = root / 'docs' / 'foundation' / 'mutations'
    folder.mkdir(parents=True)
    path = folder / name
    path.write_text(text, encoding='utf-8')
    if commit:
        git(root, 'add', '--', str(path.relative_to(root)))
        git(root, 'commit', '-q', '-m', 'Synthetic declaration')
    return root, path


def declaration(**changes):
    base = pc.Declaration(
        path='/synthetic/decl.md', sha256='0' * 64, commit='0' * 40, commit_time='2026-09-28T23:29:58+00:00',
        campaign='quillmd-v1-sonnet5-staged-40', authority_id='synthetic-authority', authorization='owner approved',
        owner_words='Approve', total_limit=Decimal('40.00'),
        stages=(pc.Stage('model_check', Decimal('5.00'), 10, None), pc.Stage('mapping', Decimal('25.00'), None, 'model_check'),
                pc.Stage('ordinary_notes', Decimal('10.00'), None, 'model_check')),
        transfers=False, provider='anthropic', model='claude-sonnet-5', rates=pc.Rates('2', '10', '0.20'),
        thinking='disabled', effort='medium', inference_geo='',
        pricing_versions=(('model_check', 'configured-v1:' + 'a' * 64),), credential_file='/synthetic/credential/key')
    return dataclasses.replace(base, **changes)


def attempt(number, stage='model_check', maximum=MAXIMUM, campaign='quillmd-v1-sonnet5-staged-40',
            authority='synthetic-authority'):
    return {'number': number, 'campaign': campaign, 'authority_id': authority, 'stage': stage, 'maximum_cost': maximum,
            'rates': {'input': '2', 'output': '10', 'cached': '0.20'}, 'started_at': pc.now()}


def usage(**changes):
    return {'input_tokens': 1000, 'output_tokens': 200, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0,
            'cache_creation': None, 'inference_geo': 'global', **changes}


class DeclarationTests(unittest.TestCase):
    def test_the_committed_declaration_parses_to_exactly_what_it_states(self):
        out = io.StringIO()
        d = pc.declared(REAL_DECLARATION, repository=REPOSITORY, out=out)
        self.assertEqual((d.campaign, d.authority_id), ('quillmd-v1-sonnet5-staged-40',
                                                        'quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk'))
        self.assertEqual(d.total_limit, Decimal('40.00'))
        self.assertEqual(d.stages, (pc.Stage('model_check', Decimal('5.00'), 10, None),
                                    pc.Stage('mapping', Decimal('25.00'), None, 'model_check'),
                                    pc.Stage('ordinary_notes', Decimal('10.00'), None, 'model_check')))
        self.assertEqual((d.provider, d.model, d.thinking, d.effort, d.inference_geo),
                         ('anthropic', 'claude-sonnet-5', 'disabled', 'medium', ''))
        self.assertEqual(d.rates, pc.Rates('2', '10', '0.20'))
        self.assertEqual(d.pricing_version('model_check'),
                         'configured-v1:8975b1585770620ede7d015cb4945abebf872845c4a6648f0d74f4de9d1be77d')
        self.assertEqual(d.pricing_version('ordinary_notes_field_relations'),
                         'configured-v1:eb280d15cbfc2cf52477c57040c3ff11d60352aac5d9a9894bdae4e6a0594180')
        self.assertEqual(d.credential_file, '/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/credential/anthropic-api-key')
        self.assertEqual(d.authorization, 'owner 2026-09-28 approved the staged $40 maximum at the stated limits')
        self.assertEqual(d.owner_words, 'Approve the staged $40 maximum')
        committed = git(REPOSITORY, 'log', '-1', '--format=%cI', '--', str(REAL_DECLARATION.relative_to(REPOSITORY)))
        self.assertIn(committed.stdout.decode().strip(), out.getvalue())
        self.assertEqual(d.commit_time, committed.stdout.decode().strip())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            d.total_limit = Decimal('400')

    def test_a_committed_copy_parses_and_its_commit_time_is_printed(self):
        root, path = repository_with(self, REAL_TEXT)
        out = io.StringIO()
        d = pc.declared(path, repository=root, out=out)
        stamp = git(root, 'log', '-1', '--format=%cI').stdout.decode().strip()
        self.assertEqual(d.commit_time, stamp)
        self.assertIn(stamp, out.getvalue())
        self.assertEqual(d.sha256, hashlib.sha256(REAL_TEXT.encode()).hexdigest())

    def refused(self, root, path, fragment=''):
        with self.assertRaises(pc.Refused) as caught:
            pc.declared(path, repository=root, out=io.StringIO())
        self.assertIn(fragment, str(caught.exception))

    def test_an_untracked_declaration_is_refused(self):
        root, path = repository_with(self, REAL_TEXT, commit=False)
        self.refused(root, path, 'tracked, committed and unmodified')

    def test_an_uncommitted_edit_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        path.write_text(REAL_TEXT.replace('total_limit_provider_usd: 40.00', 'total_limit_provider_usd: 400.00'))
        self.refused(root, path, 'tracked, committed and unmodified')

    def test_a_staged_edit_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        path.write_text(REAL_TEXT.replace('max_requests 10', 'max_requests 99'))
        git(root, 'add', '--', str(path.relative_to(root)))
        self.refused(root, path, 'tracked, committed and unmodified')

    def test_an_edit_hidden_by_assume_unchanged_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        git(root, 'update-index', '--assume-unchanged', '--', str(path.relative_to(root)))
        path.write_text(REAL_TEXT.replace('max_requests 10', 'max_requests 99'))
        self.assertEqual(git(root, 'diff', '--quiet', 'HEAD', '--', str(path.relative_to(root)), check=False).returncode, 0)
        self.refused(root, path, 'committed blob')

    def test_a_committed_revocation_is_refused_wherever_it_is_written(self):
        sentence = pc.KNOWN_NON_REVOCATIONS[0]
        for text in (REAL_TEXT + '\nrevoked: owner 2026-09-29\n',
                     REAL_TEXT + '\n## Approval rescinded\n',
                     REAL_TEXT + '\nThe owner has withdrawn this approval.\n',
                     REAL_TEXT + '\n| status | Cancelled |\n',
                     REAL_TEXT.replace('## Authority', '## Authority — SUSPENDED'),
                     REAL_TEXT + '\n' + sentence + '\n'):
            with self.subTest(tail=text[-40:]):
                root, path = repository_with(self, text)
                self.refused(root, path, 'revocation')

    def test_the_benign_key_sentence_is_the_only_exception(self):
        self.assertEqual(len(pc.KNOWN_NON_REVOCATIONS), 1)
        self.assertIn(pc.KNOWN_NON_REVOCATIONS[0], ' '.join(REAL_TEXT.split()))
        edited = REAL_TEXT.replace('revoked when the campaign ends', 'revoked now')
        root, path = repository_with(self, edited)
        self.refused(root, path, 'revocation')

    def test_two_authorization_lines_are_refused(self):
        line = 'authorization: owner 2026-09-28 approved the staged $40 maximum at the stated limits'
        for text in (REAL_TEXT.replace(line, line + '\nauthorization: owner 2026-09-29 approved $400 at the stated limits'),
                     REAL_TEXT + '\n**Authorization**: pending\n',
                     REAL_TEXT + '\n- Authorised by the owner for $400 as well\n',
                     REAL_TEXT + '\nAuthorizations: a second grant\n'):
            with self.subTest(text=text[-60:]):
                root, path = repository_with(self, text)
                self.refused(root, path, 'no owner authorization')

    def test_an_authorization_with_anything_after_it_or_missing_is_refused(self):
        line = 'authorization: owner 2026-09-28 approved the staged $40 maximum at the stated limits'
        for text in (REAL_TEXT.replace(line, line + ' once the quote is checked'), REAL_TEXT.replace(line, '')):
            with self.subTest(text=len(text)):
                root, path = repository_with(self, text)
                self.refused(root, path, 'no owner authorization')

    def test_missing_owner_words_are_refused(self):
        root, path = repository_with(self, REAL_TEXT.replace('owner_words: Approve the staged $40 maximum\n', ''))
        self.refused(root, path, 'owner_words')

    def test_a_declaration_outside_the_mutations_folder_is_refused(self):
        root, path = repository_with(self, REAL_TEXT)
        elsewhere = root / 'docs' / 'decl.md'
        shutil.copy(path, elsewhere)
        git(root, 'add', '--', 'docs/decl.md')
        git(root, 'commit', '-q', '-m', 'elsewhere')
        self.refused(root, elsewhere, 'docs/foundation/mutations')

    def test_a_credential_file_under_an_env_name_is_refused_in_the_declaration(self):
        text = REAL_TEXT.replace('credential/anthropic-api-key', 'credential/.env')
        root, path = repository_with(self, text)
        self.refused(root, path, 'environment file')


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch(self)
        self.ledger = pc.Ledger(self.root / 'ledger').acquire()
        self.addCleanup(self.ledger.release)

    def test_records_are_write_once_and_gapless(self):
        self.ledger.write_attempt(attempt(1))
        with self.assertRaises(FileExistsError):
            pc.write_new(self.ledger.dir / '001-attempt.json', attempt(1))
        with self.assertRaises(pc.Refused):
            self.ledger.write_attempt(attempt(2))           # (attempt 1 has no outcome)
        self.ledger.write_outcome(1, {'class': 'completed'})
        with self.assertRaises(pc.Refused):
            self.ledger.write_outcome(1, {'class': 'completed'})
        with self.assertRaises(pc.Refused):
            self.ledger.write_attempt(attempt(3))           # (a gap)
        pc.write_new(self.ledger.dir / '003-attempt.json', attempt(3))
        with self.assertRaises(pc.Refused) as caught:
            self.ledger.rows()
        self.assertIn('gapless', str(caught.exception))

    def test_only_the_lock_holder_writes_and_one_runner_holds_it(self):
        other = pc.Ledger(self.root / 'ledger')
        with self.assertRaises(pc.Refused):
            other.write_attempt(attempt(1))
        with self.assertRaises(pc.Refused) as caught:
            other.acquire()
        self.assertIn('Another runner', str(caught.exception))

    def test_an_outcome_needs_its_attempt_and_strays_are_refused(self):
        with self.assertRaises(pc.Refused):
            self.ledger.write_outcome(1, {'class': 'completed'})
        (self.ledger.dir / '.partial-1-001-attempt.json').write_text('{}')     # (a kill's leftover temporary: ignored)
        self.assertEqual(self.ledger.rows(), [])
        (self.ledger.dir / 'notes.txt').write_text('stray')
        with self.assertRaises(pc.Refused):
            self.ledger.rows()

    def test_an_interrupted_attempt_is_recovered_in_a_new_record_and_never_edited(self):
        self.ledger.write_attempt(attempt(1))
        path = self.ledger.dir / '001-attempt.json'
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(pc.recover_interrupted(self.ledger), [1])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        (row,) = self.ledger.rows()
        self.assertEqual(row[1]['class'], 'interrupted_unknown')
        self.assertEqual(pc.exposure(*row), Decimal(MAXIMUM) * Decimal('1.1'))
        self.assertEqual(pc.recover_interrupted(self.ledger), [])

    def test_a_stage_is_decided_once(self):
        self.ledger.write_stage('model_check', 'failed', {'reasons': ['synthetic']})
        with self.assertRaises(pc.Refused):
            self.ledger.write_stage('model_check', 'passed', {})
        self.assertEqual(self.ledger.stage_record('model_check', 'failed')['reasons'], ['synthetic'])


class ExposureTests(unittest.TestCase):
    RATES = pc.Rates('2', '10', '0.20')

    def test_known_usage_is_priced_at_the_declared_rates(self):
        split = usage(cache_read_input_tokens=300, cache_creation_input_tokens=400,
                      cache_creation={'ephemeral_5m_input_tokens': 100, 'ephemeral_1h_input_tokens': 300})
        standard = (Decimal(1000) * 2 + Decimal(300) * Decimal('0.20') + Decimal(100) * 2 * Decimal('1.25')
                    + Decimal(300) * 2 * 2 + Decimal(200) * 10) / 1000000
        self.assertEqual(standard, Decimal('0.00551'))
        self.assertEqual(pc.usage_cost(split, self.RATES), standard)
        self.assertEqual(pc.usage_cost({**split, 'inference_geo': 'us'}, self.RATES), standard * Decimal('1.1'))
        self.assertEqual(pc.usage_cost({**split, 'inference_geo': None}, self.RATES), standard * Decimal('1.1'))
        self.assertEqual(pc.usage_cost({**split, 'inference_geo': None}, self.RATES, unknown_geography_margin=False), standard)
        unsplit = usage(cache_creation_input_tokens=400)
        self.assertEqual(pc.usage_cost(unsplit, self.RATES), (Decimal(2000) + 400 * 2 * 2 + 2000) / 1000000)
        with self.assertRaises(ValueError):
            pc.usage_cost(usage(cache_creation_input_tokens=5, cache_creation={'ephemeral_5m_input_tokens': 1,
                                                                             'ephemeral_1h_input_tokens': 1}), self.RATES)

    def test_a_completed_outcome_counts_its_usage_and_every_unknown_counts_the_maximum(self):
        bound = Decimal(MAXIMUM) * Decimal('1.1')
        self.assertEqual(pc.exposure(attempt(1), {'class': 'completed', 'usage': usage()}), Decimal('0.004'))
        self.assertEqual(pc.exposure(attempt(1), None), bound)
        for cls in ('unknown', 'uncertain', 'interrupted_unknown', 'reconciliation'):
            with self.subTest(cls=cls):
                self.assertEqual(pc.exposure(attempt(1), {'class': cls}), bound)
                self.assertEqual(pc.exposure(attempt(1), {'class': cls, 'usage': usage()}), bound)
        self.assertEqual(pc.exposure(attempt(1), {'class': 'reconciliation', 'usage': usage(output_tokens=20000)}),
                         Decimal('0.202'))
        self.assertEqual(pc.exposure(attempt(1), {'class': 'completed', 'usage': usage(output_tokens=-1)}), bound)
        self.assertEqual(pc.exposure(attempt(1), {'class': 'not_sent'}), Decimal(0))


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch(self)

    def campaign(self, **changes):
        campaign = pc.Campaign(declaration(**changes), self.root)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        return campaign

    def spend(self, campaign, number, stage='model_check', maximum=MAXIMUM, outcome=None):
        campaign.ledger.write_attempt(attempt(number, stage, maximum))
        if outcome is not False:
            campaign.ledger.write_outcome(number, outcome or {'class': 'uncertain'})

    def test_an_attempt_that_fits_is_admitted_at_its_maximum_times_1_1(self):
        self.assertEqual(self.campaign().admit('model_check', MAXIMUM), Decimal('0.1153856'))

    def test_over_the_stage_cap_is_refused(self):
        campaign = self.campaign()
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', '4.60')           # 5.06 > 5.00
        self.assertIn('Stage model_check limit', str(caught.exception))
        self.spend(campaign, 1, maximum='4.00')             # an unknown outcome counts 4.40
        self.assertEqual(campaign.admit('model_check', '0.50'), Decimal('0.550'))
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', '0.60')           # 4.40 + 0.66 > 5.00

    def test_over_the_total_cap_is_refused_even_when_the_stage_fits(self):
        campaign = self.campaign(total_limit=Decimal('6.00'))
        self.spend(campaign, 1, maximum='4.00')
        campaign.ledger.write_stage('model_check', 'passed', {})
        self.assertEqual(campaign.admit('mapping', '1.40'), Decimal('1.540'))
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('mapping', '1.50')               # 4.40 + 1.65 > 6.00, while mapping's 25.00 fits
        self.assertIn('Campaign limit', str(caught.exception))

    def test_over_the_stage_request_count_is_refused(self):
        stages = (pc.Stage('model_check', Decimal('5.00'), 2, None),)
        campaign = self.campaign(stages=stages)
        self.spend(campaign, 1, outcome={'class': 'completed', 'usage': usage()})
        self.spend(campaign, 2, outcome={'class': 'completed', 'usage': usage()})
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', MAXIMUM)
        self.assertIn('all 2 requests', str(caught.exception))

    def test_an_open_attempt_is_refused(self):
        campaign = self.campaign()
        self.spend(campaign, 1, outcome=False)
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('model_check', MAXIMUM)
        self.assertIn('no outcome', str(caught.exception))

    def test_a_stage_before_its_prerequisite_passed_is_refused(self):
        campaign = self.campaign()
        with self.assertRaises(pc.Refused) as caught:
            campaign.admit('mapping', MAXIMUM)
        self.assertIn('requires model_check', str(caught.exception))
        campaign.ledger.write_stage('model_check', 'passed', {})
        self.assertEqual(campaign.admit('mapping', MAXIMUM), Decimal('0.1153856'))
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', MAXIMUM)          # (a passed stage is never re-run in place)

    def test_a_failed_model_check_stops_every_stage(self):
        campaign = self.campaign()
        campaign.ledger.write_stage('model_check', 'failed', {'reasons': ['synthetic']})
        for stage in ('model_check', 'mapping', 'ordinary_notes'):
            with self.subTest(stage=stage), self.assertRaises(pc.Refused):
                campaign.admit(stage, MAXIMUM)

    def test_an_unknown_outcome_counts_at_its_maximum_times_1_1(self):
        campaign = self.campaign()
        self.spend(campaign, 1, outcome={'class': 'uncertain', 'usage': usage(input_tokens=1, output_tokens=1)})
        self.assertEqual(campaign.totals('model_check')['exposure'], Decimal('0.1153856'))
        self.assertEqual(campaign.totals()['unknown'], 1)

    def test_money_is_decimal_and_a_stopped_or_foreign_campaign_admits_nothing(self):
        campaign = self.campaign()
        for value in (0.1, float('nan'), 'NaN', '0', '-1', True):
            with self.subTest(value=value), self.assertRaises(pc.Refused):
                campaign.admit('model_check', value)
        campaign.ledger.write_attempt(attempt(1, authority='another-authority'))
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', MAXIMUM)

    def test_a_campaign_stop_admits_nothing(self):
        campaign = self.campaign()
        campaign.ledger.write_stop({'reason': 'synthetic'})
        with self.assertRaises(pc.Refused):
            campaign.admit('model_check', MAXIMUM)


class NoEnvOpened:
    """builtins.open, io.open and os.open raise on any path naming a `.env` file or directory, and record the call."""

    def __init__(self):
        self.attempts = []

    def guard(self, original):
        def wrapped(file, *args, **kwargs):
            if isinstance(file, (str, bytes, os.PathLike)):
                text = os.fsdecode(file)
                if any(pc.env_name(part) for part in Path(text).parts):
                    self.attempts.append(text)
                    raise AssertionError(f'an environment file was opened: {text}')
            return original(file, *args, **kwargs)
        return wrapped

    def __enter__(self):
        self.patches = [patch('builtins.open', self.guard(builtins.open)), patch('io.open', self.guard(io.open)),
                        patch('os.open', self.guard(os.open))]
        for item in self.patches:
            item.start()
        return self

    def __exit__(self, *exc):
        for item in reversed(self.patches):
            item.stop()


class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.root = scratch(self)
        self.folder = self.root / 'credential'
        self.folder.mkdir(mode=0o700)
        self.path = self.folder / 'anthropic-api-key'

    def write(self, text, mode=0o600, path=None):
        path = path or self.path
        path.write_text(text)
        os.chmod(path, mode)
        return path

    def test_the_declared_file_yields_the_key(self):
        self.write(SYNTHETIC_KEY + '\n')
        self.assertEqual(pc.load_credential(str(self.path)), SYNTHETIC_KEY)
        self.write(SYNTHETIC_KEY, path=self.folder / 'no-newline')
        self.assertEqual(pc.load_credential(str(self.folder / 'no-newline')), SYNTHETIC_KEY)
        d = declaration(credential_file=str(self.path))
        self.assertEqual(pc.load_credential(str(self.path), d), SYNTHETIC_KEY)
        with self.assertRaises(pc.Refused):
            pc.load_credential(str(self.folder / 'no-newline'), d)          # (not the declared file)

    def test_an_env_path_is_refused_before_anything_is_opened(self):
        os.symlink(self.root / 'target.env', self.folder / 'link')          # (dangling: its target is never created)
        paths = [self.root / '.env', self.root / 'key.env', self.root / '.env' / 'key', self.root / 'x.env' / 'key',
                 self.folder / 'link']
        with NoEnvOpened() as guard:
            for path in paths:
                with self.subTest(path=path), self.assertRaises(pc.Refused) as caught:
                    pc.load_credential(str(path))
                self.assertIn('environment file', str(caught.exception))
        self.assertEqual(guard.attempts, [])

    def test_the_wrong_mode_owner_or_shape_is_refused(self):
        for mode in (0o640, 0o644, 0o400, 0o700):
            path = self.folder / f'mode-{mode:o}'
            with self.subTest(mode=oct(mode)), self.assertRaises(pc.Refused):
                pc.load_credential(str(self.write(SYNTHETIC_KEY + '\n', mode, path)))
        self.write(SYNTHETIC_KEY + '\n')
        with patch('os.getuid', return_value=os.getuid() + 1), self.assertRaises(pc.Refused) as caught:
            pc.load_credential(str(self.path))
        self.assertIn('owned by the account', str(caught.exception))
        for text in ('', '\n', SYNTHETIC_KEY + '\n\n', SYNTHETIC_KEY + '\nsecond-line\n', ' ' + SYNTHETIC_KEY,
                     SYNTHETIC_KEY + ' \n', SYNTHETIC_KEY + '\r\n', 'two words\n'):
            with self.subTest(text=repr(text[-12:])), self.assertRaises(pc.Refused):
                pc.load_credential(str(self.write(text)))
        with self.assertRaises(pc.Refused):
            pc.load_credential(str(self.folder / 'missing'))
        os.symlink(self.path, self.folder / 'plain-link')
        self.write(SYNTHETIC_KEY + '\n')
        with self.assertRaises(pc.Refused):
            pc.load_credential(str(self.folder / 'plain-link'))            # (a link is never followed)
        with self.assertRaises(pc.Refused):
            pc.load_credential('relative/anthropic-api-key')


class EnvironmentTests(unittest.TestCase):
    LISTED = ('ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_PROFILE', 'ANTHROPIC_CUSTOM_HEADERS',
              'ANTHROPIC_FEDERATION_RULE_ID', 'ANTHROPIC_FEDERATION_SOMETHING', 'ANTHROPIC_IDENTITY_TOKEN',
              'ANTHROPIC_ORGANIZATION_ID', 'ANTHROPIC_WORKSPACE_ID', 'ANTHROPIC_LOG', 'HTTP_PROXY', 'HTTPS_PROXY',
              'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy', 'NO_PROXY', 'no_proxy', 'SSL_CERT_FILE',
              'REQUESTS_CA_BUNDLE', 'OPENAI_API_KEY', 'PYTHONPATH')

    def test_the_request_process_inherits_nothing_and_gets_a_fresh_empty_config_dir(self):
        root = scratch(self)
        planted = {name: 'https://attacker.invalid' for name in self.LISTED}
        with patch.dict(os.environ, {**planted, 'ANTHROPIC_API_KEY': 'sk-ant-some-other-key-000000000',
                                     'ANTHROPIC_CONFIG_DIR': '/home/somebody/.config/anthropic'}):
            env = pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), {'QUILLMD_DB_NAME': 'quillmd_qa_sonnet5'},
                                          config_parent=str(root))
            second = pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), config_parent=str(root))
        for name in self.LISTED:
            self.assertNotIn(name, env)
        self.assertFalse([name for name in env if pc.forbidden_name(name)])
        self.assertEqual(env['ANTHROPIC_API_KEY'], SYNTHETIC_KEY)
        config = Path(env['ANTHROPIC_CONFIG_DIR'])
        self.assertTrue(config.is_dir() and config.parent == root and not any(config.iterdir()))
        self.assertEqual(os.stat(config).st_mode & 0o777, 0o700)
        self.assertNotEqual(env['ANTHROPIC_CONFIG_DIR'], second['ANTHROPIC_CONFIG_DIR'])
        self.assertEqual({k: env[k] for k in ('QUILLMD_AI_MODE', 'QUILLMD_AI_PROVIDER', 'QUILLMD_AI_MODEL', 'QUILLMD_AI_INPUT_RATE',
                                              'QUILLMD_AI_OUTPUT_RATE', 'QUILLMD_AI_CACHED_RATE', 'QUILLMD_AI_THINKING',
                                              'QUILLMD_AI_EFFORT', 'QUILLMD_AI_INFERENCE_GEO', 'QUILLMD_DATA_MODE',
                                              'QUILLMD_DB_NAME')},
                         {'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-5',
                          'QUILLMD_AI_INPUT_RATE': '2', 'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20',
                          'QUILLMD_AI_THINKING': 'disabled', 'QUILLMD_AI_EFFORT': 'medium', 'QUILLMD_AI_INFERENCE_GEO': '',
                          'QUILLMD_DATA_MODE': 'synthetic', 'QUILLMD_DB_NAME': 'quillmd_qa_sonnet5'})
        self.assertEqual(env['PATH'], '/usr/bin:/bin')
        pc.scrubbed_now(env)

    def test_extra_settings_cannot_add_a_removed_variable_and_the_process_checks_itself(self):
        root = scratch(self)
        for name in self.LISTED:
            with self.subTest(name=name), self.assertRaises(pc.Refused):
                pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), {name: 'x'}, config_parent=str(root))
        env = pc.scrubbed_environment(SYNTHETIC_KEY, declaration(), config_parent=str(root))
        with self.assertRaises(pc.Refused):
            pc.scrubbed_now({**env, 'https_proxy': 'http://proxy.invalid:3128'})
        (Path(env['ANTHROPIC_CONFIG_DIR']) / 'configs').mkdir()
        with self.assertRaises(pc.Refused):
            pc.scrubbed_now(env)


class CaptureTests(unittest.TestCase):
    """Through the real SDK around an in-process MockTransport: the bytes that WOULD leave, captured before they do."""

    def setUp(self):
        import anthropic
        import httpx
        self.root = scratch(self)
        self.evidence = self.root / 'evidence' / '001'
        self.evidence.mkdir(parents=True, mode=0o700)
        self.seen = []

        def handler(request):
            self.seen.append({'headers': dict(request.headers), 'captured_first': (self.evidence / 'request.json').exists()})
            return httpx.Response(200, headers={'request-id': 'req_synthetic'}, json={
                'id': 'msg_synthetic', 'type': 'message', 'role': 'assistant', 'model': 'claude-sonnet-5',
                'content': [{'type': 'text', 'text': '{}'}], 'stop_reason': 'end_turn', 'stop_sequence': None,
                'usage': {'input_tokens': 10, 'output_tokens': 2}})

        self.client = lambda retries=0: anthropic.Anthropic(api_key=SYNTHETIC_KEY, max_retries=retries,
                                                            http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        pc.install_request_capture()
        self.addCleanup(pc.uninstall_request_capture)
        self.addCleanup(pc.CURRENT_ATTEMPT.clear)

    def send(self, client):
        return client.messages.create(model='claude-sonnet-5', max_tokens=16,
                                      messages=[{'role': 'user', 'content': 'synthetic'}])

    def test_the_exact_request_is_captured_before_it_is_sent_and_never_carries_the_key(self):
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        self.send(self.client())
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(self.seen[0]['captured_first'])
        self.assertEqual(self.seen[0]['headers']['x-api-key'], SYNTHETIC_KEY)     # (the real request carried it)
        data = (self.evidence / 'request.json').read_bytes()
        self.assertNotIn(SYNTHETIC_KEY.encode(), data)
        self.assertIsNone(pc.KEY_SHAPE.search(data))
        record = json.loads(data)
        self.assertEqual((record['method'], record['url']), ('POST', 'https://api.anthropic.com/v1/messages'))
        self.assertEqual(record['body_json']['model'], 'claude-sonnet-5')
        self.assertNotIn('x-api-key', record['headers'])
        self.assertIn('x-api-key', record['removed_headers'])
        self.assertEqual(record['client']['max_retries'], 0)
        self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY), [])

    def test_a_second_request_in_one_attempt_is_refused_before_it_is_sent(self):
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        self.send(self.client())
        with self.assertRaises(pc.Refused):
            self.send(self.client())
        self.assertEqual(len(self.seen), 1)

    def test_a_request_outside_an_attempt_or_from_a_retrying_client_is_refused(self):
        with self.assertRaises(pc.Refused):
            self.send(self.client())
        pc.CURRENT_ATTEMPT.update(number=1, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        with self.assertRaises(pc.Refused):
            self.send(self.client(retries=2))
        self.assertEqual(self.seen, [])
        self.assertFalse((self.evidence / 'request.json').exists())

    def test_uninstalling_restores_the_sdk(self):
        from anthropic._base_client import SyncAPIClient
        self.assertTrue(getattr(SyncAPIClient._prepare_request, '_campaign_capture', False))
        pc.uninstall_request_capture()
        self.assertFalse(getattr(SyncAPIClient._prepare_request, '_campaign_capture', False))


class TransportGuardTests(unittest.TestCase):
    """The last door before a socket, on a REAL httpx.HTTPTransport. Every refusal happens before a connection is
    attempted; the one request it lets through then meets the network guard, which proves it was let through."""

    def setUp(self):
        import httpx
        self.httpx = httpx
        self.evidence = scratch(self)
        pc.install_transport_guard()
        self.addCleanup(pc.uninstall_transport_guard)
        self.addCleanup(pc.CURRENT_ATTEMPT.clear)
        self.addCleanup(pc.SENT.clear)
        self.client = httpx.Client(transport=httpx.HTTPTransport())
        self.addCleanup(self.client.close)

    def post(self, url=pc.PROVIDER_URL):
        return self.client.post(url, json={'model': 'claude-sonnet-5'})

    def test_outside_an_attempt_to_another_host_or_uncaptured_is_refused_before_connecting(self):
        with self.assertRaises(pc.Refused):
            self.post()
        pc.CURRENT_ATTEMPT.update(number=7, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        with self.assertRaises(pc.Refused):
            self.post()                                        # (not captured)
        (self.evidence / 'request.json').write_text('{}')
        for url in ('https://api.deepgram.com/v1/listen', 'https://api.stripe.com/v1/charges',
                    'https://api.anthropic.com/v1/messages/count_tokens', 'http://api.anthropic.com/v1/messages'):
            with self.subTest(url=url), self.assertRaises(pc.Refused):
                self.post(url)
        self.assertEqual(pc.SENT, {})

    def test_one_send_per_attempt_reaches_the_network_and_a_second_is_refused(self):
        pc.CURRENT_ATTEMPT.update(number=7, evidence_dir=str(self.evidence), secret=SYNTHETIC_KEY)
        (self.evidence / 'request.json').write_text('{}')
        with self.assertRaises(network_guard.NetworkDenied):
            self.post()                                        # (let through: the network guard stops it)
        self.assertEqual(pc.SENT, {7: 1})
        with self.assertRaises(pc.Refused):
            self.post()


class LeakTests(unittest.TestCase):
    def test_a_planted_key_is_found_wherever_it_hides_and_the_credential_itself_is_excluded(self):
        root = scratch(self)
        (root / 'evidence' / '001').mkdir(parents=True)
        (root / 'evidence' / '001' / 'clean.json').write_text('{"ok": true}')
        credential = root / 'credential' / 'anthropic-api-key'
        credential.parent.mkdir()
        credential.write_text(SYNTHETIC_KEY + '\n')
        self.assertEqual(pc.leaked(root, SYNTHETIC_KEY, exclude=(credential,)), [])
        self.assertEqual(pc.leaked(root, SYNTHETIC_KEY), ['credential/anthropic-api-key'])
        (root / 'evidence' / '001' / 'deep').mkdir()
        (root / 'evidence' / '001' / 'deep' / 'planted.log').write_text('prefix ' + SYNTHETIC_KEY + ' suffix')
        (root / 'shape.txt').write_text('an unrelated key sk-ant-admin01-abcdefghijkl')
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as handle:
            handle.writestr('word/document.xml', '<w:t>' + SYNTHETIC_KEY + '</w:t>')
        (root / 'evidence' / '001' / 'export.docx').write_bytes(archive.getvalue())
        self.assertNotIn(SYNTHETIC_KEY.encode(), archive.getvalue())      # (compressed: invisible in the raw bytes)
        self.assertEqual(sorted(pc.leaked(root, SYNTHETIC_KEY, exclude=(credential,))),
                         ['evidence/001/deep/planted.log', 'evidence/001/export.docx', 'shape.txt'])


class RequestEnvironmentTests(unittest.TestCase):
    """The QA request process's complete environment (ops/sonnet5_qa.request_environment), built without Django."""

    def test_the_qa_process_gets_the_declared_settings_the_qa_database_and_nothing_else(self):
        from ops import sonnet5_qa as sq
        root = scratch(self)
        (root / 'tmp').mkdir(mode=0o700)
        with patch.dict(os.environ, {'ANTHROPIC_BASE_URL': 'https://attacker.invalid', 'HTTPS_PROXY': 'http://p.invalid',
                                     'QUILLMD_V3_FIELD_RELATIONS': '1', 'QUILLMD_DB_NAME': 'quillmd_fresh'}):
            env = sq.request_environment(SYNTHETIC_KEY, declaration(), root, 'synthetic-db-password',
                                         {'root': str(root), 'stage': 'model_check'})
        self.assertFalse([name for name in env if pc.forbidden_name(name)])
        self.assertEqual((env['QUILLMD_DB_NAME'], env['QUILLMD_DB_HOST'], env['QUILLMD_DB_PORT'], env['QUILLMD_DB_USER']),
                         ('quillmd_qa_sonnet5', '127.0.0.1', '55731', 'quillmd_qa'))
        self.assertTrue(env['QUILLMD_DB_NAME'].startswith(sq.DATABASE_PREFIX))
        self.assertEqual(env['QUILLMD_STATE_DIR'], str(root / 'qa-state'))
        self.assertEqual(env['QUILLMD_ENV_MANAGED'], '1')                  # (settings never calls load_dotenv)
        self.assertEqual({env[name] for name in ('QUILLMD_V3_FIELD_RELATIONS', 'QUILLMD_WM_NARRATIVE',
                                                 'QUILLMD_V3_GENERATION_BATCHES', 'QUILLMD_V3_HISTORY_CONTEXT')}, {'0'})
        self.assertEqual(env['QUILLMD_DEEPGRAM_RATE_PER_MINUTE'], '0.0043')
        self.assertEqual(env['QUILLMD_DATA_MODE'], 'synthetic')
        self.assertEqual(env['ANTHROPIC_API_KEY'], SYNTHETIC_KEY)
        self.assertTrue(Path(env['ANTHROPIC_CONFIG_DIR']).parent == root / 'tmp')
        self.assertEqual(json.loads(env['SONNET5_QA_CONTEXT'])['stage'], 'model_check')
        self.assertNotIn('ANTHROPIC_BASE_URL', env)

    def test_the_fixed_form_builds_to_its_recorded_bytes(self):
        from ops import sonnet5_qa as sq
        form = sq.build_form()
        self.assertEqual(hashlib.sha256(form).hexdigest(), sq.FORM_SHA256)
        self.assertEqual(form, sq.build_form())
        self.assertEqual(sq.NOTES_SHA256, hashlib.sha256(sq.NOTES.encode()).hexdigest())
        self.assertEqual(sorted(sq.EXPECTED), sorted(sq.FORM_LABELS))
        for label, value in sq.EXPECTED.items():
            self.assertIn(f'{label}: {value}', sq.NOTES.splitlines())


class NetworkGuardTests(unittest.TestCase):
    def test_the_guard_refuses_a_provider_host_and_a_public_address(self):
        network_guard.positive_control(self)


if __name__ == '__main__':
    unittest.main()
