from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
from sqlalchemy.orm import Session

from .database import get_session_factory
from .models import Scholarship
from .services.email_service import send_verification_reminder

session_factory = get_session_factory()


def mark_due_for_review():
    db: Session = session_factory()
    try:
        today = date.today()
        due = db.query(Scholarship).filter(
            Scholarship.next_verification_due <= today
        ).all()
        for s in due:
            s.verification_status = "needs_review"
        db.commit()
        print(f"[Scheduler] Marked {len(due)} scholarships as needs_review")
        send_verification_reminder(len(due), due)
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        mark_due_for_review,
        trigger="interval",
        hours=24,
        id="verification_check",
        replace_existing=True
    )
    scheduler.start()
    return scheduler
