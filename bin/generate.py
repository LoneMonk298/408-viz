#!/usr/bin/env python3
"""Generate a 408-Viz IR from a problem + answer using an LLM API.

Usage:
  python bin/generate.py --problem "题目" --answer "解法" --out examples/foo
  python bin/generate.py --problem-file p.txt --answer-file a.txt --out examples/foo
  python bin/generate.py --problem "..." --struct-type graph --out examples/foo

Requires:
  - SENSENOVA_API_KEY environment variable (or --api-key)
  - sensenova API endpoint: https://token.sensenova.cn/v1 (OpenAI compatible)

Workflow:
  1. Build prompt (system.md + schemas/README.md + few-shot)
  2. Call LLM API
  3. Extract JSON from response
  4. Validate with validate.py
  5. On failure: feed error back to LLM, retry once
  6. Save .json + render .html
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).parent.parent
PROMPTS_DIR = BASE / 'prompts'
SCHEMAS_DIR = BASE / 'schemas'
BIN_DIR = BASE / 'bin'

sys.path.insert(0, str(BIN_DIR))
from validate import validate_ir, validate_file  # noqa: E402
from render import render  # noqa: E402

DEFAULT_MODEL = 'sensenova-6.7-flash-lite'
DEFAULT_BASE_URL = 'https://token.sensenova.cn/v1'
MAX_TOKENS = 8192
TEMPERATURE = 0.3


def load_prompt():
    """Build the system prompt: system.md + schemas/README.md injected."""
    sys_md = (PROMPTS_DIR / 'system.md').read_text(encoding='utf-8')
    ir_spec = (SCHEMAS_DIR / 'README.md').read_text(encoding='utf-8')
    return sys_md + '\n\n## IR 规范全文\n\n' + ir_spec


def load_fewshot():
    """Load few-shot examples as (user_msg, assistant_msg) pairs."""
    pairs = []
    fewshot_dir = PROMPTS_DIR / 'fewshot'
    for f in sorted(fewshot_dir.glob('*.txt')):
        text = f.read_text(encoding='utf-8')
        parts = text.split('IR JSON：', 1)
        if len(parts) == 2:
            user = parts[0].strip()
            assistant = parts[1].strip()
            pairs.append((user, assistant))
    return pairs


def build_messages(problem, answer, struct_type_hint=None):
    """Build the messages array for the API call."""
    system = load_prompt()
    fewshot = load_fewshot()

    messages = [{'role': 'system', 'content': system}]

    for user_msg, assistant_msg in fewshot:
        messages.append({'role': 'user', 'content': user_msg})
        messages.append({'role': 'assistant', 'content': assistant_msg})

    user_content = f'题目：{problem}\n\n解法：{answer}'
    if struct_type_hint:
        user_content += f'\n\n（请使用 struct_type = "{struct_type_hint}"）'
    user_content += '\n\n请输出 IR JSON：'
    messages.append({'role': 'user', 'content': user_content})
    return messages


def call_llm(messages, api_key, base_url, model):
    """Call the OpenAI-compatible chat completions API."""
    url = base_url.rstrip('/') + '/chat/completions'
    payload = {
        'model': model,
        'messages': messages,
        'temperature': TEMPERATURE,
        'max_tokens': MAX_TOKENS,
    }
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url, data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f'API error {e.code}: {body}', file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f'Network error: {e}', file=sys.stderr)
        sys.exit(1)


def extract_json(text):
    """Extract a JSON object from LLM response text."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try code fence
    if '```json' in text:
        start = text.index('```json') + 7
        end = text.index('```', start)
        return json.loads(text[start:end].strip())
    if '```' in text:
        start = text.index('```') + 3
        end = text.index('```', start)
        return json.loads(text[start:end].strip())
    # Fallback: first { to last }
    first = text.find('{')
    last = text.rfind('}')
    if first >= 0 and last > first:
        return json.loads(text[first:last + 1])
    raise ValueError('No JSON found in response')


def generate(problem, answer, api_key, base_url, model,
             struct_type_hint=None, max_retries=1):
    """Generate IR from problem+answer. Returns validated dict."""
    messages = build_messages(problem, answer, struct_type_hint)

    for attempt in range(max_retries + 1):
        prefix = f'[attempt {attempt + 1}/{max_retries + 1}] ' if max_retries > 0 else ''
        print(f'{prefix}Calling LLM...', file=sys.stderr)
        raw = call_llm(messages, api_key, base_url, model)
        print(f'{prefix}Response received ({len(raw)} chars)', file=sys.stderr)

        try:
            ir = extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            print(f'{prefix}JSON extraction failed: {e}', file=sys.stderr)
            if attempt < max_retries:
                messages.append({'role': 'assistant', 'content': raw})
                messages.append({'role': 'user', 'content':
                    f'你的输出无法解析为 JSON：{e}\n'
                    '请重新输出完整的 IR JSON，不要加任何解释文字。'})
                continue
            print(f'\nRaw response:\n{raw[:2000]}', file=sys.stderr)
            sys.exit(1)

        try:
            validate_ir(ir)
            print(f'{prefix}Validation passed', file=sys.stderr)
            return ir
        except (AssertionError, KeyError, TypeError) as e:
            print(f'{prefix}Validation failed: {e}', file=sys.stderr)
            if attempt < max_retries:
                messages.append({'role': 'assistant', 'content': raw})
                messages.append({'role': 'user', 'content':
                    f'你的 IR 校验失败：{e}\n'
                    '请修复并重新输出完整的 IR JSON，不要加任何解释文字。'})
                continue
            print(f'\nRaw response:\n{raw[:2000]}', file=sys.stderr)
            sys.exit(1)

    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Generate 408-Viz IR from problem+answer via LLM')
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--problem', help='题目描述')
    g.add_argument('--problem-file', help='从文件读取题目')
    g2 = parser.add_mutually_exclusive_group()
    g2.add_argument('--answer', help='解法描述')
    g2.add_argument('--answer-file', help='从文件读取解法')
    parser.add_argument('--out', required=True,
                        help='输出路径（不含扩展名，如 examples/foo）')
    parser.add_argument('--struct-type',
                        choices=['tree', 'fsm', 'array', 'timeline', 'graph', 'grid'],
                        help='强制指定 struct_type（可选）')
    parser.add_argument('--model', default=DEFAULT_MODEL, help=f'模型名（默认 {DEFAULT_MODEL}）')
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL, help='API base URL')
    parser.add_argument('--api-key', default=None, help='API key（默认读 SENSENOVA_API_KEY 环境变量）')
    parser.add_argument('--dry-run', action='store_true', help='只生成 IR 不渲染 HTML')
    args = parser.parse_args()

    problem = args.problem
    if args.problem_file:
        problem = Path(args.problem_file).read_text(encoding='utf-8').strip()
    answer = args.answer or ''
    if args.answer_file:
        answer = Path(args.answer_file).read_text(encoding='utf-8').strip()
    if not answer:
        print('Warning: no answer provided, LLM will generate from problem alone', file=sys.stderr)

    api_key = args.api_key or os.environ.get('SENSENOVA_API_KEY')
    if not api_key:
        print('Error: set SENSENOVA_API_KEY env var or use --api-key', file=sys.stderr)
        sys.exit(1)

    ir = generate(problem, answer, api_key, args.base_url, args.model,
                  struct_type_hint=args.struct_type)

    out_json = Path(args.out).with_suffix('.json')
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(ir, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'IR saved: {out_json}', file=sys.stderr)

    if not args.dry_run:
        out_html = Path(args.out).with_suffix('.html')
        render(str(out_json), str(out_html))
        print(f'HTML rendered: {out_html}', file=sys.stderr)

    print(f'\nstruct_type={ir["struct_type"]}, '
          f'{len(ir["presets"])} preset(s), '
          f'{len(ir["presets"][0]["steps"])} steps')


if __name__ == '__main__':
    main()
