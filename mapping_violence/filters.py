import django_filters
from django.db.models import Q

from locations.models import URBAN_RURAL_CHOICES, City

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
    person = django_filters.CharFilter(
        label="Person (Victim or Perpetrator)",
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
    urban_rural = django_filters.ChoiceFilter(
        choices=URBAN_RURAL_CHOICES,
        field_name="address__urban_rural",
        label="Urban/Rural",
        empty_label="All",
    )

    def filter_by_person(self, queryset, name, value):
        """Filter crimes where a victim or perpetrator name matches the search term"""
        if value:
            person_q = (
                Q(first_name__icontains=value)
                | Q(last_name__icontains=value)
                | Q(given_name__icontains=value)
            )
            matching_people = Person.objects.filter(person_q)
            return queryset.filter(
                Q(victim__in=matching_people) | Q(perpetrator__in=matching_people)
            ).distinct()
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
            "urban_rural",
        ]
