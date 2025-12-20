from django.contrib import admin
from django.core.management import call_command
from django.contrib import messages
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import (
    Employee, UserGroup, AnalysisTask, ChatAnalysis, 
    ReportType, Report, ReportSchedule
)
from .services import ReportGenerationService, UserSyncService

# پیام‌های ثابت
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
        'sync_users_delete_action'
    ]
    
    def changelist_view(self, request, extra_context=None):
        """افزودن دکمه‌های سینک در بالای لیست"""
        extra_context = extra_context or {}
        
        # اضافه کردن اطلاعات سینک به context
        sync_service = UserSyncService()
        summary = sync_service.get_sync_summary()
        extra_context['sync_summary'] = summary
        
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