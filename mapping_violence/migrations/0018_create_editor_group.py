from django.db import migrations


def create_editor_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    group, _ = Group.objects.get_or_create(name="Editor")

    # Grant change (but not add/delete) on core data models
    model_permissions = {
        # app_label, model: [codenames]
        ("mapping_violence", "crime"): ["view_crime", "change_crime"],
        ("mapping_violence", "person"): ["view_person", "change_person", "add_person"],
        ("mapping_violence", "weapon"): ["view_weapon"],
        ("mapping_violence", "event"): ["view_event"],
        ("mapping_violence", "witness"): [
            "view_witness",
            "change_witness",
            "add_witness",
        ],
        ("locations", "location"): ["view_location"],
        ("locations", "city"): ["view_city"],
    }

    for (app_label, model), codenames in model_permissions.items():
        ct = ContentType.objects.get(app_label=app_label, model=model)
        for codename in codenames:
            try:
                perm = Permission.objects.get(content_type=ct, codename=codename)
                group.permissions.add(perm)
            except Permission.DoesNotExist:
                pass


def remove_editor_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Editor").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("mapping_violence", "0017_add_workflow_status_and_assignment"),
        ("locations", "0007_city_country_city_region"),
    ]

    operations = [
        migrations.RunPython(create_editor_group, remove_editor_group),
    ]
