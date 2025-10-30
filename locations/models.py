import time

from django.db import models
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
from geopy.geocoders import Nominatim


class City(models.Model):
    """Model for cities/towns with general coordinates"""

    name = models.CharField(max_length=255, unique=True)
    parish = models.CharField(
        blank=True, max_length=255, help_text="Administrative parish or region"
    )
    latitude = models.DecimalField(
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        help_text="General city latitude coordinate",
    )
    longitude = models.DecimalField(
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        help_text="General city longitude coordinate",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="General notes about the city",
    )

    class Meta:
        verbose_name_plural = "Cities"

    def __str__(self):
        return self.name


class Location(models.Model):
    """Model for specific locations within cities"""

    name = models.CharField(max_length=255, help_text="Name of the specific location")
    city = models.ForeignKey(
        City, on_delete=models.CASCADE, help_text="The city this location is in"
    )
    current_name = models.CharField(
        max_length=255, blank=True, help_text="Current name if different"
    )

    # Location-specific details
    category_of_space = models.CharField(
        blank=True,
        max_length=255,
        help_text="Category of space: sacred, public, domestic, etc.",
    )
    description_of_location = models.TextField(
        blank=True,
        help_text="Specific description: in front of the Madonna di Miracoli, on the bridge of sighs",
    )

    # Address components
    address = models.CharField(blank=True, null=True, max_length=255)
    landmark = models.CharField(blank=True, null=True, max_length=255)
    street = models.CharField(blank=True, null=True, max_length=255)

    # Venice-specific
    sestiere = models.CharField(
        blank=True, max_length=255, help_text="If Venetian location, input neighborhood"
    )

    # Legacy/compatibility fields
    admin_unit = models.CharField(
        max_length=255, blank=True, verbose_name="Administrative unit"
    )
    parish_religious_order = models.CharField(
        blank=True, null=True, max_length=255, verbose_name="Religious order"
    )

    # Specific location coordinates (optional - more precise than city coordinates)
    latitude = models.DecimalField(
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        help_text="Specific location latitude (falls back to city coordinates if empty)",
    )
    longitude = models.DecimalField(
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        help_text="Specific location longitude (falls back to city coordinates if empty)",
    )

    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Non-public notes on this specific location",
    )

    class Meta:
        # Ensure unique combinations of city + category + description (allowing nulls)
        constraints = [
            models.UniqueConstraint(
                fields=["city", "category_of_space", "description_of_location"],
                name="unique_location_in_city",
            )
        ]

    def __str__(self):
        if self.category_of_space or self.description_of_location:
            parts = [self.name]
            if self.category_of_space:
                parts.append(f"({self.category_of_space})")
            return " ".join(parts)
        return self.name

    @property
    def effective_latitude(self):
        """Return specific location latitude or fall back to city latitude"""
        return self.latitude or (self.city.latitude if self.city else None)

    @property
    def effective_longitude(self):
        """Return specific location longitude or fall back to city longitude"""
        return self.longitude or (self.city.longitude if self.city else None)

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
