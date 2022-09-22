# Generated by Django 4.0.3 on 2022-09-12 10:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billpayment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CableTV',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_name', models.CharField(max_length=100)),
                ('account_no', models.CharField(max_length=10)),
                ('smart_card_no', models.CharField(max_length=100)),
                ('customer_name', models.CharField(max_length=200)),
                ('phone_number', models.CharField(max_length=20)),
                ('product', models.CharField(max_length=100)),
                ('months', models.CharField(help_text='Number of months subscribing for', max_length=5)),
                ('amount', models.CharField(max_length=50)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('transaction_id', models.CharField(blank=True, max_length=100, null=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]