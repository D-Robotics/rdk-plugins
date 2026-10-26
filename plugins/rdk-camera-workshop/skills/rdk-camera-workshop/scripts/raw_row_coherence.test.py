import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

SCRIPT = Path(__file__).with_name('raw_row_coherence.py')
spec = importlib.util.spec_from_file_location('raw_rows', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RawRowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.receipt = {'rawCalls': 3, 'rawTransportVerified': True, 'rawBytesPersisted': True, 'rawFrames': []}
        for i in range(3):
            yy = np.arange(64)[:, None]
            xx = np.arange(64)[None, :]
            # A moving row component, shared within each parity, inverted by column parity.
            values = 200 + (1 - 2 * (xx % 2)) * (10 * np.sin(yy / 2 + i)).astype(int)
            pixels = np.broadcast_to(values, (64, 64)).astype('<u2')
            name = f'frame-{i}.raw'
            data = pixels.tobytes()
            (self.root / name).write_bytes(data)
            meta = dict(width=64, height=64, stride_y=128, stride_uv=0, size_y=8192, size_uv=0, bit_depth=10, bayer=0xffffffff, packing=0, alignment=0, frame_id=i+1, timestamp_ns=(i+1)*1000)
            self.receipt['rawFrames'].append({'name': name, 'sha256': hashlib.sha256(data).hexdigest(), 'frame': meta, 'nativeCode': 0})
        self.manifest = {'schema': 'camera-raw-row-coherence-v1', 'roi': dict(x=0, y=0, width=64, height=64), 'detrendWindowPhaseRows': 9}
        self.seal()

    def seal(self):
        data = json.dumps(self.receipt).encode()
        (self.root / 'receipt.json').write_bytes(data)
        self.manifest['receipt'] = {'file': 'receipt.json', 'sha256': hashlib.sha256(data).hexdigest()}

    def analyze(self):
        return module.analyze(self.manifest, self.root)

    def test_shared_row_variation_and_opposite_parities(self):
        result = self.analyze()
        d = result['temporalDifferences'][0]
        self.assertGreater(d['phases']['00']['alternatingColumnCorrelation'], .99)
        self.assertLess(d['unlabelledPhaseCorrelations'][0][1], -.99)
        for field in ['qualityAccepted', 'rootCauseIdentified', 'bayerQualified', 'metadataAuthenticity', 'configurationEquivalence', 'sameFrameIspPairing']:
            self.assertIs(result[field], False)

    def test_constant_difference_has_undefined_correlation(self):
        for row in self.receipt['rawFrames']:
            data = np.full((64, 64), 201, dtype='<u2').tobytes()
            (self.root / row['name']).write_bytes(data)
            row['sha256'] = hashlib.sha256(data).hexdigest()
        self.seal()
        self.assertIsNone(self.analyze()['temporalDifferences'][0]['phases']['00']['alternatingColumnCorrelation'])

    def test_wrong_hash_and_duplicate_identity_rejected(self):
        (self.root / 'frame-0.raw').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'sha256'): self.analyze()
        self.setUp()
        self.receipt['rawFrames'][1]['frame']['frame_id'] = 1
        self.seal()
        with self.assertRaisesRegex(ValueError, 'increase'): self.analyze()

    def test_wrong_packing_alignment_and_length_rejected(self):
        original = copy.deepcopy(self.receipt)
        for key, value in [('packing', 1), ('alignment', 1), ('size_y', 8000), ('bayer', 0), ('width', 63)]:
            self.receipt = copy.deepcopy(original)
            self.receipt['rawFrames'][0]['frame'][key] = value
            self.seal()
            with self.subTest(key=key), self.assertRaises(ValueError): self.analyze()

    def test_left_aligned_bytes_supported_without_color_assignment(self):
        for row in self.receipt['rawFrames']:
            data = (np.fromfile(self.root / row['name'], '<u2') << 6).astype('<u2').tobytes()
            (self.root / row['name']).write_bytes(data)
            row['sha256'] = hashlib.sha256(data).hexdigest()
            row['frame']['alignment'] = 1
        self.seal()
        self.assertGreater(self.analyze()['temporalDifferences'][0]['phases']['00']['alternatingColumnCorrelation'], .99)

    def test_bounds_and_outside_symlink_rejected(self):
        self.manifest['roi']['width'] = 66
        with self.assertRaisesRegex(ValueError, 'outside_raw'): self.analyze()
        self.manifest['roi']['width'] = 64
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'bytes.raw'
            target.write_bytes((self.root / 'frame-0.raw').read_bytes())
            (self.root / 'frame-0.raw').unlink()
            (self.root / 'frame-0.raw').symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'outside_root'): self.analyze()

    def test_failed_or_too_few_transports_rejected(self):
        self.receipt['rawTransportVerified'] = False
        self.seal()
        with self.assertRaisesRegex(ValueError, 'transports'): self.analyze()
        self.receipt['rawTransportVerified'] = True
        self.receipt['rawFrames'] = self.receipt['rawFrames'][:2]
        self.receipt['rawCalls'] = 2
        self.seal()
        with self.assertRaisesRegex(ValueError, 'transports'): self.analyze()

    def test_cli_refuses_overwriting_archive(self):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps(self.manifest))
        target = self.root / 'receipt.json'
        before = target.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), str(manifest), '--root', str(self.root), '--output', str(target)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__': unittest.main()
