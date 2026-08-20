from django.db import migrations


def create_initial_branch(apps, schema_editor):
    Branch = apps.get_model("yakuza", "Branch")
    UserProfile = apps.get_model("yakuza", "UserProfile")
    User = apps.get_model("auth", "User")

    branch, _ = Branch.objects.get_or_create(
        branch_code="JND01",
        defaults={
            "branch_name": "Junagadh",
            "owner_name": "Gatistvam E-Bike",
            "address": "Junagadh, Gujarat",
            "city": "Junagadh",
            "phone": "",
            "gst_number": "",
            "is_active": True,
        },
    )

    try:
        user = User.objects.get(username="dell")

        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "branch": branch,
                "role": "SUPER_ADMIN",
                "is_active": True,
            },
        )
    except User.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ("yakuza", "0020_branchsyncstatus_syncoutbox"),
    ]

    operations = [
        migrations.RunPython(
            create_initial_branch,
            migrations.RunPython.noop,
        ),
    ]