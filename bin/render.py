#!/usr/bin/env python3
"""Render a 408-Viz IR JSON into a standalone HTML file.

Usage: python3 render.py <ir.json> <out.html>
"""
import json, sys
from pathlib import Path
from validate import validate_file

BASE = Path(__file__).parent.parent
TEMPLATE = BASE / 'bin' / 'renderer_template.html'


def render(ir_path, out_path):
    ir = validate_file(ir_path)
    template = TEMPLATE.read_text()
    json_str = json.dumps(ir, ensure_ascii=False)
    # Escape HTML-special chars so the JSON never closes the <script> tag.
    json_str = json_str.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    out = template.replace('/*__IR__*/null', json_str)
    Path(out_path).write_text(out)
    print(f'OK: {out_path} ({len(out)} bytes)')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: render.py <ir.json> <out.html>', file=sys.stderr)
        sys.exit(1)
    render(sys.argv[1], sys.argv[2])
