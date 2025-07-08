from django.contrib import admin
from .models import HistoricalDate
from .forms import HistoricalDateForm

@admin.register(HistoricalDate)
class HistoricalDateAdmin(admin.ModelAdmin):
    form = HistoricalDateForm
    list_display = ("display_date", "edtf_date", "start_date", "end_date", "certainty")
    ordering = ("start_date",)
    list_filter = ("certainty",)
    search_fields = ("display_date", "edtf_date", "notes")

