from django.db.models import Q
from django.http import JsonResponse

from .models import Person


def person_search(request):
    """AJAX endpoint for person autocomplete.

    GET params:
        q: search term (min 2 chars)
        city: optional city ID to scope results to persons involved in crimes at that city
    """
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse([], safe=False)

    persons = Person.objects.filter(
        Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(given_name__icontains=q)
    )

    city_id = request.GET.get("city")
    if city_id:
        persons = persons.filter(
            Q(crime_victim__address__city_id=city_id)
            | Q(crime_perpetrator__address__city_id=city_id)
        ).distinct()

    persons = persons.distinct()[:25]

    results = [{"value": str(p.id), "text": str(p)} for p in persons]
    return JsonResponse(results, safe=False)
