import os
import time
import json
import redis
import docker
import base64
from docker.errors import ContainerError, APIError, DockerException
import logging
from pythonjsonlogger import jsonlogger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django

django.setup()

from judge.models import Submission, Problem, TestCase
from django.contrib.auth.models import User

# 配置日志
logger = logging.getLogger("oj_worker")
logger.setLevel(logging.INFO)
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s %(task_id)s', json_ensure_ascii=False)
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

r = redis.Redis(host='redis_db', port=6379, db=0, decode_responses=True,
                password=os.environ.get('REDIS_PASSWORD', 'redis_dev_pass'))

# docker_client lazy-init — don't crash on import if Docker socket is unavailable
docker_client = None


def _get_docker():
    """Lazy-initialize Docker client; returns client or raises DockerException."""
    global docker_client
    if docker_client is None:
        docker_client = docker.from_env()
    return docker_client


LANG_MATRIX = {
    "python3": {
        "image": "python:3.9-slim",
        "ext": ".py",
        "compile": None,
        "run": "python Main.py < input.txt",
    },
    "cpp": {
        "image": "gcc:latest",
        "ext": ".cpp",
        "compile": "g++ Main.cpp -o app",
        "run": "./app < input.txt",
    },
    "java": {
        "image": "eclipse-temurin:17-jdk-jammy",
        "ext": ".java",
        "compile": "javac Main.java",
        "run": "java Main < input.txt",
    }
}


def run_all_test_cases(code_string: str, language: str, test_cases: list,
                       time_limit_ms: int, task_id: str):
    """
    一次提交 → 一个容器 → 一次编译 → 批量运行所有测试点。
    返回 (final_status, [outputs]) 或 (错误状态, '')
    """
    matrix = LANG_MATRIX.get(language, LANG_MATRIX["python3"])
    code_file = f"Main{matrix['ext']}"
    code_b64 = base64.b64encode(code_string.encode('utf-8')).decode('utf-8')
    timeout_s = max(1, time_limit_ms // 1000)
    sep = f"___END_{task_id}___"   # 唯一分隔符，避免与用户输出冲突

    # 尝试获取 Docker 客户端
    try:
        client = _get_docker()
    except DockerException as e:
        logger.error(f"🐳 Docker 客户端初始化失败: {e}", extra={"task_id": task_id})
        return 'SE', []

    # 构建批量评测脚本
    script_lines = [
        f"echo {code_b64} | base64 -d > {code_file}",
    ]
    if matrix['compile']:
        script_lines.append(
            f"{matrix['compile']} || {{ echo '___COMPILE_ERROR___'; exit 1; }}"
        )

    for tc in test_cases:
        inp_b64 = base64.b64encode(tc.input_data.encode('utf-8')).decode('utf-8')
        script_lines.append(
            f"echo {inp_b64} | base64 -d > input.txt && "
            f"timeout {timeout_s}s {matrix['run']}; echo '{sep}'"
        )

    batch_script = "\n".join(script_lines)

    try:
        output_bytes = client.containers.run(
            image=matrix['image'],
            command=["sh", "-c", batch_script],
            working_dir="/app",
            mem_limit="512m",
            memswap_limit="512m",
            network_disabled=True,
            pids_limit=128,
            cpu_period=100000,
            cpu_quota=200000,
            security_opt=["no-new-privileges:true"],
            remove=True,
            stderr=True,
            stdout=True
        )
        stdout = output_bytes.decode('utf-8', errors='replace')

        # 编译错误检测：用唯一标记代替 substring 猜测
        if '___COMPILE_ERROR___' in stdout:
            return 'CE', []

        # 按唯一分隔符拆分各测试点输出
        chunks = stdout.split(sep)
        outputs = [c.strip() for c in chunks if c.strip()]

        # 判定
        if len(outputs) < len(test_cases):
            return 'TLE', outputs

        final_status = 'AC'
        for i, (actual, tc) in enumerate(zip(outputs, test_cases)):
            clean_actual = actual.strip().replace('\r\n', '\n')
            clean_expected = tc.expected_output.strip().replace('\r\n', '\n')
            if clean_actual != clean_expected:
                logger.warning(
                    f"❌ 测试点 {i+1} WA！期望: {repr(clean_expected[:80])} 实际: {repr(clean_actual[:80])}",
                    extra={"task_id": task_id})
                final_status = 'WA'
                break

        return final_status, outputs

    except ContainerError as e:
        if e.exit_status == 124:
            return 'TLE', []
        stderr_str = (
            e.stderr.decode('utf-8', errors='replace')
            if isinstance(e.stderr, bytes)
            else (e.stderr or '')
        )
        stdout_str = (
            e.stdout.decode('utf-8', errors='replace')
            if isinstance(getattr(e, 'stdout', None), bytes)
            else (getattr(e, 'stdout', '') or '')
        )
        combined_output = f"{stdout_str}\n{stderr_str}"
        if '___COMPILE_ERROR___' in combined_output:
            return 'CE', []
        logger.error(
            f"Sandbox container failed with exit_status={e.exit_status}, stderr={stderr_str[:500]}",
            extra={"task_id": task_id},
        )
        return 'RE', []
    except APIError as e:
        logger.error(f"Docker API error while running sandbox: {e}", extra={"task_id": task_id})
        return 'SE', []


# ==========================================
# 守护进程：动态流水线控制
# ==========================================
while True:
    try:
        task = r.brpop("judge_queue", timeout=5)
        if task:
            queue_name, task_json = task
            task_data = json.loads(task_json)
            task_id = task_data.get('task_id', 'unknown')
            language = task_data.get('language', 'python3')
            problem_id = task_data['problem_id']

            logger.info(f"📦 收到任务！正在拉取题目 ID: {problem_id} 的测试点...",
                        extra={"task_id": task_id})

            try:
                problem = Problem.objects.get(id=problem_id)
            except Problem.DoesNotExist:
                logger.error(f"❌ 题目 {problem_id} 不存在", extra={"task_id": task_id})
                r.set(f"task_result:{task_id}", "SE", ex=3600)
                continue

            test_cases = list(TestCase.objects.filter(problem=problem))
            if not test_cases:
                logger.error(f"⚠️ 题目 {problem_id} 未配置测试点",
                             extra={"task_id": task_id})
                r.set(f"task_result:{task_id}", "SE", ex=3600)
                continue

            logger.info(f"🧪 启动沙箱容器，批量评测 {len(test_cases)} 个测试点...",
                        extra={"task_id": task_id})
            final_status, _ = run_all_test_cases(
                task_data['code'], language, test_cases,
                problem.time_limit, task_id
            )

            logger.info(f"✅ 动态评测最终结论: {final_status}",
                        extra={"task_id": task_id})

            # 同步至 Redis：先 set 持久化，再 publish 推送 WebSocket
            try:
                r.set(f"task_result:{task_id}", final_status, ex=3600)
                r.publish(f"task_done:{task_id}", final_status)
            except Exception as pub_err:
                logger.error(f"⚠️ Redis 写入失败: {pub_err}", extra={"task_id": task_id})
                # 尝试仅 set（publish 可能因 pub/sub 状态失败）
                try:
                    r.set(f"task_result:{task_id}", final_status, ex=3600)
                except Exception:
                    pass

            user_id = task_data.get('user_id', 1)
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"❌ 用户 {user_id} 不存在", extra={"task_id": task_id})
                r.set(f"task_result:{task_id}", "SE", ex=3600)
                continue

            Submission.objects.create(
                user=user, problem=problem, code=task_data['code'],
                language=language, status=final_status
            )
            logger.info("💾 评测流水账单已写入数据库。", extra={"task_id": task_id})

    except redis.exceptions.TimeoutError:
        pass
    except redis.exceptions.ConnectionError as e:
        logger.error(f"🔴 Redis 连接断开: {e}，5 秒后重试...",
                     extra={"task_id": "system_error"})
        try:
            time.sleep(5)
            r = redis.Redis(host='redis_db', port=6379, db=0,
                            decode_responses=True,
                            password=os.environ.get('REDIS_PASSWORD', 'redis_dev_pass'))
            logger.info("🟢 Redis 重连成功。", extra={"task_id": "system_error"})
        except Exception as reconnect_error:
            logger.error(f"💀 Redis 重连失败: {reconnect_error}",
                         extra={"task_id": "system_error"})
            time.sleep(10)
    except Exception as e:
        logger.error(f"⚠️ 评测中心未知异常: {e}", extra={"task_id": "system_error"})
        if 'task_id' in locals() and task_id != 'unknown':
            try:
                r.set(f"task_result:{task_id}", "SE", ex=3600)
            except Exception:
                pass
        time.sleep(1)
