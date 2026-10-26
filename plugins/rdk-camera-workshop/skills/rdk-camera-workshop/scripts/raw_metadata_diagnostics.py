"""Inspect archived unpacked RAW10 for frame-ID pixel injection, without repairing bytes.

NumPy required. Accepts rejected forensic snapshots solely as diagnostic evidence.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from raw_row_coherence import checked_file


def analyze(manifest, root):
    root = Path(root).resolve()
    if manifest.get('schema') != 'camera-raw-metadata-diagnostics-v1':
        raise ValueError('raw_metadata_manifest_schema_required')
    receipt_path, blob = checked_file(root, root, manifest['receipt'])
    receipt = json.loads(blob)
    frames = receipt.get('rawFrames', [])
    if not 1 <= len(frames) <= 16 or receipt.get('resourceReleaseVerified') is not True:
        raise ValueError('bounded_released_diagnostic_frames_required')
    results, seen = [], set()
    for entry in frames:
        payload = entry.get('forensicPayload', entry)
        meta = entry['frame']
        keys = ('width', 'height', 'stride_y', 'size_y', 'stride_uv', 'size_uv', 'bit_depth', 'packing', 'frame_id', 'timestamp_ns')
        if any(type(meta.get(k)) is not int for k in keys):
            raise ValueError('integer_raw_metadata_required')
        w, h, stride = meta['width'], meta['height'], meta['stride_y']
        if w < 2 or h < 2 or w % 2 or h % 2 or stride < 2 * w or stride % 2 or meta['size_y'] != stride * h or meta['size_uv'] or meta['stride_uv'] or (meta['bit_depth'], meta['packing']) != (10, 0) or meta['frame_id'] < 0 or meta['timestamp_ns'] <= 0:
            raise ValueError('unpacked_raw10_diagnostic_layout_required')
        path, data = checked_file(root, receipt_path.parent, {'file': payload['name'], 'sha256': payload['sha256']})
        if path in seen or len(data) != stride * h:
            raise ValueError('duplicate_or_wrong_length_payload')
        if 'forensicPayload' in entry and payload.get('rawInterpretationAccepted') is not False:
            raise ValueError('rejected_payload_must_remain_rejected')
        seen.add(path)
        pixels = np.frombuffer(data, dtype='<u2').reshape(h, stride // 2)[:, :w]
        right_bad = pixels > 1023
        left_bad = (pixels & 63) != 0
        count = int(np.count_nonzero(right_bad))
        results.append({'name': payload['name'], 'sha256': payload['sha256'], 'sdkFrameId': meta['frame_id'], 'sdkTimestampNs': meta['timestamp_ns'], 'firstWord': int(pixels[0, 0]), 'firstWordEqualsFrameId': meta['frame_id'] > 0 and int(pixels[0, 0]) == meta['frame_id'], 'rightAlignedInvalidWords': count, 'leftAlignedInvalidWords': int(np.count_nonzero(left_bad)), 'soleRightAlignedInvalidWordIsFirst': count == 1 and bool(right_bad[0, 0]), 'sourceNativeCode': entry.get('nativeCode'), 'sourceRejectedSnapshot': 'forensicPayload' in entry})
    positive = [r for r in results if r['sdkFrameId'] > 0]
    repeated = len({r['sdkFrameId'] for r in positive}) >= 3 and all(r['firstWordEqualsFrameId'] for r in positive)
    overflow = any(r['sdkFrameId'] > 1023 and r['firstWordEqualsFrameId'] and r['soleRightAlignedInvalidWordIsFirst'] for r in positive)
    return {'schema': 'camera-raw-metadata-observation-v1', 'receiptSha256': manifest['receipt']['sha256'], 'frames': results, 'repeatedFirstWordFrameIdAssociation': repeated, 'frameIdOverflowExplainsRightAlignmentRejection': repeated and overflow, 'hardwareInjectionMechanismConfirmed': False, 'fullFrameColorBandRootCauseIdentified': False, 'formalRawAdmissionGranted': False, 'qualityAccepted': False, 'bytesModified': False, 'scope': 'Archived byte/SDK metadata association only. Confirm VIN configuration and controlled capture separately. Do not mask bits, synthesize frame IDs, or admit rejected snapshots as replay/calibration input.'}


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
