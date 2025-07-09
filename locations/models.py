import time

from django.db import models
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim


class Location(models.Model):
    name = models.CharField(max_length=255)
    current_name = models.CharField(max_length=255)
    admin_unit = models.CharField(max_length=255, verbose_name="Administrative unit")
    parish = models.CharField(blank=True, null=True, max_length=255)
    parish_religious_order = models.CharField(
        blank=True, null=True, max_length=255, verbose_name="Religious order"
    )

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

    def geocode_address(self):
        if not self.address or not self.city:
            return

        geolocator = Nominatim(user_agent="mapping_violence_chnm")
        full_address = f"{self.address}, {self.city}"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                location = geolocator.geocode(full_address, timeout=10)
                if location:
                    self.latitude = location.latitude
                    self.longitude = location.longitude
                    return
            except GeocoderTimedOut:
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retrying
                    continue
            except GeocoderServiceError:
                break  # Don't retry on service errors
