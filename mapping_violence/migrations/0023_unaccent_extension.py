from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("mapping_violence", "0022_extend_import_batch_audit"),
    ]

    operations = [
        UnaccentExtension(),
    ]
