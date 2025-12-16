import requests
import json
import random
from django.conf import settings
from django.db import connections
from django.utils import timezone
from datetime import timedelta
from .models import SourceChat, ChatAnalysis, Employee, Report, ReportType, AnalysisTask, UserGroup
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class MockSourceChat:
    def __init__(self, id, user_id, content, created_at):
        self.id = id
        self.user_id = user_id
        self.content = content
        self.created_at = created_at

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
                query = query.filter(created_at__gte=int(start_date.timestamp()))
            
            if end_date:
                query = query.filter(created_at__lte=int(end_date.timestamp()))
            
            return query.order_by('-created_at')[:limit]
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
    def __init__(self, base_url="http://localhost:11434", model="llama3"):
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
                return json.loads(data['response'])
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
                return json.loads(data['response'])
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
            existing_analysis = ChatAnalysis.objects.filter(source_chat_id=chat.id).first()
            
            if not existing_analysis:
                task = report.task or AnalysisTask.objects.filter(task_type='chat_analysis', is_active=True).first()
                prompt = task.prompt_template if task else None
                
                result = self.ollama.analyze_text(chat.content, prompt)
                
                if result:
                    existing_analysis = ChatAnalysis.objects.create(
                        source_chat_id=chat.id,
                        user_id=chat.user_id,
                        task=task,
                        sentiment_score=result.get('sentiment_score', 5),
                        category=result.get('category', 'Unknown'),
                        is_risky=result.get('is_risky', False),
                        summary=result.get('summary', ''),
                        raw_analysis=result
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