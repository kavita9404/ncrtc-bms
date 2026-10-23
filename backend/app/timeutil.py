"""Time helpers. DB timestamps are naive UTC; duty dates / wall-clock times are IST."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def today_ist() -> date:
    return datetime.now(IST).date()


def iso(dt: datetime | None) -> str | None:
    """Naive-UTC datetime -> ISO string with Z so browsers parse it correctly."""
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


def hhmm(t: time | None) -> str | None:
    return t.strftime("%H:%M") if t else None


def ist_day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    """[start, end) of an IST calendar day, expressed as naive UTC."""
    start = datetime.combine(d, time.min, IST).astimezone(UTC).replace(tzinfo=None)
    return start, start + timedelta(days=1)


def ist_to_utc_naive(d: date, t: time) -> datetime:
    return datetime.combine(d, t, IST).astimezone(UTC).replace(tzinfo=None)
