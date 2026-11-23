"""Storage-only checks for successful restricted-process operations."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from m5rrsi.process_runtime import retain_success


@unittest.skipUnless(os.name == 'posix', 'Process runtime is a Linux entrypoint')
class ProcessStorage(unittest.TestCase):
    def test_state_and_native_requests_survive_rootfs_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            work = base / 'operation'
            root = work / 'rootfs'
            (root / 'state/native_services/calls').mkdir(parents=True)
            (root / 'state/memory.json').write_text('{"fixture":true}')
            native = root / 'state/native_services/calls/request.json'
            native.write_text('{"synthetic_only":true}')
            (work / 'stdout.log').write_text('software fixture')
            state = base / 'retained-state'
            state.mkdir()
            before = base / 'immutable-before'
            before.mkdir()
            (before / 'memory.json').write_text('prior immutable fixture')
            raw = {'answer': 'synthetic-only', 'usage': {'model_calls': 0}}
            retain_success(work, root, state, raw, {'usage': {'authoritative': True, 'model_calls': 0}})
            self.assertFalse(root.exists())
            self.assertEqual((state / 'native_services/calls/request.json').read_text(), '{"synthetic_only":true}')
            self.assertEqual((state / 'memory.json').read_text(), '{"fixture":true}')
            self.assertEqual((before / 'memory.json').read_text(), 'prior immutable fixture')
            self.assertEqual(json.loads((work / 'worker_result.json').read_text()), raw)
            mapping = json.loads((work / 'receipt.json').read_text())
            self.assertEqual(mapping['source_rootfs'], str(root))
            self.assertEqual(mapping['retained_state'], str(state))
            self.assertEqual((work / 'stdout.log').read_text(), 'software fixture')


if __name__ == '__main__':
    unittest.main()
