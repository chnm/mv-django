import csv
from datetime import date
from io import StringIO
from types import SimpleNamespace

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from tablib import Dataset

from locations.models import City, Location
from mapping_violence.admin import CrimeAdmin, ImportBatchAdmin
from mapping_violence.models import (
    Crime,
    ExternalPersonIdentifier,
    ImportBatch,
    Person,
    SourceDataset,
    Weapon,
)
from mapping_violence.resources import (
    CrimeResource,
    MiduraCrimeResource,
    canonical_import_headers,
    normalize_midura_dataset,
)


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

    def test_repeated_case_number_creates_distinct_crimes(self):
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

        self.assertEqual(Crime.objects.filter(number="MV-001").count(), 2)
        crime = Crime.objects.get(crime="homicide")
        self.assertEqual(crime.crime, "homicide")
        self.assertEqual([str(v) for v in crime.victim.all()], ["Marco Rossi"])
        self.assertEqual([str(p) for p in crime.perpetrator.all()], ["Luca Contarini"])
        self.assertEqual([str(w) for w in crime.weapon.all()], ["Dagger"])

    def test_database_id_updates_existing_crime(self):
        crime = Crime.objects.create(number="MV-UPDATE", crime="assault")

        self.import_rows(
            {
                "Database ID": crime.pk,
                "Number": "MV-UPDATE",
                "Crime": "homicide",
                "Victim_Name": "Rossi, Marco",
            }
        )

        self.assertEqual(Crime.objects.count(), 1)
        crime.refresh_from_db()
        self.assertEqual(crime.crime, "homicide")
        self.assertEqual([str(v) for v in crime.victim.all()], ["Marco Rossi"])

    def test_unknown_database_id_is_rejected_instead_of_creating_explicit_pk(self):
        dataset = Dataset(headers=["Database ID", "Number", "Crime"])
        dataset.append([999999, "MV-UNKNOWN", "assault"])

        result = CrimeResource().import_data(
            dataset,
            dry_run=False,
            raise_errors=False,
        )

        self.assertTrue(result.has_validation_errors())
        self.assertEqual(Crime.objects.count(), 0)
        self.assertIn("does not exist", str(result.invalid_rows[0].error))

    def test_blank_number_remains_blank(self):
        self.import_rows({"Crime": "assault"})

        crime = Crime.objects.get()
        self.assertEqual(crime.number, "")

    def test_case_number_alias_is_normalized_before_header_validation(self):
        dataset = Dataset(
            headers=[
                "Case Number",
                "Date (Modern Format)",
                "Year",
                "Victim_Name",
                "City",
            ]
        )
        dataset.append(["PAD-001", "1621-09-29", "1621", "Francesco", "Padua"])

        result = CrimeResource().import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        crime = Crime.objects.get(number="PAD-001")
        self.assertEqual(crime.date, date(1621, 9, 29))
        self.assertEqual(crime.address.city.name, "Padua")

    def test_known_header_variants_are_normalized_to_canonical_columns(self):
        dataset = Dataset(
            headers=[
                "Case_number",
                "Description_of_Case",
                "Date_of_Crime",
                "Day_of_Week",
                "Weapon",
                "Archival_Location",
                "Location",
                "",
            ]
        )
        dataset.append(
            [
                "ROSE-001",
                "A described case",
                "1610-05-02",
                "Sunday",
                "Sword",
                "Archive ref",
                "Venice",
                "",
            ]
        )

        resource = CrimeResource()
        result = resource.import_data(dataset, dry_run=False, raise_errors=True)

        self.assertFalse(result.has_errors())
        crime = Crime.objects.get(number="ROSE-001")
        self.assertEqual(crime.description_of_case, "A described case")
        self.assertEqual(crime.date, date(1610, 5, 2))
        self.assertEqual(crime.day_of_week, "Sunday")
        self.assertEqual(crime.archival_location, "Archive ref")
        self.assertEqual([weapon.name for weapon in crime.weapon.all()], ["Sword"])
        self.assertEqual(crime.address.city.name, "Venice")
        self.assertEqual(resource.normalization_summary["ignored_blank_columns"], 1)

    def test_missing_database_and_case_number_columns_still_create_record(self):
        dataset = Dataset(headers=["Crime", "City"])
        dataset.append(["assault", "Padua"])

        result = CrimeResource().import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
            file_name="no-identifiers.csv",
        )

        self.assertFalse(result.has_errors())
        crime = Crime.objects.get()
        self.assertIsNotNone(crime.pk)
        self.assertEqual(crime.number, "")

    def test_duplicate_number_within_one_file_creates_distinct_records(self):
        dataset = Dataset(headers=["Number", "Crime"])
        dataset.append(["DUP-001", "assault"])
        dataset.append(["DUP-001", "homicide"])

        result = CrimeResource().import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(Crime.objects.count(), 2)
        self.assertEqual(
            set(Crime.objects.values_list("crime", flat=True)),
            {"assault", "homicide"},
        )
        self.assertEqual(result.totals["new"], 2)
        self.assertEqual(result.totals["update"], 0)

    def test_large_dataset_uses_fast_preview_without_generated_case_numbers(self):
        dataset = Dataset(headers=["Case Number", "Crime"])
        for row_number in range(501):
            dataset.append(["", f"crime-{row_number}"])

        resource = CrimeResource()
        result = resource.import_data(dataset, dry_run=True, raise_errors=True)

        numbers = dataset["Number"]
        self.assertTrue(resource._meta.skip_diff)
        self.assertTrue(all(number == "" for number in numbers))
        self.assertTrue(resource.normalization_summary["row_diffs_omitted"])
        self.assertTrue(result.large_import_preview)
        self.assertEqual(result.preview_headers, ["Number", "Crime"])
        self.assertEqual(result.preview_count, 20)
        self.assertEqual(result.preview_remaining, 481)
        self.assertEqual(
            result.preview_rows[0],
            {"import_type": "new", "values": ["", "crime-0"]},
        )
        self.assertEqual(len(result.valid_rows()), 501)

        small_dataset = Dataset(headers=["Number", "Crime"])
        small_dataset.append(["SMALL-1", "assault"])
        small_resource = CrimeResource()
        small_result = small_resource.import_data(
            small_dataset,
            dry_run=True,
            raise_errors=True,
        )
        self.assertFalse(small_resource._meta.skip_diff)
        self.assertIsNotNone(small_result.valid_rows()[0].diff)

    def test_normalization_removes_completely_empty_rows(self):
        dataset = Dataset(headers=["Case Number", "Crime", ""])
        dataset.append(["PAD-001", "assault", ""])
        dataset.append(["", "", ""])

        resource = CrimeResource()
        resource.before_import(dataset)

        self.assertEqual(dataset.height, 1)
        self.assertEqual(resource.normalization_summary["ignored_empty_rows"], 1)

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
        crime = Crime.objects.get(number="MV-003")

        self.import_rows(
            {
                "Database ID": crime.pk,
                "Number": "MV-003",
                "Crime": "assault",
                "Victim_First_Name": "Marco",
                "Victim_Last_Name": "Rossi",
                "Assailant_First": "Luca",
                "Assailant_Last_Name": "Contarini",
            }
        )

        crime.refresh_from_db()
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

    def test_import_batch_is_not_attached_to_preexisting_crime(self):
        crime = Crime.objects.create(number="MV-009", crime="assault")
        batch = ImportBatch.objects.create(
            original_filename="source.csv",
            import_profile="canonical",
        )

        dataset = Dataset(headers=["Database ID", "Number", "Crime"])
        dataset.append([crime.pk, "MV-009", "homicide"])
        result = CrimeResource(import_batch=batch).import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        crime.refresh_from_db()
        self.assertEqual(crime.crime, "homicide")
        self.assertIsNone(crime.import_batch)


class CrimeAdminImportBatchTestCase(TestCase):
    """Confirmed admin imports create auditable, safely reversible batches."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="importer",
            email="importer@example.com",
            password="test",
        )
        self.factory = RequestFactory()
        self.crime_admin = CrimeAdmin(Crime, admin.site)
        self.batch_admin = ImportBatchAdmin(ImportBatch, admin.site)

    def request(self, data=None):
        request = self.factory.post("/admin/", data or {})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def form(self, filename="padua.csv"):
        return SimpleNamespace(
            cleaned_data={
                "resource": "0",
                "original_file_name": filename,
            }
        )

    def padua_dataset(self):
        dataset = Dataset(
            headers=["Case Number", "Date (Modern Format)", "Victim_Name", "City"]
        )
        dataset.append(["", "1621-09-29", "Francesco Ferro", "Padua"])
        return dataset

    def test_confirmed_import_creates_batch_with_counts_and_provenance(self):
        result = self.crime_admin.process_dataset(
            self.padua_dataset(),
            self.form(),
            self.request(),
        )

        self.assertFalse(result.has_errors())
        batch = ImportBatch.objects.get()
        crime = Crime.objects.get()
        self.assertEqual(batch.original_filename, "padua.csv")
        self.assertEqual(batch.import_profile, "canonical")
        self.assertEqual(batch.uploaded_by, self.user)
        self.assertEqual(len(batch.content_sha256), 64)
        self.assertEqual(batch.rows_total, 1)
        self.assertEqual(batch.rows_created, 1)
        self.assertEqual(batch.rows_updated, 0)
        self.assertEqual(batch.status, ImportBatch.IMPORTED)
        self.assertIn("Case Number -> Number", batch.notes)
        self.assertEqual(crime.import_batch, batch)
        self.assertEqual(result.import_batch, batch)

    def test_success_message_links_to_import_batch(self):
        request = self.request()
        result = self.crime_admin.process_dataset(
            self.padua_dataset(),
            self.form(),
            request,
        )
        batch = ImportBatch.objects.get()

        self.crime_admin.add_success_message(result, request)

        rendered_messages = " ".join(str(message) for message in request._messages)
        self.assertIn(
            reverse("admin:mapping_violence_importbatch_change", args=[batch.pk]),
            rendered_messages,
        )
        self.assertIn(
            reverse("admin:mapping_violence_importbatch_changelist"),
            rendered_messages,
        )
        self.assertIn("Import batches", rendered_messages)

    def test_import_batches_are_listed_below_violence_events_in_sidebar(self):
        data_management = settings.UNFOLD["SIDEBAR"]["navigation"][0]["items"]

        self.assertEqual(data_management[0]["title"], "Violence Events")
        self.assertEqual(data_management[1]["title"], "Import batches")
        self.assertEqual(
            data_management[1]["link"],
            "/admin/mapping_violence/importbatch/",
        )

    def test_reimport_without_database_ids_creates_a_new_batch_of_records(self):
        self.crime_admin.process_dataset(
            self.padua_dataset(), self.form(), self.request()
        )
        self.crime_admin.process_dataset(
            self.padua_dataset(), self.form(), self.request()
        )

        self.assertEqual(Crime.objects.count(), 2)
        first_batch, second_batch = ImportBatch.objects.order_by("pk")
        self.assertEqual(first_batch.rows_created, 1)
        self.assertEqual(second_batch.rows_created, 1)
        self.assertEqual(second_batch.rows_updated, 0)
        self.assertEqual(second_batch.crimes.count(), 1)

    def test_database_id_update_is_counted_but_not_owned_by_batch(self):
        crime = Crime.objects.create(number="EXISTING", crime="assault")
        dataset = Dataset(headers=["Database ID", "Number", "Crime"])
        dataset.append([crime.pk, "EXISTING", "homicide"])

        self.crime_admin.process_dataset(dataset, self.form(), self.request())

        batch = ImportBatch.objects.get()
        crime.refresh_from_db()
        self.assertEqual(crime.crime, "homicide")
        self.assertEqual(batch.rows_created, 0)
        self.assertEqual(batch.rows_updated, 1)
        self.assertEqual(batch.crimes.count(), 0)
        self.assertIn("will not be deleted by rollback", batch.notes)

    def test_confirmed_batch_rollback_deletes_only_created_crimes(self):
        preexisting = Crime.objects.create(number="EXISTING", crime="assault")
        self.crime_admin.process_dataset(
            self.padua_dataset(), self.form(), self.request()
        )
        batch = ImportBatch.objects.get()

        response = self.batch_admin.rollback_batches(
            self.request({"confirm_rollback": "yes"}),
            ImportBatch.objects.filter(pk=batch.pk),
        )

        self.assertIsNone(response)
        self.assertEqual(list(Crime.objects.all()), [preexisting])
        batch.refresh_from_db()
        self.assertEqual(batch.status, ImportBatch.ROLLED_BACK)
        self.assertIn("Updates to pre-existing records were not reverted", batch.notes)

    def test_batch_rollback_confirmation_explains_destructive_scope(self):
        self.crime_admin.process_dataset(
            self.padua_dataset(), self.form(), self.request()
        )
        batch = ImportBatch.objects.get()

        response = self.batch_admin.rollback_batches(
            self.request(),
            ImportBatch.objects.filter(pk=batch.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm import rollback")
        self.assertContains(response, "This action cannot be undone")
        self.assertContains(response, "1 violence event will be permanently deleted")
        self.assertContains(response, "Updates to existing records will be preserved")
        self.assertContains(response, "padua.csv")


class CrimeAdminImportGuideTestCase(TestCase):
    """The canonical import documentation stays private and resource-driven."""

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="guide-admin",
            email="guide@example.com",
            password="test",
        )
        self.guide_url = reverse("admin:mapping_violence_crime_import_guide")
        self.template_url = reverse("admin:mapping_violence_crime_import_template")

    def test_import_guide_and_template_require_admin_login(self):
        guide_response = self.client.get(self.guide_url)
        template_response = self.client.get(self.template_url)

        self.assertEqual(guide_response.status_code, 302)
        self.assertEqual(template_response.status_code, 302)
        self.assertIn(reverse("admin:login"), guide_response.url)
        self.assertIn(reverse("admin:login"), template_response.url)

    def test_import_guide_explains_database_identity_and_links_template(self):
        self.client.force_login(self.user)

        response = self.client.get(self.guide_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<code>Database ID</code>", html=True)
        self.assertContains(response, "Leave")
        self.assertContains(response, self.template_url)
        self.assertContains(response, "Case Number")
        self.assertContains(response, "Case_number")

    def test_downloaded_template_headers_are_generated_from_resource(self):
        self.client.force_login(self.user)

        response = self.client.get(self.template_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        headers = next(csv.reader(StringIO(response.content.decode())))
        self.assertEqual(headers, canonical_import_headers())
        self.assertEqual(headers[0], "Database ID")
        self.assertIn("Category of Space", headers)
        self.assertNotIn("Input by", headers)

    def test_crime_list_and_import_page_link_to_guide(self):
        self.client.force_login(self.user)

        changelist = self.client.get(reverse("admin:mapping_violence_crime_changelist"))
        import_page = self.client.get(reverse("admin:mapping_violence_crime_import"))

        self.assertContains(changelist, self.guide_url)
        self.assertContains(import_page, self.guide_url)
        self.assertContains(import_page, self.template_url)

    def test_large_import_confirmation_shows_totals_and_sample_rows(self):
        self.client.force_login(self.user)
        csv_rows = ["Case Number,Crime"]
        csv_rows.extend(f",crime-{row_number}" for row_number in range(501))
        upload = SimpleUploadedFile(
            "large-import.csv",
            "\n".join(csv_rows).encode(),
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("admin:mapping_violence_crime_import"),
            {"resource": "0", "format": "0", "import_file": upload},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Large import preview")
        self.assertContains(response, "All 501 rows were parsed and validated.")
        self.assertContains(response, "crime-0")
        self.assertContains(response, "crime-19")
        self.assertNotContains(response, "crime-20")
        self.assertContains(
            response,
            "481 additional valid rows are not shown in the sample.",
        )


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
        self.assertEqual(row["Database ID"], str(crime.pk))
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
