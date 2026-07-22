from django.db import migrations


def rename_hands_to_no_weapon(apps, schema_editor):
    # Update WeaponCategory rows
    WeaponCategory = apps.get_model("mapping_violence", "WeaponCategory")
    WeaponCategory.objects.filter(name="Hands").update(name="No weapon")

    # Update Weapon.weapon_category CharField values
    Weapon = apps.get_model("mapping_violence", "Weapon")
    Weapon.objects.filter(weapon_category="hands").update(weapon_category="no_weapon")


def rename_no_weapon_to_hands(apps, schema_editor):
    WeaponCategory = apps.get_model("mapping_violence", "WeaponCategory")
    WeaponCategory.objects.filter(name="No weapon").update(name="Hands")

    Weapon = apps.get_model("mapping_violence", "Weapon")
    Weapon.objects.filter(weapon_category="no_weapon").update(weapon_category="hands")


class Migration(migrations.Migration):
    dependencies = [
        ("mapping_violence", "0014_alter_event_options_alter_person_options_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_hands_to_no_weapon, rename_no_weapon_to_hands),
    ]
