from django.db import models

class Location(models.Model):
    name = models.CharField(max_length=255)
    parish = models.CharField(blank=True, null=True, max_length=255)
    city = models.CharField(blank=True, null=True, max_length=255)
    address = models.CharField(blank=True, null=True, max_length=255)
    landmark = models.CharField(blank=True, null=True, max_length=255)
    street = models.CharField(blank=True, null=True, max_length=255)
    notes = models.TextField(blank=True, null=True, max_length=255)

    latitude = models.DecimalField(
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        help_text="This will be auto-generated if left empty.",
    )
    longitude = models.DecimalField(
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        help_text="This will be auto-generated if left empty.",
    )

    def __str__(self):
        return self.name
