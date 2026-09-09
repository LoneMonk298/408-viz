#!/usr/bin/env python3
"""Validate a 408-Viz IR file or dict.

Usage: python3 validate.py <ir.json>
"""
import json, sys
from pathlib import Path

BASE = Path(__file__).parent.parent

HL_KINDS = {'insert', 'visit', 'compare', 'unbalanced', 'rotated', 'removed'}
ARRAY_HL_KINDS = {'insert', 'visit', 'compare', 'swap', 'pivot', 'sorted', 'found', 'removed'}
FSM_TYPES = {'start', 'active', 'success', 'failure', 'terminal'}


def _walk_tree_ids(node, acc):
    acc.add(node['id'])
    kids = node.get('children', [])
    assert isinstance(kids, list) and len(kids) <= 2, \
        f"node '{node['id']}': children must be a list of at most 2 (position 0=left, 1=right, null as placeholder)"
    for c in kids:
        if c is None:
            continue
        _walk_tree_ids(c, acc)


def validate_ir(data):
    assert data.get('schema_version') == 1, 'schema_version must be 1'
    assert data.get('struct_type') in ('tree', 'fsm', 'array', 'timeline'), f"unknown struct_type: {data.get('struct_type')}"
    assert data.get('meta', {}).get('title'), 'meta.title required'
    assert data.get('presets'), 'presets required'
    t = data['struct_type']

    if t == 'tree':
        for pi, p in enumerate(data['presets']):
            assert p.get('name'), f'preset[{pi}].name required'
            assert p.get('steps'), f'preset[{pi}].steps required'
            for si, s in enumerate(p['steps']):
                assert s.get('title'), f'preset[{pi}].steps[{si}].title required'
                assert s.get('desc') is not None, f'preset[{pi}].steps[{si}].desc required'
                ids = set()
                _walk_tree_ids(s['tree'], ids)
                for h in s.get('hl', []):
                    assert h['node_id'] in ids, f"hl.node_id '{h['node_id']}' not in tree (preset {pi} step {si})"
                    assert h['kind'] in HL_KINDS, f"hl.kind '{h['kind']}' invalid"
    elif t == 'array':
        for pi, p in enumerate(data['presets']):
            assert p.get('name'), f'preset[{pi}].name required'
            for si, s in enumerate(p['steps']):
                assert s.get('title'), f'preset[{pi}].steps[{si}].title required'
                assert s.get('desc') is not None, f'preset[{pi}].steps[{si}].desc required'
                arr = s.get('array')
                assert isinstance(arr, list) and 1 <= len(arr) <= 20, \
                    f'preset[{pi}].steps[{si}].array must be a list of 1-20 items'
                for v in arr:
                    assert v is None or isinstance(v, (int, str)), \
                        f'preset[{pi}].steps[{si}].array items must be int, string or null'
                for h in s.get('hl', []):
                    assert isinstance(h.get('index'), int) and 0 <= h['index'] < len(arr), \
                        f"hl.index '{h.get('index')}' out of range (preset {pi} step {si})"
                    assert h['kind'] in ARRAY_HL_KINDS, f"hl.kind '{h['kind']}' invalid"
                for ptr in s.get('ptrs', []):
                    assert ptr.get('name'), f"ptrs.name required (preset {pi} step {si})"
                    assert isinstance(ptr.get('index'), int) and 0 <= ptr['index'] < len(arr), \
                        f"ptrs.index '{ptr.get('index')}' out of range (preset {pi} step {si})"
    elif t == 'timeline':
        row_ids = set()
        rows = data.get('rows', [])
        assert 1 <= len(rows) <= 4, 'rows must be 1-4'
        for r in rows:
            assert r.get('id') and r.get('label'), f"rows[].id/label required ('{r.get('id')}')"
            assert r['id'] not in row_ids, f"duplicate row id '{r['id']}'"
            row_ids.add(r['id'])
        for pi, p in enumerate(data['presets']):
            assert p.get('name'), f'preset[{pi}].name required'
            bars = p.get('bars', [])
            assert 1 <= len(bars) <= 30, f'preset[{pi}].bars must be 1-30 items'
            bar_ids = set()
            by_row = {}
            for b in bars:
                bid = b.get('id')
                assert bid, f'preset[{pi}].bars[].id required'
                assert bid not in bar_ids, f"duplicate bar id '{bid}'"
                bar_ids.add(bid)
                assert b.get('row') in row_ids, f"bar '{bid}' row '{b.get('row')}' not in rows"
                assert b.get('kind', 'run') in ('run', 'io', 'idle'), f"bar '{bid}' kind invalid"
                try:
                    st_, e_ = float(b['start']), float(b['end'])
                except (KeyError, TypeError, ValueError):
                    raise AssertionError(f"bar '{bid}' start/end must be numbers")
                assert 0 <= st_ < e_ <= 1000, f"bar '{bid}' needs 0 <= start < end <= 1000"
                by_row.setdefault(b['row'], []).append((st_, e_, bid))
            for rid, bs in by_row.items():
                bs.sort()
                for i in range(1, len(bs)):
                    assert bs[i][0] >= bs[i - 1][1] - 1e-9, \
                        f"bars '{bs[i - 1][2]}' and '{bs[i][2]}' overlap in row '{rid}' (preset {pi})"
            max_end = max(e for _, e, _ in (b for bs in by_row.values() for b in bs))
            for m in p.get('markers', []):
                assert isinstance(m.get('t'), (int, float)), f"markers[].t must be a number (preset {pi})"
                assert 0 <= m['t'] <= max_end, \
                    f"markers[].t '{m['t']}' out of range 0..{max_end} (preset {pi})"
            for si, s in enumerate(p['steps']):
                assert s.get('title'), f'preset[{pi}].steps[{si}].title required'
                assert s.get('desc') is not None, f'preset[{pi}].steps[{si}].desc required'
                assert isinstance(s.get('reveal'), (int, float)), \
                    f"steps[{si}].reveal must be a number (preset {pi})"
                assert 0 <= s['reveal'] <= max_end, \
                    f"steps[{si}].reveal '{s['reveal']}' out of range 0..{max_end} (preset {pi})"
                for aid in s.get('active', []):
                    assert aid in bar_ids, f"active '{aid}' not in bars (preset {pi} step {si})"
    elif t == 'fsm':
        state_ids = {s['id'] for s in data['states']}
        trans_ids = {tr['id'] for tr in data['transitions'] if tr.get('id')}
        for tr in data['transitions']:
            assert tr['from'] in state_ids, f"transition from '{tr['from']}' not in states"
            assert tr['to'] in state_ids, f"transition to '{tr['to']}' not in states"
            assert tr.get('label'), 'transition.label required'
        for s in data['states']:
            assert s['type'] in FSM_TYPES, f"state.type '{s['type']}' invalid"
        for pi, p in enumerate(data['presets']):
            assert p.get('name'), f'preset[{pi}].name required'
            for si, st in enumerate(p['steps']):
                assert st.get('title'), f'preset[{pi}].steps[{si}].title required'
                assert st.get('desc') is not None, f'preset[{pi}].steps[{si}].desc required'
                for aid in st.get('active', []):
                    assert aid in state_ids, f"active '{aid}' not in states (preset {pi} step {si})"
                for tr in st.get('lastTrans', []):
                    assert tr['id'] in trans_ids, f"lastTrans '{tr['id']}' not in transitions (preset {pi} step {si})"


def validate_file(path):
    data = json.loads(Path(path).read_text())
    validate_ir(data)
    return data


if __name__ == '__main__':
    try:
        validate_file(sys.argv[1])
        print('OK')
    except (AssertionError, ValueError, KeyError) as e:
        print(f'FAIL: {e}', file=sys.stderr)
        sys.exit(1)
