"""Read-only row associations for hash-bound SDK-matched RAW10 and NV12.

Requires NumPy and the sibling raw_row_coherence helper. No device operations.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import raw_row_coherence as raw_rows


def analyze(manifest, root):
    root = Path(root).resolve()
    if manifest.get('schema') != 'camera-paired-row-diagnostics-v1':
        raise ValueError('paired_row_manifest_schema_required')
    raw_manifest = dict(manifest, schema='camera-raw-row-coherence-v1')
    raw_result = raw_rows.analyze(raw_manifest, root)
    receipt_path, data = raw_rows.checked_file(root, root, manifest['receipt'])
    receipt = json.loads(data)
    if receipt.get('status') != 'observed' or receipt.get('resourceReleaseVerified') is not True or receipt.get('pairedBytesPersisted') is not True:
        raise ValueError('completed_owned_acquisition_and_release_required')
    x, y, width, height = [manifest['roi'][k] for k in ('x', 'y', 'width', 'height')]
    window = manifest.get('detrendWindowPhaseRows', 65)
    frames, differences, previous, seen, controls = [], [], None, set(), []
    for entry in receipt['rawFrames']:
        raw_meta, pair = entry['frame'], entry['ispPair']
        meta = pair['frame']
        if entry.get('ispPairVerified') is not True or pair.get('sdkFrameIdentityMatched') is not True or any(meta.get(k) != raw_meta[k] for k in ('width', 'height', 'frame_id', 'timestamp_ns')):
            raise ValueError('matching_sdk_frame_identity_required')
        if any(type(meta.get(k)) is not int for k in ('width', 'height', 'frame_id', 'timestamp_ns')):
            raise ValueError('integer_sdk_frame_identity_required')
        fields = ('stride_y', 'stride_uv', 'size_y', 'size_uv', 'bit_depth', 'packing')
        if any(type(meta.get(k)) is not int for k in fields):
            raise ValueError('integer_nv12_layout_required')
        w, h, sy, suv = [meta[k] for k in ('width', 'height', 'stride_y', 'stride_uv')]
        if meta['packing'] != 3 or meta['bit_depth'] != 8 or sy < w or suv < w or sy % 2 or suv % 2 or meta['size_y'] != sy * h or meta['size_uv'] != suv * h // 2:
            raise ValueError('nv12_layout_required')
        _, blob = raw_rows.checked_file(root, receipt_path.parent, {'file': entry['name'], 'sha256': entry['sha256']})
        raw = np.frombuffer(blob, '<u2').reshape(h, raw_meta['stride_y'] // 2)[:, :w]
        if raw_meta['alignment'] == 1:
            raw = raw >> 6
        path, blob = raw_rows.checked_file(root, receipt_path.parent, {'file': pair['name'], 'sha256': pair['sha256']})
        if path in seen or len(blob) != meta['size_y'] + meta['size_uv']:
            raise ValueError('duplicate_or_wrong_length_nv12')
        seen.add(path)
        luma = np.frombuffer(blob[:meta['size_y']], 'u1').reshape(h, sy)[:, :w]
        chroma = np.frombuffer(blob[meta['size_y']:], 'u1').reshape(h // 2, suv)[:, :w]
        phases = {f'{py}{px}': raw[y + py:y + height:2, x + px:x + width:2].mean(axis=1) for py in range(2) for px in range(2)}
        values = {
            'rawColumnPhaseContrast': (phases['00'] + phases['10'] - phases['01'] - phases['11']) / 2,
            'rawMean': sum(phases.values()) / 4,
            'ispU': chroma[y // 2:(y + height) // 2, x:x + width:2].mean(axis=1),
            'ispV': chroma[y // 2:(y + height) // 2, x + 1:x + width:2].mean(axis=1),
            'ispY': luma[y:y + height, x:x + width].reshape(height // 2, 2, width).mean(axis=(1, 2)),
        }
        residuals = {k: raw_rows.residual(v, window) for k, v in values.items()}
        frame = {'frameId': raw_meta['frame_id'], 'recordedSdkTimestampNs': raw_meta['timestamp_ns'], 'rawSha256': entry['sha256'], 'nv12Sha256': pair['sha256'], 'rowResidualRmsCodes': {k: raw_rows.rms(v) for k, v in residuals.items()}, 'rawPhaseContrastVsIspChromaCorrelation': {k: raw_rows.correlation(residuals['rawColumnPhaseContrast'], residuals[k]) for k in ('ispU', 'ispV')}}
        if previous:
            delta = {k: raw_rows.residual(values[k] - previous['values'][k], window) for k in values}
            differences.append({'fromFrameId': previous['id'], 'toFrameId': raw_meta['frame_id'], 'rawPhaseContrastVsIspChromaCorrelation': {k: raw_rows.correlation(delta['rawColumnPhaseContrast'], delta[k]) for k in ('ispU', 'ispV')}, 'rawMeanVsIspYCorrelation': raw_rows.correlation(delta['rawMean'], delta['ispY'])})
        before, after = entry.get('mipiBefore', {}).get('values'), entry.get('mipiAfter', {}).get('values')
        covered = isinstance(before, dict) and isinstance(after, dict) and bool(before) and set(before) == set(after) and all(type(v) is int and v >= 0 for v in [*before.values(), *after.values()])
        frame['mipiCounterCoveragePresent'] = covered
        if covered:
            frame['mipiNonzeroBefore'] = {k: v for k, v in before.items() if v}
            frame['mipiNonzeroAfter'] = {k: v for k, v in after.items() if v}
            frame['mipiCounterDecreased'] = any(after[k] < before[k] for k in before)
        frames.append(frame)
        for name in ('controlReadbackBefore', 'controlReadbackAfter'):
            evidence = entry.get(name, {})
            exposure = evidence.get('exposure', {})
            controls.append(exposure.get('values') if exposure.get('sdkCode') == 0 else None)
        previous = {'id': raw_meta['frame_id'], 'values': values}
    exposure_present = all(isinstance(v, dict) and bool(v) for v in controls)
    return {'schema': 'camera-paired-row-observation-v1', 'receiptSha256': manifest['receipt']['sha256'], 'roi': manifest['roi'], 'detrendWindowPhaseRows': window, 'frameCount': len(frames), 'frames': frames, 'temporalDifferences': differences, 'observedExposureValuesStable': exposure_present and all(v == controls[0] for v in controls), 'sdkFrameIdentityMatched': True, 'bayerQualified': False, 'physicalExposureCertified': False, 'spatialRegistrationCertified': False, 'metadataAuthenticity': False, 'rootCauseIdentified': False, 'qualityAccepted': False, 'scope': 'Archived code associations only; ISP temporal processing includes history. Zero exported MIPI counters do not certify hardware. Unlabelled RAW phases are not RGB; no unique lighting/electronics/transport cause is inferred.', 'rawSourceFrameCount': len(raw_result['frames'])}


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
