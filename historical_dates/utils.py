from edtf import parse_edtf

def parse_edtf_to_dates(edtf_string):
    """
    Parses an EDTF string into (start_date, end_date) tuple.
    Returns (None, None) if invalid or empty.
    """
    if not edtf_string:
        return (None, None)

    try:
        parsed = parse_edtf(edtf_string)
        if hasattr(parsed, 'lower_strict') and hasattr(parsed, 'upper_strict'):
            return (parsed.lower_strict.date(), parsed.upper_strict.date())
        elif hasattr(parsed, 'date'):
            d = parsed.date()
            return (d, d)
    except Exception:
        pass

    return (None, None)
