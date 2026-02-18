import django_filters
from django.db.models import Q

from locations.models import City

from .models import WEAPON_CATEGORY_CHOICES, Crime, Person


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
    person = django_filters.ModelChoiceFilter(
        queryset=Person.objects.filter(
            Q(crime_victim__isnull=False) | Q(crime_perpetrator__isnull=False)
        )
        .exclude(Q(last_name="") | Q(last_name__isnull=True))
        .distinct()
        .order_by("last_name", "first_name"),
        label="Person (Victim or Perpetrator)",
        empty_label="All People",
        method="filter_by_person",
    )
    year = django_filters.CharFilter(lookup_expr="icontains", label="Year")
    fatality = django_filters.BooleanFilter(label="Fatal Only")
    weapon_category = django_filters.ChoiceFilter(
        choices=WEAPON_CATEGORY_CHOICES,
        field_name="weapon__weapon_category",
        label="Weapon Category",
        empty_label="All Weapon Categories",
    )
    weapon_subcategory = django_filters.CharFilter(
        field_name="weapon__weapon_subcategory",
        lookup_expr="icontains",
        label="Weapon Subcategory",
    )

    def filter_by_person(self, queryset, name, value):
        """Filter crimes where the person is either a victim or perpetrator"""
        if value:
            return queryset.filter(Q(victim=value) | Q(perpetrator=value)).distinct()
        return queryset

    class Meta:
        model = Crime
        fields = [
            "number",
            "crime",
            "city",
            "person",
            "year",
            "fatality",
            "weapon_category",
            "weapon_subcategory",
        ]
