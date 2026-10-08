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
from documents.layout import restore_original_wm_signing_property

ORIGINAL=Path(__file__).resolve().parents[2]/'WM IOV Template.docx'
POLICY={'protocol':'quillmd-preserve-original-layout-v1','source_sha256':WM_IOV_SHA256}
BACKEND={'backend':'wm-iov-foss-v2','source_sha256':WM_IOV_SHA256,
         'mapping_digest':'0fcc5e36dfe589a190a726f059c45b10364f3d02f312aea5fc8935d16ea05072'}
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}


class ExportLayoutTests(unittest.TestCase):
    def sdk_signing_copy(self,path,change='keepNext'):
        with zipfile.ZipFile(ORIGINAL) as package:parts={n:package.read(n) for n in package.namelist()}
        tree=etree.fromstring(parts['word/document.xml'])
        properties=tree.xpath('/w:document/w:body/w:p',namespaces=NS)[45].find('w:pPr',NS)
        flag=etree.Element('{'+NS['w']+'}keepNext');properties.insert(0,flag)
        if change=='duplicate':properties.insert(0,etree.Element(flag.tag))
        elif change=='value':flag.set('{'+NS['w']+'}val','0')
        elif change=='spacing':properties.find('w:spacing',NS).set('{'+NS['w']+'}after','17')
        elif change=='tail':flag.tail='UNEXPLAINED PROPERTY TEXT'
        elif change=='duplicate-properties':
            extra=etree.Element(properties.tag);etree.SubElement(extra,'{'+NS['w']+'}pageBreakBefore')
            properties.getparent().insert(1,extra)
        elif change=='no-flag-extra-table-paragraph':
            properties.remove(flag)
            tree.xpath('/w:document/w:body/w:tbl/w:tr/w:tc',namespaces=NS)[0].append(etree.Element('{'+NS['w']+'}p'))
        parts['word/document.xml']=etree.tostring(tree,xml_declaration=True,encoding='UTF-8')
        if change=='sdk-space':parts['word/document.xml']=parts['word/document.xml'].replace(b'<w:keepNext/>',b'<w:keepNext />')
        with zipfile.ZipFile(path,'w') as package:
            for name,payload in parts.items():package.writestr(name,payload)
        return parts

    def test_exact_added_signing_flag_restored_other_parts_and_original_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'sdk.docx';before=self.sdk_signing_copy(target)
            result=restore_original_wm_signing_property(target,ORIGINAL.read_bytes())
            self.assertTrue(result['timestamp_keep_next_restored'])
            with zipfile.ZipFile(target) as package:after={n:package.read(n) for n in package.namelist()}
            self.assertEqual(after['word/document.xml'],before['word/document.xml'].replace(b'<w:keepNext/>',b'',1))
            self.assertEqual({k:v for k,v in before.items() if k!='word/document.xml'},
                             {k:v for k,v in after.items() if k!='word/document.xml'})
            self.assertFalse(restore_original_wm_signing_property(target,ORIGINAL.read_bytes())['timestamp_keep_next_restored'])
        self.assertEqual(hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),WM_IOV_SHA256)

    def test_signing_repair_does_not_suppress_other_or_duplicate_property_changes(self):
        for mutation in ('spacing','duplicate','value','tail','duplicate-properties','no-flag-extra-table-paragraph'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                target=Path(directory)/'unexpected.docx';self.sdk_signing_copy(target,mutation)
                before=target.read_bytes()
                with self.assertRaises(DocumentError):restore_original_wm_signing_property(target,ORIGINAL.read_bytes())
                self.assertEqual(target.read_bytes(),before)

    def test_actual_sdk_empty_leaf_serialization_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'sdk-space.docx';self.sdk_signing_copy(target,'sdk-space')
            self.assertTrue(restore_original_wm_signing_property(target,ORIGINAL.read_bytes())['timestamp_keep_next_restored'])

    def test_new_policy_export_seam_restores_added_sdk_signing_flag(self):
        def sdk(workspace,request):
            self.sdk_signing_copy(workspace/'output.docx')
            return {'backend':'wm-iov-foss-v2'}
        with tempfile.TemporaryDirectory() as directory,patch('documents.sdk_service.run',sdk):
            target=Path(directory)/'filled.docx'
            result=fill_template(ORIGINAL,[],{},target,document_backend=BACKEND,export_layout=POLICY)
            self.assertTrue(result['layout']['timestamp_keep_next_restored'])
            with zipfile.ZipFile(target) as package:tree=etree.fromstring(package.read('word/document.xml'))
            self.assertIsNone(tree.xpath('/w:document/w:body/w:p',namespaces=NS)[45].find('w:pPr/w:keepNext',NS))

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
