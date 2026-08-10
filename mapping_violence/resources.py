import hashlib
import json
import re
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime

from django.core.exceptions import ValidationError
from import_export import fields, resources, widgets
from import_export.instance_loaders import ModelInstanceLoader
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

LARGE_IMPORT_PREVIEW_THRESHOLD = 500
LARGE_IMPORT_PREVIEW_SAMPLE_SIZE = 20


def _is_blankish(value):
    return str(value or "").strip().lower() in {"", "nan", "none", "null"}


def _clean_value(value):
    return "" if _is_blankish(value) else str(value).strip()


class MutableCachedInstanceLoader(ModelInstanceLoader):
    """Cache optional database IDs and records created earlier in the file."""

    def __init__(self, resource, dataset=None):
        super().__init__(resource, dataset)
        self.pk_field = resource.fields[resource.get_import_id_fields()[0]]
        ids = []
        for row in dataset.dict if dataset else []:
            value = row.get(self.pk_field.column_name)
            if not _is_blankish(value):
                ids.append(self.pk_field.clean(row))
        queryset = self.get_queryset().filter(pk__in=ids)
        self.all_instances = {instance.pk: instance for instance in queryset}
        resource.active_instance_loader = self

    def get_instance(self, row):
        value = row.get(self.pk_field.column_name)
        if _is_blankish(value):
            return None
        database_id = self.pk_field.clean(row)
        instance = self.all_instances.get(database_id)
        if instance is None:
            raise ValidationError(
                {
                    self.pk_field.column_name: (
                        f"Crime with Database ID {database_id} does not exist. "
                        "Remove the Database ID to create a new record."
                    )
                }
            )
        return instance

    def register(self, instance):
        self.all_instances[instance.pk] = instance


CANONICAL_HEADER_ALIASES = {
    "Case Number": "Number",
    "Case_number": "Number",
    "Description_of_Crime": "Description of Case",
    "Description_of_Case": "Description of Case",
    "Date_of_Crime (Modern)": "Date (Modern Format)",
    "Date_of_Crime": "Date (Modern Format)",
    "Day_of_Week": "Day_of_week",
    "Weapon": "Type_of_Weapon",
    "Archival_Location": "Archival Location",
    "Sentence_Enforced": "Sentence_Enforced (Y/N)",
    "Description_of_Location": "Description of Location",
    "Victim Description": "Victim_Description",
    "Input_By": "Input by",
}

# These columns are consumed by LocationWidget from the complete row even
# though they do not map directly to fields on CrimeResource.
CANONICAL_AUXILIARY_HEADERS = (
    "Parish",
    "Latitude",
    "Longitude",
    "Category of Space",
)

IMPORT_HEADER_HELP = {
    "Database ID": (
        "Leave blank to create a record. Use an ID from a Mapping Violence export "
        "to update that exact database record."
    ),
    "Number": (
        "Archival or source case number. It may be blank or repeated and is never "
        "used to decide whether a row is new."
    ),
    "Date (Modern Format)": "Exact date in ISO YYYY-MM-DD format when known.",
    "Arbitration (Y/N)": "Whether arbitration occurred; use Y or N.",
    "Convicted": "Whether the perpetrator was convicted; use Y or N.",
    "Sentence_Enforced (Y/N)": "Whether the sentence was enforced; use Y or N.",
    "Fatality (Y/N)": "Whether the incident caused a fatality; use Y or N.",
    "Victim_Name": (
        "Victim name. Use 'Last, First' for one person and semicolons between "
        "multiple people."
    ),
    "Victim_Last_Name": (
        "Optional legacy split-name column. Victim_Name is preferred for new files."
    ),
    "Victim_Gender": "Victim gender code or label; multiple values use semicolons.",
    "Victim_Occupation": "Victim occupation; multiple values use semicolons.",
    "Assailant_Name": (
        "Assailant name. Use 'Last, First' for one person and semicolons between "
        "multiple people."
    ),
    "Assailant_First": (
        "Optional legacy split-name column. Assailant_Name is preferred for new files."
    ),
    "Assailant_Gender": (
        "Assailant gender code or label; multiple values use semicolons."
    ),
    "Assailant_External_IDs": (
        "Source-specific person identifiers aligned with semicolon-separated "
        "assailant names."
    ),
    "Type_of_Weapon": "Weapon names separated with semicolons.",
    "City": "City associated with the crime location.",
    "Parish": "Optional parish metadata used when creating or enriching a city.",
    "Latitude": "Optional decimal latitude used when creating or enriching a city.",
    "Longitude": "Optional decimal longitude used when creating or enriching a city.",
    "Category of Space": "Optional category used to distinguish locations in a city.",
}

IMPORT_HEADER_EXAMPLES = {
    "Database ID": "1427",
    "Number": "ASVe-001",
    "Crime": "assault",
    "Date (Modern Format)": "1621-09-29",
    "Year": "1621",
    "Month": "9",
    "Day": "29",
    "Time": "evening",
    "Arbitration (Y/N)": "N",
    "Convicted": "Y",
    "Sentence_Enforced (Y/N)": "Y",
    "Fatality (Y/N)": "N",
    "Victim_Name": "Ferro, Francesco",
    "Assailant_Name": "Rossi, Marco; Bianchi, Luca",
    "Type_of_Weapon": "Sword; Dagger",
    "City": "Padua",
    "Parish": "San Lorenzo",
    "Latitude": "45.4064",
    "Longitude": "11.8768",
    "Category of Space": "public",
}


def canonical_import_headers():
    """Return the generated canonical CSV header order for Crime imports."""
    resource = CrimeResource()
    headers = [
        field.column_name
        for field in resource.get_import_fields()
        if field.column_name != "Input by"
    ]
    for header in CANONICAL_AUXILIARY_HEADERS:
        if header not in headers:
            headers.append(header)
    return headers


def dataset_fingerprint(dataset):
    """Return a stable hash of a parsed spreadsheet's headers and rows."""
    payload = {
        "headers": list(dataset.headers or []),
        "rows": [list(row) for row in dataset],
    }
    encoded = json.dumps(
        payload,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_crime_dataset(dataset):
    """Normalize known spreadsheet headers before import-export validates them.

    Canonical columns win when both a canonical header and one of its aliases
    are present. An alias still fills a blank canonical value. Empty trailing
    spreadsheet columns are discarded.
    """
    original_headers = list(dataset.headers or [])
    header_sources = OrderedDict()
    renamed_headers = OrderedDict()
    ignored_headers = []

    for index, original_header in enumerate(original_headers):
        stripped_header = str(original_header or "").strip()
        if not stripped_header:
            ignored_headers.append(original_header)
            continue

        canonical_header = CANONICAL_HEADER_ALIASES.get(
            stripped_header, stripped_header
        )
        if canonical_header != stripped_header:
            renamed_headers[stripped_header] = canonical_header

        source = (stripped_header != canonical_header, index)
        header_sources.setdefault(canonical_header, []).append(source)

    normalized_headers = list(header_sources)
    normalized_rows = []
    ignored_empty_rows = 0
    for source_row in dataset:
        normalized_row = []
        for header in normalized_headers:
            sources = sorted(header_sources[header])  # Canonical source first.
            values = [source_row[index] for _, index in sources]
            value = next((value for value in values if not _is_blankish(value)), "")
            normalized_row.append(value)
        if any(not _is_blankish(value) for value in normalized_row):
            normalized_rows.append(normalized_row)
        else:
            ignored_empty_rows += 1

    dataset.wipe()
    dataset.headers = normalized_headers
    dataset.extend(normalized_rows)
    return {
        "renamed_headers": dict(renamed_headers),
        "ignored_blank_columns": len(ignored_headers),
        "ignored_empty_rows": ignored_empty_rows,
    }


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}

    def clean(self, value, row=None, **kwargs):
        if not value:
            return []

        weapons = []
        for name in str(value).split(";"):
            name = name.strip()
            if name:
                weapon = self._cache.get(name)
                if weapon is None:
                    weapon, _ = Weapon.objects.get_or_create(
                        name=name, defaults={"name": name}
                    )
                    self._cache[name] = weapon
                weapons.append(weapon)
        return weapons


class EventWidget(widgets.ForeignKeyWidget):
    """Custom widget for Event fields"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache = {}

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        event = self._cache.get(value)
        if event is None:
            event, _ = Event.objects.get_or_create(name=value, defaults={"name": value})
            self._cache[value] = event
        return event


class LocationWidget(widgets.ForeignKeyWidget):
    """Custom widget for Location fields that handles City/Location separation"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._city_cache = {}
        self._location_cache = {}

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        # Extract location data from the row
        city_name = row.get("City", "") if row else ""
        parish = row.get("Parish", "") if row else ""
        latitude = row.get("Latitude", "") if row else ""
        longitude = row.get("Longitude", "") if row else ""
        category_of_space = row.get("Category of Space", "") if row else ""
        description_of_location = ""
        if row:
            description_of_location = row.get("Description of Location", "") or row.get(
                "Description_of_Location", ""
            )

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

        city = self._city_cache.get(city_name)
        if city is None:
            city, city_created = City.objects.get_or_create(
                name=city_name, defaults=city_defaults
            )
            self._city_cache[city_name] = city
        else:
            city_created = False

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
        location_key = (city.pk, category_of_space, description_of_location)
        location = self._location_cache.get(location_key)
        if location is None:
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
            self._location_cache[location_key] = location

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
        self.normalization_summary = {}
        super().__init__(**kwargs)
        # Resource options are class-level by default. Copy them so large-file
        # preview optimization is isolated to this resource instance/request.
        self._meta = deepcopy(self._meta)
        self._person_cache = {}
        self._new_row_numbers = set()

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
        is_new = kwargs.get("row_number") in self._new_row_numbers
        if self.importing_user and not instance.input_by_id:
            instance.input_by = self.importing_user
        # A batch owns only records it created. Existing records may be updated
        # by this import, but attaching them would make batch rollback unsafe.
        if self.import_batch and is_new:
            instance.import_batch = self.import_batch
        if is_new:
            instance.status = "triage"
        elif instance.status == "done":
            instance.status = "needs_review"
        return super().before_save_instance(instance, row, **kwargs)

    def after_init_instance(self, instance, new, row, **kwargs):
        if new:
            self._new_row_numbers.add(kwargs.get("row_number"))
        return super().after_init_instance(instance, new, row, **kwargs)

    id = fields.Field(
        column_name="Database ID",
        attribute="id",
        widget=widgets.IntegerWidget(),
    )

    # Map canonical CSV columns to model fields.
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
        # Database ID is the only update key. Number is archival/source data and
        # may be blank or repeated.
        fields = (
            "id",
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
        # Keep this as a list to match django-import-export's special handling
        # for an optional default primary-key column.
        import_id_fields = ["id"]
        instance_loader_class = MutableCachedInstanceLoader

    def before_import(self, dataset, **kwargs):
        """Canonicalize headers before import-export checks import_id_fields."""
        self.normalization_summary = normalize_crime_dataset(dataset)

        # Rendering a field-by-field HTML diff for thousands of rows can exceed
        # common web request timeouts. Large imports still perform all parsing,
        # validation, and create/update classification.
        if len(dataset) > LARGE_IMPORT_PREVIEW_THRESHOLD:
            self._meta.skip_diff = True
            self.normalization_summary["row_diffs_omitted"] = True
            # django-import-export does not pass dry_run to before_import(), so
            # retain this bounded snapshot for both phases and expose it only
            # when after_import() confirms that this is the dry-run preview.
            self._large_preview_headers = list(dataset.headers or [])
            self._large_preview_values = [
                list(row) for row in dataset[:LARGE_IMPORT_PREVIEW_SAMPLE_SIZE]
            ]
        return super().before_import(dataset, **kwargs)

    def after_import(self, dataset, result, **kwargs):
        """Attach a compact large-file sample to the confirmation result."""
        super().after_import(dataset, result, **kwargs)
        if not (
            kwargs.get("dry_run")
            and self.normalization_summary.get("row_diffs_omitted")
        ):
            return
        if result.has_errors() or result.has_validation_errors():
            return

        valid_rows = result.valid_rows()
        sample_rows = valid_rows[:LARGE_IMPORT_PREVIEW_SAMPLE_SIZE]
        sample_values = getattr(self, "_large_preview_values", [])

        result.large_import_preview = True
        result.preview_headers = getattr(self, "_large_preview_headers", [])
        result.preview_rows = [
            {"import_type": row_result.import_type, "values": values}
            for row_result, values in zip(
                sample_rows,
                sample_values,
                strict=False,
            )
        ]
        result.preview_count = len(sample_rows)
        result.preview_remaining = max(len(valid_rows) - len(sample_rows), 0)
        result.preview_error_count = result.totals["error"] + result.totals["invalid"]

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

        # Case numbers are optional source metadata, not database identifiers.
        number = row.get("Number", "")
        if number is not None:
            row["Number"] = str(number).strip()

        return super().before_import_row(row, **kwargs)

    def is_empty_row(self, row):
        """Check if a row is essentially empty.

        A row is considered empty only when it carries no identifier at all —
        no case number and no archival location.  Rows that lack Crime /
        Description / Year but still have a case number or archival reference
        are real (if sparse) records and should be imported.
        """
        return not any(not _is_blankish(value) for value in row.values())

    def after_save_instance(self, instance, row, **kwargs):
        """Process instance after saving - this is called after the instance is saved to DB"""
        # Handle many-to-many relationships for victims and perpetrators
        if instance and instance.pk:
            if hasattr(self, "active_instance_loader"):
                self.active_instance_loader.register(instance)
            is_new = kwargs.get("row_number") in self._new_row_numbers
            victim_columns = [
                "Victim_First_Name",
                "Victim_Last_Name",
                "Victim_Name",
            ]
            if self._row_has_any_column(row, victim_columns):
                victims = self._people_from_row(
                    row,
                    first_columns=["Victim_First_Name"],
                    last_columns=["Victim_Last_Name"],
                    combined_columns=["Victim_Name"],
                    gender_column="Victim_Gender",
                    occupation_column="Victim_Occupation",
                    external_id_columns=["Victim_External_IDs"],
                )
                if is_new:
                    instance.victim.add(*victims)
                else:
                    instance.victim.set(victims)

            assailant_columns = [
                "Assailant_First",
                "Assailant_Last_Name",
                "Assailant_Last",
                "Assailant _ Last_Name",
                "Assailant_Name",
            ]
            if self._row_has_any_column(row, assailant_columns):
                perpetrators = self._people_from_row(
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
                if is_new:
                    instance.perpetrator.add(*perpetrators)
                else:
                    instance.perpetrator.set(perpetrators)

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
        external_cache_key = None
        if self.source_dataset and external_id:
            external_cache_key = (
                "external",
                self.source_dataset.pk,
                external_id,
            )
            cached_person = self._person_cache.get(external_cache_key)
            if cached_person:
                return cached_person
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
                self._person_cache[external_cache_key] = identifier.person
                return identifier.person

        name_cache_key = ("name", first_name, last_name)
        person = self._person_cache.get(name_cache_key)
        status = ExternalPersonIdentifier.CREATED
        notes = ""
        if person is None:
            matches = list(
                Person.objects.filter(
                    first_name=first_name, last_name=last_name
                ).order_by("pk")[:2]
            )
            if matches:
                person = matches[0]
                status = ExternalPersonIdentifier.MATCHED
                if len(matches) > 1:
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
            self._person_cache[name_cache_key] = person
        else:
            status = ExternalPersonIdentifier.MATCHED

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
            self._person_cache[external_cache_key] = person
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
    for row_number, source_row in enumerate(dataset.dict, start=1):
        number = _clean_value(source_row.get("Number"))
        group_key = number or f"__blank_row_{row_number}"

        row = grouped.setdefault(
            group_key,
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
