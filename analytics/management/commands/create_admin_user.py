from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'ایجاد کاربر ادمین پیش‌فرض'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='admin', help='نام کاربری')
        parser.add_argument('--email', type=str, default='admin@example.com', help='ایمیل')
        parser.add_argument('--password', type=str, default='admin123', help='رمز عبور')

    def handle(self, *args, **options):
        username = options.get('username', 'admin')
        email = options.get('email', 'admin@example.com')
        password = options.get('password', 'admin123')

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'کاربر {username} از قبل وجود دارد.'))
            user = User.objects.get(username=username)
            user.set_password(password)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'رمز عبور کاربر {username} به‌روزرسانی شد.'))
        else:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(self.style.SUCCESS(f'کاربر ادمین {username} با موفقیت ایجاد شد.'))
        
        self.stdout.write(self.style.SUCCESS(f'\nاطلاعات ورود:'))
        self.stdout.write(self.style.SUCCESS(f'نام کاربری: {username}'))
        self.stdout.write(self.style.SUCCESS(f'رمز عبور: {password}'))
        self.stdout.write(self.style.SUCCESS(f'\nمی‌توانید با این اطلاعات وارد پنل ادمین شوید: /admin'))