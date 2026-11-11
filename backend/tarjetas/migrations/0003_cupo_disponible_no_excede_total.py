from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tarjetas', '0002_initial'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='tarjeta',
            constraint=models.CheckConstraint(condition=models.Q(('cupo_disponible__lte', models.F('cupo_total'))), name='tarjeta_cupo_disponible_no_excede_total'),
        ),
    ]