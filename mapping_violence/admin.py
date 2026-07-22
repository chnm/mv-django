import json
import os
import re
from itertools import groupby

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.forms import ModelChoiceField
from django.forms.models import ModelChoiceIterator
from django.shortcuts import render
from django.template.response import TemplateResponse
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.import_export.forms import ExportForm
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from locations.models import City, Location
from mapping_violence.forms import (
    CrimeConfirmImportForm,
    CrimeForm,
    CrimeImportForm,
    ImportColumnMappingForm,
    PersonForm,
)
from mapping_violence.models import (
    STATUS_CHOICES,
    Crime,
    CrimeImage,
    Event,
    ExternalPersonIdentifier,
    ImportBatch,
    ImportProfile,
    Person,
    PersonRelation,
    PersonRelationType,
    SourceDataset,
    StatusLog,
    Weapon,
    Witness,
)
from mapping_violence.resources import (
    ADDITIONAL_IMPORT_COLUMNS,
    CrimeResource,
    MiduraCrimeResource,
)

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


class CrimeImageInline(TabularInline):
    """Image attachments for a crime record."""

    model = CrimeImage
    extra = 1
    fields = ("image", "caption", "order")


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


@admin.register(SourceDataset)
class SourceDatasetAdmin(ModelAdmin):
    """Admin for researcher/source datasets used in imports."""

    list_display = ("name", "contact_name")
    search_fields = ("name", "contact_name", "description", "notes")

    fieldsets = (
        ("Dataset", {"fields": ("name", "description", "contact_name")}),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
    )


@admin.register(ExternalPersonIdentifier)
class ExternalPersonIdentifierAdmin(ModelAdmin):
    """Admin for external person IDs mapped onto local Person records."""

    list_display = (
        "source_dataset",
        "external_id",
        "person",
        "raw_name",
        "resolution_status",
    )
    list_filter = ("source_dataset", "resolution_status")
    search_fields = (
        "external_id",
        "raw_name",
        "person__first_name",
        "person__last_name",
        "person__given_name",
    )

    fieldsets = (
        (
            "Identifier",
            {"fields": ("source_dataset", "external_id", "raw_name")},
        ),
        ("Resolution", {"fields": ("person", "resolution_status", "notes")}),
    )


@admin.register(ImportBatch)
class ImportBatchAdmin(ModelAdmin):
    """Admin for tracking imported source files."""

    list_display = (
        "original_filename",
        "source_dataset",
        "import_profile",
        "status",
        "uploaded_by",
        "uploaded_at",
    )
    list_filter = ("source_dataset", "import_profile", "status", "uploaded_by")
    search_fields = ("original_filename", "import_profile", "notes")
    readonly_fields = ("uploaded_at",)

    fieldsets = (
        (
            "Import",
            {
                "fields": (
                    "source_dataset",
                    "original_filename",
                    "import_profile",
                    "status",
                )
            },
        ),
        ("Metadata", {"fields": ("uploaded_by", "uploaded_at")}),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
    )


@admin.register(ImportProfile)
class ImportProfileAdmin(ModelAdmin):
    """Admin for reusable contributor column mappings."""

    list_display = ("name", "source_dataset", "created_by", "updated_at")
    list_filter = ("source_dataset", "created_by")
    search_fields = ("name", "source_dataset__name")
    readonly_fields = ("created_by", "created_at", "updated_at")

    fieldsets = (
        ("Mapping", {"fields": ("name", "source_dataset", "column_mapping")}),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


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
    resource_classes = [CrimeResource, MiduraCrimeResource]
    import_form_class = CrimeImportForm
    confirm_form_class = CrimeConfirmImportForm
    export_form_class = ExportForm

    list_display = (
        "number",
        "crime",
        "get_victims",
        "get_perpetrators",
        "get_weapons",
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
        "weapon__weapon_category",
        "year",
        "input_by",
    )
    search_fields = ("number", "crime", "motive", "description_of_case")
    date_hierarchy = "date"
    inlines = (WitnessInline, CrimeImageInline, StatusLogInline)
    readonly_fields = (
        "year",
        "month",
        "day",
        "day_of_week",
        "input_by",
        "date_of_entry",
        "updated_by",
        "import_batch",
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
        (
            "Import Provenance",
            {"fields": ("import_batch",), "classes": ("collapse",)},
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

    def get_weapons(self, obj):
        """Display comma-separated list of weapons"""
        return ", ".join([str(w) for w in obj.weapon.all()]) or "—"

    get_weapons.short_description = "Weapon(s)"

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
        """Pass attribution and any user-selected column mapping to the resource."""
        kwargs = super().get_import_resource_kwargs(request, *args, **kwargs)
        kwargs["user"] = request.user
        form = kwargs.pop("form", None)
        if form and hasattr(form, "cleaned_data"):
            source_dataset_id = form.cleaned_data.get("source_dataset")
            if isinstance(source_dataset_id, SourceDataset):
                kwargs["source_dataset"] = source_dataset_id
            elif source_dataset_id:
                kwargs["source_dataset"] = SourceDataset.objects.filter(
                    pk=source_dataset_id
                ).first()

            if hasattr(form, "get_column_mapping"):
                kwargs["column_mapping"] = form.get_column_mapping()
            else:
                mapping = form.cleaned_data.get("column_mapping")
                if isinstance(mapping, str):
                    try:
                        mapping = json.loads(mapping)
                    except (TypeError, ValueError):
                        mapping = {}
                kwargs["column_mapping"] = mapping or {}
        return kwargs

    def get_confirm_form_initial(self, request, import_form):
        initial = super().get_confirm_form_initial(request, import_form)
        if import_form:
            source_dataset = import_form.cleaned_data.get("source_dataset")
            import_profile = import_form.cleaned_data.get("import_profile")
            initial.update(
                {
                    "source_dataset": getattr(source_dataset, "pk", ""),
                    "import_profile": getattr(import_profile, "pk", ""),
                    "column_mapping": "",
                }
            )
        return initial

    def import_action(self, request, **kwargs):
        """Insert an interactive column-mapping step before the import preview."""
        if request.method != "POST":
            return super().import_action(request, **kwargs)
        if "mapping_step" in request.POST:
            return self._preview_column_mapping(request, **kwargs)

        import_form = self.create_import_form(request)
        if not import_form.is_valid():
            return super().import_action(request, **kwargs)

        # Specialized resources retain their existing, profile-specific workflow.
        resource_index = int(import_form.cleaned_data.get("resource") or 0)
        if (
            self.get_import_resource_classes(request)[resource_index]
            is not CrimeResource
        ):
            return super().import_action(request, **kwargs)

        if not self.has_import_permission(request):
            raise PermissionDenied

        input_format = self.get_import_formats()[
            int(import_form.cleaned_data["format"])
        ]()
        if not input_format.is_binary():
            input_format.encoding = self.from_encoding
        import_file = import_form.cleaned_data["import_file"]
        tmp_storage = self.write_to_tmp_storage(import_file, input_format)
        import_file.tmp_storage_name = tmp_storage.name

        try:
            dataset = input_format.create_dataset(tmp_storage.read())
        except Exception as exc:
            tmp_storage.remove()
            self.add_data_read_fail_error_to_form(import_form, exc)
            return self._render_import_upload(request, import_form)

        if not dataset:
            tmp_storage.remove()
            import_form.add_error(
                "import_file",
                "No valid data was found in the uploaded file.",
            )
            return self._render_import_upload(request, import_form)

        profile = import_form.cleaned_data.get("import_profile")
        initial_mapping = self._suggest_column_mapping(dataset.headers)
        if profile:
            initial_mapping.update(profile.column_mapping)

        initial = {
            "import_file_name": tmp_storage.name,
            "original_file_name": import_file.name,
            "format": import_form.cleaned_data["format"],
            "resource": import_form.cleaned_data.get("resource", ""),
            "source_dataset": getattr(
                import_form.cleaned_data.get("source_dataset"), "pk", ""
            ),
            "import_profile": getattr(profile, "pk", ""),
            "source_headers": json.dumps(dataset.headers),
            "profile_name": profile.name if profile else "",
        }
        mapping_form = ImportColumnMappingForm(
            source_headers=dataset.headers,
            target_columns=self._canonical_import_columns(),
            initial_mapping=initial_mapping,
            initial=initial,
        )
        return self._render_mapping_form(request, mapping_form, dataset)

    def _preview_column_mapping(self, request, **kwargs):
        try:
            source_headers = json.loads(request.POST.get("source_headers", "[]"))
        except (TypeError, ValueError):
            source_headers = []
        if not isinstance(source_headers, list):
            source_headers = []

        mapping_form = ImportColumnMappingForm(
            request.POST,
            source_headers=source_headers,
            target_columns=self._canonical_import_columns(),
        )
        try:
            dataset = self._load_temporary_import(
                request.POST.get("import_file_name"),
                request.POST.get("format"),
            )
        except (OSError, ValueError, IndexError) as exc:
            mapping_form.add_error(
                None, f"The uploaded file could not be reopened: {exc}"
            )
            return self._render_mapping_form(request, mapping_form, None)

        if source_headers != list(dataset.headers or []):
            mapping_form.add_error(
                None,
                "The uploaded file headers no longer match this mapping session. "
                "Please begin the import again.",
            )
            return self._render_mapping_form(request, mapping_form, dataset)

        if not mapping_form.is_valid():
            return self._render_mapping_form(request, mapping_form, dataset)

        mapping = mapping_form.get_column_mapping()
        profile_id = mapping_form.cleaned_data.get("import_profile")
        if mapping_form.cleaned_data.get("save_mapping"):
            profile = (
                ImportProfile.objects.filter(pk=profile_id).first()
                if profile_id
                else None
            )
            profile_name = mapping_form.cleaned_data.get("profile_name") or profile.name
            source_dataset_id = mapping_form.cleaned_data.get("source_dataset") or None
            profile, _ = ImportProfile.objects.update_or_create(
                name=profile_name,
                defaults={
                    "source_dataset_id": source_dataset_id,
                    "column_mapping": mapping,
                    "created_by": request.user,
                },
            )
            profile_id = profile.pk

        res_kwargs = self.get_import_resource_kwargs(
            request, form=mapping_form, **kwargs
        )
        resource = CrimeResource(**res_kwargs)
        result = resource.import_data(
            dataset,
            dry_run=True,
            raise_errors=False,
            file_name=mapping_form.cleaned_data["original_file_name"],
            user=request.user,
        )

        confirm_form = None
        if not result.has_errors() and not result.has_validation_errors():
            confirm_form = CrimeConfirmImportForm(
                initial={
                    "import_file_name": mapping_form.cleaned_data["import_file_name"],
                    "original_file_name": mapping_form.cleaned_data[
                        "original_file_name"
                    ],
                    "format": mapping_form.cleaned_data["format"],
                    "resource": mapping_form.cleaned_data.get("resource", ""),
                    "source_dataset": mapping_form.cleaned_data.get(
                        "source_dataset", ""
                    ),
                    "import_profile": profile_id or "",
                    "column_mapping": json.dumps(mapping),
                }
            )

        context = self.get_import_context_data()
        context.update(self.admin_site.each_context(request))
        context.update(
            {
                "title": "Import preview",
                "confirm_form": confirm_form,
                "result": result,
                "opts": self.model._meta,
                "media": self.media,
                "import_error_display": self.import_error_display,
            }
        )
        request.current_app = self.admin_site.name
        return TemplateResponse(request, [self.import_template_name], context)

    def _load_temporary_import(self, storage_name, format_index):
        storage_name = os.path.basename(storage_name or "")
        input_format = self.get_import_formats()[int(format_index)](
            encoding=self.from_encoding
        )
        encoding = None if input_format.is_binary() else self.from_encoding
        tmp_storage = self.get_tmp_storage_class()(
            name=storage_name,
            encoding=encoding,
            read_mode=input_format.get_read_mode(),
            **self.get_tmp_storage_class_kwargs(),
        )
        return input_format.create_dataset(tmp_storage.read())

    def _canonical_import_columns(self):
        resource = CrimeResource()
        declared = [field.column_name for field in resource.get_import_fields()]
        return list(dict.fromkeys([*declared, *ADDITIONAL_IMPORT_COLUMNS]))

    def _suggest_column_mapping(self, source_headers):
        targets = self._canonical_import_columns()
        normalized_targets = {
            re.sub(r"[^a-z0-9]", "", target.lower()): target for target in targets
        }
        aliases = {
            "caseno": "Number",
            "casenumber": "Number",
            "incident": "Crime",
            "incidenttype": "Crime",
            "place": "City",
            "weapon": "Type_of_Weapon",
        }
        suggestions = {}
        for header in source_headers:
            normalized = re.sub(r"[^a-z0-9]", "", str(header).lower())
            suggestions[header] = normalized_targets.get(
                normalized, aliases.get(normalized, "")
            )
        return suggestions

    def _render_mapping_form(self, request, form, dataset):
        mapping_rows = []
        sample_data = list(dataset[:3]) if dataset else []
        for index, (header, bound_field) in enumerate(form.mapping_fields):
            mapping_rows.append(
                {
                    "header": header,
                    "field": bound_field,
                    "samples": [row[index] for row in sample_data],
                }
            )
        context = self.admin_site.each_context(request)
        context.update(
            {
                "title": "Map spreadsheet columns",
                "opts": self.model._meta,
                "mapping_form": form,
                "mapping_rows": mapping_rows,
            }
        )
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            ["admin/mapping_violence/crime/map_import_columns.html"],
            context,
        )

    def _render_import_upload(self, request, import_form):
        context = self.get_import_context_data()
        context.update(self.admin_site.each_context(request))
        context.update(
            {
                "title": "Import",
                "form": import_form,
                "opts": self.model._meta,
                "media": self.media + import_form.media,
                "fields_list": [],
                "import_error_display": self.import_error_display,
            }
        )
        request.current_app = self.admin_site.name
        return TemplateResponse(request, [self.import_template_name], context)

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

    list_display = ("__str__", "weapon_category", "weapon_subcategory", "crime_count")
    list_filter = ("weapon_category",)
    search_fields = ("name", "weapon_subcategory")
    actions = ["merge_weapons"]
    fieldsets = (
        ("Basic Information", {"fields": ("name", "definition")}),
        (
            "Classification",
            {"fields": ("weapon_category", "weapon_subcategory")},
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_crime_count=Count("crime"))

    def crime_count(self, obj):
        return obj._crime_count

    crime_count.short_description = "Cases"
    crime_count.admin_order_field = "_crime_count"

    @admin.action(description="Merge selected weapons into one")
    def merge_weapons(self, request, queryset):
        if queryset.count() < 2:
            self.message_user(request, "Select at least two weapons to merge.")
            return None

        class MergeForm(forms.Form):
            primary = forms.ModelChoiceField(
                queryset=queryset,
                label="Keep this weapon",
                empty_label=None,
                widget=forms.RadioSelect,
            )

        if "apply" in request.POST:
            form = MergeForm(request.POST)
            form.fields["primary"].queryset = queryset
            if form.is_valid():
                primary = form.cleaned_data["primary"]
                duplicates = queryset.exclude(pk=primary.pk)

                # Transfer all crime associations from duplicates to primary
                merged_count = 0
                for dup in duplicates:
                    for crime in dup.crime_set.all():
                        crime.weapon.add(primary)
                        crime.weapon.remove(dup)
                        merged_count += 1
                    dup.delete()

                dup_count = len(duplicates)
                self.message_user(
                    request,
                    f'Merged {dup_count} weapon(s) into "{primary.name}". '
                    f"{merged_count} crime association(s) transferred.",
                )
                return None
        else:
            form = MergeForm()

        return render(
            request,
            "admin/merge_weapons.html",
            {
                "title": "Merge weapons",
                "form": form,
                "queryset": queryset,
                "opts": self.model._meta,
                "action": "merge_weapons",
            },
        )
