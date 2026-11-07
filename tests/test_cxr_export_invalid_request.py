"""Malformed sent evidence must remain distinguishable from validated images."""
import base64
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments'))
from export_cxr_vqa_extension import RequestEvidencePublisher


def broken_png():
    def chunk(kind, payload, corrupt=False):
        checksum = zlib.crc32(kind + payload) ^ int(corrupt)
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack('!I', checksum)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00'), corrupt=True) + chunk(b'IEND', b''))


class InvalidRequestEvidenceTest(unittest.TestCase):
    def test_bad_crc_archived_unchanged_and_labeled(self):
        data = broken_png()
        uri = 'data:image/png;base64,' + base64.b64encode(data).decode()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            publisher = RequestEvidencePublisher(out, out / 'manifest.json')
            digest = publisher.from_uri(uri)
            asset = publisher.assets[digest]
            self.assertEqual(digest, hashlib.sha256(data).hexdigest())
            self.assertEqual(asset['target'].read_bytes(), data)
            self.assertEqual(asset['target'].suffix, '.bin')
            self.assertEqual(asset['integrity'], 'invalid_archived_request_image')
            self.assertIsNone(asset['size'])
            self.assertEqual(publisher.from_uri(uri), digest)
            self.assertIn('invalid_request_image_bytes/', publisher.clean(uri, out / 'calls.json'))

    def test_invalid_source_image_still_rejected(self):
        data = broken_png()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            publisher = RequestEvidencePublisher(out, out / 'manifest.json')
            with self.assertRaises(SyntaxError):
                publisher.put_image(data, source='images/original.png')


if __name__ == '__main__':
    unittest.main()
