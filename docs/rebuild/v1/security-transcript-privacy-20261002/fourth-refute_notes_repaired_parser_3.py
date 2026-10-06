import os,sys,json,socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,"/opt/meddoc-pro/.worktrees/v1-sol-notes-voice/rebuild")
os.environ.update(QUILLMD_ENV_MANAGED="1",QUILLMD_SECRET_KEY="synthetic-refutation-only",QUILLMD_DATA_MODE="synthetic",QUILLMD_AI_MODE="fixture",DJANGO_SETTINGS_MODULE="quillmd.settings",QUILLMD_DB_PASSWORD="synthetic-unusable-no-connection",QUILLMD_DB_HOST="127.0.0.1",QUILLMD_DB_PORT="1",QUILLMD_STATE_DIR="/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security/refute-state")
import django
django.setup()
from django.test import override_settings
from core import generation as g,v3_field_relations as r,transcript_context as tc
from core.tests.test_v3_supersession_floor import SONNET_55_DEFAULT,form,raw
from core.tests.test_v3_field_relations import relation_wire
from core.tests.test_transcript_context import proof

import importlib,hashlib
from django.apps import apps
from core import disposition
from core import source_scope as scope,v3_syntax
from core.tests.test_v3_supersession_floor import SONNET_55_DEFAULT,form
with override_settings(**SONNET_55_DEFAULT),patch.object(socket.socket,"connect",side_effect=AssertionError("Network forbidden")):
 out=[]
 for tail,label in [('No longer the daily medication.', 'Current medications'), ('Her father is not the only warfarin user.', 'Current medications'), ('Her father is the only person not taking warfarin.', 'Current medications'), ('Only her father is not taking warfarin.', 'Current medications'), ('Takes apixaban 5 mg daily. No longer a daily medication.', 'Current medications')]:
  notes="Takes warfarin 5 mg daily. "+tail
  reading=g.governance_for(notes,form(label,"Plan"))[11]["preceding"]
  docs=v3_syntax.docs(u["quote"] for u in reading["units"])
  out.append({"notes":notes,"dependencies":scope.elliptical_dependencies(reading),"exclusive":scope.exclusive_reattributions(reading),"units":[{"quote":u["quote"],"parsed":reading["parsed"].get(u["id"]),"actor":reading["actors"][u["id"]],"tokens":[{"text":t.text,"pos":t.pos_,"dep":t.dep_,"lemma":t.lemma_} for t in doc]} for u,doc in zip(reading["units"],docs)]})
 Path("/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security/refute-notes-repaired-parser-3.json").write_text(json.dumps(out,indent=2,default=lambda x:sorted(x) if isinstance(x,(set,frozenset)) else str(x)))
 print(json.dumps(out,indent=2,default=lambda x:sorted(x) if isinstance(x,(set,frozenset)) else str(x)))
