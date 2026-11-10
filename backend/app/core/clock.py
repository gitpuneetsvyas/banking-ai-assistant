from datetime import date, datetime, timezone


def today() -> date:
    return date.today()


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
