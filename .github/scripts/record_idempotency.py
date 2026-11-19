#!/usr/bin/env python3
"""Record idempotency marker for PR #107 automatic purge."""

import sys
import os

sys.path.insert(0, 'backend')
from app.database import get_session_factory, init_database
from app.models import DeletedClosedScholarship

def main():
    init_database()
    sf = get_session_factory()
    merge_sha = os.environ.get('MERGE_COMMIT_SHA', '')
    if merge_sha:
        with sf() as db:
            ts = DeletedClosedScholarship(
                official_source_url=None,
                application_link=None,
                title='PR #107 PURGE MERGE COMMIT ' + merge_sha,
                reason='pr107_purge_merge_commit_' + merge_sha
            )
            db.add(ts)
            db.commit()
            print('Idempotency marker recorded for merge commit ' + merge_sha)
    else:
        print('ERROR: MERGE_COMMIT_SHA not set')
        sys.exit(1)

if __name__ == '__main__':
    main()