from django.contrib import admin

# Register your models here.

from freelancing.voucher.models import Voucher, VoucherType 

admin.site.register(Voucher)
admin.site.register(VoucherType)