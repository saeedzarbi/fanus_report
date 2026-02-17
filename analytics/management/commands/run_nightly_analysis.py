from django.core.management.base import BaseCommand
from django.conf import settings
from analytics.models import ChatAnalysis, AnalysisTask
from analytics.services import OllamaService, OpenWebUIService
from django.db.utils import OperationalError
from django.utils import timezone

class Command(BaseCommand):
    help = 'اجرای تحلیل روی چت‌های جدید بر اساس تسک‌های فعال'

    def add_arguments(self, parser):
        parser.add_argument('--task-id', type=int, help='شناسه تسک خاص برای اجرا')
        parser.add_argument('--limit', type=int, default=50, help='تعداد چت‌های تحلیل شده')

    def handle(self, *args, **options):
        self.stdout.write("🚀 شروع فرایند تحلیل...")

        task_id = options.get('task_id')
        limit = options.get('limit', 50)
        use_mock = getattr(settings, 'USE_MOCK_DATA', False)

        if task_id:
            tasks = AnalysisTask.objects.filter(id=task_id, is_active=True)
        else:
            tasks = AnalysisTask.objects.filter(is_active=True)

        if not tasks.exists():
            self.stdout.write(self.style.WARNING("⚠️ هیچ تسک فعالی یافت نشد."))
            return

        ollama = OllamaService()
        openwebui = OpenWebUIService()

        for task in tasks:
            self.stdout.write(f"📋 در حال پردازش تسک: {task.name}")

            if use_mock:
                raw_chats = openwebui.get_chats(limit=limit)
            else:
                try:
                    from analytics.models import SourceChat
                    raw_chats = SourceChat.objects.using('openwebui_db').all().order_by('-created_at')[:limit]
                except OperationalError:
                    self.stdout.write(self.style.ERROR("❌ خطا در اتصال به دیتابیس OpenWebUI."))
                    continue

            analyzed_count = 0
            for chat in raw_chats:
                chat_updated_at = getattr(chat, 'updated_at', None) or 0
                existing = ChatAnalysis.objects.filter(source_chat_id=chat.id, task=task).first()
                if existing and (existing.source_chat_updated_at or 0) >= chat_updated_at:
                    continue
                content = getattr(chat, 'content', None) or (getattr(chat, 'chat', '') or '')[:2000]
                if not content:
                    continue
                result = ollama.analyze_text(content, task.prompt_template)
                if result:
                    ChatAnalysis.objects.update_or_create(
                        source_chat_id=chat.id,
                        defaults={
                            'user_id': chat.user_id,
                            'task': task,
                            'sentiment_score': result.get('sentiment_score', 5),
                            'category': result.get('category', 'Unknown'),
                            'is_risky': result.get('is_risky', False),
                            'summary': result.get('summary', ''),
                            'raw_analysis': result,
                            'source_chat_updated_at': chat_updated_at,
                        },
                    )
                    analyzed_count += 1
                    self.stdout.write(self.style.SUCCESS(f"✅ تحلیل شد: {chat.user_id}"))

            task.last_run = timezone.now()
            task.save()
            self.stdout.write(f"✅ تسک {task.name} تکمیل شد. تعداد تحلیل شده: {analyzed_count}")

        self.stdout.write("🏁 پایان تحلیل.")