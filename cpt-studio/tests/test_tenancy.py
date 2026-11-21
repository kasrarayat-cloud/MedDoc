"""Tenancy (FG-4; BUILD-SPEC sections 6 and 12, studio/access.py): a member reaches only the workspaces where their
membership is ACTIVE, and anything else answers 404 - never 403, never 409 - on every endpoint family: the page, the
session, the list and the upload, the encounter, its answers, decisions, stop, resume and retry, its exports, its
original and its in-page view, an export's download, and the operator console. Three ways to be outside: a member of
another workspace; a member whose membership is deactivated while signed in (the same session goes on); a member who is
inactive in this workspace and active in another. Every 404 has its positive control - the same request, from an
active reviewer, answers what the view answers - so a broken door and a closed one cannot read the same; and a refused
request changes nothing.

LINE IDENTITY (FIX-SPEC section 1): a decision names the round shown and the line ({round, line, code, action,
acknowledgement, note}), and an export the round shown ({kind, fmt, round}; FIX-SPEC-2 section 5); tenancy answers 404
before the round or the line is read, so a stale round or an unknown line of another workspace's encounter reveals
nothing. The assertion that reads the stored line (CodeDecision.line, lane
F1a's migration 0016) is skipped until that field exists.

Synthetic data only; the coding review is a fake coder (tests.support), nothing reaches the network."""
import json
from datetime import timedelta

from django.test import Client, TestCase, override_settings

from studio import decisions, models
from tests.support import coding as f
from tests.support import operator as ops
from tests.support import rounds as r
from tests.test_frontend import PLAIN_STATIC

READS = ('session', 'list', 'encounter', 'original', 'view', 'download')
# in an order the positive controls can run in one after another: the answers, which start a new round, last
WRITES = ('upload', 'decisions', 'reports', 'stop', 'resume', 'retry', 'answers')
# What each write answers an ACTIVE reviewer on a done round (the positive control): the view runs
WRITE_STATUS = {'upload': 201, 'answers': 201, 'decisions': 201, 'stop': 409, 'resume': 409, 'retry': 409,
                'reports': 201}
COUNTED = (models.Encounter, models.SourceRevision, models.CodingRound, models.CodingAnswer, models.CodeDecision,
           models.ExportArtifact, models.Job)
HAS_LINE = any(field.name == 'line' for field in models.CodeDecision._meta.get_fields())


@override_settings(STORAGES=PLAIN_STATIC)  # the page and the sign-in page are rendered
class TenancyCase(r.CustomerCase, TestCase):
    def setUp(self):
        super().setUp()
        self.enc = self.done()  # round 1 done: ready codes, a question, quotes
        reviewer = self.client_for(self.reviewer)
        self.payload = reviewer.get(f'/api/encounters/{self.enc.pk}').json()
        export = reviewer.post(f'/api/encounters/{self.enc.pk}/reports',
                               data=json.dumps({'kind': 'draft', 'fmt': 'pdf', 'round': self.payload['round']['number']}),
                               content_type='application/json')
        self.assertEqual(export.status_code, 201)
        self.download_url = export.json()['download_url']

    def ready_line(self):
        """The first READY row: its code and line (FIX-SPEC section 1: reader rows are L1..Ln in the reader's order)."""
        for index, row in enumerate(self.payload['codes']):
            if row['status'] == 'ready' and 'approve' in row['allowed_actions']:
                return row['code'], row.get('line') or f'L{index + 1}'
        raise AssertionError('no ready row')

    def bodies(self):
        code, line = self.ready_line()
        return {
            'answers': {'answers': [{'question_id': self.payload['questions'][0]['id'],
                                     'text': 'Yes, at a separate site.'}]},
            'decisions': {'round': self.payload['round']['number'], 'line': line, 'code': code, 'action': 'approve',
                          'acknowledgement': decisions.ACKNOWLEDGEMENTS['human'], 'note': 'synthetic tenancy test'},
            'stop': {}, 'resume': {}, 'retry': {},
            'reports': {'kind': 'draft', 'fmt': 'pdf', 'round': self.payload['round']['number']}}

    def read(self, client, name):
        url = {'session': '/api/session', 'list': '/api/encounters', 'encounter': f'/api/encounters/{self.enc.pk}',
               'original': f'/api/encounters/{self.enc.pk}/original',
               'view': f'/api/encounters/{self.enc.pk}/original?view=1', 'download': self.download_url}[name]
        return client.get(url)

    def write(self, client, name):
        if name == 'upload':
            return client.post('/api/encounters', {'text': f.NOTE, 'synthetic_attestation': 'yes', 'title': 'Tenancy'})
        return client.post(f'/api/encounters/{self.enc.pk}/{name}', data=json.dumps(self.bodies()[name]),
                           content_type='application/json')

    def counts(self):
        return {model.__name__: model.objects.count() for model in COUNTED}

    def operator_doors(self, client):
        """Every operator URL, answered to ``client``: {path: status}."""
        found = {}
        for path in ('/ops/', f'/ops/encounters/{self.enc.pk}', f'/ops/encounters/{self.enc.pk}/original'):
            found[path] = client.get(path).status_code
        for path in (f'/ops/encounters/{self.enc.pk}/reconcile', f'/ops/encounters/{self.enc.pk}/retry',
                     '/ops/holds/release'):
            found[path] = client.post(path, {'note': 'synthetic tenancy test of the operator gate'}).status_code
        return found

    def assert_outside(self, client, *, upload_lands_elsewhere=False):
        """Every customer endpoint family of this workspace answers ``client`` 404 and changes nothing; the encounter's
        id is in no answer."""
        before = self.counts()
        for name in READS:
            with self.subTest(read=name):
                response = self.read(client, name)
                if name in ('session', 'list') and upload_lands_elsewhere:
                    self.assertEqual(response.status_code, 200)  # their own workspace's session and list
                else:
                    self.assertEqual(response.status_code, 404, response.content[:200])
                self.assertNotIn(str(self.enc.pk).encode(), response.content)
        for name in WRITES:
            if name == 'upload' and upload_lands_elsewhere:
                continue  # an upload goes to the caller's own active workspace (test below)
            with self.subTest(write=name):
                response = self.write(client, name)
                self.assertEqual(response.status_code, 404, response.content[:200])
        self.assertEqual(self.counts(), before)
        # no decision reached the rows, as another active reviewer of the workspace reads them
        self.assertEqual(self.client_for(self.agent).get(f'/api/encounters/{self.enc.pk}').json()['codes'],
                         self.payload['codes'])


class InactiveMembershipTests(TenancyCase):
    def test_a_member_deactivated_while_signed_in_reaches_nothing_in_the_same_session(self):
        client = self.client_for(self.reviewer)
        for name in READS:  # the positive control: the session reads everything while the membership is active
            with self.subTest(control=name):
                self.assertEqual(self.read(client, name).status_code, 200)
        self.assertEqual(client.get('/').status_code, 200)
        models.Membership.objects.filter(user=self.reviewer, workspace=self.ws).update(active=False)
        self.assertEqual(client.get('/').status_code, 404)
        self.assert_outside(client)
        # the same requests from the same session, once the membership is active again: every view runs
        models.Membership.objects.filter(user=self.reviewer, workspace=self.ws).update(active=True)
        for name in WRITES:
            with self.subTest(control=name):
                self.assertEqual(self.write(client, name).status_code, WRITE_STATUS[name])

    def test_a_member_inactive_here_and_active_elsewhere_sees_only_the_other_workspace(self):
        active = models.Membership.objects.get(user=self.outsider, workspace=self.other_ws)
        inactive = models.Membership.objects.create(user=self.outsider, workspace=self.ws,
                                                    role=models.Membership.REVIEWER, active=False)
        # the membership the member was removed from is the OLDER one (FG-4 residue): the session and the list land on
        # the oldest active membership, so a door that took the oldest membership whatever its state would land here
        models.Membership.objects.filter(pk=inactive.pk).update(created_at=active.created_at - timedelta(hours=1))
        self.assertEqual(list(models.Membership.objects.filter(user=self.outsider).order_by('created_at')
                              .values_list('workspace_id', 'active')), [(self.ws.pk, False), (self.other_ws.pk, True)])
        client = Client()
        signed_in = client.post('/login/', {'username': self.outsider.username, 'password': 'synthetic-pass-123!'})
        self.assertEqual(signed_in.status_code, 302)
        session = client.get('/api/session').json()
        self.assertEqual(session['workspace']['id'], str(self.other_ws.pk))
        self.assertNotIn(str(self.enc.pk), json.dumps(client.get('/api/encounters').json()))
        self.assert_outside(client, upload_lands_elsewhere=True)
        uploaded = self.write(client, 'upload')
        self.assertEqual(uploaded.status_code, 201)
        self.assertEqual(models.Encounter.objects.get(pk=uploaded.json()['id']).workspace_id, self.other_ws.pk)

    def test_a_member_with_no_active_membership_cannot_sign_in_and_a_session_reads_nothing(self):
        models.Membership.objects.filter(user=self.viewer).update(active=False)
        refused = Client().post('/login/', {'username': self.viewer.username, 'password': 'synthetic-pass-123!'})
        self.assertEqual(refused.status_code, 400)
        client = self.client_for(self.viewer)  # a session from before the deactivation
        self.assertEqual(client.get('/').status_code, 404)
        self.assertEqual(self.read(client, 'session').status_code, 404)
        self.assertEqual(self.read(client, 'list').status_code, 404)
        self.assertEqual(self.write(client, 'upload').status_code, 404)

    def test_an_inactive_account_is_signed_out_of_every_family(self):
        client = self.client_for(self.reviewer)
        models.User.objects.filter(pk=self.reviewer.pk).update(is_active=False)
        for name in READS:
            with self.subTest(read=name):
                self.assertIn(self.read(client, name).status_code, (401, 404))
        for name in WRITES:
            with self.subTest(write=name):
                self.assertIn(self.write(client, name).status_code, (401, 404))


class OtherWorkspaceTests(TenancyCase):
    def test_every_endpoint_family_of_another_workspace_answers_404(self):
        self.assert_outside(self.client_for(self.outsider), upload_lands_elsewhere=True)

    def test_the_operator_console_answers_404_to_every_member_and_200_to_an_operator(self):
        inactive = self.client_for(self.viewer)
        models.Membership.objects.filter(user=self.viewer).update(active=False)
        for who, client in (('reviewer', self.client_for(self.reviewer)), ('outsider', self.client_for(self.outsider)),
                            ('inactive', inactive)):
            with self.subTest(who=who):
                self.assertEqual(set(self.operator_doors(client).values()), {404})
        operator = ops.client(f.user('synthetic-operator'))  # the positive control: the gate opens for a grant
        self.assertEqual(operator.get('/ops/').status_code, 200)
        self.assertEqual(operator.get(f'/ops/encounters/{self.enc.pk}').status_code, 200)

    def test_line_identity_a_stale_round_or_unknown_line_of_another_workspace_reveals_nothing(self):
        # tenancy answers before the round or the line is read: the same 404 for the round shown, a stale round, an
        # unknown line and a code that differs - never the 409 a member of the workspace would read
        outsider = self.client_for(self.outsider)
        code, line = self.ready_line()
        body = self.bodies()['decisions']
        for changed in ({}, {'round': body['round'] + 1}, {'line': 'L99'}, {'code': '99999'}, {'line': line,
                                                                                               'code': code}):
            with self.subTest(changed=changed):
                response = outsider.post(f'/api/encounters/{self.enc.pk}/decisions',
                                         data=json.dumps({**body, **changed}), content_type='application/json')
                self.assertEqual((response.status_code, response.json()), (404, {'error': 'Not found.'}))
        self.assertEqual(models.CodeDecision.objects.count(), 0)

    def test_line_identity_the_reviewers_decision_is_stored_on_the_line_it_names(self):
        if not HAS_LINE:
            self.skipTest('CodeDecision has no line yet (FIX-SPEC section 1, lane F1a): run after the merge')
        code, line = self.ready_line()
        response = self.write(self.client_for(self.reviewer), 'decisions')
        self.assertEqual(response.status_code, 201, response.content[:300])
        stored = models.CodeDecision.objects.get()
        self.assertEqual((stored.code, stored.line, stored.round.number), (code, line, self.payload['round']['number']))
