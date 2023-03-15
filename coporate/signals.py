from django.db.models.signals import post_save
from django.dispatch import receiver

from coporate.models import Institution, Limit


@receiver(signal=post_save, sender=Institution)
def create_transaction_limit(sender, instance, **kwargs):
    if not instance.limit:
        Limit.objects.create(institution=instance)



