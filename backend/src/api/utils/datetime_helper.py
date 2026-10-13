"""Timezone handling for DATETIME columns and report date boundaries.

MySQL's DATETIME carries no timezone. SQLAlchemy's DateTime(timezone=True)
does not change that -- it only affects how a value is *bound*, and a driver
silently strips the offset on the way in. So a row written with an aware
datetime comes back NAIVE.

That means the stored wall-clock is UTC (this app only ever writes UTC), and
any arithmetic against a freshly generated `datetime.now(timezone.utc)` raises

    TypeError: can't subtract offset-naive and offset-aware datetimes

Every elapsed-time calculation has to normalise first, which is what `as_utc`
is for. Call it on anything loaded from the database before doing date maths,
and use `utcnow()` rather than `datetime.now(timezone.utc)` when writing, so the
two sides of every comparison are the same kind.

A future move to TIMESTAMP, or to Postgres which does honour timezones, would
make this a no-op rather than a rewrite -- that is the point of funneling
through one helper.

REPORT BOUNDARIES
-----------------
`business_today()`, `local_day_bounds_utc()` and `resolve_report_range()` exist
because a report for "today" must mean the trading day the staff recognise. A
cafe in Asia/Kolkata closes at 01:00 and opens again at 08:00, so the trading
day starts at 18:30 UTC the previous day. Slicing on UTC midnight would put
the late-night and early-morning trade in the wrong bucket on every single
figure.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


## Resolved once: the IANA zone name is validated and cached, because every
## report query hits these helpers and ZoneInfo() is not free.
_BUSINESS_TZ_NAME = None
_BUSINESS_TZ = None
_TZ_RESOLVED = False


def business_timezone() -> ZoneInfo:
    """The configured trading timezone, falling back to UTC if misconfigured."""
    global _BUSINESS_TZ_NAME, _BUSINESS_TZ, _TZ_RESOLVED

    if not _TZ_RESOLVED:
        from src.config.base import BaseConfig

        name = BaseConfig.BUSINESS_TIMEZONE
        try:
            _BUSINESS_TZ = ZoneInfo(name)
            _BUSINESS_TZ_NAME = name
        except (ZoneInfoNotFoundError, ValueError, TypeError, KeyError):
            ## A typo in BUSINESS_TIMEZONE must not take the whole reports
            ## module down. UTC is wrong-but-consistent, and the configured
            ## name is returned so the caller can log it.
            _BUSINESS_TZ = timezone.utc
            _BUSINESS_TZ_NAME = f"{name} (INVALID - falling back to UTC)"

        _TZ_RESOLVED = True

    return _BUSINESS_TZ


def business_timezone_name() -> str:
    business_timezone()
    return _BUSINESS_TZ_NAME


def reset_timezone_cache() -> None:
    """Test hook: forces the zone to be re-read on next use."""
    global _TZ_RESOLVED
    _TZ_RESOLVED = False


## ----------------------------------------------------------------------
## Naive UTC, matching what a DATETIME column actually stores
## ----------------------------------------------------------------------

def utcnow() -> datetime:
    """Naive UTC 'now', matching what a DATETIME column will actually store."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime | None) -> datetime | None:
    """Interpret a naive datetime as UTC; pass an aware one through unchanged."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def elapsed_minutes(since: datetime | None, until: datetime | None = None) -> int | None:
    """Whole minutes from `since` to `until`, or None when `since` is unset.

    Never negative: clock skew between the app server and the database host can
    otherwise produce -1 minutes, which a UI would render as a negative wait.
    """
    start = as_utc(since)
    if start is None:
        return None
    end = as_utc(until) or datetime.now(timezone.utc)
    return max(int((end - start).total_seconds() // 60), 0)


## ----------------------------------------------------------------------
## Trading-day boundaries
## ----------------------------------------------------------------------

def business_now() -> datetime:
    """Current wall-clock time in the trading timezone (aware)."""
    return datetime.now(business_timezone())


def business_today() -> date:
    """Today's date in the trading timezone."""
    return business_now().date()


def to_business_tz(value: datetime | None) -> datetime | None:
    """Move a naive-UTC database timestamp into the trading timezone."""
    utc = as_utc(value)
    if utc is None:
        return None
    return utc.astimezone(business_timezone())


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """UTC bounds of one trading day, as NAIVE UTC datetimes.

    Returns a half-open interval [start, end) so consecutive days tile without
    overlap and a row is counted exactly once.

        Asia/Kolkata 2026-10-09
          -> 2026-10-08 18:30:00  ..  2026-10-09 18:30:00
    """
    tz = business_timezone()
    local_start = datetime.combine(day, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)

    return (
        local_start.astimezone(timezone.utc).replace(tzinfo=None),
        local_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def add_month(day: date, months: int) -> date:
    """Shift a date by whole months, clamping to the end of the target month.

    31 Jan minus 1 month is 31 Dec, not a nonexistent 31 Feb.
    """
    total = (day.year * 12 + (day.month - 1)) + months
    year, month = divmod(total, 12)
    month += 1

    if month == 12:
        next_month_first = date(year + 1, 1, 1)
    else:
        next_month_first = date(year, month + 1, 1)

    last_day = (next_month_first - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


## Ranges are half-open in UTC: [start, end). Never use <= on the upper bound,
## or an order landing exactly on midnight is counted twice across two days.
REPORT_PRESETS = [
    "today",
    "yesterday",
    "last_7_days",
    "last_30_days",
    "this_month",
    "last_month",
    "custom",
]


def resolve_report_range(preset: str, from_date: date | None, to_date: date | None):
    """Turn a preset or an explicit pair of dates into UTC bounds.

    Returns (start_utc, end_utc, resolved_from_date, resolved_to_date) as naive
    UTC datetimes, where resolved_* are the trading-timezone dates actually
    covered -- the caller echoes those back so the UI can label the report
    without guessing.

    Raises ValueError for a preset it does not recognise, or for a `custom`
    range missing either bound or given them the wrong way round.
    """
    today = business_today()

    if preset == "today":
        from_day = to_day = today
    elif preset == "yesterday":
        from_day = to_day = today - timedelta(days=1)
    elif preset == "last_7_days":
        ## Includes today, so this is 7 trading days, not 6.
        from_day, to_day = today - timedelta(days=6), today
    elif preset == "last_30_days":
        from_day, to_day = today - timedelta(days=29), today
    elif preset == "this_month":
        from_day, to_day = today.replace(day=1), today
    elif preset == "last_month":
        first_of_this = today.replace(day=1)
        from_day = add_month(first_of_this, -1)
        to_day = first_of_this - timedelta(days=1)
    elif preset == "custom":
        if from_date is None or to_date is None:
            raise ValueError(
                "A custom range needs both from_date and to_date."
            )
        if to_date < from_date:
            raise ValueError("to_date cannot be earlier than from_date.")
        from_day, to_day = from_date, to_date
    else:
        raise ValueError(f"Unknown report range preset '{preset}'.")

    start_utc, _ = local_day_bounds_utc(from_day)
    _, end_utc = local_day_bounds_utc(to_day)

    return start_utc, end_utc, from_day, to_day


def iter_local_days(from_day: date, to_day: date):
    """Every trading date from `from_day` to `to_day` inclusive."""
    current = from_day
    while current <= to_day:
        yield current
        current += timedelta(days=1)


def utc_hour_to_business(value: datetime) -> datetime:
    """Reinterpret a naive-UTC timestamp as business-local wall-clock time.

    Used to re-bucket UTC hourly aggregates into local hours and days. Report
    queries group by UTC hour (cheap, index-friendly) and the shift happens in
    Python over a handful of rows, instead of asking MySQL for CONVERT_TZ /
    DATE_FORMAT per row.
    """
    return as_utc(value).astimezone(business_timezone())


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None