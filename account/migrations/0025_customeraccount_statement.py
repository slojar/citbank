# Generated by Django 4.0.3 on 2022-11-04 12:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0024_bank_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='customeraccount',
            name='statement',
            field=models.FileField(blank=True, null=True, upload_to='waybill'),
        ),
    ]