import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from controlled_raw_phase_series import analyze


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        frames = []
        for i in range(12):
            gain = [1, 4, 8, 1][i // 3]
            a = (50 + np.indices((32, 32))[0] % 7 + (i % 3) * (np.indices((32, 32))[0] % 3)).astype('<u2')
            blob = a.tobytes()
            name = f'{i}.raw'
            (self.root / name).write_bytes(blob)
            exp = {'mode': 1, 'manual_attr.again': gain, 'manual_attr.exp_time': .001, 'manual_attr.dgain': 1, 'manual_attr.ispgain': 1}
            white = {'mode': 1, **{'manual_attr.gain.' + k: 1 for k in ('rgain', 'grgain', 'gbgain', 'bgain')}}
            control = {'exposure': {'sdkCode': 0, 'values': exp}, 'awb': {'sdkCode': 0, 'values': white}}
            frames.append({'name': name, 'sha256': hashlib.sha256(blob).hexdigest(), 'gainPhase': i // 3,
                           'nativeCode': 0, 'sdkAgain': gain, 'sdkIntegrationSeconds': .001,
                           'controlReadbackBefore': copy.deepcopy(control), 'controlReadbackAfter': copy.deepcopy(control),
                           'frame': {'width': 32, 'height': 32, 'stride_y': 64, 'stride_uv': 0, 'size_y': 2048,
                                     'size_uv': 0, 'bit_depth': 10, 'bayer': 0xffffffff, 'packing': 0, 'alignment': 0,
                                     'frame_id': 0 if i < 8 else i - 7, 'timestamp_ns': 1000 + i}})
        self.receipt = {'rawFrames': frames, 'rawCalls': 12, 'rawBytesPersisted': True, 'resourceReleaseVerified': True,
                        'ispOriginalsRestored': True, 'diagnosticRawSnapshotsComplete': True,
                        'streamObservedAndReleased': True, 'rawTransportVerified': False, 'rawBayerQualified': False}
        self.manifest = {'schema': 'camera-controlled-raw-phase-series-v1', 'roi': {'x': 0, 'y': 0, 'width': 32, 'height': 32}, 'detrendWindowPhaseRows': 15}

    def tearDown(self):
        self.tmp.cleanup()

    def run_analysis(self):
        blob = json.dumps(self.receipt).encode()
        (self.root / 'receipt.json').write_bytes(blob)
        self.manifest['receipt'] = {'file': 'receipt.json', 'sha256': hashlib.sha256(blob).hexdigest()}
        return analyze(self.manifest, self.root)

    def test_zero_and_nonzero_ids_preserved_without_identity_grant(self):
        r = self.run_analysis()
        self.assertEqual(len(r['frames']), 12)
        self.assertEqual(len(r['temporalDifferences']), 8)
        self.assertEqual(r['frames'][8]['frame']['frame_id'], 1)
        self.assertFalse(r['sameFrameIspPairing'])
        self.assertFalse(r['qualityAccepted'])
        self.assertFalse(r['rootCauseIdentified'])

    def test_repeated_timestamp_rejected(self):
        self.receipt['rawFrames'][4]['frame']['timestamp_ns'] = 1003
        with self.assertRaisesRegex(ValueError, 'strict_actual_timestamp'):
            self.run_analysis()

    def test_readback_mismatch_rejected(self):
        self.receipt['rawFrames'][3]['controlReadbackAfter']['exposure']['values']['manual_attr.again'] = 1
        with self.assertRaisesRegex(ValueError, 'actual_frozen'):
            self.run_analysis()

    def test_white_balance_change_rejected(self):
        self.receipt['rawFrames'][4]['controlReadbackBefore']['awb']['values']['manual_attr.gain.bgain'] = 2
        with self.assertRaisesRegex(ValueError, 'white_balance'):
            self.run_analysis()

    def test_other_gain_change_rejected(self):
        self.receipt['rawFrames'][4]['controlReadbackBefore']['exposure']['values']['manual_attr.ispgain'] = 2
        with self.assertRaisesRegex(ValueError, 'other_exposure_gains'):
            self.run_analysis()

    def test_unrestored_receipt_rejected(self):
        self.receipt['ispOriginalsRestored'] = False
        with self.assertRaisesRegex(ValueError, 'restoration'):
            self.run_analysis()

    def test_out_of_range_payload_rejected_even_with_updated_hash(self):
        blob = bytearray((self.root / '0.raw').read_bytes())
        blob[:2] = (1029).to_bytes(2, 'little')
        (self.root / '0.raw').write_bytes(blob)
        self.receipt['rawFrames'][0]['sha256'] = hashlib.sha256(blob).hexdigest()
        with self.assertRaisesRegex(ValueError, 'out_of_range'):
            self.run_analysis()

    def test_tampered_payload_rejected(self):
        (self.root / '0.raw').write_bytes(b'x' * 2048)
        with self.assertRaisesRegex(ValueError, 'sha256_mismatch'):
            self.run_analysis()

    def test_wrong_phase_and_path_escape_rejected(self):
        self.receipt['rawFrames'][3]['gainPhase'] = 0
        with self.assertRaisesRegex(ValueError, 'three_frames_per_phase'):
            self.run_analysis()
        self.receipt['rawFrames'][3]['gainPhase'] = 1
        self.receipt['rawFrames'][0]['name'] = '../outside.raw'
        with self.assertRaisesRegex(ValueError, 'outside_root_or_missing'):
            self.run_analysis()


if __name__ == '__main__':
    unittest.main()
