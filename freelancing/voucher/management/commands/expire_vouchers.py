# from django.core.management.base import BaseCommand
# from django.utils import timezone
# from freelancing.voucher.models import UserVoucherRedemption
# from django.db import transaction, DatabaseError
# from django.core.exceptions import ValidationError

# class Command(BaseCommand):
#     help = 'Expire vouchers that have passed their expiry date with optimized transaction handling'

#     def add_arguments(self, parser):
#         parser.add_argument(
#             '--dry-run',
#             action='store_true',
#             help='Show what would be expired without actually expiring them',
#         )
#         parser.add_argument(
#             '--batch-size',
#             type=int,
#             default=1000,
#             help='Number of vouchers to process in each batch (default: 1000)',
#         )
#         parser.add_argument(
#             '--force',
#             action='store_true',
#             help='Force expiry even if there are errors',
#         )

#     def handle(self, *args, **options):
#         dry_run = options['dry_run']
#         batch_size = options['batch_size']
#         force = options['force']
        
#         try:
#             if dry_run:
#                 self._dry_run_expiry()
#             else:
#                 self._perform_bulk_expiry(batch_size, force)
                
#         except Exception as e:
#             self.stdout.write(
#                 self.style.ERROR(f'Critical error: {str(e)}')
#             )
#             if not force:
#                 raise

#     def _dry_run_expiry(self):
#         """Perform dry run to show what would be expired"""
#         try:
#             # Get vouchers that would be expired
#             expired_vouchers = UserVoucherRedemption.objects.filter(
#                 purchase_status='purchased',
#                 expiry_date__lt=timezone.now(),
#                 redeemed_at__isnull=True
#             )
            
#             count = expired_vouchers.count()
            
#             self.stdout.write(
#                 self.style.WARNING(
#                     f'DRY RUN: Would expire {count} vouchers'
#                 )
#             )
            
#             # Show sample of vouchers that would be expired
#             sample_vouchers = expired_vouchers.select_related('user', 'voucher')[:10]
            
#             for voucher in sample_vouchers:
#                 self.stdout.write(
#                     f'  - {voucher.user.email} - {voucher.voucher.title} '
#                     f'(Expired: {voucher.expiry_date})'
#                 )
            
#             if count > 10:
#                 self.stdout.write(f'  ... and {count - 10} more')
                
#         except Exception as e:
#             self.stdout.write(
#                 self.style.ERROR(f'Dry run failed: {str(e)}')
#             )

#     def _perform_bulk_expiry(self, batch_size, force):
#         """Perform actual bulk expiry with batching"""
#         total_expired = 0
#         total_errors = 0
        
#         try:
#             # Use the optimized bulk expiry method
#             expired_count = UserVoucherRedemption.bulk_expire_vouchers()
#             total_expired = expired_count
            
#             self.stdout.write(
#                 self.style.SUCCESS(
#                     f'Successfully expired {total_expired} vouchers'
#                 )
#             )
            
#         except ValidationError as e:
#             self.stdout.write(
#                 self.style.ERROR(f'Validation error: {str(e)}')
#             )
#             if not force:
#                 raise
#         except DatabaseError as e:
#             self.stdout.write(
#                 self.style.ERROR(f'Database error: {str(e)}')
#             )
#             if not force:
#                 raise
#         except Exception as e:
#             self.stdout.write(
#                 self.style.ERROR(f'Unexpected error: {str(e)}')
#             )
#             if not force:
#                 raise

#     def _batch_expire_vouchers(self, batch_size):
#         """Alternative method for batch processing if needed"""
#         offset = 0
#         total_expired = 0
        
#         while True:
#             try:
#                 with transaction.atomic():
#                     # Get batch of vouchers to expire
#                     expired_batch = UserVoucherRedemption.objects.filter(
#                         purchase_status='purchased',
#                         expiry_date__lt=timezone.now(),
#                         redeemed_at__isnull=True
#                     )[offset:offset + batch_size]
                    
#                     batch_count = expired_batch.count()
#                     if batch_count == 0:
#                         break
                    
#                     # Expire the batch
#                     expired_batch.update(
#                         is_active=False,
#                         purchase_status='expired',
#                         redemption_notes=models.F('redemption_notes') + f" | Auto-expired on {timezone.now()}"
#                     )
                    
#                     total_expired += batch_count
#                     offset += batch_size
                    
#                     self.stdout.write(f'Processed batch: {batch_count} vouchers expired')
                    
#             except DatabaseError as e:
#                 raise
#             except Exception as e:
#                 raise
        
#         return total_expired 