import os
import resend
from dotenv import load_dotenv

from ..core.config import get_settings

load_dotenv()

settings = get_settings()


def send_verification_reminder(due_count: int, scholarships: list) -> bool:
    if not settings.resend_api_key:
        print("[Email] RESEND_API_KEY not set, skipping email")
        return False

    resend.api_key = settings.resend_api_key

    names = "\n".join(f"- {s.title} ({s.country})" for s in scholarships)

    try:
        resend.Emails.send({
            "from": "ScholarZone <onboarding@resend.dev>",
            "to": [os.getenv("NOTIFICATION_EMAIL", "")],
            "subject": f"[ScholarZone] {due_count} scholarship(s) need verification",
            "text": f"The following scholarships are due for verification:\n\n{names}\n\nLogin to verify them."
        })
        print(f"[Email] Reminder sent for {due_count} scholarships")
        return True
    except Exception as e:
        print(f"[Email] Failed to send: {e}")
        return False
