# Generated by Django 4.0.3 on 2022-09-14 12:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billpayment', '0002_cabletv'),
    ]

    operations = [
        migrations.AlterField(
            model_name='airtime',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=20),
        ),
        migrations.AlterField(
            model_name='cabletv',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=20),
        ),
        migrations.AlterField(
            model_name='data',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=20),
        ),
    ]
