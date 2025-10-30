from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from locations.models import City, Location


class CityModelTestCase(TestCase):
    """Test cases for the City model"""

    def test_city_creation(self):
        """Test basic city creation"""
        city = City.objects.create(
            name="Modena", parish="Modena Parish", latitude=44.6471, longitude=10.9250
        )

        self.assertEqual(city.name, "Modena")
        self.assertEqual(city.parish, "Modena Parish")
        self.assertEqual(city.latitude, Decimal("44.6471"))
        self.assertEqual(city.longitude, Decimal("10.9250"))
        self.assertEqual(str(city), "Modena")

    def test_city_unique_name_constraint(self):
        """Test that city names must be unique"""
        City.objects.create(name="Venice")

        with self.assertRaises(IntegrityError):
            City.objects.create(name="Venice")

    def test_city_optional_fields(self):
        """Test city creation with only required fields"""
        city = City.objects.create(name="Florence")

        self.assertEqual(city.name, "Florence")
        self.assertEqual(city.parish, "")
        self.assertIsNone(city.latitude)
        self.assertIsNone(city.longitude)
        self.assertIsNone(city.notes)


class LocationModelTestCase(TestCase):
    """Test cases for the Location model"""

    def setUp(self):
        """Set up test data"""
        self.city = City.objects.create(
            name="Modena", parish="Modena Parish", latitude=44.6471, longitude=10.9250
        )

    def test_location_creation(self):
        """Test basic location creation"""
        location = Location.objects.create(
            name="Church of San Agostino",
            city=self.city,
            category_of_space="sacred",
            description_of_location="Main church in the city center",
        )

        self.assertEqual(location.name, "Church of San Agostino")
        self.assertEqual(location.city, self.city)
        self.assertEqual(location.category_of_space, "sacred")
        self.assertEqual(
            location.description_of_location, "Main church in the city center"
        )

    def test_location_str_with_category(self):
        """Test location string representation with category"""
        location = Location.objects.create(
            name="Modena", city=self.city, category_of_space="public"
        )

        self.assertEqual(str(location), "Modena (public)")

    def test_location_str_without_category(self):
        """Test location string representation without category or description"""
        location = Location.objects.create(name="Modena", city=self.city)

        self.assertEqual(str(location), "Modena")

    def test_effective_coordinates_specific(self):
        """Test effective coordinates when location has specific coordinates"""
        location = Location.objects.create(
            name="Specific Location",
            city=self.city,
            latitude=44.6500,
            longitude=10.9300,
        )

        self.assertEqual(location.effective_latitude, Decimal("44.6500"))
        self.assertEqual(location.effective_longitude, Decimal("10.9300"))

    def test_effective_coordinates_fallback_to_city(self):
        """Test effective coordinates fall back to city coordinates"""
        location = Location.objects.create(name="General Location", city=self.city)

        self.assertEqual(location.effective_latitude, self.city.latitude)
        self.assertEqual(location.effective_longitude, self.city.longitude)

    def test_effective_coordinates_no_coordinates(self):
        """Test effective coordinates when neither location nor city has coordinates"""
        city_no_coords = City.objects.create(name="Unknown City")
        location = Location.objects.create(name="Unknown Location", city=city_no_coords)

        self.assertIsNone(location.effective_latitude)
        self.assertIsNone(location.effective_longitude)

    def test_unique_constraint(self):
        """Test unique constraint on city + category + description"""
        # Create first location
        Location.objects.create(
            name="Church",
            city=self.city,
            category_of_space="sacred",
            description_of_location="Main church",
        )

        # Try to create duplicate - should fail
        with self.assertRaises(IntegrityError):
            Location.objects.create(
                name="Another Church",  # Different name, but same constraint fields
                city=self.city,
                category_of_space="sacred",
                description_of_location="Main church",
            )

    def test_unique_constraint_allows_different_cities(self):
        """Test that same category/description is allowed in different cities"""
        venice = City.objects.create(name="Venice")

        # Create location in Modena
        Location.objects.create(
            name="Church",
            city=self.city,
            category_of_space="sacred",
            description_of_location="Main church",
        )

        # Create similar location in Venice - should succeed
        location2 = Location.objects.create(
            name="Church",
            city=venice,
            category_of_space="sacred",
            description_of_location="Main church",
        )

        self.assertEqual(location2.city, venice)

    def test_unique_constraint_prevents_duplicate_empty_fields(self):
        """Test that unique constraint prevents duplicate locations with same empty category/description"""
        # Create first location with empty category and description
        Location.objects.create(
            name="Location 1",
            city=self.city,
            category_of_space="",
            description_of_location="",
        )

        # Try to create another with same empty fields - should fail
        with self.assertRaises(IntegrityError):
            Location.objects.create(
                name="Location 2",
                city=self.city,
                category_of_space="",
                description_of_location="",
            )


class LocationRelationshipTestCase(TestCase):
    """Test relationships between City and Location models"""

    def test_city_deletion_cascades_to_locations(self):
        """Test that deleting a city deletes its locations"""
        city = City.objects.create(name="Test City")

        Location.objects.create(name="Location 1", city=city)
        Location.objects.create(name="Location 2", city=city)

        self.assertEqual(Location.objects.filter(city=city).count(), 2)

        city.delete()

        self.assertEqual(Location.objects.filter(city_id=city.id).count(), 0)

    def test_city_locations_relationship(self):
        """Test reverse relationship from city to locations"""
        city = City.objects.create(name="Test City")

        location1 = Location.objects.create(name="Location 1", city=city)
        location2 = Location.objects.create(name="Location 2", city=city)

        city_locations = city.location_set.all()

        self.assertEqual(city_locations.count(), 2)
        self.assertIn(location1, city_locations)
        self.assertIn(location2, city_locations)
