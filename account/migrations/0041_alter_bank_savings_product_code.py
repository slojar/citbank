# Generated by Django 4.0.3 on 2023-03-10 15:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0040_bank_savings_product_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bank',
            name='savings_product_code',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
