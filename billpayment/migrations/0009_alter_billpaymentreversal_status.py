# Generated by Django 4.0.3 on 2022-09-27 18:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billpayment', '0008_billpaymentreversal'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billpaymentreversal',
            name='status',
            field=models.CharField(choices=[('completed', 'Completed'), ('pending', 'Pending')], default='pending', max_length=50),
        ),
    ]