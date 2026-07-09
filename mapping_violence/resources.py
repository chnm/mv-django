import re
import time
from collections import OrderedDict
from datetime import datetime

from import_export import fields, resources, widgets
from import_export.widgets import BooleanWidget
from tablib import Dataset

from locations.models import City, Location

from .models import (
    Crime,
    Event,
    ExternalPersonIdentifier,
    Person,
    SourceDataset,
    Weapon,
)


def _is_blankish(value):
    return str(value or "").strip().lower() in {"", "nan", "none", "null"}


def _clean_value(value):
    return "" if _is_blankish(value) else str(value).strip()


class PersonWidget(widgets.ForeignKeyWidget):
    """Custom widget for Person fields that handles name parsing"""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        # Handle comma-separated names (Last, First format)
        if "," in value:
            parts = [part.strip() for part in value.split(",")]
            last_name = parts[0] if parts else ""
            first_name = parts[1] if len(parts) > 1 else ""
        else:
            # Handle space-separated names
            parts = value.strip().split()
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = " ".join(parts[1:])
            else:
                first_name = ""
                last_name = parts[0] if parts else value

        person = (
            Person.objects.filter(first_name=first_name, last_name=last_name)
            .order_by("pk")
            .first()
        )
        if person:
            return person
        return Person.objects.create(first_name=first_name, last_name=last_name)


class WeaponWidget(widgets.ManyToManyWidget):
    """Custom widget for Weapon M2M field — resolves semicolon-separated names."""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return []

        weapons = []
        for name in str(value).split(";"):
            name = name.strip()
            if name:
                weapon, created = Weapon.objects.get_or_create(
                    name=name, defaults={"name": name}
                )
                weapons.append(weapon)
        return weapons


class EventWidget(widgets.ForeignKeyWidget):
    """Custom widget for Event fields"""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        event, created = Event.objects.get_or_create(
            name=value, defaults={"name": value}
        )
        return event


class LocationWidget(widgets.ForeignKeyWidget):
    """Custom widget for Location fields that handles City/Location separation"""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        # Extract location data from the row
        city_name = row.get("City", "") if row else ""
        parish = row.get("Parish", "") if row else ""
        latitude = row.get("Latitude", "") if row else ""
        longitude = row.get("Longitude", "") if row else ""
        category_of_space = row.get("Category of Space", "") if row else ""
        description_of_location = row.get("Description_of_Location", "") if row else ""

        # Use city name from CSV, fall back to main value
        city_name = city_name or value
        if not city_name:
            return None

        # Parse coordinates
        city_lat = None
        city_lon = None
        if latitude:
            try:
                city_lat = float(latitude)
            except (ValueError, TypeError):
                pass

        if longitude:
            try:
                city_lon = float(longitude)
            except (ValueError, TypeError):
                pass

        # Step 1: Create or get the City
        city_defaults = {
            "name": city_name,
            "parish": parish,
        }
        if city_lat is not None:
            city_defaults["latitude"] = city_lat
        if city_lon is not None:
            city_defaults["longitude"] = city_lon

        city, city_created = City.objects.get_or_create(
            name=city_name, defaults=city_defaults
        )

        # Update city with new data if available
        if not city_created:
            updated = False
            if parish and not city.parish:
                city.parish = parish
                updated = True
            if city_lat is not None and not city.latitude:
                city.latitude = city_lat
                updated = True
            if city_lon is not None and not city.longitude:
                city.longitude = city_lon
                updated = True
            if updated:
                city.save()

        # Step 2: Create or get the specific Location within the City
        # Create a unique location name based on city + category + description
        location_name = city_name
        if category_of_space or description_of_location:
            # Add distinguishing details to the name
            parts = [city_name]
            if description_of_location:
                parts.append(description_of_location)
            elif category_of_space:
                parts.append(f"({category_of_space})")
            location_name = " - ".join(parts)

        # Auto-detect urban/rural from place name text
        combined_text = f"{city_name} {location_name}".lower()
        if "contado" in combined_text:
            urban_rural = "rural"
        elif "citta" in combined_text or "città" in combined_text:
            urban_rural = "urban"
        else:
            urban_rural = "unknown"

        location_defaults = {
            "name": location_name,
            "city": city,
            "category_of_space": category_of_space,
            "description_of_location": description_of_location,
            "urban_rural": urban_rural,
        }

        # Try to find existing location or create new one
        # Use city + category + description as unique identifier
        try:
            location = Location.objects.get(
                city=city,
                category_of_space=category_of_space,
                description_of_location=description_of_location,
            )
        except Location.DoesNotExist:
            location = Location.objects.create(**location_defaults)
        except Location.MultipleObjectsReturned:
            # If multiple exist, get the first one
            location = Location.objects.filter(
                city=city,
                category_of_space=category_of_space,
                description_of_location=description_of_location,
            ).first()

        return location


MONTH_NAMES = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


class CustomDateWidget(widgets.Widget):
    """Custom date widget that handles various date formats"""

    def clean(self, value, row=None, **kwargs):
        if not value or str(value).strip() == "":
            # If no date provided, try to parse from year/month if available
            year = row.get("Year", "") if row else ""
            month = row.get("Month", "") if row else ""

            if year and month:
                try:
                    month_num = MONTH_NAMES.get(month, None) or int(month)
                    return datetime(int(year), month_num, 1).date()
                except (ValueError, TypeError):
                    pass

            return None

        value_str = str(value).strip()

        # 4-digit year formats first
        date_formats = [
            "%m/%d/%Y",  # 03/15/1615
            "%m/%Y",  # 05/1612
            "%Y-%m-%d",  # 1615-03-15
            "%Y/%m/%d",  # 1615/03/15
        ]
        for fmt in date_formats:
            try:
                return datetime.strptime(value_str, fmt).date()
            except ValueError:
                continue

        # 2-digit year: MM/DD/YY — infer century from the row's Year field
        if "/" in value_str:
            parts = value_str.split("/")
            try:
                if len(parts) == 3 and len(parts[2]) == 2:
                    month, day, year_2 = int(parts[0]), int(parts[1]), int(parts[2])
                    row_year = (row.get("Year", "") or "") if row else ""
                    if str(row_year).strip().isdigit():
                        century = (int(str(row_year).strip()) // 100) * 100
                        full_year = century + year_2
                    else:
                        full_year = 1600 + year_2
                    return datetime(full_year, month, day).date()
                elif len(parts) == 2:  # MM/YYYY
                    return datetime(int(parts[1]), int(parts[0]), 1).date()
            except (ValueError, TypeError):
                pass

        return None


class HistoricalDateWidget(widgets.Widget):
    """Custom widget for historical date parsing"""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        try:
            # Try to parse MM/YYYY format
            if "/" in value:
                parts = value.split("/")
                if len(parts) == 2:
                    month, year = parts
                    # Convert month name to number if needed
                    month_names = {
                        "January": 1,
                        "February": 2,
                        "March": 3,
                        "April": 4,
                        "May": 5,
                        "June": 6,
                        "July": 7,
                        "August": 8,
                        "September": 9,
                        "October": 10,
                        "November": 11,
                        "December": 12,
                    }
                    if month in month_names:
                        month = month_names[month]
                    else:
                        month = int(month)

                    year = int(year)
                    return datetime(year, month, 1).date()
        except (ValueError, TypeError):
            pass

        return value


class CrimeResource(resources.ModelResource):
    """Import/Export resource for Crime model"""

    source_dataset_name = ""
    import_profile = "canonical"

    def __init__(self, user=None, source_dataset=None, import_batch=None, **kwargs):
        self.importing_user = user
        self.source_dataset = self._coerce_source_dataset(source_dataset)
        self.import_batch = import_batch
        super().__init__(**kwargs)

    def _coerce_source_dataset(self, source_dataset):
        if source_dataset:
            if isinstance(source_dataset, SourceDataset):
                return source_dataset
            source_dataset, _ = SourceDataset.objects.get_or_create(
                name=str(source_dataset)
            )
            return source_dataset
        if self.source_dataset_name:
            source_dataset, _ = SourceDataset.objects.get_or_create(
                name=self.source_dataset_name
            )
            return source_dataset
        return None

    def before_save_instance(self, instance, row, **kwargs):
        """Set input_by to the importing user for new records.
        New imports default to 'triage'; re-imported 'done' records get
        kicked back to 'needs_review'.
        """
        if self.importing_user and not instance.input_by_id:
            instance.input_by = self.importing_user
        if self.import_batch and not instance.import_batch_id:
            instance.import_batch = self.import_batch
        if not instance.pk:
            instance.status = "triage"
        elif instance.status == "done":
            instance.status = "needs_review"
        return super().before_save_instance(instance, row, **kwargs)

    # Map CSV columns to model fields - column mapping handled in before_import_row
    number = fields.Field(column_name="Number", attribute="number")

    crime = fields.Field(column_name="Crime", attribute="crime")

    description_of_case = fields.Field(
        column_name="Description of Case", attribute="description_of_case"
    )

    court = fields.Field(column_name="Court", attribute="court")

    court_classification = fields.Field(
        column_name="Court_Classification", attribute="court_classification"
    )

    trial_phase = fields.Field(column_name="Trial_Phase", attribute="trial_phase")

    arbitration = fields.Field(
        column_name="Arbitration (Y/N)", attribute="arbitration", widget=BooleanWidget()
    )

    sentence = fields.Field(column_name="Sentence", attribute="sentence")

    convicted = fields.Field(
        column_name="Convicted",
        attribute="convicted",
        widget=BooleanWidget(),
    )

    sentence_enforced = fields.Field(
        column_name="Sentence_Enforced (Y/N)",
        attribute="sentence_enforced",
        widget=BooleanWidget(),
    )

    date = fields.Field(
        column_name="Date (Modern Format)", attribute="date", widget=CustomDateWidget()
    )

    year = fields.Field(column_name="Year", attribute="year")

    month = fields.Field(column_name="Month", attribute="month")

    day = fields.Field(column_name="Day", attribute="day")

    day_of_week = fields.Field(column_name="Day_of_week", attribute="day_of_week")

    time = fields.Field(column_name="Time", attribute="time")

    connected_event = fields.Field(
        column_name="Connected_Event",
        attribute="connected_event",
        widget=EventWidget(Event, "name"),
    )

    # These fields are used for creating Person records but don't map to Crime model fields
    victim_name = fields.Field(
        column_name="Victim_Name", attribute="victim_name", readonly=True
    )

    victim_last_name = fields.Field(
        column_name="Victim_Last_Name", attribute="victim_last_name", readonly=True
    )

    victim_gender = fields.Field(
        column_name="Victim_Gender", attribute="victim_gender", readonly=True
    )

    victim_occupation = fields.Field(
        column_name="Victim_Occupation", attribute="victim_occupation", readonly=True
    )

    assailant_name = fields.Field(
        column_name="Assailant_Name", attribute="assailant_name", readonly=True
    )

    assailant_first_name = fields.Field(
        column_name="Assailant_First", attribute="assailant_first_name", readonly=True
    )

    assailant_gender = fields.Field(
        column_name="Assailant_Gender", attribute="assailant_gender", readonly=True
    )

    assailant_external_ids = fields.Field(
        column_name="Assailant_External_IDs",
        attribute="assailant_external_ids",
        readonly=True,
    )

    victim_description = fields.Field(
        column_name="Victim_Description", attribute="victim_description"
    )

    assailant_description = fields.Field(
        column_name="Assailant_Description", attribute="assailant_description"
    )

    motive = fields.Field(column_name="Motive", attribute="motive")

    relationship = fields.Field(column_name="Relationship", attribute="relationship")

    weapon = fields.Field(
        column_name="Type_of_Weapon",
        attribute="weapon",
        widget=WeaponWidget(Weapon, separator=";"),
    )

    description_of_location = fields.Field(
        column_name="Description of Location", attribute="description_of_location"
    )

    fatality = fields.Field(
        column_name="Fatality (Y/N)", attribute="fatality", widget=BooleanWidget()
    )

    archival_location = fields.Field(
        column_name="Archival Location", attribute="archival_location"
    )

    reference = fields.Field(column_name="Reference", attribute="reference")

    address = fields.Field(
        column_name="City", attribute="address", widget=LocationWidget(Location, "name")
    )

    input_by_name = fields.Field(
        column_name="Input by", attribute="input_by_name", readonly=True
    )

    def dehydrate_victim_name(self, crime):
        """Export victim names as semicolon-separated list."""
        return "; ".join(str(v) for v in crime.victim.all())

    def dehydrate_victim_gender(self, crime):
        genders = [v.gender for v in crime.victim.all() if v.gender]
        return "; ".join(genders)

    def dehydrate_victim_occupation(self, crime):
        occupations = [v.occupation for v in crime.victim.all() if v.occupation]
        return "; ".join(occupations)

    def dehydrate_assailant_name(self, crime):
        """Export perpetrator names as semicolon-separated list."""
        return "; ".join(str(p) for p in crime.perpetrator.all())

    def dehydrate_assailant_gender(self, crime):
        genders = [p.gender for p in crime.perpetrator.all() if p.gender]
        return "; ".join(genders)

    def dehydrate_weapon(self, crime):
        """Export weapon names in the same format accepted by WeaponWidget."""
        return "; ".join(str(w) for w in crime.weapon.all())

    def dehydrate_address(self, crime):
        """Export the city name for the import LocationWidget."""
        return crime.address.city.name if crime.address and crime.address.city else ""

    class Meta:
        model = Crime
        # Number is the stable archival identifier used for round-trip imports.
        fields = (
            "number",
            "crime",
            "description_of_case",
            "court",
            "court_classification",
            "trial_phase",
            "arbitration",
            "sentence",
            "convicted",
            "sentence_enforced",
            "date",
            "year",
            "month",
            "day",
            "day_of_week",
            "time",
            "connected_event",
            "victim_name",
            "victim_last_name",
            "victim_gender",
            "victim_occupation",
            "assailant_name",
            "assailant_first_name",
            "assailant_gender",
            "assailant_external_ids",
            "victim_description",
            "assailant_description",
            "motive",
            "relationship",
            "weapon",
            "address",
            "description_of_location",
            "fatality",
            "archival_location",
            "reference",
            "input_by_name",
        )
        skip_unchanged = False
        report_skipped = False
        use_bulk = False
        import_id_fields = ("number",)

    def skip_row(self, instance, original, row, import_validation_errors=None):
        """Silently skip empty rows instead of raising an error."""
        if self.is_empty_row(row):
            return True
        return super().skip_row(instance, original, row, import_validation_errors)

    def before_import_row(self, row, **kwargs):
        """Normalize column names and values before importing."""

        # Drop stray columns with blank/whitespace-only header names
        for key in [k for k in list(row.keys()) if not (k or "").strip()]:
            row.pop(key, None)

        # Normalize column names — handles both the standard format and
        # rose_data.csv's underscore/spacing variants
        column_mappings = {
            "Case Number": "Number",
            "Case_number": "Number",
            "Description_of_Crime": "Description of Case",
            "Description_of_Case": "Description of Case",
            "Date_of_Crime (Modern)": "Date (Modern Format)",
            "Date_of_Crime": "Date (Modern Format)",
            "Weapon": "Type_of_Weapon",
            "Archival_Location": "Archival Location",
            "Sentence_Enforced": "Sentence_Enforced (Y/N)",
        }
        for src, dst in column_mappings.items():
            if src in row and dst not in row:
                row[dst] = row[src]

        for key, value in list(row.items()):
            if isinstance(value, str) and value.strip().lower() == "nan":
                row[key] = ""

        # LocationWidget reads 'City' from the row; fall back to 'Location'
        # when only a single combined location column is present
        if not (row.get("City") or "").strip() and (row.get("Location") or "").strip():
            row["City"] = row["Location"]

        # Parse Y/N prefix from Sentence field.
        # Formats seen in the data: "Y - <text>", "Y- <text>", "Y <text>",
        # "Y", "Y?", "N - <reason>", "N", lowercase variants, freeform text.
        # Sets Convicted from the prefix and reduces Sentence to the annotation.
        sentence_raw = (row.get("Sentence") or "").strip()
        if sentence_raw:
            m = re.match(r"^([YyNn])\s*[-–]?\s*(.*)", sentence_raw, re.DOTALL)
            if m:
                prefix, remainder = m.group(1).upper(), m.group(2).strip()
                yn = "Y" if prefix == "Y" else "N"
                # Only set these if not already explicitly provided in the row
                if not row.get("Convicted"):
                    row["Convicted"] = prefix == "Y"
                if not (row.get("Sentence_Enforced (Y/N)") or "").strip():
                    row["Sentence_Enforced (Y/N)"] = yn
                row["Sentence"] = remainder

        # Handle Y/N values for boolean fields
        bool_fields = ["Arbitration (Y/N)", "Sentence_Enforced (Y/N)", "Fatality (Y/N)"]
        for field in bool_fields:
            if field in row:
                value = str(row[field]).strip().upper()
                row[field] = value == "Y" or value == "YES"

        # Populate missing case numbers for sparse rows. Existing numbers are
        # left intact so import-export can update matching records.
        number = row.get("Number", "")
        if not number or str(number).strip() == "":
            timestamp = int(time.time() * 1000000)  # microseconds since epoch
            row["Number"] = f"AUTO_{timestamp}"
        else:
            row["Number"] = str(number).strip()

        return super().before_import_row(row, **kwargs)

    def is_empty_row(self, row):
        """Check if a row is essentially empty.

        A row is considered empty only when it carries no identifier at all —
        no case number and no archival location.  Rows that lack Crime /
        Description / Year but still have a case number or archival reference
        are real (if sparse) records and should be imported.
        """
        id_fields = [
            "Number",
            "Case_number",
            "Archival Location",
            "Archival_Location",
        ]
        for field in id_fields:
            if (row.get(field) or "").strip():
                return False
        return True

    def after_save_instance(self, instance, row, **kwargs):
        """Process instance after saving - this is called after the instance is saved to DB"""
        # Handle many-to-many relationships for victims and perpetrators
        if instance and instance.pk:
            victim_columns = [
                "Victim_First_Name",
                "Victim_Last_Name",
                "Victim_Name",
            ]
            if self._row_has_any_column(row, victim_columns):
                instance.victim.set(
                    self._people_from_row(
                        row,
                        first_columns=["Victim_First_Name"],
                        last_columns=["Victim_Last_Name"],
                        combined_columns=["Victim_Name"],
                        gender_column="Victim_Gender",
                        occupation_column="Victim_Occupation",
                        external_id_columns=["Victim_External_IDs"],
                    )
                )

            assailant_columns = [
                "Assailant_First",
                "Assailant_Last_Name",
                "Assailant_Last",
                "Assailant _ Last_Name",
                "Assailant_Name",
            ]
            if self._row_has_any_column(row, assailant_columns):
                instance.perpetrator.set(
                    self._people_from_row(
                        row,
                        first_columns=["Assailant_First"],
                        last_columns=[
                            "Assailant_Last_Name",
                            "Assailant_Last",
                            "Assailant _ Last_Name",
                        ],
                        combined_columns=["Assailant_Name"],
                        gender_column="Assailant_Gender",
                        external_id_columns=["Assailant_External_IDs"],
                    )
                )

    def _row_has_any_column(self, row, column_names):
        """Return True when a CSV row includes any column in a logical group."""
        return any(col_name in row for col_name in column_names)

    def _people_from_row(
        self,
        row,
        *,
        first_columns,
        last_columns,
        combined_columns,
        gender_column,
        occupation_column=None,
        external_id_columns=None,
    ):
        """Build Person instances from split or semicolon-separated name columns."""
        first = self._get_flexible_value(row, first_columns)
        last = self._get_flexible_value(row, last_columns)
        gender = self._clean_gender(row.get(gender_column, ""))
        occupation = row.get(occupation_column, "") if occupation_column else ""
        external_ids = self._split_multi_value(
            self._get_flexible_value(row, external_id_columns or [])
        )
        people = []

        if first or last:
            names = [(first or "", last or "")]
        else:
            names = []
            combined = self._get_flexible_value(row, combined_columns)
            if combined:
                for name in str(combined).split(";"):
                    name = name.strip()
                    if name:
                        names.append(self._parse_name(name))

        for index, (first_name, last_name) in enumerate(names):
            if not (first_name or last_name):
                continue
            external_id = external_ids[index] if index < len(external_ids) else ""
            person = self._resolve_person(
                first_name=first_name,
                last_name=last_name,
                raw_name=", ".join(part for part in [last_name, first_name] if part),
                external_id=external_id,
                gender=gender,
                occupation=occupation,
            )
            update_fields = []
            if gender and not person.gender:
                person.gender = gender
                update_fields.append("gender")
            if occupation and not person.occupation:
                person.occupation = occupation
                update_fields.append("occupation")
            if update_fields:
                person.save(update_fields=update_fields)
            people.append(person)

        return people

    def _resolve_person(
        self,
        *,
        first_name,
        last_name,
        raw_name,
        external_id="",
        gender="",
        occupation="",
    ):
        external_id = _clean_value(external_id)
        if self.source_dataset and external_id:
            identifier = (
                ExternalPersonIdentifier.objects.filter(
                    source_dataset=self.source_dataset,
                    external_id=external_id,
                )
                .select_related("person")
                .first()
            )
            if identifier and identifier.person:
                if raw_name and identifier.raw_name != raw_name:
                    identifier.raw_name = raw_name
                    identifier.save(update_fields=["raw_name"])
                return identifier.person

        matches = Person.objects.filter(first_name=first_name, last_name=last_name)
        status = ExternalPersonIdentifier.CREATED
        notes = ""
        if matches.exists():
            person = matches.order_by("pk").first()
            status = ExternalPersonIdentifier.MATCHED
            if matches.count() > 1:
                status = ExternalPersonIdentifier.AMBIGUOUS_NAME_REUSED
                notes = (
                    "Multiple local people had this exact first/last name during "
                    "import; the earliest matching Person was reused."
                )
        else:
            person = Person.objects.create(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                occupation=occupation,
            )

        if self.source_dataset and external_id:
            ExternalPersonIdentifier.objects.update_or_create(
                source_dataset=self.source_dataset,
                external_id=external_id,
                defaults={
                    "person": person,
                    "raw_name": raw_name,
                    "resolution_status": status,
                    "notes": notes,
                },
            )
        return person

    def _clean_gender(self, value):
        gender = str(value or "").strip().upper()
        if len(gender) > 1:
            gender = gender[0]
        return gender

    def _split_multi_value(self, value):
        if not value:
            return []
        return [part.strip() for part in str(value).split(";") if part.strip()]

    def _get_flexible_value(self, row, column_names):
        """Helper method to get value from first available column"""
        for col_name in column_names:
            if col_name in row and row[col_name] is not None:
                value = str(row[col_name]).strip()
                if value:  # Only return non-empty values
                    return value
        return None

    def _parse_name(self, name):
        """Helper method to parse a name into first and last parts"""
        if "," in name:
            parts = [part.strip() for part in name.split(",")]
            last_name = parts[0]
            first_name = parts[1] if len(parts) > 1 else ""
        else:
            parts = name.split()
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = " ".join(parts[1:])
            else:
                first_name = ""
                last_name = name
        return first_name, last_name


MIDURA_HEADERS = [
    "Number",
    "Crime",
    "Description of Case",
    "Court",
    "Trial_Phase",
    "Sentence",
    "Convicted",
    "Sentence_Enforced (Y/N)",
    "Date (Modern Format)",
    "Year",
    "Month",
    "Day",
    "Victim_Name",
    "Assailant_Name",
    "Assailant_External_IDs",
    "Reference",
    "Input by",
]


def normalize_midura_dataset(dataset):
    """Convert Midura's one-row-per-subject TSV into canonical crime rows."""
    grouped = OrderedDict()
    for source_row in dataset.dict:
        number = _clean_value(source_row.get("Number"))
        if not number:
            number = f"AUTO_{int(time.time() * 1000000)}"

        row = grouped.setdefault(
            number,
            {
                "Number": number,
                "Crime": "",
                "Description of Case": "",
                "Court": "",
                "Trial_Phase": "",
                "Sentence": "",
                "Convicted": "",
                "Sentence_Enforced (Y/N)": "",
                "Date (Modern Format)": "",
                "Year": "",
                "Month": "",
                "Day": "",
                "Victim_Name": "",
                "Assailant_Name": "",
                "Assailant_External_IDs": "",
                "Reference": "",
                "Input by": "",
            },
        )

        for source, destination in [
            ("Crime", "Crime"),
            ("Description of Case", "Description of Case"),
            ("Court", "Court"),
            ("Trial_Phase", "Trial_Phase"),
            ("Sentence", "Sentence"),
            ("Convicted", "Convicted"),
            ("Sentence_Enforced", "Sentence_Enforced (Y/N)"),
            ("Sentence_Enforced (Y/N)", "Sentence_Enforced (Y/N)"),
            ("Date (Modern Format)", "Date (Modern Format)"),
            ("Year", "Year"),
            ("Month", "Month"),
            ("Day", "Day"),
            ("Victim_Name", "Victim_Name"),
            ("Reference", "Reference"),
            ("Input by", "Input by"),
        ]:
            value = _clean_value(source_row.get(source))
            if value and not row[destination]:
                row[destination] = value

        # Year-only values belong in Year, not in the exact DateField.
        if re.fullmatch(r"\d{4}", row["Date (Modern Format)"]):
            if not row["Year"]:
                row["Year"] = row["Date (Modern Format)"]
            row["Date (Modern Format)"] = ""

        assailant = _clean_value(source_row.get("Assailant_Name"))
        if assailant:
            existing = (
                set(row["Assailant_Name"].split("; "))
                if row["Assailant_Name"]
                else set()
            )
            if assailant not in existing:
                row["Assailant_Name"] = "; ".join(
                    part for part in [row["Assailant_Name"], assailant] if part
                )

        external_id = _clean_value(source_row.get("subject_ids"))
        if external_id:
            existing_ids = (
                set(row["Assailant_External_IDs"].split("; "))
                if row["Assailant_External_IDs"]
                else set()
            )
            if external_id not in existing_ids:
                row["Assailant_External_IDs"] = "; ".join(
                    part
                    for part in [row["Assailant_External_IDs"], external_id]
                    if part
                )

    normalized = Dataset(headers=MIDURA_HEADERS)
    for row in grouped.values():
        normalized.append([row.get(header, "") for header in MIDURA_HEADERS])
    return normalized


class MiduraCrimeResource(CrimeResource):
    """Import profile for Rachel Midura's High Crime in Venice TSV."""

    source_dataset_name = "Midura"
    import_profile = "midura_high_crime_venice"

    class Meta(CrimeResource.Meta):
        name = "Midura High Crime TSV"

    def import_data(self, dataset, *args, **kwargs):
        return super().import_data(normalize_midura_dataset(dataset), *args, **kwargs)
