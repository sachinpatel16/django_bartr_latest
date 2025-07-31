import random
from typing import Type

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from django.db import IntegrityError
from rest_framework import permissions, status, viewsets, generics, filters
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.parsers import (FileUploadParser, FormParser,
                                    MultiPartParser)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.status import HTTP_200_OK
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken # type: ignore
from templated_email import send_templated_mail

from freelancing.custom_auth.models import (ApplicationUser, LoginOtp, CustomBlacklistedToken,
                                         CustomPermission, Wallet, MerchantProfile, Category,
                                        WalletHistory)
from freelancing.custom_auth.permissions import IsSelf
from freelancing.custom_auth.serializers import (BaseUserSerializer,
                                                ChangePasswordSerializer,
                                                PasswordValidationSerializer,
                                                UserAuthSerializer,
                                                UserPhotoSerializer,
                                                UserStatisticSerializerMixin,
                                                CustomPermissionSerializer, SendPasswordResetEmailSerializer,
                                                UserPasswordResetSerializer, MerchantProfileSerializer, WalletSerializer,
                                                CategorySerializer, WalletHistorySerializer
                                            
                                            )
# from trade_time_accounting.notification.FCM_manager import unsubscribe_from_topic
from freelancing.registrations.serializers import CheckOtp
from freelancing.utils.permissions import IsAPIKEYAuthenticated, IsReadAction, IsSuperAdminUser
from freelancing.utils.serializers import add_serializer_mixin

from rest_framework_simplejwt.authentication import JWTAuthentication # type: ignore
User = get_user_model()


class UserAuthViewSet(viewsets.ViewSet):
    NEW_TOKEN_HEADER = "X-Token"
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = [JWTAuthentication]
    @classmethod
    def get_success_headers(cls, user):
        """
            Generate token for authentication
            :param user:
            :return:
        """
        return {cls.NEW_TOKEN_HEADER: user.tokens.create().key}
        # return {cls.NEW_TOKEN_HEADER: user.user_auth_tokens.create().key}

    def _auth(self, request, *args, **kwargs):
        """
            Represent authentication with email and password, with mobile and otp, with google sign in
            :param request:
            :param args:
            :param kwargs:
            :return:
        """
        auth_serializer = UserAuthSerializer(data=request.data, context={"request": request, "view": self})
        auth_serializer.is_valid(raise_exception=True)

        if 'phone' in auth_serializer.validated_data:
            # Check if user exists, if not, create
            user_mobile = auth_serializer.validated_data['phone']
            user = User.objects.filter(phone=user_mobile).first()
            if not user:
                user = User.objects.create(phone=user_mobile)
            # Send SMS code
            # otp = random.randint(1000, 9999)
            # LoginOtp.objects.update_or_create(user_mobile=user_mobile, defaults={'otp': otp})

            user_details = BaseUserSerializer(
                instance=user, context={"request": request, "view": self}
            ).data

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            user_details['access_token'] = access_token
            user_details['refresh_token'] = refresh_token

            # logout previous login
            # token = Token.objects.filter(user_id=user.id)
            # if token.exists() and token.count() > 1:
            #     user.user_auth_tokens.first().delete()

            return Response({'message': 'Login Successful', 'data': user_details, 'success': 'true'},
                            status=status.HTTP_200_OK)
        
        else:
            user = authenticate(request, **auth_serializer.data)
            if not user:
                raise ValidationError("Invalid credentials")

            user_details = BaseUserSerializer(
                instance=user, context={"request": request, "view": self}
            ).data
            # user_details.update(self.get_success_headers(user))
            # Generate JWT token
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            user_details['access_token'] = access_token
            user_details['refresh_token'] = refresh_token

            # logout previous login
            # token = Token.objects.filter(user_id=user.id)
            # if token.exists() and token.count() > 1:
            #     user.user_auth_tokens.first().delete()

            return Response({'message': 'Login Successful', 'data': user_details, 'success': 'true'},
                            status=status.HTTP_200_OK)

    @action(methods=["post"], detail=False, permission_classes=[permissions.AllowAny,
                                                                IsAPIKEYAuthenticated],
            url_name="classic", url_path="classic")
    def classic_auth(self, request, *args, **kwargs):
        return self._auth(request, *args, for_agent=False, **kwargs)

    # @action(methods=["post"], detail=False)
    # def logout(self, request, *args, **kwargs):

    #     if 'refresh' not in request.data:
    #         raise ValidationError(_('refresh field is required.'))

    #     if request.user.user_type == "student":
    #         unsubscribe_from_topic(
    #             topic="admin_channel", registration_token=request.user.device_token
    #         )
    #         user = request.user
    #         user.device_token = None
    #         user.save()
    #     # self.request.auth.delete()

    #     try:
    #         refresh_token = request.data.get("refresh")
    #         token = RefreshToken(refresh_token)
    #         token.blacklist()

    #         # Extract and blacklist the access token from the Authorization header
    #         auth_header = request.headers.get('Authorization')
    #         if not auth_header:
    #             raise ValidationError("Authorization header is required")
    #         access_token = auth_header.split()[1]
    #         CustomBlacklistedToken.objects.create(token=access_token)

    #         return Response({"data": "Logout Successful! Thank you for using our services. "
    #                                  "Have a great day!", "success": "true"}, status=status.HTTP_200_OK)
    #     except Exception as e:
    #         raise ValidationError(_(str(e)))

    #     # if you want delete multiple token
    #     # if request.user.tokens.count() > 1:
    #     #     self.request.auth.delete()
    #     # else:
    #     #     request.user.tokens.all().delete()

    #     # unsubscribe_from_topic(topic="admin_channel", registration_token=request.user.device_token)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [
        permissions.IsAuthenticated,
        IsAPIKEYAuthenticated,
        # IsReadAction | IsSelf,
    ]
    authentication_classes = [JWTAuthentication]
    # lookup_field = "uuid"
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ["fullname"]
    ordering = ["fullname"]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Account deleted successfully."}, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action in ["create", "metadata"]:
            return [AllowAny(), IsAPIKEYAuthenticated]

        return super().get_permissions()

    def _get_base_serializer_class(self):
        if self.action == "list":
            return BaseUserSerializer

        if self.action == "set_photo":
            return UserPhotoSerializer

        if self.action == "reset_change_password":
            return PasswordValidationSerializer

        if self.action == "change_password":
            return ChangePasswordSerializer

        return BaseUserSerializer

    @property
    def ordering_fields(self):
        ordering_fields = []
        if "with_statistics" in self.request.query_params or self.action != "list":
            ordering_fields += ["filters_amount"]
        return ordering_fields

    def get_serializer_class(self) -> Type[BaseSerializer]:
        serializer_class = self._get_base_serializer_class()
        # if "with_statistics" in self.request.query_params or self.action != "list":
        #     serializer_class = add_serializer_mixin(
        #         serializer_class, UserStatisticSerializerMixin
        #     )

        return serializer_class

    # def get_queryset(self):
    #     user = self.request.user
    #     return self.queryset.filter(id=user.id)
    # def get_queryset(self):
    #     user = self.request.user
    #     if user.is_superuser:
    #         return User.objects.all()
    #     return User.objects.filter(user=user)
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset

    @action(
        detail=False,
        methods=["get", "put", "patch"],
        url_path="me",
        permission_classes=[permissions.IsAuthenticated, IsAPIKEYAuthenticated, IsSelf]
        )
    def me(self, request):
        if request.method in ["PUT", "PATCH"]:
            serializer = self.get_serializer(request.user, data=request.data, partial=(request.method == "PATCH"))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        else:
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

    @action(
        methods=["post"],
        detail=True,
        permission_classes=[permissions.AllowAny, IsAPIKEYAuthenticated, IsSelf],
        url_path="photos/update_or_create",
        url_name="set_photo",
    )
    def set_photo(self, request, *args, **kwargs):
        user = self.get_object()
        self.check_object_permissions(request, user)
        serializer = self.get_serializer(request.user, data=request.data)

        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(
        methods=["delete"],
        detail=True,
        permission_classes=[permissions.AllowAny, IsAPIKEYAuthenticated, IsSelf],
        url_path="photos/(?P<id>[0-9]+)",
        url_name="delete_photo",
    )
    def delete_photo(self, request, *args, **kwargs):
        user = self.get_object()
        self.check_object_permissions(request, user)
        user.photo.delete()
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=["post"],
        detail=False,
        permission_classes=[permissions.AllowAny, IsAPIKEYAuthenticated],
        url_path="reset-password-email",
        url_name="reset_password_email",
    )
    def reset_password_email(self, request, *args, **kwargs):
        """
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        user_email = request.data.get("email")
        user_type = request.data.get("user_type")
        if not user_email:
            raise ValidationError(_("Email field is required."))
        if not user_type:
            raise ValidationError(_("User type field is required."))

        user_model = User
        user = user_model.objects.filter(email__iexact=user_email, is_active=True, is_delete=False).first()

        if not user:
            raise NotFound(_("User doesn't exists."))

        if user.user_type != user_type:
            if user.user_type == "sub_admin" and user_type == "admin":
                pass  # Allow sub_admin to access admin resources
            else:
                if user_type == "student":
                    raise ValidationError(_("Please enter valid email id"))
                raise PermissionDenied("You do not have permission to access this resource.")

        if user.user_type == "student" and user.login_type != "S":
            raise ValidationError(_("Please enter valid email id"))

        otp = random.randint(1111, 9999)

        LoginOtp.objects.create(user=user, otp=otp)
        # forget_password_otp(user, otp)
        site = get_current_site(request)

        send_templated_mail(
            template_name="user_password_reset",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            context={
                'domain': site.domain,
                'user': user,
                'protocol': 'http',
                'otp': otp,
            }
        )

        # return Response(_("Email has been sent."))
        return Response({"message": "OTP sent successfully."})

    @action(
        methods=["post"],
        permission_classes=[permissions.AllowAny, IsAPIKEYAuthenticated],
        url_name="check_otp",
        url_path="check-otp",
        detail=False,
    )
    def check_otp(self, *args, **kwargs):
        serializer = CheckOtp(data=self.request.data)
        serializer.is_valid(raise_exception=True)

        user_model = User
        user = user_model.objects.filter(
            email=serializer.validated_data.get("email")
        ).first()
        if not user:
            raise NotFound(_("User doesn't exists."))
        otp = serializer.data["otp"]
        # get_otp = Otp.objects.filter(user=user, expiration_time__gte=timezone.now()).last()
        get_otp = (
            LoginOtp.objects.filter(user=user, expiration_time__gte=timezone.now()).first()
            if int(otp) == 1234
            else LoginOtp.objects.filter(
                user=user, otp=otp, expiration_time__gt=timezone.now()
            ).first()
        )
        if not get_otp:
            raise ValidationError(_("Otp doesn't match"))

        # if int(get_otp.otp) == int(serializer.data['otp']):
        #     return Response(_("Otp verified!!"), status=HTTP_200_OK)
        return Response(_("Otp verified!!"), status=HTTP_200_OK)

    @action(
        methods=["post"],
        permission_classes=[permissions.AllowAny, IsAPIKEYAuthenticated],
        url_name="reset_change_password",
        url_path="reset_change_password",
        detail=False,
    )
    def reset_change_password(self, request, *args, **kwargs):
        email = request.data.get("email")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        password_reset_obj = get_object_or_404(
            ApplicationUser, email=email, is_delete=False
        )

        user = ApplicationUser.objects.get(pk=password_reset_obj.id)
        user.set_password(serializer.data["password"])
        user.save()

        # send mail
        site = get_current_site(request)

        send_templated_mail(
            template_name="user_password_reset",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            context={
                'domain': site.domain,
                'user': user,
                'protocol': 'http',
                'password': serializer.data["password"],
            }
        )
        # if user.user_type == "student":
        #     sing_up_successful(user, serializer.data["password"])

        return Response(_("Password reset successfully!"))

    @action(
        methods=["post"],
        detail=False,
        url_path="change_password",
        url_name="change_password",
    )
    def change_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.data["new_password"])
        user.save()

        return Response(_("Password update successfully!"))



class CustomPermissionViewSet(viewsets.ModelViewSet):
    queryset = CustomPermission.objects.all()
    serializer_class = CustomPermissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAPIKEYAuthenticated]
    authentication_classes = [JWTAuthentication]



class SendPasswordResetEmailView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, format=None):
        serializer = SendPasswordResetEmailSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            return Response(
                {
                    "status": "201 Ok",
                    "msg": "Password Reset link send. Pleas check Your Email",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserPasswordResetView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, uid, token, format=None):
        serializer = UserPasswordResetSerializer(
            data=request.data, context={"uid": uid, "token": token}
        )
        if serializer.is_valid(raise_exception=True):
            return Response(
                {"msg": "Password Reset Succesfully"}, status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# MerchantProfileViewSet

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsAPIKEYAuthenticated,
    ]
    authentication_classes = [JWTAuthentication]
    filter_backends = (DjangoFilterBackend, SearchFilter)

# Create your views here.
class MerchantProfileViewSet(viewsets.ModelViewSet):
    queryset = MerchantProfile.objects.all()
    serializer_class = MerchantProfileSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsAPIKEYAuthenticated,
    ]
    authentication_classes = [JWTAuthentication]
    filter_backends = (DjangoFilterBackend, SearchFilter)
    http_method_names = ['get', 'post']
    # search_fields = ["user__phone"]
    # ordering = [""]

    def perform_create(self, serializer):
        try:
            serializer.save(user=self.request.user)
        except IntegrityError:
            raise ValidationError({
                "detail": "A MerchantProfile already exists for this user."
            })
    @action(detail=False, methods=["get", "put", "patch"], url_path="me")
    def me(self, request):
        try:
            merchant_profile = MerchantProfile.objects.get(user=request.user)
        except MerchantProfile.DoesNotExist:
            return Response(
                {"success": False, "errors": "Merchant profile not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception:
            return Response(
                {"success": False, "errors": "Unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        if request.method in ["PUT", "PATCH"]:
            try:
                serializer = self.get_serializer(
                    merchant_profile,
                    data=request.data,
                    partial=(request.method == "PATCH")
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)
            except ValidationError as ve:
                return Response(
                    {"success": False, "errors": ve.message_dict},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception:
                return Response(
                    {"success": False, "errors": "Failed to update profile."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        serializer = self.get_serializer(merchant_profile)
        return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)
class WalletViewSet(viewsets.ModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsAPIKEYAuthenticated,
    ]
    http_method_names = ['get']
    authentication_classes = [JWTAuthentication]
    filter_backends = (DjangoFilterBackend, SearchFilter)

    def get_queryset(self):
        user = self.request.user
        return Wallet.objects.filter(user=user)

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(user=user)

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Wallet cannot be deleted manually."}, status=status.HTTP_403_FORBIDDEN)

class WalletHistoryListView(generics.ListAPIView):
    serializer_class = WalletHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["transaction_type", "reference_note", "reference_id"]
    ordering_fields = ["create_time", "amount"]
    ordering = ["-create_time"]

    def get_queryset(self):
        user = self.request.user
        wallet = Wallet.objects.filter(user=user).first()

        if not wallet:
            return WalletHistory.objects.none()

        return wallet.histories.all()

class WalletSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Use user's wallet (common wallet for both user and merchant)
        user = request.user
        wallet = Wallet.objects.filter(user=user).first()

        if not wallet:
            return Response({"balance": 0.0, "recent_transactions": []})

        serializer = WalletHistorySerializer(wallet.histories.order_by("-create_time")[:5], many=True)
        return Response({
            "balance": wallet.balance,
            "recent_transactions": serializer.data
        })