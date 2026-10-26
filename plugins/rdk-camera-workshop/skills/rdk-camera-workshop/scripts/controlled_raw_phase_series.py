"""Observe controlled RAW phase series; no camera access or calibration grant.

Requires NumPy and raw_row_coherence.py. Diagnostic SDK IDs may be zero;
actual timestamps and control readbacks are retained without creating frame IDs.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from raw_row_coherence import checked_file, correlation, residual, rms


def analyze(manifest, root):
    root = Path(root).resolve()
    if manifest.get('schema') != 'camera-controlled-raw-phase-series-v1':
        raise ValueError('controlled_series_schema_required')
    path, data = checked_file(root, root, manifest['receipt'])
    receipt = json.loads(data)
    required = ('rawBytesPersisted', 'resourceReleaseVerified', 'ispOriginalsRestored',
                'diagnosticRawSnapshotsComplete', 'streamObservedAndReleased')
    if any(receipt.get(k) is not True for k in required):
        raise ValueError('completed_diagnostic_bytes_close_and_restoration_required')
    if receipt.get('rawTransportVerified') is not False or receipt.get('rawBayerQualified') is not False:
        raise ValueError('separate_unqualified_diagnostic_scope_required')
    frames = receipt['rawFrames']
    if len(frames) != 12 or receipt.get('rawCalls') != 12:
        raise ValueError('four_phases_of_three_recorded_frames_required')
    roi = manifest['roi']
    if set(roi) != {'x', 'y', 'width', 'height'} or any(type(v) is not int or v % 2 for v in roi.values()):
        raise ValueError('even_integer_roi_required')
    x, y, width, height = [roi[k] for k in ('x', 'y', 'width', 'height')]
    window = manifest.get('detrendWindowPhaseRows', 15)
    if x < 0 or y < 0 or width < 32 or height < 6 or type(window) is not int or window % 2 != 1 or not 3 <= window <= min(height // 2, 513):
        raise ValueError('valid_roi_and_odd_phase_row_window_required')
    previous_time = 0
    dimensions = None
    awb = None
    other_gains = None
    seen = set()
    previous = {}
    results, differences = [], []
    phase_controls = {}
    for number, frame in enumerate(frames):
        phase = number // 3
        if type(frame.get('gainPhase')) is not int or frame['gainPhase'] != phase:
            raise ValueError('ordered_three_frames_per_phase_required')
        gain, exposure = frame['sdkAgain'], frame['sdkIntegrationSeconds']
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (gain, exposure)):
            raise ValueError('finite_positive_sdk_controls_required')
        if phase in phase_controls and phase_controls[phase] != (gain, exposure):
            raise ValueError('frozen_phase_controls_required')
        phase_controls[phase] = (gain, exposure)
        for key in ('controlReadbackBefore', 'controlReadbackAfter'):
            control = frame[key]
            exp = control['exposure']['values']
            white = control['awb']['values']
            if control['exposure']['sdkCode'] != 0 or control['awb']['sdkCode'] != 0 or exp.get('mode') != 1 or white.get('mode') != 1 or exp.get('manual_attr.again') != gain or exp.get('manual_attr.exp_time') != exposure:
                raise ValueError('actual_frozen_manual_readbacks_required')
            extra = tuple(exp.get(k) for k in ('manual_attr.dgain', 'manual_attr.ispgain'))
            white_gains = tuple(white.get('manual_attr.gain.' + k) for k in ('rgain', 'grgain', 'gbgain', 'bgain'))
            if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in extra + white_gains):
                raise ValueError('complete_positive_digital_and_white_gains_required')
            if other_gains is not None and extra != other_gains:
                raise ValueError('other_exposure_gains_must_stay_fixed')
            other_gains = extra
            if awb is not None and awb != white:
                raise ValueError('white_balance_must_stay_fixed')
            awb = white
        meta = frame['frame']
        keys = ('width', 'height', 'stride_y', 'stride_uv', 'size_y', 'size_uv', 'bit_depth', 'bayer', 'packing', 'alignment', 'frame_id', 'timestamp_ns')
        if any(type(meta.get(k)) is not int for k in keys):
            raise ValueError('integer_metadata_required')
        w, h, stride = meta['width'], meta['height'], meta['stride_y']
        if w <= 0 or h <= 0 or w % 2 or h % 2 or stride < w * 2 or stride % 2 or meta['size_y'] != stride * h or stride * h > 32 * 1024 * 1024 or meta['size_uv'] or meta['stride_uv'] or (meta['bit_depth'], meta['packing'], meta['bayer'], meta['alignment']) != (10, 0, 0xffffffff, 0):
            raise ValueError('unknown_bayer_right_aligned_unpacked_raw10_required')
        if type(frame.get('nativeCode')) is not int or frame['nativeCode'] != 0 or meta['frame_id'] < 0 or meta['timestamp_ns'] <= previous_time:
            raise ValueError('successful_native_and_strict_actual_timestamp_required')
        if dimensions is not None and dimensions != (w, h, stride):
            raise ValueError('fixed_dimensions_required')
        dimensions, previous_time = (w, h, stride), meta['timestamp_ns']
        if x + width > w or y + height > h:
            raise ValueError('roi_outside_frame')
        source, blob = checked_file(root, path.parent, {'file': frame['name'], 'sha256': frame['sha256']})
        if source in seen or len(blob) != stride * h:
            raise ValueError('unique_payload_path_and_exact_size_required')
        seen.add(source)
        pixels = np.frombuffer(blob, '<u2').reshape(h, stride // 2)[:, :w]
        if not (pixels <= 1023).all():
            raise ValueError('out_of_range_raw_samples')
        pixels = pixels[y:y + height, x:x + width].astype(np.float64)
        profiles = [pixels[py::2, px::2] for py in range(2) for px in range(2)]
        rows = [residual(v.mean(axis=1), window) for v in profiles]
        contrast = (rows[0] + rows[2] - rows[1] - rows[3]) / 2
        results.append({'name': frame['name'], 'sha256': frame['sha256'], 'frame': meta,
                        'phase': phase, 'sdkGain': gain, 'sdkExposureSeconds': exposure,
                        'meanCode': float(pixels.mean()), 'columnPhaseRowRmsCodes': rms(contrast)})
        if phase in previous:
            before, before_meta = previous[phase]
            delta = [residual((a - b).mean(axis=1), window) for a, b in zip(profiles, before)]
            differences.append({'phase': phase, 'fromActualSdkFrameId': before_meta['frame_id'],
                                'toActualSdkFrameId': meta['frame_id'],
                                'timestampDeltaNs': meta['timestamp_ns'] - before_meta['timestamp_ns'],
                                'columnPhaseRowDeltaRmsCodes': rms((delta[0] + delta[2] - delta[1] - delta[3]) / 2),
                                'unlabelledPhaseCorrelations': [[correlation(a, b) for b in delta] for a in delta]})
        previous[phase] = profiles, meta
    return {'schema': 'camera-controlled-raw-phase-observation-v1', 'receiptSha256': manifest['receipt']['sha256'],
            'roi': roi, 'detrendWindowPhaseRows': window, 'frames': results, 'temporalDifferences': differences,
            'sameFrameIspPairing': False, 'metadataAuthenticity': False, 'physicalGainExposureCertified': False,
            'coveredDarkField': False, 'bayerQualified': False, 'rootCauseIdentified': False,
            'qualityAccepted': False, 'scope': 'Recorded frozen-control RAW code associations; no RGB labels, ISP pair admission, physical cause, calibration or automatic best-parameter selection.'}


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
