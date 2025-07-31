from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from freelancing.utils.permissions import IsAPIKEYAuthenticated
from django.db import transaction
import json
import requests
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.db import IntegrityError, DatabaseError
from decimal import Decimal, InvalidOperation

from freelancing.voucher.models import Voucher, WhatsAppContact, Advertisement, UserVoucherRedemption, VoucherType
from freelancing.voucher.serializers import (
    VoucherCreateSerializer, WhatsAppContactSerializer, GiftCardShareSerializer, 
    AdvertisementSerializer, VoucherListSerializer, VoucherPurchaseSerializer,
    UserVoucherSerializer, VoucherRedeemSerializer, VoucherTypeSerializer,
    VoucherCancelSerializer, VoucherRefundSerializer, PurchaseHistorySerializer
)
from freelancing.custom_auth.models import Wallet, SiteSetting
from rest_framework.filters import SearchFilter

class VoucherViewSet(viewsets.ModelViewSet):
    queryset = Voucher.objects.all()
    serializer_class = VoucherCreateSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsAPIKEYAuthenticated,
    ]
    authentication_classes = [JWTAuthentication]
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ["title", "message", "merchant__business_name"]
    ordering = ["-create_time"]
    filterset_fields = ["voucher_type", "is_gift_card", "category"]

    def get_queryset(self):
        # Only show merchant's own vouchers
        return Voucher.objects.filter(merchant__user=self.request.user)

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"], url_path="redeem", permission_classes=[permissions.AllowAny,
                                                                IsAPIKEYAuthenticated])
    def redeem_voucher(self, request, pk=None):
        """Redeem a voucher - increases redemption count"""
        try:
            voucher = self.get_object()
           
            with transaction.atomic():
                # Check if voucher has a limit and if it's been reached
                if voucher.count and voucher.redemption_count >= voucher.count:
                    return Response(
                        {"error": "Voucher redemption limit reached"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
               
                # Increment redemption count
                voucher.redemption_count += 1
                voucher.save(update_fields=['redemption_count'])
               
                return Response({
                    "message": "Voucher redeemed successfully",
                    "redemption_count": voucher.redemption_count,
                    "remaining": voucher.count - voucher.redemption_count if voucher.count else None
                })
               
        except Voucher.DoesNotExist:
            return Response(
                {"error": "Voucher not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": "Failed to redeem voucher"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"], url_path="share-gift-card", permission_classes=[permissions.AllowAny,
                                                                IsAPIKEYAuthenticated])
    def share_gift_card(self, request, pk=None):
        """Share gift card via WhatsApp"""
        try:
            voucher = self.get_object()
           
            # Check if it's a gift card
            if not voucher.is_gift_card:
                return Response(
                    {"error": "Only gift cards can be shared"},
                    status=status.HTTP_400_BAD_REQUEST
                )
           
            serializer = GiftCardShareSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
           
            phone_numbers = serializer.validated_data.get('phone_numbers', [])
           
            # Get user's WhatsApp contacts
            user_contacts = WhatsAppContact.objects.filter(
                user=request.user,
                phone_number__in=phone_numbers,
                is_on_whatsapp=True
            )
           
            if not user_contacts.exists():
                return Response(
                    {"error": "No valid WhatsApp contacts found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
           
            # Send gift card via WhatsApp API
            success_count = 0
            failed_numbers = []
           
            for contact in user_contacts:
                try:
                    # WhatsApp API call (you'll need to implement this based on your WhatsApp provider)
                    success = self.send_whatsapp_gift_card(contact.phone_number, voucher)
                    if success:
                        success_count += 1
                    else:
                        failed_numbers.append(contact.phone_number)
                except Exception as e:
                    failed_numbers.append(contact.phone_number)
           
            return Response({
                "message": f"Gift card shared successfully to {success_count} contacts",
                "success_count": success_count,
                "failed_numbers": failed_numbers
            })
           
        except Exception as e:
            return Response(
                {"error": "Failed to share gift card"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def send_whatsapp_gift_card(self, phone_number, voucher):
        """Send gift card via WhatsApp API"""
        try:
            # Implement your WhatsApp API integration here
            # This is a placeholder implementation
            return True
        except Exception:
            return False

    def get_voucher_value(self, voucher):
        """Get voucher value based on type"""
        if voucher.voucher_type.name == 'percentage':
            return f"{voucher.percentage_value}% off"
        elif voucher.voucher_type.name == 'flat':
            return f"₹{voucher.flat_amount} off"
        elif voucher.voucher_type.name == 'product':
            return f"Free {voucher.product_name}"
        return "Special offer"

    @action(detail=False, methods=["get"], url_path="popular", permission_classes=[permissions.AllowAny,
                                                                IsAPIKEYAuthenticated])
    def popular_vouchers(self, request):
        try:
            # Fixed: Use redemption_count instead of count for filtering
            top_vouchers = Voucher.objects.filter(
                redemption_count__gt=0,
                is_gift_card=False  # Exclude gift cards from public listing
            ).order_by("-redemption_count")[:10]
           
            data = [{
                "id": v.id,
                "title": v.title,
                "merchant": v.merchant.business_name,
                "redemption_count": v.redemption_count,
                "voucher_type": v.voucher_type.name
            } for v in top_vouchers]
           
            return Response(data)
        except Exception as e:
            return Response(
                {"error": "Failed to fetch popular vouchers"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PublicVoucherViewSet(viewsets.ReadOnlyModelViewSet):
    """Public API for users to browse and purchase vouchers"""
    queryset = Voucher.objects.filter(is_active=True, is_gift_card=False)
    serializer_class = VoucherListSerializer
    permission_classes = [permissions.IsAuthenticated, IsAPIKEYAuthenticated]
    authentication_classes = [JWTAuthentication]
    filter_backends = (DjangoFilterBackend, SearchFilter)
    search_fields = ["title", "message", "merchant__business_name"]
    filterset_fields = ["voucher_type", "category", "merchant"]
    ordering = ["-create_time"]

    def get_queryset(self):
        """Filter vouchers based on availability and user preferences"""
        queryset = super().get_queryset()
        
        # Filter by category if provided
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by merchant if provided
        merchant_id = self.request.query_params.get('merchant')
        if merchant_id:
            queryset = queryset.filter(merchant_id=merchant_id)
        
        # Filter by voucher type if provided
        voucher_type = self.request.query_params.get('voucher_type')
        if voucher_type:
            queryset = queryset.filter(voucher_type__name=voucher_type)
        
        # Filter by price range if provided
        min_cost = self.request.query_params.get('min_cost')
        max_cost = self.request.query_params.get('max_cost')
        
        if min_cost or max_cost:
            # This would require additional logic to filter by purchase cost
            # For now, we'll return all vouchers
            pass
        
        return queryset

    @action(detail=False, methods=["get"], url_path="categories")
    def voucher_categories(self, request):
        """Get all voucher categories"""
        categories = VoucherType.objects.filter(is_active=True)
        serializer = VoucherTypeSerializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="featured")
    def featured_vouchers(self, request):
        """Get featured vouchers (most popular)"""
        featured = self.get_queryset().filter(
            redemption_count__gt=0
        ).order_by('-redemption_count')[:10]
        serializer = self.get_serializer(featured, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="nearby")
    def nearby_vouchers(self, request):
        """Get vouchers from nearby merchants"""
        # This would require location-based filtering
        # For now, return recent vouchers
        nearby = self.get_queryset().order_by('-create_time')[:20]
        serializer = self.get_serializer(nearby, many=True)
        return Response(serializer.data)

class VoucherPurchaseViewSet(viewsets.ViewSet):
    """Handle voucher purchases with optimized transaction management"""
    permission_classes = [permissions.IsAuthenticated, IsAPIKEYAuthenticated]
    authentication_classes = [JWTAuthentication]

    @action(detail=False, methods=["post"], url_path="purchase", permission_classes=[permissions.AllowAny,
                                                                IsAPIKEYAuthenticated])
    def purchase_voucher(self, request):
        """Purchase a voucher using wallet points with atomic transaction"""
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required. Please provide a valid JWT token."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = VoucherPurchaseSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        voucher_id = serializer.validated_data['voucher_id']
        user = request.user
        
        try:
            # Use atomic transaction for all database operations
            with transaction.atomic():
                # 1. Get voucher with select_for_update to prevent race conditions
                try:
                    voucher = Voucher.objects.select_for_update().get(
                        id=voucher_id, 
                        is_active=True
                    )
                except Voucher.DoesNotExist:
                    raise ValidationError("Voucher not found or inactive")
                
                # 2. Check if user already purchased this voucher
                if UserVoucherRedemption.objects.filter(
                    user=user, 
                    voucher=voucher
                ).exists():
                    raise ValidationError("You have already purchased this voucher")
                
                # 3. Check voucher availability
                if voucher.count and voucher.redemption_count >= voucher.count:
                    raise ValidationError("Voucher is out of stock")

                # 4. Get user wallet with select_for_update
                try:
                    wallet = Wallet.objects.select_for_update().get(user=user)
                except Wallet.DoesNotExist:
                    raise ValidationError("User wallet not found")
                
                # 5. Calculate cost with proper decimal handling
                try:
                    # Get voucher cost from settings, with better error handling
                    voucher_cost_setting = SiteSetting.get_value("voucher_cost", "10")
                    cost = Decimal(str(voucher_cost_setting))
                    if cost <= 0:
                        raise ValidationError("Invalid voucher cost")
                except (InvalidOperation, ValueError, TypeError):
                    # If there's any issue with the setting, use default value
                    cost = Decimal("10")
                    if cost <= 0:
                        raise ValidationError("Invalid voucher cost")
                
                # 6. Validate sufficient balance
                if wallet.balance < cost:
                    raise ValidationError(
                        f"Insufficient balance. Required: ₹{cost}, Available: ₹{wallet.balance}"
                    ) 
                
                # 7. Generate unique transaction ID
                transaction_id = f"WT-{wallet.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"

                # 8. Deduct from wallet with error handling
                try:
                    wallet.deduct(cost, note=f"Voucher Purchase: {voucher.title}", ref_id=str(voucher.id))
                except ValidationError as e:
                    raise ValidationError(f"Wallet deduction failed: {str(e)}")
                # 9. Create redemption record
                try:
                    redemption = UserVoucherRedemption.objects.create(
                        user=user,
                        voucher=voucher,
                        purchase_cost=cost,
                        is_active=True,
                        wallet_transaction_id=transaction_id
                    )
                except IntegrityError:
                    raise ValidationError("Failed to create purchase record")

                return Response({
                    "message": "Voucher purchased successfully",
                    "voucher_id": voucher.id,
                    "voucher_title": voucher.title,
                    "purchase_cost": float(cost),
                    "remaining_balance": float(wallet.balance),
                    "redemption_id": redemption.id,
                    "purchase_reference": redemption.purchase_reference,
                    "expiry_date": redemption.expiry_date,
                    "transaction_id": transaction_id
                }, status=status.HTTP_201_CREATED)
                
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            return Response(
                {"error": "Database error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"], url_path="redeem")
    def redeem_purchased_voucher(self, request):
        """Redeem a purchased voucher with atomic transaction"""
        serializer = VoucherRedeemSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        redemption_id = serializer.validated_data['redemption_id']
        location = serializer.validated_data.get('location', '')
        notes = serializer.validated_data.get('notes', '')
        user = request.user
        
        try:
            with transaction.atomic():
                # 1. Get redemption record with select_for_update
                try:
                    redemption = UserVoucherRedemption.objects.select_for_update().get(
                        id=redemption_id,
                        user=user
                    )
                except UserVoucherRedemption.DoesNotExist:
                    raise ValidationError("Voucher not found or not purchased")
                
                # 2. Validate redemption eligibility
                if not redemption.can_redeem():
                    if redemption.is_expired():
                        raise ValidationError("Voucher has expired")
                    elif redemption.redeemed_at:
                        raise ValidationError("Voucher has already been redeemed")
                    else:
                        raise ValidationError("Voucher cannot be redeemed")
                
                # 3. Redeem the voucher
                try:
                    redemption.redeem(location=location, notes=notes)
                except ValidationError as e:
                    raise ValidationError(f"Redemption failed: {str(e)}")
                
                return Response({
                    "message": "Voucher redeemed successfully",
                    "voucher_title": redemption.voucher.title,
                    "redeemed_at": redemption.redeemed_at,
                    "redemption_location": redemption.redemption_location,
                    "purchase_reference": redemption.purchase_reference,
                    "transaction_id": redemption.wallet_transaction_id
                })
                
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            return Response(
                {"error": "Database error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"], url_path="cancel")
    def cancel_purchase(self, request):
        """Cancel a voucher purchase with atomic transaction"""
        serializer = VoucherCancelSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        redemption_id = serializer.validated_data['redemption_id']
        reason = serializer.validated_data.get('reason', '')
        user = request.user
        
        try:
            with transaction.atomic():
                # 1. Get redemption record with select_for_update
                try:
                    redemption = UserVoucherRedemption.objects.select_for_update().get(
                        id=redemption_id,
                        user=user
                    )
                except UserVoucherRedemption.DoesNotExist:
                    raise ValidationError("Voucher not found")
                
                # 2. Validate cancellation eligibility
                if redemption.redeemed_at:
                    raise ValidationError("Cannot cancel redeemed voucher")
                if redemption.purchase_status in ['cancelled', 'refunded']:
                    raise ValidationError("Voucher is already cancelled or refunded")
                
                # 3. Cancel the purchase
                try:
                    redemption.cancel_purchase(reason=reason)
                except ValidationError as e:
                    raise ValidationError(f"Cancellation failed: {str(e)}")
                
                return Response({
                    "message": "Voucher purchase cancelled successfully",
                    "voucher_title": redemption.voucher.title,
                    "purchase_reference": redemption.purchase_reference,
                    "purchase_status": redemption.purchase_status,
                    "transaction_id": redemption.wallet_transaction_id
                })
                
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            return Response(
                {"error": "Database error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["post"], url_path="refund")
    def refund_purchase(self, request):
        """Refund a voucher purchase with atomic transaction"""
        serializer = VoucherRefundSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        redemption_id = serializer.validated_data['redemption_id']
        reason = serializer.validated_data.get('reason', '')
        user = request.user
        
        try:
            with transaction.atomic():
                # 1. Get redemption record with select_for_update
                try:
                    redemption = UserVoucherRedemption.objects.select_for_update().get(
                        id=redemption_id,
                        user=user
                    )
                except UserVoucherRedemption.DoesNotExist:
                    raise ValidationError("Voucher not found")
                
                # 2. Validate refund eligibility
                if redemption.redeemed_at:
                    raise ValidationError("Cannot refund redeemed voucher")
                if redemption.purchase_status in ['cancelled', 'refunded']:
                    raise ValidationError("Voucher is already cancelled or refunded")
                
                # 3. Get user wallet with select_for_update
                try:
                    wallet = Wallet.objects.select_for_update().get(user=user)
                except Wallet.DoesNotExist:
                    raise ValidationError("User wallet not found for refund")
                
                # 4. Refund the purchase
                try:
                    redemption.refund_purchase(reason=reason)
                except ValidationError as e:
                    raise ValidationError(f"Refund failed: {str(e)}")
                
                return Response({
                    "message": "Voucher purchase refunded successfully",
                    "voucher_title": redemption.voucher.title,
                    "purchase_reference": redemption.purchase_reference,
                    "refund_amount": float(redemption.purchase_cost),
                    "remaining_balance": float(wallet.balance),
                    "purchase_status": redemption.purchase_status,
                    "transaction_id": redemption.wallet_transaction_id
                })
                
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except DatabaseError as e:
            return Response(
                {"error": "Database error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": "An unexpected error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserVoucherViewSet(viewsets.ReadOnlyModelViewSet):
    """Manage user's purchased vouchers"""
    serializer_class = UserVoucherSerializer
    permission_classes = [permissions.IsAuthenticated, IsAPIKEYAuthenticated]
    authentication_classes = [JWTAuthentication]
    filter_backends = (DjangoFilterBackend,)
    filterset_fields = ["purchase_status", "is_gift_voucher"]
    ordering = ["-purchased_at"]

    def get_queryset(self):
        """Get user's purchased vouchers"""
        return UserVoucherRedemption.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="active")
    def active_vouchers(self, request):
        """Get user's active (unredeemed) vouchers"""
        active_vouchers = self.get_queryset().filter(
            purchase_status='purchased',
            redeemed_at__isnull=True
        ).exclude(expiry_date__lt=timezone.now())
        serializer = self.get_serializer(active_vouchers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="redeemed")
    def redeemed_vouchers(self, request):
        """Get user's redeemed vouchers"""
        redeemed_vouchers = self.get_queryset().filter(
            purchase_status='redeemed'
        )
        serializer = self.get_serializer(redeemed_vouchers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="expired")
    def expired_vouchers(self, request):
        """Get user's expired vouchers"""
        expired_vouchers = self.get_queryset().filter(
            purchase_status='purchased',
            expiry_date__lt=timezone.now()
        )
        serializer = self.get_serializer(expired_vouchers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="cancelled")
    def cancelled_vouchers(self, request):
        """Get user's cancelled vouchers"""
        cancelled_vouchers = self.get_queryset().filter(
            purchase_status='cancelled'
        )
        serializer = self.get_serializer(cancelled_vouchers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="refunded")
    def refunded_vouchers(self, request):
        """Get user's refunded vouchers"""
        refunded_vouchers = self.get_queryset().filter(
            purchase_status='refunded'
        )
        serializer = self.get_serializer(refunded_vouchers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="gift-cards")
    def gift_cards(self, request):
        """Get user's gift cards"""
        gift_cards = self.get_queryset().filter(
            is_gift_voucher=True
        )
        serializer = self.get_serializer(gift_cards, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="history")
    def purchase_history(self, request):
        """Get detailed purchase history"""
        history = self.get_queryset()
        
        # Apply filters if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            history = history.filter(purchase_status=status_filter)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            history = history.filter(purchased_at__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            history = history.filter(purchased_at__lte=date_to)
        
        serializer = PurchaseHistorySerializer(history, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="summary")
    def purchase_summary(self, request):
        """Get purchase summary statistics"""
        user_vouchers = self.get_queryset()
        
        summary = {
            "total_purchases": user_vouchers.count(),
            "total_spent": sum(v.purchase_cost for v in user_vouchers),
            "active_vouchers": user_vouchers.filter(
                purchase_status='purchased',
                redeemed_at__isnull=True
            ).exclude(expiry_date__lt=timezone.now()).count(),
            "redeemed_vouchers": user_vouchers.filter(purchase_status='redeemed').count(),
            "expired_vouchers": user_vouchers.filter(
                purchase_status='purchased',
                expiry_date__lt=timezone.now()
            ).count(),
            "cancelled_vouchers": user_vouchers.filter(purchase_status='cancelled').count(),
            "refunded_vouchers": user_vouchers.filter(purchase_status='refunded').count(),
            "total_refunds": sum(v.purchase_cost for v in user_vouchers.filter(purchase_status='refunded')),
            "gift_cards": user_vouchers.filter(is_gift_voucher=True).count()
        }
        
        return Response(summary)


class WhatsAppContactViewSet(viewsets.ModelViewSet):
    """Manage WhatsApp contacts for gift card sharing"""
    queryset = WhatsAppContact.objects.all()
    serializer_class = WhatsAppContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WhatsAppContact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["post"], url_path="sync-contacts")
    def sync_contacts(self, request):
        """Sync user's phone contacts and check WhatsApp status"""
        try:
            contacts_data = request.data.get('contacts', [])
           
            if not contacts_data:
                return Response(
                    {"error": "No contacts provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )
           
            # Clear existing contacts for this user
            WhatsAppContact.objects.filter(user=request.user).delete()
           
            # Create new contacts
            created_contacts = []
            for contact in contacts_data:
                name = contact.get('name', '')
                phone_number = contact.get('phone_number', '')
               
                if phone_number:
                    # Check if contact is on WhatsApp (implement your WhatsApp API check here)
                    is_on_whatsapp = self.check_whatsapp_status(phone_number)
                   
                    contact_obj = WhatsAppContact.objects.create(
                        user=request.user,
                        name=name,
                        phone_number=phone_number,
                        is_on_whatsapp=is_on_whatsapp
                    )
                    created_contacts.append(contact_obj)
           
            # Return only WhatsApp contacts
            whatsapp_contacts = WhatsAppContact.objects.filter(
                user=request.user,
                is_on_whatsapp=True
            )
           
            serializer = self.get_serializer(whatsapp_contacts, many=True)
           
            return Response({
                "message": f"Synced {len(created_contacts)} contacts, {len(whatsapp_contacts)} on WhatsApp",
                "whatsapp_contacts": serializer.data
            })
           
        except Exception as e:
            return Response(
                {"error": "Failed to sync contacts"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def check_whatsapp_status(self, phone_number):
        """Check if a phone number is registered on WhatsApp"""
        # This is a placeholder - implement based on your WhatsApp provider
        # Example: Use WhatsApp Business API to check number status
       
        try:
            # api_url = "https://your-whatsapp-api.com/check"
            # payload = {"phone": phone_number}
            # response = requests.post(api_url, json=payload)
            # return response.json().get('is_whatsapp', False)
           
            # For now, return True as placeholder (you should implement actual check)
            return True
        except Exception:
            return False

    @action(detail=False, methods=["get"], url_path="whatsapp-contacts")
    def whatsapp_contacts(self, request):
        """Get only WhatsApp contacts"""
        try:
            whatsapp_contacts = WhatsAppContact.objects.filter(
                user=request.user,
                is_on_whatsapp=True
            ).order_by('name')
           
            serializer = self.get_serializer(whatsapp_contacts, many=True)
            return Response(serializer.data)
           
        except Exception as e:
            return Response(
                {"error": "Failed to fetch WhatsApp contacts"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdvertisementViewSet(viewsets.ModelViewSet):
    """Manage voucher advertisements"""
    queryset = Advertisement.objects.all()
    serializer_class = AdvertisementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show advertisements for user's vouchers
        return Advertisement.objects.filter(voucher__merchant__user=self.request.user)

    def perform_create(self, serializer):
        # Ensure the voucher belongs to the current user
        voucher = serializer.validated_data.get('voucher')
        if voucher.merchant.user != self.request.user:
            raise ValidationError("You can only create advertisements for your own vouchers")
        serializer.save()

    @action(detail=False, methods=["get"], url_path="active")
    def active_advertisements(self, request):
        """Get active advertisements"""
        try:
            current_date = timezone.now().date()
            active_ads = Advertisement.objects.filter(
                start_date__lte=current_date,
                end_date__gte=current_date,
                is_active=True
            ).order_by('-create_time')
           
            serializer = self.get_serializer(active_ads, many=True)
            return Response(serializer.data)
           
        except Exception as e:
            return Response(
                {"error": "Failed to fetch active advertisements"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], url_path="by-location")
    def advertisements_by_location(self, request):
        """Get advertisements by city and state"""
        try:
            city = request.query_params.get('city')
            state = request.query_params.get('state')
           
            if not city or not state:
                return Response(
                    {"error": "City and state parameters are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
           
            current_date = timezone.now().date()
            location_ads = Advertisement.objects.filter(
                city__iexact=city,
                state__iexact=state,
                start_date__lte=current_date,
                end_date__gte=current_date,
                is_active=True
            ).order_by('-create_time')
           
            serializer = self.get_serializer(location_ads, many=True)
            return Response(serializer.data)
           
        except Exception as e:
            return Response(
                {"error": "Failed to fetch advertisements by location"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )