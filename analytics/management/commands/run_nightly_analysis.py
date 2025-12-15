from django.core.management.base import BaseCommand
from analytics.models import SourceChat, ChatAnalysis
from analytics.services import analyze_text_with_ollama
from django.db.utils import OperationalError

class Command(BaseCommand):
    help = 'اجرای تحلیل روی چت‌های جدید'

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 شروع فرایند تحلیل...")

        try:
            raw_chats = SourceChat.objects.using('openwebui_db').all().order_by('-created_at')[:20]
        except OperationalError:
            self.stdout.write(self.style.ERROR("❌ خطا در اتصال به دیتابیس OpenWebUI. تنظیمات را چک کنید."))
            return

        for chat in raw_chats:
            if ChatAnalysis.objects.filter(source_chat_id=chat.id).exists():
                continue

            self.stdout.write(f"Analyzing chat {chat.id}...")
            
            result = analyze_text_with_ollama(chat.content)
            
            if result:
                ChatAnalysis.objects.create(
                    source_chat_id=chat.id,
                    user_id=chat.user_id,
                    sentiment_score=result.get('sentiment_score', 5),
                    category=result.get('category', 'Unknown'),
                    is_risky=result.get('is_risky', False),
                    summary=result.get('summary', '')
                )
                self.stdout.write(self.style.SUCCESS(f"✅ Saved: {chat.user_id}"))
            else:
                self.stdout.write(self.style.WARNING("Skipped due to AI error"))

        self.stdout.write("🏁 پایان تحلیل.")