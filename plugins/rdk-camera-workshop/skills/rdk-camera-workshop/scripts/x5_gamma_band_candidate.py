"""Construct a bounded AUTO Gamma candidate, without any camera access.

Profile: observed 3044-byte X5 Gamma layout, 20x64 uint16 curves, endpoint1023.
Band values are curve output codes, not linear RAW exposure or calibrated Y.
Other models/layouts require fresh SDK/layout evidence. This is not a writer.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct


def candidate(blob, strength, lower, upper):
    if len(blob) != 3044 or struct.unpack_from('=i', blob, 0)[0] != 0:
        raise ValueError('observed_3044_byte_AUTO_gamma_required')
    if type(strength) not in (int, float) or not math.isfinite(strength) or not 0 < strength < 1:
        raise ValueError('finite_relative_strength_between_zero_and_one_required')
    if type(lower) is not int or type(upper) is not int or not 0 <= lower < upper <= 1023:
        raise ValueError('integer_band_in_observed_curve_code_domain_required')
    count = blob[4]
    if not 1 <= count <= 20:
        raise ValueError('actual_active_ISO_rows_required')
    gains = struct.unpack_from('=' + str(count) + 'f', blob, 8)
    if any(not math.isfinite(v) or v <= 0 for v in gains) or any(b <= a for a, b in zip(gains, gains[1:])):
        raise ValueError('positive_increasing_actual_gain_grid_required')
    out = bytearray(blob)
    changes = []
    for row in range(count):
        off = 88 + 128 * row
        old = struct.unpack_from('=64H', blob, off)
        if old[-1] != 1023 or any(v > 1023 for v in old) or any(b < a for a, b in zip(old, old[1:])):
            raise ValueError('observed_monotone_10bit_curve_endpoint_required')
        new = tuple(round(v - strength * (v - lower) * (1 - (v - lower) / (upper - lower)) ** 2)
                    if lower < v < upper else v for v in old)
        if any(not 0 <= v <= 1023 for v in new) or any(b < a for a, b in zip(new, new[1:])):
            raise ValueError('bounded_monotone_candidate_required')
        if any(a != b for a, b in zip(old, new) if a <= lower or a >= upper):
            raise ValueError('curve_outside_band_must_stay_original')
        struct.pack_into('=64H', out, off, *new)
        changes.append({'row': row, 'gain': gains[row], 'old': list(old), 'new': list(new)})
    allowed = {i for row in range(count) for i in range(88 + 128 * row, 88 + 128 * (row + 1))}
    if out == blob or any(i not in allowed for i, (a, b) in enumerate(zip(blob, out)) if a != b):
        raise ValueError('only_active_curve_bytes_and_nonnoop_required')
    result = bytes(out)
    return result, {'schema': 'camera-x5-gamma-band-candidate-v1', 'sourceSha256': hashlib.sha256(blob).hexdigest(),
                    'requestedSha256': hashlib.sha256(result).hexdigest(), 'strength': strength,
                    'lowerCurveCode': lower, 'upperCurveCode': upper, 'activeIsoRows': count,
                    'gainGrid': list(gains), 'curves': changes,
                    'hardwareQualified': False, 'qualityAccepted': False, 'deployed': False,
                    'physicalHaloCorrection': False, 'opticalResolutionQualified': False,
                    'requiresIndependentCurrentCurveReadbackAndOriginalRestoration': True,
                    'scope': 'Pure candidate construction for observed SDK layout. No fixed values are a universal sensor preset; actual AUTO interpolation/current response and visual tradeoffs require device verification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--strength', type=float, required=True)
    parser.add_argument('--lower', type=int, required=True)
    parser.add_argument('--upper', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.source.stat().st_size != 3044 or not re.fullmatch('[a-f0-9]{64}', args.source_sha256):
        raise ValueError('bounded_source_and_sha256_required')
    blob = args.source.read_bytes()
    if hashlib.sha256(blob).hexdigest() != args.source_sha256:
        raise ValueError('source_sha256_mismatch')
    requested, receipt = candidate(blob, args.strength, args.lower, args.upper)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(requested)
    print(json.dumps(receipt, allow_nan=False))


if __name__ == '__main__':
    main()
