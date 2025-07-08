from django import forms
from edtf.parser.grammar import parse_edtf as safe_parse_edtf
from .models import HistoricalDate

class HistoricalDateForm(forms.ModelForm):
    class Meta:
        model = HistoricalDate
        fields = "__all__"

    def clean_edtf_date(self):
        value = self.cleaned_data.get("edtf_date")
        if value:
            try:
                safe_parse_edtf(value)
            except Exception:
                raise forms.ValidationError("Invalid EDTF string.")
        return value

