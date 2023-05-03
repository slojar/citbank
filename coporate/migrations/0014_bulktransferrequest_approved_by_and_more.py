# Generated by Django 4.0.3 on 2023-05-03 13:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coporate', '0013_transferrequest_approved_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bulktransferrequest',
            name='approved_by',
            field=models.ManyToManyField(blank=True, related_name='bulk_trans_approved', to='coporate.mandate'),
        ),
        migrations.AddField(
            model_name='bulktransferrequest',
            name='declined_by',
            field=models.ManyToManyField(blank=True, related_name='bulk_trans_declined', to='coporate.mandate'),
        ),
    ]