from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("yakuza", "0025_alter_invoicesequence_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="sales",
            name="extra_accessories",
            field=models.TextField(blank=True, default=""),
        ),
    ]