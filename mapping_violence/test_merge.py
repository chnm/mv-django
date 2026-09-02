from django.test import TestCase

from mapping_violence.models import Person, PersonAlias, PersonMergeLog


class ModelShapeTests(TestCase):
    def test_person_alias_defaults_and_str(self):
        p = Person.objects.create(first_name="Anna", last_name="Falier")
        alias = PersonAlias.objects.create(person=p, name="Ser Anna Falier")
        self.assertEqual(str(alias), "Ser Anna Falier")
        self.assertEqual(list(p.aliases.all()), [alias])

    def test_person_alias_unique_per_person_name(self):
        from django.db import IntegrityError

        p = Person.objects.create(first_name="Anna", last_name="Falier")
        PersonAlias.objects.create(person=p, name="dup")
        with self.assertRaises(IntegrityError):
            PersonAlias.objects.create(person=p, name="dup")

    def test_person_merge_log_records_snapshot(self):
        survivor = Person.objects.create(first_name="Anna", last_name="Falier")
        log = PersonMergeLog.objects.create(
            survivor=survivor, merged_person_id=999, merged_person_label="Old Anna"
        )
        self.assertEqual(list(survivor.merge_logs.all()), [log])
        self.assertEqual(log.merged_person_id, 999)
