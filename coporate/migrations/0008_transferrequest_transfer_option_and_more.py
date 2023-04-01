# Generated by Django 4.0.3 on 2023-04-01 10:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('coporate', '0007_bulkuploadfile'),
    ]

    operations = [
        migrations.AddField(
            model_name='transferrequest',
            name='transfer_option',
            field=models.CharField(choices=[('single', 'Single'), ('bulk', 'Bulk')], default='single', max_length=50),
        ),
        migrations.AlterField(
            model_name='bulkuploadfile',
            name='file',
            field=models.FileField(upload_to='bulk-upload'),
        ),
        migrations.CreateModel(
            name='BulkTransferRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled', models.BooleanField(default=False)),
                ('description', models.CharField(max_length=200)),
                ('checked', models.BooleanField(default=False)),
                ('verified', models.BooleanField(default=False)),
                ('approved', models.BooleanField(default=False)),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('institution', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='coporate.institution')),
                ('scheduler', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='coporate.transferscheduler')),
            ],
        ),
        migrations.AddField(
            model_name='transferrequest',
            name='bulk_transfer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='coporate.bulktransferrequest'),
        ),
    ]
