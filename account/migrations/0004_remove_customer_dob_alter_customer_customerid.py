# Generated by Django 4.0.3 on 2022-04-09 07:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0003_customer_image_alter_customer_customerid'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customer',
            name='dob',
        ),
        migrations.AlterField(
            model_name='customer',
            name='customerID',
            field=models.CharField(default='d3af7c7d-70d0-4150-afdd-67849d227f85', max_length=200),
        ),
    ]
