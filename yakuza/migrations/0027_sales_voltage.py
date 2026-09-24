from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('yakuza', '0026_sales_extra_accessories'),
    ]

    operations = [
        migrations.AddField(
            model_name='sales',
            name='voltage',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
