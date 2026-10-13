from copy import deepcopy
import importlib
from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import connection, DatabaseError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from core import testing_authority as authority
from core.models import Department, Encounter, Membership, Organization, Patient, Template, TemplateVersion, User, Job
from core.tests.test_testing_authority import SETTINGS

migration=importlib.import_module('core.migrations.0027_cedar_synthetic_clinician')

@override_settings(**SETTINGS)
class CedarEnrollmentTests(TestCase):
    def setUp(self):
        self.actor=User.objects.create_user(id=migration.ACTOR,username='cedar-fixture',email='cedar@synthetic.invalid',verified_at=timezone.now())
        self.department=Department.objects.create(id=migration.DEPARTMENT,organization=Organization.objects.create(name='Synthetic clinic'),name='X-ray')
        Membership.objects.create(user=self.actor,department=self.department,role='clinician')
        self.base=authority.active_config({'mode':'live','provider':'anthropic','model':SETTINGS['AI_MODEL']},'generation')
        self.config=authority.bind_actor_config(self.base,self.actor,self.department.pk)

    def test_actual_postgresql_actor_and_installed_function_bodies(self):
        self.assertEqual(self.config[authority.ACTOR_ENROLLMENT_KEY],migration.ENROLLMENT)
        self.assertTrue(authority.runtime_admission(self.actor,self.department.pk)['admitted'])
        for actor,department,marker in [(migration.ACTOR,migration.DEPARTMENT,None),
                (migration.ACTOR,migration.DEPARTMENT,authority.ACTOR_ENROLLMENT),
                (authority.ENROLLED_ACTOR,migration.DEPARTMENT,migration.ENROLLMENT),
                (migration.ACTOR,str(self.department.organization_id),migration.ENROLLMENT)]:
            config={**self.config,authority.ACTOR_ENROLLMENT_KEY:marker}
            with self.subTest(actor=actor,marker=marker),self.assertRaises(DatabaseError),transaction.atomic():
                with connection.cursor() as cursor:
                    import json
                    cursor.execute('SELECT quillmd_standing_actor(%s::uuid,%s::uuid,%s::jsonb)',[actor,department,json.dumps(config)])

    def test_cross_actor_configuration_is_never_relabelled(self):
        old={**self.base,authority.ACTOR_ENROLLMENT_KEY:authority.ACTOR_ENROLLMENT};snapshot=deepcopy(old)
        with self.assertRaises(ValidationError):authority.bind_actor_config(old,self.actor,self.department.pk)
        self.assertEqual(old,snapshot)
        self.assertNotIn(authority.ACTOR_ENROLLMENT_KEY,self.base)

    def test_database_refuses_sponsoring_another_clinicians_encounter(self):
        other=User.objects.create_user(username='other-enrollment',verified_at=timezone.now())
        patient=Patient.objects.create(department=self.department,created_by=other,display_name='Synthetic other')
        template=Template.objects.create(department=self.department,created_by=other,name='Synthetic blank',format='pdf',sha256='a'*64)
        version=TemplateVersion.objects.create(template=template,created_by=other,number=1)
        encounter=Encounter.objects.create(patient=patient,department=self.department,created_by=other,template_version=version,service_date=timezone.localdate())
        config={**self.config,'testing_quote_usd':'1.000000000000'}
        with self.assertRaises(DatabaseError),transaction.atomic():
            Job.objects.create(encounter=encounter,user=self.actor,request_key='foreign-document',config=config)
        encounter.created_by=self.actor;encounter.save()
        Job.objects.create(encounter=encounter,user=self.actor,request_key='own-document',config=config)
        self.assertEqual(Job.objects.count(),1)
