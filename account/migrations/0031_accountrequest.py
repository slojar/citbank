# Generated by Django 4.0.3 on 2022-12-16 15:01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('account', '0030_bank_tm_service_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bvn', models.CharField(max_length=50)),
                ('phone_no', models.CharField(max_length=50)),
                ('first_name', models.CharField(max_length=100)),
                ('last_name', models.CharField(max_length=100)),
                ('other_name', models.CharField(max_length=100)),
                ('gender', models.CharField(choices=[('male', 'Male'), ('female', 'Female')], default='male', max_length=50)),
                ('dob', models.CharField(max_length=50)),
                ('nin', models.CharField(max_length=50)),
                ('email', models.EmailField(max_length=254)),
                ('address', models.CharField(max_length=250)),
                ('signature', models.ImageField(upload_to='account-opening')),
                ('image', models.ImageField(upload_to='account-opening')),
                ('utility', models.ImageField(upload_to='account-opening')),
                ('valid_id', models.ImageField(upload_to='account-opening')),
                ('status', models.CharField(choices=[('approved', 'Approved'), ('declined', 'Declined'), ('pending', 'Pending')], default='pending', max_length=50)),
                ('rejection_reason', models.TextField(blank=True, null=True)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_by', to=settings.AUTH_USER_MODEL)),
                ('rejected_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rejected_by', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
