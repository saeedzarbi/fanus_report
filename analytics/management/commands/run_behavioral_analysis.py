"""
اجرای تحلیل رفتاری کاربران در پس‌زمینه (تسک زمان‌بندی‌شده).

این کامند را می‌توان با cron یا Windows Task Scheduler اجرا کرد تا تحلیل
به‌صورت خودکار در پس‌زمینه انجام شود.

مثال cron (هر شب ساعت ۲):
  0 2 * * * cd /path/to/project && python manage.py run_behavioral_analysis

مثال ویندوز: در Task Scheduler یک Task بسازید که برنامه آن:
  python manage.py run_behavioral_analysis
  و مسیر شروع را به پوشه پروژه بدهید.
"""
from django.core.management.base import BaseCommand
from analytics.models import Employee
from analytics.services import UserReportService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'تحلیل رفتاری چت‌های کاربران برای همهٔ کارمندان فعال (برای اجرا به‌صورت تسک در پس‌زمینه)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='تعداد چت‌های هر کاربر برای تحلیل (پیش‌فرض: 20)',
        )
        parser.add_argument(
            '--user-id',
            type=str,
            default=None,
            help='فقط یک کاربر با user_id مشخص تحلیل شود',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط لیست کاربران را نشان بده، تحلیل انجام نده',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        user_id_filter = options.get('user_id')
        dry_run = options.get('dry_run', False)

        self.stdout.write('🚀 شروع تسک تحلیل رفتاری (پس‌زمینه)...')

        if user_id_filter:
            employees = Employee.objects.filter(user_id=user_id_filter, is_active=True)
            if not employees.exists():
                self.stdout.write(self.style.WARNING(f'⚠️ کاربر با user_id={user_id_filter} یافت نشد.'))
                return
        else:
            employees = Employee.objects.filter(is_active=True).order_by('name')

        total = employees.count()
        self.stdout.write(f'📋 تعداد کارمندان برای تحلیل: {total}')

        if dry_run:
            for emp in employees:
                self.stdout.write(f'   - {emp.name} ({emp.user_id})')
            self.stdout.write(self.style.SUCCESS('✅ حالت dry-run؛ بدون تحلیل.'))
            return

        service = UserReportService()
        total_analyzed = 0
        total_skipped = 0
        errors = 0

        for emp in employees:
            self.stdout.write(f'🔄 در حال تحلیل: {emp.name} ({emp.user_id})...')
            try:
                result = service.analyze_last_chats(emp.user_id, limit=limit)
                if not result.get('employee_found'):
                    self.stdout.write(self.style.WARNING(f'   ⚠️ رکورد کارمند یافت نشد؛ رد شد.'))
                    continue
                a = result.get('analyzed', 0)
                s = result.get('skipped_existing', 0)
                total_analyzed += a
                total_skipped += s
                self.stdout.write(self.style.SUCCESS(f'   ✅ تحلیل شده: {a} | از قبل بود: {s}'))
            except Exception as e:
                errors += 1
                logger.exception('خطا در تحلیل کاربر %s: %s', emp.user_id, e)
                self.stdout.write(self.style.ERROR(f'   ❌ خطا: {e}'))

        self.stdout.write('')
        self.stdout.write('=' * 50)
        self.stdout.write('📊 جمع‌بندی:')
        self.stdout.write(f'   چت‌های جدید تحلیل‌شده: {total_analyzed}')
        self.stdout.write(f'   چت‌های تکراری (رد شده): {total_skipped}')
        if errors:
            self.stdout.write(self.style.ERROR(f'   خطا: {errors}'))
        self.stdout.write(self.style.SUCCESS('🏁 پایان تسک تحلیل رفتاری.'))
