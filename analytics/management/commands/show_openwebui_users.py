from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError, DatabaseError
from analytics.models import SourceUser
from django.conf import settings


class Command(BaseCommand):
    help = 'استخراج و نمایش کاربران از دیتابیس OpenWebUI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='حداکثر تعداد کاربران برای نمایش (پیش‌فرض: 100)'
        )
        parser.add_argument(
            '--active-only',
            action='store_true',
            help='فقط کاربران فعال را نمایش بده'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json', 'csv'],
            default='table',
            help='فرمت خروجی (table, json, csv)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        active_only = options.get('active_only', False)
        output_format = options['format']

        self.stdout.write("🔍 در حال اتصال به دیتابیس OpenWebUI...")

        # بررسی وجود دیتابیس openwebui_db
        if 'openwebui_db' not in settings.DATABASES:
            self.stdout.write(
                self.style.ERROR('❌ دیتابیس openwebui_db در تنظیمات یافت نشد!')
            )
            return

        try:
            # تست اتصال به دیتابیس
            db_conn = connections['openwebui_db']
            db_conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS('✅ اتصال به دیتابیس برقرار شد'))

            # استخراج کاربران
            self.stdout.write("📊 در حال استخراج کاربران...")
            
            users_query = SourceUser.objects.using('openwebui_db').all()
            
            if active_only:
                users_query = users_query.filter(is_active=True)
            
            users = list(users_query.order_by('-created_at')[:limit])

            if not users:
                self.stdout.write(self.style.WARNING('⚠️  هیچ کاربری یافت نشد!'))
                return

            self.stdout.write(
                self.style.SUCCESS(f'✅ {len(users)} کاربر یافت شد\n')
            )

            # نمایش کاربران
            if output_format == 'table':
                self.display_table(users)
            elif output_format == 'json':
                self.display_json(users)
            elif output_format == 'csv':
                self.display_csv(users)

            # آمار کلی
            total_count = SourceUser.objects.using('openwebui_db').count()
            active_count = SourceUser.objects.using('openwebui_db').filter(
                is_active=True
            ).count()

            self.stdout.write("\n" + "="*80)
            self.stdout.write(f"📈 آمار کلی:")
            self.stdout.write(f"   کل کاربران: {total_count}")
            self.stdout.write(f"   کاربران فعال: {active_count}")
            self.stdout.write(f"   کاربران غیرفعال: {total_count - active_count}")

        except OperationalError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطا در اتصال به دیتابیس: {e}')
            )
            self.stdout.write(
                self.style.WARNING(
                    '💡 لطفاً مطمئن شوید که:\n'
                    '   1. دیتابیس PostgreSQL در حال اجرا است\n'
                    '   2. اطلاعات اتصال در settings.py صحیح است\n'
                    '   3. جدول user در دیتابیس openwebui وجود دارد'
                )
            )
        except DatabaseError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطا در اجرای کوئری: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطای غیرمنتظره: {e}')
            )

    def display_table(self, users):
        """نمایش کاربران به صورت جدول"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write(f"{'ID':<30} {'نام':<25} {'نام کاربری':<20} {'ایمیل':<30} {'وضعیت'}")
        self.stdout.write("="*80)

        for user in users:
            user_id = str(user.id)[:28] + '..' if len(str(user.id)) > 30 else str(user.id)
            name = (user.name or '-')[:23] + '..' if user.name and len(user.name) > 25 else (user.name or '-')
            username = (user.username or '-')[:18] + '..' if user.username and len(user.username) > 20 else (user.username or '-')
            email = (user.email or '-')[:28] + '..' if user.email and len(user.email) > 30 else (user.email or '-')
            status = '✅ فعال' if user.is_active else '❌ غیرفعال'

            self.stdout.write(
                f"{user_id:<30} {name:<25} {username:<20} {email:<30} {status}"
            )

    def display_json(self, users):
        """نمایش کاربران به صورت JSON"""
        import json
        users_data = []
        
        for user in users:
            users_data.append({
                'id': str(user.id),
                'name': user.name,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None,
            })
        
        self.stdout.write(json.dumps(users_data, indent=2, ensure_ascii=False))

    def display_csv(self, users):
        """نمایش کاربران به صورت CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['ID', 'Name', 'Username', 'Email', 'Is Active', 'Created At', 'Updated At'])
        
        # Data
        for user in users:
            writer.writerow([
                user.id,
                user.name or '',
                user.username or '',
                user.email or '',
                user.is_active,
                user.created_at.isoformat() if user.created_at else '',
                user.updated_at.isoformat() if user.updated_at else '',
            ])
        
        self.stdout.write(output.getvalue())

