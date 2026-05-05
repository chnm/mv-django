from itertools import groupby

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.forms import ModelChoiceField
from django.forms.models import ModelChoiceIterator
from django.shortcuts import render
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.import_export.forms import ExportForm, ImportForm
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from locations.models import City, Location
from mapping_violence.forms import CrimeForm, PersonForm
from mapping_violence.models import (
    STATUS_CHOICES,
    Crime,
    Event,
    Person,
    PersonRelation,
    PersonRelationType,
    StatusLog,
    Weapon,
    Witness,
)
from mapping_violence.resources import CrimeResource

# Unregister then re-register to get Unfold styling applied
admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    # Forms loaded from `unfold.forms`
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass


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


class PersonInline(TabularInline):
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


class PersonReverseInline(TabularInline):
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


class WitnessInline(StackedInline):
    """Witness inline for the Crime admin"""

    model = Witness
    extra = 0
    fields = ("name", "date_of_testimony", "claims", "notes")
    verbose_name = "Witness"
    verbose_name_plural = "Witnesses"


class StatusLogInline(TabularInline):
    """Read-only audit trail of status changes."""

    model = StatusLog
    extra = 0
    max_num = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "timestamp", "note")
    fields = ("timestamp", "from_status", "to_status", "changed_by", "note")
    verbose_name = "Status Change"
    verbose_name_plural = "Status History"


def _is_editor(user):
    """Check if a user is in the Editor group (and not a superuser/admin)."""
    return not user.is_superuser and user.groups.filter(name="Editor").exists()


@admin.register(PersonRelationType)
class PersonRelationTypeAdmin(ModelAdmin):
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
class EventAdmin(ModelAdmin):
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


@admin.register(City)
class CityAdmin(ModelAdmin):
    """Admin for City entities"""

    list_display = ("name", "country", "region", "parish", "latitude", "longitude")
    list_filter = ("country", "region", "parish")
    search_fields = ("name", "country", "region", "parish")
    actions = ["assign_country"]

    fieldsets = (
        ("Basic Information", {"fields": ("name", "country", "region", "parish")}),
        (
            "Coordinates",
            {"fields": ("latitude", "longitude"), "classes": ("collapse",)},
        ),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
    )

    @admin.action(description="Assign country to selected cities")
    def assign_country(self, request, queryset):
        class AssignCountryForm(forms.Form):
            country = forms.CharField(
                max_length=255,
                label="Country",
                widget=forms.TextInput(attrs={"placeholder": "e.g., Italy"}),
            )
            region = forms.CharField(
                max_length=255,
                label="Region (optional)",
                required=False,
                widget=forms.TextInput(attrs={"placeholder": "e.g., Veneto, Lombardy"}),
            )

        if "apply" in request.POST:
            form = AssignCountryForm(request.POST)
            if form.is_valid():
                country = form.cleaned_data["country"]
                region = form.cleaned_data["region"]
                update_fields = {"country": country}
                if region:
                    update_fields["region"] = region
                count = queryset.update(**update_fields)
                self.message_user(
                    request,
                    f"Assigned {count} cit{'y' if count == 1 else 'ies'} to {country}.",
                )
                return None
        else:
            form = AssignCountryForm()

        return render(
            request,
            "admin/assign_country.html",
            {
                "title": "Assign country to cities",
                "form": form,
                "queryset": queryset,
                "opts": self.model._meta,
                "action": "assign_country",
            },
        )


@admin.register(Location)
class LocationAdmin(ModelAdmin):
    """Admin for Location entities"""

    list_display = (
        "name",
        "city",
        "category_of_space",
        "urban_rural",
        "get_coordinates",
    )
    list_filter = (
        "city",
        "category_of_space",
        "urban_rural",
        "city__parish",
    )
    search_fields = (
        "name",
        "current_name",
        "category_of_space",
        "city__name",
        "description_of_location",
    )

    fieldsets = (
        ("Basic Information", {"fields": ("name", "city", "current_name")}),
        (
            "Location Details",
            {"fields": ("category_of_space", "description_of_location", "urban_rural")},
        ),
        (
            "Address Components",
            {
                "fields": ("address", "street", "landmark", "sestiere"),
                "classes": ("collapse",),
            },
        ),
        (
            "Specific Coordinates",
            {"fields": ("latitude", "longitude"), "classes": ("collapse",)},
        ),
        (
            "Miscellaneous Fields",
            {
                "fields": ("admin_unit", "parish_religious_order"),
                "classes": ("collapse",),
            },
        ),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
    )

    def get_coordinates(self, obj):
        """Display effective coordinates (specific or city fallback)"""
        lat = obj.effective_latitude
        lon = obj.effective_longitude
        if lat and lon:
            return f"{lat:.4f}, {lon:.4f}"
        return "No coordinates"

    get_coordinates.short_description = "Coordinates"


@admin.register(Crime)
class CrimeAdmin(ImportExportModelAdmin, ModelAdmin):
    """Admin for Crime entities with import/export functionality"""

    form = CrimeForm
    resource_class = CrimeResource
    import_form_class = ImportForm
    export_form_class = ExportForm

    list_display = (
        "number",
        "crime",
        "get_victims",
        "get_perpetrators",
        "weapon",
        "date",
        "fatality",
        "status",
        "assigned_to",
        "get_location",
    )
    list_filter = (
        "status",
        "assigned_to",
        "offense_category",
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
    inlines = (WitnessInline, StatusLogInline)
    readonly_fields = (
        "year",
        "month",
        "day",
        "day_of_week",
        "input_by",
        "date_of_entry",
        "updated_by",
    )
    actions = ["reassign_input_by", "assign_to_editor", "set_status"]

    fieldsets = (
        (
            "Workflow",
            {"fields": ("status", "assigned_to")},
        ),
        (
            "Basic Information",
            {"fields": ("number", "crime", "offense_category", "description_of_case")},
        ),
        (
            "Court & Legal Information",
            {
                "fields": (
                    "court",
                    "court_classification",
                    "trial_phase",
                    "arbitration",
                    "sentence",
                    "sentence_in_absentia",
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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Editors see all records but can only edit their own (handled in has_change_permission)
        return qs

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return super().has_change_permission(request, obj)
        if _is_editor(request.user):
            # Editors can only edit records assigned to them or that they created
            return obj.assigned_to == request.user or obj.input_by == request.user
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if _is_editor(request.user):
            # Editors cannot set status to "done" or reassign records
            readonly.extend(["assigned_to"])
        return readonly

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "status" and _is_editor(request.user):
            # Editors can only set triage, assigned, or needs_review — not done
            kwargs["choices"] = [c for c in STATUS_CHOICES if c[0] != "done"]
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Auto-populate date components from the main date field
        if obj.date:
            obj.year = str(obj.date.year)
            obj.month = str(obj.date.month)
            obj.day = str(obj.date.day)
            obj.day_of_week = obj.date.strftime("%A")

        # Log status changes
        if change and "status" in form.changed_data:
            old_status = form.initial.get("status", "")
            StatusLog.objects.create(
                crime=obj,
                from_status=old_status,
                to_status=obj.status,
                changed_by=request.user,
            )

        # Record the user who created the object
        if not change:
            obj.input_by = request.user
        # And record who edited the object
        else:
            obj.updated_by = request.user

        super().save_model(request, obj, form, change)

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        """Pass the logged-in user to the resource so imported rows are attributed."""
        kwargs = super().get_import_resource_kwargs(request, *args, **kwargs)
        kwargs["user"] = request.user
        return kwargs

    @admin.action(description="Reassign selected crimes to a user")
    def reassign_input_by(self, request, queryset):
        class ReassignForm(forms.Form):
            user = forms.ModelChoiceField(
                queryset=User.objects.filter(is_active=True).order_by("username"),
                label="Assign to",
                empty_label="— select a user —",
            )

        if "apply" in request.POST:
            form = ReassignForm(request.POST)
            if form.is_valid():
                user = form.cleaned_data["user"]
                count = queryset.update(input_by=user)
                self.message_user(request, f"Reassigned {count} crime(s) to {user}.")
                return None
        else:
            form = ReassignForm()

        return render(
            request,
            "admin/reassign_input_by.html",
            {
                "title": "Reassign crimes to a user",
                "form": form,
                "queryset": queryset,
                "opts": self.model._meta,
                "action": "reassign_input_by",
            },
        )

    @admin.action(description="Assign selected records to an editor")
    def assign_to_editor(self, request, queryset):
        class AssignForm(forms.Form):
            editor = forms.ModelChoiceField(
                queryset=User.objects.filter(is_active=True).order_by("username"),
                label="Assign to",
                empty_label="— select a user —",
            )

        if "apply" in request.POST:
            form = AssignForm(request.POST)
            if form.is_valid():
                editor = form.cleaned_data["editor"]
                old_statuses = dict(queryset.values_list("pk", "status"))
                count = queryset.update(assigned_to=editor, status="assigned")
                # Log the status changes
                logs = []
                for pk, old_status in old_statuses.items():
                    if old_status != "assigned":
                        logs.append(
                            StatusLog(
                                crime_id=pk,
                                from_status=old_status,
                                to_status="assigned",
                                changed_by=request.user,
                                note=f"Bulk assigned to {editor}",
                            )
                        )
                if logs:
                    StatusLog.objects.bulk_create(logs)
                self.message_user(request, f"Assigned {count} record(s) to {editor}.")
                return None
        else:
            form = AssignForm()

        return render(
            request,
            "admin/assign_to_editor.html",
            {
                "title": "Assign records to an editor",
                "form": form,
                "queryset": queryset,
                "opts": self.model._meta,
                "action": "assign_to_editor",
            },
        )

    @admin.action(description="Set status on selected records")
    def set_status(self, request, queryset):
        class StatusForm(forms.Form):
            status = forms.ChoiceField(
                choices=STATUS_CHOICES,
                label="New status",
            )

        if "apply" in request.POST:
            form = StatusForm(request.POST)
            if form.is_valid():
                new_status = form.cleaned_data["status"]
                old_statuses = dict(queryset.values_list("pk", "status"))
                count = queryset.update(status=new_status)
                # Log the status changes
                logs = []
                for pk, old_status in old_statuses.items():
                    if old_status != new_status:
                        logs.append(
                            StatusLog(
                                crime_id=pk,
                                from_status=old_status,
                                to_status=new_status,
                                changed_by=request.user,
                                note="Bulk status change",
                            )
                        )
                if logs:
                    StatusLog.objects.bulk_create(logs)
                self.message_user(
                    request,
                    f"Set {count} record(s) to '{dict(STATUS_CHOICES)[new_status]}'.",
                )
                return None
        else:
            form = StatusForm()

        return render(
            request,
            "admin/set_status.html",
            {
                "title": "Set status on selected records",
                "form": form,
                "queryset": queryset,
                "opts": self.model._meta,
                "action": "set_status",
            },
        )


@admin.register(StatusLog)
class StatusLogAdmin(ModelAdmin):
    """Read-only admin for the workflow status audit trail."""

    list_display = (
        "crime",
        "from_status",
        "to_status",
        "changed_by",
        "timestamp",
        "note",
    )
    list_filter = ("to_status", "changed_by")
    search_fields = ("crime__number", "note")
    readonly_fields = (
        "crime",
        "from_status",
        "to_status",
        "changed_by",
        "timestamp",
        "note",
    )
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Person)
class PersonAdmin(ModelAdmin):
    """Admin for Person entities"""

    list_display = ("__str__", "honorific", "gender", "citizenship", "occupation")
    list_filter = ("gender", "citizenship", "occupation")
    search_fields = (
        "first_name",
        "last_name",
        "given_name",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "given_name",
                    "honorific",
                    "gender",
                )
            },
        ),
        (
            "Description & Background",
            {
                "fields": (
                    "description",
                    "occupation",
                    "citizenship",
                    "nationality_ethnicity",
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
class WeaponAdmin(ModelAdmin):
    """Admin for Weapon entities"""

    list_display = ("__str__", "weapon_category", "weapon_subcategory", "category")
    list_filter = ("weapon_category",)
    search_fields = ("name", "weapon_subcategory")
    fieldsets = (
        ("Basic Information", {"fields": ("name", "definition")}),
        (
            "Classification",
            {"fields": ("weapon_category", "weapon_subcategory", "category")},
        ),
    )
