from datetime import datetime, timedelta, timezone

# Times typed by teachers are in the institution's timezone (India Standard Time).
# They are stored in the database as UTC and converted back for display.
INSTITUTION_TZ = timezone(timedelta(hours=5, minutes=30))


def parse_local(value):
    """'2026-11-10T14:30' typed in institution time -> aware UTC datetime, or None."""
    try:
        naive = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return None
    return naive.replace(tzinfo=INSTITUTION_TZ).astimezone(timezone.utc)


def to_local(dt):
    return dt.astimezone(INSTITUTION_TZ) if dt else None


def local_display(dt):
    """For showing a time on a page, e.g. '10 Nov 2026, 02:30 PM'."""
    return to_local(dt).strftime("%d %b %Y, %I:%M %p") if dt else ""


def local_input(dt):
    """For filling a datetime-local input."""
    return to_local(dt).strftime("%Y-%m-%dT%H:%M") if dt else ""
