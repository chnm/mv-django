from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render

from locations.models import Location
from mapping_violence.context_helpers import get_filter_context


def map_view(request):
    """Display the map interface with filter options"""
    context = get_filter_context()
    return render(request, "locations/map.html", context)


def locations_geojson(request):
    """Return locations with crimes as GeoJSON for the map"""
    # Start with locations that have crimes
    locations = Location.objects.select_related("city").filter(crime__isnull=False)

    # Apply filters from request
    country = request.GET.get("country")
    city_id = request.GET.get("city")
    location_id = request.GET.get("location")
    crime_type = request.GET.get("crime_type")
    year_from = request.GET.get("year_from")
    year_to = request.GET.get("year_to")
    weapon_category = request.GET.get("weapon_category")
    weapon_subcategory = request.GET.get("weapon_subcategory")
    urban_rural = request.GET.get("urban_rural")
    person = request.GET.get("person")
    fatality = request.GET.get("fatality")

    if country:
        locations = locations.filter(city__country=country)

    if location_id:
        locations = locations.filter(id=location_id)
    elif city_id:
        locations = locations.filter(city_id=city_id)

    if crime_type:
        locations = locations.filter(crime__crime=crime_type)

    if year_from:
        locations = locations.filter(crime__year__gte=year_from)

    if year_to:
        locations = locations.filter(crime__year__lte=year_to)

    if weapon_category:
        locations = locations.filter(crime__weapon__weapon_category=weapon_category)

    if weapon_subcategory:
        locations = locations.filter(
            crime__weapon__weapon_subcategory=weapon_subcategory
        )

    if urban_rural:
        locations = locations.filter(urban_rural=urban_rural)

    if person:
        person_ids = [int(p) for p in person.split(",") if p.strip().isdigit()]
        if person_ids:
            locations = locations.filter(
                Q(crime__victim__id__in=person_ids)
                | Q(crime__perpetrator__id__in=person_ids)
            )

    if fatality and fatality.lower() in ("true", "1", "on"):
        locations = locations.filter(crime__fatality=True)

    # Get unique locations with crime counts
    locations = locations.annotate(crime_count=Count("crime", distinct=True)).distinct()

    features = []
    for location in locations:
        # Skip locations without coordinates
        if not location.effective_latitude or not location.effective_longitude:
            continue

        # Get crimes for this location (applying same filters)
        crimes_query = location.crime_set.all()
        if crime_type:
            crimes_query = crimes_query.filter(crime=crime_type)
        if year_from:
            crimes_query = crimes_query.filter(year__gte=year_from)
        if year_to:
            crimes_query = crimes_query.filter(year__lte=year_to)
        if weapon_category:
            crimes_query = crimes_query.filter(weapon__weapon_category=weapon_category)
        if weapon_subcategory:
            crimes_query = crimes_query.filter(
                weapon__weapon_subcategory=weapon_subcategory
            )
        if person:
            person_ids = [int(p) for p in person.split(",") if p.strip().isdigit()]
            if person_ids:
                crimes_query = crimes_query.filter(
                    Q(victim__id__in=person_ids) | Q(perpetrator__id__in=person_ids)
                ).distinct()
        if fatality and fatality.lower() in ("true", "1", "on"):
            crimes_query = crimes_query.filter(fatality=True)

        crimes_data = []
        for crime in crimes_query.order_by("date", "year").prefetch_related(
            "victim", "perpetrator"
        ):
            victim_genders = [v.gender for v in crime.victim.all() if v.gender]
            perp_genders = [p.gender for p in crime.perpetrator.all() if p.gender]
            crimes_data.append(
                {
                    "id": crime.id,
                    "crime": crime.crime,
                    "number": crime.number,
                    "date": str(crime.date) if crime.date else None,
                    "year": crime.year,
                    "fatality": crime.fatality,
                    "victim_gender": victim_genders[0] if victim_genders else "U",
                    "perpetrator_gender": perp_genders[0] if perp_genders else "U",
                }
            )

        # Determine coordinate precision
        has_own_coords = bool(location.latitude and location.longitude)
        precision = "precise" if has_own_coords else "city"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(location.effective_longitude),
                    float(location.effective_latitude),
                ],
            },
            "properties": {
                "id": location.id,
                "name": location.name,
                "city": location.city.name if location.city else "",
                "city_id": location.city.id if location.city else None,
                "category": location.category_of_space or "",
                "description": location.description_of_location or "",
                "current_name": location.current_name or "",
                "sestiere": location.sestiere or "",
                "street": location.street or "",
                "landmark": location.landmark or "",
                "urban_rural": location.urban_rural or "unknown",
                "precision": precision,
                "crime_count": len(crimes_data),
                "crimes": crimes_data,
            },
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    return JsonResponse(geojson)
