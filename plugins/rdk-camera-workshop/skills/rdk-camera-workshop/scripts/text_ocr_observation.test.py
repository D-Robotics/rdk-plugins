"""Optional real macOS Vision smoke plus input-boundary checks; no camera."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageFont


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('xcrun'), 'macOS Vision/Swift required')
class TextOcrObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.build.name) / 'text-ocr'
        subprocess.run(['xcrun', 'swiftc', '-O', str(Path(__file__).with_name('text_ocr_observation.swift')),
                        '-o', str(cls.binary)], check=True, capture_output=True, timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.root = self.base / 'archive'
        self.root.mkdir()
        image = Image.new('RGB', (900, 160), 'white')
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 72)
        ImageDraw.Draw(image).text((20, 25), 'Camera Test 123', font=font, fill='black')
        self.image = self.root / 'sample.png'
        image.save(self.image)

    def tearDown(self):
        self.directory.cleanup()

    def entry(self, file='sample.png', digest=None):
        return {'file': file, 'sha256': digest or hashlib.sha256(self.image.read_bytes()).hexdigest()}

    def invoke(self, frames):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'schema': 'camera-text-ocr-observation-v1', 'frames': frames}))
        output = self.root / 'result.json'
        result = subprocess.run([str(self.binary), str(manifest), '--root', str(self.root), '--output', str(output)],
                                capture_output=True, text=True, timeout=30)
        return result, output

    def test_actual_recognition_and_no_quality_grant(self):
        result, output = self.invoke([self.entry()])
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(output.read_text())
        row = data['frames'][0]
        text = ''.join(v['text'] for v in row['lines'])
        self.assertIn('cameratest123', ''.join(c for c in text.lower() if c.isalnum()))
        self.assertEqual(row['sha256'], self.entry()['sha256'])
        self.assertFalse(data['languageCorrection'])
        self.assertEqual(data['customWords'], [])
        for key in ('qualityAccepted', 'mtfQualified', 'sdkMetadataAuthenticated', 'modelDrivenCameraDecisions'):
            self.assertFalse(data[key])

    def test_hash_mismatch_does_not_write_result(self):
        result, output = self.invoke([self.entry(digest='0' * 64)])
        self.assertEqual(result.returncode, 1)
        self.assertFalse(output.exists())

    def test_traversal_and_symlink_are_rejected(self):
        outside = self.base / 'outside.png'
        shutil.copyfile(self.image, outside)
        (self.root / 'escape.png').symlink_to(outside)
        for file in ('../outside.png', 'escape.png', str(outside)):
            result, output = self.invoke([self.entry(file)])
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())

    def test_duplicate_aliases_and_oversized_manifest(self):
        for frames in ([self.entry(), self.entry('./sample.png')], [self.entry()] * 65):
            result, output = self.invoke(frames)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(output.exists())

    def test_existing_output_is_preserved(self):
        output = self.root / 'result.json'
        output.write_bytes(b'preserve-existing-evidence')
        result, _ = self.invoke([self.entry()])
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), b'preserve-existing-evidence')

    def test_non_rgb_and_excessive_pixel_dimensions(self):
        Image.new('RGBA', (20, 20)).save(self.image)
        result, output = self.invoke([self.entry()])
        self.assertEqual(result.returncode, 1)
        self.assertFalse(output.exists())
        blob = bytearray(self.image.read_bytes())
        blob[16:24] = struct.pack('>II', 0xffffffff, 0xffffffff)
        blob[25] = 2
        self.image.write_bytes(blob)
        result, output = self.invoke([self.entry()])
        self.assertEqual(result.returncode, 1)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
