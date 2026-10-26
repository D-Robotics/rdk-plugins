"""Read-only code-edge profiles from hash-bound diagnostic RAW10/NV12 pairs.

Requires NumPy and raw_row_coherence.py. No demosaic, MTF, optical diagnosis,
formal same-frame admission, camera control, or automatic quality acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from raw_row_coherence import checked_file


def geometry(meta, raw):
    keys = ('width', 'height', 'stride_y', 'stride_uv', 'size_y', 'size_uv',
            'bit_depth', 'bayer', 'packing', 'alignment', 'frame_id', 'timestamp_ns')
    if any(type(meta.get(k)) is not int for k in keys):
        raise ValueError('integer_actual_metadata_required')
    w, h, stride = meta['width'], meta['height'], meta['stride_y']
    if w <= 0 or h <= 0 or w % 2 or h % 2 or w * h > 16 * 1024 * 1024 or meta['frame_id'] < 0 or meta['timestamp_ns'] <= 0:
        raise ValueError('bounded_even_geometry_and_actual_metadata_required')
    if meta['size_y'] != stride * h:
        raise ValueError('exact_y_plane_size_required')
    if raw:
        if stride < 2 * w or stride % 2 or meta['stride_uv'] or meta['size_uv'] or (meta['bit_depth'], meta['bayer'], meta['packing'], meta['alignment']) != (10, 0xffffffff, 0, 0):
            raise ValueError('unlabelled_unpacked_right_aligned_RAW10_required')
    elif stride < w or meta['stride_uv'] < w or meta['size_uv'] != meta['stride_uv'] * (h // 2) or (meta['bit_depth'], meta['packing'], meta['alignment']) != (8, 3, 0):
        raise ValueError('actual_NV12_plane_layout_required')
    if meta['size_y'] + meta['size_uv'] > 32 * 1024 * 1024:
        raise ValueError('bounded_payload_required')
    return w, h, stride


def edge_profile(image, edge, py, px):
    xs = np.arange(edge['x'][0] + px, edge['x'][1], 2)
    ys = np.arange(edge['y'][0] + py, edge['y'][1], 2)
    profile = image[np.ix_(ys, xs)].mean(axis=0)
    dark = (xs >= edge['dark'][0]) & (xs < edge['dark'][1])
    bright = (xs >= edge['bright'][0]) & (xs < edge['bright'][1])
    if min(int(dark.sum()), int(bright.sum())) < 2 or len(ys) < 3:
        raise ValueError('two_plateau_samples_and_three_rows_each_phase_required')
    low, high = float(profile[dark].mean()), float(profile[bright].mean())
    if high - low < 3:
        raise ValueError('observed_rising_edge_contrast_at_least_three_codes_required')
    normal = (profile - low) / (high - low)
    start = np.flatnonzero(dark)[np.argmin(profile[dark])]

    def crossing(value):
        for i in range(start, len(xs) - 1):
            if normal[i] <= value <= normal[i + 1] and normal[i + 1] > normal[i]:
                return float(xs[i] + (value - normal[i]) / (normal[i + 1] - normal[i]) * (xs[i + 1] - xs[i]))
        raise ValueError('observed_rising_crossing_required')

    x10, x90 = crossing(.1), crossing(.9)
    if x90 <= x10:
        raise ValueError('ordered_edge_crossings_required')
    return {'x10': x10, 'x90': x90, 'width10to90FullResolutionPixels': x90 - x10,
            'lowCode': low, 'highCode': high, 'profileX': xs.tolist(), 'profileCodes': profile.tolist()}


def analyze(manifest, root):
    root = Path(root).resolve()
    if manifest.get('schema') != 'camera-raw-isp-edge-observation-v1':
        raise ValueError('edge_manifest_schema_required')
    path, blob = checked_file(root, root, manifest['receipt'])
    receipt = json.loads(blob)
    required = ('rawBytesPersisted', 'resourceReleaseVerified', 'ispOriginalsRestored',
                'diagnosticRawSnapshotsComplete', 'streamObservedAndReleased')
    if any(receipt.get(k) is not True for k in required) or receipt.get('rawTransportVerified') is not False or receipt.get('rawBayerQualified') is not False:
        raise ValueError('completed_restored_separate_diagnostic_scope_required')
    recorded = receipt['rawFrames']
    if not 3 <= len(recorded) <= 12 or receipt.get('rawCalls') != len(recorded) or len({f['name'] for f in recorded}) != len(recorded):
        raise ValueError('bounded_unique_recorded_raw_calls_required')
    selected = manifest['rawNames']
    if type(selected) is not list or not 3 <= len(selected) <= 8 or any(type(n) is not str for n in selected) or len(set(selected)) != len(selected):
        raise ValueError('three_to_eight_distinct_selected_raws_required')
    entries = {f['name']: f for f in recorded}
    edges = manifest['edges']
    if type(edges) is not list or not 1 <= len(edges) <= 8 or len({e['name'] for e in edges}) != len(edges):
        raise ValueError('bounded_named_edges_required')
    previous = 0
    shape = controls = None
    rows = []
    selected_evidence = []
    for name in selected:
        f = entries[name]
        pair = f['ispPair']
        meta, isp_meta = f['frame'], pair['frame']
        w, h, stride = geometry(meta, True)
        iw, ih, istride = geometry(isp_meta, False)
        if type(f.get('nativeCode')) is not int or f['nativeCode'] != 0 or pair.get('sdkTimestampMatched') is not True or meta['timestamp_ns'] != isp_meta['timestamp_ns'] or meta['timestamp_ns'] <= previous or (w, h) != (iw, ih):
            raise ValueError('successful_ordered_actual_timestamp_pairs_required')
        if shape is not None and shape != (w, h, stride, istride):
            raise ValueError('fixed_selected_pair_geometry_required')
        shape, previous = (w, h, stride, istride), meta['timestamp_ns']
        for label in ('controlReadbackBefore', 'controlReadbackAfter'):
            c = f[label]
            values = {}
            for module in ('exposure', 'awb'):
                if type(c[module]['sdkCode']) is not int or c[module]['sdkCode'] != 0 or type(c[module]['values'].get('mode')) is not int or c[module]['values']['mode'] != 1:
                    raise ValueError('archived_successful_manual_readbacks_required')
                values[module] = c[module]['values']
            if controls is not None and values != controls:
                raise ValueError('selected_readback_values_must_stay_fixed')
            controls = values
        _, raw = checked_file(root, path.parent, {'file': name, 'sha256': f['sha256']})
        _, isp = checked_file(root, path.parent, {'file': pair['name'], 'sha256': pair['sha256']})
        if len(raw) != meta['size_y'] or len(isp) != isp_meta['size_y'] + isp_meta['size_uv']:
            raise ValueError('exact_selected_payload_sizes_required')
        a = np.frombuffer(raw, '<u2').reshape(h, stride // 2)[:, :w]
        b = np.frombuffer(isp, np.uint8)[:isp_meta['size_y']].reshape(h, istride)[:, :w]
        if not (a <= 1023).all():
            raise ValueError('RAW10_sample_range_required')
        selected_evidence.append({'rawName': name, 'rawSha256': f['sha256'], 'ispName': pair['name'],
                                  'ispSha256': pair['sha256'], 'rawFrame': meta, 'ispFrame': isp_meta,
                                  'readbackValuesSha256': hashlib.sha256(json.dumps(values, sort_keys=True, allow_nan=False).encode()).hexdigest()})
        for edge in edges:
            if set(edge) != {'name', 'x', 'y', 'dark', 'bright'} or type(edge['name']) is not str or not edge['name']:
                raise ValueError('named_profile_geometry_required')
            for key in ('x', 'y', 'dark', 'bright'):
                v = edge[key]
                if type(v) is not list or len(v) != 2 or any(type(n) is not int for n in v) or v[0] < 0 or v[1] <= v[0]:
                    raise ValueError('integer_ordered_profile_intervals_required')
            if edge['x'][0] % 2 or edge['y'][0] % 2 or edge['x'][1] > w or edge['y'][1] > h or not edge['x'][0] <= edge['dark'][0] < edge['dark'][1] <= edge['bright'][0] < edge['bright'][1] <= edge['x'][1]:
                raise ValueError('even_origin_inside_frame_ordered_plateaus_required')
            for py in (0, 1):
                for px in (0, 1):
                    rows.append({'rawName': name, 'edge': edge['name'], 'phase': f'{py}{px}',
                                 'raw': edge_profile(a, edge, py, px), 'ispY': edge_profile(b, edge, py, px)})
    summary = []
    for edge in edges:
        for label in ('raw', 'ispY'):
            values = [v[label]['width10to90FullResolutionPixels'] for v in rows if v['edge'] == edge['name']]
            summary.append({'edge': edge['name'], 'stream': label, 'medianObservedCodeWidth': float(np.median(values)),
                            'minimum': min(values), 'maximum': max(values), 'count': len(values)})
    return {'schema': 'camera-raw-isp-code-edge-result-v1', 'receiptSha256': manifest['receipt']['sha256'],
            'selectedEvidence': selected_evidence, 'edges': edges, 'profiles': rows, 'summary': summary,
            'sameSdkTimestampObserved': True, 'formalFrameIdentityQualified': False, 'bayerQualified': False,
            'mtfQualified': False, 'opticalFocusCauseQualified': False, 'qualityAccepted': False,
            'metadataAuthenticity': False, 'physicalIlluminationControlled': False,
            'scope': 'Selected real code edges only. Unlabelled RAW phases and nonlinear ISP Y are not calibrated PSF/MTF or an all-frame sharpness/optical diagnosis.'}


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
