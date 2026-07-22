import csv
from datetime import date
from io import StringIO

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from tablib import Dataset

from locations.models import City, Location
from mapping_violence.models import (
    Crime,
    ExternalPersonIdentifier,
    ImportBatch,
    ImportProfile,
    Person,
    SourceDataset,
    Weapon,
)
from mapping_violence.resources import (
    CrimeResource,
    MiduraCrimeResource,
    apply_column_mapping,
    normalize_midura_dataset,
)

User = get_user_model()


class CrimeResourceImportTestCase(TestCase):
    """Regression tests for admin CSV import behavior."""

    def import_rows(self, *rows, resource_kwargs=None):
        default_headers = [
            "Number",
            "Crime",
            "Victim_Name",
            "Victim_Gender",
            "Assailant_Name",
            "Assailant_Gender",
            "Type_of_Weapon",
        ]
        extra_headers = []
        for row in rows:
            for header in row:
                if header not in default_headers and header not in extra_headers:
                    extra_headers.append(header)
        headers = default_headers + extra_headers
        dataset = Dataset(headers=headers)
        for row in rows:
            dataset.append([row.get(header, "") for header in headers])

        result = CrimeResource(**(resource_kwargs or {})).import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )
        self.assertFalse(result.has_errors())
        return result

    def test_import_updates_existing_crime_by_number(self):
        self.import_rows(
            {
                "Number": "MV-001",
                "Crime": "assault",
                "Victim_Name": "Badoer, Angelo",
                "Assailant_Name": "Grimani, Giovanni",
                "Type_of_Weapon": "Sword",
            }
        )

        self.import_rows(
            {
                "Number": "MV-001",
                "Crime": "homicide",
                "Victim_Name": "Rossi, Marco",
                "Assailant_Name": "Contarini, Luca",
                "Type_of_Weapon": "Dagger",
            }
        )

        self.assertEqual(Crime.objects.count(), 1)
        crime = Crime.objects.get(number="MV-001")
        self.assertEqual(crime.crime, "homicide")
        self.assertEqual([str(v) for v in crime.victim.all()], ["Marco Rossi"])
        self.assertEqual([str(p) for p in crime.perpetrator.all()], ["Luca Contarini"])
        self.assertEqual([str(w) for w in crime.weapon.all()], ["Dagger"])

    def test_blank_number_gets_auto_number(self):
        self.import_rows({"Crime": "assault"})

        crime = Crime.objects.get()
        self.assertTrue(crime.number.startswith("AUTO_"))

    def test_reimport_reuses_existing_people_and_weapons(self):
        Person.objects.create(first_name="Angelo", last_name="Badoer")
        Weapon.objects.create(name="Sword")

        self.import_rows(
            {
                "Number": "MV-002",
                "Crime": "assault",
                "Victim_Name": "Badoer, Angelo",
                "Type_of_Weapon": "Sword",
            }
        )

        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Weapon.objects.count(), 1)

    def test_split_name_columns_replace_existing_people(self):
        self.import_rows(
            {
                "Number": "MV-003",
                "Crime": "assault",
                "Victim_Name": "Badoer, Angelo",
                "Assailant_Name": "Grimani, Giovanni",
            }
        )

        self.import_rows(
            {
                "Number": "MV-003",
                "Crime": "assault",
                "Victim_First_Name": "Marco",
                "Victim_Last_Name": "Rossi",
                "Assailant_First": "Luca",
                "Assailant_Last_Name": "Contarini",
            }
        )

        crime = Crime.objects.get(number="MV-003")
        self.assertEqual([str(v) for v in crime.victim.all()], ["Marco Rossi"])
        self.assertEqual([str(p) for p in crime.perpetrator.all()], ["Luca Contarini"])

    def test_external_person_id_reuses_existing_mapping(self):
        source = SourceDataset.objects.create(name="Midura")
        person = Person.objects.create(first_name="Francesco", last_name="Falier")
        ExternalPersonIdentifier.objects.create(
            source_dataset=source,
            external_id="480",
            person=person,
            raw_name="Falier, Francesco",
            resolution_status=ExternalPersonIdentifier.MATCHED,
        )

        self.import_rows(
            {
                "Number": "MV-006",
                "Crime": "treason",
                "Assailant_Name": "Falier, Francesco",
                "Assailant_External_IDs": "480",
            },
            resource_kwargs={"source_dataset": source},
        )

        crime = Crime.objects.get(number="MV-006")
        self.assertEqual(list(crime.perpetrator.all()), [person])

    def test_duplicate_exact_person_match_is_audited_not_crashing(self):
        source = SourceDataset.objects.create(name="Midura")
        first = Person.objects.create(
            first_name="Francesco",
            last_name="Falier",
            honorific="Messer",
        )
        Person.objects.create(
            first_name="Francesco",
            last_name="Falier",
            honorific="Ser",
        )
        dataset = Dataset(
            headers=[
                "Number",
                "Crime",
                "Assailant_Name",
                "Assailant_External_IDs",
            ]
        )
        dataset.append(["MV-007", "treason", "Falier, Francesco", "480"])

        result = CrimeResource(source_dataset=source).import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        crime = Crime.objects.get(number="MV-007")
        self.assertEqual(list(crime.perpetrator.all()), [first])
        identifier = ExternalPersonIdentifier.objects.get(
            source_dataset=source,
            external_id="480",
        )
        self.assertEqual(
            identifier.resolution_status,
            ExternalPersonIdentifier.AMBIGUOUS_NAME_REUSED,
        )
        self.assertIn("Multiple local people", identifier.notes)

    def test_import_batch_is_attached_to_imported_crime(self):
        batch = ImportBatch.objects.create(
            original_filename="source.csv",
            import_profile="canonical",
        )

        dataset = Dataset(headers=["Number", "Crime"])
        dataset.append(["MV-008", "assault"])
        result = CrimeResource(import_batch=batch).import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(Crime.objects.get(number="MV-008").import_batch, batch)


class MiduraCrimeResourceTestCase(TestCase):
    """Regression tests for Midura TSV normalization and import behavior."""

    def midura_dataset(self):
        dataset = Dataset(
            headers=[
                "Number",
                "Crime",
                "Description of Case",
                "Court",
                "Trial_Phase",
                "Sentence",
                "Convicted",
                "Sentence_Enforced",
                "Date (Modern Format)",
                "Year",
                "Month",
                "Day",
                "Victim_Name",
                "Assailant_Name",
                "subject_ids",
                "Reference",
                "Input by",
            ]
        )
        dataset.append(
            [
                "2130",
                "Treason",
                "Group case",
                "Inquisitori di Stato",
                "sentence",
                "",
                "Y",
                "Y",
                "1612",
                "1612",
                "",
                "",
                "",
                "Falier, Francesco",
                "480",
                "ASVe.Gen.197A_2",
                "Midura, Rachel",
            ]
        )
        dataset.append(
            [
                "2130",
                "Nan",
                "Group case",
                "Inquisitori di Stato",
                "sentence",
                "",
                "Y",
                "Y",
                "1612",
                "1612",
                "",
                "",
                "",
                "Contarini, Luca",
                "481",
                "ASVe.Gen.197A_2",
                "Midura, Rachel",
            ]
        )
        return dataset

    def test_normalize_midura_dataset_groups_subject_rows_by_number(self):
        normalized = normalize_midura_dataset(self.midura_dataset())

        self.assertEqual(normalized.height, 1)
        row = normalized.dict[0]
        self.assertEqual(row["Number"], "2130")
        self.assertEqual(row["Crime"], "Treason")
        self.assertEqual(row["Date (Modern Format)"], "")
        self.assertEqual(row["Year"], "1612")
        self.assertEqual(
            row["Assailant_Name"],
            "Falier, Francesco; Contarini, Luca",
        )
        self.assertEqual(row["Assailant_External_IDs"], "480; 481")
        self.assertEqual(row["Sentence_Enforced (Y/N)"], "Y")

    def test_midura_resource_imports_grouped_people_and_external_ids(self):
        result = MiduraCrimeResource().import_data(
            self.midura_dataset(),
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(Crime.objects.count(), 1)
        crime = Crime.objects.get(number="2130")
        self.assertEqual(crime.crime, "Treason")
        self.assertEqual(crime.year, "1612")
        self.assertIsNone(crime.date)
        self.assertEqual(
            [str(person) for person in crime.perpetrator.order_by("last_name")],
            ["Luca Contarini", "Francesco Falier"],
        )
        self.assertEqual(SourceDataset.objects.get().name, "Midura")
        self.assertEqual(
            set(ExternalPersonIdentifier.objects.values_list("external_id", flat=True)),
            {"480", "481"},
        )


class CrimeExportCsvTestCase(TestCase):
    """Regression tests for public CSV export round-tripping into import."""

    def read_csv_response(self, response):
        content = "".join(
            chunk.decode() if isinstance(chunk, bytes) else chunk
            for chunk in response.streaming_content
        )
        return list(csv.DictReader(StringIO(content)))

    def test_export_uses_importable_columns_and_human_readable_values(self):
        city = City.objects.create(name="Venice")
        location = Location.objects.create(
            name="Rialto",
            city=city,
            category_of_space="public",
            description_of_location="Bridge",
        )
        victim = Person.objects.create(
            first_name="Angelo",
            last_name="Badoer",
            gender="M",
            occupation="merchant",
        )
        perpetrator = Person.objects.create(
            first_name="Giovanni",
            last_name="Grimani",
            gender="M",
        )
        sword = Weapon.objects.create(name="Sword")
        dagger = Weapon.objects.create(name="Dagger")
        crime = Crime.objects.create(
            number="MV-004",
            crime="assault",
            description_of_case="A quarrel at the bridge.",
            court="Giudice del Maleficio",
            court_classification="battery",
            trial_phase="sentence",
            arbitration=True,
            sentence="fine",
            convicted=True,
            sentence_enforced=True,
            date=date(1615, 10, 23),
            year="1615",
            month="10",
            day="23",
            day_of_week="Monday",
            time="evening",
            address=location,
            victim_description="merchant of Venice",
            assailant_description="nobleman",
            motive="insult",
            relationship="neighbor",
            description_of_location="near the Rialto",
            fatality=False,
            archival_location="ASVe",
            reference="Ref 1",
        )
        crime.victim.add(victim)
        crime.perpetrator.add(perpetrator)
        crime.weapon.add(sword, dagger)

        response = self.client.get(reverse("crime_export_csv"), {"number": "MV-004"})

        self.assertEqual(response.status_code, 200)
        rows = self.read_csv_response(response)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["Number"], "MV-004")
        self.assertEqual(row["Date (Modern Format)"], "1615-10-23")
        self.assertEqual(row["City"], "Venice")
        self.assertEqual(row["Category of Space"], "public")
        self.assertEqual(row["Description_of_Location"], "Bridge")
        self.assertEqual(row["Victim_Name"], "Angelo Badoer")
        self.assertEqual(row["Victim_Gender"], "M")
        self.assertEqual(row["Victim_Occupation"], "merchant")
        self.assertEqual(row["Assailant_Name"], "Giovanni Grimani")
        self.assertEqual(row["Assailant_Gender"], "M")
        self.assertEqual(row["Type_of_Weapon"], "Dagger; Sword")
        self.assertEqual(row["Arbitration (Y/N)"], "Y")
        self.assertEqual(row["Convicted"], "Y")
        self.assertEqual(row["Sentence_Enforced (Y/N)"], "Y")
        self.assertEqual(row["Fatality (Y/N)"], "N")

    def test_exported_row_can_be_reimported_to_update_same_crime(self):
        Crime.objects.create(number="MV-005", crime="assault")

        response = self.client.get(reverse("crime_export_csv"), {"number": "MV-005"})
        row = self.read_csv_response(response)[0]
        row["Crime"] = "homicide"

        dataset = Dataset(headers=list(row.keys()))
        dataset.append([row[header] for header in row.keys()])
        result = CrimeResource().import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(Crime.objects.count(), 1)
        self.assertEqual(Crime.objects.get(number="MV-005").crime, "homicide")


class ColumnMappingImportTestCase(TestCase):
    """Tests for importing contributor spreadsheets through the mapping wizard."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username="importer",
            email="importer@example.com",
            password="password",
        )

    def test_apply_column_mapping_renames_and_ignores_columns(self):
        source = Dataset(headers=["Case No.", "Incident Type", "Private Notes"])
        source.append(["MV-101", "assault", "not for import"])

        mapped = apply_column_mapping(
            source,
            {
                "Case No.": "Number",
                "Incident Type": "Crime",
                "Private Notes": "",
            },
        )

        self.assertEqual(mapped.headers, ["Number", "Crime"])
        self.assertEqual(list(mapped[0]), ["MV-101", "assault"])

    def test_resource_imports_nonstandard_headers_with_mapping(self):
        source = Dataset(headers=["Case No.", "Incident Type", "Harmed Person"])
        source.append(["MV-102", "assault", "Badoer, Angelo"])

        result = CrimeResource(
            column_mapping={
                "Case No.": "Number",
                "Incident Type": "Crime",
                "Harmed Person": "Victim_Name",
            }
        ).import_data(source, dry_run=False, raise_errors=True)

        self.assertFalse(result.has_errors())
        crime = Crime.objects.get(number="MV-102")
        self.assertEqual(crime.crime, "assault")
        self.assertEqual(
            [str(person) for person in crime.victim.all()], ["Angelo Badoer"]
        )

    def test_admin_mapping_wizard_imports_and_saves_profile(self):
        self.client.force_login(self.user)
        source_dataset = SourceDataset.objects.create(name="Rossi collection")
        crime_admin = admin.site._registry[Crime]
        csv_format_index = next(
            index
            for index, format_class in enumerate(crime_admin.get_import_formats())
            if format_class().get_title() == "csv"
        )
        import_url = reverse("admin:mapping_violence_crime_import")

        upload_response = self.client.post(
            import_url,
            {
                "resource": "0",
                "format": str(csv_format_index),
                "source_dataset": str(source_dataset.pk),
                "import_profile": "",
                "import_file": SimpleUploadedFile(
                    "rossi.csv",
                    b"Case No.,Incident Type,Harmed Person,Private Notes\n"
                    b"MV-103,assault,Grimani Giovanni,omit me\n",
                    content_type="text/csv",
                ),
            },
        )

        self.assertEqual(upload_response.status_code, 200)
        mapping_form = upload_response.context["mapping_form"]
        self.assertEqual(mapping_form["column_0"].value(), "Number")
        self.assertEqual(mapping_form["column_1"].value(), "Crime")

        mapping_post = {
            name: mapping_form[name].value() or ""
            for name, field in mapping_form.fields.items()
            if field.widget.is_hidden
        }
        mapping_post.update(
            {
                "column_0": "Number",
                "column_1": "Crime",
                "column_2": "Victim_Name",
                "column_3": "",
                "save_mapping": "on",
                "profile_name": "Rossi standard export",
            }
        )
        preview_response = self.client.post(import_url, mapping_post)

        self.assertEqual(preview_response.status_code, 200)
        confirm_form = preview_response.context["confirm_form"]
        self.assertIsNotNone(confirm_form)
        profile = ImportProfile.objects.get(name="Rossi standard export")
        self.assertEqual(profile.source_dataset, source_dataset)
        self.assertEqual(profile.column_mapping["Harmed Person"], "Victim_Name")

        confirm_post = {
            name: confirm_form[name].value() or "" for name in confirm_form.fields
        }
        process_url = reverse("admin:mapping_violence_crime_process_import")
        final_response = self.client.post(process_url, confirm_post)

        self.assertRedirects(
            final_response,
            reverse("admin:mapping_violence_crime_changelist"),
        )
        crime = Crime.objects.get(number="MV-103")
        self.assertEqual(crime.crime, "assault")
        self.assertEqual(crime.input_by, self.user)
        self.assertEqual(
            [str(person) for person in crime.victim.all()], ["Grimani Giovanni"]
        )
