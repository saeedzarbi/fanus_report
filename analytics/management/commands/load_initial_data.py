from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from analytics.models import (
    Employee, UserGroup, AnalysisTask, ReportType, 
    Report, ReportSchedule
)

class Command(BaseCommand):
    help = 'بارگذاری داده‌های اولیه و mock'

    def handle(self, *args, **options):
        self.stdout.write("🚀 شروع بارگذاری داده‌های اولیه...")

        employees_created = self.create_employees()
        self.stdout.write(self.style.SUCCESS(f'✅ {employees_created} کارمند ایجاد شد'))

        groups_created = self.create_user_groups()
        self.stdout.write(self.style.SUCCESS(f'✅ {groups_created} گروه کاربری ایجاد شد'))

        report_types_created = self.create_report_types()
        self.stdout.write(self.style.SUCCESS(f'✅ {report_types_created} نوع گزارش ایجاد شد'))

        tasks_created = self.create_analysis_tasks()
        self.stdout.write(self.style.SUCCESS(f'✅ {tasks_created} تسک تحلیل ایجاد شد'))

        schedules_created = self.create_report_schedules()
        self.stdout.write(self.style.SUCCESS(f'✅ {schedules_created} زمانبندی ایجاد شد'))

        self.stdout.write(self.style.SUCCESS('\n🏁 بارگذاری داده‌ها با موفقیت انجام شد!'))

    def create_employees(self):
        employees_data = [
            {"user_id": "user_1", "name": "علی احمدی", "email": "ali@example.com", "department": "فناوری"},
            {"user_id": "user_2", "name": "سارا محمدی", "email": "sara@example.com", "department": "منابع انسانی"},
            {"user_id": "user_3", "name": "حسین رضایی", "email": "hossein@example.com", "department": "فناوری"},
            {"user_id": "user_4", "name": "فاطمه کریمی", "email": "fatemeh@example.com", "department": "پشتیبانی"},
            {"user_id": "user_5", "name": "محمد حسینی", "email": "mohammad@example.com", "department": "مدیریت"},
        ]

        count = 0
        for emp_data in employees_data:
            employee, created = Employee.objects.get_or_create(
                user_id=emp_data["user_id"],
                defaults={
                    "name": emp_data["name"],
                    "email": emp_data["email"],
                    "department": emp_data["department"],
                    "is_active": True
                }
            )
            if created:
                count += 1

        return count

    def create_user_groups(self):
        groups_data = [
            {
                "name": "تیم فناوری",
                "description": "کارمندان بخش فناوری اطلاعات",
                "user_ids": ["user_1", "user_3"]
            },
            {
                "name": "تیم مدیریت",
                "description": "مدیران و سرپرستان",
                "user_ids": ["user_5"]
            },
            {
                "name": "تیم پشتیبانی",
                "description": "کارمندان بخش پشتیبانی",
                "user_ids": ["user_4"]
            },
        ]

        count = 0
        for group_data in groups_data:
            group, created = UserGroup.objects.get_or_create(
                name=group_data["name"],
                defaults={"description": group_data["description"]}
            )
            
            if created:
                count += 1
                employees = Employee.objects.filter(user_id__in=group_data["user_ids"])
                group.employees.set(employees)

        return count

    def create_report_types(self):
        report_types_data = [
            {
                "name": "گزارش تحلیل چت‌ها",
                "report_type": "chat_analysis",
                "description": "تحلیل کلی از چت‌ها و ارتباطات کارمندان"
            },
            {
                "name": "گزارش پیش‌بینی رفتاری",
                "report_type": "future_prediction",
                "description": "پیش‌بینی الگوهای رفتاری و ریسک‌های آینده"
            },
        ]

        count = 0
        for rt_data in report_types_data:
            report_type, created = ReportType.objects.get_or_create(
                report_type=rt_data["report_type"],
                defaults={
                    "name": rt_data["name"],
                    "description": rt_data["description"],
                    "is_active": True
                }
            )
            if created:
                count += 1

        return count

    def create_analysis_tasks(self):
        tasks_data = [
            {
                "name": "تحلیل روزانه چت‌ها",
                "task_type": "chat_analysis",
                "cron_schedule": "0 2 * * *",
                "prompt_template": """تحلیل پیام کاربر به فارسی.
خروجی فقط JSON معتبر با کلیدهای:
"sentiment_score" (1-10),
"category" (Technical/HR/Casual/Security),
"is_risky" (boolean),
"summary" (خلاصه به فارسی)."""
            },
            {
                "name": "پیش‌بینی رفتار هفتگی",
                "task_type": "future_prediction",
                "cron_schedule": "0 3 * * 0",
                "prompt_template": """بر اساس تاریخچه چت کاربر، رفتار آینده را پیش‌بینی کن.
خروجی فقط JSON معتبر با کلیدهای:
"predicted_topics" (لیست موضوعات),
"risk_level" (low/medium/high),
"recommendations" (لیست توصیه‌ها به فارسی),
"behavioral_trend" (improving/stable/declining),
"summary" (خلاصه به فارسی)."""
            },
        ]

        count = 0
        for task_data in tasks_data:
            task, created = AnalysisTask.objects.get_or_create(
                name=task_data["name"],
                defaults={
                    "task_type": task_data["task_type"],
                    "prompt_template": task_data["prompt_template"],
                    "cron_schedule": task_data["cron_schedule"],
                    "is_active": True
                }
            )
            if created:
                count += 1

        return count

    def create_report_schedules(self):
        schedules_data = [
            {
                "name": "گزارش روزانه تحلیل چت",
                "period": "daily",
                "cron_schedule": "0 6 * * *",
                "report_type": "chat_analysis"
            },
            {
                "name": "گزارش هفتگی پیش‌بینی",
                "period": "weekly",
                "cron_schedule": "0 8 * * 1",
                "report_type": "future_prediction"
            },
        ]

        count = 0
        for schedule_data in schedules_data:
            report_type = ReportType.objects.filter(
                report_type=schedule_data["report_type"]
            ).first()
            
            task = AnalysisTask.objects.filter(
                task_type=schedule_data["report_type"]
            ).first()

            if report_type:
                schedule, created = ReportSchedule.objects.get_or_create(
                    name=schedule_data["name"],
                    defaults={
                        "report_type": report_type,
                        "period": schedule_data["period"],
                        "cron_schedule": schedule_data["cron_schedule"],
                        "task": task,
                        "is_active": True
                    }
                )
                if created:
                    count += 1

        return count
