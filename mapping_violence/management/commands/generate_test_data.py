"""
Generate dummy Crime/Person/Location data for testing the map at scale.

Usage:
    uv run manage.py generate_test_data --count 500
    uv run manage.py generate_test_data --clear

Generated records are tagged so --clear only removes test data, not real records.
"""

import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from locations.models import City, Location
from mapping_violence.models import Crime, Person, Weapon

# Tag prefix used to identify generated data
TAG = "[TEST] "

# ── Reference data ──────────────────────────────────────────────────────────

VENETIAN_CITIES = [
    ("Venice", "45.4408", "12.3155"),
    ("Padova", "45.4064", "11.8768"),
    ("Verona", "45.4384", "10.9916"),
    ("Vicenza", "45.5455", "11.5354"),
    ("Treviso", "45.6669", "12.2430"),
    ("Brescia", "45.5416", "10.2118"),
    ("Bergamo", "45.6983", "9.6773"),
    ("Udine", "46.0711", "13.2346"),
    ("Belluno", "46.1459", "12.2181"),
    ("Rovigo", "45.0701", "11.7901"),
    ("Chioggia", "45.2194", "12.2789"),
    ("Murano", "45.4585", "12.3525"),
    ("Mestre", "45.4908", "12.2381"),
    ("Bassano del Grappa", "45.7660", "11.7351"),
]

LOCATION_TEMPLATES = [
    ("Campo {name}", "public", "urban"),
    ("Calle {name}", "public", "urban"),
    ("Ponte {name}", "public", "urban"),
    ("Chiesa di {name}", "sacred", "urban"),
    ("Piazza {name}", "public", "urban"),
    ("Osteria {name}", "domestic", "urban"),
    ("Palazzo {name}", "domestic", "urban"),
    ("Fondamenta {name}", "public", "urban"),
    ("Strada {name}", "public", "rural"),
    ("Borgo {name}", "public", "rural"),
    ("Cascina {name}", "domestic", "rural"),
    ("Taverna {name}", "domestic", "urban"),
]

LOCATION_NAMES = [
    "San Marco",
    "San Polo",
    "Santa Croce",
    "Rialto",
    "San Giovanni",
    "Santa Maria",
    "San Pietro",
    "Sant'Angelo",
    "San Luca",
    "San Giacomo",
    "dei Frari",
    "della Pietà",
    "dei Servi",
    "del Gallo",
    "della Madonna",
    "San Nicolò",
    "San Barnaba",
    "San Geremia",
    "San Trovaso",
    "San Vio",
    "dei Miracoli",
    "del Redentore",
    "della Salute",
    "San Cassiano",
    "San Moisè",
    "San Zulian",
    "San Fantin",
    "San Beneto",
    "San Maurizio",
]

FIRST_NAMES_M = [
    "Giovanni",
    "Marco",
    "Antonio",
    "Pietro",
    "Francesco",
    "Giacomo",
    "Andrea",
    "Lorenzo",
    "Paolo",
    "Alessandro",
    "Niccolò",
    "Domenico",
    "Alvise",
    "Bartolomeo",
    "Bernardo",
    "Carlo",
    "Cristoforo",
    "Daniele",
    "Federico",
    "Girolamo",
    "Luca",
    "Matteo",
    "Sebastiano",
    "Vincenzo",
]

FIRST_NAMES_F = [
    "Maria",
    "Caterina",
    "Lucia",
    "Elena",
    "Francesca",
    "Isabella",
    "Chiara",
    "Giovanna",
    "Teresa",
    "Angela",
    "Margherita",
    "Elisabetta",
    "Anna",
    "Beatrice",
    "Bianca",
    "Cecilia",
    "Diana",
    "Giulia",
]

LAST_NAMES = [
    "Morosini",
    "Contarini",
    "Grimani",
    "Barbarigo",
    "Venier",
    "Foscarini",
    "Priuli",
    "Loredan",
    "Dolfin",
    "Pisani",
    "Dandolo",
    "Giustinian",
    "Marcello",
    "Bragadin",
    "Querini",
    "Soranzo",
    "Tiepolo",
    "Badoer",
    "Malipiero",
    "Cornaro",
    "Zeno",
    "Gradenigo",
    "Mocenigo",
    "Falier",
    "Bembo",
    "Trevisan",
    "Valier",
    "Cappello",
    "Emo",
    "Donà",
]

HONORIFICS_M = ["", "", "", "Ser", "Messer", "Magnifico", "Signor"]
HONORIFICS_F = ["", "", "", "Madonna", "Signora"]

CRIME_TYPES = [
    "homicide",
    "assault",
    "robbery",
    "theft",
    "arson",
    "fraud",
    "insult",
    "vendetta",
    "brawl",
    "trespassing",
    "abduction",
    "poisoning",
    "counterfeiting",
    "smuggling",
    "duel",
]

OFFENSE_CATEGORIES = [
    "homicide",
    "premeditated_homicide",
    "insult",
    "sexual_offenses",
    "abduction",
    "assault",
    "other",
]

WEAPON_NAMES = [
    ("Sword", "blade"),
    ("Dagger", "blade"),
    ("Stiletto", "blade"),
    ("Knife", "blade"),
    ("Halberd", "blade"),
    ("Pistol", "firearm"),
    ("Arquebus", "firearm"),
    ("Musket", "firearm"),
    ("Club", "blunt_instrument"),
    ("Staff", "blunt_instrument"),
    ("Mace", "blunt_instrument"),
    ("Stone", "blunt_instrument"),
    ("Fists", "hands"),
    ("Hands", "hands"),
    ("Rope", "other"),
    ("Poison", "other"),
]

COURTS = [
    "Council of Ten",
    "Avogaria di Comun",
    "Signori di Notte",
    "Quarantia Criminal",
    "Cinque alla Pace",
    "Podestà",
    "Capitano di Giustizia",
    "Magistrato alle Acque",
]

SESTIERI = [
    "San Marco",
    "San Polo",
    "Santa Croce",
    "Dorsoduro",
    "Cannaregio",
    "Castello",
]

TIMES_OF_DAY = [
    "morning",
    "afternoon",
    "evening",
    "night",
    "dawn",
    "dusk",
    "midday",
]

OCCUPATIONS = [
    "merchant",
    "sailor",
    "soldier",
    "priest",
    "baker",
    "fisherman",
    "blacksmith",
    "tailor",
    "gondolier",
    "innkeeper",
    "carpenter",
    "notary",
    "physician",
    "weaver",
    "mason",
    "butcher",
    "servant",
    "glassmaker",
    "nobleman",
    "farmer",
    "boatman",
    "barber",
]


class Command(BaseCommand):
    help = "Generate dummy crime data for testing the map, or clear it with --clear"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=200,
            help="Number of crimes to generate (default: 200)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all previously generated test data",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            return self.clear_data()
        return self.generate_data(options["count"])

    def clear_data(self):
        # Delete crimes first (they reference persons/locations/weapons)
        crimes = Crime.objects.filter(source__startswith=TAG)
        crime_count = crimes.count()

        # Collect M2M person IDs before deleting crimes
        victim_ids = set()
        perp_ids = set()
        for c in crimes:
            victim_ids.update(c.victim.values_list("id", flat=True))
            perp_ids.update(c.perpetrator.values_list("id", flat=True))
        test_person_ids = victim_ids | perp_ids

        crimes.delete()

        # Delete test persons (only those tagged)
        persons = Person.objects.filter(id__in=test_person_ids, notes__startswith=TAG)
        person_count = persons.count()
        persons.delete()

        # Delete test weapons
        weapons = Weapon.objects.filter(definition__startswith=TAG)
        weapon_count = weapons.count()
        weapons.delete()

        # Delete test locations and cities
        locations = Location.objects.filter(notes__startswith=TAG)
        loc_count = locations.count()
        locations.delete()

        cities = City.objects.filter(notes__startswith=TAG)
        city_count = cities.count()
        cities.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleared test data: {crime_count} crimes, {person_count} persons, "
                f"{weapon_count} weapons, {loc_count} locations, {city_count} cities"
            )
        )

    def generate_data(self, count):
        self.stdout.write(f"Generating {count} test crimes...")

        # ── Cities ───────────────────────────────────────────────────────
        cities = []
        for name, lat, lng in VENETIAN_CITIES:
            city, _ = City.objects.get_or_create(
                name=name,
                defaults={
                    "latitude": Decimal(lat),
                    "longitude": Decimal(lng),
                    "notes": TAG + "auto-generated city",
                },
            )
            cities.append(city)
        self.stdout.write(f"  {len(cities)} cities ready")

        # ── Locations ────────────────────────────────────────────────────
        locations = []
        for city in cities:
            num_locations = random.randint(5, 12)
            for i in range(num_locations):
                tmpl = random.choice(LOCATION_TEMPLATES)
                loc_name = tmpl[0].format(name=random.choice(LOCATION_NAMES))
                category = tmpl[1]
                urban_rural = tmpl[2]

                # Use a unique description to avoid unique constraint collisions
                description = f"Near the {random.choice(LOCATION_NAMES)}, #{i + 1}"

                # 80% get specific coordinates (jittered from city)
                lat = lng = None
                if random.random() < 0.8 and city.latitude and city.longitude:
                    lat = city.latitude + Decimal(
                        str(round(random.uniform(-0.03, 0.03), 6))
                    )
                    lng = city.longitude + Decimal(
                        str(round(random.uniform(-0.03, 0.03), 6))
                    )

                try:
                    location = Location.objects.create(
                        name=loc_name,
                        city=city,
                        category_of_space=category,
                        description_of_location=description,
                        urban_rural=urban_rural,
                        latitude=lat,
                        longitude=lng,
                        sestiere=random.choice(SESTIERI)
                        if city.name == "Venice"
                        else "",
                        notes=TAG + "auto-generated location",
                    )
                    locations.append(location)
                except Exception:
                    # Unique constraint violation — skip duplicate
                    pass

        self.stdout.write(f"  {len(locations)} locations created")

        # ── Weapons ──────────────────────────────────────────────────────
        weapons = []
        for name, category in WEAPON_NAMES:
            weapon, _ = Weapon.objects.get_or_create(
                name=name,
                weapon_category=category,
                defaults={
                    "definition": TAG + f"A {name.lower()} used in combat",
                },
            )
            weapons.append(weapon)
        self.stdout.write(f"  {len(weapons)} weapons ready")

        # ── Persons ──────────────────────────────────────────────────────
        persons = []
        num_persons = max(count, 100)  # ensure enough people to reuse
        for _ in range(num_persons):
            gender = random.choice(["M", "F", "U"])
            if gender == "F":
                first = random.choice(FIRST_NAMES_F)
                honorific = random.choice(HONORIFICS_F)
            else:
                first = random.choice(FIRST_NAMES_M)
                honorific = random.choice(HONORIFICS_M)
            last = random.choice(LAST_NAMES)

            person = Person.objects.create(
                first_name=first,
                last_name=last,
                given_name=f"{first} {last}",
                honorific=honorific,
                gender=gender,
                occupation=random.choice(OCCUPATIONS) if random.random() < 0.6 else "",
                citizenship="Venetian"
                if random.random() < 0.7
                else random.choice(
                    ["Paduan", "Brescian", "Friulian", "Greek", "Ottoman", "German"]
                ),
                notes=TAG + "auto-generated person",
            )
            persons.append(person)
        self.stdout.write(f"  {len(persons)} persons created")

        # ── Crimes ───────────────────────────────────────────────────────
        created = 0
        for i in range(count):
            year = random.randint(1500, 1700)
            month = random.randint(1, 12)
            day = random.randint(1, 28)  # safe for all months
            crime_date = date(year, month, day)

            crime_type = random.choice(CRIME_TYPES)
            offense = random.choice(OFFENSE_CATEGORIES)
            is_fatal = offense in ("homicide", "premeditated_homicide") or (
                random.random() < 0.15
            )

            location = random.choice(locations)

            crime = Crime.objects.create(
                number=f"TEST-{i + 1:05d}",
                crime=crime_type,
                offense_category=offense,
                date=crime_date,
                year=str(year),
                month=str(month),
                day=str(day),
                time_of_day=random.choice(TIMES_OF_DAY)
                if random.random() < 0.5
                else "",
                weapon=random.choice(weapons) if random.random() < 0.7 else None,
                address=location,
                fatality=is_fatal,
                violence_caused_death=is_fatal,
                court=random.choice(COURTS) if random.random() < 0.5 else "",
                sestiere=location.sestiere,
                source=TAG + "auto-generated crime",
                convicted=random.random() < 0.3,
                pardoned=random.random() < 0.1,
            )

            # Add 1–3 victims
            num_victims = random.randint(1, 3)
            crime.victim.set(random.sample(persons, min(num_victims, len(persons))))

            # Add 1–2 perpetrators
            num_perps = random.randint(1, 2)
            crime.perpetrator.set(random.sample(persons, min(num_perps, len(persons))))

            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Created {created} test crimes across "
                f"{len(locations)} locations in {len(cities)} cities.\n"
                f"Run 'uv run manage.py generate_test_data --clear' to remove."
            )
        )
