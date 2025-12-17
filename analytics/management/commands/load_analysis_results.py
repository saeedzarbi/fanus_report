from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import models
from datetime import timedelta
import random
from analytics.models import (
    Employee, AnalysisTask, ChatAnalysis, 
    ReportType, Report
)

class Command(BaseCommand):
    help = 'ساخت و ذخیره نتایج تحلیل mock'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='تعداد تحلیل‌های mock که باید ایجاد شود'
        )
        parser.add_argument(
            '--reports',
            type=int,
            default=10,
            help='تعداد گزارش‌های mock که باید ایجاد شود'
        )

    def handle(self, *args, **options):
        count = options['count']
        reports_count = options['reports']
        
        self.stdout.write("🚀 شروع ساخت نتایج تحلیل mock...")

        # ایجاد تحلیل‌های چت
        analyses_created = self.create_chat_analyses(count)
        self.stdout.write(self.style.SUCCESS(f'✅ {analyses_created} تحلیل چت ایجاد شد'))

        # ایجاد گزارش‌ها
        reports_created = self.create_reports(reports_count)
        self.stdout.write(self.style.SUCCESS(f'✅ {reports_created} گزارش ایجاد شد'))

        self.stdout.write(self.style.SUCCESS('\n🏁 ساخت نتایج تحلیل با موفقیت انجام شد!'))

    def create_chat_analyses(self, count):
        """ایجاد تحلیل‌های چت mock"""
        
        # دریافت کارمندان و تسک‌ها
        employees = list(Employee.objects.all())
        tasks = list(AnalysisTask.objects.filter(task_type='chat_analysis'))
        
        if not employees:
            self.stdout.write(self.style.WARNING('⚠️  هیچ کارمندی وجود ندارد. ابتدا load_initial_data را اجرا کنید.'))
            return 0
        
        if not tasks:
            self.stdout.write(self.style.WARNING('⚠️  هیچ تسک تحلیلی وجود ندارد.'))
            task = None
        else:
            task = tasks[0]

        # دسته‌بندی‌های ممکن
        categories = ['Technical', 'HR', 'Casual', 'Security', 'Management', 'Support']
        
        # خلاصه‌های نمونه
        summaries_positive = [
            "کاربر در مورد پروژه جدید سوال کرده و علاقه‌مند به مشارکت است.",
            "بحث سازنده در مورد بهبود فرآیندهای تیمی.",
            "درخواست کمک برای حل مشکل فنی با رویکرد مثبت.",
            "به اشتراک‌گذاری ایده‌های نوآورانه برای بهبود محصول.",
            "پیگیری وظایف محوله با انگیزه بالا.",
        ]
        
        summaries_neutral = [
            "سوال در مورد جزئیات پروژه و تاریخچه تحویل.",
            "درخواست اطلاعات در مورد سیاست‌های سازمان.",
            "هماهنگی جلسه با اعضای تیم.",
            "پیگیری وضعیت درخواست قبلی.",
            "بحث در مورد جزئیات فنی پروژه.",
        ]
        
        summaries_negative = [
            "ابراز نارضایتی از فرآیندهای طولانی تصمیم‌گیری.",
            "شکایت از کمبود منابع برای انجام وظایف.",
            "بیان نگرانی از فشار کاری زیاد.",
            "انتقاد از کیفیت ارتباطات درون تیمی.",
            "ابراز سردرگمی در مورد اهداف پروژه.",
        ]
        
        summaries_risky = [
            "⚠️ بحث در مورد دسترسی غیرمجاز به سیستم‌ها.",
            "⚠️ به اشتراک‌گذاری اطلاعات محرمانه شرکت.",
            "⚠️ صحبت در مورد تغییر شغل و ترک سازمان.",
            "⚠️ نارضایتی شدید از مدیریت و سیاست‌های شرکت.",
            "⚠️ درخواست دسترسی به داده‌های حساس بدون مجوز.",
        ]

        created_count = 0
        now = timezone.now()

        for i in range(count):
            # انتخاب تصادفی کارمند
            employee = random.choice(employees)
            
            # تعیین نوع تحلیل (70% مثبت/خنثی، 30% منفی/ریسکی)
            is_risky = random.random() < 0.1  # 10% احتمال ریسکی
            is_negative = random.random() < 0.2  # 20% احتمال منفی
            
            if is_risky:
                sentiment = random.randint(1, 3)
                category = random.choice(['Security', 'HR', 'Management'])
                summary = random.choice(summaries_risky)
            elif is_negative:
                sentiment = random.randint(3, 5)
                category = random.choice(categories)
                summary = random.choice(summaries_negative)
            elif random.random() < 0.5:
                sentiment = random.randint(5, 7)
                category = random.choice(categories)
                summary = random.choice(summaries_neutral)
            else:
                sentiment = random.randint(7, 10)
                category = random.choice(categories)
                summary = random.choice(summaries_positive)

            # زمان تصادفی در 30 روز گذشته
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            timestamp = now - timedelta(days=days_ago, hours=hours_ago)

            # ساخت داده‌های تحلیل خام
            raw_analysis = {
                "sentiment_score": sentiment,
                "category": category,
                "is_risky": is_risky,
                "summary": summary,
                "analyzed_at": timestamp.isoformat(),
                "confidence": round(random.uniform(0.7, 0.99), 2),
                "keywords": random.sample([
                    "پروژه", "تیم", "مدیریت", "فنی", "کیفیت", 
                    "زمان", "منابع", "هدف", "عملکرد", "ارتباط"
                ], k=random.randint(2, 5))
            }

            # ایجاد source_chat_id یکتا
            source_chat_id = f"chat_{employee.user_id}_{i}_{int(timestamp.timestamp())}"

            try:
                analysis, created = ChatAnalysis.objects.get_or_create(
                    source_chat_id=source_chat_id,
                    defaults={
                        'user_id': employee.user_id,
                        'task': task,
                        'sentiment_score': sentiment,
                        'category': category,
                        'is_risky': is_risky,
                        'summary': summary,
                        'raw_analysis': raw_analysis,
                        'timestamp': timestamp
                    }
                )
                
                if created:
                    created_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ خطا در ایجاد تحلیل: {e}'))

        return created_count

    def create_reports(self, count):
        """ایجاد گزارش‌های mock"""
        
        report_types = list(ReportType.objects.all())
        employees = list(Employee.objects.all())
        tasks = list(AnalysisTask.objects.all())
        
        if not report_types:
            self.stdout.write(self.style.WARNING('⚠️  هیچ نوع گزارشی وجود ندارد.'))
            return 0

        created_count = 0
        now = timezone.now()

        for i in range(count):
            report_type = random.choice(report_types)
            task = random.choice(tasks) if tasks else None
            
            # دوره تصادفی
            period = random.choice(['daily', 'weekly', 'monthly'])
            
            # وضعیت تصادفی (بیشتر completed)
            status_choices = ['completed'] * 7 + ['processing', 'pending', 'failed']
            status = random.choice(status_choices)
            
            # تاریخ‌های شروع و پایان
            days_ago = random.randint(1, 60)
            start_date = now - timedelta(days=days_ago)
            
            if period == 'daily':
                end_date = start_date + timedelta(days=1)
            elif period == 'weekly':
                end_date = start_date + timedelta(days=7)
            else:
                end_date = start_date + timedelta(days=30)

            # نام گزارش
            name = f"گزارش {report_type.name} - {start_date.strftime('%Y/%m/%d')}"

            # داده‌های گزارش
            analyses = ChatAnalysis.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            )
            
            total_analyses = analyses.count()
            risky_count = analyses.filter(is_risky=True).count()
            avg_sentiment = analyses.aggregate(
                avg=models.Avg('sentiment_score')
            )['avg'] or 5.0

            report_data = {
                "total_analyses": total_analyses,
                "risky_analyses": risky_count,
                "average_sentiment": round(avg_sentiment, 2),
                "period": period,
                "categories": dict(
                    analyses.values_list('category').annotate(
                        count=models.Count('id')
                    )
                ),
                "generated_at": now.isoformat()
            }

            summary = f"""
گزارش {period} از {start_date.strftime('%Y/%m/%d')} تا {end_date.strftime('%Y/%m/%d')}

📊 آمار کلی:
- تعداد تحلیل‌ها: {total_analyses}
- تحلیل‌های ریسکی: {risky_count}
- میانگین احساس: {avg_sentiment:.1f}/10

{'⚠️ نیاز به توجه: تعداد بالای تحلیل‌های ریسکی' if risky_count > total_analyses * 0.15 else '✅ وضعیت مناسب'}
            """.strip()

            try:
                report = Report.objects.create(
                    name=name,
                    report_type=report_type,
                    period=period,
                    status=status,
                    start_date=start_date,
                    end_date=end_date,
                    task=task,
                    generated_at=now if status == 'completed' else None,
                    report_data=report_data,
                    summary=summary
                )
                
                # اضافه کردن کارمندان تصادفی
                if employees:
                    selected_employees = random.sample(
                        employees, 
                        k=min(random.randint(1, 5), len(employees))
                    )
                    report.employees.set(selected_employees)
                
                created_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ خطا در ایجاد گزارش: {e}'))

        return created_count

