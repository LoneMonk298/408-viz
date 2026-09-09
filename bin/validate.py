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
    assert data.get('struct_type') in ('tree', 'fsm', 'array'), f"unknown struct_type: {data.get('struct_type')}"
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
