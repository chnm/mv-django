from itertools import groupby

from django.contrib import admin
from django.forms import ModelChoiceField
from django.forms.models import ModelChoiceIterator

from locations.models import Location
from mapping_violence.forms import PersonForm
from mapping_violence.models import (
    Crime,
    Person,
    PersonRelation,
    PersonRelationType,
    Weapon,
)


class PersonRelationTypeChoiceIterator(ModelChoiceIterator):
    """Override ModelChoiceIterator in order to group Person-Person
    relationship types by category"""

    def __iter__(self):
        """Override the iterator to group type by category"""
        # first, display empty label if applicable
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        # then group the queryset (ordered by category, then name) by category
        ordered_queryset = self.queryset.order_by("category", "name")
        groups = groupby(ordered_queryset, key=lambda x: x.category)
        # map category keys to their full names for display
        category_names = dict(PersonRelationType.CATEGORY_CHOICES)
        # return the groups in the format expected by ModelChoiceField
        for category, types in groups:
            yield (category_names[category], [(type.id, type.name) for type in types])


class PersonRelationTypeChoiceField(ModelChoiceField):
    """Override ModelChoiceField's iterator property to use ModelChoiceIterator
    override"""

    iterator = PersonRelationTypeChoiceIterator


class PersonInline(admin.TabularInline):
    """Person-Person relationships inline for the Person admin"""

    model = PersonRelation
    verbose_name = "Related Person"
    verbose_name_plural = "Related People"
    form = PersonForm
    fk_name = "from_person"
    extra = 1

    def get_formset(self, request, obj=None, **kwargs):
        """Override 'type' field for PersonRelation, change ModelChoiceField
        to our new PersonRelationTypeChoiceField"""
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields["type"] = PersonRelationTypeChoiceField(
            queryset=PersonRelationType.objects.all(),
            empty_label="Select relationship type...",
            required=False,
        )
        return formset


class PersonReverseInline(admin.TabularInline):
    """Person-Person reverse relationships inline for the Person admin"""

    model = PersonRelation
    verbose_name = "Related Person"
    verbose_name_plural = "Related People (automatically populated)"
    fields = (
        "from_person",
        "relation",
        "notes",
    )
    fk_name = "to_person"
    readonly_fields = ("from_person", "relation", "notes")
    extra = 0
    max_num = 0

    def relation(self, obj=None):
        """Get the relationship type's converse name, if it exists, or else the type name"""
        return (obj.type.converse_name or str(obj.type)) if obj else None


@admin.register(PersonRelationType)
class PersonRelationTypeAdmin(admin.ModelAdmin):
    """Admin for managing the controlled vocabulary of relationships"""

    list_display = ("__str__", "converse_name", "category")
    list_filter = ("name", "category")
    search_fields = ("name", "converse_name")
    ordering = ("name",)

    fieldsets = (
        ("Relationship Names", {"fields": ("name", "converse_name")}),
        ("Classification", {"fields": ("category",)}),
    )


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin for Location entities"""

    list_display = ("name", "parish", "city", "street")
    list_filter = (
        "parish",
        "city",
    )


@admin.register(Crime)
class CrimeAdmin(admin.ModelAdmin):
    """Admin for Crime entities"""

    list_display = (
        "__str__",
        "get_victims",
        "get_perpetrators",
        "weapon",
        "historical_date",
        "get_location",
    )
    list_filter = (
        "violence_caused_death",
        "convicted",
        "pardoned",
        "weapon",
        "historical_date",
    )
    search_fields = ("crime", "motive")
    date_hierarchy = "date"

    fieldsets = (
        ("Crime Details", {"fields": ("crime", "motive", "weapon")}),
        (
            "People Involved",
            {"fields": ("victim", "perpetrator", "judge"), "classes": ("collapse",)},
        ),
        (
            "Time & Place",
            {
                "fields": (
                    "date",
                    "historical_date",
                    "liturgical_occasion",
                    "time_of_day",
                    "address",
                )
            },
        ),
        (
            "Outcomes",
            {
                "fields": ("violence_caused_death", "convicted", "pardoned"),
                "classes": ("collapse",),
            },
        ),
        ("Sources", {"fields": ("source",), "classes": ("collapse",)}),
    )

    def get_victims(self, obj):
        """Display comma-separated list of victims"""
        return ", ".join([str(victim) for victim in obj.victim.all()]) or "No victims"

    get_victims.short_description = "Victims"

    def get_perpetrators(self, obj):
        """Display comma-separated list of perpetrators"""
        return (
            ", ".join([str(perp) for perp in obj.perpetrator.all()])
            or "No perpetrators"
        )

    get_perpetrators.short_description = "Perpetrators"

    def get_location(self, obj):
        """Display location if available"""
        return str(obj.address) if obj.address else "Unknown location"

    get_location.short_description = "Location"


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    """Admin for Person entities"""

    list_display = ("__str__", "gender", "citizenship", "occupation")
    list_filter = ("gender", "citizenship", "occupation")
    search_fields = (
        "first_name",
        "last_name",
    )

    fieldsets = (
        ("Basic Information", {"fields": ("first_name", "last_name", "gender")}),
        (
            "Background",
            {
                "fields": ("occupation", "citizenship", "identifying_information"),
                "classes": ("collapse",),
            },
        ),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
    )

    inlines = (PersonInline,)
    own_pk = None

    def get_form(self, request, obj=None, **kwargs):
        """For Person-Person autocomplete on the PersonAdmin form, keep track of own pk"""
        if obj:
            self.own_pk = obj.pk
        else:
            # reset own_pk to None if we are creating a new person
            self.own_pk = None
        return super().get_form(request, obj, **kwargs)


admin.site.register(Weapon)
