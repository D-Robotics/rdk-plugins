"""Read-only row observations from hash-bound unpacked RAW10 archives.

Requires NumPy. Keeps Bayer phases unlabeled; never tunes or calibrates a camera.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np


def checked_file(root, base, entry):
    name, digest = entry['file'], entry['sha256']
    if not isinstance(name, str) or not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
        raise ValueError('archive_path_and_sha256_required')
    path = (base / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('archive_path_outside_root_or_missing')
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('archive_file_too_large')
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != digest:
        raise ValueError('archive_sha256_mismatch')
    return path, blob


def residual(values, window):
    pad = window // 2
    return values - np.convolve(np.pad(values, (pad, pad), mode='edge'), np.ones(window) / window, mode='valid')


def rms(values):
    return float(np.sqrt(np.mean(values * values)))


def correlation(left, right):
    left, right = left - left.mean(), right - right.mean()
    norm = float(np.linalg.norm(left) * np.linalg.norm(right))
    return None if norm < 1e-12 else float(np.clip(np.dot(left, right) / norm, -1, 1))


def analyze(manifest, root):
    root = Path(root).resolve()
    if manifest.get('schema') != 'camera-raw-row-coherence-v1':
        raise ValueError('raw_row_manifest_schema_required')
    receipt_path, blob = checked_file(root, root, manifest['receipt'])
    receipt = json.loads(blob)
    frames = receipt['rawFrames']
    if not 3 <= len(frames) <= 8 or receipt.get('rawCalls') != len(frames) or receipt.get('rawTransportVerified') is not True or receipt.get('rawBytesPersisted') is not True:
        raise ValueError('three_to_eight_recorded_raw_transports_required')
    roi = manifest['roi']
    if set(roi) != {'x', 'y', 'width', 'height'} or any(type(v) is not int or v % 2 for v in roi.values()):
        raise ValueError('even_integer_roi_required')
    x, y, width, height = [roi[k] for k in ('x', 'y', 'width', 'height')]
    window = manifest.get('detrendWindowPhaseRows', 65)
    if x < 0 or y < 0 or width < 32 or height < 6 or type(window) is not int or window % 2 != 1 or not 3 <= window <= min(height // 2, 513):
        raise ValueError('valid_roi_and_odd_phase_row_window_required')
    previous_meta = previous_roi = dimensions = None
    results, differences, seen = [], [], set()
    for frame in frames:
        meta = frame['frame']
        keys = ('width', 'height', 'stride_y', 'stride_uv', 'size_y', 'size_uv', 'bit_depth', 'bayer', 'packing', 'alignment', 'frame_id', 'timestamp_ns')
        if any(type(meta.get(k)) is not int for k in keys):
            raise ValueError('integer_raw_metadata_required')
        w, h, stride = meta['width'], meta['height'], meta['stride_y']
        if w <= 0 or h <= 0 or w % 2 or h % 2 or stride < w * 2 or stride % 2 or meta['size_y'] != stride * h or stride * h > 32 * 1024 * 1024 or meta['size_uv'] or meta['stride_uv'] or (meta['bit_depth'], meta['packing'], meta['bayer']) != (10, 0, 0xffffffff) or meta['alignment'] not in (0, 1):
            raise ValueError('unknown_bayer_unpacked_raw10_required')
        if frame.get('nativeCode') != 0 or meta['frame_id'] <= 0 or meta['timestamp_ns'] <= 0:
            raise ValueError('recorded_successful_raw_identity_required')
        if previous_meta and (meta['frame_id'] <= previous_meta['frame_id'] or meta['timestamp_ns'] <= previous_meta['timestamp_ns']):
            raise ValueError('recorded_raw_frames_must_increase')
        if dimensions is not None and dimensions != (w, h):
            raise ValueError('raw_dimensions_must_match')
        if x + width > w or y + height > h:
            raise ValueError('roi_outside_raw')
        path, data = checked_file(root, receipt_path.parent, {'file': frame['name'], 'sha256': frame['sha256']})
        if path in seen or len(data) != stride * h:
            raise ValueError('duplicate_or_wrong_length_raw')
        seen.add(path)
        pixels = np.frombuffer(data, dtype='<u2').reshape(h, stride // 2)[:, :w]
        right, left = bool((pixels <= 1023).all()), bool(((pixels & 63) == 0).all())
        if right == left or meta['alignment'] != (0 if right else 1):
            raise ValueError('unique_raw_alignment_required')
        if left:
            pixels = pixels >> 6
        pixels = pixels[y:y + height, x:x + width].astype(np.float64)
        entry = {'name': frame['name'], 'sha256': frame['sha256'], 'frame': meta, 'phases': {}}
        for py in range(2):
            for px in range(2):
                phase = pixels[py::2, px::2]
                profile = residual(phase.mean(axis=1), window)
                entry['phases'][f'{py}{px}'] = {'meanCode': float(phase.mean()), 'rowResidualRmsCodes': rms(profile)}
        results.append(entry)
        if previous_roi is not None:
            delta = pixels - previous_roi
            diff = {'fromFrameId': previous_meta['frame_id'], 'toFrameId': meta['frame_id'], 'recordedSdkDeltaNs': meta['timestamp_ns'] - previous_meta['timestamp_ns'], 'phases': {}}
            profiles = []
            for py in range(2):
                for px in range(2):
                    phase = delta[py::2, px::2]
                    profile = residual(phase.mean(axis=1), window)
                    profiles.append(profile)
                    diff['phases'][f'{py}{px}'] = {'rowMeanChangeCodes': float(phase.mean()), 'detrendedRowDifferenceRmsCodes': rms(profile), 'alternatingColumnCorrelation': correlation(residual(phase[:, ::2].mean(axis=1), window), residual(phase[:, 1::2].mean(axis=1), window))}
            diff['unlabelledPhaseCorrelations'] = [[correlation(a, b) for b in profiles] for a in profiles]
            differences.append(diff)
        previous_meta, previous_roi, dimensions = meta, pixels, (w, h)
    return {'schema': 'camera-raw-row-coherence-observation-v1', 'receiptSha256': manifest['receipt']['sha256'], 'roi': roi, 'detrendWindowPhaseRows': window, 'frames': results, 'temporalDifferences': differences, 'qualityAccepted': False, 'rootCauseIdentified': False, 'bayerQualified': False, 'metadataAuthenticity': False, 'configurationEquivalence': False, 'sameFrameIspPairing': False, 'scope': 'Archived RAW code and row associations only; no RGB labels, calibration, physical exposure, flicker frequency, or automatic sensor diagnosis.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = analyze(json.loads(args.manifest.read_text()), args.root)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')


if __name__ == '__main__':
    main()
