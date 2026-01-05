from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Q
from django.conf import settings
from .models import Report, ChatAnalysis, Employee, AnalysisTask, ReportSchedule
from .services import UserReportService

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


from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings

@staff_member_required
def metabase_charts(request):
    metabase_url = getattr(settings, 'METABASE_SITE_URL', 'http://localhost:3000')
    all_dashboards = getattr(settings, 'METABASE_DASHBOARDS', [])
    
    dashboard_urls = []
    
    for dashboard in all_dashboards:
        # شرط مهم: اگر داشبورد نیاز به پارامتر فیلتر (مثل user_id) دارد، 
        # آن را در این صفحه عمومی نشان نده و رد شو.
        if dashboard.get('filter_param'):
            continue

        public_uuid = dashboard.get('public_uuid')
        
        if public_uuid:
            embed_url = f"{metabase_url}/public/dashboard/{public_uuid}#bordered=true&titled=true"
            
            dashboard_urls.append({
                'name': dashboard.get('name', 'داشبورد عمومی'),
                'description': dashboard.get('description', ''),
                'embed_url': embed_url,
                'full_url': embed_url, 
            })
    
    context = {
        'dashboards': dashboard_urls,
        'has_dashboards': len(dashboard_urls) > 0,
    }
    
    return render(request, 'admin/metabase_charts.html', context)

@staff_member_required
def user_reports_list(request):
    employees = Employee.objects.filter(is_active=True).order_by('name')
    report_service = UserReportService()
    
    employees_with_stats = []
    for employee in employees:
        stats = report_service.get_user_activity_summary(employee.user_id, days=7)
        employees_with_stats.append({
            'employee': employee,
            'stats': stats
        })
    
    context = {
        'employees_with_stats': employees_with_stats,
    }
    
    return render(request, 'admin/user_reports_list.html', context)

@staff_member_required
def user_report_detail(request, user_id):
    employee = get_object_or_404(Employee, user_id=user_id)
    
    report_service = UserReportService()
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    end_date = timezone.now()
    
    report_data = report_service.generate_user_report(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date
    )
    
    metabase_url = getattr(settings, 'METABASE_SITE_URL', '')
    all_dashboards = getattr(settings, 'METABASE_DASHBOARDS', [])
    
    user_dashboards = []
    
    for dashboard in all_dashboards:
        public_uuid = dashboard.get('public_uuid')
        filter_param = dashboard.get('filter_param') 

        if public_uuid:
            
            if filter_param:
                embed_url = f"{metabase_url}/public/dashboard/{public_uuid}?{filter_param}={user_id}#bordered=true&titled=true"
                
                user_dashboards.append({
                    'name': dashboard.get('name'),
                    'description': dashboard.get('description', ''),
                    'embed_url': embed_url
                })
            

    context = {
        'report': report_data,
        'selected_days': days,
        'employee': employee, 
        'metabase_dashboards': user_dashboards,
        'has_metabase_dashboards': len(user_dashboards) > 0,
    }
    
    return render(request, 'admin/user_report_detail.html', context)