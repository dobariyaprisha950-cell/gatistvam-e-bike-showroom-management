# Generated manually for branch-scoped purchase master data.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('yakuza', '0017_auditlog_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suppliers', to='yakuza.branch'),
        ),
        migrations.AddField(
            model_name='vehiclecolor',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vehicle_colors', to='yakuza.branch'),
        ),
        migrations.AddField(
            model_name='vehiclemodel',
            name='branch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vehicle_models', to='yakuza.branch'),
        ),
        migrations.AlterField(
            model_name='vehiclecolor',
            name='color_name',
            field=models.CharField(max_length=50),
        ),
        migrations.AddConstraint(
            model_name='vehiclecolor',
            constraint=models.UniqueConstraint(fields=('branch', 'color_name'), name='unique_color_name_per_branch'),
        ),
        migrations.AlterUniqueTogether(
            name='vehiclemodel',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='vehiclemodel',
            constraint=models.UniqueConstraint(fields=('branch', 'company', 'model_name'), name='unique_model_name_per_branch_company'),
        ),
    ]
