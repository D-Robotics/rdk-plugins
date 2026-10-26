import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
import paired_row_diagnostics as module
spec = importlib.util.spec_from_file_location('raw_row_tests', SCRIPTS / 'raw_row_coherence.test.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class PairedRowsTest(unittest.TestCase):
    def setUp(self):
        self.raw = fixtures.RawRowsTest()
        self.raw.setUp()
        self.addCleanup(self.raw.doCleanups)
        self.root, self.receipt = self.raw.root, self.raw.receipt
        self.receipt.update(status='observed', resourceReleaseVerified=True, pairedBytesPersisted=True)
        for i, entry in enumerate(self.receipt['rawFrames']):
            raw = np.fromfile(self.root / entry['name'], '<u2').reshape(64, 64).astype(float)
            phases = [raw[py::2, px::2].mean(axis=1) for py in range(2) for px in range(2)]
            contrast = (phases[0] + phases[2] - phases[1] - phases[3]) / 2
            y = np.full((64, 64), 64, dtype='u1')
            uv = np.empty((32, 64), dtype='u1')
            uv[:, ::2] = np.round(128 - contrast)[:, None]
            uv[:, 1::2] = np.round(128 + contrast)[:, None]
            blob = y.tobytes() + uv.tobytes()
            name = f'paired-{i}.nv12'
            (self.root / name).write_bytes(blob)
            frame = dict(entry['frame'], bit_depth=8, packing=3, bayer=0, stride_y=64, stride_uv=64, size_y=4096, size_uv=2048)
            entry.update(ispPairVerified=True, ispPair={'name': name, 'sha256': hashlib.sha256(blob).hexdigest(), 'frame': frame, 'sdkFrameIdentityMatched': True}, mipiBefore={'values': {'crc': 0}}, mipiAfter={'values': {'crc': 0}}, controlReadbackBefore={'exposure': {'sdkCode': 0, 'values': {'gain': 2}}}, controlReadbackAfter={'exposure': {'sdkCode': 0, 'values': {'gain': 2}}})
        self.raw.seal()
        self.manifest = dict(self.raw.manifest, schema='camera-paired-row-diagnostics-v1')

    def seal(self):
        self.raw.seal()
        self.manifest['receipt'] = self.raw.manifest['receipt']

    def analyze(self):
        return module.analyze(self.manifest, self.root)

    def test_known_row_mapping_and_temporal_differences(self):
        r = self.analyze()
        self.assertTrue(r['observedExposureValuesStable'])
        for row in r['frames'] + r['temporalDifferences']:
            self.assertLess(row['rawPhaseContrastVsIspChromaCorrelation']['ispU'], -.99)
            self.assertGreater(row['rawPhaseContrastVsIspChromaCorrelation']['ispV'], .99)
        for key in ['bayerQualified', 'physicalExposureCertified', 'spatialRegistrationCertified', 'metadataAuthenticity', 'rootCauseIdentified', 'qualityAccepted']:
            self.assertIs(r[key], False)

    def test_pair_identity_and_layout_rejected(self):
        frame = self.receipt['rawFrames'][0]['ispPair']['frame']
        frame['frame_id'] += 1
        self.seal()
        with self.assertRaisesRegex(ValueError, 'identity'): self.analyze()
        frame['frame_id'] -= 1
        frame['packing'] = 1
        self.seal()
        with self.assertRaisesRegex(ValueError, 'nv12_layout'): self.analyze()

    def test_payload_hash_and_length_rejected(self):
        entry = self.receipt['rawFrames'][0]['ispPair']
        path = self.root / entry['name']
        path.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError, 'sha256'): self.analyze()
        entry['sha256'] = hashlib.sha256(b'bad').hexdigest()
        self.seal()
        with self.assertRaisesRegex(ValueError, 'length'): self.analyze()

    def test_failed_acquisition_and_unverified_pair_rejected(self):
        self.receipt['resourceReleaseVerified'] = False
        self.seal()
        with self.assertRaisesRegex(ValueError, 'release'): self.analyze()
        self.receipt['resourceReleaseVerified'] = True
        self.receipt['rawFrames'][0]['ispPairVerified'] = False
        self.seal()
        with self.assertRaisesRegex(ValueError, 'identity'): self.analyze()

    def test_exposure_changes_and_counter_resets_are_observations(self):
        entry = self.receipt['rawFrames'][1]
        entry['controlReadbackAfter']['exposure']['values']['gain'] = 3
        entry['mipiBefore']['values']['crc'] = 2
        self.seal()
        r = self.analyze()
        self.assertFalse(r['observedExposureValuesStable'])
        self.assertTrue(r['frames'][1]['mipiCounterDecreased'])
        self.assertEqual(r['frames'][1]['mipiNonzeroBefore'], {'crc': 2})
        self.assertFalse(r['rootCauseIdentified'])

    def test_missing_counters_not_treated_as_zero_errors(self):
        del self.receipt['rawFrames'][0]['mipiBefore']
        self.seal()
        self.assertFalse(self.analyze()['frames'][0]['mipiCounterCoveragePresent'])

    def test_outside_symlink_rejected(self):
        entry = self.receipt['rawFrames'][0]['ispPair']
        with tempfile.TemporaryDirectory() as outside:
            path = self.root / entry['name']
            target = Path(outside) / 'payload'
            target.write_bytes(path.read_bytes())
            path.unlink()
            path.symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'outside_root'): self.analyze()

    def test_cli_refuses_overwriting_receipt(self):
        source = self.root / 'manifest.json'
        source.write_text(json.dumps(self.manifest))
        target = self.root / 'receipt.json'
        before = target.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPTS / 'paired_row_diagnostics.py'), str(source), '--root', str(self.root), '--output', str(target)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, target.read_bytes())


if __name__ == '__main__': unittest.main()
