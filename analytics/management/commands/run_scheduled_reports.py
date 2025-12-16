from django.core.management.base import BaseCommand
from analytics.models import ReportSchedule, Report, ReportType
from analytics.services import ReportGenerationService
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'اجرای گزارش‌های زمانبندی شده'

    def add_arguments(self, parser):
        parser.add_argument('--schedule-id', type=int, help='شناسه زمانبندی خاص برای اجرا')

    def handle(self, *args, **options):
        self.stdout.write("🚀 شروع اجرای گزارش‌های زمانبندی شده...")

        schedule_id = options.get('schedule_id')
        
        if schedule_id:
            schedules = ReportSchedule.objects.filter(id=schedule_id, is_active=True)
        else:
            schedules = ReportSchedule.objects.filter(is_active=True)

        if not schedules.exists():
            self.stdout.write(self.style.WARNING("⚠️ هیچ زمانبندی فعالی یافت نشد."))
            return

        service = ReportGenerationService()

        for schedule in schedules:
            self.stdout.write(f"📋 در حال پردازش زمانبندی: {schedule.name}")

            end_date = timezone.now()
            
            if schedule.period == 'daily':
                start_date = end_date - timedelta(days=1)
            elif schedule.period == 'weekly':
                start_date = end_date - timedelta(weeks=1)
            elif schedule.period == 'monthly':
                start_date = end_date - timedelta(days=30)
            else:
                continue

            report = Report.objects.create(
                name=f"{schedule.name} - {end_date.strftime('%Y-%m-%d')}",
                report_type=schedule.report_type,
                period=schedule.period,
                start_date=start_date,
                end_date=end_date,
                task=schedule.task,
                status='pending'
            )

            if schedule.employees.exists():
                report.employees.set(schedule.employees.all())
            
            if schedule.groups.exists():
                report.groups.set(schedule.groups.all())

            self.stdout.write(f"📊 در حال تولید گزارش: {report.name}")
            
            success = service.process_report(report)
            
            if success:
                self.stdout.write(self.style.SUCCESS(f"✅ گزارش {report.name} با موفقیت تولید شد."))
                schedule.last_run = timezone.now()
                schedule.save()
            else:
                self.stdout.write(self.style.ERROR(f"❌ خطا در تولید گزارش {report.name}."))

        self.stdout.write("🏁 پایان اجرای گزارش‌ها.")