import uuid
from django.utils.translation import gettext_lazy as _
from django.db import models
from freelancing.custom_auth.models import MerchantProfile, BaseModel, Category
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError
from django.utils import timezone
from freelancing.custom_auth.models import Wallet

User = get_user_model()

# Create your models here.
class VoucherType(BaseModel):
    name = models.CharField("Voucher Type Name", max_length=100, unique=True)

    def __str__(self):
        return self.name

class Voucher(BaseModel):
    DEFAULT_TERMS = """Only one offer can be redeemed per transaction.
This offer is applicable once per user.
This offer can't be redeemed or clubbed with any other offers.
This offer is valid in select McDonald's (Hardcastle Restaurants) Branches in the West and South of India.
This offer is not applicable on delivery orders.
This offer cannot be replaced with cash.
This offer is valid while stocks lasts - McDonald's West and South (Hardcastle Restaurants Pvt. Ltd.) reserves the right to change the offers, menu and offers period any time without prior notice."""

    TYPE_PERCENTAGE = 'percentage'
    TYPE_FLAT = 'flat'
    TYPE_PRODUCT = 'product'
    uuid = models.UUIDField(
        verbose_name=_("uuid"),
        unique=True,
        help_text=_(
            "Required. A 32 hexadecimal digits number as specified in RFC 4122"
        ),
        error_messages={
            "unique": _("A user with that uuid already exists."),
        },
        default=uuid.uuid4,
    )
    merchant = models.ForeignKey(MerchantProfile, on_delete=models.CASCADE, related_name='vouchers')
    title = models.CharField("Title", max_length=255)
    message = models.TextField("Message")
    terms_conditions = models.TextField("Terms & Conditions", blank=True, default=DEFAULT_TERMS)
    count = models.PositiveIntegerField("Redemption Count", null=True, blank=True)
    image = models.ImageField(upload_to="vouchers/", null=True, blank=True)
    voucher_type = models.ForeignKey(VoucherType, on_delete=models.PROTECT, related_name='vouchers')

    # Type Specific Fields
    percentage_value = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    percentage_min_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    flat_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    flat_min_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    product_name = models.CharField(max_length=255, null=True, blank=True)
    product_min_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='vouchers')
    redemption_count = models.PositiveIntegerField(default=0)
    
    is_gift_card = models.BooleanField(default=False)  # Hide from frontend listing

    def get_display_image(self):
        return self.image or self.merchant.banner_image

    def __str__(self):
        return f"{self.title} - {self.voucher_type.name}"

    class Meta:
        ordering = ['-create_time']


class Advertisement(BaseModel):
    voucher = models.OneToOneField(Voucher, on_delete=models.CASCADE, related_name="advertisement")
    banner_image = models.ImageField(upload_to="advertisements/")
    start_date = models.DateField()
    end_date = models.DateField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)

    def clean(self):
        if not self.banner_image:
            raise ValidationError("Banner image is required to promote the voucher.")
    def __str__(self):
        return f"Ad: {self.voucher.title} in {self.city}, {self.state}"


class WhatsAppContact(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="whatsapp_contacts")
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    is_on_whatsapp = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({'✅' if self.is_on_whatsapp else '❌'})"

class UserVoucherRedemption(BaseModel):
    """Track which users purchased and redeemed which vouchers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voucher_redemptions')
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='user_redemptions')
    purchased_at = models.DateTimeField(auto_now_add=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    is_gift_voucher = models.BooleanField(default=False)  # Track if it was a gift voucher redemption
    purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Cost in wallet points
    is_active = models.BooleanField(default=True)  # Whether the voucher is still valid
   
    # Additional fields for better purchase management
    purchase_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)  # Unique purchase ID
    purchase_status = models.CharField(
        max_length=20,
        choices=[
            ('purchased', 'Purchased'),
            ('redeemed', 'Redeemed'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled'),
            ('refunded', 'Refunded')
        ],
        default='purchased'
    )
    expiry_date = models.DateTimeField(null=True, blank=True)  # When voucher expires
    redemption_location = models.CharField(max_length=255, null=True, blank=True)  # Where voucher was redeemed
    redemption_notes = models.TextField(null=True, blank=True)  # Additional notes for redemption
    wallet_transaction_id = models.CharField(max_length=100, null=True, blank=True)  # Reference to wallet transaction
   
    class Meta:
        unique_together = ['user', 'voucher']  # User can only purchase a voucher once
        ordering = ['-purchased_at']
   
    def __str__(self):
        return f"{self.user.fullname} purchased {self.voucher.title}"

    def save(self, *args, **kwargs):
        # Generate unique purchase reference if not provided
        if not self.purchase_reference:
            import uuid
            self.purchase_reference = f"VCH-{uuid.uuid4().hex[:8].upper()}"
       
        # Set expiry date if not provided (default 1 year from purchase)
        if not self.expiry_date:
            from datetime import timedelta
            # Use current time if purchased_at is not set yet
            base_time = self.purchased_at if self.purchased_at else timezone.now()
            self.expiry_date = base_time + timedelta(days=365)
       
        super().save(*args, **kwargs)

    def redeem(self, location=None, notes=None):
        """Mark voucher as redeemed with atomic transaction"""
        if not self.is_active:
            raise ValidationError("Voucher is no longer active")
        if self.redeemed_at:
            raise ValidationError("Voucher has already been redeemed")
        if self.is_expired():
            raise ValidationError("Voucher has expired")
       
        try:
            with transaction.atomic():
                # Update redemption details
                self.redeemed_at = timezone.now()
                self.is_active = False
                self.purchase_status = 'redeemed'
                if location:
                    self.redemption_location = location
                if notes:
                    self.redemption_notes = notes
                self.save()
               
                # Increment voucher redemption count atomically
                self.voucher.redemption_count = models.F('redemption_count') + 1
                self.voucher.save(update_fields=['redemption_count'])
               
        except DatabaseError as e:
            raise ValidationError("Failed to redeem voucher due to database error")
        except Exception as e:
            raise ValidationError("Failed to redeem voucher")

    def is_expired(self):
        """Check if voucher has expired"""
        if self.expiry_date:
            return timezone.now() > self.expiry_date
        return False

    def can_redeem(self):
        """Check if voucher can be redeemed"""
        return (
            self.is_active and
            not self.redeemed_at and
            not self.is_expired() and
            self.purchase_status == 'purchased'
        )

    def cancel_purchase(self, reason=None):
        """Cancel a voucher purchase (for refunds) with atomic transaction"""
        if self.redeemed_at:
            raise ValidationError("Cannot cancel redeemed voucher")
       
        try:
            with transaction.atomic():
                self.is_active = False
                self.purchase_status = 'cancelled'
                if reason:
                    self.redemption_notes = f"Cancelled: {reason}"
                self.save()
               
        except DatabaseError as e:
            raise ValidationError("Failed to cancel voucher due to database error")
        except Exception as e:
            raise ValidationError("Failed to cancel voucher")

    def refund_purchase(self, reason=None):
        """Refund a voucher purchase with atomic transaction"""
        if self.redeemed_at:
            raise ValidationError("Cannot refund redeemed voucher")
       
        try:
            with transaction.atomic():
                # Update voucher status
                self.is_active = False
                self.purchase_status = 'refunded'
                if reason:
                    self.redemption_notes = f"Refunded: {reason}"
                self.save()

                # Refund to wallet with atomic transaction
                try:
                    wallet = Wallet.objects.select_for_update().get(user=self.user)
                    wallet.credit(
                        self.purchase_cost,
                        note=f"Voucher Refund: {self.voucher.title}",
                        ref_id=self.purchase_reference
                    )
                except Wallet.DoesNotExist:
                    raise ValidationError("User wallet not found for refund")
                except Exception as e:
                    raise ValidationError("Failed to process wallet refund")
                   
        except ValidationError:
            raise
        except DatabaseError as e:
            raise ValidationError("Failed to refund voucher due to database error")
        except Exception as e:
            raise ValidationError("Failed to refund voucher")

    @classmethod
    def bulk_expire_vouchers(cls):
        """Bulk expire vouchers that have passed their expiry date"""
        try:
            with transaction.atomic():
                expired_vouchers = cls.objects.filter(
                    purchase_status='purchased',
                    expiry_date__lt=timezone.now(),
                    redeemed_at__isnull=True
                )
               
                count = expired_vouchers.update(
                    is_active=False,
                    purchase_status='expired',
                    redemption_notes=models.F('redemption_notes') + f" | Auto-expired on {timezone.now()}"
                )
               
                return count
               
        except DatabaseError as e:
            raise ValidationError("Failed to expire vouchers due to database error")
        except Exception as e:
            raise ValidationError("Failed to expire vouchers")

    def get_remaining_days(self):
        """Get remaining days until expiry"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now()
            return max(0, delta.days)
        return None

    def is_about_to_expire(self, days_threshold=7):
        """Check if voucher is about to expire"""
        remaining_days = self.get_remaining_days()
        return remaining_days is not None and remaining_days <= days_threshold

