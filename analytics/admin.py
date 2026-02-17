import threading
from django.contrib import admin
from django.core.management import call_command
from django.contrib import messages
from django.db.utils import OperationalError
from .models import (
    Employee, UserGroup, AnalysisTask, ChatAnalysis,
    ReportType, Report, ReportSchedule,
    ChatSyncState, SyncedChat,
    SourceUser, SourceChat
)
from .services import ReportGenerationService, UserSyncService, ChatSyncService, UserReportService

ALL_USERS_UP_TO_DATE_MSG = "همه کاربران به‌روز هستند."

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_id', 'department', 'is_active', 'created_at')
    list_filter = ('is_active', 'department', 'created_at')
    search_fields = ('name', 'user_id', 'email')
    ordering = ('name',)
    actions = [
        'show_sync_summary_action',
        'sync_users_action',
        'sync_users_deactivate_action',
        'sync_users_delete_action',
        'sync_chats_action',
        'analyze_last_20_chats_action',
        'run_behavioral_analysis_background_action',
    ]

    def changelist_view(self, request, extra_context=None):
        """افزودن دکمه‌های سینک در بالای لیست"""
        extra_context = extra_context or {}

        # اضافه کردن اطلاعات سینک کاربران به context
        sync_service = UserSyncService()
        summary = sync_service.get_sync_summary()
        extra_context['sync_summary'] = summary

        # اضافه کردن اطلاعات سینک چت‌ها به context
        chat_sync_service = ChatSyncService()
        extra_context['chat_sync_summary'] = chat_sync_service.get_sync_summary()

        return super().changelist_view(request, extra_context)
    
    def show_sync_summary_action(self, request, queryset):
        """
        نمایش خلاصه وضعیت سینک
        """
        sync_service = UserSyncService()
        summary = sync_service.get_sync_summary()
        
        message_parts = [
            f"کاربران در دیتابیس منبع: {summary['source_count']}",
            f"کاربران در سیستم محلی: {summary['local_count']}",
            f"کاربران جدید: {summary['new_users_count']}",
            f"کاربران حذف شده: {summary['missing_users_count']}",
            f"کاربران همگام شده: {summary['synced_users_count']}"
        ]
        
        if summary['new_users']:
            message_parts.append(f"\nکاربران جدید: {', '.join(summary['new_users'][:10])}")
            if len(summary['new_users']) > 10:
                message_parts.append(f"... و {len(summary['new_users']) - 10} کاربر دیگر")
        
        if summary['missing_users']:
            message_parts.append(f"\nکاربران حذف شده: {', '.join(summary['missing_users'][:10])}")
            if len(summary['missing_users']) > 10:
                message_parts.append(f"... و {len(summary['missing_users']) - 10} کاربر دیگر")
        
        self.message_user(
            request,
            "\n".join(message_parts),
            messages.INFO
        )
    
    show_sync_summary_action.short_description = "📊 نمایش خلاصه وضعیت سینک"
    
    def sync_users_action(self, request, queryset):
        """
        سینک کاربران از دیتابیس OpenWebUI (فقط اضافه و به‌روزرسانی)
        اگر queryset خالی باشد، همه کاربران را سینک می‌کند
        """
        # اگر هیچ کاربری انتخاب نشده، همه را سینک کن
        if not queryset.exists():
            queryset = Employee.objects.all()
        
        sync_service = UserSyncService()
        result = sync_service.sync_users(deactivate_missing=False, delete_missing=False)
        
        message_parts = []
        if result['added'] > 0:
            message_parts.append(f"{result['added']} کاربر جدید اضافه شد")
        if result['updated'] > 0:
            message_parts.append(f"{result['updated']} کاربر به‌روزرسانی شد")
        if result['errors']:
            message_parts.append(f"{len(result['errors'])} خطا رخ داد")
        
        if message_parts:
            self.message_user(
                request,
                " | ".join(message_parts),
                messages.SUCCESS if not result['errors'] else messages.WARNING
            )
        else:
            self.message_user(
                request,
                ALL_USERS_UP_TO_DATE_MSG,
                messages.INFO
            )
    
    sync_users_action.short_description = "🔄 سینک کاربران (اضافه و به‌روزرسانی)"
    
    def sync_users_deactivate_action(self, request, queryset):
        """
        سینک کاربران و غیرفعال کردن کاربرانی که در OpenWebUI نیستند
        همیشه همه کاربران را سینک می‌کند (queryset نادیده گرفته می‌شود)
        """
        sync_service = UserSyncService()
        result = sync_service.sync_users(deactivate_missing=True, delete_missing=False)
        
        message_parts = []
        if result['added'] > 0:
            message_parts.append(f"{result['added']} کاربر جدید اضافه شد")
        if result['updated'] > 0:
            message_parts.append(f"{result['updated']} کاربر به‌روزرسانی شد")
        if result['deactivated'] > 0:
            message_parts.append(f"{result['deactivated']} کاربر غیرفعال شد")
        if result['errors']:
            message_parts.append(f"{len(result['errors'])} خطا رخ داد")
        
        if message_parts:
            self.message_user(
                request,
                " | ".join(message_parts),
                messages.SUCCESS if not result['errors'] else messages.WARNING
            )
        else:
            self.message_user(
                request,
                ALL_USERS_UP_TO_DATE_MSG,
                messages.INFO
            )
    
    sync_users_deactivate_action.short_description = "🔄 سینک کاربران (با غیرفعال کردن کاربران حذف شده)"
    
    def sync_users_delete_action(self, request, queryset):
        """
        سینک کاربران و حذف کاربرانی که در OpenWebUI نیستند
        همیشه همه کاربران را سینک می‌کند (queryset نادیده گرفته می‌شود)
        """
        from django.contrib.admin import helpers
        from django.template.response import TemplateResponse
        
        # درخواست تأیید از کاربر
        if request.POST.get('confirm'):
            sync_service = UserSyncService()
            result = sync_service.sync_users(deactivate_missing=False, delete_missing=True)
            
            message_parts = []
            if result['added'] > 0:
                message_parts.append(f"{result['added']} کاربر جدید اضافه شد")
            if result['updated'] > 0:
                message_parts.append(f"{result['updated']} کاربر به‌روزرسانی شد")
            if result['deleted'] > 0:
                message_parts.append(f"{result['deleted']} کاربر حذف شد")
            if result['errors']:
                message_parts.append(f"{len(result['errors'])} خطا رخ داد")
            
            if message_parts:
                self.message_user(
                    request,
                    " | ".join(message_parts),
                    messages.SUCCESS if not result['errors'] else messages.WARNING
                )
            else:
                self.message_user(
                    request,
                    "همه کاربران به‌روز هستند.",
                    messages.INFO
                )
            return
        
        # نمایش صفحه تأیید
        sync_service = UserSyncService()
        summary = sync_service.get_sync_summary()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'تأیید حذف کاربران',
            'objects_name': 'کاربران',
            'queryset': queryset,
            'opts': self.model._meta,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'summary': summary,
        }
        
        return TemplateResponse(
            request,
            'admin/analytics/employee/confirm_sync_delete.html',
            context
        )
    
    sync_users_delete_action.short_description = "🗑️ سینک کاربران (با حذف کاربران حذف شده)"

    def sync_chats_action(self, request, queryset):
        """
        سینک چت‌های کاربران از OpenWebUI.
        فقط چت‌هایی که بعد از آخرین زمان سینک به‌روزرسانی شده‌اند ذخیره می‌شوند.
        """
        chat_sync_service = ChatSyncService()
        result = chat_sync_service.sync_chats()

        message_parts = []
        if result['added'] > 0:
            message_parts.append(f"{result['added']} چت جدید ذخیره شد")
        if result['updated'] > 0:
            message_parts.append(f"{result['updated']} چت به‌روزرسانی شد")
        if result['errors']:
            message_parts.append(f"{len(result['errors'])} خطا")

        if message_parts:
            self.message_user(
                request,
                " | ".join(message_parts),
                messages.SUCCESS if not result['errors'] else messages.WARNING
            )
        else:
            self.message_user(
                request,
                "همه چت‌ها به‌روز هستند. (چت جدیدی برای سینک نبود)",
                messages.INFO
            )
        if result.get('last_sync_at'):
            self.message_user(
                request,
                f"آخرین زمان سینک: {result['last_sync_at']}",
                messages.INFO
            )

    sync_chats_action.short_description = "💬 سینک چت‌های کاربران (از آخرین به‌روزرسانی)"

    def analyze_last_20_chats_action(self, request, queryset):
        """
        تحلیل آخرین 20 چت برای هر کارمند انتخاب‌شده.
        از سرویس UserReportService استفاده می‌کند و نتایج را در ChatAnalysis ذخیره می‌کند.
        """
        service = UserReportService()
        total_analyzed = 0
        total_skipped = 0
        users_without_employee = 0

        for employee in queryset:
            result = service.analyze_last_chats(employee.user_id, limit=20)
            if not result.get('employee_found'):
                users_without_employee += 1
                continue

            total_analyzed += result.get('analyzed', 0)
            total_skipped += result.get('skipped_existing', 0)

        msg_parts = []
        if total_analyzed:
            msg_parts.append(f"{total_analyzed} چت جدید تحلیل شد")
        if total_skipped:
            msg_parts.append(f"{total_skipped} چت قبلاً تحلیل شده بود")
        if users_without_employee:
            msg_parts.append(f"{users_without_employee} کاربر بدون رکورد معتبر کارمند بود")

        if msg_parts:
            self.message_user(
                request,
                " | ".join(msg_parts),
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                "چتی برای تحلیل پیدا نشد. احتمالاً برای کاربران انتخاب‌شده در OpenWebUI چتی وجود ندارد، "
                "یا همهٔ چت‌ها قبلاً تحلیل شده‌اند. اتصال به دیتابیس OpenWebUI و سینک چت‌ها را بررسی کنید.",
                messages.WARNING
            )

    analyze_last_20_chats_action.short_description = "🧠 تحلیل آخرین ۲۰ چت کاربر"

    def run_behavioral_analysis_background_action(self, request, queryset):
        """
        اجرای تحلیل رفتاری در پس‌زمینه (تسک). صفحه بلافاصله برمی‌گردد و تحلیل در سرور ادامه می‌یابد.
        برای مشاهدهٔ پیام ارسالی به AI و پاسخ AI، لاگ‌های کنسول سرور را ببینید.
        """
        limit = 20
        employee_ids = list(queryset.values_list('user_id', flat=True))
        if not employee_ids:
            self.message_user(request, "هیچ کارمندی انتخاب نشده است.", messages.WARNING)
            return

        def run_analysis():
            service = UserReportService()
            for user_id in employee_ids:
                try:
                    service.analyze_last_chats(user_id, limit=limit)
                except Exception:
                    pass  # خطاها در logger ثبت می‌شوند

        t = threading.Thread(target=run_analysis, daemon=True)
        t.start()
        self.message_user(
            request,
            f"تحلیل رفتاری برای {len(employee_ids)} کاربر در پس‌زمینه شروع شد. "
            "لاگ‌های «درخواست به AI» و «پاسخ AI» را در کنسول سرور ببینید.",
            messages.SUCCESS,
        )

    run_behavioral_analysis_background_action.short_description = "⏳ اجرای تحلیل رفتاری در پس‌زمینه (تسک)"

@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee_count', 'created_at')
    filter_horizontal = ('employees',)
    search_fields = ('name', 'description')

    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = 'تعداد کارمندان'

@admin.register(AnalysisTask)
class AnalysisTaskAdmin(admin.ModelAdmin):
    list_display = ('name', 'task_type', 'is_active', 'last_run', 'cron_schedule')
    list_filter = ('task_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('last_run',)

@admin.register(ChatAnalysis)
class ChatAnalysisAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'category', 'sentiment_score', 'is_risky', 'task', 'timestamp')
    list_filter = ('is_risky', 'category', 'task', 'timestamp')
    search_fields = ('user_id', 'summary')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp', 'raw_analysis')
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('source_chat_id', 'user_id', 'task', 'timestamp')
        }),
        ('نتایج تحلیل', {
            'fields': ('sentiment_score', 'category', 'is_risky', 'summary', 'raw_analysis')
        }),
    )

@admin.register(ReportType)
class ReportTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'is_active')
    list_filter = ('report_type', 'is_active')

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'period', 'status', 'generated_at', 'created_at')
    list_filter = ('status', 'period', 'report_type', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('generated_at', 'created_at', 'updated_at', 'report_data', 'summary', 'generated_by')
    filter_horizontal = ('employees', 'groups')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('اطلاعات گزارش', {
            'fields': ('name', 'report_type', 'period', 'status')
        }),
        ('بازه زمانی', {
            'fields': ('start_date', 'end_date')
        }),
        ('محدوده کاربران', {
            'fields': ('employees', 'groups')
        }),
        ('تنظیمات تحلیل', {
            'fields': ('task',)
        }),
        ('نتایج', {
            'fields': ('summary', 'report_data', 'file_path', 'generated_at', 'generated_by')
        }),
        ('اطلاعات سیستم', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['generate_report_action']

    def save_model(self, request, obj, form, change):
        if not change and not obj.generated_by:
            obj.generated_by = request.user
        super().save_model(request, obj, form, change)

    def generate_report_action(self, request, queryset):
        service = ReportGenerationService()
        success_count = 0
        for report in queryset:
            if report.status != 'processing':
                if service.process_report(report):
                    report.generated_by = request.user
                    report.save()
                    success_count += 1
        
        self.message_user(
            request,
            f"{success_count} گزارش با موفقیت تولید شد.",
            messages.SUCCESS
        )
    generate_report_action.short_description = "تولید گزارش‌های انتخاب شده"

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'period', 'is_active', 'last_run', 'next_run')
    list_filter = ('period', 'is_active', 'report_type')
    search_fields = ('name',)
    filter_horizontal = ('employees', 'groups')
    readonly_fields = ('last_run', 'next_run')
    
    fieldsets = (
        ('اطلاعات زمانبندی', {
            'fields': ('name', 'report_type', 'period', 'is_active')
        }),
        ('محدوده کاربران', {
            'fields': ('employees', 'groups')
        }),
        ('تنظیمات', {
            'fields': ('task', 'cron_schedule')
        }),
        ('وضعیت اجرا', {
            'fields': ('last_run', 'next_run')
        }),
    )

    actions = ['run_schedule_action']

    def run_schedule_action(self, request, queryset):
        for schedule in queryset:
            if schedule.is_active:
                try:
                    call_command('run_scheduled_reports', schedule_id=schedule.id)
                    self.message_user(request, f"زمانبندی {schedule.name} اجرا شد.", messages.SUCCESS)
                except Exception as e:
                    self.message_user(request, f"خطا در اجرای {schedule.name}: {e}", messages.ERROR)
    run_schedule_action.short_description = "اجرای زمانبندی‌های انتخاب شده"


@admin.register(ChatSyncState)
class ChatSyncStateAdmin(admin.ModelAdmin):
    list_display = ('key', 'last_sync_at')
    readonly_fields = ('key', 'last_sync_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SyncedChat)
class SyncedChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'title_short', 'updated_at_display', 'synced_at')
    list_filter = ('user_id', 'synced_at')
    search_fields = ('id', 'user_id', 'title')
    readonly_fields = ('id', 'user_id', 'title', 'chat', 'created_at', 'updated_at', 'synced_at')
    ordering = ('-synced_at',)

    def title_short(self, obj):
        return (obj.title[:50] + '...') if obj.title and len(obj.title) > 50 else (obj.title or '-')
    title_short.short_description = 'عنوان'

    def updated_at_display(self, obj):
        if not obj.updated_at:
            return '-'
        from datetime import datetime
        from django.utils import timezone as tz
        try:
            dt = datetime.fromtimestamp(obj.updated_at)
            return tz.make_aware(dt, tz.get_current_timezone()).strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(obj.updated_at)
    updated_at_display.short_description = 'به‌روزرسانی در منبع'


@admin.register(SourceUser)
class SourceUserAdmin(admin.ModelAdmin):
    """کاربران دیتابیس OpenWebUI (فقط نمایش)"""
    list_display = ('id', 'name', 'username', 'email', 'is_active', 'created_at', 'updated_at')
    # is_active در جدول OpenWebUI وجود ندارد؛ فقط به صورت property نمایش داده می‌شود
    search_fields = ('id', 'name', 'username', 'email')
    readonly_fields = ('id', 'name', 'username', 'email', 'created_at', 'updated_at', 'is_active')
    ordering = ('name',)

    def get_queryset(self, request):
        """
        تلاش برای خواندن کاربران از دیتابیس openwebui_db.
        اگر جدول user وجود نداشته باشد، به‌جای خطا، queryset خالی برمی‌گردانیم.
        """
        try:
            return super().get_queryset(request).using('openwebui_db')
        except OperationalError:
            self.message_user(
                request,
                "جدول user در دیتابیس OpenWebUI یافت نشد؛ نمایش کاربران ممکن نیست.",
                level=messages.WARNING,
            )
            return self.model.objects.none()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SourceChat)
class SourceChatAdmin(admin.ModelAdmin):
    """چت‌های دیتابیس OpenWebUI (فقط نمایش)"""
    list_display = ('id', 'user_id', 'title_short', 'created_at_ts', 'updated_at_ts')
    list_filter = ('user_id',)
    search_fields = ('id', 'user_id', 'title')
    readonly_fields = ('id', 'user_id', 'title', 'share_id', 'archived', 'created_at', 'updated_at', 'chat', 'pinned', 'meta', 'folder_id')
    ordering = ('-updated_at',)

    def get_queryset(self, request):
        """
        خواندن چت‌ها از دیتابیس openwebui_db (جدول chat).
        اگر اتصال برقرار نباشد یا جدول وجود نداشته باشد، queryset خالی برمی‌گردانیم.
        """
        try:
            return super().get_queryset(request).using('openwebui_db')
        except OperationalError:
            self.message_user(
                request,
                "جدول chat در دیتابیس OpenWebUI یافت نشد یا اتصال برقرار نیست. تنظیمات openwebui_db را بررسی کنید.",
                level=messages.WARNING,
            )
            return self.model.objects.none()

    def title_short(self, obj):
        return (obj.title[:50] + '...') if obj.title and len(obj.title) > 50 else (obj.title or '-')
    title_short.short_description = 'عنوان'

    def created_at_ts(self, obj):
        if not obj.created_at:
            return '-'
        from datetime import datetime
        from django.utils import timezone as tz
        try:
            dt = datetime.fromtimestamp(obj.created_at)
            return tz.make_aware(dt, tz.get_current_timezone()).strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(obj.created_at)
    created_at_ts.short_description = 'ایجاد'

    def updated_at_ts(self, obj):
        if not obj.updated_at:
            return '-'
        from datetime import datetime
        from django.utils import timezone as tz
        try:
            dt = datetime.fromtimestamp(obj.updated_at)
            return tz.make_aware(dt, tz.get_current_timezone()).strftime('%Y-%m-%d %H:%M')
        except Exception:
            return str(obj.updated_at)
    updated_at_ts.short_description = 'به‌روزرسانی'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False