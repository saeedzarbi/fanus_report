"""
REST API برای کارمندان و چت‌های کاربران.
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Employee, SyncedChat


def _parse_json_body(request):
    """بدنهٔ JSON درخواست را پارس می‌کند. در صورت خطا None برمی‌گرداند."""
    try:
        return json.loads(request.body.decode('utf-8')) if request.body else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


@csrf_exempt
@require_http_methods(["POST"])
def api_create_employee(request):
    """
    ساخت کارمند (REST API).

    ورودی (JSON در بدنهٔ درخواست):
        user_id (الزامی): شناسه یکتای کاربر
        name (الزامی): نام
        email (اختیاری): ایمیل
        department (اختیاری): دپارتمان
        is_active (اختیاری): فعال/غیرفعال، پیش‌فرض true

    خروجی موفق (201):
        { "id": <pk>, "user_id": "...", "name": "...", "email": null, "department": null, "is_active": true, "created_at": "..." }

    خطاها: 400 (ورودی نامعتبر)، 409 (user_id تکراری)
    """
    data = _parse_json_body(request)
    if data is None:
        return JsonResponse(
            {"error": "بدنهٔ درخواست باید JSON معتبر باشد."},
            status=400,
        )

    user_id = (data.get("user_id") or "").strip()
    name = (data.get("name") or "").strip()

    if not user_id:
        return JsonResponse(
            {"error": "فیلد user_id الزامی است."},
            status=400,
        )
    if not name:
        return JsonResponse(
            {"error": "فیلد name الزامی است."},
            status=400,
        )

    if Employee.objects.filter(user_id=user_id).exists():
        return JsonResponse(
            {"error": f"کاربری با شناسهٔ '{user_id}' از قبل وجود دارد."},
            status=409,
        )

    email = (data.get("email") or "").strip() or None
    department = (data.get("department") or "").strip() or None
    is_active = data.get("is_active", True)
    if not isinstance(is_active, bool):
        is_active = True

    employee = Employee.objects.create(
        user_id=user_id,
        name=name,
        email=email,
        department=department,
        is_active=is_active,
    )

    return JsonResponse(
        {
            "id": employee.id,
            "user_id": employee.user_id,
            "name": employee.name,
            "email": employee.email,
            "department": employee.department,
            "is_active": employee.is_active,
            "created_at": employee.created_at.isoformat() if employee.created_at else None,
        },
        status=201,
    )


@require_http_methods(["GET"])
def api_user_chats(request, user_id):
    """
    دریافت چت‌های یک کاربر بر اساس شناسه (user_id).

    مسیر: GET /api/users/<user_id>/chats/

    پارامترهای اختیاری (query string):
        limit: حداکثر تعداد (پیش‌فرض 100)
        offset: تعداد رد شدن از ابتدا (پیش‌فرض 0)

    خروجی موفق (200):
        {
            "user_id": "...",
            "count": <تعداد>,
            "chats": [
                {
                    "id": "...",
                    "title": "...",
                    "created_at": <timestamp>,
                    "updated_at": <timestamp>,
                    "synced_at": "...",
                    "chat": <محتوای JSON یا رشته>
                },
                ...
            ]
        }
    """
    limit = request.GET.get("limit", "100")
    offset = request.GET.get("offset", "0")
    try:
        limit = max(1, min(1000, int(limit)))
    except ValueError:
        limit = 100
    try:
        offset = max(0, int(offset))
    except ValueError:
        offset = 0

    qs = SyncedChat.objects.filter(user_id=user_id).order_by("-updated_at")
    total = qs.count()
    chats_qs = qs[offset : offset + limit]

    chats = []
    for c in chats_qs:
        # محتوای chat ممکن است JSON رشته باشد؛ برای API همان‌طور که هست برمی‌گردانیم
        chat_content = c.chat
        if isinstance(chat_content, str) and chat_content:
            try:
                chat_content = json.loads(chat_content)
            except (json.JSONDecodeError, TypeError):
                pass
        chats.append({
            "id": c.id,
            "title": c.title or "",
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "synced_at": c.synced_at.isoformat() if c.synced_at else None,
            "chat": chat_content,
        })

    return JsonResponse(
        {
            "user_id": user_id,
            "count": len(chats),
            "total": total,
            "chats": chats,
        },
        safe=False,
    )
