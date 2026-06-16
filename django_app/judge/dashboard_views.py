"""
运行监控大盘 API
纯 Django ORM 聚合统计，零 Pandas 内存开销
"""
import os
import jwt
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Submission

# 与 views.py / FastAPI 一致的 JWT 密钥
_JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'dummy-jwt-key-for-dev-only')


def _require_jwt(view_func):
    """Decorator: require valid JWT Bearer token on dashboard endpoints."""
    def wrapper(request, *args, **kwargs):
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth.startswith('Bearer '):
            return JsonResponse({"code": 401, "message": "需要身份认证"}, status=401)
        try:
            jwt.decode(auth[7:], _JWT_SECRET, algorithms=["HS256"])
        except Exception:
            return JsonResponse({"code": 401, "message": "无效的身份令牌"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


# ---------- 统一的空数据响应格式 ----------
EMPTY_OVERVIEW = {
    "total_submissions": 0,
    "ac_rate": 0,
    "unique_users": 0,
    "unique_problems": 0,
}
EMPTY_TREND = {"dates": [], "counts": []}
EMPTY_LIST = []

# Cache TTLs (seconds)
CACHE_TTL_FAST = 30    # overview, status-dist
CACHE_TTL_SLOW = 60    # trend, ranking


def _cached_or_compute(key, ttl, compute_fn):
    """Return cached value or compute + cache it."""
    val = cache.get(key)
    if val is not None:
        return val
    val = compute_fn()
    cache.set(key, val, ttl)
    return val


@csrf_exempt
@_require_jwt
def api_dashboard_overview(request):
    """总览卡片：总提交数 / AC 率 / 用户数 / 题目数"""
    try:
        def _compute():
            total = Submission.objects.count()
            if total == 0:
                return {"code": 200, "data": EMPTY_OVERVIEW}
            ac_count = Submission.objects.filter(status='AC').count()
            ac_rate = round(ac_count / total * 100, 1)
            unique_users = Submission.objects.values('user_id').distinct().count()
            unique_problems = Submission.objects.values('problem_id').distinct().count()
            return {"code": 200, "data": {
                "total_submissions": total, "ac_rate": ac_rate,
                "unique_users": unique_users, "unique_problems": unique_problems,
            }}

        result = _cached_or_compute("dash:overview", CACHE_TTL_FAST, _compute)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"code": 500, "message": str(e)}, status=500)


@csrf_exempt
@_require_jwt
def api_submissions_trend(request):
    """提交趋势：按日统计，支持 ?days=7/30/90（纯 ORM，零 Pandas）"""
    try:
        days = int(request.GET.get('days', 30))
        days = max(1, min(days, 365))

        def _compute():
            since = timezone.now() - timedelta(days=days)
            daily = (
                Submission.objects
                .filter(created_at__gte=since)
                .annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(count=Count('id'))
                .order_by('date')
            )
            if not daily:
                return {"code": 200, "data": EMPTY_TREND}
            dates = [str(r['date']) for r in daily]
            counts = [r['count'] for r in daily]
            return {"code": 200, "data": {"dates": dates, "counts": counts}}

        result = _cached_or_compute(f"dash:trend:{days}", CACHE_TTL_SLOW, _compute)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"code": 500, "message": str(e)}, status=500)


@csrf_exempt
@_require_jwt
def api_status_distribution(request):
    """判题状态分布（饼图）"""
    try:
        def _compute():
            status_counts = (
                Submission.objects
                .values('status')
                .annotate(count=Count('id'))
                .order_by()
            )
            data = [{"name": item['status'], "value": item['count']} for item in status_counts if item['count'] > 0]
            return {"code": 200, "data": data if data else EMPTY_LIST}

        result = _cached_or_compute("dash:status_dist", CACHE_TTL_FAST, _compute)
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"code": 500, "message": str(e)}, status=500)


@csrf_exempt
@_require_jwt
def api_user_ranking(request):
    """用户排名：?limit=10，按 AC 数降序（纯 ORM，零 Pandas）"""
    try:
        limit = int(request.GET.get('limit', 10))
        limit = max(1, min(limit, 100))

        def _compute():
            ranking = (
                Submission.objects
                .filter(status='AC')
                .values('user__username')
                .annotate(ac_count=Count('id'))
                .order_by('-ac_count')[:100]
            )
            if not ranking:
                return {"code": 200, "data": EMPTY_LIST}
            data = [{"username": r['user__username'], "ac_count": r['ac_count']} for r in ranking]
            return {"code": 200, "data": data}

        result = _cached_or_compute("dash:ranking", CACHE_TTL_SLOW, _compute)
        # Truncate to requested limit after cache retrieval
        if result["data"] and isinstance(result["data"], list):
            result["data"] = result["data"][:limit]
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"code": 500, "message": str(e)}, status=500)
