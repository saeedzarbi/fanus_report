"""
URL configuration for fanus_report project.
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from analytics.views import dashboard, metabase_charts, user_reports_list, user_report_detail
from analytics.api import api_create_employee, api_user_chats

urlpatterns = [
    path('admin/dashboard/', dashboard, name='admin_dashboard'),
    path('admin/metabase-charts/', metabase_charts, name='metabase_charts'),
    path('admin/user-reports/', user_reports_list, name='user_reports_list'),
    path('admin/user-reports/<str:user_id>/', user_report_detail, name='user_report_detail'),
    path('admin/', admin.site.urls),
    # REST API
    path('api/employees/', api_create_employee, name='api_create_employee'),
    path('api/users/<str:user_id>/chats/', api_user_chats, name='api_user_chats'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

