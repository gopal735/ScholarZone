#!/usr/bin/env python3
"""Fix JSONL duration_months values."""
import json
import re

fixed_lines = []
with open('backend/verification/research_ledger_world_top_demand.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
            fixed_lines.append(line)
        except json.JSONDecodeError as e:
            # Fix: wrap duration_months value in quotes if it's a range like 12-24
            fixed = re.sub(r'"duration_months":\s*([0-9]+-[0-9]+)', r'"duration_months": "\1"', line)
            # Also fix single numbers that might be followed by comma
            fixed = re.sub(r'"duration_months":\s*([0-9]+)([,\}])', r'"duration_months": \1\2', fixed)
            try:
                json.loads(fixed)
                fixed_lines.append(fixed)
                print(f'Fixed line {i}')
            except json.JSONDecodeError as e2:
                print(f'Failed to fix line {i}: {e2}')

with open('backend/verification/research_ledger_world_top_demand.jsonl', 'w', encoding='utf-8') as f:
    for line in fixed_lines:
        f.write(line + '\n')

print(f'Total lines: {len(fixed_lines)}')