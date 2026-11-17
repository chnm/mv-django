"""Free-text search across Crime records, shared by the map and the data table."""

import unicodedata

from django.db.models import Q

# Crime fields matched by the free-text `q` param.
CRIME_SEARCH_FIELDS = (
    "number",
    "crime",
    "year",
    "description_of_case",
    "motive",
    "victim_description",
    "assailant_description",
    "sentence",
    "victim__first_name",
    "victim__last_name",
    "victim__given_name",
    "perpetrator__first_name",
    "perpetrator__last_name",
    "perpetrator__given_name",
    "address__name",
    "address__city__name",
)


def strip_accents(text):
    """'Módena' -> 'Modena'. Mirrors Postgres unaccent() for Latin scripts."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def crime_search_q(q, prefix=""):
    """Build a Q for a free-text query.

    Every whitespace-separated term must match at least one of
    CRIME_SEARCH_FIELDS, case- and accent-insensitively. `prefix` lets callers
    filter through a relation (e.g. "crime__" from Location).
    """
    combined = Q()
    for term in strip_accents(q).split():
        term_q = Q()
        for field in CRIME_SEARCH_FIELDS:
            term_q |= Q(**{f"{prefix}{field}__unaccent__icontains": term})
        combined &= term_q
    return combined
