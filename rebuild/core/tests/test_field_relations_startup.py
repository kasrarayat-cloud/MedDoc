"""The effective ordinary-notes contract comes from real service settings.

Fresh processes use only synthetic settings; no database or provider send.
"""
import json
from django.test import SimpleTestCase
from .test_v1_data_mode import start, COMPLETE_REAL


class FieldRelationsStartup(SimpleTestCase):
    expression = ('{"switch": s.V3_FIELD_RELATIONS_SWITCH, "flag": s.V3_FIELD_RELATIONS, '
                  '"model": s.AI_MODEL, "effective": '
                  '__import__("core.generation", fromlist=["field_relations_enabled"]).field_relations_enabled()}')

    def test_actual_synthetic_service_default_and_explicit_choices(self):
        for model, switch, expected in [('claude-sonnet-5-5', None, True),
                ('claude-sonnet-5-5', '', True), ('claude-sonnet-5-5', '0', False),
                ('claude-sonnet-5-5', '1', True), ('claude-sonnet-5', None, False),
                ('claude-sonnet-4-6', None, False)]:
            env={'DJANGO_SETTINGS_MODULE':'quillmd.settings','QUILLMD_AI_MODEL':model}
            if switch is not None:env['QUILLMD_V3_FIELD_RELATIONS']=switch
            with self.subTest(model=model,switch=switch):
                result=start(env,self.expression)
                self.assertEqual(result.returncode,0,result.stderr)
                found=json.loads(result.stdout)
                self.assertEqual(found['model'],model)
                self.assertEqual(found['effective'],expected)
                self.assertEqual(found['switch'],None if not switch else switch=='1')
                self.assertEqual(found['flag'],switch=='1')

    def test_invalid_switch_refuses_at_start_and_real_mode_stays_explicit(self):
        for value in ['true','on','2','yes']:
            with self.subTest(value=value):
                result=start({'QUILLMD_V3_FIELD_RELATIONS':value})
                self.assertNotEqual(result.returncode,0)
                self.assertIn('QUILLMD_V3_FIELD_RELATIONS',result.stderr)
        result=start({**COMPLETE_REAL,'QUILLMD_AI_MODEL':'claude-sonnet-5-5'})
        self.assertNotEqual(result.returncode,0)
        self.assertIn("QUILLMD_V3_FIELD_RELATIONS must be set to '0' or '1'",result.stderr)
