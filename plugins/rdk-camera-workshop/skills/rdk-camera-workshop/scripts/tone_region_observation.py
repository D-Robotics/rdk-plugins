"""Read-only A/B/A PNG tone observations, without optical or quality acceptance.

Requires OpenCV, NumPy, and raw_row_coherence.py. Preserves SDK IDs including0;
metadata provenance, scene equivalence and physical illumination remain unverified.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

import cv2
import numpy as np
from raw_row_coherence import checked_file


def analyze(manifest, root):
    root = Path(root).resolve()
    if manifest.get('schema') != 'camera-tone-region-observation-v1':
        raise ValueError('tone_manifest_schema_required')
    receipt_path, blob = checked_file(root, root, manifest['receipt'])
    receipt = json.loads(blob)
    if any(receipt.get(k) is not True for k in ('resourceReleaseVerified', 'ispOriginalsRestored', 'streamObservedAndReleased')):
        raise ValueError('completed_capture_close_and_restoration_required')
    images = receipt['images']
    if not 9 <= len(images) <= 128 or len({x['name'] for x in images}) != len(images):
        raise ValueError('bounded_unique_image_receipt_required')
    entries = {x['name']: x for x in images}
    groups = manifest['groups']
    if set(groups) != {'baseline', 'candidate', 'restored'} or any(type(v) is not list or len(v) != 3 for v in groups.values()):
        raise ValueError('three_frames_each_ABA_group_required')
    names = [n for k in ('baseline', 'candidate', 'restored') for n in groups[k]]
    if any(type(n) is not str for n in names) or len(set(names)) != 9:
        raise ValueError('nine_distinct_recorded_images_required')

    def load(name):
        entry = entries[name]
        _, data = checked_file(root, receipt_path.parent, {'file': name, 'sha256': entry['sha256']})
        if len(data) < 29 or data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR' or data[24:26] != bytes([8, 2]):
            raise ValueError('eight_bit_RGB_PNG_required')
        width, height = struct.unpack('>II', data[16:24])
        if width <= 0 or height <= 0 or width * height > 16 * 1024 * 1024:
            raise ValueError('bounded_PNG_dimensions_required')
        meta = entry['frame']
        if any(type(meta.get(k)) is not int for k in ('width', 'height', 'frame_id', 'timestamp_ns')) or (meta['width'], meta['height']) != (width, height) or meta['frame_id'] < 0 or meta['timestamp_ns'] <= 0:
            raise ValueError('actual_image_metadata_required')
        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape != (height, width, 3) or image.dtype != np.uint8:
            raise ValueError('decoded_image_dimensions_required')
        return entry, cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    reference_name = manifest.get('maskReference', groups['baseline'][0])
    reference, reference_gray = load(reference_name)
    h, w = reference_gray.shape
    rois = manifest['roi']
    if set(rois) != {'paper', 'letters', 'lamp'}:
        raise ValueError('paper_letters_lamp_ROIs_required')
    for roi in rois.values():
        if set(roi) != {'x', 'y', 'width', 'height'} or any(type(v) is not int for v in roi.values()):
            raise ValueError('integer_ROI_geometry_required')
        if roi['x'] < 0 or roi['y'] < 0 or roi['width'] < 8 or roi['height'] < 8 or roi['x'] + roi['width'] > w or roi['y'] + roi['height'] > h:
            raise ValueError('ROI_outside_image_or_too_small')

    def crop(gray, key):
        r = rois[key]
        return gray[r['y']:r['y'] + r['height'], r['x']:r['x'] + r['width']]

    threshold = manifest.get('lampCoreThreshold', 240)
    ring_range = manifest.get('ringPixels', [15, 80])
    far_range = manifest.get('farPixels', [100, 160])
    if type(threshold) is not int or not 1 <= threshold <= 254 or any(type(x) is not list or len(x) != 2 for x in (ring_range, far_range)):
        raise ValueError('valid_fixed_lamp_masks_required')
    distances = ring_range + far_range
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in distances) or not 0 < distances[0] < distances[1] <= distances[2] < distances[3]:
        raise ValueError('ordered_finite_ring_distances_required')
    lamp = crop(reference_gray, 'lamp')
    count, labels, stats, _ = cv2.connectedComponentsWithStats((lamp >= threshold).astype(np.uint8), 8)
    if count < 2 or max(stats[1:, cv2.CC_STAT_AREA]) < 4:
        raise ValueError('baseline_bright_component_required')
    core = labels == 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    distance = cv2.distanceTransform((~core).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    ring = (distance >= distances[0]) & (distance < distances[1])
    far = (distance >= distances[2]) & (distance < distances[3])
    if min(int(ring.sum()), int(far.sum())) < 32:
        raise ValueError('enough_fixed_ring_samples_required')
    del reference_gray
    frames, summaries = [], []
    previous = 0
    for role in ('baseline', 'candidate', 'restored'):
        current = []
        for name in groups[role]:
            entry, gray = load(name)
            if gray.shape != (h, w) or entry['frame']['timestamp_ns'] <= previous:
                raise ValueError('fixed_dimensions_and_increasing_actual_timestamps_required')
            previous = entry['frame']['timestamp_ns']
            paper, letters, lamp = [crop(gray, k) for k in ('paper', 'letters', 'lamp')]
            p10, p90 = np.percentile(letters, [10, 90])
            controls = entry.get('verifiedControls')
            row = {'name': name, 'sha256': entry['sha256'], 'frame': entry['frame'], 'role': role,
                   'paperMeanCode': float(paper.mean()), 'letterP90MinusP10Codes': float(p90 - p10),
                   'lampRingMeanCode': float(lamp[ring].mean()), 'lampFarMeanCode': float(lamp[far].mean()),
                   'archivedReadbackSha256': hashlib.sha256(json.dumps(controls, sort_keys=True, allow_nan=False).encode()).hexdigest() if isinstance(controls, dict) else None}
            row['lampRingMinusFarCodes'] = row['lampRingMeanCode'] - row['lampFarMeanCode']
            frames.append(row)
            current.append(row)
        summaries.append({'role': role, **{k: float(np.mean([r[k] for r in current])) for k in ('paperMeanCode', 'letterP90MinusP10Codes', 'lampRingMeanCode', 'lampFarMeanCode', 'lampRingMinusFarCodes')}})
    baseline = summaries[0]
    changes = [{'role': row['role'], 'paperMeanRatio': row['paperMeanCode'] / baseline['paperMeanCode'] if baseline['paperMeanCode'] else None,
                'lampRingMeanDeltaCodes': row['lampRingMeanCode'] - baseline['lampRingMeanCode'],
                'lampContrastDeltaCodes': row['lampRingMinusFarCodes'] - baseline['lampRingMinusFarCodes']} for row in summaries[1:]]
    return {'schema': 'camera-tone-region-coded-observation-v1', 'receiptSha256': manifest['receipt']['sha256'], 'roi': rois,
            'maskReference': {'name': reference_name, 'sha256': reference['sha256']}, 'lampCoreThreshold': threshold,
            'ringPixels': ring_range, 'farPixels': far_range, 'ringMaskSha256': hashlib.sha256(ring.tobytes()).hexdigest(),
            'farMaskSha256': hashlib.sha256(far.tobytes()).hexdigest(), 'frames': frames, 'summary': summaries, 'changes': changes,
            'qualityAccepted': False, 'opticalHaloFixed': False, 'mtfQualified': False, 'metadataAuthenticity': False,
            'configurationEquivalence': False, 'physicalIlluminationControlled': False,
            'scope': 'Hash-bound processed code observations in fixed image coordinates; no physical halo, sharpness, calibration or automatic best-value acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(json.loads(args.manifest.read_text()), args.root)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')


if __name__ == '__main__':
    main()
