import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fanus_report.settings')
django.setup()

from django.contrib.auth.models import User

username = 'admin'
email = 'admin@example.com'
password = 'admin123'

if User.objects.filter(username=username).exists():
    user = User.objects.get(username=username)
    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f'User {username} updated successfully!')
else:
    User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    print(f'User {username} created successfully!')

print(f'\nLogin credentials:')
print(f'Username: {username}')
print(f'Password: {password}')
print(f'\nAccess admin panel at: /admin')