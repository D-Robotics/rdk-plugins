import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

from wb_paper_observation import observe


class PaperObservationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        rng = np.random.default_rng(45)
        self.base = rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)
        self.base = cv2.GaussianBlur(self.base, (3, 3), 0)
        self.manifest = {'schema': 'camera-wb-paper-observation-v1',
                         'registrationRoi': [0, 0, 640, 480], 'motionLimitPixels': 5,
                         'paperRois': {'paper': [180, 180, 220, 90]}, 'phases': []}
        for label, blue in [('original', 206), ('candidate', 187)]:
            frames = []
            for i in range(3):
                a = self.base.copy()
                a[180:270, 180:400] = [178+i, 180, blue]
                frames.append(self.save(f'{label}-{i}.png', a))
            self.manifest['phases'].append({'label': label, 'frames': frames})
        self.manifest['reference'] = self.manifest['phases'][0]['frames'][0]

    def tearDown(self):
        self.temp.cleanup()

    def save(self, name, pixels):
        p = self.root/name
        Image.fromarray(pixels).save(p)
        return {'file': name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

    def test_fixed_masks_and_ratios_do_not_grant_quality(self):
        r = observe(self.manifest, self.root)
        self.assertAlmostEqual(r['phases'][0]['paperMedian']['paper']['BoverGMedian'], 206/180)
        self.assertAlmostEqual(r['phases'][1]['paperMedian']['paper']['BoverGMedian'], 187/180)
        self.assertTrue(all(p['geometryWithinLimitObserved'] for p in r['phases']))
        self.assertFalse(r['qualityAccepted'])
        self.assertFalse(r['awbCalibrationQualified'])
        self.assertFalse(r['sdkFrameIdentityQualified'])

    def test_large_geometry_change_is_observed_and_not_admitted(self):
        for i in range(3):
            a = self.base.copy()
            a[180:270, 180:400] = [178+i, 180, 187]
            a = cv2.warpAffine(a, np.float32([[1, 0, 45], [0, 1, 30]]), (640, 480))
            self.manifest['phases'][1]['frames'][i] = self.save(f'moved-{i}.png', a)
        r = observe(self.manifest, self.root)
        self.assertFalse(r['phases'][1]['geometryWithinLimitObserved'])
        self.assertTrue(all(f['geometry']['status'] == 'changed' for f in r['phases'][1]['frames']))
        self.assertIsNone(r['phases'][1]['paperMedian'])
        self.assertTrue(all(f['paper'] is None for f in r['phases'][1]['frames']))

    def test_changed_image_bytes_and_duplicate_samples_rejected(self):
        entry = self.manifest['phases'][1]['frames'][0]
        (self.root/entry['file']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'sha256'):
            observe(self.manifest, self.root)
        m = copy.deepcopy(self.manifest)
        m['phases'][0]['frames'][1] = m['phases'][0]['frames'][0]
        with self.assertRaisesRegex(ValueError, 'duplicate_images'):
            observe(m, self.root)

    def test_root_escape_and_invalid_rois_rejected(self):
        m = copy.deepcopy(self.manifest)
        m['reference']['file'] = '../outside.png'
        with self.assertRaisesRegex(ValueError, 'outside_root'):
            observe(m, self.root)
        self.manifest['paperRois']['paper'] = [630, 0, 20, 90]
        with self.assertRaisesRegex(ValueError, 'roi_outside'):
            observe(self.manifest, self.root)

    def test_untextured_paper_does_not_prove_registration(self):
        for phase_number, phase in enumerate(self.manifest['phases']):
            phase['frames'] = [self.save(f'plain-{phase_number}-{i}.png',
                                        np.full((480, 640, 3), 180+phase_number*10+i, np.uint8))
                               for i in range(3)]
        self.manifest['reference'] = self.manifest['phases'][0]['frames'][0]
        r = observe(self.manifest, self.root)
        self.assertFalse(any(p['geometryWithinLimitObserved'] for p in r['phases']))

    def test_clipping_is_retained_with_original_mask(self):
        for i in range(3):
            a = self.base.copy()
            a[180:270, 180:400] = 255
            a[5, 5] = i
            self.manifest['phases'][1]['frames'][i] = self.save(f'clipped-{i}.png', a)
        r = observe(self.manifest, self.root)
        self.assertTrue(all(f['paper']['paper']['clippedAt255Fraction'] == 1 for f in r['phases'][1]['frames']))
        self.assertFalse(r['phases'][1]['paperUsableObserved'])
        self.assertIsNone(r['phases'][1]['paperMedian'])
        self.assertFalse(r['qualityAccepted'])


if __name__ == '__main__':
    unittest.main()
