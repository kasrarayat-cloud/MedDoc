"""New source-bound WM layout policy; legacy export behavior stays unchanged."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from lxml import etree
from documents.service import DocumentError, fill_template, validate_export_layout
from documents.sdk_service import WM_IOV_SHA256

ORIGINAL=Path(__file__).resolve().parents[2]/'WM IOV Template.docx'
POLICY={'protocol':'quillmd-preserve-original-layout-v1','source_sha256':WM_IOV_SHA256}
BACKEND={'backend':'wm-iov-foss-v2','source_sha256':WM_IOV_SHA256,
         'mapping_digest':'0fcc5e36dfe589a190a726f059c45b10364f3d02f312aea5fc8935d16ea05072'}
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


class ExportLayoutTests(unittest.TestCase):
    def test_policy_refuses_unknown_extra_keys_wrong_source_and_backend(self):
        for policy,sha,backend in ((True,WM_IOV_SHA256,BACKEND),
                ({**POLICY,'unexpected':True},WM_IOV_SHA256,BACKEND),
                ({**POLICY,'protocol':'skip-checks'},WM_IOV_SHA256,BACKEND),
                (POLICY,'0'*64,BACKEND),(POLICY,WM_IOV_SHA256,{}),
                (POLICY,WM_IOV_SHA256,{**BACKEND,'mapping_digest':'0'*64})):
            with self.subTest(policy=policy,sha=sha),self.assertRaises(DocumentError):
                validate_export_layout(policy,sha,backend)

    def test_selected_policy_preserves_original_geometry_and_legacy_still_splits(self):
        # Exercise the real parent/export seam with a byte-preserving isolated-SDK
        # stand-in. Separate pinned-runtime qualification measures actual filled bytes.
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),WM_IOV_SHA256)
        def sdk(workspace,request):
            shutil.copyfile(workspace/'input.docx',workspace/'output.docx')
            return {'backend':'wm-iov-foss-v2'}
        with tempfile.TemporaryDirectory() as directory,patch('documents.sdk_service.run',sdk):
            paths=[]
            for name,policy in (('new',POLICY),('legacy',None)):
                target=Path(directory)/(name+'.docx')
                result=fill_template(ORIGINAL,[],{},target,document_backend=BACKEND,
                    expected_sha256=WM_IOV_SHA256,export_layout=policy)
                self.assertEqual(result['output_sha256'],hashlib.sha256(target.read_bytes()).hexdigest())
                with zipfile.ZipFile(target) as package:
                    tree=etree.fromstring(package.read('word/document.xml'))
                tables=tree.xpath('/w:document/w:body/w:tbl',namespaces=NS)
                paths.append(([len(t.findall('w:tr',NS)) for t in tables],
                    len(tree.xpath('/w:document/w:body/w:p',namespaces=NS))))
            self.assertEqual(paths,[([28],48),([14,14],49)])
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),WM_IOV_SHA256)

    def test_invalid_policy_refuses_before_sdk_or_creating_export(self):
        with tempfile.TemporaryDirectory() as directory,patch('documents.sdk_service.run') as sdk:
            target=Path(directory)/'refused.docx'
            with self.assertRaises(DocumentError):
                fill_template(ORIGINAL,[],{},target,document_backend=BACKEND,
                    export_layout={**POLICY,'source_sha256':'0'*64})
            sdk.assert_not_called();self.assertFalse(target.exists())


if __name__=='__main__':unittest.main()
