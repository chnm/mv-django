from itertools import groupby

from django.contrib import admin
from django.forms import ModelChoiceField
from django.forms.models import ModelChoiceIterator
from import_export.admin import ImportExportModelAdmin

from locations.models import Location
from mapping_violence.forms import PersonForm
from mapping_violence.models import (
    Crime,
    Event,
    Person,
    PersonRelation,
    PersonRelationType,
    Weapon,
    Witness,
)
from mapping_violence.resources import CrimeResource


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


class WitnessInline(admin.StackedInline):
    """Witness inline for the Crime admin"""

    model = Witness
    extra = 0
    fields = ("name", "date_of_testimony", "claims", "notes")
    verbose_name = "Witness"
    verbose_name_plural = "Witnesses"


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


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin for Event entities"""

    list_display = ("name", "event_type", "date", "location")
    list_filter = ("event_type", "date")
    search_fields = ("name", "event_type", "description")
    date_hierarchy = "date"

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "event_type", "date", "historical_date")},
        ),
        ("Details", {"fields": ("description", "location"), "classes": ("collapse",)}),
    )


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin for Location entities"""

    list_display = ("name", "category_of_space", "parish", "city", "street")
    list_filter = (
        "category_of_space",
        "parish",
        "city",
    )
    search_fields = ("name", "current_name", "category_of_space", "city", "parish")


@admin.register(Crime)
class CrimeAdmin(ImportExportModelAdmin):
    """Admin for Crime entities with import/export functionality"""

    resource_class = CrimeResource

    list_display = (
        "number",
        "crime",
        "get_victims",
        "get_perpetrators",
        "weapon",
        "date",
        "fatality",
        "get_location",
    )
    list_filter = (
        "fatality",
        "violence_caused_death",
        "convicted",
        "pardoned",
        "arbitration",
        "sentence_enforced",
        "weapon",
        "year",
        "input_by",
    )
    search_fields = ("number", "crime", "motive", "description_of_case")
    date_hierarchy = "date"
    inlines = (WitnessInline,)
    readonly_fields = (
        "year",
        "month",
        "day",
        "day_of_week",
        "date_of_entry",
        "input_by",
        "updated_by",
    )

    fieldsets = (
        ("Basic Information", {"fields": ("number", "crime", "description_of_case")}),
        (
            "Court & Legal Information",
            {
                "fields": (
                    "court",
                    "court_classification",
                    "trial_phase",
                    "arbitration",
                    "sentence",
                    "sentence_enforced",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Date & Time Information",
            {
                "fields": (
                    "date",
                    "historical_date",
                    "year",
                    "month",
                    "day",
                    "day_of_week",
                    "time",
                    "liturgical_occasion",
                    "connected_event",
                ),
            },
        ),
        (
            "People Involved",
            {
                "fields": (
                    "victim",
                    "victim_description",
                    "perpetrator",
                    "assailant_description",
                    "judge",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Case Details", {"fields": ("motive", "relationship", "weapon")}),
        ("Location Information", {"fields": ("address",)}),
        (
            "Outcome Information",
            {
                "fields": (
                    "fatality",
                    "violence_caused_death",
                    "convicted",
                    "pardoned",
                    "accord",
                    "accord_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Source & Archival Information",
            {
                "fields": ("source", "archival_location", "reference"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("input_by", "updated_by", "date_of_entry"),
                "classes": ("collapse",),
            },
        ),
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

    def save_model(self, request, obj, form, change):
        # Auto-populate date components from the main date field
        if obj.date:
            obj.year = str(obj.date.year)
            obj.month = str(obj.date.month)
            obj.day = str(obj.date.day)
            obj.day_of_week = obj.date.strftime("%A")

        # Record the user who created the object
        if not change:
            obj.input_by = request.user
        # And record who edited the object
        else:
            obj.updated_by = request.user

        super().save_model(request, obj, form, change)


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
            "Description & Background",
            {
                "fields": (
                    "description",
                    "occupation",
                    "citizenship",
                    "identifying_information",
                ),
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


@admin.register(Weapon)
class WeaponAdmin(admin.ModelAdmin):
    """Admin for Weapon entities"""

    list_display = ("__str__", "definition", "category")
    list_filter = ("name", "category")
