from datetime import date

from edtf import parse_edtf


def _struct_time_to_date(value):
    return date(value.tm_year, value.tm_mon, value.tm_mday)


def parse_edtf_to_dates(edtf_string):
    """
    Parses an EDTF string into (start_date, end_date) tuple.
    Returns (None, None) if invalid or empty.
    """
    if not edtf_string:
        return (None, None)

    try:
        parsed = parse_edtf(edtf_string)
        if hasattr(parsed, "lower_strict") and hasattr(parsed, "upper_strict"):
            return (
                _struct_time_to_date(parsed.lower_strict()),
                _struct_time_to_date(parsed.upper_strict()),
            )
        elif hasattr(parsed, "date"):
            d = parsed.date()
            return (d, d)
    except Exception:
        pass

    return (None, None)
