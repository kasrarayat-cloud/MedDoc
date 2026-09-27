"""One exact authorized count-only request; existing attempts never replayed."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
from dotenv import dotenv_values
from anthropic import Anthropic
root=Path(__file__).parent
if (root/'compact-count-attempt.json').exists():raise SystemExit('Existing attempt: reconcile without replay.')
data=(root/'compact-count-request.json').read_bytes()
sha=hashlib.sha256(data).hexdigest()
if sha!='52225de3bd14756722430db311884433c5b1179ad33b8f4076c95999a9009ac6':raise SystemExit('Unauthorized request hash.')
request=json.loads(data)
values=dotenv_values('/opt/meddoc-pro/rebuild/.env');key=values.get('ANTHROPIC_API_KEY')
if not key:raise SystemExit('Credential unavailable; no request.')
client=Anthropic(api_key=key,base_url='https://api.anthropic.com',max_retries=0,timeout=30)
values.clear();del key
attempt={'request_sha256':sha,'timestamp':datetime.now(timezone.utc).isoformat(),'endpoint':'https://api.anthropic.com/v1/messages/count_tokens','model':'claude-sonnet-5','max_retries':0,'timeout_seconds':30,'measurement':'Native INPUT tokens of prospective output text, not generation proof.'}
with (root/'compact-count-attempt.json').open('x') as stream:json.dump(attempt,stream,indent=2);stream.flush();os.fsync(stream.fileno())
try:outcome={'state':'completed','input_tokens':client.messages.count_tokens(**request).input_tokens}
except Exception as exc:outcome={'state':'unknown_or_refused','error_class':type(exc).__name__,'http_status':getattr(exc,'status_code',None)}
outcome.update(timestamp=datetime.now(timezone.utc).isoformat(),request_sha256=sha)
with (root/'compact-count-outcome.json').open('x') as stream:json.dump(outcome,stream,indent=2);stream.flush();os.fsync(stream.fileno())
client.close();print(json.dumps(outcome))
