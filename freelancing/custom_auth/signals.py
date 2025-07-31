# your_app/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from freelancing.custom_auth.models import Wallet, MerchantProfile

User = get_user_model()
@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    if created:
        # Create wallet with 1000.00 for the new user
        Wallet.objects.create(
            user=instance,
            balance=1000.00
        )


@receiver(post_save, sender=MerchantProfile)
def update_user_merchant_flag(sender, instance, created, **kwargs):
    if created:
        user = instance.user
        user.is_merchant = True
        user.merchant_id = instance.id
        user.save(update_fields=["is_merchant", "merchant_id"])
        # No separate wallet creation - user already has wallet