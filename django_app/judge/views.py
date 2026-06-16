from django.shortcuts import render

# Create your views here.
import os
import logging
import jwt
import time
import json
import redis
from django.http import JsonResponse
from django.contrib.auth import authenticate
from django.views.decorators.csrf import csrf_exempt
from .models import Problem

logger = logging.getLogger("oj_auth")

# ⚠️ 这个秘钥必须和 FastAPI 里的一模一样！
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dummy-jwt-key-for-dev-only')

# 登录限流：使用 Redis 共享存储（多进程安全），懒连接防泄漏
MAX_ATTEMPTS = 5          # 最大允许失败次数
LOCKOUT_SECONDS = 300      # 锁定 5 分钟
_rate_redis = None


def _get_rate_redis():
    """Lazy-init Redis rate-limiter connection."""
    global _rate_redis
    if _rate_redis is None:
        try:
            _rate_redis = redis.Redis(
                host='redis_db', port=6379, db=0,
                decode_responses=True,
                password=os.environ.get('REDIS_PASSWORD', 'redis_dev_pass'),
                socket_connect_timeout=1,
                socket_keepalive=True,
                health_check_interval=30,
            )
            _rate_redis.ping()
        except Exception:
            _rate_redis = False  # sentinel: unavailable
    return _rate_redis if _rate_redis is not False else None


def _client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


@csrf_exempt
def api_login(request):
    """JWT 登录接口（含 IP+用户名 Redis 限流与审计日志）"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "message": "Method Not Allowed"}, status=405)

    data = json.loads(request.body)
    username = data.get("username")
    password = data.get("password")
    ip = _client_ip(request)

    if not username or not password:
        return JsonResponse({"code": 400, "message": "账号和密码不能为空"}, status=400)

    # --- Redis 限流（仅当 Redis 可用时）---
    r = _get_rate_redis()
    if r is not None:
        lock_ip = r.get(f"login_lock:ip:{ip}")
        lock_user = r.get(f"login_lock:user:{username}")
        if lock_ip or lock_user:
            remaining = max(
                int(lock_ip or 0) - time.time() if lock_ip else 0,
                int(lock_user or 0) - time.time() if lock_user else 0,
            )
            if remaining > 0:
                logger.warning(f"Rate-limited: user={username} ip={ip}")
                return JsonResponse({
                    "code": 429, "message": f"登录过于频繁，请 {int(remaining)}s 后再试"
                }, status=429)

    # Django 密码校验
    user = authenticate(username=username, password=password)
    if user:
        # 登录成功：清除失败记录
        r = _get_rate_redis()
        if r is not None:
            r.delete(f"login_fail:ip:{ip}", f"login_fail:user:{username}",
                               f"login_lock:ip:{ip}", f"login_lock:user:{username}")
        logger.info(f"Login success: user={username} ip={ip}")

        payload = {
            "user_id": user.id,
            "exp": int(time.time()) + 3600 * 24 * 30
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return JsonResponse({"code": 200, "token": token, "username": user.username})

    # 登录失败：累加计数并设置锁定
    r = _get_rate_redis()
    if r is not None:
        fails_ip = r.incr(f"login_fail:ip:{ip}")
        r.expire(f"login_fail:ip:{ip}", LOCKOUT_SECONDS * 2)
        fails_user = r.incr(f"login_fail:user:{username}")
        r.expire(f"login_fail:user:{username}", LOCKOUT_SECONDS * 2)

        if fails_ip >= MAX_ATTEMPTS:
            lock_time = int(time.time() + LOCKOUT_SECONDS * (2 ** min(fails_ip - MAX_ATTEMPTS, 3)))
            r.setex(f"login_lock:ip:{ip}", LOCKOUT_SECONDS * 10, lock_time)
        if fails_user >= MAX_ATTEMPTS:
            lock_time = int(time.time() + LOCKOUT_SECONDS * (2 ** min(fails_user - MAX_ATTEMPTS, 3)))
            r.setex(f"login_lock:user:{username}", LOCKOUT_SECONDS * 10, lock_time)

        logger.warning(f"Login failed: user={username} ip={ip} ip_fails={fails_ip} user_fails={fails_user}")
    else:
        logger.warning(f"Login failed: user={username} ip={ip} (rate limiter unavailable)")

    return JsonResponse({"code": 401, "message": "账号或密码错误！"}, status=401)


def api_get_problems(request):
    """动态获取数据库里的题目列表"""
    problems = list(Problem.objects.values('id', 'title'))
    return JsonResponse({"code": 200, "data": problems})
