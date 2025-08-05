import time

from django.db import models
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim


class Location(models.Model):
    name = models.CharField(max_length=255)
    current_name = models.CharField(max_length=255)
    admin_unit = models.CharField(max_length=255, verbose_name="Administrative unit")
    parish = models.CharField(
        blank=True, max_length=255, help_text="Input Parish, if known"
    )
    parish_religious_order = models.CharField(
        blank=True, null=True, max_length=255, verbose_name="Religious order"
    )

    sestiere = models.CharField(
        blank=True, max_length=255, help_text="If Venetian crime, input neighborhood"
    )
    description_of_location = models.TextField(
        blank=True,
        help_text="Input description of location if given. Example: in front of the Madonna di Miracoli, on the bridge of sighs",
    )

    city = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input city (or village), if known. Example: Venice, Lake Garda",
    )
    address = models.CharField(blank=True, null=True, max_length=255)
    landmark = models.CharField(blank=True, null=True, max_length=255)
    street = models.CharField(blank=True, null=True, max_length=255)

    notes = models.TextField(
        blank=True,
        null=True,
        max_length=255,
        help_text="Non-public notes on the location.",
    )
    category_of_space = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input category of space, if applicable (sacred, public, domestic)",
    )

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
