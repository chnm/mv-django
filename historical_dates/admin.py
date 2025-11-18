from django.contrib import admin
from unfold.admin import ModelAdmin

from .forms import HistoricalDateForm
from .models import HistoricalDate


@admin.register(HistoricalDate)
class HistoricalDateAdmin(ModelAdmin):
    form = HistoricalDateForm
    list_display = ("display_date", "edtf_date", "start_date", "end_date", "certainty")
    ordering = ("start_date",)
    list_filter = ("certainty",)
    search_fields = ("display_date", "edtf_date", "notes")
