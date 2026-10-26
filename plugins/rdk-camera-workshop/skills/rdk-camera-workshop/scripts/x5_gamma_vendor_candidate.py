"""Render a Gamma-only vendor JSON from an exactly matching X5 AUTO snapshot.

No device access. Uses the observed AGC_2 non-HDR table mapping, not a generic
sensor schema. A fresh SDK reload/current-curve check and restore remain required.
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


def render(template, source, requested):
    if not 0 < len(template) <= 8 * 1024 * 1024:
        raise ValueError('bounded_vendor_template_required')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('duplicate_vendor_key')
            result[key] = value
        return result
    try:
        doc = json.loads(template, object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('vendor_json_invalid') from exc
    if len(source) != 3044 or len(requested) != 3044 or struct.unpack_from('=i', source)[0] != 0:
        raise ValueError('observed_3044_byte_AUTO_source_required')
    count = source[4]
    if not 1 <= count <= 20:
        raise ValueError('active_rows_required')
    end = 88 + 128 * count
    if source[:88] != requested[:88] or source[end:] != requested[end:] or source == requested:
        raise ValueError('only_active_curve_changes_required')
    gains = list(struct.unpack_from('=20f', source, 8))
    if any(not math.isfinite(v) or v <= 0 for v in gains[:count]) or any(b <= a for a, b in zip(gains[:count], gains[1:count])):
        raise ValueError('active_gain_grid_invalid')
    try: table = doc['tuning']['AGC_2']['tables'][0]
    except (KeyError, TypeError, IndexError) as exc: raise ValueError('observed_vendor_mapping_required') from exc
    if not isinstance(table, dict): raise ValueError('vendor_table_object_required')
    vendor_gains = table.get('gains')
    if not isinstance(vendor_gains, list) or len(vendor_gains) != 20 or any(type(v) not in (int, float) or not math.isfinite(v) for v in vendor_gains):
        raise ValueError('finite_numeric_vendor_gain_grid_required')
    if table.get('hdr') is not False or vendor_gains != gains:
        raise ValueError('non_HDR_exact_gain_grid_required')
    rows = table.get('curve')
    if not isinstance(rows, list) or len(rows) != 20 or any(not isinstance(row, list) or len(row) != 64 or any(type(v) is not int or not 0 <= v <= 1023 for v in row) for row in rows):
        raise ValueError('20_by_64_integer_vendor_curves_required')
    result = copy.deepcopy(doc)
    for index in range(count):
        offset = 88 + 128 * index
        old = list(struct.unpack_from('=64H', source, offset))
        new = list(struct.unpack_from('=64H', requested, offset))
        if rows[index] != old:
            raise ValueError('template_does_not_match_actual_AUTO_source')
        for values in (old, new):
            if values[-1] != 1023 or any(v > 1023 for v in values) or any(b < a for a, b in zip(values, values[1:])):
                raise ValueError('monotone_10bit_endpoint_required')
        result['tuning']['AGC_2']['tables'][0]['curve'][index] = new
    reverted = copy.deepcopy(result)
    reverted['tuning']['AGC_2']['tables'][0]['curve'] = copy.deepcopy(rows)
    if reverted != doc: raise ValueError('unexpected_vendor_change')
    output = (json.dumps(result, allow_nan=False, separators=(',', ':')) + '\n').encode()
    digest = lambda blob: hashlib.sha256(blob).hexdigest()
    return output, {'schema': 'camera-x5-gamma-vendor-candidate-v1', 'templateSha256': digest(template),
                    'sourceModuleSha256': digest(source), 'requestedModuleSha256': digest(requested),
                    'candidateSha256': digest(output), 'pointer': '/tuning/AGC_2/tables/0/curve',
                    'activeRows': count, 'onlyActiveGammaCurvesChanged': True,
                    'hardwareQualified': False, 'reloadVerified': False, 'qualityAccepted': False,
                    'includesWhiteBalanceOverlay': False, 'deployed': False,
                    'scope': 'Factory-based Gamma-only JSON candidate; untouched factory modules are not an export of their current runtime state.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('template', 'source', 'requested'):
        parser.add_argument(name, type=Path)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    blobs = []
    for name in ('template', 'source', 'requested'):
        file = getattr(args, name); expected = getattr(args, name + '_sha256')
        limit = 8 * 1024 * 1024 if name == 'template' else 3044
        if not 0 < file.stat().st_size <= limit or not re.fullmatch('[a-f0-9]{64}', expected):
            raise ValueError('bounded_input_and_sha256_required')
        blob = file.read_bytes()
        if hashlib.sha256(blob).hexdigest() != expected: raise ValueError('input_sha256_mismatch_' + name)
        blobs.append(blob)
    output, receipt = render(*blobs)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as file: file.write(output)
    print(json.dumps(receipt, allow_nan=False))


if __name__ == '__main__': main()
