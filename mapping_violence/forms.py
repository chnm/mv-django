import json

from dal import autocomplete, forward
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from import_export.forms import ConfirmImportForm
from unfold.contrib.import_export.forms import ImportForm

from mapping_violence.models import Crime, ImportProfile, PersonRelation, SourceDataset


class CrimeImportForm(ImportForm):
    source_dataset = forms.ModelChoiceField(
        queryset=SourceDataset.objects.all(),
        required=False,
        help_text="Identifies the scholar or dataset that supplied these records.",
    )
    import_profile = forms.ModelChoiceField(
        queryset=ImportProfile.objects.select_related("source_dataset"),
        required=False,
        help_text="Optionally begin with a previously saved column mapping.",
    )


class ImportColumnMappingForm(forms.Form):
    mapping_step = forms.BooleanField(initial=True, widget=forms.HiddenInput())
    import_file_name = forms.CharField(widget=forms.HiddenInput())
    original_file_name = forms.CharField(widget=forms.HiddenInput())
    format = forms.CharField(widget=forms.HiddenInput())
    resource = forms.CharField(widget=forms.HiddenInput(), required=False)
    source_dataset = forms.CharField(widget=forms.HiddenInput(), required=False)
    import_profile = forms.CharField(widget=forms.HiddenInput(), required=False)
    source_headers = forms.CharField(widget=forms.HiddenInput())
    save_mapping = forms.BooleanField(
        required=False,
        label="Save this mapping for future imports",
    )
    profile_name = forms.CharField(
        required=False,
        max_length=255,
        label="Mapping name",
        help_text="Use a descriptive name such as “Rossi archive export”.",
    )

    def __init__(
        self,
        *args,
        source_headers=None,
        target_columns=None,
        initial_mapping=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.source_headers = list(source_headers or [])
        self.mapping_fields = []
        choices = [("", "— Ignore this column —")]
        choices.extend((column, column) for column in (target_columns or []))
        initial_mapping = initial_mapping or {}

        for index, header in enumerate(self.source_headers):
            field_name = f"column_{index}"
            self.fields[field_name] = forms.ChoiceField(
                label=header,
                choices=choices,
                required=False,
                initial=initial_mapping.get(header, ""),
            )
            self.mapping_fields.append((header, self[field_name]))

        self.order_fields(
            [
                *(name for name in self.fields if name.startswith("column_")),
                "save_mapping",
                "profile_name",
                *(
                    name
                    for name in self.fields
                    if name
                    not in {
                        *(
                            f"column_{index}"
                            for index in range(len(self.source_headers))
                        ),
                        "save_mapping",
                        "profile_name",
                    }
                ),
            ]
        )

    def clean(self):
        cleaned_data = super().clean()
        selected = [
            cleaned_data.get(f"column_{index}")
            for index in range(len(self.source_headers))
        ]
        selected = [value for value in selected if value]
        duplicates = sorted({value for value in selected if selected.count(value) > 1})
        if duplicates:
            raise forms.ValidationError(
                "Each destination can be used only once. Duplicate selections: "
                + ", ".join(duplicates)
            )
        if cleaned_data.get("save_mapping") and not (
            cleaned_data.get("profile_name") or cleaned_data.get("import_profile")
        ):
            self.add_error(
                "profile_name",
                "Enter a name when saving a new mapping.",
            )
        return cleaned_data

    def get_column_mapping(self):
        return {
            header: self.cleaned_data.get(f"column_{index}", "")
            for index, header in enumerate(self.source_headers)
        }


class CrimeConfirmImportForm(ConfirmImportForm):
    column_mapping = forms.CharField(widget=forms.HiddenInput(), required=False)
    source_dataset = forms.CharField(widget=forms.HiddenInput(), required=False)
    import_profile = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean_column_mapping(self):
        value = self.cleaned_data.get("column_mapping")
        if not value:
            return {}
        try:
            mapping = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise forms.ValidationError("The saved column mapping is invalid.") from exc
        if not isinstance(mapping, dict):
            raise forms.ValidationError("The saved column mapping is invalid.")
        return mapping


class PersonForm(forms.ModelForm):
    class Meta:
        model = PersonRelation
        fields = (
            "to_person",
            "type",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
            "to_person": autocomplete.ModelSelect2(
                forward=(forward.Const(True, "is_person_person_form"),),
            ),
            "type": autocomplete.ModelSelect2(
                url="personpersonrelationtype-autocomplete",
            ),
        }
        help_texts = {
            "to_person": "Please check auto-populated and manually-input people sections to ensure you are not entering the same relationship twice. If there is more than one relationship between the same two people, record the family relationship and add a note about the other relationship."
        }


class CrimeForm(forms.ModelForm):
    class Meta:
        model = Crime
        fields = "__all__"
        widgets = {
            "victim": FilteredSelectMultiple("Victims", is_stacked=False),
            "perpetrator": FilteredSelectMultiple("Assailants", is_stacked=False),
            "weapon": FilteredSelectMultiple("Weapons", is_stacked=False),
        }
