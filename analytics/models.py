from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class SourceChat(models.Model):
    id = models.CharField(primary_key=True, unique=True, max_length=255)
    user_id = models.CharField(max_length=255)
    title = models.TextField()
    share_id = models.CharField(unique=True, max_length=255, blank=True, null=True)
    archived = models.BooleanField()
    created_at = models.BigIntegerField()
    updated_at = models.BigIntegerField()
    
    chat = models.TextField(blank=True, null=True) 
    
    pinned = models.BooleanField(blank=True, null=True)
    meta = models.TextField() 
    folder_id = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'chat' 
        app_label = 'analytics'

class SourceUser(models.Model):
    """
    مدل خواندن‌-only از جدول user دیتابیس OpenWebUI.
    توجه: جدول user در OpenWebUI ممکن است ستون is_active نداشته باشد؛
    is_active به صورت property و همیشه True است.
    """
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255, blank=True, null=True, verbose_name="نام")
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name="نام کاربری")
    email = models.EmailField(blank=True, null=True, verbose_name="ایمیل")
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    # is_active در جدول user OpenWebUI وجود ندارد؛ برای سازگاری با ادمین/سرویس به صورت property
    # اگر نسخهٔ OpenWebUI شما ستون is_active دارد، می‌توانید دوباره فیلد مدل اضافه کنید.

    class Meta:
        managed = True
        db_table = 'user'
        app_label = 'analytics'

    @property
    def is_active(self):
        """جدول user در OpenWebUI این ستون را ندارد؛ مقدار پیش‌فرض."""
        return True

class ChatSyncState(models.Model):
    """ذخیره زمان آخرین سینک چت‌ها برای سینک افزایشی"""
    key = models.CharField(max_length=50, unique=True, default='default', verbose_name="کلید")
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name="آخرین زمان سینک")

    class Meta:
        verbose_name = "وضعیت سینک چت"
        verbose_name_plural = "وضعیت سینک چت‌ها"

    def __str__(self):
        return f"آخرین سینک: {self.last_sync_at}"


class SyncedChat(models.Model):
    """کپی محلی چت‌های سینک‌شده از OpenWebUI (از آخرین زمان به‌روزرسانی)"""
    id = models.CharField(primary_key=True, max_length=255, verbose_name="شناسه چت")
    user_id = models.CharField(max_length=255, verbose_name="کاربر")
    title = models.TextField(blank=True, verbose_name="عنوان")
    chat = models.TextField(blank=True, null=True, verbose_name="محتوای چت (JSON)")
    created_at = models.BigIntegerField(default=0, verbose_name="زمان ایجاد در منبع")
    updated_at = models.BigIntegerField(default=0, verbose_name="زمان به‌روزرسانی در منبع")
    synced_at = models.DateTimeField(auto_now=True, verbose_name="زمان سینک در سیستم")

    class Meta:
        verbose_name = "چت سینک‌شده"
        verbose_name_plural = "چت‌های سینک‌شده"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user_id} - {self.title[:30] if self.title else self.id}"


class Employee(models.Model):
    user_id = models.CharField(max_length=255, unique=True, verbose_name="شناسه کاربر")
    name = models.CharField(max_length=255, verbose_name="نام")
    email = models.EmailField(blank=True, null=True, verbose_name="ایمیل")
    department = models.CharField(max_length=100, blank=True, null=True, verbose_name="دپارتمان")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "کارمند"
        verbose_name_plural = "کارمندان"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.user_id})"

class UserGroup(models.Model):
    name = models.CharField(max_length=255, verbose_name="نام گروه")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    employees = models.ManyToManyField(Employee, blank=True, verbose_name="کارمندان")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "گروه کاربران"
        verbose_name_plural = "گروه‌های کاربران"

    def __str__(self):
        return self.name

class AnalysisTask(models.Model):
    TASK_TYPE_CHOICES = [
        ('chat_analysis', 'تحلیل چت'),
        ('future_prediction', 'پیش‌بینی آینده'),
    ]
    
    name = models.CharField(max_length=255, verbose_name="نام تسک")
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES, verbose_name="نوع تسک")
    prompt_template = models.TextField(verbose_name="قالب پرامپت")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    cron_schedule = models.CharField(max_length=100, verbose_name="زمانبندی Cron")
    last_run = models.DateTimeField(null=True, blank=True, verbose_name="آخرین اجرا")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "تسک تحلیل"
        verbose_name_plural = "تسک‌های تحلیل"

    def __str__(self):
        return f"{self.name} ({self.get_task_type_display()})"

class ChatAnalysis(models.Model):
    source_chat_id = models.CharField(max_length=255, unique=True, verbose_name="شناسه چت اصلی")
    user_id = models.CharField(max_length=255, verbose_name="کاربر")
    task = models.ForeignKey(AnalysisTask, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="تسک")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="زمان تحلیل")
    
    sentiment_score = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)], verbose_name="امتیاز احساس (۱-۱۰)")
    category = models.CharField(max_length=100, verbose_name="دسته‌بندی موضوعی")
    is_risky = models.BooleanField(default=False, verbose_name="ریسک امنیتی/رفتاری")
    summary = models.TextField(verbose_name="خلاصه تحلیل")
    raw_analysis = models.JSONField(default=dict, blank=True, verbose_name="تحلیل خام")

    class Meta:
        verbose_name = "گزارش تحلیل رفتار"
        verbose_name_plural = "گزارش‌های تحلیل رفتار"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user_id} - {self.category}"

class ReportType(models.Model):
    REPORT_TYPE_CHOICES = [
        ('chat_analysis', 'گزارش کلی چت‌ها'),
        ('future_prediction', 'گزارش پیش‌بینی آینده'),
    ]
    
    name = models.CharField(max_length=255, verbose_name="نام نوع گزارش")
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES, verbose_name="نوع گزارش")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "نوع گزارش"
        verbose_name_plural = "انواع گزارش"

    def __str__(self):
        return self.name

class Report(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'روزانه'),
        ('weekly', 'هفتگی'),
        ('monthly', 'ماهانه'),
        ('custom', 'سفارشی'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'خطا'),
    ]
    
    name = models.CharField(max_length=255, verbose_name="نام گزارش")
    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE, verbose_name="نوع گزارش")
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default='daily', verbose_name="دوره")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    
    start_date = models.DateTimeField(verbose_name="تاریخ شروع")
    end_date = models.DateTimeField(verbose_name="تاریخ پایان")
    
    employees = models.ManyToManyField(Employee, blank=True, verbose_name="کارمندان")
    groups = models.ManyToManyField(UserGroup, blank=True, verbose_name="گروه‌ها")
    
    task = models.ForeignKey(AnalysisTask, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="تسک تحلیل")
    
    generated_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تولید")
    generated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="تولید شده توسط")
    
    report_data = models.JSONField(default=dict, blank=True, verbose_name="داده‌های گزارش")
    summary = models.TextField(blank=True, verbose_name="خلاصه گزارش")
    file_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="مسیر فایل")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین بروزرسانی")

    class Meta:
        verbose_name = "گزارش"
        verbose_name_plural = "گزارش‌ها"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_period_display()}"

class ReportSchedule(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'روزانه'),
        ('weekly', 'هفتگی'),
        ('monthly', 'ماهانه'),
    ]
    
    name = models.CharField(max_length=255, verbose_name="نام زمانبندی")
    report_type = models.ForeignKey(ReportType, on_delete=models.CASCADE, verbose_name="نوع گزارش")
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES, verbose_name="دوره")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    
    employees = models.ManyToManyField(Employee, blank=True, verbose_name="کارمندان")
    groups = models.ManyToManyField(UserGroup, blank=True, verbose_name="گروه‌ها")
    
    task = models.ForeignKey(AnalysisTask, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="تسک تحلیل")
    
    cron_schedule = models.CharField(max_length=100, verbose_name="زمانبندی Cron")
    last_run = models.DateTimeField(null=True, blank=True, verbose_name="آخرین اجرا")
    next_run = models.DateTimeField(null=True, blank=True, verbose_name="اجرای بعدی")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "زمانبندی گزارش"
        verbose_name_plural = "زمانبندی‌های گزارش"

    def __str__(self):
        return f"{self.name} - {self.get_period_display()}"