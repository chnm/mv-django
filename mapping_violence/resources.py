import time
from datetime import datetime

from import_export import fields, resources, widgets
from import_export.widgets import BooleanWidget

from locations.models import Location

from .models import Crime, Event, Person, Weapon


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

        # Try to find existing person or create new one
        person, created = Person.objects.get_or_create(
            first_name=first_name,
            last_name=last_name,
            defaults={"first_name": first_name, "last_name": last_name},
        )
        return person


class WeaponWidget(widgets.ForeignKeyWidget):
    """Custom widget for Weapon fields"""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        weapon, created = Weapon.objects.get_or_create(
            name=value, defaults={"name": value}
        )
        return weapon


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
    """Custom widget for Location fields"""

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None

        location, created = Location.objects.get_or_create(
            name=value, defaults={"name": value}
        )
        return location


class CustomDateWidget(widgets.Widget):
    """Custom date widget that handles various date formats"""

    def clean(self, value, row=None, **kwargs):
        if not value or str(value).strip() == "":
            # If no date provided, try to parse from year/month if available
            year = row.get("Year", "") if row else ""
            month = row.get("Month", "") if row else ""

            if year and month:
                try:
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
                        month_num = month_names[month]
                    else:
                        month_num = int(month)

                    year_num = int(year)
                    return datetime(year_num, month_num, 1).date()
                except (ValueError, TypeError):
                    pass

            # Default to a placeholder date if nothing else works
            return datetime(1600, 1, 1).date()

        # Try to parse various date formats
        value_str = str(value).strip()

        # Try different date formats
        date_formats = [
            "%m/%d/%Y",  # 03/15/1615
            "%m/%Y",  # 05/1612
            "%Y-%m-%d",  # 1615-03-15
            "%Y/%m/%d",  # 1615/03/15
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(value_str, fmt).date()
                return parsed_date
            except ValueError:
                continue

        # If none of the formats work, try to extract year/month manually
        try:
            if "/" in value_str:
                parts = value_str.split("/")
                if len(parts) == 2:  # MM/YYYY format
                    month, year = parts
                    return datetime(int(year), int(month), 1).date()
                elif len(parts) == 3:  # MM/DD/YYYY format
                    month, day, year = parts
                    return datetime(int(year), int(month), int(day)).date()
        except (ValueError, TypeError):
            pass

        # Last resort: return placeholder date
        return datetime(1600, 1, 1).date()


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

    # Map CSV columns to model fields with custom widgets
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

    victim_gender = fields.Field(
        column_name="Victim_Gender", attribute="victim_gender", readonly=True
    )

    victim_occupation = fields.Field(
        column_name="Victim_Occupation", attribute="victim_occupation", readonly=True
    )

    assailant_name = fields.Field(
        column_name="Assailant_Name", attribute="assailant_name", readonly=True
    )

    assailant_gender = fields.Field(
        column_name="Assailant_Gender", attribute="assailant_gender", readonly=True
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
        widget=WeaponWidget(Weapon, "name"),
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

    input_by_name = fields.Field(
        column_name="Input by", attribute="input_by_name", readonly=True
    )

    class Meta:
        model = Crime
        # Don't use number as import_id since we're auto-generating it
        fields = (
            "number",
            "crime",
            "description_of_case",
            "court",
            "court_classification",
            "trial_phase",
            "arbitration",
            "sentence",
            "sentence_enforced",
            "date",
            "year",
            "month",
            "day",
            "day_of_week",
            "time",
            "connected_event",
            "victim_name",
            "victim_gender",
            "victim_occupation",
            "assailant_name",
            "assailant_gender",
            "victim_description",
            "assailant_description",
            "motive",
            "relationship",
            "weapon",
            "description_of_location",
            "fatality",
            "archival_location",
            "reference",
            "input_by_name",
        )
        skip_unchanged = False
        report_skipped = False
        use_bulk = False
        import_id_fields = []

    def before_import_row(self, row, **kwargs):
        """Process row before importing"""

        # Skip completely empty rows
        if self.is_empty_row(row):
            raise ValueError("There are empty rows in the data - please remove them.")

        # Handle Y/N values for boolean fields
        bool_fields = ["Arbitration (Y/N)", "Sentence_Enforced (Y/N)", "Fatality (Y/N)"]
        for field in bool_fields:
            if field in row:
                value = str(row[field]).strip().upper()
                row[field] = value == "Y" or value == "YES"

        # Handle empty number fields by generating unique values
        if not row.get("Number") or str(row.get("Number", "")).strip() == "":
            # Generate a unique number based on timestamp and microseconds
            timestamp = int(time.time() * 1000000)  # microseconds since epoch
            row["Number"] = f"AUTO_{timestamp}"

        return super().before_import_row(row, **kwargs)

    def is_empty_row(self, row):
        """Check if a row is essentially empty"""
        # Key fields that should have data for a valid crime record
        key_fields = ["Crime", "Description of Case", "Year"]

        # Check if any key field has meaningful data
        for field in key_fields:
            value = row.get(field, "")
            if value and str(value).strip():
                return False

        # If no key fields have data, consider it empty
        return True

    def after_save_instance(self, instance, row, **kwargs):
        """Process instance after saving - this is called after the instance is saved to DB"""
        # Handle many-to-many relationships for victims and perpetrators
        if instance and instance.pk:
            # Handle victim names
            victim_names = row.get("Victim_Name", "")
            if victim_names and str(victim_names).strip():
                for name in str(victim_names).split(";"):
                    name = name.strip()
                    if name:
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

                        person, created = Person.objects.get_or_create(
                            first_name=first_name,
                            last_name=last_name,
                            defaults={
                                "first_name": first_name,
                                "last_name": last_name,
                                "gender": row.get("Victim_Gender", ""),
                                "occupation": row.get("Victim_Occupation", ""),
                            },
                        )
                        instance.victim.add(person)

            # Handle perpetrator names
            perpetrator_names = row.get("Assailant_Name", "")
            if perpetrator_names and str(perpetrator_names).strip():
                for name in str(perpetrator_names).split(";"):
                    name = name.strip()
                    if name:
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

                        person, created = Person.objects.get_or_create(
                            first_name=first_name,
                            last_name=last_name,
                            defaults={
                                "first_name": first_name,
                                "last_name": last_name,
                                "gender": row.get("Assailant_Gender", ""),
                            },
                        )
                        instance.perpetrator.add(person)

    def get_instance(self, instance_loader, row, **kwargs):
        """Always return None to create new instances instead of updating existing ones"""
        return None
