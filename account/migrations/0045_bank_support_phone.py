# Generated by Django 4.0.3 on 2023-07-05 10:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0044_customeraccount_institution_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bank',
            name='support_phone',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
