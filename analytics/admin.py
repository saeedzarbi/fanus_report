from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.core.management import call_command
from django.contrib import messages
from .models import ChatAnalysis

@admin.register(ChatAnalysis)
class AnalyticsAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'category', 'sentiment_score', 'is_risky', 'timestamp')
    list_filter = ('is_risky', 'category', 'timestamp')
    search_fields = ('user_id', 'summary')
    ordering = ('-timestamp',)
    
    change_list_template = "admin/analytics_change_list.html"

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST" and "run_analysis" in request.POST:
            try:
                call_command('run_nightly_analysis')
                self.message_user(request, "تحلیل با موفقیت انجام شد.", messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"خطا در اجرا: {e}", messages.ERROR)
                
        return super().changelist_view(request, extra_context=extra_context)