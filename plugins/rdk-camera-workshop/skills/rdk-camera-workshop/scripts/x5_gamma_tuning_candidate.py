"""Construct a complete typed tuning candidate from an actual Gamma baseline.

Pure JSON transformation, no device access or candidate registration. Requires
new full AUTO descriptors; only the observed common-curve profile is supported.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
from x5_gamma_band_candidate import candidate


def tuning_candidate(source, strength, lower, upper):
    if not isinstance(source, dict) or set(source) != {'kind', 'snapshotId', 'layoutHash', 'modules'} or source.get('kind') != 'x5-hbn-isp-v2':
        raise ValueError('actual_complete_typed_tuning_required')
    if not isinstance(source['snapshotId'], str) or not re.fullmatch('[a-f0-9]{32}', source['snapshotId']) or not isinstance(source['layoutHash'], str) or not re.fullmatch('[a-f0-9]{64}', source['layoutHash']):
        raise ValueError('actual_snapshot_and_layout_binding_required')
    try: gamma = source['modules']['gamma']
    except (KeyError, TypeError): raise ValueError('actual_gamma_module_required') from None
    if not isinstance(gamma, dict) or type(gamma.get('mode')) is not int or gamma['mode'] != 0:
        raise ValueError('actual_AUTO_gamma_required')
    count = gamma.get('auto_attr.auto_level'); gains = gamma.get('auto_attr.gain'); curves = gamma.get('auto_attr.curve')
    if type(count) is not int or not 1 <= count <= 20 or not isinstance(gains, list) or len(gains) != 20 or any(type(v) not in (int, float) or not math.isfinite(v) for v in gains):
        raise ValueError('observed_AUTO_grid_required')
    if not isinstance(curves, list) or len(curves) != 1280 or any(type(v) is not int or not 0 <= v <= 65535 for v in curves):
        raise ValueError('observed_full_20_by_64_curve_required')
    if any(curves[i * 64:(i + 1) * 64] != curves[:64] for i in range(count)):
        raise ValueError('common_active_curve_profile_required')
    raw = bytearray(3044); raw[4] = count; struct.pack_into('=20f', raw, 8, *gains); struct.pack_into('=1280H', raw, 88, *curves)
    requested, evidence = candidate(bytes(raw), strength, lower, upper)
    flat = list(struct.unpack_from('=1280H', requested, 88))
    if any(flat[i * 64] != curves[i * 64] or flat[i * 64 + 63] != curves[i * 64 + 63] for i in range(count)):
        raise ValueError('observed_curve_endpoints_must_stay_original')
    result = copy.deepcopy(source); result['modules']['gamma']['auto_attr.curve'] = flat
    # Ensure the complete output is finite JSON, including untouched modules.
    json.dumps(result, allow_nan=False)
    return result, {'schema': 'camera-x5-gamma-tuning-candidate-v1', 'sourceSnapshotId': source['snapshotId'],
                    'layoutHash': source['layoutHash'], 'activeRows': count, 'strength': strength,
                    'curveCodeBand': [lower, upper], 'changedField': '/modules/gamma/auto_attr.curve',
                    'hardwareQualified': False, 'qualityAccepted': False, 'deployed': False,
                    'candidateRegistered': False, 'adapterOperation': 'apply_tuning',
                    'requiresExplicitOperatorCurvePolicy': True,
                    'requiresIndependentTableAndCurrentCurveAfterFreshFrame': True,
                    'scope': 'Complete tuning JSON candidate, retaining all other modules/snapshot/layout bindings. Not a vendor library or an AI decision.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path); parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--strength', type=float, required=True); parser.add_argument('--lower', type=int, required=True); parser.add_argument('--upper', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    if not 0 < args.source.stat().st_size <= 2 * 1024 * 1024 or not re.fullmatch('[a-f0-9]{64}', args.source_sha256): raise ValueError('bounded_source_and_SHA_required')
    blob = args.source.read_bytes()
    if hashlib.sha256(blob).hexdigest() != args.source_sha256: raise ValueError('source_sha256_mismatch')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('duplicate_key')
            result[key] = value
        return result
    source = json.loads(blob, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))
    result, evidence = tuning_candidate(source, args.strength, args.lower, args.upper)
    output = (json.dumps(result, indent=2, allow_nan=False) + '\n').encode(); evidence.update(sourceSha256=args.source_sha256, requestedSha256=hashlib.sha256(output).hexdigest())
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as file: file.write(output)
    print(json.dumps(evidence, allow_nan=False))


if __name__ == '__main__': main()
