import requests
import json
import random
from django.conf import settings
from django.db import connections
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta
from .models import SourceChat, ChatAnalysis, Employee, Report, ReportType, AnalysisTask, UserGroup, SourceUser, ChatSyncState, SyncedChat
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def _log_truncated(log, prefix: str, text: str, max_len: int = 500):
    """برای چاپ در لاگ؛ متن طولانی را کوتاه می‌کند."""
    if not text:
        log.info("%s (خالی)", prefix)
        return
    s = text if len(text) <= max_len else text[:max_len] + "..."
    log.info("%s %s", prefix, s)

class MockSourceChat:
    def __init__(self, id, user_id, content, created_at, updated_at=None):
        self.id = id
        self.user_id = user_id
        self.content = content
        self.created_at = created_at
        self.updated_at = updated_at if updated_at is not None else created_at

class MockOpenWebUIService:
    MOCK_CHATS = [
        {"id": "chat_1", "user_id": "user_1", "content": "سلام، من نیاز به کمک در مورد سیستم دارم", "created_at": 1700000000},
        {"id": "chat_2", "user_id": "user_1", "content": "مشکلی در لاگین دارم، لطفا راهنمایی کنید", "created_at": 1700001000},
        {"id": "chat_3", "user_id": "user_2", "content": "گزارش ماهانه را کی می‌فرستید؟", "created_at": 1700002000},
        {"id": "chat_4", "user_id": "user_2", "content": "می‌خواهم اطلاعات محرمانه را به اشتراک بگذارم", "created_at": 1700003000},
        {"id": "chat_5", "user_id": "user_3", "content": "سلام، روز خوبی داشته باشید", "created_at": 1700004000},
        {"id": "chat_6", "user_id": "user_3", "content": "کد جدید را بررسی کردم، عالی است", "created_at": 1700005000},
        {"id": "chat_7", "user_id": "user_1", "content": "نیاز به دسترسی به دیتابیس دارم", "created_at": 1700006000},
        {"id": "chat_8", "user_id": "user_4", "content": "می‌خواهم رمز عبور را تغییر دهم", "created_at": 1700007000},
        {"id": "chat_9", "user_id": "user_4", "content": "سیستم کند کار می‌کند، باید بررسی شود", "created_at": 1700008000},
        {"id": "chat_10", "user_id": "user_2", "content": "لطفا فایل‌های حساس را پاک کنید", "created_at": 1700009000},
        {"id": "chat_11", "user_id": "user_5", "content": "پروژه جدید عالی پیش می‌رود", "created_at": 1700010000},
        {"id": "chat_12", "user_id": "user_5", "content": "می‌خواهم در مورد حقوق صحبت کنم", "created_at": 1700011000},
        {"id": "chat_13", "user_id": "user_1", "content": "سیستم امنیتی را بررسی کردم، همه چیز خوب است", "created_at": 1700012000},
        {"id": "chat_14", "user_id": "user_3", "content": "نیاز به آموزش دارم", "created_at": 1700013000},
        {"id": "chat_15", "user_id": "user_2", "content": "می‌خواهم به فایل‌های محرمانه دسترسی داشته باشم", "created_at": 1700014000},
    ]

    @staticmethod
    def get_chats(user_ids: Optional[List[str]] = None, start_date=None, end_date=None, limit=1000):
        chats = []
        for chat_data in MockOpenWebUIService.MOCK_CHATS:
            if user_ids and chat_data["user_id"] not in user_ids:
                continue
            
            chat_time = chat_data["created_at"]
            if start_date and chat_time < int(start_date.timestamp()):
                continue
            if end_date and chat_time > int(end_date.timestamp()):
                continue
            
            chats.append(MockSourceChat(
                id=chat_data["id"],
                user_id=chat_data["user_id"],
                content=chat_data["content"],
                created_at=chat_data["created_at"]
            ))
        
        return sorted(chats, key=lambda x: x.created_at, reverse=True)[:limit]

    @staticmethod
    def get_user_chats_count(user_id: str, start_date=None, end_date=None):
        count = 0
        for chat_data in MockOpenWebUIService.MOCK_CHATS:
            if chat_data["user_id"] != user_id:
                continue
            
            chat_time = chat_data["created_at"]
            if start_date and chat_time < int(start_date.timestamp()):
                continue
            if end_date and chat_time > int(end_date.timestamp()):
                continue
            
            count += 1
        return count

class MockOllamaService:
    CATEGORIES = ["Technical", "HR", "Casual", "Security"]
    SENTIMENT_KEYWORDS = {
        "positive": ["عالی", "خوب", "ممتاز", "عالی است", "خوب است"],
        "negative": ["مشکل", "خطا", "کند", "خراب", "بد"],
        "risky": ["محرمانه", "حساس", "پاک", "دسترسی", "رمز"]
    }

    def analyze_text(self, text: str, prompt_template: str = None) -> Optional[Dict]:
        text_lower = text.lower()
        
        sentiment_score = 5
        is_risky = False
        
        for keyword in self.SENTIMENT_KEYWORDS["positive"]:
            if keyword in text_lower:
                sentiment_score = random.randint(7, 10)
                break
        
        for keyword in self.SENTIMENT_KEYWORDS["negative"]:
            if keyword in text_lower:
                sentiment_score = random.randint(1, 4)
                break
        
        for keyword in self.SENTIMENT_KEYWORDS["risky"]:
            if keyword in text_lower:
                is_risky = True
                sentiment_score = random.randint(1, 5)
                break
        
        category = random.choice(self.CATEGORIES)
        if is_risky:
            category = "Security"
        
        summaries = {
            "Technical": "درخواست فنی مربوط به سیستم",
            "HR": "سوال یا درخواست منابع انسانی",
            "Casual": "گفتگوی عادی و غیررسمی",
            "Security": "هشدار امنیتی: درخواست مشکوک شناسایی شد"
        }
        
        return {
            "sentiment_score": sentiment_score,
            "category": category,
            "is_risky": is_risky,
            "summary": summaries.get(category, "تحلیل انجام شد")
        }

    def predict_future(self, user_chats: List[Dict], prompt_template: str = None) -> Optional[Dict]:
        total_chats = len(user_chats)
        risky_count = sum(1 for chat in user_chats if any(kw in chat.get('content', '').lower() for kw in self.SENTIMENT_KEYWORDS["risky"]))
        
        if risky_count > total_chats * 0.3:
            risk_level = "high"
            behavioral_trend = "declining"
        elif risky_count > total_chats * 0.1:
            risk_level = "medium"
            behavioral_trend = "stable"
        else:
            risk_level = "low"
            behavioral_trend = "improving"
        
        predicted_topics = ["تحلیل رفتاری", "الگوهای استفاده", "ریسک‌های امنیتی"]
        recommendations = [
            "نظارت منظم بر فعالیت‌های کاربر",
            "آموزش امنیت سایبری",
            "بررسی دسترسی‌های کاربر"
        ] if risk_level != "low" else [
            "ادامه نظارت عادی",
            "ارائه بازخورد مثبت"
        ]
        
        return {
            "predicted_topics": predicted_topics,
            "risk_level": risk_level,
            "recommendations": recommendations,
            "behavioral_trend": behavioral_trend,
            "summary": f"تحلیل رفتاری کاربر نشان می‌دهد سطح ریسک {risk_level} است و روند رفتاری {behavioral_trend} می‌باشد."
        }

import json


def _extract_chat_content_for_analysis(chat_history):
    """
    استخراج محتوای گفت‌وگو برای تحلیل از ساختارهای مختلف OpenWebUI.
    ترجیح: آخرین پیام کاربر؛ در غیر این صورت متن همهٔ پیام‌های کاربر؛ در نهایت کل گفت‌وگو.
    """
    def msg_text(m):
        return (m.get('content') or m.get('text') or '').strip()

    def msg_role(m):
        return (m.get('role') or '').lower()

    messages_ordered = []

    if isinstance(chat_history, list):
        messages_ordered = chat_history
    elif isinstance(chat_history, dict):
        if 'messages' in chat_history:
            msgs = chat_history['messages']
            if isinstance(msgs, list):
                messages_ordered = msgs
            elif isinstance(msgs, dict):
                # ساختار history با messages به صورت دیکشنری (key = id)
                messages_ordered = list(msgs.values())
        elif 'history' in chat_history:
            hist = chat_history['history']
            if isinstance(hist, dict) and 'messages' in hist:
                m = hist['messages']
                messages_ordered = list(m.values()) if isinstance(m, dict) else (m if isinstance(m, list) else [])

    if not messages_ordered:
        return ""

    # آخرین پیام کاربر
    for msg in reversed(messages_ordered):
        if msg_role(msg) == 'user':
            t = msg_text(msg)
            if t:
                return t

    # اگر پیام کاربر نبود، متن همهٔ پیام‌های کاربر را با هم ادغام کن
    user_texts = [msg_text(m) for m in messages_ordered if msg_role(m) == 'user' and msg_text(m)]
    if user_texts:
        return "\n".join(user_texts)

    # fallback: همهٔ پیام‌ها (user + assistant) برای تحلیل کلی
    all_texts = [msg_text(m) for m in messages_ordered if msg_text(m)]
    if all_texts:
        return "\n".join(all_texts)

    return ""


class OpenWebUIService:
    @staticmethod
    def get_chats(user_ids: Optional[List[str]] = None, start_date=None, end_date=None, limit=1000):
        if getattr(settings, 'USE_MOCK_DATA', False):
            return MockOpenWebUIService.get_chats(user_ids, start_date, end_date, limit)
        
        try:
            query = SourceChat.objects.using('openwebui_db').all()
            
            if user_ids:
                query = query.filter(user_id__in=user_ids)
            
            if start_date:
                # تبدیل تاریخ به Timestamp (چون created_at در دیتابیس شما BigInt است)
                query = query.filter(created_at__gte=int(start_date.timestamp()))
            
            if end_date:
                query = query.filter(created_at__lte=int(end_date.timestamp()))
            
            source_chats = query.order_by('-created_at')[:limit]
            
            # --- بخش مهم: استخراج پیام‌ها از JSON (سازگار با ساختارهای مختلف OpenWebUI) ---
            processed_chats = []
            for sc in source_chats:
                try:
                    # 1. پارس کردن فیلد chat (ممکن است از دیتابیس به صورت str یا از قبل dict/list برگردد)
                    raw_chat = sc.chat
                    if not raw_chat:
                        chat_history = []
                    elif isinstance(raw_chat, (dict, list)):
                        chat_history = raw_chat
                    else:
                        chat_history = json.loads(raw_chat)

                    # 2. استخراج محتوای قابل تحلیل از هر ساختار شناخته‌شده
                    content_to_analyze = _extract_chat_content_for_analysis(chat_history)

                    if content_to_analyze:
                        processed_chats.append(MockSourceChat(
                            id=sc.id,
                            user_id=sc.user_id,
                            content=content_to_analyze,
                            created_at=sc.created_at,
                            updated_at=getattr(sc, 'updated_at', sc.created_at) or sc.created_at,
                        ))
                except Exception as json_err:
                    logger.warning(f"Error parsing chat JSON for {sc.id}: {json_err}")
                    continue

            return processed_chats

        except Exception as e:
            logger.error(f"خطا در دریافت چت‌ها از OpenWebUI: {e}")
            return []

    @staticmethod
    def get_user_chats_count(user_id: str, start_date=None, end_date=None):
        if getattr(settings, 'USE_MOCK_DATA', False):
            return MockOpenWebUIService.get_user_chats_count(user_id, start_date, end_date)
        
        try:
            query = SourceChat.objects.using('openwebui_db').filter(user_id=user_id)
            
            if start_date:
                query = query.filter(created_at__gte=int(start_date.timestamp()))
            
            if end_date:
                query = query.filter(created_at__lte=int(end_date.timestamp()))
            
            return query.count()
        except Exception as e:
            logger.error(f"خطا در شمارش چت‌های کاربر: {e}")
            return 0

class OllamaService:
    def __init__(self, base_url="http://localhost:11434", model="qwen2.5:14b"):
        self.base_url = base_url
        self.model = model
        self.use_mock = getattr(settings, 'USE_MOCK_DATA', False)
        if self.use_mock:
            self.mock_service = MockOllamaService()

    def analyze_text(self, text: str, prompt_template: str = None) -> Optional[Dict]:
        if self.use_mock:
            return self.mock_service.analyze_text(text, prompt_template)
        
        url = f"{self.base_url}/api/generate"
        
        if prompt_template:
            system_instruction = prompt_template
        else:
            system_instruction = """
            You are an AI analyst. Analyze the employee's chat message.
            Output ONLY strictly valid JSON with keys: 
            "sentiment_score" (1-10), 
            "category" (Technical/HR/Casual/Security), 
            "is_risky" (boolean), 
            "summary" (Translate intent to Persian).
            """

        full_prompt = f"{system_instruction}\n\nUser Message to Analyze: \"{text}\""

        # لاگ: پیامی که به AI ارسال می‌شود
        _log_truncated(logger, "Ollama درخواست (متن کاربر برای تحلیل):", text, max_len=500)
        logger.info("Ollama پرامپت کامل (شامل دستورات): %s", full_prompt[:800] + ("..." if len(full_prompt) > 800 else ""))

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                data = response.json()
                raw_response = data.get('response', '')
                # لاگ: پاسخی که AI برگردانده (قبل از پارس تا در صورت خطا هم دیده شود)
                logger.info("Ollama پاسخ خام: %s", raw_response[:1000] + ("..." if len(raw_response) > 1000 else ""))
                parsed = json.loads(raw_response)
                logger.info("Ollama پاسخ پارس‌شده: sentiment_score=%s, category=%s, is_risky=%s, summary=%s",
                            parsed.get('sentiment_score'), parsed.get('category'), parsed.get('is_risky'),
                            (parsed.get('summary') or '')[:200])
                return parsed
            else:
                logger.error(f"Ollama Error: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Connection Error: {e}")
            return None

    def predict_future(self, user_chats: List[Dict], prompt_template: str = None) -> Optional[Dict]:
        if self.use_mock:
            return self.mock_service.predict_future(user_chats, prompt_template)
        
        url = f"{self.base_url}/api/generate"
        
        chats_text = "\n".join([f"Chat {i+1}: {chat.get('content', '')}" for i, chat in enumerate(user_chats[-50:])])
        
        if prompt_template:
            system_instruction = prompt_template
        else:
            system_instruction = """
            You are an AI behavioral analyst. Based on the user's chat history, predict future behavior patterns.
            Output ONLY strictly valid JSON with keys:
            "predicted_topics" (list of strings),
            "risk_level" (low/medium/high),
            "recommendations" (list of strings in Persian),
            "behavioral_trend" (improving/stable/declining),
            "summary" (Persian text).
            """

        full_prompt = f"{system_instruction}\n\nUser Chat History:\n{chats_text}"

        _log_truncated(logger, "Ollama درخواست (تاریخچه چت برای پیش‌بینی):", chats_text, max_len=600)
        logger.info("Ollama پرامپت پیش‌بینی (ابتدای متن): %s", full_prompt[:600] + ("..." if len(full_prompt) > 600 else ""))

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                raw_response = data.get('response', '')
                parsed = json.loads(raw_response)
                logger.info("Ollama پاسخ پیش‌بینی: %s", raw_response[:800] + ("..." if len(raw_response) > 800 else ""))
                return parsed
            else:
                logger.error(f"Ollama Error: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Connection Error: {e}")
            return None

class ReportGenerationService:
    def __init__(self):
        self.ollama = OllamaService()
        self.openwebui = OpenWebUIService()

    def generate_chat_analysis_report(self, report: Report) -> Dict:
        user_ids = self._get_target_user_ids(report)
        
        chats = self.openwebui.get_chats(
            user_ids=user_ids,
            start_date=report.start_date,
            end_date=report.end_date
        )
        
        analysis_data = {
            'total_chats': len(chats),
            'users_analyzed': len(user_ids),
            'analyses': [],
            'statistics': {
                'total_risky': 0,
                'avg_sentiment': 0,
                'categories': {},
            }
        }
        
        sentiment_sum = 0
        sentiment_count = 0
        
        for chat in chats:
            chat_updated_at = getattr(chat, 'updated_at', None) or 0
            existing_analysis = ChatAnalysis.objects.filter(source_chat_id=chat.id).first()
            if existing_analysis and (existing_analysis.source_chat_updated_at or 0) >= chat_updated_at:
                pass
            else:
                task = report.task or AnalysisTask.objects.filter(task_type='chat_analysis', is_active=True).first()
                prompt = task.prompt_template if task else None
                result = self.ollama.analyze_text(chat.content, prompt)
                if result:
                    existing_analysis, _ = ChatAnalysis.objects.update_or_create(
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
            
            if existing_analysis:
                analysis_data['analyses'].append({
                    'user_id': existing_analysis.user_id,
                    'category': existing_analysis.category,
                    'sentiment_score': existing_analysis.sentiment_score,
                    'is_risky': existing_analysis.is_risky,
                    'summary': existing_analysis.summary,
                })
                
                if existing_analysis.is_risky:
                    analysis_data['statistics']['total_risky'] += 1
                
                sentiment_sum += existing_analysis.sentiment_score
                sentiment_count += 1
                
                category = existing_analysis.category
                analysis_data['statistics']['categories'][category] = \
                    analysis_data['statistics']['categories'].get(category, 0) + 1
        
        if sentiment_count > 0:
            analysis_data['statistics']['avg_sentiment'] = round(sentiment_sum / sentiment_count, 2)
        
        return analysis_data

    def generate_future_prediction_report(self, report: Report) -> Dict:
        user_ids = self._get_target_user_ids(report)
        
        prediction_data = {
            'users_analyzed': len(user_ids),
            'predictions': [],
            'overall_trend': 'stable',
        }
        
        task = report.task or AnalysisTask.objects.filter(task_type='future_prediction', is_active=True).first()
        prompt = task.prompt_template if task else None
        
        for user_id in user_ids:
            chats = list(self.openwebui.get_chats(
                user_ids=[user_id],
                start_date=report.start_date - timedelta(days=30),
                end_date=report.end_date,
                limit=100
            ))
            
            if chats:
                chats_data = [{'content': chat.content, 'created_at': chat.created_at} for chat in chats]
                prediction = self.ollama.predict_future(chats_data, prompt)
                
                if prediction:
                    prediction_data['predictions'].append({
                        'user_id': user_id,
                        'predicted_topics': prediction.get('predicted_topics', []),
                        'risk_level': prediction.get('risk_level', 'low'),
                        'recommendations': prediction.get('recommendations', []),
                        'behavioral_trend': prediction.get('behavioral_trend', 'stable'),
                        'summary': prediction.get('summary', ''),
                    })
        
        return prediction_data

    def _get_target_user_ids(self, report: Report) -> List[str]:
        user_ids = set()
        
        if report.employees.exists():
            user_ids.update(report.employees.values_list('user_id', flat=True))
        
        if report.groups.exists():
            for group in report.groups.all():
                user_ids.update(group.employees.values_list('user_id', flat=True))
        
        return list(user_ids) if user_ids else list(Employee.objects.values_list('user_id', flat=True))

    def process_report(self, report: Report) -> bool:
        try:
            report.status = 'processing'
            report.save()
            
            if report.report_type.report_type == 'chat_analysis':
                data = self.generate_chat_analysis_report(report)
            elif report.report_type.report_type == 'future_prediction':
                data = self.generate_future_prediction_report(report)
            else:
                raise ValueError(f"نوع گزارش نامعتبر: {report.report_type.report_type}")
            
            report.report_data = data
            report.summary = self._generate_summary(data, report.report_type.report_type)
            report.status = 'completed'
            report.generated_at = timezone.now()
            report.save()
            
            return True
        except Exception as e:
            logger.error(f"خطا در تولید گزارش: {e}")
            report.status = 'failed'
            report.save()
            return False

    def _generate_summary(self, data: Dict, report_type: str) -> str:
        if report_type == 'chat_analysis':
            stats = data.get('statistics', {})
            return f"تعداد کل چت‌ها: {data.get('total_chats', 0)}, کاربران تحلیل شده: {data.get('users_analyzed', 0)}, چت‌های ریسکی: {stats.get('total_risky', 0)}, میانگین احساس: {stats.get('avg_sentiment', 0)}"
        elif report_type == 'future_prediction':
            return f"کاربران تحلیل شده: {data.get('users_analyzed', 0)}, تعداد پیش‌بینی‌ها: {len(data.get('predictions', []))}"
        return ""

def analyze_text_with_ollama(text):
    service = OllamaService()
    return service.analyze_text(text)


class UserSyncService:
    """
    سرویس برای سینک کردن کاربران از دیتابیس OpenWebUI با مدل Employee
    """
    
    def __init__(self):
        self.use_mock = getattr(settings, 'USE_MOCK_DATA', False)
    
    def _get_display_name(self, user_obj):
        """
        تعیین نام نمایشی برای کاربر بر اساس اولویت:
        1. name (اگر وجود داشته باشد)
        2. username (اگر وجود داشته باشد)
        3. email (بدون @ و دامنه)
        4. id (شناسه کاربر)
        """
        if hasattr(user_obj, 'name') and user_obj.name:
            return user_obj.name
        
        if hasattr(user_obj, 'username') and user_obj.username:
            return user_obj.username
        
        if hasattr(user_obj, 'email') and user_obj.email:
            # استفاده از بخش قبل از @ در ایمیل
            email_part = user_obj.email.split('@')[0]
            return email_part
        
        # در نهایت از id استفاده می‌کنیم
        return user_obj.id if hasattr(user_obj, 'id') else str(user_obj)
    
    def get_source_users(self):
        """
        دریافت لیست کاربران از دیتابیس OpenWebUI
        در صورت نبودن نام، از username یا email استفاده می‌کند
        """
        if self.use_mock:
            # داده‌های mock برای تست - شامل حالات مختلف
            return [
                {'id': 'user_1', 'name': 'علی احمدی', 'username': 'ali_ahmadi', 'email': 'ali@example.com', 'is_active': True},
                {'id': 'user_2', 'name': None, 'username': 'maryam_rezaei', 'email': 'maryam@example.com', 'is_active': True},
                {'id': 'user_3', 'name': None, 'username': None, 'email': 'hossein@example.com', 'is_active': True},
                {'id': 'user_4', 'name': None, 'username': None, 'email': None, 'is_active': True},  # فقط id
                {'id': 'user_5', 'name': 'رضا نوری', 'username': 'reza_nouri', 'email': 'reza@example.com', 'is_active': True},
            ]
        
        try:
            # اول از جدول user (SourceUser) خواندن — نام و ایمیل واقعی برای سینک با کارمندان
            users_by_id = {}
            try:
                for u in SourceUser.objects.using('openwebui_db').all():
                    users_by_id[u.id] = {
                        'id': u.id,
                        'name': u.name,
                        'username': getattr(u, 'username', None) or '',
                        'email': u.email or '',
                        'is_active': getattr(u, 'is_active', True) if u.is_active is not None else True,
                    }
            except Exception as user_table_error:
                logger.debug(f"جدول user در OpenWebUI در دسترس نیست، استفاده از چت‌ها: {user_table_error}")
                users_by_id = {}

            # user_idهایی که در چت‌ها هستند ولی شاید در جدول user نباشند
            chats = SourceChat.objects.using('openwebui_db').values('user_id').distinct()
            for chat in chats:
                user_id = chat['user_id']
                if not user_id:
                    continue
                if user_id not in users_by_id:
                    users_by_id[user_id] = {
                        'id': user_id,
                        'name': user_id,
                        'username': '',
                        'email': '',
                        'is_active': True,
                    }
            return list(users_by_id.values())
        except Exception as e:
            logger.error(f"خطا در دریافت کاربران از OpenWebUI: {e}")
            return []
    
    def sync_users(self, deactivate_missing=True, delete_missing=False):
        """
        سینک کردن کاربران از دیتابیس OpenWebUI با Employee
        
        Args:
            deactivate_missing: اگر True باشد، کاربرانی که در OpenWebUI نیستند را غیرفعال می‌کند
            delete_missing: اگر True باشد، کاربرانی که در OpenWebUI نیستند را حذف می‌کند
                           (این گزینه فقط در صورتی اعمال می‌شود که deactivate_missing=False باشد)
        
        Returns:
            dict: نتیجه سینک شامل تعداد کاربران اضافه شده، به‌روزرسانی شده و حذف/غیرفعال شده
        """
        result = {
            'added': 0,
            'updated': 0,
            'deactivated': 0,
            'deleted': 0,
            'errors': []
        }
        
        try:
            # دریافت کاربران از دیتابیس منبع
            source_users = self.get_source_users()
            source_user_ids = {user['id'] for user in source_users}
            
            # دریافت کاربران فعلی
            existing_employees = Employee.objects.all()
            existing_user_ids = {emp.user_id for emp in existing_employees}
            
            # اضافه کردن یا به‌روزرسانی کاربران جدید
            for source_user in source_users:
                try:
                    # تعیین نام نمایشی بر اساس اولویت
                    display_name = (
                        source_user.get('name') or 
                        source_user.get('username') or 
                        (source_user.get('email', '').split('@')[0] if source_user.get('email') else '') or
                        source_user['id']
                    )
                    
                    employee, created = Employee.objects.get_or_create(
                        user_id=source_user['id'],
                        defaults={
                            'name': display_name,
                            'email': source_user.get('email') or None,
                            'is_active': source_user.get('is_active', True)
                        }
                    )
                    
                    if created:
                        result['added'] += 1
                        logger.info(f"کاربر جدید اضافه شد: {employee.name} ({employee.user_id})")
                    else:
                        # به‌روزرسانی اطلاعات موجود
                        updated = False
                        if employee.name != display_name:
                            employee.name = display_name
                            updated = True
                        if employee.email != (source_user.get('email') or None):
                            employee.email = source_user.get('email') or None
                            updated = True
                        if employee.is_active != source_user.get('is_active', True):
                            employee.is_active = source_user.get('is_active', True)
                            updated = True
                        
                        if updated:
                            employee.save()
                            result['updated'] += 1
                            logger.info(f"کاربر به‌روزرسانی شد: {employee.name} ({employee.user_id})")
                except Exception as e:
                    error_msg = f"خطا در پردازش کاربر {source_user.get('id', 'unknown')}: {str(e)}"
                    result['errors'].append(error_msg)
                    logger.error(error_msg)
            
            missing_user_ids = existing_user_ids - source_user_ids
            
            if delete_missing and not deactivate_missing:
                deleted_count = Employee.objects.filter(user_id__in=missing_user_ids).delete()[0]
                result['deleted'] = deleted_count
                logger.info(f"{deleted_count} کاربر حذف شد")
            elif deactivate_missing:
                deactivated_count = Employee.objects.filter(
                    user_id__in=missing_user_ids,
                    is_active=True
                ).update(is_active=False)
                result['deactivated'] = deactivated_count
                logger.info(f"{deactivated_count} کاربر غیرفعال شد")
            
        except Exception as e:
            error_msg = f"خطا در فرایند سینک: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg)
        
        return result
    
    def get_sync_summary(self):

        try:
            source_users = self.get_source_users()
            source_user_ids = {user['id'] for user in source_users}
            
            existing_employees = Employee.objects.all()
            existing_user_ids = {emp.user_id for emp in existing_employees}
            
            new_users = source_user_ids - existing_user_ids
            missing_users = existing_user_ids - source_user_ids
            synced_users = source_user_ids & existing_user_ids
            
            return {
                'source_count': len(source_users),
                'local_count': existing_employees.count(),
                'new_users_count': len(new_users),
                'missing_users_count': len(missing_users),
                'synced_users_count': len(synced_users),
                'new_users': list(new_users),
                'missing_users': list(missing_users)
            }
        except Exception as e:
            logger.error(f"خطا در دریافت خلاصه سینک: {e}")
            return {
                'source_count': 0,
                'local_count': 0,
                'new_users_count': 0,
                'missing_users_count': 0,
                'synced_users_count': 0,
                'new_users': [],
                'missing_users': []
            }


class ChatSyncService:
    """
    سینک چت‌های کاربران از OpenWebUI.
    هر بار فقط چت‌هایی که بعد از آخرین زمان سینک به‌روزرسانی شده‌اند ذخیره می‌شوند.
    """

    def get_last_sync_time(self):
        """زمان آخرین سینک چت را برمی‌گرداند یا None برای اولین بار."""
        state, _ = ChatSyncState.objects.get_or_create(
            key='default',
            defaults={'last_sync_at': None}
        )
        return state.last_sync_at

    def sync_chats(self, limit=5000):
        """
        چت‌های جدید یا به‌روز شده (از آخرین سینک) را از OpenWebUI می‌خواند و در SyncedChat ذخیره می‌کند.
        Returns:
            dict: added, updated, errors, last_sync_at
        """
        result = {'added': 0, 'updated': 0, 'errors': [], 'last_sync_at': None}
        if getattr(settings, 'USE_MOCK_DATA', False):
            result['errors'].append('USE_MOCK_DATA فعال است؛ سینک واقعی از دیتابیس OpenWebUI انجام نشد.')
            return result
        try:
            last_sync_at = self.get_last_sync_time()
            query = SourceChat.objects.using('openwebui_db').all()
            if last_sync_at is not None:
                last_ts = int(last_sync_at.timestamp())
                query = query.filter(updated_at__gt=last_ts)
            # ابتدا سعی می‌کنیم فقط چت‌های بعد از آخرین زمان سینک را بگیریم
            source_chats_qs = query.order_by('updated_at')[:limit]
            source_chats = list(source_chats_qs)

            # اگر هیچ چتی در بازهٔ بعد از آخرین سینک پیدا نشد،
            # به‌عنوان fallback، همهٔ چت‌ها (تا حد limit) را می‌گیریم.
            # این رفتار کمک می‌کند اگر کاربری در بازهٔ قبلی چتی نداشته،
            # دفعهٔ بعد کل تاریخچه‌اش سینک شود.
            if last_sync_at is not None and not source_chats:
                logger.info("هیچ چت جدیدی بعد از آخرین زمان سینک یافت نشد؛ دریافت همهٔ چت‌ها تا محدودیت تعیین‌شده.")
                source_chats = list(
                    SourceChat.objects.using('openwebui_db').all().order_by('updated_at')[:limit]
                )

            max_updated = None
            for sc in source_chats:
                try:
                    _, created = SyncedChat.objects.update_or_create(
                        id=sc.id,
                        defaults={
                            'user_id': sc.user_id or '',
                            'title': getattr(sc, 'title', '') or '',
                            'chat': sc.chat or '',
                            'created_at': getattr(sc, 'created_at', 0) or 0,
                            'updated_at': getattr(sc, 'updated_at', 0) or 0,
                        }
                    )
                    if created:
                        result['added'] += 1
                    else:
                        result['updated'] += 1
                    if getattr(sc, 'updated_at', None):
                        if max_updated is None or sc.updated_at > max_updated:
                            max_updated = sc.updated_at
                except Exception as e:
                    result['errors'].append(f"چت {getattr(sc, 'id', '?')}: {str(e)}")
                    logger.warning(f"خطا در ذخیره چت {getattr(sc, 'id', '?')}: {e}")
            state, _ = ChatSyncState.objects.get_or_create(key='default', defaults={'last_sync_at': None})
            if max_updated is not None:
                from datetime import datetime
                state.last_sync_at = timezone.make_aware(
                    datetime.fromtimestamp(max_updated),
                    timezone.get_current_timezone()
                )
            else:
                state.last_sync_at = timezone.now()
            state.save()
            result['last_sync_at'] = state.last_sync_at
        except Exception as e:
            logger.error(f"خطا در سینک چت‌ها: {e}")
            result['errors'].append(str(e))
        return result

    def get_sync_summary(self):
        """خلاصه وضعیت سینک چت برای نمایش در ادمین."""
        try:
            state = ChatSyncState.objects.filter(key='default').first()
            last_sync_at = state.last_sync_at if state else None
            total_synced = SyncedChat.objects.count()
            return {
                'last_sync_at': last_sync_at,
                'total_synced': total_synced,
            }
        except Exception as e:
            logger.error(f"خطا در دریافت خلاصه سینک چت: {e}")
            return {'last_sync_at': None, 'total_synced': 0}


class UserReportService:
    
    def __init__(self):
        self.openwebui = OpenWebUIService()
        self.ollama = OllamaService()
    
    def generate_user_report(self, user_id, start_date=None, end_date=None):
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        employee = Employee.objects.filter(user_id=user_id).first()
        if not employee:
            return None
        
        chats = self.openwebui.get_chats(
            user_ids=[user_id],
            start_date=start_date,
            end_date=end_date
        )
        
        analyses = ChatAnalysis.objects.filter(
            user_id=user_id,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )
        
        total_chats = len(chats)
        total_analyses = analyses.count()
        risky_count = analyses.filter(is_risky=True).count()
        
        avg_sentiment = analyses.aggregate(avg=Avg('sentiment_score'))['avg'] or 0
        
        category_breakdown = analyses.values('category').annotate(
            count=Count('id')
        ).order_by('-count')
        
        sentiment_trend = []
        daily_analyses = analyses.extra(
            select={'day': 'date(timestamp)'}
        ).values('day').annotate(
            count=Count('id'),
            avg_sentiment=Avg('sentiment_score')
        ).order_by('day')
        
        for day_data in daily_analyses:
            sentiment_trend.append({
                'date': day_data['day'],
                'count': day_data['count'],
                'avg_sentiment': round(day_data['avg_sentiment'], 2)
            })
        
        risk_analysis = {
            'total_risky': risky_count,
            'risk_percentage': round((risky_count / total_analyses * 100) if total_analyses > 0 else 0, 2),
            'risk_level': 'high' if risky_count > total_analyses * 0.3 else 'medium' if risky_count > total_analyses * 0.1 else 'low'
        }
        
        recent_risky = analyses.filter(is_risky=True).order_by('-timestamp')[:5]
        
        return {
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'user_id': employee.user_id,
                'email': employee.email,
                'department': employee.department
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days
            },
            'statistics': {
                'total_chats': total_chats,
                'total_analyses': total_analyses,
                'risky_count': risky_count,
                'avg_sentiment': round(avg_sentiment, 2),
                'risk_level': risk_analysis['risk_level']
            },
            'category_breakdown': list(category_breakdown),
            'sentiment_trend': sentiment_trend,
            'risk_analysis': risk_analysis,
            'recent_risky_analyses': [
                {
                    'timestamp': a.timestamp,
                    'category': a.category,
                    'sentiment_score': a.sentiment_score,
                    'summary': a.summary
                }
                for a in recent_risky
            ]
        }
    
    def get_user_activity_summary(self, user_id, days=7):
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        analyses = ChatAnalysis.objects.filter(
            user_id=user_id,
            timestamp__gte=start_date
        )
        
        return {
            'total_analyses': analyses.count(),
            'risky_count': analyses.filter(is_risky=True).count(),
            'avg_sentiment': round(analyses.aggregate(avg=Avg('sentiment_score'))['avg'] or 0, 2),
            'most_common_category': analyses.values('category').annotate(
                count=Count('id')
            ).order_by('-count').first()
        }

    def analyze_last_chats(self, user_id: str, limit: int = 20):
        """
        تحلیل آخرین N چت یک کاربر مشخص و ذخیره نتیجه در ChatAnalysis.
        از تسک فعال 'chat_analysis' برای ساخت پرامپت استفاده می‌کند.
        """
        employee = Employee.objects.filter(user_id=user_id).first()
        if not employee:
            return {
                'user_id': user_id,
                'employee_found': False,
                'analyzed': 0,
                'skipped_existing': 0,
            }

        # دریافت آخرین چت‌ها از OpenWebUI
        chats = self.openwebui.get_chats(
            user_ids=[user_id],
            limit=limit,
        )

        task = AnalysisTask.objects.filter(task_type='chat_analysis', is_active=True).first()
        prompt = task.prompt_template if task else None

        analyzed = 0
        skipped_existing = 0

        for chat in chats:
            chat_updated_at = getattr(chat, 'updated_at', None) or 0
            existing = ChatAnalysis.objects.filter(source_chat_id=chat.id, user_id=user_id).first()
            # اگر قبلاً همین نسخهٔ چت (یا جدیدتر) تحلیل شده، رد کن
            if existing and (existing.source_chat_updated_at or 0) >= chat_updated_at:
                skipped_existing += 1
                continue

            result = self.ollama.analyze_text(chat.content, prompt)
            if not result:
                continue

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
            analyzed += 1

        return {
            'user_id': user_id,
            'employee_found': True,
            'requested': limit,
            'analyzed': analyzed,
            'skipped_existing': skipped_existing,
        }