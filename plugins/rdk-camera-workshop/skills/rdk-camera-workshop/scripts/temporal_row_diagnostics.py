"""Read-only diagnostics of 3–8 hash-bound archived RGB PNG frames.

Requires NumPy and Pillow. Does not connect to a device, tune ISP, authenticate
SDK metadata, identify a physical cause, or accept image quality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image


def checked_file(root, base, name, digest):
    if not isinstance(name, str) or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("archive_path_and_sha256_required")
    path = (base / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("archive_path_outside_root")
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("archive_sha256_mismatch")
    return path


def positive_int(value):
    return type(value) is int and value > 0


def residual(profile, window):
    pad = window // 2
    return profile - np.convolve(np.pad(profile, (pad, pad), mode="edge"), np.ones(window) / window, mode="valid")


def rms(profile):
    value = float(np.sqrt(np.mean(profile * profile)))
    return 0.0 if value < 1e-8 else value


def correlation(left, right):
    left, right = left - left.mean(), right - right.mean()
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator < 1e-12:
        return None
    return float(np.clip(np.dot(left, right) / denominator, -1, 1))


def peaks(profile, window):
    if rms(profile) == 0:
        return []
    amplitudes = np.abs(np.fft.rfft(profile)) * 2 / len(profile)
    frequencies = np.fft.rfftfreq(len(profile))
    # Discard DC and periods longer than the explicitly selected detrend window.
    eligible = np.flatnonzero(frequencies >= 1 / window)
    eligible = eligible[np.argsort(amplitudes[eligible])[-3:][::-1]]
    return [{"periodRows": float(1 / frequencies[i]), "amplitudeCodes": float(amplitudes[i])} for i in eligible]


def analyze(manifest, root):
    root = Path(root).resolve()
    if manifest.get("schema") != "camera-temporal-row-diagnostics-v1":
        raise ValueError("temporal_row_manifest_schema_required")
    evidence = manifest["journal"]
    journal_path = checked_file(root, root, evidence["file"], evidence["sha256"])
    if journal_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("journal_too_large")
    journal = json.loads(journal_path.read_text())
    phases = [p for p in journal["phases"] if p["label"] == evidence["phase"]]
    if len(phases) != 1:
        raise ValueError("unique_archived_phase_required")
    phase = phases[0]
    frames = phase["images"] + phase.get("additionalImages", [])
    if not 3 <= len(frames) <= 8:
        raise ValueError("three_to_eight_frames_required")
    roi = manifest["roi"]
    if set(roi) != {"x", "y", "width", "height"} or any(type(v) is not int for v in roi.values()):
        raise ValueError("integer_roi_required")
    x, y, width, height = [roi[k] for k in ("x", "y", "width", "height")]
    window = manifest.get("detrendWindowRows", 65)
    if x < 0 or y < 0 or width < 16 or height < 3 or type(window) is not int or not 3 <= window <= min(height, 513) or window % 2 != 1:
        raise ValueError("valid_roi_and_odd_detrend_window_required")
    rows, profiles, intervals = [], [], []
    previous_meta = previous_pixels = dimensions = None
    seen = set()
    for entry in frames:
        path = checked_file(root, journal_path.parent, entry["name"], entry["sha256"])
        if str(path) in seen:
            raise ValueError("duplicate_archived_frame")
        seen.add(str(path))
        meta = entry["frame"]
        if not all(positive_int(meta.get(k)) for k in ("frame_id", "timestamp_ns", "width", "height")):
            raise ValueError("recorded_frame_identity_required")
        if previous_meta:
            if meta["frame_id"] <= previous_meta["frame_id"] or meta["timestamp_ns"] <= previous_meta["timestamp_ns"]:
                raise ValueError("recorded_frames_must_increase")
            intervals.append(meta["timestamp_ns"] - previous_meta["timestamp_ns"])
        with Image.open(path) as image:
            if image.format != "PNG" or image.mode != "RGB":
                raise ValueError("rgb_png_required")
            with path.open("rb") as source:
                header = source.read(26)
            if len(header) != 26 or header[12:16] != b"IHDR" or header[24:26] != bytes([8, 2]):
                raise ValueError("eight_bit_rgb_png_required")
            size = image.size
            if size != (meta["width"], meta["height"]) or size[0] * size[1] > 40_000_000:
                raise ValueError("png_dimensions_do_not_match_record")
            if dimensions is not None and size != dimensions:
                raise ValueError("all_png_dimensions_must_match")
            if x + width > size[0] or y + height > size[1]:
                raise ValueError("roi_outside_image")
            pixels = np.asarray(image.crop((x, y, x + width, y + height)), dtype=np.float32)
        rgb_rows = pixels.mean(axis=1, dtype=np.float64)
        values = {
            "lumaCode": rgb_rows @ np.array([.2126, .7152, .0722]),
            "RminusG": rgb_rows[:, 0] - rgb_rows[:, 1],
            "BminusG": rgb_rows[:, 2] - rgb_rows[:, 1],
        }
        detrended = {k: residual(v, window) for k, v in values.items()}
        gray = pixels.mean(axis=2)
        row = {
            "name": entry["name"], "sha256": entry["sha256"], "frameId": meta["frame_id"],
            "recordedTimestampNs": meta["timestamp_ns"], "roiMeanCode": float(pixels.mean()),
            "roiMedianGrayCode": float(np.median(gray)), "roiBelow16Fraction": float((gray < 16).mean()),
            "roiAnyChannelAtLeast250Fraction": float(np.any(pixels >= 250, axis=2).mean()),
            "rowResidualRmsCodes": {k: rms(v) for k, v in detrended.items()},
            "rowSpectralPeaks": {k: peaks(v, window) for k, v in detrended.items()},
        }
        if previous_pixels is not None:
            row["previousFrameRoiMeanAbsoluteCodeDifference"] = float(np.abs(pixels - previous_pixels).mean())
            row["previousFrameRowProfileCorrelation"] = {k: correlation(profiles[-1][k], v) for k, v in detrended.items()}
        rows.append(row)
        profiles.append(detrended)
        previous_meta, previous_pixels, dimensions = meta, pixels, size
    means = [r["roiMeanCode"] for r in rows]
    return {
        "schema": "camera-temporal-row-observation-v1", "journalSha256": evidence["sha256"],
        "phase": evidence["phase"], "frameCount": len(rows), "roi": roi, "detrendWindowRows": window,
        "frames": rows, "recordedTimestampIntervalsNs": intervals,
        "roiMeanCodeRange": {"minimum": min(means), "maximum": max(means), "span": max(means) - min(means)},
        "archiveHashesAndRecordedFrameSequenceVerified": True,
        "metadataAuthenticityVerified": False, "configurationEquivalenceVerified": False,
        "newHardwareProbePerformed": False, "qualityAccepted": False, "rootCauseIdentified": False,
        "limitations": [
            "Processed RGB code statistics, not Bayer RAW, calibrated noise, SNR or MTF.",
            "Archive consistency does not authenticate SDK metadata, scene or per-frame control state.",
            "Scene texture, motion, illumination and ISP behavior remain confounded without controlled comparisons.",
            "Recorded time intervals and row periods do not identify physical flicker frequency or a faulty sensor.",
            "No candidate ranking or improvement decision is inferred from these measurements.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, required=True, help="Allowed archive directory")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(json.loads(args.manifest.read_text()), args.root)
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        # Never overwrite a journal, image, or previous observation by accident.
        with args.output.open("x") as target:
            target.write(encoded)
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
