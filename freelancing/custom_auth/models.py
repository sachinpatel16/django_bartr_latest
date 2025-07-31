import uuid as uuid
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from django.core.exceptions import ValidationError
from model_utils import Choices
from phonenumber_field.modelfields import PhoneNumberField
from rest_framework.authtoken.models import Token
# from tinymce.models import HTMLField

from freelancing.custom_auth.managers import ApplicationUserManager
from freelancing.custom_auth.mixins import UserPhotoMixin

from freelancing.utils.utils import set_otp_expiration_time, set_otp_reset_expiration_time


class MultiToken(Token):
    user = models.ForeignKey(  # changed from OneToOne to ForeignKey
        settings.AUTH_USER_MODEL,
        related_name="tokens",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )


class CustomBlacklistedToken(models.Model):
    """
        Represent block access token of JWT
    """
    token = models.CharField(max_length=256, unique=True)
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.token


# Create your models here.
class BaseModel(models.Model):
    """This model is used for every model in same fields"""

    is_active = models.BooleanField(default=True)
    is_delete = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ApplicationUser(AbstractBaseUser, UserPhotoMixin, PermissionsMixin):
    GENDER_TYPES = Choices(
        ("male", "Male"),
        ("female", "Female"),
        ("others", "Others"),
    )

    # uuid = universal unique identification
    username_validator = UnicodeUsernameValidator()
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

    username = models.CharField(
        _("username"),
        max_length=150,
        # unique=True,
        blank=True,
        null=False,  
        default="",
        help_text=(
            "Required. 150 characters or fewer. Lettres , digits and @/./+/-/ only ."
        ),
        validators=[username_validator],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )

    email = models.EmailField(
        _("email address"),
        null=True,
        blank=True,
        unique=True,
        error_messages={"unique": _("A user with that email already exists.")},
    )

    is_email_verified = models.BooleanField(
        _("email verified"),
        default=False,
    )

    first_name = models.CharField(
        _("first name"),
        max_length=30,
        blank=True,
    )

    last_name = models.CharField(
        _("last name"),
        max_length=150,
        blank=True,
    )
    fullname = models.CharField(
        _("full name"),
        max_length=300,
        blank=True,
        help_text=_("Full name as it was returned by social provider"),
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )

    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether the user should be treated as active."
            "Unselect this instead of deleting account."
        ),
    )

    is_delete = models.BooleanField(
        _("delete"),
        default=False,
        help_text=_("Designates whether this user has been deleted."),
    )

    readable_password = models.CharField(max_length=128, null=True, blank=True)
    date_joined = models.DateTimeField(_("Registered date"), default=timezone.now)
    last_modified = models.DateTimeField(_("last modified"), auto_now=True)
    last_user_activity = models.DateTimeField(_("last activity"), default=timezone.now)
    phone = PhoneNumberField(
        _("Mobile Number"),
        null=True,
        blank=True,
        unique=True,
        error_messages={"unique": _("A user with that phone already exists.")},
    )
    is_phone_verified = models.BooleanField(
        _("phone verified"),
        default=False,
    )
    gender = models.CharField(
        max_length=10, choices=GENDER_TYPES, null=True, blank=True
    )

    is_merchant = models.BooleanField(
        _('Is Merchant'),
        default=False,
        help_text=_('Designates whether the user is a merchant.'),
    )

    merchant_id = models.PositiveIntegerField(
        _('Merchant ID'),
        null=True,
        blank=True,
        help_text=_('Stores related MerchantProfile ID.')
    )

    address = models.TextField(_("Address"), null=True, blank=True)
    area = models.CharField(_("Area"), max_length=256, null=True, blank=True)
    pin = models.CharField(_("PIN Code"), max_length=10, null=True, blank=True)
    city = models.CharField(_("City"), max_length=100, null=True, blank=True)
    state = models.CharField(_("State"), max_length=100, null=True, blank=True)

    # address = models.TextField(_("Address"), null=True, blank=True)
    # partnership = models.BooleanField(default=False)
    # percentage = models.PositiveIntegerField(default=0)
    # assign_user_roll = models.ForeignKey("master.RollMaster", on_delete=models.PROTECT,
    #                                      related_name="user_roll_master_details", null=True, blank=True)

    # device address
    device_type = models.CharField(
        _("Device Type"), max_length=1, null=True, blank=True
    )
    device_token = models.CharField(
        _("Device Token"), max_length=256, null=True, blank=True
    )
    # device_id = models.CharField(_("Device Id"), max_length=256, null=True, blank=True)
    # os_version = models.CharField(_("OS Version"), max_length=8, null=True, blank=True)
    # device_name = models.CharField(
    #     _("Device Name"), max_length=64, null=True, blank=True
    # )
    # model_name = models.CharField(_("Model Name"), max_length=64, null=True, blank=True)
    # ip_address = models.CharField(_("IP Address"), max_length=32, null=True, blank=True)

    objects = ApplicationUserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"  # email
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.email or self.first_name or self.last_name or str(self.uuid)

    def save(self, *args, **kwargs):
        if self.photo and (not self.width_photo or not self.height_photo):
            self.width_photo = self.photo.width
            self.height_photo = self.photo.height

        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email)


        if self.fullname:
            self.assign_first_last_name_to_the_object()
        super(ApplicationUser, self).save(*args, **kwargs)

    def assign_first_last_name_to_the_object(self):
        if not self.fullname or not self.fullname.strip():
            return
            
        fullname_parts = self.fullname.strip().split(" ")
        # Filter out empty strings that might result from multiple spaces
        fullname_parts = [part for part in fullname_parts if part]
        
        if not fullname_parts:
            return
            
        self.first_name = fullname_parts[0]
        if len(fullname_parts) > 1:
            self.last_name = fullname_parts[1]
        else:
            self.last_name = fullname_parts[0]

    def update_last_activity(self):
        now = timezone.now()

        self.last_user_activity = now
        self.save(update_fields=("last_user_activity", "last_modified"))
    
    def clean(self):
        super().clean()
        if self.username is None:
            self.username = None  # ensure it's explicitly set

class Category(BaseModel):
    name = models.CharField(_("Category Name"), max_length=100, unique=True)
    description = models.TextField(_("Description"), blank=True, null=True)

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
        ordering = ['name']

    def __str__(self):
        return self.name
    
class MerchantProfile(BaseModel):
    user = models.OneToOneField(ApplicationUser, on_delete=models.CASCADE, related_name='merchant_profile')
    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='merchants'
    )
    
    business_name = models.CharField(max_length=255)
    email = models.EmailField(_("Merchant Email"), null=True, blank=True)
    phone = PhoneNumberField(_("Merchant Phone"), null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[("male", "Male"), ("female", "Female"), ("others", "Others")], null=True, blank=True)
    
    gst_number = models.CharField(max_length=20, null=True, blank=True)
    fssai_number = models.CharField(max_length=20, null=True, blank=True)
    
    address = models.TextField(_("Address"), null=True, blank=True)
    area = models.CharField(_("Area"), max_length=256, null=True, blank=True)
    pin = models.CharField(_("PIN Code"), max_length=10, null=True, blank=True)
    city = models.CharField(_("City"), max_length=100, null=True, blank=True)
    state = models.CharField(_("State"), max_length=100, null=True, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    logo = models.ImageField(upload_to="merchant/logo/", null=True, blank=True)
    banner_image = models.ImageField(upload_to="merchant/banner/", null=True, blank=True)
    def __str__(self):
        return f"{self.business_name} ({self.user.email})"


class Wallet(BaseModel):
    user = models.OneToOneField(ApplicationUser, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        if self.user:
            return f"Wallet of {self.user.fullname} - ₹{self.balance}"
        else:
            return f"Orphaned Wallet - ₹{self.balance}"

    def deduct(self, amount: Decimal, note=None, ref_id=None):
        if self.balance < amount:
            raise ValidationError("Insufficient balance in wallet.")
        self.balance -= amount
        self.save()
        WalletHistory.objects.create(
            wallet=self,
            amount=-amount,
            transaction_type='debit',
            reference_note=note,
            reference_id=ref_id
        )

    def credit(self, amount: Decimal, note=None, ref_id=None):
        self.balance += amount
        self.save()
        WalletHistory.objects.create(
            wallet=self,
            amount=amount,
            transaction_type='credit',
            reference_note=note,
            reference_id=ref_id
        )
class WalletHistory(BaseModel):
    TRANSACTION_CHOICES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='histories')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference_note = models.CharField(max_length=255, null=True, blank=True)
    reference_id = models.CharField(max_length=100, null=True, blank=True)  # e.g. Voucher ID or Order ID
    meta = models.JSONField(null=True, blank=True) 
    def __str__(self):
        return f"{self.transaction_type.title()} ₹{self.amount}"

class LoginOtp(BaseModel):
    """
        Represent check otp when you will login with phone number
    """
    user_mobile = PhoneNumberField()
    otp = models.IntegerField()
    expiration_time = models.DateTimeField(default=set_otp_reset_expiration_time)

    def save(self, *args, **kwargs):
        if not self.expiration_time:
            self.expiration_time = set_otp_expiration_time()
        return super().save()


class StudentOTP(BaseModel):
    email = models.EmailField(_("email"))
    otp = models.PositiveIntegerField(_("OTP"), null=True, blank=True)
    expiration_time = models.DateTimeField(default=set_otp_expiration_time)
    is_verified = models.BooleanField(default=0)

    def save(self, *args, **kwargs):
        self.expiration_time = set_otp_expiration_time()
        return super().save()


class UserActivity(models.Model):
    """
        It stores information about user activity
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(auto_now=True)


class CustomPermission(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    is_read_access = models.BooleanField(_("Read Access"), default=False)
    is_create_access = models.BooleanField(_("Create Access"), default=False)
    is_update_access = models.BooleanField(_("Update Access"), default=False)
    is_delete_access = models.BooleanField(_("Delete Access"), default=False)
    is_printed_access = models.BooleanField(_("Printed Access"), default=False)

    def __str__(self):
        return self.name


class SiteSetting(BaseModel):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.key}: {self.value}"

    @staticmethod
    def get_value(key, default=None):
        try:
            return SiteSetting.objects.get(key=key).value
        except SiteSetting.DoesNotExist:
            return default
