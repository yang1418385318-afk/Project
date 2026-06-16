import time
import asyncio
import json
import os
import uuid
import jwt
import logging
import redis.asyncio as redis

# 🟢 修复 1：补齐遗漏的 Request 和 status 导入
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 1. 初始化限流器 + 日志
logger = logging.getLogger("oj_gateway")
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')

limiter = Limiter(key_func=get_remote_address)

redis_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    redis_client = redis.Redis(host='redis_db', port=6379, db=0, decode_responses=True, password=os.environ.get('REDIS_PASSWORD', 'redis_dev_pass'))
    logger.info("🚀 高并发安全网关已点火！成功连接至 Redis 消息队列。")
    yield
    await redis_client.close()
    logger.info("🛑 网关关闭，释放连接。")

app = FastAPI(title="Geek OJ High-Concurrency API (Secured)", lifespan=lifespan)

# CORS: read allowed origins from env, default to localhost for dev
ALLOWED_ORIGINS = os.environ.get(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173'
).split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'dummy-jwt-key-for-dev-only')
ALGORITHM = "HS256"
security_bearer = HTTPBearer()

async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security_bearer)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的身份令牌，拒绝访问")

class SubmitCodeRequest(BaseModel):
    problem_id: int
    code: str
    language: str = "python3"

ALLOWED_LANGUAGES = {"python3", "cpp", "java"}
MAX_CODE_LENGTH = 65536  # 64KB — prevents queue/excessive memory consumption


@app.post("/submit/")
@limiter.limit("5/minute")
async def submit_code(
        request: Request,
        body: SubmitCodeRequest,
        token_user: dict = Depends(verify_jwt_token)
):
    real_user_id = token_user.get("user_id")
    task_id = str(uuid.uuid4())

    # Validate language
    if body.language not in ALLOWED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"不支持的语言: {body.language}")

    # Validate code size
    if len(body.code.encode('utf-8')) > MAX_CODE_LENGTH:
        raise HTTPException(status_code=400, detail=f"代码过长，最大 {MAX_CODE_LENGTH // 1024}KB")

    # Store task ownership in Redis so result/WS can verify
    await redis_client.set(f"task_owner:{task_id}", str(real_user_id), ex=3600)

    task_data = {
        "task_id": task_id,
        "user_id": real_user_id,
        "problem_id": body.problem_id,
        "code": body.code,
        "language": body.language,
        "status": "PENDING"
    }

    await redis_client.lpush("judge_queue", json.dumps(task_data))

    return {
        "code": 200,
        "message": "身份验证成功，代码已送入隔离排队链条！",
        "task_id": task_id
    }

@app.websocket("/ws/result/{task_id}")
async def websocket_judge_result(websocket: WebSocket, task_id: str, token: str = None):
    await websocket.accept()

    # Verify JWT token from query param
    if not token:
        await websocket.send_text("NO_AUTH")
        await websocket.close()
        return
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = str(payload.get("user_id"))
    except Exception:
        await websocket.send_text("NO_AUTH")
        await websocket.close()
        return

    # Verify task ownership
    owner = await redis_client.get(f"task_owner:{task_id}")
    if owner and owner != user_id:
        await websocket.send_text("FORBIDDEN")
        await websocket.close()
        return

    logger.info(f"🔗 前端取餐器已连接，正在监听任务: {task_id}")

    # 🚀 Redis Pub/Sub 替代轮询：零延迟推送
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"task_done:{task_id}")
    try:
        # 先检查是否已经有结果（可能在订阅前已完成）
        cached = await redis_client.get(f"task_result:{task_id}")
        if cached:
            await websocket.send_text(cached)
            return

        # 等待 Pub/Sub 推送，30s 超时保护（兼容 Python 3.9）
        async def _listen():
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    return message['data']

        try:
            data = await asyncio.wait_for(_listen(), timeout=30)
            if data:
                await websocket.send_text(data)
                logger.info(f"🎯 任务 {task_id} 评测完成，已通过 Pub/Sub 推送: {data}")
                return
        except asyncio.TimeoutError:
            await websocket.send_text("SE")
            logger.warning(f"⏰ 任务 {task_id} 等待超时（30s），返回 SE")
    except WebSocketDisconnect:
        logger.warning(f"⚠️ 前端断开了任务 {task_id} 的连接")
    finally:
        await pubsub.unsubscribe(f"task_done:{task_id}")

@app.get("/result/{task_id}")
async def get_result(
    task_id: str,
    token_user: dict = Depends(verify_jwt_token)
):
    user_id = str(token_user.get("user_id"))
    owner = await redis_client.get(f"task_owner:{task_id}")
    if owner and owner != user_id:
        raise HTTPException(status_code=403, detail="无权查看此任务")

    status_res = await redis_client.get(f"task_result:{task_id}")
    if not status_res:
        return {"code": 200, "task_id": task_id, "status": "PENDING"}
    return {"code": 200, "task_id": task_id, "status": status_res}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)