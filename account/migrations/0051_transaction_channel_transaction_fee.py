# Generated by Django 4.0.3 on 2023-11-17 14:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0050_bank_payattitude_client_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='channel',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='transaction',
            name='fee',
            field=models.FloatField(blank=True, null=True),
        ),
    ]