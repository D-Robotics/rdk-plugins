import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from temporal_row_diagnostics import analyze


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, images, ids=None):
        frames = []
        for i, pixels in enumerate(images):
            file = self.root / (str(i) + ".png")
            Image.fromarray(pixels.astype(np.uint8)).save(file)
            frames.append({"name": file.name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                           "frame": {"frame_id": ids[i] if ids else i + 1,
                                     "timestamp_ns": (i + 1) * 1_000_000_000,
                                     "width": pixels.shape[1], "height": pixels.shape[0]}})
        journal = self.root / "journal.json"
        journal.write_text(json.dumps({"phases": [{"label": "candidate", "images": frames[:3], "additionalImages": frames[3:]}]}))
        return {"schema": "camera-temporal-row-diagnostics-v1",
                "journal": {"file": journal.name, "sha256": hashlib.sha256(journal.read_bytes()).hexdigest(), "phase": "candidate"},
                "roi": {"x": 0, "y": 0, "width": 64, "height": 128}, "detrendWindowRows": 33}

    def flat(self, value=80):
        return np.full((128, 64, 3), value, dtype=np.uint8)

    def stripes(self, phase=0):
        a = self.flat().astype(float)
        wave = 12 * np.sin(2 * np.pi * (np.arange(128) + phase) / 16)
        a[:, :, 0] += wave[:, None]
        a[:, :, 2] -= wave[:, None]
        return a

    def test_uniform_brightness_changes_do_not_become_a_row_band_diagnosis(self):
        result = analyze(self.fixture([self.flat(40), self.flat(60), self.flat(80)]), self.root)
        self.assertEqual(result["roiMeanCodeRange"]["span"], 40)
        for frame in result["frames"]:
            self.assertEqual(frame["rowResidualRmsCodes"]["RminusG"], 0)
            self.assertEqual(frame["rowSpectralPeaks"]["RminusG"], [])
        self.assertFalse(result["rootCauseIdentified"])
        self.assertFalse(result["qualityAccepted"])
        json.dumps(result, allow_nan=False)

    def test_static_scene_rows_and_moving_phase_are_observations_not_causes(self):
        result = analyze(self.fixture([self.stripes(0), self.stripes(0), self.stripes(8)]), self.root)
        self.assertAlmostEqual(result["frames"][1]["previousFrameRowProfileCorrelation"]["RminusG"], 1, places=6)
        self.assertLess(result["frames"][2]["previousFrameRowProfileCorrelation"]["RminusG"], -.9)
        self.assertAlmostEqual(result["frames"][0]["rowSpectralPeaks"]["RminusG"][0]["periodRows"], 16)
        self.assertFalse(result["metadataAuthenticityVerified"])
        self.assertFalse(result["configurationEquivalenceVerified"])
        self.assertFalse(result["rootCauseIdentified"])

    def test_two_triplets_keep_the_full_recorded_sequence(self):
        result = analyze(self.fixture([self.flat()] * 6), self.root)
        self.assertEqual(result["frameCount"], 6)
        self.assertEqual(len(result["recordedTimestampIntervalsNs"]), 5)
        self.assertIsNone(result["frames"][1]["previousFrameRowProfileCorrelation"]["RminusG"])

    def test_tampered_image_or_journal_is_rejected(self):
        manifest = self.fixture([self.flat()] * 3)
        (self.root / "0.png").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "sha256_mismatch"):
            analyze(manifest, self.root)
        manifest = self.fixture([self.flat()] * 3)
        (self.root / "journal.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "sha256_mismatch"):
            analyze(manifest, self.root)

    def test_repeated_frame_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "frames_must_increase"):
            analyze(self.fixture([self.flat()] * 3, ids=[1, 1, 2]), self.root)

    def test_image_size_and_roi_must_match(self):
        with self.assertRaisesRegex(ValueError, "dimensions_must_match"):
            analyze(self.fixture([self.flat(), np.zeros((128, 65, 3)), self.flat()]), self.root)
        manifest = self.fixture([self.flat()] * 3)
        manifest["roi"]["x"] = 1
        with self.assertRaisesRegex(ValueError, "roi_outside_image"):
            analyze(manifest, self.root)

    def test_symlink_outside_root_is_rejected_even_with_correct_hash(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "journal.json"
            target.write_text("{}")
            manifest = self.fixture([self.flat()] * 3)
            (self.root / "outside.json").symlink_to(target)
            manifest["journal"] = {"file": "outside.json", "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "phase": "candidate"}
            with self.assertRaisesRegex(ValueError, "outside_root"):
                analyze(manifest, self.root)

    def test_cli_cannot_overwrite_the_input_journal(self):
        manifest = self.fixture([self.flat()] * 3)
        file = self.root / "manifest.json"
        file.write_text(json.dumps(manifest))
        journal = self.root / "journal.json"
        original = journal.read_bytes()
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("temporal_row_diagnostics.py")),
                                 str(file), "--root", str(self.root), "--output", str(journal)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FileExistsError", result.stderr)
        self.assertEqual(journal.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
