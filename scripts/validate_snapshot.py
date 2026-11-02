#!/usr/bin/env python3
"""
Validate public snapshot structure.
"""
import json
import sys

def main():
    with open('frontend/public/scholarships-snapshot.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    if 'scholarships' not in data or not isinstance(data['scholarships'], list):
        print('ERROR: Missing scholarships array')
        sys.exit(1)

    required = ['id', 'title', 'country', 'degree', 'funding', 'deadline_date', 'status', 'verification_status', 'official_source_url', 'application_link', 'image_url']
    if data['scholarships']:
        s = data['scholarships'][0]
        missing = [f for f in required if f not in s]
        if missing:
            print('ERROR: Missing fields:', missing)
            sys.exit(1)

    print('Snapshot validation passed')
    print('Records:', len(data['scholarships']))

if __name__ == '__main__':
    main()