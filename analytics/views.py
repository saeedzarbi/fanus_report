from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Q
from .models import Report, ChatAnalysis, Employee, AnalysisTask, ReportSchedule

@staff_member_required
def dashboard(request):
    now = timezone.now()
    last_24h = now - timedelta(days=1)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_reports = Report.objects.count()
    completed_reports = Report.objects.filter(status='completed').count()
    pending_reports = Report.objects.filter(status='pending').count()
    processing_reports = Report.objects.filter(status='processing').count()

    recent_reports = Report.objects.filter(status='completed').order_by('-generated_at')[:5]

    total_analyses = ChatAnalysis.objects.count()
    risky_analyses = ChatAnalysis.objects.filter(is_risky=True).count()
    avg_sentiment = ChatAnalysis.objects.aggregate(avg=Avg('sentiment_score'))['avg'] or 0

    analyses_last_24h = ChatAnalysis.objects.filter(timestamp__gte=last_24h).count()
    analyses_last_7d = ChatAnalysis.objects.filter(timestamp__gte=last_7d).count()
    analyses_last_30d = ChatAnalysis.objects.filter(timestamp__gte=last_30d).count()

    category_stats = ChatAnalysis.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')[:5]

    total_employees = Employee.objects.filter(is_active=True).count()
    total_tasks = AnalysisTask.objects.filter(is_active=True).count()
    total_schedules = ReportSchedule.objects.filter(is_active=True).count()

    active_tasks = AnalysisTask.objects.filter(is_active=True).order_by('-last_run')[:5]

    context = {
        'total_reports': total_reports,
        'completed_reports': completed_reports,
        'pending_reports': pending_reports,
        'processing_reports': processing_reports,
        'recent_reports': recent_reports,
        'total_analyses': total_analyses,
        'risky_analyses': risky_analyses,
        'avg_sentiment': round(avg_sentiment, 2),
        'analyses_last_24h': analyses_last_24h,
        'analyses_last_7d': analyses_last_7d,
        'analyses_last_30d': analyses_last_30d,
        'category_stats': category_stats,
        'total_employees': total_employees,
        'total_tasks': total_tasks,
        'total_schedules': total_schedules,
        'active_tasks': active_tasks,
    }
    
    return render(request, 'admin/dashboard.html', context)
