import django_filters
from django.db.models import Q

from locations.models import URBAN_RURAL_CHOICES, City, Location

from .models import WEAPON_CATEGORY_CHOICES, Crime, Weapon


class CrimeFilter(django_filters.FilterSet):
    """Shared filter for Crime data — used by both data table and map."""

    number = django_filters.CharFilter(lookup_expr="icontains", label="Case Number")

    country = django_filters.CharFilter(
        field_name="address__city__country",
        label="Country",
    )

    city = django_filters.ModelChoiceFilter(
        queryset=City.objects.all(),
        field_name="address__city",
        label="City",
        empty_label="All Cities",
    )

    location = django_filters.ModelChoiceFilter(
        queryset=Location.objects.all(),
        field_name="address",
        label="Location",
        empty_label="All Locations",
    )

    crime_type = django_filters.ChoiceFilter(
        field_name="crime",
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

    person = django_filters.CharFilter(
        label="Person",
        method="filter_by_person",
    )

    year_from = django_filters.NumberFilter(
        label="Year From",
        method="filter_year_from",
    )

    year_to = django_filters.NumberFilter(
        label="Year To",
        method="filter_year_to",
    )

    fatality = django_filters.BooleanFilter(label="Fatal Only")

    weapon_category = django_filters.ChoiceFilter(
        choices=WEAPON_CATEGORY_CHOICES,
        field_name="weapon__weapon_category",
        label="Weapon Category",
        empty_label="All Weapon Categories",
    )

    weapon_subcategory = django_filters.ChoiceFilter(
        field_name="weapon__weapon_subcategory",
        label="Weapon Subcategory",
        empty_label="All Subcategories",
        choices=lambda: [
            (sc, sc)
            for sc in Weapon.objects.exclude(weapon_subcategory="")
            .values_list("weapon_subcategory", flat=True)
            .distinct()
            .order_by("weapon_subcategory")
        ],
    )

    urban_rural = django_filters.ChoiceFilter(
        choices=URBAN_RURAL_CHOICES,
        field_name="address__urban_rural",
        label="Urban/Rural",
        empty_label="All",
    )

    def filter_by_person(self, queryset, name, value):
        """Filter crimes involving specific persons.

        Accepts comma-separated person IDs (from Tom Select)
        or a text search term (fallback).
        """
        if not value:
            return queryset

        # Try parsing as comma-separated IDs first
        parts = [p.strip() for p in value.split(",") if p.strip()]
        try:
            person_ids = [int(p) for p in parts]
            return queryset.filter(
                Q(victim__id__in=person_ids) | Q(perpetrator__id__in=person_ids)
            ).distinct()
        except ValueError:
            pass

        # Fallback: text search
        from .models import Person

        person_q = (
            Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
            | Q(given_name__icontains=value)
        )
        matching_people = Person.objects.filter(person_q)
        return queryset.filter(
            Q(victim__in=matching_people) | Q(perpetrator__in=matching_people)
        ).distinct()

    def filter_year_from(self, queryset, name, value):
        if value:
            return queryset.filter(year__gte=str(value))
        return queryset

    def filter_year_to(self, queryset, name, value):
        if value:
            return queryset.filter(year__lte=str(value))
        return queryset

    class Meta:
        model = Crime
        fields = [
            "number",
            "country",
            "city",
            "location",
            "crime_type",
            "person",
            "year_from",
            "year_to",
            "fatality",
            "weapon_category",
            "weapon_subcategory",
            "urban_rural",
        ]
