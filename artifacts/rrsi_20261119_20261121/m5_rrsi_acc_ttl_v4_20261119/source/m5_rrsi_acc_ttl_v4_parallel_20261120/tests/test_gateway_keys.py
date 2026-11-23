"""Native paired credential-slot selection with synthetic key text."""
from pathlib import Path
import tempfile
import unittest

from integration.native_gateway import GatewayError, read_key


class TestGatewayCredentialSlots(unittest.TestCase):
    def test_existing_paired_slot_selects_nonempty_line_without_joining(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'paired.keys'
            path.write_text('synthetic-main\n\nsynthetic-memory\n', encoding='utf-8')
            self.assertEqual(read_key({'path': str(path), 'line': 0}), 'synthetic-main')
            self.assertEqual(read_key({'path': str(path), 'line': 1}), 'synthetic-memory')

    def test_missing_slot_is_an_explicit_binding_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'paired.keys'
            path.write_text('synthetic-main\n', encoding='utf-8')
            with self.assertRaisesRegex(GatewayError, 'credential_line_unavailable'):
                read_key({'path': str(path), 'line': 1})

    def test_original_single_key_file_remains_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'single.key'
            path.write_text('synthetic-main\n', encoding='utf-8')
            self.assertEqual(read_key(str(path)), 'synthetic-main')


if __name__ == '__main__':
    unittest.main()
