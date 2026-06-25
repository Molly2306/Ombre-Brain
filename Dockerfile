FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝新版多层架构（src 内部已经包含了 VERSION 文件）
COPY src/ ./src/
COPY frontend/ ./frontend/

# 写入配置文件（Zeabur 部署时作为默认配置）
COPY config.example.yaml ./config.yaml

# 时区修正
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 环境与挂载点规范
ENV OMBRE_TRANSPORT=streamable-http
ENV OMBRE_BUCKETS_DIR=/app/buckets
VOLUME ["/app/buckets"]
EXPOSE 8000

# 启动新版入口：一号门与二号门双进程并开通电
CMD python src/server.py & \
    python src/server_extra.py & \
    echo "[OB] 核心主副双连接器已在后台并发拉起，正在监听服务..." && \
    wait -n && \
    exit 1
