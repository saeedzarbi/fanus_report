from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError, DatabaseError
from analytics.models import SourceUser
from django.conf import settings
from analytics.services import UserSyncService


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
        parser.add_argument(
            '--sync',
            action='store_true',
            help='سینک کاربران استخراج شده به دیتابیس محلی (Employee)'
        )
        parser.add_argument(
            '--sync-deactivate',
            action='store_true',
            help='سینک کاربران و غیرفعال کردن کاربرانی که در OpenWebUI نیستند'
        )
        parser.add_argument(
            '--sync-delete',
            action='store_true',
            help='سینک کاربران و حذف کاربرانی که در OpenWebUI نیستند (خطرناک!)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        active_only = options.get('active_only', False)
        output_format = options['format']
        sync = options.get('sync', False)
        sync_deactivate = options.get('sync_deactivate', False)
        sync_delete = options.get('sync_delete', False)

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

            self.stdout.write("📊 در حال استخراج کاربران (با سرویس UserSyncService)...")

            # استفاده از همان منطقی که در UserSyncService.get_source_users استفاده می‌شود
            sync_service = UserSyncService()
            source_users = sync_service.get_source_users()

            # فیلتر فعال‌ها در صورت نیاز
            if active_only:
                source_users = [u for u in source_users if u.get('is_active', True)]

            total_count = len(source_users)

            if not source_users:
                self.stdout.write(self.style.WARNING('⚠️  هیچ کاربری یافت نشد!'))
                return

            # اعمال limit
            source_users = source_users[:limit]

            # تبدیل به اشیاء سازگار با توابع display_*
            users = []
            for u in source_users:
                user_obj = type('User', (), {
                    'id': str(u.get('id', '')),
                    'name': u.get('name'),
                    'username': u.get('username'),
                    'email': u.get('email'),
                    'created_at': None,
                    'updated_at': None,
                    'is_active': u.get('is_active', True),
                })()
                users.append(user_obj)

            has_is_active = True  # چون خودمان فیلد is_active را تولید می‌کنیم

            self.stdout.write(
                self.style.SUCCESS(f'✅ {len(users)} کاربر برای نمایش بارگذاری شد\n')
            )

            # نمایش کاربران
            if output_format == 'table':
                self.display_table(users, has_is_active)
            elif output_format == 'json':
                self.display_json(users, has_is_active)
            elif output_format == 'csv':
                self.display_csv(users, has_is_active)

            # آمار کلی
            self.stdout.write("\n" + "="*80)
            self.stdout.write("📈 آمار کلی:")
            self.stdout.write(f"   کل کاربران (قبل از limit): {total_count}")
            active_count = sum(1 for u in source_users if u.get('is_active', True))
            self.stdout.write(f"   کاربران فعال (در لیست نمایش): {active_count}")
            self.stdout.write(f"   کاربران غیرفعال (در لیست نمایش): {len(source_users) - active_count}")

            # انجام سینک اگر درخواست شده باشد
            if sync or sync_deactivate or sync_delete:
                self.stdout.write("\n" + "="*80)
                self.stdout.write("🔄 شروع فرآیند سینک کاربران...")
                
                try:
                    sync_service = UserSyncService()
                    
                    # تعیین نوع سینک
                    if sync_delete:
                        self.stdout.write(
                            self.style.WARNING(
                                "⚠️  هشدار: این عملیات کاربرانی که در OpenWebUI نیستند را حذف می‌کند!"
                            )
                        )
                        deactivate_missing = False
                        delete_missing = True
                    elif sync_deactivate:
                        deactivate_missing = True
                        delete_missing = False
                    else:
                        deactivate_missing = False
                        delete_missing = False
                    
                    # انجام سینک
                    result = sync_service.sync_users(
                        deactivate_missing=deactivate_missing,
                        delete_missing=delete_missing
                    )
                    
                    # نمایش نتایج
                    self.stdout.write("\n📊 نتایج سینک:")
                    if result['added'] > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f"   ✅ {result['added']} کاربر جدید اضافه شد")
                        )
                    if result['updated'] > 0:
                        self.stdout.write(
                            self.style.SUCCESS(f"   🔄 {result['updated']} کاربر به‌روزرسانی شد")
                        )
                    if result.get('deactivated', 0) > 0:
                        self.stdout.write(
                            self.style.WARNING(f"   ⏸️  {result['deactivated']} کاربر غیرفعال شد")
                        )
                    if result.get('deleted', 0) > 0:
                        self.stdout.write(
                            self.style.ERROR(f"   🗑️  {result['deleted']} کاربر حذف شد")
                        )
                    if result['errors']:
                        self.stdout.write(
                            self.style.ERROR(f"   ⚠️  {len(result['errors'])} خطا رخ داد:")
                        )
                        for error in result['errors'][:5]:  # نمایش حداکثر 5 خطا
                            self.stdout.write(f"      - {error}")
                        if len(result['errors']) > 5:
                            self.stdout.write(f"      ... و {len(result['errors']) - 5} خطای دیگر")
                    
                    if (result['added'] == 0 and result['updated'] == 0 and 
                        result.get('deactivated', 0) == 0 and result.get('deleted', 0) == 0 and 
                        not result['errors']):
                        self.stdout.write(
                            self.style.SUCCESS("   ✅ همه کاربران به‌روز هستند!")
                        )
                    
                    self.stdout.write(self.style.SUCCESS("\n✅ فرآیند سینک با موفقیت انجام شد!"))
                    
                except Exception as sync_error:
                    self.stdout.write(
                        self.style.ERROR(f"❌ خطا در فرآیند سینک: {sync_error}")
                    )

        except OperationalError as e:
            self.stdout.write(
                self.style.ERROR(f'❌ خطا در اتصال به دیتابیس: {e}')
            )
            self.stdout.write(
                self.style.WARNING(
                    '💡 لطفاً مطمئن شوید که دیتابیس PostgreSQL در حال اجرا است و اطلاعات اتصال در settings.py صحیح است.'
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

    def display_table(self, users, has_is_active=False):
        """نمایش کاربران به صورت جدول"""
        if not users:
            return
        
        self.stdout.write("\n" + "="*80)
        if has_is_active:
            self.stdout.write(f"{'ID':<30} {'نام':<25} {'نام کاربری':<20} {'ایمیل':<30} {'وضعیت'}")
        else:
            self.stdout.write(f"{'ID':<30} {'نام':<25} {'نام کاربری':<20} {'ایمیل':<30}")
        self.stdout.write("="*80)

        for user in users:
            user_id = str(user.id)[:28] + '..' if len(str(user.id)) > 30 else str(user.id)
            name = (user.name or '-')[:23] + '..' if user.name and len(user.name) > 25 else (user.name or '-')
            username = (user.username or '-')[:18] + '..' if user.username and len(user.username) > 20 else (user.username or '-')
            email = (user.email or '-')[:28] + '..' if user.email and len(user.email) > 30 else (user.email or '-')
            
            if has_is_active:
                try:
                    status = '✅ فعال' if getattr(user, 'is_active', True) else '❌ غیرفعال'
                    self.stdout.write(
                        f"{user_id:<30} {name:<25} {username:<20} {email:<30} {status}"
                    )
                except:
                    self.stdout.write(
                        f"{user_id:<30} {name:<25} {username:<20} {email:<30}"
                    )
            else:
                self.stdout.write(
                    f"{user_id:<30} {name:<25} {username:<20} {email:<30}"
                )

    def display_json(self, users, has_is_active=False):
        """نمایش کاربران به صورت JSON"""
        import json
        users_data = []
        
        for user in users:
            user_data = {
                'id': str(user.id),
                'name': user.name,
                'username': user.username,
                'email': user.email,
            }
            
            # اضافه کردن is_active فقط اگر وجود دارد
            if has_is_active:
                user_data['is_active'] = getattr(user, 'is_active', True)
            
            # اضافه کردن تاریخ‌ها اگر وجود دارند
            if hasattr(user, 'created_at') and user.created_at:
                user_data['created_at'] = user.created_at.isoformat()
            if hasattr(user, 'updated_at') and user.updated_at:
                user_data['updated_at'] = user.updated_at.isoformat()
            
            users_data.append(user_data)
        
        self.stdout.write(json.dumps(users_data, indent=2, ensure_ascii=False))

    def display_csv(self, users, has_is_active=False):
        """نمایش کاربران به صورت CSV"""
        import csv
        import io
        
        if not users:
            return
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # بررسی وجود ستون‌ها
        has_created_at = hasattr(users[0], 'created_at')
        has_updated_at = hasattr(users[0], 'updated_at')
        
        # Header
        header = ['ID', 'Name', 'Username', 'Email']
        if has_is_active:
            header.append('Is Active')
        if has_created_at:
            header.append('Created At')
        if has_updated_at:
            header.append('Updated At')
        writer.writerow(header)
        
        # Data
        for user in users:
            row = [
                user.id,
                user.name or '',
                user.username or '',
                user.email or '',
            ]
            if has_is_active:
                row.append(getattr(user, 'is_active', ''))
            if has_created_at:
                row.append(user.created_at.isoformat() if getattr(user, 'created_at', None) else '')
            if has_updated_at:
                row.append(user.updated_at.isoformat() if getattr(user, 'updated_at', None) else '')
            
            writer.writerow(row)
        
        self.stdout.write(output.getvalue())

