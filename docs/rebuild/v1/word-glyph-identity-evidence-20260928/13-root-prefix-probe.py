from pathlib import Path
import sys,importlib.util,json,io,zipfile
from docx import Document
R=Path(__file__).parent;sys.path.insert(0,str(Path('rebuild/documents').resolve()));p=R/'fixed_word_v3.py';spec=importlib.util.spec_from_file_location('glyph_local_prefix',p);w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
d=Document();d.add_paragraph('☐ First: _____ ☐ Last');stream=io.BytesIO();d.save(stream);z=zipfile.ZipFile(io.BytesIO(stream.getvalue()));parts={n:z.read(n) for n in z.namelist()};parts['word/document.xml']=parts['word/document.xml'].replace(b'<w:r>',b'<x:r xmlns:x="http://schemas.openxmlformats.org/wordprocessingml/2006/main">').replace(b'</w:r>',b'</x:r>').replace(b'<w:t>',b'<x:t>').replace(b'</w:t>',b'</x:t>');buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as out:
 for n,b in parts.items():out.writestr(n,b)
raw=buffer.getvalue();(R/'local-prefix-original.docx').write_bytes(raw);idx=w.SlotIndex(w.open_package(raw));slot=next(s for s in idx.slots if s.kind=='p');s=w.paragraph_text(slot.el)[0];start=s.index('_____');loc={'contract':'v3','part':slot.part,'slot':slot.path,'fingerprint':w.fingerprint(slot.el)}
fs=[{'key':'c','kind':'multi_choice','label':'Choices','options':['First','Last'],'locator':{**loc,'target':{'type':'checkboxes','boxes':w.place_box_refs(idx,slot)}}},{'key':'t','kind':'text','label':'First description','locator':{**loc,'target':{'type':'span','start':start,'end':start+5,'shape':'blank'}}}]
result={'original_text':s,'fields':fs}
try:
 out=w.fill(raw,fs,{'c':['First','Last'],'t':'literal ☐ text'});(R/'local-prefix-export.docx').write_bytes(out);result['outcome']='exported'
except Exception as e:result.update(outcome='refused',error_type=type(e).__name__,message=str(e))
(R/'prefix-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
