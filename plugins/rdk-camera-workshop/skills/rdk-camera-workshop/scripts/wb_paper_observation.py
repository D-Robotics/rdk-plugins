"""Read-only, hash-bound white-paper code observations; no device or calibration.

Requires NumPy, Pillow and OpenCV (SIFT). Registration is an image observation,
not SDK frame authentication, a physical lighting check or quality acceptance.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

import cv2
import numpy as np
from PIL import Image


def load(root, entry):
    if not isinstance(entry, dict) or set(entry) != {'file', 'sha256'}:
        raise ValueError('file_and_sha256_required')
    name, digest = entry['file'], entry['sha256']
    if not isinstance(name, str) or not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
        raise ValueError('invalid_image_binding')
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('image_outside_root_or_too_large')
    blob = path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != digest:
        raise ValueError('image_sha256_mismatch')
    with Image.open(BytesIO(blob)) as image:
        if image.format != 'PNG' or image.mode != 'RGB' or image.width * image.height > 16_000_000:
            raise ValueError('bounded_RGB_PNG_required')
        return np.asarray(image).copy()


def region(value, width, height):
    if not isinstance(value, list) or len(value) != 4 or any(type(v) is not int for v in value):
        raise ValueError('integer_roi_required')
    x, y, w, h = value
    if min(x, y) < 0 or min(w, h) < 8 or x + w > width or y + h > height:
        raise ValueError('roi_outside_image')
    return x, y, w, h


def observe(manifest, root):
    root = Path(root).resolve()
    if manifest.get('schema') != 'camera-wb-paper-observation-v1':
        raise ValueError('wb_paper_manifest_schema_required')
    reference = load(root, manifest['reference'])
    height, width = reference.shape[:2]
    rx, ry, rw, rh = region(manifest['registrationRoi'], width, height)
    motion_limit = manifest['motionLimitPixels']
    if type(motion_limit) not in (int, float) or not np.isfinite(motion_limit) or not 0 < motion_limit <= 20:
        raise ValueError('bounded_motion_limit_required')
    rois = manifest['paperRois']
    if not isinstance(rois, dict) or not 1 <= len(rois) <= 8:
        raise ValueError('one_to_eight_paper_rois_required')
    masks, coordinates = {}, {}
    for name, value in rois.items():
        if not isinstance(name, str) or not re.fullmatch('[a-zA-Z0-9_-]{1,60}', name):
            raise ValueError('invalid_paper_roi_name')
        x, y, w, h = coordinates[name] = region(value, width, height)
        a = reference[y:y+h, x:x+w].astype(float)
        mask = ((a.min(2) > 120) & (a.max(2) < 245) & (np.ptp(a, axis=2) < 60)).astype('uint8')
        masks[name] = cv2.erode(mask, np.ones((3, 3), np.uint8)) > 0
        if masks[name].sum() < 100:
            raise ValueError('insufficient_unsaturated_reference_paper_pixels')
    phases = manifest['phases']
    if not isinstance(phases, list) or not 2 <= len(phases) <= 8:
        raise ValueError('two_to_eight_phases_required')
    labels = [v.get('label') for v in phases]
    if any(not isinstance(v, str) or not re.fullmatch('[a-zA-Z0-9_-]{1,80}', v) for v in labels) or len(set(labels)) != len(labels):
        raise ValueError('unique_phase_labels_required')
    sift = cv2.SIFT_create(nfeatures=1800)
    registration_mask = np.zeros((height, width), np.uint8)
    registration_mask[ry:ry+rh, rx:rx+rw] = 255
    k1, d1 = sift.detectAndCompute(cv2.cvtColor(reference, cv2.COLOR_RGB2GRAY), registration_mask)
    corners = np.float32([[[rx, ry], [rx+rw, ry], [rx+rw, ry+rh], [rx, ry+rh]]])
    result = {'schema': 'camera-wb-paper-observation-result-v1', 'reference': manifest['reference'],
              'paperMaskPixels': {k: int(v.sum()) for k, v in masks.items()}, 'phases': [],
              'qualityAccepted': False, 'awbCalibrationQualified': False,
              'sdkFrameIdentityQualified': False, 'physicalLightingControlled': False,
              'scope': 'Fixed reference paper masks and image registration only; paper neutrality, camera controls, lighting and SDK identities require separate evidence. No candidate ranking or best selection.'}
    for phase in phases:
        frames = phase.get('frames')
        if not isinstance(frames, list) or not 3 <= len(frames) <= 8:
            raise ValueError('three_to_eight_frames_per_phase_required')
        if len({f['sha256'] for f in frames}) != len(frames):
            raise ValueError('duplicate_images_within_phase')
        entries = []
        for entry in frames:
            image = load(root, entry)
            if image.shape != reference.shape:
                raise ValueError('image_dimensions_changed')
            geometry = {'status': 'insufficient_features'}
            if entry['sha256'] == manifest['reference']['sha256']:
                geometry = {'status': 'identical_source', 'cornerMedianMovementPixels': 0.0}
            elif d1 is not None:
                k2, d2 = sift.detectAndCompute(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), None)
                if d2 is not None and len(d2) >= 2:
                    matches = [m for m, n in cv2.BFMatcher().knnMatch(d1, d2, k=2) if m.distance < .7*n.distance]
                    if len(matches) >= 12:
                        left = np.float32([k1[m.queryIdx].pt for m in matches])
                        right = np.float32([k2[m.trainIdx].pt for m in matches])
                        transform, inliers = cv2.findHomography(left, right, cv2.RANSAC, 3)
                        if transform is not None and inliers.sum() >= 12 and inliers.mean() >= .5:
                            moved = cv2.perspectiveTransform(corners, transform)
                            distance = float(np.median(np.linalg.norm(moved-corners, axis=2)))
                            if np.isfinite(distance):
                                geometry = {'status': 'within_limit' if distance <= motion_limit else 'changed',
                                            'cornerMedianMovementPixels': distance, 'inliers': int(inliers.sum())}
            papers = {}
            for name, (x, y, w, h) in coordinates.items():
                values = image[y:y+h, x:x+w][masks[name]].astype(float)
                papers[name] = {'BoverGMedian': float(np.median(values[:, 2]/np.maximum(1, values[:, 1]))),
                                'RoverGMedian': float(np.median(values[:, 0]/np.maximum(1, values[:, 1]))),
                                'meanRGB': values.mean(axis=0).tolist(),
                                'zeroGreenFraction': float(np.mean(values[:, 1] == 0)),
                                'clippedAt255Fraction': float(np.mean(values.max(axis=1) == 255))}
            registered = geometry['status'] in ('identical_source', 'within_limit')
            entries.append({**entry, 'geometry': geometry, 'paper': papers if registered else None})
        registered = all(e['geometry']['status'] in ('identical_source', 'within_limit') for e in entries)
        usable = registered and all(v['zeroGreenFraction'] == 0 and v['clippedAt255Fraction'] <= .01
                                    for e in entries for v in e['paper'].values())
        result['phases'].append({'label': phase['label'], 'frames': entries,
                                'geometryWithinLimitObserved': registered,
                                'paperUsableObserved': usable,
                                'paperMedian': {name: {key: float(np.median([e['paper'][name][key] for e in entries])) for key in ('BoverGMedian', 'RoverGMedian')} for name in masks} if usable else None})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    path = Path(args.manifest)
    if path.stat().st_size > 256 * 1024:
        raise ValueError('manifest_too_large')
    print(json.dumps(observe(json.loads(path.read_text()), args.root), indent=2))
