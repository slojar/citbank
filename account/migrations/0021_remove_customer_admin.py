# Generated by Django 4.0.3 on 2022-09-14 16:58

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0020_customer_admin'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customer',
            name='admin',
        ),
    ]
