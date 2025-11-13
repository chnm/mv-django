import django_filters

from locations.models import City

from .models import Crime


class CrimeFilter(django_filters.FilterSet):
    """Filter for Crime data"""

    number = django_filters.CharFilter(lookup_expr="icontains", label="Case Number")
    crime = django_filters.ChoiceFilter(
        label="Crime Type",
        empty_label="All Crime Types",
        choices=lambda: [
            (ct, ct)
            for ct in Crime.objects.exclude(crime="")
            .values_list("crime", flat=True)
            .distinct()
            .order_by("crime")
        ],
    )
    city = django_filters.ModelChoiceFilter(
        queryset=City.objects.all(),
        field_name="address__city",
        label="City",
        empty_label="All Cities",
    )
    year = django_filters.CharFilter(lookup_expr="icontains", label="Year")
    fatality = django_filters.BooleanFilter(label="Fatal Only")

    class Meta:
        model = Crime
        fields = ["number", "crime", "city", "year", "fatality"]
