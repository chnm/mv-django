from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render

from locations.models import City, Location
from mapping_violence.models import WEAPON_CATEGORY_CHOICES, Crime


def map_view(request):
    """Display the map interface with filter options"""
    # Get unique cities and crime types for filter dropdowns
    cities = (
        City.objects.filter(location__crime__isnull=False).distinct().order_by("name")
    )
    crime_types = (
        Crime.objects.exclude(crime="")
        .values_list("crime", flat=True)
        .distinct()
        .order_by("crime")
    )

    context = {
        "cities": cities,
        "crime_types": crime_types,
        "weapon_categories": WEAPON_CATEGORY_CHOICES,
    }
    return render(request, "locations/map.html", context)


def locations_geojson(request):
    """Return locations with crimes as GeoJSON for the map"""
    # Start with locations that have crimes
    locations = Location.objects.select_related("city").filter(crime__isnull=False)

    # Apply filters from request
    city_id = request.GET.get("city")
    crime_type = request.GET.get("crime_type")
    year_from = request.GET.get("year_from")
    year_to = request.GET.get("year_to")
    weapon_category = request.GET.get("weapon_category")

    if city_id:
        locations = locations.filter(city_id=city_id)

    if crime_type:
        locations = locations.filter(crime__crime=crime_type)

    if year_from:
        locations = locations.filter(crime__year__gte=year_from)

    if year_to:
        locations = locations.filter(crime__year__lte=year_to)

    if weapon_category:
        locations = locations.filter(crime__weapon__weapon_category=weapon_category)

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

        crimes_data = []
        for crime in crimes_query.prefetch_related("victim", "perpetrator"):
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
                "category": location.category_of_space or "",
                "description": location.description_of_location or "",
                "current_name": location.current_name or "",
                "sestiere": location.sestiere or "",
                "street": location.street or "",
                "landmark": location.landmark or "",
                "crime_count": len(crimes_data),
                "crimes": crimes_data,
            },
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    return JsonResponse(geojson)
