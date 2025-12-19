"""
Django settings for fanus_report project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-change-this-secret-key-in-production'

DEBUG = True

ALLOWED_HOSTS = []

USE_MOCK_DATA = True

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'analytics'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fanus_report.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fanus_report.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'openwebui_db': {
        'ENGINE': 'django.db.backends.postgresql', 
        'NAME': 'openwebui',       
        'USER': 'your_db_user',  
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'fa-ir'

TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True

# Force LTR layout for admin panel (sidebar on left)
USE_L10N = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Metabase Configuration
METABASE_SITE_URL = 'http://localhost:3000'  # URL سرویس Metabase شما
METABASE_SECRET_KEY = ''  # Secret Key برای signed embedding (اختیاری)
# لیست نمودارهای Metabase که می‌خواهید نمایش دهید
# فرمت: {'name': 'نام نمایشی', 'dashboard_id': 'ID داشبورد', 'card_id': 'ID کارت (اختیاری)'}
METABASE_DASHBOARDS = [
    {
        'name': 'داشبورد اصلی',
        'dashboard_id': 1,
        'description': 'نمای کلی آمار و تحلیل‌ها'
    },
    # می‌توانید نمودارهای بیشتری اضافه کنید
    # {
    #     'name': 'تحلیل احساسات',
    #     'dashboard_id': 2,
    #     'description': 'نمودارهای تحلیل احساسات'
    # },
]

JAZZMIN_SETTINGS = {
    "site_title": "سامانه هوشمند فانوس",
    "site_header": "پنل مدیریت فانوس",
    "site_brand": "فانوس",
    "site_logo": "images/logo_site.png",
    "login_logo": "images/logo.png",
    "login_logo_dark": None,
    "site_logo_classes": "img-circle",
    "site_icon": None,
    "welcome_sign": "سامانه هوشمند تحلیل رفتاری فانوس",
    "copyright": "فانوس",
    "search_model": ["auth.User", "auth.Group", "analytics.Employee"],
    "user_avatar": None,
    "theme": "darkly",
    "dark_mode_theme": "cyborg",
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": ["analytics", "auth"],
    "custom_links": {
        "analytics": [{
            "name": "📊 داشبورد تحلیلی",
            "url": "admin_dashboard",
            "icon": "fas fa-chart-line",
            "permissions": ["analytics.view_report"],
        }],
    },
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "analytics": "fas fa-chart-bar",
        "analytics.employee": "fas fa-user-tie",
        "analytics.usergroup": "fas fa-users",
        "analytics.analysistask": "fas fa-tasks",
        "analytics.chatanalysis": "fas fa-comments",
        "analytics.reporttype": "fas fa-file-alt",
        "analytics.report": "fas fa-chart-bar",
        "analytics.reportschedule": "fas fa-calendar-alt",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "show_ui_builder": True,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
    "language_chooser": False,
    "custom_css": "css/custom_admin.css",
    "custom_js": None,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "navbar_fixed": True,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "rtl": False,  # Force LTR (Left to Right)
}

