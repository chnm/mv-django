# Generated by Django 5.2.4 on 2025-07-17 15:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "mapping_violence",
            "0004_weaponcategory_crime_accord_crime_accord_date_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="witness",
            name="crime",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="witnesses",
                to="mapping_violence.crime",
            ),
        ),
    ]
