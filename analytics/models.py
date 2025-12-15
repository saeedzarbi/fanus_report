from django.db import models

# Create your models here.
from django.db import models

class SourceChat(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    user_id = models.CharField(max_length=255)
    content = models.TextField()  
    created_at = models.BigIntegerField() 

    class Meta:
        managed = False  
        db_table = 'chat'  
        app_label = 'analytics'

class ChatAnalysis(models.Model):
    source_chat_id = models.CharField(max_length=255, unique=True, verbose_name="شناسه چت اصلی")
    user_id = models.CharField(max_length=255, verbose_name="کاربر")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="زمان تحلیل")
    
    sentiment_score = models.IntegerField(default=5, verbose_name="امتیاز احساس (۱-۱۰)")
    category = models.CharField(max_length=100, verbose_name="دسته‌بندی موضوعی")
    is_risky = models.BooleanField(default=False, verbose_name="ریسک امنیتی/رفتاری")
    summary = models.TextField(verbose_name="خلاصه تحلیل")

    class Meta:
        verbose_name = "گزارش تحلیل رفتار"
        verbose_name_plural = "گزارش‌های تحلیل رفتار"

    def __str__(self):
        return f"{self.user_id} - {self.category}"