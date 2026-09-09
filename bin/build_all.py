#!/usr/bin/env python3
"""Render all example IR files in examples/."""
import sys
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from render import render  # noqa: E402

examples_dir = BASE.parent / 'examples'
for ir_path in sorted(examples_dir.glob('*.json')):
    out_path = ir_path.with_suffix('.html')
    render(str(ir_path), str(out_path))
