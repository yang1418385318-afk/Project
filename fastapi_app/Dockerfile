# fastapi_app/Dockerfile
FROM python:3.11-slim
WORKDIR /app
# 复制当前目录下所有文件到容器的 /app 目录
COPY . /app
# 安装依赖
RUN pip install fastapi uvicorn redis slowapi pyjwt websockets -i https://pypi.tuna.tsinghua.edu.cn/simple
# 暴露 8080 端口
EXPOSE 8080
# 启动命令 — forwarded-allow-ips 限制为仅信任本地反向代理
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]