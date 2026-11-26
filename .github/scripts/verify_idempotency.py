#!/usr/bin/env python3
import sys, os
sys.path.insert(0, 'backend')
from app.database import get_session_factory, init_database
from sqlalchemy import select
from app.models import PurgeExecutionLedger
def main():
    init_database()
    sf = get_session_factory()
    merge_sha = os.environ.get('MERGE_COMMIT_SHA', '')
    if merge_sha:
        with sf() as db:
            existing = db.execute(select(PurgeExecutionLedger).where(PurgeExecutionLedger.merge_commit_sha == merge_sha)).scalar_one_or_none()
            if existing:
                print('ALREADY_EXECUTED: Purge already executed for merge commit ' + merge_sha); sys.exit(2)
            else:
                print('ALREADY_EXECUTED=false')
    else:
        print('ERROR: MERGE_COMMIT_SHA not set'); sys.exit(1)
if __name__ == '__main__':
    main()
