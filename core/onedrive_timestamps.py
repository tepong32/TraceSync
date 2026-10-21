"""OneDrive RFC3339 client time without truncating NTFS's 100 ns precision."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
import re


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_TICKS_PER_SECOND = 10_000_000
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})$")
_FRACTION = re.compile(r"\.(\d{1,7})(?=Z$|[+-]\d{2}:\d{2}$)")


def parse_modified_time(value):
    if not isinstance(value, str) or not _RFC3339.fullmatch(value):
        raise ValueError("Unsupported OneDrive modification time.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("OneDrive modification time must include a time zone.")
    fraction = _FRACTION.search(value)
    # Compute whole seconds as an integer, then round only once to the float
    # used by stat(). datetime.fromisoformat alone discards the seventh digit.
    whole = parsed.replace(microsecond=0) - _EPOCH
    seconds = whole.days * 86400 + whole.seconds
    decimal_fraction = Decimal("0." + fraction[1]) if fraction else Decimal(0)
    if parsed.microsecond and fraction is None:
        raise ValueError("Unsupported OneDrive modification-time precision.")
    return float(Decimal(seconds) + decimal_fraction)


def format_modified_time(value):
    if isinstance(value, bool):
        raise ValueError("Modification time must be a finite number.")
    timestamp = Decimal.from_float(float(value))
    if not timestamp.is_finite():
        raise ValueError("Modification time must be a finite number.")
    ticks = int((timestamp * _TICKS_PER_SECOND).to_integral_value(rounding=ROUND_HALF_EVEN))
    seconds, fraction = divmod(ticks, _TICKS_PER_SECOND)
    date = _EPOCH + timedelta(seconds=seconds)
    return date.strftime("%Y-%m-%dT%H:%M:%S") + f".{fraction:07d}Z"
