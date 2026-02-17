from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError, DatabaseError
from django.conf import settings
from django.utils import timezone
from datetime import datetime
import json
import csv
import io

from analytics.models import SourceChat, SyncedChat


def _parse_ts(value: str):
    """
    ورودی را به unix timestamp (ثانیه) تبدیل می‌کند.
    - اگر عدد باشد همان را برمی‌گرداند
    - اگر ISO باشد (YYYY-MM-DD یا YYYY-MM-DDTHH:MM:SS) تبدیل می‌کند
    """
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    # ISO date/time
    dt = datetime.fromisoformat(value)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return int(dt.timestamp())


class Command(BaseCommand):
    help = 'استخراج و نمایش چت‌ها از دیتابیس OpenWebUI (جدول chat)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='حداکثر تعداد چت برای نمایش (پیش‌فرض: 100)'
        )
        parser.add_argument(
            '--user-id',
            type=str,
            default=None,
            help='فقط چت‌های یک کاربر خاص (user_id)'
        )
        parser.add_argument(
            '--updated-since',
            type=str,
            default=None,
            help='فقط چت‌هایی که updated_at >= این مقدار (unix ts یا ISO)'
        )
        parser.add_argument(
            '--updated-until',
            type=str,
            default=None,
            help='فقط چت‌هایی که updated_at <= این مقدار (unix ts یا ISO)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json', 'csv'],
            default='table',
            help='فرمت خروجی (table, json, csv)'
        )
        parser.add_argument(
            '--include-chat',
            action='store_true',
            help='فیلد chat (JSON بزرگ) را هم خروجی بده'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='چت‌های استخراج شده را در دیتابیس محلی (SyncedChat) ذخیره/به‌روزرسانی کن'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        user_id = options.get('user_id')
        output_format = options['format']
        include_chat = options.get('include_chat', False)
        do_sync = options.get('sync', False)
        updated_since = _parse_ts(options.get('updated_since'))
        updated_until = _parse_ts(options.get('updated_until'))

        self.stdout.write("🔍 در حال اتصال به دیتابیس OpenWebUI...")

        if getattr(settings, 'USE_MOCK_DATA', False):
            self.stdout.write(self.style.ERROR("❌ USE_MOCK_DATA فعال است؛ این دستور فقط دیتای واقعی را می‌خواند."))
            return

        # بررسی وجود دیتابیس openwebui_db
        if 'openwebui_db' not in settings.DATABASES:
            self.stdout.write(self.style.ERROR('❌ دیتابیس openwebui_db در تنظیمات یافت نشد!'))
            return

        try:
            db_conn = connections['openwebui_db']
            db_conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS('✅ اتصال به دیتابیس برقرار شد'))

            self.stdout.write("🔍 در حال بررسی ساختار جدول chat...")
            cursor = db_conn.cursor()
            table_name = SourceChat._meta.db_table

            # گرفتن ستون‌ها به صورت قابل حمل (Postgres/SQLite)
            available_columns = []
            try:
                desc = db_conn.introspection.get_table_description(cursor, table_name)
                available_columns = [col.name for col in desc]
            except Exception:
                if db_conn.vendor == 'sqlite':
                    cursor.execute(f'PRAGMA table_info("{table_name}")')
                    available_columns = [row[1] for row in cursor.fetchall()]
                else:
                    raise

            if not available_columns:
                self.stdout.write(self.style.ERROR(
                    f'❌ جدول "{table_name}" یافت نشد یا ستون‌ها قابل خواندن نیستند!'
                ))
                return

            self.stdout.write(self.style.SUCCESS(
                f'✅ ستون‌های موجود: {", ".join(sorted(available_columns))}'
            ))

            self.stdout.write("📊 در حال استخراج چت‌ها...")

            # ستون‌های مورد نیاز
            needed_columns = ['id', 'user_id', 'title', 'created_at', 'updated_at']
            if 'archived' in available_columns:
                needed_columns.append('archived')
            if 'share_id' in available_columns:
                needed_columns.append('share_id')
            if include_chat and 'chat' in available_columns:
                needed_columns.append('chat')

            columns_to_select = [c for c in needed_columns if c in available_columns]
            columns_str = ', '.join([f'"{c}"' for c in columns_to_select])

            where_parts = []
            params = []

            if user_id:
                where_parts.append('"user_id" = %s' if db_conn.vendor == 'postgresql' else '"user_id" = ?')
                params.append(user_id)

            if updated_since is not None and 'updated_at' in available_columns:
                where_parts.append('"updated_at" >= %s' if db_conn.vendor == 'postgresql' else '"updated_at" >= ?')
                params.append(int(updated_since))

            if updated_until is not None and 'updated_at' in available_columns:
                where_parts.append('"updated_at" <= %s' if db_conn.vendor == 'postgresql' else '"updated_at" <= ?')
                params.append(int(updated_until))

            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

            # مرتب‌سازی و limit
            limit_placeholder = '%s' if db_conn.vendor == 'postgresql' else '?'
            order_clause = 'ORDER BY "updated_at" DESC' if 'updated_at' in available_columns else 'ORDER BY "created_at" DESC'
            sql_query = f'SELECT {columns_str} FROM "{table_name}" {where_clause} {order_clause} LIMIT {limit_placeholder}'
            params.append(int(limit))

            cursor.execute(sql_query, params)
            rows = cursor.fetchall()

            if not rows:
                self.stdout.write(self.style.WARNING('⚠️  هیچ چتی یافت نشد!'))
                return

            chats = [dict(zip(columns_to_select, row)) for row in rows]
            self.stdout.write(self.style.SUCCESS(f'✅ {len(chats)} چت یافت شد\n'))

            # خروجی
            if output_format == 'table':
                self.display_table(chats, include_chat=include_chat)
            elif output_format == 'json':
                self.display_json(chats)
            else:
                self.display_csv(chats)

            # آمار کلی
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("📈 آمار:")
            self.stdout.write(f"   تعداد خروجی: {len(chats)}")
            if user_id:
                self.stdout.write(f"   فیلتر user_id: {user_id}")
            if updated_since is not None:
                self.stdout.write(f"   updated_since: {updated_since}")
            if updated_until is not None:
                self.stdout.write(f"   updated_until: {updated_until}")

            # سینک به دیتابیس محلی
            if do_sync:
                self.stdout.write("\n" + "=" * 80)
                self.stdout.write("🔄 شروع ذخیره/به‌روزرسانی در SyncedChat ...")
                added = 0
                updated = 0
                errors = []

                for c in chats:
                    try:
                        _, created = SyncedChat.objects.update_or_create(
                            id=str(c.get('id')),
                            defaults={
                                'user_id': str(c.get('user_id', '') or ''),
                                'title': c.get('title', '') or '',
                                'chat': c.get('chat', '') if include_chat else (c.get('chat', '') if 'chat' in c else ''),
                                'created_at': int(c.get('created_at') or 0),
                                'updated_at': int(c.get('updated_at') or 0),
                            }
                        )
                        if created:
                            added += 1
                        else:
                            updated += 1
                    except Exception as e:
                        errors.append(f"{c.get('id', '?')}: {e}")

                self.stdout.write(self.style.SUCCESS(f"✅ افزودن: {added} | به‌روزرسانی: {updated}"))
                if errors:
                    self.stdout.write(self.style.ERROR(f"⚠️  تعداد خطا: {len(errors)}"))
                    for err in errors[:10]:
                        self.stdout.write(f"   - {err}")
                    if len(errors) > 10:
                        self.stdout.write(f"   ... و {len(errors) - 10} خطای دیگر")

        except OperationalError as e:
            self.stdout.write(self.style.ERROR(f'❌ خطا در اتصال به دیتابیس: {e}'))
        except DatabaseError as e:
            self.stdout.write(self.style.ERROR(f'❌ خطا در اجرای کوئری: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ خطای غیرمنتظره: {e}'))

    def _fmt_ts(self, ts):
        if ts is None:
            return '-'
        try:
            dt = datetime.fromtimestamp(int(ts))
            dt = timezone.make_aware(dt, timezone.get_current_timezone()) if timezone.is_naive(dt) else dt
            return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(ts)

    def display_table(self, chats, include_chat=False):
        self.stdout.write("\n" + "=" * 120)
        header = f"{'ID':<28} {'USER':<22} {'UPDATED':<16} {'TITLE':<45}"
        if include_chat:
            header += f" {'CHAT':<30}"
        self.stdout.write(header)
        self.stdout.write("=" * 120)

        for c in chats:
            chat_id = str(c.get('id', ''))[:26] + '..' if len(str(c.get('id', ''))) > 28 else str(c.get('id', ''))
            user_id = str(c.get('user_id', ''))[:20] + '..' if len(str(c.get('user_id', ''))) > 22 else str(c.get('user_id', ''))
            updated = self._fmt_ts(c.get('updated_at'))
            title = (c.get('title') or '-')
            title = title[:43] + '..' if len(title) > 45 else title

            row = f"{chat_id:<28} {user_id:<22} {updated:<16} {title:<45}"
            if include_chat:
                chat_raw = c.get('chat') or ''
                preview = str(chat_raw).replace('\n', ' ')[:28] + '..' if len(str(chat_raw)) > 30 else str(chat_raw)
                row += f" {preview:<30}"
            self.stdout.write(row)

    def display_json(self, chats):
        self.stdout.write(json.dumps(chats, indent=2, ensure_ascii=False))

    def display_csv(self, chats):
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(chats[0].keys()))
        writer.writeheader()
        for c in chats:
            writer.writerow(c)
        self.stdout.write(output.getvalue())

