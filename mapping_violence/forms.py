from dal import autocomplete, forward
from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from mapping_violence.models import Crime, PersonRelation


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
        }
