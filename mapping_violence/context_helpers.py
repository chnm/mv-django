"""Shared context builders for filter bar used by map and data table views."""

import json

from locations.models import URBAN_RURAL_CHOICES, City, Location
from mapping_violence.models import WEAPON_CATEGORY_CHOICES, Crime, Weapon


def get_filter_context():
    """Return context dict shared by map and data table filter bars."""
    countries = (
        City.objects.filter(location__crime__isnull=False)
        .exclude(country="")
        .values_list("country", flat=True)
        .distinct()
        .order_by("country")
    )

    cities = (
        City.objects.filter(location__crime__isnull=False).distinct().order_by("name")
    )

    crime_types = (
        Crime.objects.exclude(crime="")
        .values_list("crime", flat=True)
        .distinct()
        .order_by("crime")
    )

    weapon_subcategories = (
        Weapon.objects.exclude(weapon_subcategory="")
        .values_list("weapon_subcategory", flat=True)
        .distinct()
        .order_by("weapon_subcategory")
    )

    # Build city → locations mapping for cascading dropdown
    locations_with_crimes = (
        Location.objects.filter(crime__isnull=False)
        .select_related("city")
        .distinct()
        .order_by("name")
    )
    locations_by_city = {}
    for loc in locations_with_crimes:
        if not loc.city:
            continue
        cid = loc.city.id
        if cid not in locations_by_city:
            locations_by_city[cid] = []
        has_own_coords = bool(loc.latitude and loc.longitude)
        locations_by_city[cid].append(
            {
                "id": loc.id,
                "name": loc.name,
                "precise": has_own_coords,
            }
        )

    # Build country → cities mapping for cascading dropdown
    cities_by_country = {}
    for city in (
        City.objects.filter(location__crime__isnull=False)
        .exclude(country="")
        .distinct()
        .order_by("name")
    ):
        country = city.country
        if country not in cities_by_country:
            cities_by_country[country] = []
        cities_by_country[country].append({"id": city.id, "name": city.name})

    return {
        "countries": countries,
        "cities": cities,
        "cities_by_country_json": json.dumps(cities_by_country),
        "crime_types": crime_types,
        "weapon_categories": WEAPON_CATEGORY_CHOICES,
        "weapon_subcategories": weapon_subcategories,
        "urban_rural_choices": URBAN_RURAL_CHOICES,
        "locations_by_city_json": json.dumps(locations_by_city),
    }
