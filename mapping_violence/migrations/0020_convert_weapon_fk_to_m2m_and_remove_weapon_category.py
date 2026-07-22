# Convert Crime.weapon from FK to M2M and remove legacy WeaponCategory model.

from django.db import migrations, models


def migrate_weapon_fk_to_m2m(apps, schema_editor):
    """Copy each Crime's FK weapon into the new M2M relationship."""
    Crime = apps.get_model("mapping_violence", "Crime")
    for crime in Crime.objects.filter(weapon_old__isnull=False).iterator():
        crime.weapon.add(crime.weapon_old)


def migrate_weapon_m2m_to_fk(apps, schema_editor):
    """Reverse: copy the first M2M weapon back to the FK field."""
    Crime = apps.get_model("mapping_violence", "Crime")
    for crime in Crime.objects.prefetch_related("weapon").iterator():
        first = crime.weapon.first()
        if first:
            crime.weapon_old = first
            crime.save(update_fields=["weapon_old_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("mapping_violence", "0019_add_crime_images"),
    ]

    operations = [
        # 1. Remove legacy WeaponCategory FK from Weapon
        migrations.RemoveField(
            model_name="weapon",
            name="category",
        ),
        # 2. Rename existing FK column so we can reuse the name "weapon" for M2M
        migrations.RenameField(
            model_name="crime",
            old_name="weapon",
            new_name="weapon_old",
        ),
        # 3. Add new M2M field
        migrations.AddField(
            model_name="crime",
            name="weapon",
            field=models.ManyToManyField(
                blank=True,
                help_text="Select weapon(s) used. Hold Ctrl/Cmd to select multiple.",
                to="mapping_violence.weapon",
                verbose_name="Weapon(s)",
            ),
        ),
        # 4. Copy FK data into M2M
        migrations.RunPython(migrate_weapon_fk_to_m2m, migrate_weapon_m2m_to_fk),
        # 5. Remove the old FK column
        migrations.RemoveField(
            model_name="crime",
            name="weapon_old",
        ),
        # 6. Delete the legacy WeaponCategory model
        migrations.DeleteModel(
            name="WeaponCategory",
        ),
    ]
