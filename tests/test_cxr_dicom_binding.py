"""DICOM native argument binding must stay under executor control."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from cxr_vqa_tool_worker import execute


class DicomBindingTest(unittest.TestCase):
    def test_executor_uses_dicom_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);image=root/'source.dcm';image.write_bytes(b'fixture')
            tool=Mock();tool.invoke.return_value={'format':'dicom'}
            registry=SimpleNamespace(build_tools=lambda *a,**kw:({'dicom_processor':tool},{}))
            modules={'tool_registry_ext':registry,'build_case_tool_evidence':SimpleNamespace(CLASSIFIER_FILENAME='unused')}
            req={'backend':'dicom_processor','args':{},'image':str(image),'artifact_dir':str(root/'artifacts'),'runtime':{'root':str(root),'tool_repo':'source'}}
            with patch.dict(sys.modules,modules):result=execute(req)
            tool.invoke.assert_called_once_with({'dicom_path':str(image)})
            self.assertEqual(result['status'],'completed')

    def test_model_cannot_supply_dicom_path(self):
        with tempfile.TemporaryDirectory() as folder:
            req={'backend':'dicom_processor','args':{'dicom_path':'unbound'},'image':'bound.dcm','artifact_dir':folder,'runtime':{'root':folder,'tool_repo':'source'}}
            with self.assertRaisesRegex(ValueError,'model_paths_forbidden'):execute(req)


if __name__=='__main__':unittest.main()
