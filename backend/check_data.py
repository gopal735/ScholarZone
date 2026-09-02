import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.data.verified_scholarships import VERIFIED_SCHOLARSHIPS

# Count records with deadline_date
with_date = [s for s in VERIFIED_SCHOLARSHIPS if s.deadline_date is not None]
print(f"Records with deadline_date in verified data: {len(with_date)}")
for s in with_date:
    print(f"  {s.name}: deadline_date={s.deadline_date}")
