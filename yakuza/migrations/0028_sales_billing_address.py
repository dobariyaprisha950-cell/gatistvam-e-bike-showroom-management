from django.db import migrations, models


def populate_legacy_billing_addresses(apps, schema_editor):
    Sales = apps.get_model('yakuza', 'Sales')
    for sale in Sales.objects.filter(billing_address='').select_related('stock__branch').iterator():
        branch = sale.stock.branch if sale.stock_id else None
        sale.billing_address = branch.branch_name if branch else 'Main Branch'
        sale.save(update_fields=['billing_address'])


class Migration(migrations.Migration):
    dependencies = [
        ('yakuza', '0027_sales_voltage'),
    ]

    operations = [
        migrations.AddField(
            model_name='sales',
            name='billing_address',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.RunPython(populate_legacy_billing_addresses, migrations.RunPython.noop),
    ]
