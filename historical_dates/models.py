from django.db import models
from .utils import parse_edtf_to_dates

class HistoricalDate(models.Model):
    display_date = models.CharField(
        max_length=255,
        help_text="Human-readable date (e.g. 'circa 1850', 'early 19th century')."
    )
    edtf_date = models.CharField(
        max_length=255, 
        blank=True, 
        help_text=(
        'EDTF expression (e.g. "1850-03~" or "1800/1850"). '
        'See <a href="https://www.loc.gov/standards/datetime/" target="_blank" rel="noopener">EDTF documentation</a>.'
    ),
        verbose_name="EDTF date"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    certainty = models.CharField(
        max_length=20,
        choices=[
            ("exact", "Exact"),
            ("approximate", "Approximate"),
            ("uncertain", "Uncertain"),
        ],
        default="exact"
    )
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.edtf_date:
            start, end = parse_edtf_to_dates(self.edtf_date)
            self.start_date = start
            self.end_date = end
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_date or self.edtf_date or str(self.start_date)

    class Meta:
        ordering = ["start_date"]

