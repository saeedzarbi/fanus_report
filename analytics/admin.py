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
from .services import ReportGenerationService

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_id', 'department', 'is_active', 'created_at')
    list_filter = ('is_active', 'department', 'created_at')
    search_fields = ('name', 'user_id', 'email')
    ordering = ('name',)

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