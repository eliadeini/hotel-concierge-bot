"""Delete GuestSession rows whose stay has ended (check_out < today).

Fulfils the "phone + vacation info are auto-deleted at checkout, not kept
permanently" principle in hotel_concierge_bot_plan.md. There's no
scheduler/cron infrastructure in this app — this script has to actually be
scheduled to run for that to be true in practice, e.g.:

    # cron (daily at 03:00)
    0 3 * * * /path/to/.venv/bin/python -m scripts.purge_expired_guest_sessions

    # Windows Task Scheduler (daily at 03:00), Action:
    #   Program:  C:\path\to\.venv\Scripts\python.exe
    #   Arguments: -m scripts.purge_expired_guest_sessions
    #   Start in:  C:\path\to\Hotel Concierge Bot

Usage (from the project root, venv active):
    python -m scripts.purge_expired_guest_sessions
"""

from datetime import date

from app.db import SessionLocal, init_db
from app.models.guest_session import GuestSession


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        deleted = (
            db.query(GuestSession)
            .filter(GuestSession.check_out < date.today())
            .delete(synchronize_session=False)
        )
        db.commit()
    finally:
        db.close()
    print(f"Purged {deleted} expired guest session(s).")


if __name__ == "__main__":
    main()