from django.urls import include, path
from rest_framework import routers

from freelancing.voucher import api

router = routers.SimpleRouter()
router.register("v1/voucher", api.VoucherViewSet, basename="voucher")
router.register("v1/whatsapp-contacts", api.WhatsAppContactViewSet, basename="whatsapp-contacts")
router.register("v1/public/vouchers", api.PublicVoucherViewSet, basename="public-vouchers")
router.register("v1/purchase", api.VoucherPurchaseViewSet, basename="voucher-purchase")
router.register("v1/my-vouchers", api.UserVoucherViewSet, basename="user-vouchers")
router.register("v1/advertisements", api.AdvertisementViewSet, basename="advertisements")



app_name = "voucher"

urlpatterns = [
    # JWT Token Endpoints
    # path('v1/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path("", include(router.urls))
]
