import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from raw_metadata_diagnostics import analyze


class MetadataDiagnosticTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.receipt = {'resourceReleaseVerified': True, 'rawFrames': []}
        for n, frame_id in enumerate([901, 980, 1059]):
            a = np.full((4, 6), 51, dtype='<u2'); a[0, 0] = frame_id
            name = f'raw-{n}.bin'; data = a.tobytes(); (self.root / name).write_bytes(data)
            payload = {'name': name, 'sha256': hashlib.sha256(data).hexdigest()}
            row = {'frame': dict(width=6, height=4, stride_y=12, size_y=48, stride_uv=0, size_uv=0, bit_depth=10, packing=0, frame_id=frame_id, timestamp_ns=n + 1), 'nativeCode': 0 if n < 2 else -74}
            if n == 2: row['forensicPayload'] = {**payload, 'rawInterpretationAccepted': False}
            else: row.update(payload)
            self.receipt['rawFrames'].append(row)

    def run_analysis(self):
        data = json.dumps(self.receipt).encode(); (self.root / 'receipt.json').write_bytes(data)
        return analyze({'schema': 'camera-raw-metadata-diagnostics-v1', 'receipt': {'file': 'receipt.json', 'sha256': hashlib.sha256(data).hexdigest()}}, self.root)

    def test_injection_overflow_is_diagnostic_only(self):
        r = self.run_analysis()
        self.assertTrue(r['repeatedFirstWordFrameIdAssociation'])
        self.assertTrue(r['frameIdOverflowExplainsRightAlignmentRejection'])
        for key in ['hardwareInjectionMechanismConfirmed', 'fullFrameColorBandRootCauseIdentified', 'formalRawAdmissionGranted', 'qualityAccepted', 'bytesModified']: self.assertFalse(r[key])

    def test_more_corruption_not_explained_by_first_word(self):
        row = self.receipt['rawFrames'][-1]; payload = row['forensicPayload']; data = bytearray((self.root / payload['name']).read_bytes()); data[4:6] = b'\xff\xff'; (self.root / payload['name']).write_bytes(data); payload['sha256'] = hashlib.sha256(data).hexdigest()
        self.assertFalse(self.run_analysis()['frameIdOverflowExplainsRightAlignmentRejection'])

    def test_zero_frame_id_is_unavailable(self):
        for row in self.receipt['rawFrames']: row['frame']['frame_id'] = 0
        self.assertFalse(self.run_analysis()['repeatedFirstWordFrameIdAssociation'])

    def test_hash_corruption(self):
        (self.root / 'raw-0.bin').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'sha256'): self.run_analysis()

    def test_unreleased(self):
        self.receipt['resourceReleaseVerified'] = False
        with self.assertRaisesRegex(ValueError, 'released'): self.run_analysis()

    def test_wrong_layout(self):
        self.receipt['rawFrames'][0]['frame']['stride_y'] = 11
        with self.assertRaisesRegex(ValueError, 'layout'): self.run_analysis()

    def test_rejected_not_promoted(self):
        self.receipt['rawFrames'][-1]['forensicPayload']['rawInterpretationAccepted'] = True
        with self.assertRaisesRegex(ValueError, 'remain_rejected'): self.run_analysis()

    def test_escape(self):
        payload = self.receipt['rawFrames'][0]; payload['name'] = '../outside.bin'
        with self.assertRaisesRegex(ValueError, 'outside'): self.run_analysis()


if __name__ == '__main__': unittest.main()
