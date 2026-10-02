"""Optional role rows never take the ordinary response's capped output room."""
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from core import destination_roles, generation as g
from .test_destination_roles import LIVE


@override_settings(**LIVE)
class RoleOutputRoom(SimpleTestCase):
    def build(self, notes):
        role={'key':'role','label':'Troponin (initial)','kind':'text',
              'destination_role':{'reason':destination_roles.ROLE_NOT_GENERATED,'suggest':True}}
        form=[{'key':'plan','label':'Plan','kind':'text'},role]
        asked,context,v3=g.v3_generation_fields(form)
        config={**g.configuration(form),'role_suggestion_contract':g.ROLE_SUGGESTION_CONTRACT}
        plain=g.extractive_request(notes,asked,context,config,v3)
        return form,config,plain,v3

    def test_optional_rows_are_dropped_when_complete_output_would_not_fit(self):
        form,config,plain,v3=self.build('Plan: Rest.\nTroponin (initial): 14 ng/L')
        full=g.extractive_request('Plan: Rest.\nTroponin (initial): 14 ng/L',form,
                                 plain['payload']['context_labels'],config,v3)
        cap=g.role_response_bound(full)-1
        profile={**g.job_request_profile(config),'max_output_tokens':cap,'thinking':None}
        with patch('core.generation.job_request_profile',return_value=profile):
            suggested,asked,request=g.role_request('Plan: Rest.\nTroponin (initial): 14 ng/L',form,(),config,v3,plain,{'role'})
        self.assertEqual(suggested,frozenset())
        self.assertEqual(g.request_bytes(request),g.request_bytes(plain))
        self.assertEqual([f['key'] for f in asked],['plan'])

    def test_thinking_has_headroom_and_optional_rows_fit_when_room_exists(self):
        notes='Plan: Rest.\nTroponin (initial): 14 ng/L'
        form,config,plain,v3=self.build(notes)
        full=g.extractive_request(notes,form,plain['payload']['context_labels'],config,v3)
        bound=g.role_response_bound(full)
        profile={**g.job_request_profile(config),'max_output_tokens':bound+1,'thinking':{'type':'adaptive'}}
        with patch('core.generation.job_request_profile',return_value=profile):
            suggested,_,request=g.role_request(notes,form,(),config,v3,plain,{'role'})
        self.assertFalse(suggested)
        self.assertEqual(g.request_bytes(request),g.request_bytes(plain))
        profile['max_output_tokens']=2*bound
        with patch('core.generation.job_request_profile',return_value=profile):
            suggested,_,request=g.role_request(notes,form,(),config,v3,plain,{'role'})
        self.assertEqual(suggested,frozenset({'role'}))
        self.assertEqual(g.request_bytes(request,suggested),g.request_bytes(plain))
