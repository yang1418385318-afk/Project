# django_app/Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY . /app

# ==========================================
# 🆕 新增：召唤 Linux 底层编译工具链
# ==========================================
# apt-get update 更新软件源，然后安装编译 mysqlclient 必备的底层包
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/* # 极其细节的大厂操作装完后立刻清空安装包缓存保持镜像极小

# 安装核心依赖
RUN pip install django redis PyJWT docker python-json-logger mysqlclient django-cors-headers pandas -i https://pypi.tuna.tsinghua.edu.cn/simple
# 启动评测机监听
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]