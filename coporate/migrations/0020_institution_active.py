# Generated by Django 4.0.3 on 2023-06-26 10:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coporate', '0019_limit_approved_by_limit_declined_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='institution',
            name='active',
            field=models.BooleanField(default=False),
        ),
    ]