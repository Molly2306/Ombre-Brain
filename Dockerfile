FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 拷贝新版多层架构
COPY src/ ./src/
COPY frontend/ ./frontend/
COPY VERSION ./VERSION

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

# 启动新版入口
CMD ["python", "src/server.py"]
