"""The new-path call-guard matrix (Gemini migration slice S12; design/FINAL.md 10.4(1) and (3), as
design/ADJUDICATION.md R-6 amends them; DECISIONS D17 and D22). Synthetic data only; nothing is sent.

On the new path Gemini is the only interpreter (P1): no code object of the legacy reader executes during new-path work.
The matrix runs every way into the application on new-path encounters in every state FINAL 10.4(1) names, and the
production sentinel - its CALL-level checks on, as tests run it - counts what ran (tests/guard_support.py).

What each class proves:
- GeneratedTests: the matrix is generated, never hand-listed - from cptstudio/urls.py's patterns, jobs.STAGES' keys and
  the scripts and commands ops/install.py runs in an image of the app - so a pattern, a stage kind or an in-image script
  added there and not driven is reported missing (a planted one of each is, in every form the installer can name one:
  positional or keyword, a list spelled out, a local assigned one, a function returning one, an entrypoint role); a form
  the generator cannot read raises naming its line, never dropped (fail-closed: a planted one of each); an exemption
  names something the installer runs and says why it reads no encounter row.
- NewPathOnlyDatabaseTests (R-6): on a database that holds ONLY new-path encounters, every generated item runs and the
  sentinel counts NOTHING under any label - new_path, other, unscoped, or legacy_record - so neither the list, session
  and operator-list loops (which label per row) nor the in-image scripts (which run with no scope, and meet two members'
  answers left standing: UNDO_HAZARDS names exactly those) run legacy code on a new-path row; FINAL 10.4(1)'s list
  (FACETS) is met entry by entry, and no write gate tripped.
- BesideLegacyRecordsTests: the same matrix where the database also holds encounters the legacy reader read (the
  test-only legacy chain): zero new_path executions, and nothing under other or unscoped either, while the legacy
  rows' own reads in the matrix's lists ran legacy code as legacy_record (the archived reader serving the records it
  made, which D22 reports as residual legacy execution).
- PositiveControlTests (FINAL 10.4(3); an instrument that never fires proves nothing): the legacy chain run inside a
  new_path scope records hits in every class - a gi function, an engine or reconcile function, a legacy regex (CALL) and
  a legacy cache wrapper (CALL).

DESIGN V2 (docs/gemini-migration/FINAL-V2.md 5.7 measure 8; AMENDMENT-1 11.1 U15; step 6a of its 8.1). The worlds above
were written for design v1's one-pass reading; since step 5b's switch the new path is design v2 (pass 1, pass 2,
engine/), so the matrix runs over V2World: generated from cptstudio/urls.py, jobs.STAGES (appraise among them) and the
in-image scripts, over cpt-studio-events@2 assessments only, the 17 retired modules armed as the RETIRED kind beside the
legacy deny set, and nothing counted under any label for either:
- V2NewPathOnlyDatabaseTests: every generated item runs (pass 2's appraise stage included) and the sentinel counts
  nothing - legacy or retired - under new_path, other, unscoped or legacy_record; 5.7 measure 8's worlds are met (assess
  FIRST, FINAL and AGAIN; answer recompute; context save; the review view; decision save; reload; export approved,
  draft and operator; the peer request; a reinstated code's reviewed coverage re-run over the frozen inventory), and so
  is FINAL 10.4(1)'s list but what V2_UNREACHED names, each with what was measured;
- V2BesideLegacyRecordsTests: the same beside legacy rows (the test-only legacy chain) and v1 rows (the test-only v1
  chain, cpt-studio-events@1): zero new_path executions, nothing under other or unscoped, and every v1 row labelled
  and read legacy_record - a v1 row is never read under new_path (5.7 measure 8's separate world);
- V2PositiveControlTests: the recorder turns red for each class under each label it judges - a legacy function, a
  legacy regex and a legacy cache, a RETIRED function, a RETIRED cache and (refutation 6a-r1 F7: the RETIRED kind's
  regex class) a RETIRED regex, on a request and in a script - naming the planted read;
- U15Tests (AMENDMENT-1 11.1 U15, A14, A17): the page of a legacy encounter whose update recorded its assess #1 (never
  current), as labelled and with the encounter's label forced to new_path (the relabel guard): the new_path scope counts
  0 legacy executions while the earlier codes are drawn; and the new worlds - an update pending on a legacy encounter,
  a completed update's what-changed read - green.
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import URLPattern, get_resolver, path
from django.utils import timezone

from studio import customer_api, interpretation, jobs, models, review
from studio.gi import cues, structure
from studio.interpretation import adapter, holds, readers, sentinel
from studio.providers.base import request_sha256
from tests import guard_support, v1_chain
from tests.guard_support import (APP, CACHE, CODE, IN_IMAGE_EXEMPT, INSTALL, LABELS, LEGACY, NEW, OK, OTHER, REGEX,
                                 UNSCOPED, WORKER, GuardCase, LegacyWorld, Matrix, World, generated, in_image,
                                 in_process_children, installer, legacy_chain, participants, stage_kinds, tagged,
                                 url_routes)
from tests.support import factories as f
from tests.test_interpretation_adapter import encoded, envelope
from tests.test_pipeline_api import FakeProvider
from tests.test_pipeline_assess_events import AUTH, MODULES, Scripted, final_answer, is_peer, one_colonoscopy, reading
from tests.test_pipeline_assess_events import Corti as PipelineCorti
from tests.test_pipeline_assess_events import two_procedures
from tests.v2.test_adapter import measured_pins
from tests.v2.test_jobs import (EXTRACTION, UNKNOWN, USAGE as V2_USAGE, ScriptedInterpreterV2, answered, appraisal_for,
                                body, oracle_answer)
from tests.v2.test_settle import HEALTH_PIN, NOTE, colonoscopy, event, fact, lesion, note_answer, src

Job, Run = models.Job, models.ProviderRun


class GeneratedTests(SimpleTestCase):
    def test_the_items_are_read_from_the_url_map_the_stages_and_the_installer(self):
        measured = [str(pattern.pattern) for pattern in get_resolver().url_patterns if isinstance(pattern, URLPattern)]
        self.assertEqual(url_routes(), measured)
        self.assertEqual(len(set(measured)), len(measured))
        self.assertIn('api/encounters/<uuid:encounter_id>/retry-reading', measured)
        self.assertEqual(stage_kinds(), sorted(jobs.STAGES))
        self.assertIn(jobs.INTERPRET, stage_kinds())
        found = in_image()
        # FINAL 10.4(1) names three; each is generated from the installer's own calls, with the others it runs
        for name in ('RECOMPUTE_STATES', 'CLOSE_STAGES', 'UNDO_HAZARDS_READ'):
            self.assertEqual(found[('script', name)], 'app_script')
        self.assertTrue(installer().UNDO_HAZARDS_READ.startswith(installer().UNDO_HAZARDS))
        self.assertIn(('command', 'interpretation_report'), found)
        self.assertNotIn(('script', 'source'), found)  # app_script's own local is its plumbing, not a script
        items = generated()
        self.assertEqual(len(items), len(set(items)))
        self.assertEqual([item for item in items if item[0] == 'worker'], [('worker', name) for name in WORKER])

    def test_every_exemption_names_what_the_installer_runs_and_says_why(self):
        found = in_image()
        for item, why in IN_IMAGE_EXEMPT.items():
            with self.subTest(item=item):
                self.assertIn(item, found)
                self.assertIn('no encounter row', why)

    def test_an_item_added_and_not_driven_is_missing(self):
        matrix = Matrix(self)
        # nothing observed: every item is missing
        self.assertEqual(set(matrix.missing()), set(generated()) - set(IN_IMAGE_EXEMPT))
        from cptstudio import urls

        planted_view = path('planted-s12/', lambda request: HttpResponse('planted'))
        # each form the installer can name a script or a command in: positional and keyword, a list, a local bound to
        # one, a function returning one, and the entrypoint's own migrate role
        source = INSTALL.read_text(encoding='utf-8') + (
            "\n\ndef planted_phase(image_id, env):\n"
            "    app_script(image_id, env, APP_SCRIPT_ANSWER, {}, what='a planted script')\n"
            "    app_script(image_id, env, body=APP_SCRIPT_PRELUDE, params={}, what='a planted keyword script')\n"
            "    oneshot(image_id, command=['manage', 'planted_keyword_command'], env_bytes=env)\n"
            "    command = ['manage', 'planted_local_command', '--flag']\n"
            "    oneshot(image_id, command, env)\n"
            "    oneshot(image_id, planted_command_list('x'), env)\n"
            "    extended = ['manage', 'planted_extended_command']\n"
            "    extended = extended + ['--flag']\n"
            "    oneshot(image_id, extended, env)\n"
            "    return oneshot(image_id, ['manage', 'planted_command'], env)\n"
            "\n\ndef planted_command_list(value):\n"
            "    return ['manage', 'planted_returned_command', value] + []\n")
        with mock.patch.object(urls, 'urlpatterns', urls.urlpatterns + [planted_view]), \
                mock.patch.dict(jobs.STAGES, {'planted': lambda job: {}}):
            missing = set(matrix.missing(source))
        for item in (('url', 'planted-s12/'), ('stage', 'planted'), ('script', 'APP_SCRIPT_ANSWER'),
                     ('script', 'APP_SCRIPT_PRELUDE'), ('command', 'planted_keyword_command'),
                     ('command', 'planted_local_command'), ('command', 'planted_returned_command'),
                     ('command', 'planted_extended_command'), ('command', 'planted_command')):
            with self.subTest(item=item):
                self.assertIn(item, missing)
        matrix.observations.append(type('Seen', (), {'key': ('url', 'no-such-route/')})())
        self.assertEqual(matrix.unknown(), [('url', 'no-such-route/')])

    def test_a_form_the_generator_cannot_read_fails_closed(self):
        # the review of S12, finding 3: an in-image script or command the generator cannot resolve to a module-level
        # script or a literal command raises, naming its line - it is never dropped (the matrix would stay green over a
        # script it never ran)
        base = INSTALL.read_text(encoding='utf-8')
        forms = {
            'a concatenated body': "app_script(image_id, env, UNDO_HAZARDS + APP_SCRIPT_ANSWER, {}, what='x')",
            'a starred command': "oneshot(image_id, [*['manage'], 'planted_command'], env)",
            'a computed command name': "oneshot(image_id, ['manage', name], env)",
            'a starred argument before the body': "app_script(*arguments, what='x')",
            'a body passed by **': 'app_script(image_id, env, **options)',
            'a manage list with no command': "oneshot(image_id, ['manage'] + rest, env)",
            'a shell script that is no module script': "oneshot(image_id, ['manage', 'shell', '-c', body], env)",
            'an entrypoint role it does not know': "oneshot(image_id, ['planted_role'], env)",
            'a command passed in': 'oneshot(image_id, command, env)',
            'a command bound by a loop': 'for each in commands:\n        oneshot(image_id, each, env)',
            'a command bound by a handler': 'try:\n        pass\n    except Exception as caught:\n'
                                            '        oneshot(image_id, caught, env)',
            'a command that only extends itself': "grown = grown + ['--flag']\n    oneshot(image_id, grown, env)",
            'an alias of oneshot': "run_once = oneshot\n    run_once(image_id, ['manage', 'planted_alias'], env)",
            'a partial of app_script': 'functools.partial(app_script, image_id)',
        }
        for what, statement in forms.items():
            with self.subTest(form=what):
                source = base + ('\n\ndef planted_phase(image_id, env, name, body, arguments, options, rest, command, '
                                 f'commands):\n    {statement}\n')
                with self.assertRaisesRegex(ValueError, r'ops/install\.py:\d+: .* the matrix cannot tell what'):
                    in_image(source)
        self.assertTrue(in_image())  # the installer's own source reads whole

    def test_the_entrypoint_roles_it_resolves_are_the_images_own(self):
        # a one-shot given an entrypoint role (deploy/entrypoint.sh) runs what that role execs: each role the generator
        # resolves is a `python manage.py <command>` arm of the entrypoint, and the item is that command
        text = (APP / 'deploy' / 'entrypoint.sh').read_text(encoding='utf-8')
        arms = dict(re.findall(r'^ {4}([a-z]+)\)\n(?: {8}.*\n)*? {8}exec (.*)$', text, re.MULTILINE))
        self.assertEqual(set(arms), {'web', 'worker', 'migrate', 'manage'})
        self.assertTrue(guard_support.ENTRYPOINT_ROLES)
        for role, item in guard_support.ENTRYPOINT_ROLES.items():
            with self.subTest(role=role):
                self.assertEqual(item[0], 'command')
                self.assertTrue(arms[role].startswith(f'python manage.py {item[1]} '), arms[role])
                self.assertIn(item, in_image())


class PositiveControlTests(GuardCase):
    def test_the_legacy_chain_in_a_new_path_scope_records_a_hit_in_every_class(self):
        # FINAL 10.4(3): its stages' bounded children run in this process here, so their reading is counted too
        _, text = tagged(two_procedures, 'P0')()
        with sentinel.call_checks(), in_process_children(), legacy_chain(), \
                sentinel.scope(NEW, entry='positive control: the legacy chain') as opened:
            encounter = models.Encounter.objects.create(workspace=self.ws, title='Synthetic', created_by=self.user)
            revision = f.pasted_revision(encounter, self.user, text, extract=False)
            jobs.start_pipeline(revision, self.user)
            ran = []
            while (job := jobs.claim_next()) is not None:
                ran.append(jobs.run_job(job))
            encounter.refresh_from_db()
            review.effective_view(encounter.current_assessment)
        self.assertEqual([(job.kind, job.state) for job in ran], [('extract', 'succeeded'), ('analyze', 'succeeded'),
                                                                  ('predict', 'succeeded'), ('assess', 'succeeded')])
        kinds = opened.by_kind(NEW)
        self.assertTrue(all(kinds[kind] > 0 for kind in (CODE, REGEX, CACHE)), kinds)
        described = '\n'.join(opened.describe(NEW))
        self.assertIn('studio/gi/', described)  # a gi function
        self.assertTrue(any(name in described for name in ('studio/validation/engine.py',
                                                           'studio/validation/reconcile.py')), described[:2000])
        self.assertIn('(cache)', described)
        self.assertEqual(sentinel.refusal(opened), 'executed')
        self.assertGreater(opened.count(LEGACY), 0)  # the legacy overlay's own read, relabelled by its reader


# --- design v2 (docs/gemini-migration/FINAL-V2.md 5.7 measure 8; AMENDMENT-1 11.1 U15; step 6a) -----------------------

TAG = 'Synthetic call-guard matrix document {}.\n'  # each document's own last line: a distinct text, and Corti's key
SNARE = ('45385', 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.')
ANTRAL = ('43239', 'Biopsies of the gastric antrum were taken with cold forceps.')
DENIED = ('45380', 'Neither biopsy nor tattoo was performed.')
# Corti's selections per world document (its tag line), FakeProvider's evidence quoted verbatim from the document
SELECTIONS = {
    'E1': (SNARE, ANTRAL, DENIED),  # 45385 and 43239 ready, 45380 held on the procedure (answerable)
    'E2': (SNARE,),  # the upper endoscopy no proposal covers: the bounded second review is offered
    'E4': (('45385', 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'),
           ('45380', 'A 3 mm polyp in the ascending colon was biopsied with cold forceps.')),
    'E5': (SNARE, ANTRAL, DENIED),  # no date of service stated: each code asks its act's time
    'E6': (SNARE,), 'E7': (SNARE, ANTRAL), 'E8': (SNARE, ANTRAL, DENIED),
    'L15': (SNARE, ANTRAL),  # U15's legacy encounter: read by the legacy chain, then by design v2 after a save
}
# Astra's and Fable's first readings (the peer stages review them): a world document's, and the legacy rows' (the legacy
# matrix's own, GuardCase.participant_codes)
PARTICIPANT_CODES = (SNARE,)  # agreeing with Corti: agreement adds proposers and nothing else (5a's pinned test)
UNDATED_NOTE = NOTE.replace('Date of service: 03/14/2031', 'Written for software tests only.')
TWO_PLACES = ('SYNTHETIC COLONOSCOPY REPORT\n'                                              # S1
              'Date of service: 03/14/2031\n'                                                # S2
              'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                # S3
              '\n'
              'Findings: The colonoscope was advanced to the cecum.\n'                       # S4
              'A 6 mm polyp in the sigmoid colon was removed with a cold snare.\n'           # S5
              'A 3 mm polyp in the ascending colon was biopsied with cold forceps.\n')       # S6
# What the v2 world does not reach on the v2 product as built (each measured: the step's NOTES, the experiment logs
# logs/g6ax*.log), so no FACET is silently skipped: the test asserts exactly these are unsatisfied, and a facet that
# becomes reachable fails it until it leaves this list.
V2_UNREACHED = {
    'an approval with a modifier': 'no separate-lesion modifier review is offered on a v2 encounter read through the '
                                   'pipeline (two lesions at two places, each established distinct from the other: '
                                   'both codes READY, no modifier_review; logs/g6ax6.log)',
}


def v2_answer(name):
    """Pass 1's answer to world document ``name`` (tests/v2/test_settle.py's builders; the tag line, the document's last
    unit, is cited by none)."""
    if name == 'E4':
        data = colonoscopy(
            TWO_PLACES,
            event('E2', ['S5'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S5']))],
                  target__lesion=[fact('L1', src(['S5'], 'A 6 mm polyp'))],
                  target__places=[fact('sigmoid_colon', src(['S5'], 'sigmoid colon'))],
                  technique__device=[fact('cold_snare', src(['S5'], 'cold snare'))]),
            event('E3', ['S6'], 'biopsied', 'was biopsied', 'biopsy', session=[fact('X1', src(['S6']))],
                  target__lesion=[fact('L2', src(['S6'], 'A 3 mm polyp'))],
                  target__places=[fact('ascending_colon', src(['S6'], 'ascending colon'))],
                  technique__device=[fact('cold_forceps', src(['S6'], 'cold forceps'))]),
            lesions=[lesion('L1', src(['S5'], 'A 6 mm polyp'), multiplicity=[fact('single', src(['S5'], 'A 6 mm polyp'))],
                            places=[fact('sigmoid_colon', src(['S5'], 'sigmoid colon'))],
                            distinct_from=[fact('L2', src(['S6'], 'A 3 mm polyp'))]),
                     lesion('L2', src(['S6'], 'A 3 mm polyp'), multiplicity=[fact('single', src(['S6'], 'A 3 mm polyp'))],
                            places=[fact('ascending_colon', src(['S6'], 'ascending colon'))],
                            distinct_from=[fact('L1', src(['S5'], 'A 6 mm polyp'))])])
        return data
    data = note_answer()
    if name == 'E5':
        data['encounter']['date_of_service'] = {'state': 'not_stated', 'value': '', 'sources': [], 'options': []}
    return data


def v2_document(name) -> str:
    base = TWO_PLACES if name == 'E4' else UNDATED_NOTE if name == 'E5' else NOTE
    return base + TAG.format(name)


class WorldCorti(PipelineCorti):
    """Corti's fake: a world document's selections by its tag line (SELECTIONS); any other document (the legacy rows', a
    second review's excerpt) as the legacy matrix's groups answer it."""

    def send(self, request, *, deadline_s):
        text = request.contexts[0]
        for name, selections in SELECTIONS.items():
            if TAG.format(name) in text:
                self.selections = list(selections)
                return FakeProvider.send(self, request, deadline_s=deadline_s)
        return super().send(request, deadline_s=deadline_s)


class WorldInterpreter(ScriptedInterpreterV2):
    """Design v2's InterpreterV2 (tests/v2/test_jobs.ScriptedInterpreterV2) answering pass 1 for the world document whose
    text the revision begins with (an addendum's revision begins with its document's), pass 2 by the faithful oracle
    over the claim set the production builder makes for it; ``script``'s exchanges first, by purpose."""

    def _exchange(self, body_dict, deadline, purpose):
        sha = request_sha256(body_dict)
        self.sent.append((purpose, sha))
        queued = self.script.get(purpose)
        if queued:
            return queued.pop(0)
        text = self._request.contexts[0]
        found = sorted((key for key in self.answers if text.startswith(key)), key=len)
        if not found:
            raise AssertionError('no world document begins this revision')
        answer_dict = self.answers[found[-1]]()
        if purpose == EXTRACTION:
            return answered(body(answer_dict))
        return answered(oracle_answer(appraisal_for(*self._document(text), answer_dict), self.oracle))


class WorldScripted(Scripted):
    """tests/test_pipeline_assess_events.Scripted whose first reading is a world document's (PARTICIPANT_CODES) for a
    world document, and the legacy matrix's (GuardCase.participant_codes) for any other - each reading's quotes the
    document's own."""

    def __init__(self, name, replay_dir, codes):
        super().__init__(name, replay_dir, codes)
        self.legacy_first = final_answer(name, reading(guard_support.GuardCase.participant_codes), 1)
        self.world_first = self.answers['first']

    def send_loop(self, request, **kwargs):
        if not is_peer(request.body):
            world = any(TAG.format(name).strip() in json.dumps(request.body) for name in SELECTIONS)
            self.answers['first'] = self.world_first if world else self.legacy_first
        return super().send_loop(request, **kwargs)


@override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR='/nonexistent-replay-dir', PROVIDER_MODE='live',
                   AUTHORIZATION_REF=AUTH, ASTRA_MODE='disabled', FABLE_MODE='disabled', INTERPRET_MAX_CHARS=20_000,
                   INTERPRET_MAX_PAGES=40, STORAGES=guard_support.PLAIN_STATIC)
class V2GuardCase(TestCase):
    """The design v2 pipeline (FINAL-V2 7.4) through the product's doors: pass 1 and pass 2 by WorldInterpreter, the pins
    of 2.5 measured on this tree and the health thresholds pinned (tests/v2/test_jobs.PipelineCase's), Corti's fake by
    document (WorldCorti), Astra and Fable the scripted replay adapters (tests/test_pipeline_assess_events.Scripted) -
    and NOT the test-only v1 chain: every retired code object is armed throughout."""
    corti_groups = guard_support.GuardCase.corti_groups  # the legacy rows' documents
    participant_codes = PARTICIPANT_CODES

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        status = sentinel.install()
        assert status['state'] == 'ok', status

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.multiple(interpretation, HEALTH_THRESHOLDS_SHA256=HEALTH_PIN, **measured_pins()))
        self.replay = tempfile.mkdtemp(prefix='s6a-replay-', dir=os.environ.get('TMPDIR'))
        self.addCleanup(shutil.rmtree, self.replay, True)
        self.enterContext(override_settings(GEMINI_REPLAY_DIR=self.replay))
        self.ws = f.workspace()
        self.user = f.member(self.ws, f.user(), role=models.Membership.REVIEWER)
        self.membership = models.Membership.objects.get(user=self.user, workspace=self.ws)
        self.corti = WorldCorti(*self.corti_groups)
        self.interpreter = WorldInterpreter({})
        self.adapters = {name: WorldScripted(name, self.replay, self.participant_codes) for name in MODULES}
        self.enterContext(mock.patch.object(adapter, 'get_interpreter_v2', return_value=self.interpreter))
        self.enterContext(mock.patch('studio.jobs.get_provider', return_value=self.corti))
        self.enterContext(mock.patch('studio.participants.get_participant', side_effect=self.adapter))
        self.assertTrue(sentinel.retired_armed())

    def adapter(self, name):
        from studio import participants as participants_module

        return None if participants_module.participant_mode(name) == 'disabled' else self.adapters[name]


class V2World(World):
    """The new-path world on design v2 (FINAL-V2 5.7 measure 8): every act a matrix entry, through the product's doors,
    over cpt-studio-events@2 assessments only. Its encounters: E1 (two ready codes and a held one answerable; an approval,
    a member's answer, its recompute and its withdrawal; a context save that re-checks; Stop and Resume; the doors this
    state refuses, retry-update's among them; the exports; an addendum read), E2 (Astra and Fable configured: their
    readings, the peer requests, assess #1 and #2; the bounded second review offered, asked, run and followed up), E3
    (an excluded, reinstatable code: confirmed, revoked, reinstated - its reviewed coverage re-run by the engine over the
    frozen inventory - approved and the other rejected, the approved exports), E4 (two lesions established distinct),
    E5 (no date of service: a context save that re-predicts on the member's date), E6 (a pass-1 answer the reader
    refuses: the member's and the operator's retries), E7 (pass 1's outcome unknown: the operator's reconciliation), E8
    (a worker that died while pass 1 was sending: mark_stale's settled path), an interpreter hold and its release, two
    members' answers left standing, a sign-in and sign-out, and every in-image script and command.

    E3's rows are built as tests/v2/test_readers.V2World builds them (store.row_v2 of a settled inventory, the engine's
    assessment persisted in the renderer's shape, an excluded reinstatable proposal) - the pipeline as built reaches no
    4.6 exclusion on these synthetic documents (logs/g6ax3.log, g6ax6.log); every act on them is a request through the
    product's doors."""

    def __init__(self, case, matrix, **kwargs):
        super().__init__(case, matrix, **kwargs)
        self.v1_ids = []

    def record(self, queued):
        """Nothing to write: pass 1 and pass 2 are answered by the case's WorldInterpreter."""

    def legacy_upload(self, name):
        """A world document read by the test-only legacy chain (a legacy context and assessment, no EventInventory) -
        fixture work, not matrix entries; its pass-1 answer registered for the design v2 reading an update makes."""
        text = v2_document(name)
        self.case.interpreter.answers[text] = functools.partial(v2_answer, name)
        with legacy_chain():
            response = self.member.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes',
                                                            'title': f'Synthetic {name}'})
            self.case.assertEqual(response.status_code, 201, response.content[:400])
            self.ids[name] = response.json()['id']
            Matrix(self.case).drain(tag=name)
        return self.ids[name]

    def reads_of(self, pk, tag):
        """Every read of the encounter ``pk``: the customer's detail, the list and the session, the operator's detail,
        trace and report list."""
        self.get(f'/api/encounters/{pk}', tag=tag)
        self.get('/api/encounters', tag=tag)
        self.get('/api/session', tag=tag)
        for path in (f'/ops/api/encounters/{pk}', f'/ops/api/encounters/{pk}/trace', f'/ops/api/encounters/{pk}/reports'):
            self.get(path, client=self.operator, tag=tag)

    def v2_upload(self, name, *, file=False):
        """POST /api/encounters of world document ``name`` (attested synthetic), its pass-1 answer registered."""
        text = v2_document(name)
        self.case.interpreter.answers[text] = functools.partial(v2_answer, name)
        if file:
            files = {'file': SimpleUploadedFile(f'{name.lower()}.txt', text.encode('utf-8'), content_type='text/plain'),
                     'synthetic_attestation': 'yes', 'title': f'Synthetic {name}'}
        else:
            files = {'text': text, 'synthetic_attestation': 'yes', 'title': f'Synthetic {name}'}
        response = self.post('/api/encounters', files=files, tag=name)
        self.ids[name] = response.json()['id']
        return self.ids[name]

    def run(self):
        from studio.interpretation import readers

        real = readers.EventReader.reading

        def reading(reader, assessment):
            self.recounts += 1
            return real(reader, assessment)

        with mock.patch.object(readers.EventReader, 'reading', reading):
            return self._run()

    def _run(self):
        self.no_encounter()
        if self.legacy_rows:
            self.legacy_records()
            self.v1_records()
        self.held_and_answered()
        self.participants_and_second_review()
        self.excluded_and_reinstated()
        self.modifier()
        self.new_date()
        self.failed_reading()
        self.unknown_outcome()
        self.stale_stage()
        self.addendum()
        self.interpreter_hold()
        self.standing_answers()
        self.sign_out()
        self.in_image()
        return self

    def v1_records(self):
        """v1 rows (cpt-studio-events@1: a test instance's), made by the test-only v1 chain with its seam - fixture rows,
        never matrix entries; the matrix's lists and scripts then meet them, and a v1 row is read as stored under
        legacy_record, never under new_path (FINAL-V2 6.2; 5.7 measure 8's separate world)."""
        world = World(self.case, Matrix(self.case), operator=(self.operator_user, self.operator))
        with v1_chain.v1_chain():
            replay = Path(self.case.replay) / adapter.NAME
            replay.mkdir(exist_ok=True)
            world.case = self.case
            pk = world.upload('V1', tagged(one_colonoscopy, 'V1'))
            world.drain('V1')
        assessment = models.Encounter.objects.get(pk=pk).current_assessment
        self.case.assertIsNotNone(assessment)
        self.case.assertEqual(assessment.engine_version, interpretation.ENGINE_VERSION)  # v1's events engine
        self.v1_ids.append(pk)

    def held_and_answered(self):
        pk = self.v2_upload('E1', file=True)
        self.drain('E1 first')
        payload = self.reads('E1')
        self.case.assertEqual({code: row['status'] for code, row in self.codes(payload).items()},
                              {'45385': 'ready', '43239': 'ready', '45380': 'needs_detail'})
        self.get(f'/api/encounters/{pk}/original', tag='E1')
        self.get(f'/ops/api/encounters/{pk}/original', client=self.operator, tag='E1')
        self.decide('E1', '43239', 'approve')
        row = next(item for item in self.detail('E1')['details_needed']
                   if '45380' in item['affects'] and 'not_documented' in item['allow'])
        saved = self.post(f'/api/encounters/{pk}/details',
                          {'answers': [{'id': row['id'], 'fact': row['fact'], 'value': 'not_documented'}]}, tag='E1')
        self.drain('E1 answer')
        self.reads('E1', 'answered')
        self.post(f'/api/encounters/{pk}/details/{saved.json()["answer_ids"][0]}/revoke', tag='E1')
        self.drain('E1 answer withdrawn')
        self.post(f'/api/encounters/{pk}/context', {'setting': 'asc'}, tag='E1 re-check')
        self.post(f'/api/encounters/{pk}/stop', expect=OK, tag='E1')
        self.post(f'/api/encounters/{pk}/resume', tag='E1')
        self.drain('E1 re-check')
        clarification = models.Clarification.objects.filter(encounter_id=pk).order_by('created_at').first()
        self.post(f'/api/encounters/{pk}/clarifications/{clarification.pk}/confirm',
                  {'candidate_id': 'c1', 'attestation': 'synthetic'}, expect=(409,), tag='E1 not offered')
        self.post(f'/api/encounters/{pk}/second-review', expect=(409,), tag='E1 nothing open')
        self.post(f'/api/encounters/{pk}/retry-reading', expect=(409,), tag='E1 nothing to retry')
        self.post(f'/api/encounters/{pk}/retry-update', expect=(409,), tag='E1 no update failed')
        self.exports('E1')
        self.reads('E1', 'exported')

    def participants_and_second_review(self):
        with participants():
            pk = self.v2_upload('E2')
            self.drain('E2 participants')
            payload = self.reads('E2', 'offer')
            self.case.assertTrue(payload['recheck']['available'], payload['recheck'])
            self.post(f'/api/encounters/{pk}/second-review', tag='E2')
            self.drain('E2 second review')
            self.reads('E2', 'second review')
            self.exports('E2')

    def excluded_and_reinstated(self):
        from tests.v2 import test_readers

        row = test_readers.excluded_row()
        # its evidence as the renderer stores a proposer's quote (context_index 0, exact), so the reviewer's
        # reinstatement is offered on it (review._actions reads review.exact_evidence)
        row = dataclasses.replace(row, evidence=tuple({**span, 'context_index': 0, 'exact': True}
                                                      for span in row.evidence))
        with mock.patch.object(test_readers.f, 'workspace', return_value=self.case.ws), \
                mock.patch.object(test_readers.f, 'member', return_value=self.case.user):
            built = test_readers.V2World(excluded=row)
        # its two runs settled as the stages settle theirs (scope.effect), so no later send reads them as an answer
        # no stage settled (jobs._record_unsettled_holds, DECISIONS D53)
        Run.objects.filter(pk__in=(built.first.pk, built.second.pk)).update(scope={'effect': holds.ANSWERED})
        self.ids['E3'] = str(built.enc.pk)
        payload = self.reads('E3')
        self.case.assertEqual(self.codes(payload)['45386']['status'], 'excluded')
        self.decide('E3', '45386', 'confirm')
        self.decide('E3', '45386', 'revoke')
        self.decide('E3', '45386', 'reinstate')
        before = self.recounts
        self.reads('E3', 'reinstated')
        self.case.assertGreater(self.recounts, before)  # the reinstated code's coverage re-run over the frozen inventory
        self.decide('E3', '45386', 'approve')
        rejectable = [code for code, row in self.codes(self.detail('E3')).items()
                      if 'reject' in row['allowed_actions'] and code != '45386']
        self.case.assertTrue(rejectable)
        self.decide('E3', rejectable[0], 'reject')
        self.reads('E3', 'reinstated and decided')
        self.exports('E3')  # its rows record no coding-service run, so its approved export waits (E4's is made)

    def modifier(self):
        self.v2_upload('E4')
        self.drain('E4')
        payload = self.reads('E4')
        self.case.assertEqual({code: row['status'] for code, row in self.codes(payload).items()},
                              {'45385': 'ready', '45380': 'ready'})
        offered = [row for row in payload['codes'] if row.get('modifier_review')]
        for row in payload['codes']:  # each approved - with the reviewer's modifier where the review is offered
            if row in offered:
                self.decide('E4', row['code'], 'approve', tag='modifier',
                            modifiers=[row['modifier_review']['options'][0]])
            else:
                self.decide('E4', row['code'], 'approve', tag='both approved')
        self.reads('E4', 'approved')
        self.exports('E4', approved=True)

    def new_date(self):
        pk = self.v2_upload('E5')
        self.drain('E5 undated')
        self.reads('E5')
        self.post(f'/api/encounters/{pk}/context', {'service_date': '2031-03-14'}, tag='E5 new date')
        self.drain('E5 new date')
        self.reads('E5', 'dated')

    def failed_reading(self):
        refused = answered(encoded(envelope('{"not": "the schema"')))
        self.case.interpreter.script[EXTRACTION] = [refused, refused, refused]
        pk = self.v2_upload('E6')
        self.drain('E6', expect=(Job.SUCCEEDED, Job.FAILED))
        self.reads('E6', 'failed')
        self.post(f'/api/encounters/{pk}/retry-reading', tag='E6')
        self.drain('E6 retry', expect=(Job.SUCCEEDED, Job.FAILED))
        self.post(f'/ops/api/encounters/{pk}/retry-reading', {'override': False}, client=self.operator, tag='E6')
        self.drain('E6 operator retry', expect=(Job.SUCCEEDED, Job.FAILED))
        self.reads('E6', 'failed again')
        self.case.assertEqual(self.case.interpreter.script[EXTRACTION], [])

    def unknown_outcome(self):
        pk = self.v2_upload('E7')
        self.drain('E7', until=Job.EXTRACT)
        self.case.interpreter.script[EXTRACTION] = [UNKNOWN]
        self.drain('E7 unknown', until=jobs.INTERPRET)
        run = Run.objects.get(encounter_id=pk, purpose=interpretation.PURPOSE, state=Run.UNKNOWN)
        self.reads('E7', 'unknown')
        self.post(f'/ops/api/encounters/{pk}/reconcile', {'provider_run_id': str(run.pk), 'note': NOTE_TEXT},
                  client=self.operator, tag='E7')
        self.drain('E7 reconciled', expect=(Job.SUCCEEDED, Job.FAILED))
        self.reads('E7', 'reconciled')

    def stale_stage(self):
        pk = self.v2_upload('E8')
        self.drain('E8', until=Job.EXTRACT)
        job = Job.objects.get(encounter_id=pk, kind=jobs.INTERPRET)
        Job.objects.filter(pk=job.pk).update(state=Job.RUNNING, started_at=timezone.now() - timedelta(seconds=700),
                                             attempts=1)
        sending_pass_1(job, body(v2_answer('E8')), self.case.user)
        self.matrix.call(('worker', 'mark_stale'), 'jobs.mark_stale', jobs.mark_stale, tag='E8')
        self.drain('E8 settled')
        self.reads('E8', 'settled')

    def standing_answers(self):
        for name, value in (('E5', 'cannot_confirm'), ('E8', 'not_documented')):
            pk = self.ids[name]
            rows = [item for item in self.detail(name, tag='before a standing answer')['details_needed']
                    if value in item['allow']]
            self.case.assertTrue(rows, f'{name} asks nothing a member can answer {value!r}')
            self.post(f'/api/encounters/{pk}/details',
                      {'answers': [{'id': rows[0]['id'], 'fact': rows[0]['fact'], 'value': value}]},
                      tag=f'{name} standing answer')
            self.drain(f'{name} standing answer')
            self.reads(name, 'standing answer')


NOTE_TEXT = guard_support.NOTE


def sending_pass_1(job, data: bytes, user):
    """The pass-1 run a worker that died mid-send leaves (FINAL-V2 7.4's settled path): SENDING, its one exchange
    recorded succeeded with HTTP 200 and ``data``."""
    revision = job.revision
    request = adapter.build_extraction_request(revision.text, jobs._participant_pages(revision),
                                               jobs._participant_document(revision)[0])
    run = Run.objects.create(
        encounter=job.encounter, revision=revision, provider=interpretation.PROVIDER,
        adapter_version=interpretation.ADAPTER_VERSION_V2, request_sha256=request.canonical_sha256,
        request_body=request.body, contexts=list(request.contexts), state=Run.SENDING, sent=True,
        purpose=interpretation.PURPOSE, scope={'mode': 'replay'}, endpoint=WorldInterpreter.endpoint,
        requested_model=interpretation.MODEL, started_at=timezone.now(), authorization_ref=AUTH, requested_by=user)
    models.ProviderExchange.objects.create(
        run=run, turn=1, request_body=request.body, request_sha256=request.canonical_sha256, state='succeeded',
        http_status=200, response_bytes=data, response_sha256=hashlib.sha256(data).hexdigest(), usage=dict(V2_USAGE),
        response_id='synthetic-s6a', started_at=timezone.now(), finished_at=timezone.now())
    return run


def _retired_hits(observation) -> int:
    return sum(n for label in LABELS for key, n in observation.hits[label].items()
               if sentinel.kind_of(key) == sentinel.RETIRED)


class V2NewPathOnlyDatabaseTests(V2GuardCase):
    def test_every_generated_item_runs_on_v2_assessments_and_nothing_is_counted_under_any_label(self):
        matrix = Matrix(self)
        with sentinel.call_checks():
            world = V2World(self, matrix).run()
        encounters = list(models.Encounter.objects.all())
        self.assertEqual({str(item.pk) for item in encounters}, set(world.ids.values()))
        self.assertEqual({readers.label_of(item) for item in encounters}, {NEW})
        # over v2 assessments only (5.7 measure 8)
        self.assertEqual(set(models.Assessment.objects.values_list('engine_version', flat=True)),
                         {interpretation.ENGINE_VERSION_V2})
        self.assertEqual(matrix.missing(), [])
        self.assertEqual(matrix.unknown(), [])
        unsatisfied = sorted(name for name, found in matrix.satisfied().items() if not found)
        self.assertEqual(unsatisfied, sorted(V2_UNREACHED), 'a facet left unreached, or one V2_UNREACHED no longer '
                                                             'needs (it then leaves the list)')
        self.assertEqual(matrix.red(LABELS), [], matrix.report(LABELS))
        self.assertEqual([item.describe() for item in matrix.observations if _retired_hits(item)], [])
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())
        status = sentinel.status()
        self.assertEqual((status['state'], status['retired_armed']), ('ok', True))
        # pass 2 ran in it, and 5.7 measure 8's worlds were each observed
        ran = {(item.key[1], item.detail.get('mode')) for item in matrix.observations
               if item.key[0] == 'stage' and item.detail.get('state') == Job.SUCCEEDED}
        self.assertLessEqual({(jobs.INTERPRET, ''), (jobs.APPRAISE, ''), ('assess', 'first'), ('assess', 'final'),
                              ('assess', 'again'), ('astra_peer', ''), ('fable_peer', '')},
                             {(kind, mode or '') for kind, mode in ran})
        self.assertGreater(len(matrix.observations), 250)


class V2BesideLegacyRecordsTests(V2GuardCase):
    def test_zero_new_path_executions_beside_legacy_and_v1_rows_and_a_v1_row_never_under_new_path(self):
        matrix = Matrix(self)
        with sentinel.call_checks():
            world = V2World(self, matrix, legacy_rows=True).run()
        legacy = models.Encounter.objects.filter(pk__in=world.legacy_ids)
        self.assertEqual(legacy.count(), len(LegacyWorld.SCENARIOS))
        self.assertEqual({readers.label_of(item) for item in legacy}, {LEGACY})
        v1 = models.Encounter.objects.filter(pk__in=world.v1_ids)
        self.assertEqual(v1.count(), 1)
        self.assertEqual({readers.label_of(item) for item in v1}, {LEGACY})  # FINAL-V2 6.2: legacy_record
        self.assertEqual(matrix.missing(), [])
        self.assertEqual(sorted(name for name, found in matrix.satisfied().items() if not found), sorted(V2_UNREACHED))
        self.assertEqual(matrix.red((NEW,)), [], matrix.report((NEW,)))
        self.assertEqual(matrix.red((OTHER, UNSCOPED)), [], matrix.report((OTHER, UNSCOPED)))
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())
        lists = (('url', 'api/encounters'), ('url', 'api/session'), ('url', 'ops/api/encounters'))
        listed = [item for item in matrix.observations if item.key in lists]
        self.assertTrue(any(item.count(LEGACY) for item in listed))  # the old rows' own reads, as legacy_record
        # a v1 row is read as stored under legacy_record: its page, as the member reads it
        observation = matrix.observe(('url', guard_support.ENC), 'GET the v1 row',
                                     lambda: world.member.get(f'/api/encounters/{world.v1_ids[0]}'), tag='v1')[1]
        self.assertEqual((observation.count(NEW), observation.count((OTHER, UNSCOPED))), (0, 0), observation.describe())


class V2PositiveControlTests(V2GuardCase):
    def test_the_matrix_turns_red_for_each_class_under_each_label_it_judges(self):
        from studio.interpretation import lexicon, literals

        matrix = Matrix(self)
        world = V2World(self, matrix)
        with sentinel.call_checks():
            pk = world.v2_upload('E1')
            world.drain('E1')
            clean = len(matrix.observations)

            def planted(target, name, call):
                real = getattr(target, name)

                def run(*args, **kwargs):
                    call()
                    return real(*args, **kwargs)

                return mock.patch.object(target, name, side_effect=run)

            def legacy_twice():
                structure._course_start.cache_clear()
                structure._course_start()
                structure._course_start()  # a hit: only the CALL check sees it

            def retired_twice():
                lexicon._compiled.cache_clear()
                lexicon._compiled(('no',))
                lexicon._compiled(('no',))  # a hit of a retired cache: only the CALL check sees it

            with planted(customer_api, 'encounter_json', lambda: cues.page_number_line('3')):
                world.detail('E1', tag='a gi function')  # a request naming a new-path encounter: new_path, code
            with planted(customer_api, 'session_json', lambda: cues.PAGE_NUMBER_LINE.search('3')):
                world.get('/api/session', tag='a legacy regex')  # a request naming none: other, regex
            with planted(review, 'refresh_state', legacy_twice):
                world.matrix.script('RECOMPUTE_STATES', {}, tag='a legacy cache')  # a script: unscoped, cache
            with planted(customer_api, 'encounter_json', lambda: lexicon.negation('no')):
                world.detail('E1', tag='a retired function')  # new_path, the RETIRED kind's code
            with planted(customer_api, 'session_json', retired_twice):
                world.get('/api/session', tag='a retired cache')  # other, the RETIRED kind's cache
            # the RETIRED kind's regex class (refutation 6a-r1 F7): a retired module's pattern read on a request naming a
            # new-path encounter, and in a script
            with planted(customer_api, 'encounter_json', lambda: literals.SIZE.search('A 6 mm polyp')):
                world.detail('E1', tag='a retired regex')  # new_path, the RETIRED kind's regex
            with planted(review, 'refresh_state', lambda: literals.SIZE.search('A 6 mm polyp')):
                world.matrix.script('RECOMPUTE_STATES', {}, tag='a retired regex in a script')  # unscoped, regex
            world.post(f'/api/encounters/{pk}/context', {'setting': 'asc'}, tag='a re-check')
            with planted(jobs, '_retrieval', lambda: lexicon.negation('no')):
                world.drain('a retired function in a stage', expect=None)  # a stage: new_path (its gate refuses)
        self.assertEqual([item for item in matrix.observations[:clean] if item.count(LABELS)], [])  # clean before
        expected = (('a gi function', NEW, CODE, sentinel.LEGACY, 'studio/gi/cues.py'),
                    ('a legacy regex', OTHER, REGEX, sentinel.LEGACY, 'studio.gi.cues.PAGE_NUMBER_LINE'),
                    ('a legacy cache', UNSCOPED, CACHE, sentinel.LEGACY, 'studio.gi.structure._course_start (cache)'),
                    ('a retired function', NEW, CODE, sentinel.RETIRED, 'studio/interpretation/lexicon.py'),
                    ('a retired cache', OTHER, CACHE, sentinel.RETIRED, 'studio.interpretation.lexicon._compiled (cache)'),
                    ('a retired regex', NEW, REGEX, sentinel.RETIRED, 'studio.interpretation.literals.SIZE'),
                    ('a retired regex in a script', UNSCOPED, REGEX, sentinel.RETIRED,
                     'studio.interpretation.literals.SIZE'),
                    ('a retired function in a stage', NEW, CODE, sentinel.RETIRED, 'studio/interpretation/lexicon.py'))
        for tag, label, kind, family, named in expected:
            with self.subTest(planted=tag):
                found = [item for item in matrix.observations if item.tag.endswith(tag) and item.count(LABELS)]
                self.assertTrue(found, tag)
                red = found[0]
                self.assertGreater(red.count(label), 0, red.describe())
                self.assertGreater(red.kinds(label)[kind], 0, red.describe())
                self.assertTrue(any(sentinel.kind_of(key) == family for key in red.hits[label]), red.describe())
                self.assertIn(named, red.describe())
                self.assertIn(red, matrix.red(LABELS))
        report = matrix.report((NEW,))
        self.assertRegex(report, r'studio/gi/cues\.py:\d+ page_number_line')
        self.assertRegex(report, r'studio/interpretation/lexicon\.py:\d+ negation')
        self.assertIn('entered: ', report)
        self.assertTrue(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())  # the stage's gate refused


class U15Tests(V2GuardCase):
    """AMENDMENT-1 11.1 U15 (A14, A17): a legacy encounter (the test-only legacy chain) updated after a save."""

    def legacy(self, world):
        pk = world.legacy_upload('L15')
        encounter = models.Encounter.objects.get(pk=pk)
        self.assertFalse(interpretation.is_new_assessment(encounter.current_assessment))
        self.assertFalse(models.EventInventory.objects.filter(encounter=encounter).exists())
        return pk, encounter.current_assessment

    def page(self, matrix, world, pk, tag):
        response, observation = matrix.observe(('url', guard_support.ENC), f'GET the page ({tag})',
                                               lambda: world.member.get(f'/api/encounters/{pk}'), tag=tag)
        self.assertEqual(response.status_code, 200, response.content[:400])
        return response.json(), observation

    def test_the_page_while_assess_1_is_recorded_and_with_the_label_forced_to_new_path(self):
        matrix = Matrix(self)
        world = V2World(self, matrix)
        with sentinel.call_checks():
            pk, legacy = self.legacy(world)
            world.post(f'/api/encounters/{pk}/context', {'setting': 'office'}, tag='L15 save')
            with participants():
                world.drain('L15 update', until='assess')  # assess #1 of the update: it owes the peer stages
            encounter = models.Encounter.objects.get(pk=pk)
            update = models.Assessment.objects.filter(encounter_id=pk).exclude(pk=legacy.pk)
            self.assertTrue(update.exists())  # recorded ...
            self.assertEqual(encounter.current_assessment_id, legacy.pk)  # ... never current (A17)
            payload, labelled = self.page(matrix, world, pk, 'as labelled')
            self.assertTrue(payload['update']['pending'])
            self.assertTrue(payload['earlier_codes'])
            with mock.patch.object(readers, '_label', return_value=NEW):  # the relabel guard (A14)
                self.assertEqual(readers.label_of(encounter), NEW)
                forced_payload, forced = self.page(matrix, world, pk, 'forced to new_path')
        self.assertTrue(forced_payload['earlier_codes'])
        self.assertEqual(labelled.count(NEW), 0, labelled.describe())
        self.assertEqual(forced.count(NEW), 0, forced.describe())  # 0 legacy executions while the earlier codes drawn
        self.assertGreater(forced.count(LEGACY), 0, forced.describe())  # drawn under their own label
        self.assertEqual(forced.errors, 0)

    def test_an_update_pending_on_a_legacy_encounter_and_a_completed_updates_what_changed_read(self):
        matrix = Matrix(self)
        world = V2World(self, matrix)
        with sentinel.call_checks():
            pk, legacy = self.legacy(world)
            world.post(f'/api/encounters/{pk}/context', {'setting': 'office'}, tag='L15 save')
            pending = len(matrix.observations)
            world.reads_of(pk, 'pending')
            during = matrix.observations[pending:]
            world.drain('L15 update')
            completed = len(matrix.observations)
            payload, read = self.page(matrix, world, pk, 'completed')
            world.reads_of(pk, 'completed')
            after = matrix.observations[completed:]
        encounter = models.Encounter.objects.get(pk=pk)
        self.assertEqual(encounter.current_assessment.engine_version, interpretation.ENGINE_VERSION_V2)
        self.assertIsNotNone(payload['what_changed'])
        self.assertEqual([item for item in during if item.count((NEW, OTHER, UNSCOPED)) or item.errors], [],
                         '\n'.join(item.describe() for item in during))
        self.assertEqual([item for item in after if item.count(LABELS) or item.errors], [],
                         '\n'.join(item.describe() for item in after))
        self.assertEqual(readers.label_of(encounter), NEW)
