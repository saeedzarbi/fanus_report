import random
from datetime import datetime, timedelta
import pytz
from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import Employee, UserGroup, ChatAnalysis, AnalysisTask

class Command(BaseCommand):
    help = 'پر کردن دیتابیس با داده‌های تستی هوشمند برای متابیس'

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 شروع عملیات تولید داده...")

        # 1. ساخت تسک‌ها
        task, _ = AnalysisTask.objects.get_or_create(
            name="تحلیل شبانه",
            defaults={'task_type': 'chat_analysis', 'cron_schedule': '0 0 * * *'}
        )

        # 2. ساخت گروه‌ها
        groups_data = {
            'تیم فنی': 'Technical',
            'تیم فروش': 'Sales',
            'منابع انسانی': 'HR'
        }
        groups = {}
        for fa_name, code in groups_data.items():
            g, _ = UserGroup.objects.get_or_create(name=fa_name)
            groups[code] = g

        # 3. ساخت کارمندان
        employees_list = [
            ('ali_rezaei', 'علی رضایی', 'Technical'),
            ('sara_m', 'سارا محمدی', 'Sales'),
            ('mohsen_y', 'محسن یگانه', 'Technical'),
            ('maryam_k', 'مریم کاویانی', 'HR'),
            ('reza_p', 'رضا پناهی', 'Sales'),
            ('admin_sys', 'ادمین سیستم', 'Technical'),
            ('neda_a', 'ندا آقایی', 'HR'),
            ('kaveh_b', 'کاوه بیات', 'Sales'),
        ]

        db_employees = []
        for user_id, name, dept in employees_list:
            emp, created = Employee.objects.get_or_create(
                user_id=user_id,
                defaults={'name': name, 'department': dept, 'email': f"{user_id}@fanus.local"}
            )
            # اتصال به گروه
            groups[dept].employees.add(emp)
            db_employees.append(emp)

        # 4. تولید چت‌ها (برای ۳۰ روز گذشته)
        categories = ['مشکل فنی', 'حقوق و دستمزد', 'شکایت', 'پیشنهاد', 'گپ عمومی', 'امنیتی']
        summaries = [
            "سیستم قطع شده است.", "چرا فیش حقوقی صادر نشد؟", "کولر اتاق گرم است.",
            "ناهار امروز عالی بود.", "دسترسی به سرور قطع شده.", "درخواست مرخصی."
        ]

        # پاک کردن داده‌های قبلی برای تمیز شدن نمودار
        ChatAnalysis.objects.all().delete()
        
        records = []
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)

        current_date = start_date
        while current_date <= end_date:
            # ایجاد روزانه ۱۰ تا ۳۰ چت تصادفی
            daily_count = random.randint(10, 30)
            
            for _ in range(daily_count):
                emp = random.choice(db_employees)
                cat = random.choice(categories)
                
                # منطق هوشمند برای واقعی کردن نمودار:
                # اگر دسته "امنیتی" یا "شکایت" بود، امتیاز پایین (خشمگین) باشد
                if cat in ['امنیتی', 'شکایت']:
                    score = random.randint(1, 4)
                    is_risky = True if score < 3 else False
                elif cat == 'مشکل فنی':
                    score = random.randint(3, 6)
                    is_risky = False
                else:
                    score = random.randint(6, 10)
                    is_risky = False

                # شنبه‌ها همه عصبانی‌ترند! (کاهش امتیاز تصادفی)
                if current_date.weekday() == 5: # Saturday
                    score = max(1, score - 1)

                records.append(ChatAnalysis(
                    source_chat_id=f"msg_{current_date.strftime('%Y%m%d')}_{random.randint(1000,9999)}",
                    user_id=emp.user_id,
                    task=task,
                    timestamp=current_date + timedelta(hours=random.randint(8, 18)), # ساعات کاری
                    sentiment_score=score,
                    category=cat,
                    is_risky=is_risky,
                    summary=random.choice(summaries)
                ))
            
            current_date += timedelta(days=1)

        ChatAnalysis.objects.bulk_create(records)
        
        self.stdout.write(self.style.SUCCESS(f"✅ با موفقیت {len(records)} رکورد تحلیل، {len(db_employees)} کارمند و ۳ گروه ساخته شد."))