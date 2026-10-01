"""Finite compact-envelope boundary checks. Pure synthetic metadata; no document corpus."""
import copy
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from core import mapping_wire as wire, generation

class MappingWire(SimpleTestCase):
    def payload(self,count=2,fields=1):
        payload={'slots':[{'slot':f'word/document.xml#body/p[{n}]','text':'🏥 Plan: rest','heading':'Clinical form','row_label':'Plan','options':['Yes','No','Maybe','Unknown']} for n in range(count)],
                 'fields':[{'key':f'f{n}','label':'Plan','kind':'text','slots':[f'word/document.xml#body/p[{n}]'],'options':[]} for n in range(fields)]}
        payload['text_refs']=wire.catalog(payload)
        return payload

    def target(self,payload,sid=0,fid=-1):
        ref=payload['text_refs'].index([sid,0,0])
        return [fid,sid,0,ref,2,6,-1]

    def test_complete_long_label_spans_and_target_schema_share_the_limit(self):
        from core.mapping_assistance import Target
        for length in (334, 409, 1000, 1001):
            payload = self.payload(1, 0)
            label = ('🏥' if length >= 1000 else 'Q') * length
            payload['slots'][0]['text'] = label
            payload['text_refs'] = wire.catalog(payload)
            body = wire.fixture(payload)
            body['x'] = [[-1, 0, 1, payload['text_refs'].index([0, 0, 0]), 0, length, -1]]
            target = dict(slot=payload['slots'][0]['slot'], kind='long_text', label=label, options=[], glyph=None)
            with self.subTest(length=length):
                if length <= 1000:
                    expanded, _ = wire.expand(payload, body)
                    self.assertEqual(expanded['additions'][0]['label'], label)
                    self.assertEqual(Target.model_validate(target).label, label)
                else:
                    # An over-long label is ONE invalid change: held with its reason, never truncated, never adopted.
                    expanded, _ = wire.expand(payload, body)
                    self.assertEqual(expanded['additions'], [])
                    self.assertEqual([row['reason'] for row in expanded['rejected']],
                                     ['Invalid Unicode source span; source text was not truncated.'])
                    with self.assertRaises(ValueError): Target.model_validate(target)

    def test_minimum_empty_complete_and_unicode_source_expansion(self):
        payload=self.payload(0,0)
        result,exhausted=wire.expand(payload,wire.fixture(payload))
        self.assertEqual({k:result[k] for k in ('fields','slots','additions','rejected')},
                         {'fields':[],'slots':[],'additions':[],'rejected':[]});self.assertFalse(exhausted)
        payload=self.payload();body=wire.fixture(payload);body['x']=[self.target(payload,1)]
        result,_=wire.expand(payload,body)
        self.assertEqual(result['additions'][0]['label'],'Plan')
        self.assertEqual(result['additions'][0]['slot'],payload['slots'][1]['slot'])

    def test_maximum_complete_changes_options_and_exhaustion_are_not_truncated(self):
        payload=self.payload(1200,200);body=wire.fixture(payload)
        body['f']['k']=list(range(100));body['f']['r']=list(range(100,200))
        for fid in range(100,200):
            change=self.target(payload,fid,fid)
            for n,option in enumerate(payload['slots'][fid]['options']):
                change.extend([payload['text_refs'].index([fid,3,n]),0,len(option)])
            body['x'].append(change)
        result,exhausted=wire.expand(payload,body)
        self.assertEqual(len(result['slots']),1200);self.assertEqual(len(result['fields']),200)
        replacements=[f['target'] for f in result['fields'] if f['verdict']=='replace']
        self.assertEqual(len(replacements),100);self.assertEqual(sum(len(t['options']) for t in replacements),400)
        self.assertFalse(exhausted)
        body['e']=True;self.assertTrue(wire.expand(payload,body)[1])
        body['x'][0].extend(body['x'][0][-3:])
        with self.assertRaises(ValidationError):wire.expand(payload,body)

    def test_disjoint_groups_and_strict_numeric_ids(self):
        payload=self.payload();good=wire.fixture(payload)
        candidates=[]
        for group,code in [('f','k'),('s','u')]:
            for value in [[True],[False],[-1],[1200],[0,0],['0'],[5]]:
                body=copy.deepcopy(good);body[group][code]=value;candidates.append(body)
        body=copy.deepcopy(good);body['f']['u']=[0];candidates.append(body)
        body=copy.deepcopy(good);body['s']['n']=[0];candidates.append(body)
        for body in candidates:
            with self.subTest(body=body),self.assertRaises((ValidationError,ValueError)):wire.expand(payload,body)

    def test_an_omitted_field_or_slot_is_held_uncertain_not_refused(self):
        """Campaign attempt 24: the model left eleven checkbox slots of one form unclassified and the whole proposal was
        refused. An OMITTED ID is held `uncertain` (never a target, never adopted); the rest of the proposal stands."""
        payload=self.payload(4,2);good=wire.fixture(payload)
        body=copy.deepcopy(good)
        body['s']={'c':[0],'n':[],'u':[]}                       # slots 1, 2 and 3 omitted
        body['f']={'k':[1],'r':[],'n':[],'u':[]}                # field 0 omitted
        body['x']=[self.target(payload,2)]                       # a valid addition on an omitted slot
        result,_=wire.expand(payload,body)
        self.assertEqual([(s['slot'],s['verdict']) for s in result['slots']],
                         [(payload['slots'][0]['slot'],'covered')]+[(payload['slots'][n]['slot'],'uncertain') for n in (1,2,3)])
        self.assertEqual([(f['key'],f['verdict'],f['target']) for f in result['fields']],
                         [('f0','uncertain',None),('f1','keep',None)])
        self.assertEqual([a['slot'] for a in result['additions']],[payload['slots'][2]['slot']])
        self.assertEqual(result['rejected'],[])

    def test_spans_refuse_foreign_context_wrong_destination_and_invalid_unicode_bounds(self):
        """⚠️ ONE INVALID CHANGE IS HELD WITH ITS REASON; IT NEVER REFUSES THE REST (M05). Each bad change below comes
        back in `rejected` beside a valid change that is still expanded; a replacement's field is held `uncertain`."""
        payload=self.payload(2,2);good=wire.fixture(payload)
        target=self.target(payload)
        changes=[]
        for index,value in [(1,1),(3,399999),(4,-1),(5,999),(5,2),(6,200),(2,9)]:
            bad=target.copy();bad[index]=value;changes.append(bad)
        # A field label reference cannot be used as an addition or in another field.
        for fid in [-1,1]:
            bad=self.target(payload,0,fid);bad[3]=payload['text_refs'].index([0,4,0]);bad[4:6]=[0,4];changes.append(bad)
        valid=self.target(payload,1)
        for bad in changes:
            body=copy.deepcopy(good);body['x']=[bad,valid]
            if bad[0]>=0:body['f']['k'].remove(bad[0]);body['f']['r']=[bad[0]]
            with self.subTest(change=bad):
                expanded,_=wire.expand(payload,body)
                self.assertEqual([row['change'] for row in expanded['rejected']],[0])
                self.assertEqual(expanded['rejected'][0]['wire'],bad)
                self.assertTrue(expanded['rejected'][0]['reason'])
                self.assertEqual([a['slot'] for a in expanded['additions']],[payload['slots'][1]['slot']])
                if bad[0]>=0:
                    held=next(f for f in expanded['fields'] if f['key']==payload['fields'][bad[0]]['key'])
                    self.assertEqual((held['verdict'],held['target']),('uncertain',None))
        # The ENVELOPE still refuses the whole response: a catalog that differs from the bound request.
        payload['text_refs'][0][0]=1
        with self.assertRaises(ValidationError):wire.expand(payload,good)

    def test_replacement_ownership_is_complete_and_unique(self):
        payload=self.payload();body=wire.fixture(payload)
        body['f']['k']=[];body['f']['r']=[0]
        # A replace verdict without its change: the field is held uncertain and recorded, nothing else is refused.
        expanded,_=wire.expand(payload,body)
        self.assertEqual((expanded['fields'][0]['verdict'],expanded['fields'][0]['target']),('uncertain',None))
        self.assertEqual([r['reason'] for r in expanded['rejected']],['A replacement verdict lacks its bound change.'])
        body['x']=[self.target(payload,0,0)]
        self.assertEqual(wire.expand(payload,body)[0]['fields'][0]['target']['label'],'Plan')
        # Two changes for one field: neither owns it uniquely; both are held, the field is held.
        body['x']*=2
        expanded,_=wire.expand(payload,body)
        self.assertEqual([r['change'] for r in expanded['rejected']],[0,1])
        self.assertEqual(expanded['fields'][0]['verdict'],'uncertain')
        # An incomplete option triple is an ENVELOPE violation: the whole response refuses.
        body['x']=[self.target(payload,0,0)+[0]]
        with self.assertRaises(ValidationError):wire.expand(payload,body)
        # So is a change naming a field the request does not contain.
        body['x']=[self.target(payload,0,5)]
        with self.assertRaises(ValidationError):wire.expand(payload,body)

    def test_legacy_and_clinical_generation_profiles_are_unchanged(self):
        self.assertEqual(generation.request_profile('anthropic','claude-sonnet-5','disabled','medium','')['max_output_tokens'],8000)
        self.assertEqual(generation.request_profile('anthropic','claude-sonnet-5','adaptive','medium','')['max_output_tokens'],16000)
        self.assertEqual(generation.request_profile('anthropic','claude-sonnet-4-6','disabled','medium',''),generation.LEGACY_PROFILE)

    def test_change_and_per_change_option_limits_and_boolean_exhaustion_are_strict(self):
        payload=self.payload();good=wire.fixture(payload)
        candidates=[]
        body=copy.deepcopy(good);body['x']=[self.target(payload)]*101;candidates.append(body)
        body=copy.deepcopy(good);body['x']=[self.target(payload)+[0,0,1]*101];candidates.append(body)
        for value in ['false',0,1,None]:
            body=copy.deepcopy(good);body['e']=value;candidates.append(body)
        for body in candidates:
            with self.assertRaises(ValueError):wire.expand(payload,body)
