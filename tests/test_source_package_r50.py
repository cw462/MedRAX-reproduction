"""New outgoing-source sanitation rules; no source package or model run."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'local_assets'))
import capture_r50_publication_sources as source


class SourceCopies(unittest.TestCase):
    def test_redacts_selected_values_preserving_json_and_field_names(self):
        fixture='opaque-'+'test-secret'
        original=json.dumps({'api_key':fixture,'model':'qwen3.7-plus','total_tokens':12})
        result,counts=source.sanitize(original);value=json.loads(result)
        self.assertEqual(value,{'api_key':'[REDACTED]','model':'qwen3.7-plus','total_tokens':12})
        self.assertEqual(counts['quoted_credential_fields'],1)

    def test_full_private_key_block_removed_but_truncated_block_rejected(self):
        begin='-----BEGIN '+'PRIVATE KEY-----';end='-----END '+'PRIVATE KEY-----'
        result,counts=source.sanitize(begin+'\nfixture-only\n'+end)
        self.assertNotIn('fixture-only',result);self.assertEqual(counts['private_key_blocks'],1)
        with self.assertRaisesRegex(ValueError,'incomplete_private_key'):
            source.sanitize(begin+'\nfixture-only')

    def test_source_map_paths_cannot_escape_explicit_destination(self):
        self.assertEqual(str(source.relative_path('actual_CODE/experiments/runtime.py')),'actual_CODE/experiments/runtime.py')
        for relative in ('../private.key','C:/private.key','/home/private.key','actual_CODE\\private.key'):
            with self.subTest(relative=relative),self.assertRaises(ValueError):source.relative_path(relative)


if __name__=='__main__':unittest.main()
