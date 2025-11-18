from django.test import TestCase

from locations.models import City, Location
from mapping_violence.resources import LocationWidget


class LocationWidgetTestCase(TestCase):
    """Test cases for the LocationWidget import functionality"""

    def setUp(self):
        """Set up test data"""
        self.widget = LocationWidget(Location, "name")

    def test_widget_creates_city_and_location(self):
        """Test that widget creates both city and location from CSV data"""
        row = {
            "City": "Modena",
            "Parish": "Modena Parish",
            "Latitude": "44.6471",
            "Longitude": "10.9250",
            "Category of Space": "sacred",
            "Description_of_Location": "Main church",
        }

        location = self.widget.clean("Modena", row=row)

        # Check that city was created
        self.assertEqual(City.objects.count(), 1)
        city = City.objects.get(name="Modena")
        self.assertEqual(city.parish, "Modena Parish")
        self.assertEqual(float(city.latitude), 44.6471)
        self.assertEqual(float(city.longitude), 10.9250)

        # Check that location was created
        self.assertEqual(Location.objects.count(), 1)
        self.assertEqual(location.city, city)
        self.assertEqual(location.category_of_space, "sacred")
        self.assertEqual(location.description_of_location, "Main church")
        self.assertEqual(location.name, "Modena - Main church")

    def test_widget_reuses_existing_city(self):
        """Test that widget reuses existing city instead of creating duplicate"""
        # Create existing city
        existing_city = City.objects.create(name="Venice")

        row = {
            "City": "Venice",
            "Category of Space": "public",
            "Description_of_Location": "Main square",
        }

        location = self.widget.clean("Venice", row=row)

        # Should still only have one city
        self.assertEqual(City.objects.count(), 1)
        self.assertEqual(location.city, existing_city)

    def test_widget_creates_unique_locations_same_city(self):
        """Test that widget creates separate locations for same city with different categories"""
        row1 = {
            "City": "Modena",
            "Category of Space": "sacred",
            "Description_of_Location": "Church",
        }

        row2 = {
            "City": "Modena",
            "Category of Space": "public",
            "Description_of_Location": "Plaza",
        }

        location1 = self.widget.clean("Modena", row=row1)
        location2 = self.widget.clean("Modena", row=row2)

        # Should have one city but two locations
        self.assertEqual(City.objects.count(), 1)
        self.assertEqual(Location.objects.count(), 2)

        self.assertEqual(location1.city, location2.city)
        self.assertEqual(location1.category_of_space, "sacred")
        self.assertEqual(location2.category_of_space, "public")
        self.assertNotEqual(location1.id, location2.id)

    def test_widget_reuses_existing_location_same_criteria(self):
        """Test that widget reuses existing location with same city/category/description"""
        # First import
        row = {
            "City": "Venice",
            "Category of Space": "sacred",
            "Description_of_Location": "St. Mark's Basilica",
        }

        location1 = self.widget.clean("Venice", row=row)

        # Second import with same criteria
        location2 = self.widget.clean("Venice", row=row)

        # Should reuse the same location
        self.assertEqual(location1.id, location2.id)
        self.assertEqual(Location.objects.count(), 1)

    def test_widget_creates_simple_location_name_without_details(self):
        """Test location name creation when no category or description provided"""
        row = {"City": "Simple"}

        location = self.widget.clean("Simple", row=row)

        self.assertEqual(location.name, "Simple")

    def test_widget_creates_location_name_with_category_only(self):
        """Test location name creation with category but no description"""
        row = {"City": "TestCity", "Category of Space": "domestic"}

        location = self.widget.clean("TestCity", row=row)

        self.assertEqual(location.name, "TestCity - (domestic)")

    def test_widget_handles_none_value(self):
        """Test that widget returns None when given None value"""
        result = self.widget.clean(None, row={})
        self.assertIsNone(result)

    def test_widget_handles_empty_string_value(self):
        """Test that widget returns None when given empty string"""
        result = self.widget.clean("", row={})
        self.assertIsNone(result)
