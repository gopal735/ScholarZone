#!/usr/bin/env python3
"""Check overall preflight status from summary JSON."""

import json
import sys
import os

def main():
    if not os.path.exists('preflight_summary.json'):
        print('No summary generated')
        return 1

    with open('preflight_summary.json') as f:
        s = json.load(f)

    print('Overall status:', s['overall_status'])

    if s['overall_status'] == 'ALL_PREFLIGHT_GATES_COMPLETE':
        print('SUCCESS: All gates passed')
        return 0
    else:
        # INCOMPLETE_MISSING_GATES and FAILED_GATES_PRESENT are both failures
        print('FAILURE: Preflight incomplete or failed')
        return 1

if __name__ == '__main__':
    sys.exit(main())